"""Real data restoration under newly acquired canonical control descriptors."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_recovery_roles as fixtures
from literate_ai.adapters import retained_layout_recovery_data as data
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)


@unittest.skipUnless(os.name == "posix", "POSIX actual source/metadata recovery")
class RetainedLayoutDataRecoveryTests(unittest.TestCase):
    plan = fixtures.RetainedLayoutRecoveryRoleTests.plan
    pool = fixtures.RetainedLayoutRecoveryRoleTests.pool
    phase = fixtures.RetainedLayoutRecoveryRoleTests.phase
    git = fixtures.RetainedLayoutRecoveryRoleTests.git
    init_git = fixtures.RetainedLayoutRecoveryRoleTests.init_git
    reopened = fixtures.RetainedLayoutRecoveryRoleTests.reopened
    proposal = fixtures.RetainedLayoutRecoveryRoleTests.proposal
    acquire = fixtures.RetainedLayoutRecoveryRoleTests.acquire

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutRecoveryRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutRecoveryRoleTests.setUp(self)
        self.recovery = self.state / "data-recovery"
        self.recovery.mkdir(mode=0o700)

    def interrupted(self, *, metadata=False, finalized=False, stop=None):
        self.original = self.plan()
        self.before = {item.path: item for item in self.original.inputs}
        self.source_inode = self.source.stat().st_ino
        with self.pool(self.original) as (pool, journal):
            append = journal.append

            def interrupted(kind, content):
                result = append(kind, content)
                if kind == stop:
                    raise OSError("controlled original interruption")
                return result

            try:
                with self.phase(self.original, pool) as phase:
                    self.targets = tuple(
                        m.target for m in phase.controls.reservations._markers
                    )
                    with mock.patch.object(journal, "append", side_effect=interrupted):
                        phase.move_source()
                        if metadata or finalized:
                            phase.publish_metadata(self.metadata)
                        if finalized:
                            phase.finalize_controls(self.retired)
            except (ValueError, OSError, transaction.LayoutCommitOutcomeError) as error:
                if finalized and stop is None:
                    raise
                self.assertRegex(
                    str(error), "incomplete|controlled original|commit-outcome"
                )

    @contextmanager
    def owner(self):
        with self.reopened() as (pool, journal, raw):
            proposal = self.proposal(pool, raw)
            with self.acquire(pool, raw, proposal) as roles:
                yield pool, journal, roles

    def apply(self, pool, roles, plan, **overrides):
        return data.apply_layout_data_recovery(
            pool,
            roles,
            plan,
            **{
                "acknowledged_recovery_identity": plan.identity,
                "allow_host_execution": True,
                **overrides,
            },
        )

    def assert_original(self):
        self.assertTrue(self.source.is_dir())
        self.assertEqual(self.source.stat().st_ino, self.source_inode)
        self.assertFalse(self.destination.exists())
        for path, old in self.before.items():
            self.assertEqual(path.read_bytes() if path.exists() else None, old.content)
            if (
                path.relative_to(self.project).as_posix() in data._TARGETS
                and old.signature
            ):
                self.assertEqual(path.stat().st_ino, old.signature[1])
        self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_actual_source_only_interruption_restores_original_directory_inode(self):
        self.interrupted()
        with self.owner() as (pool, journal, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.assertEqual(len(plan.actions), 1)
            result = self.apply(pool, roles, plan)
            self.assertEqual(result["state"], "original-data-restored-controls-pending")
            self.assertFalse(result["complete"])
            self.assertFalse(result["qualified"])
            self.assertEqual(journal.events[-1]["kind"], "data-recovery-observed")
        self.assert_original()

    def test_restoration_preserves_source_links_modes_and_native_nodes(self):
        (self.source / "data").mkdir(mode=0o750)
        tool = self.source / "data/tool"
        tool.write_bytes(b"original executable bytes\n")
        tool.chmod(0o751)
        os.link(tool, self.source / "second-name")
        (self.source / "alias").symlink_to("data/tool")
        (self.source / "directory-alias").symlink_to("data", target_is_directory=True)
        before = data._native_tree(
            data.capture_retained_cargo_tree_v2(self.source, budget=self.budget)
        )
        self.interrupted(metadata=True)
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.apply(pool, roles, plan)
        self.assert_original()
        after = data._native_tree(
            data.capture_retained_cargo_tree_v2(self.source, budget=self.budget)
        )
        self.assertEqual(before[1:], after[1:])
        self.assertEqual(before[0][1].after_rename(), after[0][1].after_rename())
        self.assertEqual(tool.stat().st_nlink, 2)
        self.assertEqual(
            tool.stat().st_ino, (self.source / "second-name").stat().st_ino
        )
        self.assertEqual(os.readlink(self.source / "directory-alias"), "data")

    def test_original_quarantine_effect_before_observation_is_recoverable(self):
        move = transaction.move_layout_entry_exclusive

        def interrupted(source, destination, **kwargs):
            move(source, destination, **kwargs)
            if destination.parent == self.metadata:
                raise OSError("controlled original interruption")

        with mock.patch.object(
            transaction, "move_layout_entry_exclusive", side_effect=interrupted
        ):
            self.interrupted(metadata=True)
        self.assertTrue((self.metadata / "old-0").is_file())
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.apply(pool, roles, plan)
        self.assert_original()

    def test_same_byte_foreign_original_backup_is_preserved(self):
        self.interrupted(metadata=True)
        backup = self.metadata / "old-0"
        retained = self.state / "retained-original"
        backup.rename(retained)
        backup.write_bytes(retained.read_bytes())
        foreign = data.layout_entry_node(backup)
        with self.owner() as (pool, journal, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertTrue(plan.issues)
            history = journal.events
            self.assertEqual(self.apply(pool, roles, plan)["state"], "unresolved")
            self.assertEqual(journal.events, history)
        self.assertEqual(data.layout_entry_node(backup), foreign)
        self.assertTrue(retained.is_file())
        self.assertTrue(self.destination.is_dir())

    def test_original_publication_effect_before_observation_is_recoverable(self):
        move = transaction.move_layout_entry_exclusive

        def interrupted(source, destination, **kwargs):
            move(source, destination, **kwargs)
            if source.parent == self.metadata and source.name.startswith("new-"):
                raise OSError("controlled original interruption")

        with mock.patch.object(
            transaction, "move_layout_entry_exclusive", side_effect=interrupted
        ):
            self.interrupted(metadata=True)
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.apply(pool, roles, plan)
        self.assert_original()

    def test_durable_commit_before_control_release_forbids_rollback(self):
        self.interrupted(finalized=True, stop="layout-commit-observed")
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.assertTrue(plan.committed)
            self.assertEqual(plan.actions, ())
            self.apply(pool, roles, plan)
        self.assertFalse(self.source.exists())
        self.assertTrue(self.destination.is_dir())

    def late_data_observation_change(self, dependency):
        if dependency == "git":
            self.init_git()
        self.interrupted()
        armed, calls, injected = False, 0, False
        with self.assertRaises(ValueError):
            with self.owner() as (pool, journal, roles):
                plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
                append, area = journal.append, data._area
                if dependency == "journal":
                    changed = self.state / "journal/foreign"
                elif dependency == "pool":
                    changed = pool.root / "foreign"
                elif dependency == "git":
                    changed = self.project / ".git/HEAD"
                elif dependency == "project":
                    changed = self.project / data.PROJECT_FILENAME
                else:
                    changed = layout_pending_control_path(self.project)
                expected = b"foreign late dependency"
                if dependency in {"git", "project"}:
                    expected = changed.read_bytes()

                def armed_append(kind, content):
                    nonlocal armed
                    result = append(kind, content)
                    if kind == "data-recovery-entry-intent":
                        armed = True
                    return result

                def changed_area(root):
                    nonlocal calls, injected
                    observed = area(root)
                    if armed and root == self.recovery:
                        calls += 1
                        if calls == 2:
                            if dependency in {"git", "project"}:
                                changed.rename(self.state / "original-input")
                            changed.write_bytes(expected)
                            injected = True
                    return observed

                with (
                    mock.patch.object(journal, "append", side_effect=armed_append),
                    mock.patch.object(data, "_area", side_effect=changed_area),
                ):
                    self.apply(pool, roles, plan)
        self.assertTrue(injected)
        self.assertEqual(changed.read_bytes(), expected)
        self.assertFalse(self.source.exists())
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(self.destination.stat().st_ino, self.source_inode)

    def test_late_private_observation_closes_journal_before_source_effect(self):
        self.late_data_observation_change("journal")

    def test_late_private_observation_closes_pool_before_source_effect(self):
        self.late_data_observation_change("pool")

    def test_late_private_observation_closes_control_before_source_effect(self):
        self.late_data_observation_change("control")

    def test_late_private_observation_closes_git_before_source_effect(self):
        self.late_data_observation_change("git")

    def test_late_private_observation_closes_project_before_source_effect(self):
        self.late_data_observation_change("project")

    def test_published_metadata_restores_original_nodes_and_retains_new_nodes(self):
        self.interrupted(metadata=True)
        new = {
            name: (
                (self.project / name).stat().st_ino,
                (self.project / name).read_bytes(),
            )
            for name in data._TARGETS
        }
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.assertEqual(len(plan.actions), 6)
            self.apply(pool, roles, plan)
        self.assert_original()
        for index, name in enumerate(data._TARGETS):
            path = self.recovery / f"new-{index}"
            self.assertEqual((path.stat().st_ino, path.read_bytes()), new[name])

    def test_first_quarantine_interruption_preserves_unpublished_private_stages(self):
        self.interrupted(metadata=True, stop="metadata-quarantine-observed")
        stages = {
            path: (path.stat().st_ino, path.read_bytes())
            for path in self.metadata.glob("new-*")
        }
        self.assertEqual(len(stages), 3)
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.apply(pool, roles, plan)
        self.assert_original()
        self.assertEqual(
            {path: (path.stat().st_ino, path.read_bytes()) for path in stages}, stages
        )

    def test_durable_committed_layout_is_verified_without_data_rollback(self):
        self.interrupted(finalized=True)
        current = {name: (self.project / name).read_bytes() for name in data._TARGETS}
        inode = self.destination.stat().st_ino
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.assertTrue(plan.committed)
            self.assertEqual(plan.actions, ())
            result = self.apply(pool, roles, plan)
            self.assertEqual(result["state"], "committed-unqualified-controls-pending")
        self.assertEqual(self.destination.stat().st_ino, inode)
        self.assertFalse(self.source.exists())
        self.assertEqual(
            {name: (self.project / name).read_bytes() for name in data._TARGETS},
            current,
        )

    def test_before_original_source_effect_is_verified_from_actual_endpoints(self):
        self.interrupted(stop="source-move-intent")
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            self.assertEqual(plan.actions, ())
            self.apply(pool, roles, plan)
        self.assert_original()

    def test_missing_exact_ack_and_execution_leave_data_and_journal_unchanged(self):
        self.interrupted(metadata=True)
        with self.owner() as (pool, journal, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            history = journal.events
            for overrides in (
                {"allow_host_execution": False},
                {"acknowledged_recovery_identity": None},
            ):
                with self.subTest(overrides=overrides):
                    with self.assertRaises(ValueError):
                        self.apply(pool, roles, plan, **overrides)
            self.assertEqual(journal.events, history)
        self.assertFalse(self.source.exists())
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_forged_recovery_move_cannot_redirect_the_original_source(self):
        self.interrupted()
        unrelated = self.state / "not-source"
        unrelated.mkdir()
        (unrelated / "foreign").write_bytes(b"preserve unrelated")
        with self.owner() as (pool, journal, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            forged = replace(
                plan, actions=(replace(plan.actions[0], source=unrelated),)
            )
            history = journal.events
            with self.assertRaisesRegex(ValueError, "exact fresh"):
                self.apply(pool, roles, forged)
            self.assertEqual(journal.events, history)
        self.assertEqual((unrelated / "foreign").read_bytes(), b"preserve unrelated")
        self.assertFalse(self.source.exists())

    def test_same_byte_foreign_public_metadata_is_retained_as_unresolved(self):
        self.interrupted(metadata=True)
        path = self.project / data._LIFT
        saved = self.state / "actual-published-lift"
        path.rename(saved)
        path.write_bytes(saved.read_bytes())
        foreign = path.stat().st_ino
        with self.owner() as (pool, journal, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertTrue(plan.issues)
            history = journal.events
            result = self.apply(pool, roles, plan)
            self.assertEqual(result["state"], "unresolved")
            self.assertEqual(journal.events, history)
        self.assertEqual(path.stat().st_ino, foreign)
        self.assertEqual(path.read_bytes(), saved.read_bytes())
        self.assertFalse(self.source.exists())

    def test_changed_source_payload_refuses_without_restoring_other_data(self):
        self.interrupted(metadata=True)
        changed = self.destination / "app.py"
        changed.write_bytes(b"concurrent source edit")
        current = {name: (self.project / name).read_bytes() for name in data._TARGETS}
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertTrue(plan.issues)
            self.assertEqual(self.apply(pool, roles, plan)["state"], "unresolved")
        self.assertEqual(changed.read_bytes(), b"concurrent source edit")
        self.assertEqual(
            {name: (self.project / name).read_bytes() for name in data._TARGETS},
            current,
        )

    def test_foreign_old_source_destination_is_preserved(self):
        self.interrupted()
        self.source.mkdir()
        (self.source / "foreign").write_bytes(b"foreign destination")
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertTrue(plan.issues)
            self.assertEqual(self.apply(pool, roles, plan)["state"], "unresolved")
        self.assertEqual((self.source / "foreign").read_bytes(), b"foreign destination")
        self.assertTrue(self.destination.is_dir())

    def test_stale_journal_proposal_cannot_start_recovery_effects(self):
        self.interrupted()
        with self.owner() as (pool, journal, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            journal.append("new-recovery-observation", b"{}")
            history = journal.events
            with self.assertRaisesRegex(ValueError, "exact fresh"):
                self.apply(pool, roles, plan)
            self.assertEqual(journal.events, history)
        self.assertFalse(self.source.exists())

    def test_metadata_changed_during_recovery_intent_is_not_adopted(self):
        self.interrupted(metadata=True)
        changed = self.project / data._LIFT
        with self.assertRaises(ValueError):
            with self.owner() as (pool, journal, roles):
                plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
                append = journal.append

                def altered(kind, content):
                    result = append(kind, content)
                    if kind == "data-recovery-intent":
                        changed.write_bytes(b"concurrent metadata")
                    return result

                with mock.patch.object(journal, "append", side_effect=altered):
                    self.apply(pool, roles, plan)
        self.assertEqual(changed.read_bytes(), b"concurrent metadata")
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(list(self.recovery.iterdir()), [])

    def test_private_insertion_after_recovery_intent_is_preserved_and_refused(self):
        self.interrupted(metadata=True)
        foreign = self.recovery / "foreign"
        with self.assertRaises(ValueError):
            with self.owner() as (pool, journal, roles):
                plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
                append = journal.append

                def altered(kind, content):
                    result = append(kind, content)
                    if kind == "data-recovery-entry-intent":
                        foreign.write_bytes(b"preserve foreign private state")
                    return result

                with mock.patch.object(journal, "append", side_effect=altered):
                    self.apply(pool, roles, plan)
        self.assertEqual(foreign.read_bytes(), b"preserve foreign private state")
        self.assertTrue(self.destination.is_dir())

    def test_recovery_recognizes_real_metadata_move_before_observed_record(self):
        self.interrupted(metadata=True)
        move = data.move_layout_entry_exclusive
        injected = False
        with self.assertRaisesRegex(OSError, "controlled data postmove"):
            with self.owner() as (pool, _, roles):
                plan = data.plan_layout_data_recovery(pool, roles, self.recovery)

                def interrupted(source, destination, **kwargs):
                    nonlocal injected
                    move(source, destination, **kwargs)
                    if not injected:
                        injected = True
                        raise OSError("controlled data postmove")

                with mock.patch.object(
                    data, "move_layout_entry_exclusive", side_effect=interrupted
                ):
                    self.apply(pool, roles, plan)
        self.assertTrue((self.recovery / "new-0").is_file())
        second = self.state / "data-recovery-second"
        second.mkdir(mode=0o700)
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, second)
            self.assertEqual(plan.issues, ())
            self.apply(pool, roles, plan)
        self.assert_original()
        self.assertTrue((self.recovery / "new-0").is_file())

    def test_recovery_recognizes_real_source_restore_before_observed_record(self):
        self.interrupted()
        move = data.move_layout_entry_exclusive
        with self.assertRaisesRegex(OSError, "controlled source postmove"):
            with self.owner() as (pool, _, roles):
                plan = data.plan_layout_data_recovery(pool, roles, self.recovery)

                def interrupted(*args, **kwargs):
                    move(*args, **kwargs)
                    raise OSError("controlled source postmove")

                with mock.patch.object(
                    data, "move_layout_entry_exclusive", side_effect=interrupted
                ):
                    self.apply(pool, roles, plan)
        self.assertTrue(self.source.is_dir())
        second = self.state / "data-recovery-second"
        second.mkdir(mode=0o700)
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, second)
            self.assertEqual(plan.issues, ())
            self.assertEqual(plan.actions, ())
            self.apply(pool, roles, plan)
        self.assert_original()

    def test_completed_recovery_reopens_from_current_nodes_without_saved_success(self):
        self.interrupted(metadata=True)
        with self.owner() as (pool, _, roles):
            self.apply(
                pool, roles, data.plan_layout_data_recovery(pool, roles, self.recovery)
            )
        second = self.state / "data-recovery-second"
        second.mkdir(mode=0o700)
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, second)
            self.assertEqual(plan.issues, ())
            self.assertEqual(plan.actions, ())
            self.apply(pool, roles, plan)
        self.assert_original()

    def test_committed_changed_metadata_never_rolls_back(self):
        self.interrupted(finalized=True)
        changed = self.project / data._LIFT
        changed.write_bytes(b"concurrent committed metadata")
        with self.owner() as (pool, journal, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertTrue(plan.committed)
            self.assertTrue(plan.issues)
            history = journal.events
            self.assertEqual(self.apply(pool, roles, plan)["state"], "unresolved")
            self.assertEqual(journal.events, history)
        self.assertEqual(changed.read_bytes(), b"concurrent committed metadata")
        self.assertFalse(self.source.exists())
        self.assertTrue(self.destination.is_dir())

    def test_expired_role_owner_refuses_before_borrowed_native_fd_access(self):
        self.interrupted()
        with self.owner() as (pool, _, roles):
            plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
        with mock.patch.object(
            os, "fstat", side_effect=AssertionError("expired native FD")
        ):
            with self.assertRaisesRegex(ValueError, "context ended"):
                self.apply(pool, roles, plan)
