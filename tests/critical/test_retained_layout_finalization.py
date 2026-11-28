"""Actual normal nonroot control handoff, not fresh recovery/feature acceptance."""

from __future__ import annotations

import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

import tests.critical.test_retained_layout_transaction as source_fixtures
from literate_ai.adapters import retained_layout_reservations as reservations
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.lifecycle_lock import (
    ProjectLifecycleLockError,
    project_lifecycle_lock,
)
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "POSIX normal transaction finalization")
class RetainedLayoutFinalizationTests(unittest.TestCase):
    plan = source_fixtures.RetainedLayoutTransactionTests.plan
    pool = source_fixtures.RetainedLayoutTransactionTests.pool
    phase = source_fixtures.RetainedLayoutTransactionTests.phase
    git = source_fixtures.RetainedLayoutTransactionTests.git
    init_git = source_fixtures.RetainedLayoutTransactionTests.init_git

    @classmethod
    def setUpClass(cls):
        source_fixtures.RetainedLayoutTransactionTests.setUpClass.__func__(cls)

    def setUp(self):
        source_fixtures.RetainedLayoutTransactionTests.setUp(self)
        self.metadata = self.state / "metadata"
        self.retired = self.state / "retired"
        self.metadata.mkdir(mode=0o700)
        self.retired.mkdir(mode=0o700)

    def test_normal_nonroot_completion_keeps_advisory_inodes_locked_until_exit(self):
        plan = self.plan()
        existing = self.project / ".literate/conversion-authority.lock"
        existing_bytes, existing_inode = existing.read_bytes(), existing.stat().st_ino
        with self.pool(plan) as (pool, journal):
            with self.phase(plan, pool) as phase:
                owned = phase.controls.reservations
                before = {
                    m.target.path: (m.node, m.created, m.target.advisory, m.content)
                    for m in owned._markers
                }
                self.assertTrue(layout_pending_control_path(self.project).exists())
                phase.move_source()
                phase.publish_metadata(self.metadata)
                result = phase.finalize_controls(self.retired)
                self.assertEqual(result["state"], "committed-unqualified")
                self.assertFalse(result["qualified"])
                with self.assertRaises(ProjectLifecycleLockError):
                    with project_lifecycle_lock(self.project, operation="contender"):
                        self.fail("canonical mutex released before context exit")
                for path, (node, created, advisory, content) in before.items():
                    if advisory:
                        self.assertEqual(path.stat().st_ino, node[1])
                        self.assertEqual(
                            path.read_bytes(), b"\0" if created else content
                        )
                    else:
                        self.assertFalse(path.exists())
                with self.assertRaisesRegex(ValueError, "unspent finalization"):
                    phase.finalize_controls(self.retired)
            self.assertEqual(journal.events[-1]["kind"], "layout-finalization-observed")
        with project_lifecycle_lock(self.project, operation="after-finalization"):
            pass
        self.assertEqual(existing.read_bytes(), existing_bytes)
        self.assertEqual(existing.stat().st_ino, existing_inode)
        self.assertFalse(layout_pending_control_path(self.project).exists())
        self.assertTrue((self.metadata / "old-0").is_file())
        self.assertTrue(list(self.retired.iterdir()))
        self.assertEqual(
            json.loads((self.project / transaction._LIFT).read_bytes())["state"],
            "requalification-required",
        )

    def test_native_git_writer_can_resume_after_handoff_without_invalidating_commit(
        self,
    ):
        self.init_git()
        self.git("add", self.source.relative_to(self.project).as_posix())
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.phase(plan, pool) as phase:
                phase.move_source()
                phase.publish_metadata(self.metadata)
                phase.finalize_controls(self.retired)
                self.assertEqual(self.git("add", "retained", check=False).returncode, 0)
                phase.controls.reservations.verify_finalized()
        self.assertFalse((self.project / ".git/index.lock").exists())
        self.assertTrue(self.destination.is_dir())

    def test_pending_control_refuses_another_plan_after_incomplete_metadata_phase(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
        self.assertTrue(layout_pending_control_path(self.project).is_file())
        with self.assertRaisesRegex(ValueError, "pending transaction"):
            transaction.plan_retained_layout_source_move(
                self.project, "another", budget=self.budget
            )

    def test_partial_advisory_normalization_retains_busy_pending_and_same_inode(self):
        plan = self.plan()
        truncate = os.ftruncate
        selected = None
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(OSError, "controlled truncate interruption"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    selected = next(
                        m
                        for m in phase.controls.reservations._markers
                        if m.target.advisory and m.created
                    )
                    inode = selected.target.path.stat().st_ino

                    def interrupted(fd, size):
                        if fd == selected.descriptor:
                            raise OSError("controlled truncate interruption")
                        return truncate(fd, size)

                    with mock.patch.object(
                        reservations.os, "ftruncate", side_effect=interrupted
                    ):
                        phase.finalize_controls(self.retired)
        self.assertEqual(selected.target.path.stat().st_ino, inode)
        self.assertTrue(selected.target.path.read_bytes().startswith(b"\0"))
        self.assertTrue(layout_pending_control_path(self.project).exists())
        with self.assertRaisesRegex(ValueError, "pending transaction"):
            transaction.plan_retained_layout_source_move(
                self.project, "another", budget=self.budget
            )

    def _foreign_device_preflight(self, *, reservation_owner):
        """Controlled stat-device projection; all descriptors/writes remain native."""
        plan = self.plan()
        native = self.retired.lstat()
        identity = native.st_dev, native.st_ino

        def projected(call):
            def observe(*args, **kwargs):
                info = call(*args, **kwargs)
                if (info.st_dev, info.st_ino) != identity:
                    return info
                fields = {
                    name: getattr(info, name)
                    for name in dir(info)
                    if name.startswith("st_")
                }
                fields["st_dev"] = native.st_dev + 1
                return SimpleNamespace(**fields)

            return observe

        with self.pool(plan) as (pool, journal):
            with self.assertRaisesRegex(ValueError, "one filesystem"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    before = {
                        m.target.path: (m.target.path.stat().st_ino, m.content)
                        for m in phase.controls.reservations._markers
                    }
                    with (
                        mock.patch.object(os, "stat", side_effect=projected(os.stat)),
                        mock.patch.object(os, "lstat", side_effect=projected(os.lstat)),
                        mock.patch.object(os, "fstat", side_effect=projected(os.fstat)),
                    ):
                        if reservation_owner:
                            phase.controls.reservations.begin_finalization(self.retired)
                        else:
                            phase.finalize_controls(self.retired)
            self.assertFalse(
                any(
                    e["kind"]
                    in {
                        "advisory-normalization-intent",
                        "native-control-retirement-intent",
                        "control-finalization-intent",
                    }
                    for e in journal.events
                )
            )
        for path, (inode, content) in before.items():
            self.assertEqual(path.stat().st_ino, inode)
            self.assertEqual(path.read_bytes(), content)
        self.assertEqual(list(self.retired.iterdir()), [])
        self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_source_finalizer_refuses_projected_foreign_device_before_normalization(
        self,
    ):
        self._foreign_device_preflight(reservation_owner=False)

    def test_reservation_owner_refuses_projected_foreign_device_before_normalization(
        self,
    ):
        self._foreign_device_preflight(reservation_owner=True)

    def test_foreign_retirement_namespace_is_not_collected(self):
        foreign = self.retired / "foreign"
        foreign.write_bytes(b"foreign state")
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "not empty"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
        self.assertEqual(foreign.read_bytes(), b"foreign state")
        self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_changed_source_during_release_intent_prevents_any_control_handoff(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "layout-finalization-intent":
                    (self.destination / "app.py").write_bytes(
                        b"changed before control release"
                    )
                return result

            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.finalize_controls(self.retired)
            self.assertFalse(
                any(
                    e["kind"] == "advisory-normalization-intent" for e in journal.events
                )
            )
        self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_same_byte_foreign_pending_inode_is_not_retired(self):
        plan = self.plan()
        pending = layout_pending_control_path(self.project)
        displaced = self.state / "actual-pending"
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "native-control-retirement-intent":
                    pending.rename(displaced)
                    pending.write_bytes(displaced.read_bytes())
                return result

            with self.assertRaises(transaction.LayoutCommitOutcomeError) as caught:
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.finalize_controls(self.retired)
            self.assertTrue(caught.exception.committed)
            self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertEqual(pending.read_bytes(), displaced.read_bytes())
        self.assertNotEqual(pending.stat().st_ino, displaced.stat().st_ino)

    def test_source_destination_cannot_swallow_canonical_runtime_control(self):
        with self.assertRaisesRegex(ValueError, "mixed-partition"):
            transaction.plan_retained_layout_source_move(
                self.project, "LITAI", budget=self.budget
            )

    def test_declared_source_cannot_reclassify_actual_framework_metadata(self):
        declaration = transaction.RetainedLayoutDeclaration(
            "components/legacy-project-wrapper", ".literate", (), None
        )
        (self.project / transaction.RETAINED_LAYOUT_PATH).write_bytes(
            canonical_json_bytes(declaration.to_dict()) + b"\n"
        )
        lift_path = self.project / transaction._LIFT
        lift = json.loads(lift_path.read_bytes())
        lift.update(
            implementation_directory=".literate",
            wrapper_component=declaration.wrapper_component,
            layout_identity=declaration.identity,
            previous_layout_identity=None,
        )
        lift_path.write_bytes(canonical_json_bytes(lift) + b"\n")
        wrapper = self.project / transaction.HARNESS_WRAPPER_FILENAME
        wrapper.write_bytes(
            wrapper.read_bytes().replace(
                b"LITAI_LEGACY := components/legacy-project-wrapper/implementation\n",
                b"LITAI_LEGACY := .literate\n",
            )
        )
        with self.assertRaisesRegex(ValueError, "mixed-partition|framework metadata"):
            self.plan()
        self.assertTrue(
            (self.project / ".literate/conversion-authority.json").is_file()
        )
        self.assertFalse(self.destination.exists())

    def test_native_retirement_posteffect_failure_preserves_real_token_and_pending(
        self,
    ):
        self.init_git()
        plan = self.plan()
        move = reservations.move_layout_entry_exclusive
        injected = False
        with self.pool(plan) as (pool, journal):
            with self.assertRaisesRegex(
                OSError, "controlled native retirement interruption"
            ):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)

                    def interrupted(source, destination, **kwargs):
                        nonlocal injected
                        move(source, destination, **kwargs)
                        if not injected and destination.parent == self.retired:
                            injected = True
                            raise OSError("controlled native retirement interruption")

                    with mock.patch.object(
                        reservations,
                        "move_layout_entry_exclusive",
                        side_effect=interrupted,
                    ):
                        phase.finalize_controls(self.retired)
            self.assertEqual(
                journal.events[-1]["kind"], "native-control-retirement-intent"
            )
        self.assertTrue(injected)
        self.assertTrue(list(self.retired.iterdir()))
        self.assertTrue(layout_pending_control_path(self.project).is_file())

    def test_late_journal_failure_reports_committed_without_a_pending_barrier(self):
        plan = self.plan()
        pending = layout_pending_control_path(self.project)
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def interrupted(kind, content):
                if kind == "layout-finalization-observed":
                    raise OSError("controlled late journal failure")
                return append(kind, content)

            with self.assertRaises(Exception) as caught:
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    with mock.patch.object(journal, "append", side_effect=interrupted):
                        phase.finalize_controls(self.retired)
            self.assertIs(getattr(caught.exception, "committed", "missing"), True)
            self.assertIs(caught.exception.qualified, False)
            self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertFalse(phase._finalized)
            self.assertFalse(pending.exists())
            kinds = [event["kind"] for event in journal.events]
            self.assertIn("layout-commit-observed", kinds)
            self.assertEqual(kinds[-1], "native-control-retirement-observed")
        # A new plan is legitimate for the actually committed unqualified layout.
        transaction.plan_retained_layout_source_move(
            self.project, "another", budget=self.budget
        )

    def test_commit_record_attempt_failure_reports_unknown_and_preserves_pending(self):
        for after_effect in (False, True):
            with self.subTest(after_effect=after_effect):
                # Each subcase needs a fresh source/metadata transaction.
                if after_effect:
                    self.setUp()
                plan = self.plan()
                with self.pool(plan) as (pool, journal):
                    append = journal.append

                    def interrupted(
                        kind, content, *, after_effect=after_effect, append=append
                    ):
                        if kind == "layout-commit-observed":
                            if after_effect:
                                append(kind, content)
                            raise OSError("controlled commit append interruption")
                        return append(kind, content)

                    with self.assertRaises(Exception) as caught:
                        with self.phase(plan, pool) as phase:
                            phase.move_source()
                            phase.publish_metadata(self.metadata)
                            with mock.patch.object(
                                journal, "append", side_effect=interrupted
                            ):
                                phase.finalize_controls(self.retired)
                    self.assertIs(
                        getattr(caught.exception, "committed", "missing"), None
                    )
                    self.assertFalse(caught.exception.qualified)
                    self.assertIsInstance(caught.exception.__cause__, OSError)
                    self.assertTrue(layout_pending_control_path(self.project).exists())
                    kinds = [event["kind"] for event in journal.events]
                    self.assertEqual("layout-commit-observed" in kinds, after_effect)
                with self.assertRaisesRegex(ValueError, "pending transaction"):
                    transaction.plan_retained_layout_source_move(
                        self.project, "another", budget=self.budget
                    )

    def test_last_pending_move_then_failure_reports_committed_and_retains_token(self):
        plan = self.plan()
        pending = layout_pending_control_path(self.project)
        move = reservations.move_layout_entry_exclusive
        with self.pool(plan) as (pool, journal):
            with self.assertRaises(Exception) as caught:
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    token = pending.read_bytes()

                    def interrupted(source, destination, **kwargs):
                        move(source, destination, **kwargs)
                        if source == pending:
                            raise OSError("controlled pending post-move failure")

                    with mock.patch.object(
                        reservations,
                        "move_layout_entry_exclusive",
                        side_effect=interrupted,
                    ):
                        phase.finalize_controls(self.retired)
            self.assertIs(getattr(caught.exception, "committed", "missing"), True)
            self.assertFalse(pending.exists())
            self.assertIn(token, [path.read_bytes() for path in self.retired.iterdir()])
            self.assertIn("layout-commit-observed", [e["kind"] for e in journal.events])

    def test_context_output_conflict_after_commit_keeps_committed_error_outcome(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaises(Exception) as caught:
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
                    (self.destination / "app.py").write_bytes(b"post-commit conflict")
            self.assertIs(getattr(caught.exception, "committed", "missing"), True)
            self.assertFalse(caught.exception.qualified)
            self.assertIsInstance(caught.exception.__cause__, ValueError)
        self.assertEqual(
            (self.destination / "app.py").read_bytes(), b"post-commit conflict"
        )

    def test_context_resource_release_failure_keeps_committed_error_outcome(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaises(Exception) as caught:
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)

                    def interrupted():
                        raise OSError("controlled resource release failure")

                    phase._resources.callback(interrupted)
            self.assertIs(getattr(caught.exception, "committed", "missing"), True)
            self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_post_commit_keyboard_interrupt_preserves_interrupt_and_outcome_note(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaises(KeyboardInterrupt) as caught:
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
                    raise KeyboardInterrupt("controlled post-commit interruption")
            self.assertTrue(
                any(
                    "committed-unqualified" in note
                    for note in caught.exception.__notes__
                )
            )

    def test_old_private_writer_and_live_role_claims_expire_after_completed_context(
        self,
    ):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.phase(plan, pool) as phase:
                phase.move_source()
                phase.publish_metadata(self.metadata)
                phase.finalize_controls(self.retired)
                area = phase._retirement_area
                with self.assertRaisesRegex(ValueError, "control role context ended"):
                    phase.controls.require_current()
            with self.assertRaisesRegex(ValueError, "context ended"):
                area.require_current()
            with self.assertRaises(ValueError):
                phase.controls.reservations.verify_finalized()
