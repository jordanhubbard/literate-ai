"""Actual recovery control effects, live mutex lifetime and interrupted reentry."""

from __future__ import annotations

import os
import shutil
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_recovery_data as fixtures
from literate_ai.adapters import retained_layout_recovery_controls as controls
from literate_ai.adapters import retained_layout_recovery_data as data
from literate_ai.adapters import retained_layout_recovery_disposition as disposition
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_journal import _LayoutJournalWriter


@unittest.skipUnless(os.name == "posix", "POSIX actual recovery disposition")
class RetainedLayoutRecoveryDispositionTests(unittest.TestCase):
    plan = fixtures.RetainedLayoutDataRecoveryTests.plan
    pool = fixtures.RetainedLayoutDataRecoveryTests.pool
    phase = fixtures.RetainedLayoutDataRecoveryTests.phase
    git = fixtures.RetainedLayoutDataRecoveryTests.git
    init_git = fixtures.RetainedLayoutDataRecoveryTests.init_git
    reopened = fixtures.RetainedLayoutDataRecoveryTests.reopened
    proposal = fixtures.RetainedLayoutDataRecoveryTests.proposal
    acquire = fixtures.RetainedLayoutDataRecoveryTests.acquire
    owner = fixtures.RetainedLayoutDataRecoveryTests.owner
    interrupted = fixtures.RetainedLayoutDataRecoveryTests.interrupted
    probe_mutex = fixtures.fixtures.RetainedLayoutRecoveryRoleTests.probe_mutex

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutDataRecoveryTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutDataRecoveryTests.setUp(self)
        self.disposals = self.state / "control-recovery"
        self.disposals.mkdir(mode=0o700)
        self.counter = 0

    def fresh_data(self, pool, roles):
        self.counter += 1
        private = self.state / f"verified-{self.counter}"
        private.mkdir(mode=0o700)
        return data.plan_layout_data_recovery(pool, roles, private)

    def restore(self, pool, roles):
        plan = data.plan_layout_data_recovery(pool, roles, self.recovery)
        self.assertEqual(plan.issues, ())
        data.apply_layout_data_recovery(
            pool,
            roles,
            plan,
            acknowledged_recovery_identity=plan.identity,
            allow_host_execution=True,
        )
        return self.fresh_data(pool, roles)

    def prepare(self, pool, roles, state=None):
        return disposition.plan_recovery_control_disposition(
            pool, roles, state or self.fresh_data(pool, roles), self.disposals
        )

    def apply(self, pool, roles, plan, **overrides):
        return disposition.apply_recovery_control_disposition(
            pool,
            roles,
            plan,
            **{
                "acknowledged_recovery_identity": plan.identity,
                "allow_host_execution": True,
                **overrides,
            },
        )

    def test_actual_restoration_releases_pending_keeps_same_locked_advisories(self):
        self.interrupted(metadata=True)
        with self.owner() as (pool, journal, roles):
            state = self.restore(pool, roles)
            plan = self.prepare(pool, roles, state)
            before = {
                e.target.path: (e.node.inode, e.content, e.original_content)
                for e in plan.entries
                if e.target.advisory
            }
            result = self.apply(pool, roles, plan)
            self.assertTrue(result["internal_recovery_complete"])
            self.assertFalse(result["qualified"])
            self.assertFalse(layout_pending_control_path(self.project).exists())
            for path, (inode, content, original) in before.items():
                self.assertEqual(path.stat().st_ino, inode)
                self.assertEqual(
                    path.read_bytes(),
                    b"\0" if original.startswith(disposition._PREFIX) else content,
                )
                self.assertEqual(self.probe_mutex(path).returncode, 23)
            with self.assertRaises(ValueError):
                roles.require_current()
            for owner in roles.reservations._recovered:
                owner.verify_all()
            self.assertEqual(
                journal.events[-1]["kind"], "recovery-control-disposition-observed"
            )
        for path in before:
            self.assertEqual(self.probe_mutex(path).returncode, 0)
        self.assertEqual(self.source.stat().st_ino, self.source_inode)
        self.assertFalse(self.destination.exists())
        for path, old in self.before.items():
            self.assertEqual(path.read_bytes() if path.exists() else None, old.content)

    def test_committed_layout_supplemental_controls_release_without_rollback(self):
        self.interrupted(finalized=True)
        inode = self.destination.stat().st_ino
        with self.owner() as (pool, _, roles):
            state = self.fresh_data(pool, roles)
            self.assertTrue(state.committed)
            plan = self.prepare(pool, roles, state)
            self.assertIsNotNone(roles.reservations._incoming)
            result = self.apply(pool, roles, plan)
            self.assertEqual(result["state"], "committed-unqualified")
            with mock.patch.object(
                disposition.os,
                "fstat",
                side_effect=AssertionError("revoked incoming writer FD access"),
            ):
                with self.assertRaisesRegex(ValueError, "handed off"):
                    roles.reservations._incoming.begin_finalization(self.disposals)
        self.assertEqual(self.destination.stat().st_ino, inode)
        self.assertFalse(self.source.exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_ack_execution_and_unrestored_data_refuse_without_effects(self):
        self.interrupted()
        with self.owner() as (pool, journal, roles):
            with self.assertRaisesRegex(ValueError, "fully verified"):
                self.prepare(pool, roles)
            state = self.restore(pool, roles)
            plan = self.prepare(pool, roles, state)
            history = journal.events
            for overrides in (
                {"allow_host_execution": False},
                {"acknowledged_recovery_identity": None},
            ):
                with self.assertRaises(ValueError):
                    self.apply(pool, roles, plan, **overrides)
            self.assertEqual(history, journal.events)
            self.assertTrue(layout_pending_control_path(self.project).exists())
            self.assertEqual(list(self.disposals.iterdir()), [])

    def test_native_git_pending_is_last_after_durable_recovery_decision(self):
        self.init_git()
        self.interrupted(metadata=True)
        with self.owner() as (pool, journal, roles):
            plan = self.prepare(pool, roles, self.restore(pool, roles))
            self.apply(pool, roles, plan)
            intents = [
                e
                for e in journal.events
                if e["kind"] == "recovery-control-retirement-intent"
            ]
            decision = next(
                e
                for e in journal.events
                if e["kind"] == "recovery-control-release-decision"
            )
            self.assertGreater(len(intents), 1)
            self.assertEqual(
                intents[-1]["data"]["source"],
                str(layout_pending_control_path(self.project)),
            )
            self.assertLess(intents[-2]["sequence"], decision["sequence"])
            self.assertLess(decision["sequence"], intents[-1]["sequence"])

    def test_real_native_move_before_observation_reopens_exact_private_node(self):
        self.interrupted()
        move = disposition.move_layout_entry_exclusive
        with self.assertRaises(disposition.RecoveryDispositionOutcomeError):
            with self.owner() as (pool, _, roles):
                plan = self.prepare(pool, roles, self.restore(pool, roles))

                def interrupted(source, destination, **kwargs):
                    move(source, destination, **kwargs)
                    raise OSError("controlled recovery retirement postmove")

                with mock.patch.object(
                    disposition, "move_layout_entry_exclusive", side_effect=interrupted
                ):
                    self.apply(pool, roles, plan)
        retired = tuple(self.disposals.iterdir())
        self.assertEqual(len(retired), 1)
        inode = retired[0].stat().st_ino
        self.disposals = self.state / "control-recovery-retry"
        self.disposals.mkdir(mode=0o700)
        with self.owner() as (pool, _, roles):
            plan = self.prepare(pool, roles)
            self.assertIsNotNone(roles.reservations._incoming)
            self.apply(pool, roles, plan)
        self.assertEqual(retired[0].stat().st_ino, inode)
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_partial_same_fd_normalization_reopens_and_completes(self):
        self.interrupted()
        truncate = disposition.os.ftruncate
        injected = False
        with self.assertRaisesRegex(OSError, "controlled recovery truncate"):
            with self.owner() as (pool, _, roles):
                plan = self.prepare(pool, roles, self.restore(pool, roles))

                def interrupted(fd, length):
                    nonlocal injected
                    if not injected:
                        injected = True
                        raise OSError("controlled recovery truncate")
                    return truncate(fd, length)

                with mock.patch.object(
                    disposition.os, "ftruncate", side_effect=interrupted
                ):
                    self.apply(pool, roles, plan)
        self.assertTrue(injected)
        self.assertTrue(layout_pending_control_path(self.project).exists())
        self.disposals = self.state / "control-recovery-retry"
        self.disposals.mkdir(mode=0o700)
        with self.owner() as (pool, _, roles):
            plan = self.prepare(pool, roles)
            self.apply(pool, roles, plan)
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_fresh_ordinary_source_transaction_reenters_after_recovery_exit(self):
        self.interrupted(metadata=True)
        with self.owner() as (pool, _, roles):
            self.apply(
                pool, roles, self.prepare(pool, roles, self.restore(pool, roles))
            )
        old_state = self.state
        self.state = old_state / "ordinary"
        self.state.mkdir(mode=0o700)
        for name in ("stages", "metadata", "retired"):
            (self.state / name).mkdir(mode=0o700)
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.phase(plan, pool) as phase:
                phase.move_source()
                phase.publish_metadata(self.state / "metadata")
                result = phase.finalize_controls(self.state / "retired")
                self.assertEqual(result["state"], "committed-unqualified")
        self.assertFalse(layout_pending_control_path(self.project).exists())
        self.assertTrue(self.destination.is_dir())

    def test_linked_worktree_recovery_holds_actual_registration_control(self):
        self.init_git(commit=True)
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "--detach", str(linked))
        shutil.copytree(
            self.project,
            linked,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        source = self.source.relative_to(self.project)
        self.project = linked
        self.source, self.destination = linked / source, linked / "retained"
        self.interrupted()
        with self.owner() as (pool, _, roles):
            plan = self.prepare(pool, roles, self.restore(pool, roles))
            locked = roles.git.files.git_directory / "locked"
            self.assertTrue(locked.is_file())
            self.apply(pool, roles, plan)
            self.assertFalse(locked.exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_live_bindings_immutable_and_cached_writer_expires_before_fd_access(self):
        self.interrupted()
        with self.owner() as (pool, journal, roles):
            plan = self.prepare(pool, roles, self.restore(pool, roles))
            append = journal.append
            actor = None

            def checked(kind, content):
                nonlocal actor
                result = append(kind, content)
                if kind == "recovery-control-normalization-intent":
                    actor = roles._disposition
                    for name in (
                        "roles",
                        "pool",
                        "plan",
                        "owners",
                        "entries",
                        "areas",
                        "native_released",
                    ):
                        with self.assertRaises(AttributeError):
                            setattr(actor, name, object())
                    with self.assertRaises(ValueError):
                        roles.require_current()
                return result

            with mock.patch.object(journal, "append", side_effect=checked):
                self.apply(pool, roles, plan)
            self.assertIsNotNone(actor)
            with mock.patch.object(
                disposition.os, "fstat", side_effect=AssertionError("expired FD access")
            ):
                with self.assertRaisesRegex(ValueError, "writer context ended"):
                    actor.normalize(plan.entries[0])

    def test_foreign_private_insertion_after_intent_is_preserved_before_write(self):
        self.interrupted()
        foreign = self.disposals / "foreign"
        with self.assertRaises(ValueError):
            with self.owner() as (pool, journal, roles):
                plan = self.prepare(pool, roles, self.restore(pool, roles))
                before = {e.named: e.content for e in plan.entries}
                append = journal.append

                def changed(kind, content):
                    result = append(kind, content)
                    if kind == "recovery-control-normalization-intent":
                        foreign.write_bytes(b"foreign private node")
                    return result

                with mock.patch.object(journal, "append", side_effect=changed):
                    self.apply(pool, roles, plan)
        self.assertEqual(foreign.read_bytes(), b"foreign private node")
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_late_private_observation_closes_git_before_first_token_write(self):
        self.init_git()
        self.interrupted()
        head = self.project / ".git/HEAD"
        original = self.state / "original-head"
        armed = injected = False
        with self.assertRaises(ValueError):
            with self.owner() as (pool, journal, roles):
                plan = self.prepare(pool, roles, self.restore(pool, roles))
                before = {e.named: e.content for e in plan.entries}
                append, area = journal.append, disposition._recovery_area

                def armed_append(kind, content):
                    nonlocal armed
                    result = append(kind, content)
                    if kind == "recovery-control-normalization-intent":
                        armed = True
                    return result

                def changed(root):
                    nonlocal injected
                    result = area(root)
                    if armed and not injected:
                        head.rename(original)
                        head.write_bytes(original.read_bytes())
                        injected = True
                    return result

                with (
                    mock.patch.object(journal, "append", side_effect=armed_append),
                    mock.patch.object(
                        disposition, "_recovery_area", side_effect=changed
                    ),
                ):
                    self.apply(pool, roles, plan)
        self.assertTrue(injected)
        self.assertNotEqual(head.stat().st_ino, original.stat().st_ino)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_decision_attempt_error_reports_unknown_and_reopens_durable_facts(self):
        self.interrupted()
        with self.assertRaises(disposition.RecoveryDispositionOutcomeError) as raised:
            with self.owner() as (pool, journal, roles):
                plan = self.prepare(pool, roles, self.restore(pool, roles))
                append = journal.append

                def interrupted(kind, content):
                    result = append(kind, content)
                    if kind == "recovery-control-release-decision":
                        raise OSError("controlled durable decision return failure")
                    return result

                with mock.patch.object(journal, "append", side_effect=interrupted):
                    self.apply(pool, roles, plan)
        self.assertIsNone(raised.exception.decision)
        self.assertTrue(layout_pending_control_path(self.project).exists())
        self.disposals = self.state / "control-recovery-retry"
        self.disposals.mkdir(mode=0o700)
        with self.owner() as (pool, _, roles):
            self.apply(pool, roles, self.prepare(pool, roles))
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_foreign_retired_inode_replacement_remains_unresolved(self):
        self.interrupted()
        with self.owner() as (pool, _, roles):
            self.apply(
                pool, roles, self.prepare(pool, roles, self.restore(pool, roles))
            )
        retired = next(self.disposals.iterdir())
        retained = self.state / "original-retired"
        retired.rename(retained)
        retired.write_bytes(retained.read_bytes())
        foreign = disposition.layout_entry_node(retired)
        with self.assertRaises(ValueError):
            with self.owner():
                self.fail("foreign retirement must not gain actual descriptors")
        self.assertEqual(disposition.layout_entry_node(retired), foreign)
        self.assertTrue(retained.is_file())

    def test_final_private_observation_preserves_concurrent_advisory_bytes(self):
        self.interrupted()
        armed, injected, calls = False, False, 0
        with self.assertRaises(ValueError):
            with self.owner() as (pool, journal, roles):
                plan = self.prepare(pool, roles, self.restore(pool, roles))
                advisory = disposition._actions(plan.entries)[0][0].named
                append, area = journal.append, disposition._recovery_area

                def armed_append(kind, content):
                    nonlocal armed
                    result = append(kind, content)
                    if kind == "recovery-control-normalization-intent":
                        armed = True
                    return result

                def changed(root):
                    nonlocal injected, calls
                    result = area(root)
                    if armed and root == self.disposals:
                        calls += 1
                        if calls == 2:
                            advisory.write_bytes(b"foreign concurrent advisory bytes")
                            injected = True
                    return result

                with (
                    mock.patch.object(journal, "append", side_effect=armed_append),
                    mock.patch.object(
                        disposition, "_recovery_area", side_effect=changed
                    ),
                ):
                    self.apply(pool, roles, plan)
        self.assertTrue(injected)
        self.assertEqual(advisory.read_bytes(), b"foreign concurrent advisory bytes")
        self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_actual_raw_fd_close_failure_retains_durable_recovery_outcome(self):
        self.interrupted()
        close = disposition.os.close
        target = None
        injected = False

        def interrupted(fd):
            nonlocal injected
            close(fd)
            if fd == target and not injected:
                injected = True
                raise OSError("controlled failure after actual raw marker close")

        with self.assertRaises(disposition.RecoveryDispositionOutcomeError) as raised:
            with mock.patch.object(disposition.os, "close", side_effect=interrupted):
                with self.owner() as (pool, _, roles):
                    target = roles.reservations._recovered[0]._markers[0].descriptor
                    self.apply(
                        pool,
                        roles,
                        self.prepare(pool, roles, self.restore(pool, roles)),
                    )
        self.assertTrue(injected)
        self.assertEqual(
            raised.exception.decision, "original-data-restored-unqualified"
        )
        self.assertIsNotNone(raised.exception.__cause__)
        with self.assertRaises(OSError):
            os.fstat(target)
        self.assertFalse(layout_pending_control_path(self.project).exists())
        self.assertEqual(self.source.stat().st_ino, self.source_inode)

    def test_actual_raw_directory_close_failure_retains_durable_outcome(self):
        self.interrupted()
        close = disposition.os.close
        target = None
        changed = False

        def closing(fd):
            nonlocal changed
            close(fd)
            if fd == target and not changed:
                changed = True
                raise OSError("controlled local directory close failure")

        with self.assertRaises(disposition.RecoveryDispositionOutcomeError) as raised:
            with mock.patch.object(disposition.os, "close", side_effect=closing):
                with self.owner() as (pool, _, roles):
                    self.apply(
                        pool,
                        roles,
                        self.prepare(pool, roles, self.restore(pool, roles)),
                    )
                    target = roles.reservations._recovered[0]._held.nodes[
                        self.disposals
                    ][0]
        self.assertTrue(changed)
        self.assertEqual(
            raised.exception.decision, "original-data-restored-unqualified"
        )
        self.assertIsNotNone(raised.exception.__cause__)
        with self.assertRaises(OSError):
            os.fstat(target)
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_postdecision_role_exit_conflict_retains_outcome_and_foreign_source(self):
        self.interrupted()
        with self.assertRaises(disposition.RecoveryDispositionOutcomeError) as raised:
            with self.owner() as (pool, _, roles):
                self.apply(
                    pool, roles, self.prepare(pool, roles, self.restore(pool, roles))
                )
                (self.source / "foreign-after-release").write_bytes(
                    b"retain foreign source"
                )
        self.assertEqual(
            raised.exception.decision, "original-data-restored-unqualified"
        )
        self.assertEqual(
            (self.source / "foreign-after-release").read_bytes(),
            b"retain foreign source",
        )

    def test_postdecision_interrupt_preserves_type_and_durable_decision_note(self):
        self.interrupted()
        move = disposition.move_layout_entry_exclusive
        with self.assertRaises(KeyboardInterrupt) as raised:
            with self.owner() as (pool, _, roles):
                plan = self.prepare(pool, roles, self.restore(pool, roles))

                def interrupted(source, destination, **kwargs):
                    move(source, destination, **kwargs)
                    raise KeyboardInterrupt("controlled actual retirement interrupt")

                with mock.patch.object(
                    disposition, "move_layout_entry_exclusive", side_effect=interrupted
                ):
                    self.apply(pool, roles, plan)
        self.assertTrue(
            any(
                "original-data-restored-unqualified" in note
                for note in raised.exception.__notes__
            )
        )
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_factory_key_cannot_construct_missing_actual_descriptor_coverage(self):
        self.interrupted()
        with self.owner() as (pool, _, roles):
            plan = self.prepare(pool, roles, self.restore(pool, roles))
            owners = disposition._owners(roles)
            with self.assertRaisesRegex(ValueError, "complete current"):
                disposition._RecoveryDisposition(
                    disposition._KEY,
                    pool,
                    roles,
                    replace(plan, entries=plan.entries[:-1]),
                    owners,
                )
            with self.assertRaisesRegex(ValueError, "actual disposition factory"):
                disposition._RecoveryDisposition(
                    disposition._KEY,
                    pool,
                    roles,
                    plan,
                    (),
                )
            roles.require_current()
            self.assertTrue(layout_pending_control_path(self.project).exists())

    def raw_closing_change(self, *, journal_node=False):
        self.interrupted()
        with self.owner() as (pool, _, roles):
            plan = self.prepare(pool, roles, self.restore(pool, roles))
            advisory = next(e.named for e in plan.entries if e.target.advisory)
            self.apply(pool, roles, plan)
        armed, injected, yielded, calls = False, False, False, 0
        append, area = _LayoutJournalWriter.append, controls._recovery_area
        foreign = (
            self.state / "journal/foreign-after-area" if journal_node else advisory
        )

        def armed_append(writer, kind, content):
            nonlocal armed
            result = append(writer, kind, content)
            if kind == "control-recovery-acquisition-observed":
                armed = True
            return result

        def changed(root):
            nonlocal injected, calls
            result = area(root)
            if armed and root == self.disposals:
                calls += 1
                if calls == 2:
                    foreign.write_bytes(b"foreign after recovery area")
                    injected = True
            return result

        with self.assertRaises(ValueError):
            with (
                mock.patch.object(_LayoutJournalWriter, "append", new=armed_append),
                mock.patch.object(controls, "_recovery_area", side_effect=changed),
            ):
                with self.reopened():
                    yielded = True
        self.assertTrue(injected)
        self.assertFalse(yielded)
        self.assertEqual(foreign.read_bytes(), b"foreign after recovery area")

    def test_fresh_raw_acquisition_closes_markers_after_new_retirement_area(self):
        self.raw_closing_change()

    def test_fresh_raw_acquisition_closes_journal_after_new_retirement_area(self):
        self.raw_closing_change(journal_node=True)

    def test_canonical_roles_close_git_after_shared_retirement_observations(self):
        self.init_git()
        self.interrupted()
        with self.owner() as (pool, _, roles):
            self.apply(
                pool, roles, self.prepare(pool, roles, self.restore(pool, roles))
            )
        head = self.project / ".git/HEAD"
        retained = self.state / "original-head-at-role-close"
        armed, changed, returned = False, False, False
        with self.assertRaises(ValueError):
            with self.owner() as (_, _, roles):
                observer = type(roles.git)
                close, area = observer.close_native_inputs, controls._recovery_area

                def checked(instance, reservations=None):
                    nonlocal armed
                    result = close(instance, reservations)
                    if instance is roles.git:
                        armed = True
                    return result

                def observed(root):
                    nonlocal changed
                    result = area(root)
                    if armed and not changed:
                        head.rename(retained)
                        head.write_bytes(retained.read_bytes())
                        changed = True
                    return result

                with (
                    mock.patch.object(observer, "close_native_inputs", new=checked),
                    mock.patch.object(controls, "_recovery_area", side_effect=observed),
                ):
                    roles.require_current()
                    returned = True
        self.assertTrue(changed)
        self.assertFalse(returned)
        self.assertEqual(head.read_bytes(), retained.read_bytes())
        self.assertNotEqual(head.stat().st_ino, retained.stat().st_ino)

    def test_control_writer_closes_source_after_last_retirement_observation(self):
        self.interrupted()
        armed, changed, calls = False, False, 0
        with self.assertRaises(ValueError):
            with self.owner() as (pool, journal, roles):
                plan = self.prepare(pool, roles, self.restore(pool, roles))
                advisory = disposition._actions(plan.entries)[0][0]
                append, area = journal.append, disposition._recovery_area

                def armed_append(kind, content):
                    nonlocal armed
                    result = append(kind, content)
                    if kind == "recovery-control-normalization-intent":
                        armed = True
                    return result

                def observed(root):
                    nonlocal changed, calls
                    result = area(root)
                    if armed and root == self.disposals:
                        calls += 1
                        if calls == 2:
                            (self.source / "late-application-input").write_bytes(
                                b"keep this source"
                            )
                            changed = True
                    return result

                with (
                    mock.patch.object(journal, "append", side_effect=armed_append),
                    mock.patch.object(
                        disposition, "_recovery_area", side_effect=observed
                    ),
                ):
                    self.apply(pool, roles, plan)
        self.assertTrue(changed)
        self.assertEqual(advisory.named.read_bytes(), advisory.content)
        self.assertEqual(
            (self.source / "late-application-input").read_bytes(), b"keep this source"
        )

    def test_cold_data_verification_closes_source_after_retirement_observations(self):
        self.interrupted()
        with self.owner() as (pool, _, roles):
            self.apply(
                pool, roles, self.prepare(pool, roles, self.restore(pool, roles))
            )
        armed, closed, changed, returned = False, False, False, False
        error = None
        try:
            with self.owner() as (pool, journal, roles):
                state = self.fresh_data(pool, roles)
                append, close, area = (
                    journal.append,
                    data._close_data,
                    controls._recovery_area,
                )

                def armed_append(kind, content):
                    nonlocal armed
                    result = append(kind, content)
                    if kind == "data-recovery-observed":
                        armed = True
                    return result

                def data_closed(snapshot):
                    nonlocal closed
                    result = close(snapshot)
                    if armed:
                        closed = True
                    return result

                def observed(root):
                    nonlocal changed
                    result = area(root)
                    if closed and not changed:
                        (self.source / "late-application-input").write_bytes(
                            b"keep this source"
                        )
                        changed = True
                    return result

                with (
                    mock.patch.object(journal, "append", side_effect=armed_append),
                    mock.patch.object(data, "_close_data", side_effect=data_closed),
                    mock.patch.object(controls, "_recovery_area", side_effect=observed),
                ):
                    data.apply_layout_data_recovery(
                        pool,
                        roles,
                        state,
                        acknowledged_recovery_identity=state.identity,
                        allow_host_execution=True,
                    )
                    returned = True
        except ValueError as failure:
            error = failure
        if changed:
            self.assertIsNotNone(error)
            self.assertFalse(returned)
            self.assertEqual(
                (self.source / "late-application-input").read_bytes(),
                b"keep this source",
            )
        else:
            # Moving all full retirement observations before source closure
            # removes this old interleaving altogether. No later full-area
            # traversal may be hidden inside the final Git owned-lock query.
            self.assertIsNone(error)
            self.assertTrue(returned)
            self.assertFalse((self.source / "late-application-input").exists())

    def producer_read_source_change(self, *, cold=False):
        self.interrupted()
        if cold:
            with self.owner() as (pool, _, roles):
                self.apply(
                    pool, roles, self.prepare(pool, roles, self.restore(pool, roles))
                )
        armed, closed, changed, returned = False, False, False, False
        with self.assertRaises(ValueError):
            with self.owner() as (pool, journal, roles):
                if cold:
                    state = self.fresh_data(pool, roles)
                    provider = data
                else:
                    plan = self.prepare(pool, roles, self.restore(pool, roles))
                    entry = disposition._actions(plan.entries)[0][0]
                    provider = disposition
                append, close, names = journal.append, provider._close_data, pool._names

                def armed_append(kind, content):
                    nonlocal armed
                    result = append(kind, content)
                    if kind == (
                        "data-recovery-observed"
                        if cold
                        else "recovery-control-normalization-intent"
                    ):
                        armed = True
                    return result

                def data_closed(snapshot):
                    nonlocal closed
                    result = close(snapshot)
                    if armed:
                        closed = True
                    return result

                def observed_names():
                    nonlocal changed
                    result = names()
                    if closed and not changed:
                        (self.source / "late-producer-input").write_bytes(
                            b"preserve source"
                        )
                        changed = True
                    return result

                with (
                    mock.patch.object(journal, "append", side_effect=armed_append),
                    mock.patch.object(provider, "_close_data", side_effect=data_closed),
                    mock.patch.object(pool, "_names", side_effect=observed_names),
                ):
                    if cold:
                        data.apply_layout_data_recovery(
                            pool,
                            roles,
                            state,
                            acknowledged_recovery_identity=state.identity,
                            allow_host_execution=True,
                        )
                    else:
                        self.apply(pool, roles, plan)
                    returned = True
        self.assertTrue(changed)
        self.assertFalse(returned)
        self.assertEqual(
            (self.source / "late-producer-input").read_bytes(), b"preserve source"
        )
        if not cold:
            self.assertEqual(entry.named.read_bytes(), entry.content)

    def test_control_source_close_follows_last_producer_directory_read(self):
        self.producer_read_source_change()

    def test_cold_data_close_follows_last_producer_directory_read(self):
        self.producer_read_source_change(cold=True)
