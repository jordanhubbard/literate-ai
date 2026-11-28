"""Actual shared canonical storage under the original source observation owner."""

from __future__ import annotations

import copy
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
from literate_ai.adapters import component_locks as locks
from literate_ai.adapters import retained_layout_source_admission as admission
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters import retained_layout_transaction as transaction


@unittest.skipUnless(os.name == "posix", "actual external canonical store custody")
class SourceStorageTests(unittest.TestCase):
    prepare = fixtures.SourceAdmissionTests.prepare
    pool = fixtures.SourceAdmissionTests.pool
    inspecting = fixtures.SourceAdmissionTests.inspecting

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        self.metadata_limit = 8 * 1024**3
        self.namesake = self.project / "unclaimed" / "component.lock.json"
        self.namesake.parent.mkdir()
        self.namesake.write_bytes(b"unclaimed stale evidence\n")

    def external(self, *, present):
        self.enterContext(
            mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(self.state)})
        )
        lock = locks.ComponentLockStore(self.source.parent).path
        if present:
            lock.parent.mkdir(parents=True)
            lock.write_bytes(b"stale original external lock evidence\n")
        return lock

    def complete(self, owner, *, callback=None):
        with self.pool(owner.plan) as (pool, _journal):
            with owner.source_phase(
                pool,
                acknowledged_plan_identity=owner.plan.identity,
                allow_host_execution=True,
            ) as phase:
                with phase.complete_partition(
                    budget=self.input_budget,
                    maximum_metadata_bytes=self.metadata_limit,
                ) as partition:
                    self.assertEqual(
                        dict(partition.roles)[
                            self.namesake.relative_to(self.project).as_posix()
                        ],
                        "unclaimed",
                    )
                    phase.move_source()
                phase.publish_metadata(self.metadata)
                result = phase.finalize_controls(self.retired)
                self.assertEqual(result["state"], "committed-unqualified")
                if callback is not None:
                    phase._resources.callback(callback)
            owner.require_current()
        owner.require_current()
        self.assertEqual(self.namesake.read_bytes(), b"unclaimed stale evidence\n")

    def test_existing_external_lock_completes_and_keeps_stale_evidence(self):
        lock = self.external(present=True)
        before = lock.read_bytes()
        with self.prepare() as owner:
            selection = preparation._state(owner).authored.selection
            self.assertEqual(owner.plan.authored_lock, lock)
            self.assertEqual(owner.plan.authored_storage, selection.identity.uri)
            self.assertNotIn(lock, {item.path for item in owner.plan.inputs})
            self.complete(owner)
        self.assertEqual(lock.read_bytes(), before)
        self.assertTrue((self.destination / "app.py").is_file())

    def test_absent_external_storage_completes_without_creating_lock_directories(self):
        lock = self.external(present=False)
        with self.prepare() as owner:
            self.assertEqual(owner.plan.authored_lock, lock)
            self.complete(owner)
        self.assertFalse(lock.parent.exists())
        self.assertTrue((self.destination / "app.py").is_file())

    def test_fresh_legacy_constructor_inside_source_reader_refuses_before_probe(self):
        with self.prepare() as owner:
            with owner._reads():
                with mock.patch.object(
                    locks, "Path", side_effect=AssertionError("unowned path probe")
                ) as path:
                    with self.assertRaisesRegex(
                        locks.ComponentLockStoreError, "original|observation"
                    ):
                        locks.ComponentLockStore(self.source.parent)
                    path.assert_not_called()

    def test_changed_external_lock_refuses_before_source_effects(self):
        lock = self.external(present=True)
        changed = []
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                lock.write_bytes(b"foreign external edit\n")
                changed.append(True)
                owner.require_current()
        self.assertEqual(changed, [True])
        self.assertEqual(lock.read_bytes(), b"foreign external edit\n")
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_late_external_lock_creation_is_not_a_fresh_original_observation(self):
        lock = self.external(present=False)
        changed = []
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                lock.parent.mkdir(parents=True)
                lock.write_bytes(b"foreign late evidence\n")
                changed.append(True)
                owner.require_current()
        self.assertEqual(changed, [True])
        self.assertEqual(lock.read_bytes(), b"foreign late evidence\n")
        self.assertFalse(self.destination.exists())

    def test_copied_forged_and_ended_selection_cannot_reuse_original_reader(self):
        self.external(present=True)
        with self.prepare() as owner:
            selection = preparation._state(owner).authored.selection
            with owner._reads():
                for candidate in (
                    copy.copy(selection),
                    object.__new__(type(selection)),
                ):
                    with self.assertRaises(ValueError):
                        candidate.require_current()
                selection.require_current()
        with self.assertRaises(ValueError):
            selection.require_current()
        with self.assertRaises(ValueError):
            _ = selection.identity

    def test_registered_record_replacement_and_storage_mutation_refuse_before_reads(
        self,
    ):
        from literate_ai.adapters import component_lock_observation as storage
        from literate_ai.adapters import retained_layout_git_controls as native_inputs

        self.external(present=True)
        with self.prepare() as owner:
            selection = preparation._state(owner).authored.selection
            original = storage._OWNERS[selection]
            original_storage = original.storage

            def refuse():
                with mock.patch.object(
                    native_inputs,
                    "_presence",
                    side_effect=AssertionError("changed store reached native input"),
                ) as native:
                    with self.assertRaisesRegex(
                        ValueError, "original canonical record"
                    ):
                        with owner._reads():
                            selection.require_current()
                    native.assert_not_called()

            for changed in (
                copy.copy(original),
                replace(original, storage=original.component),
            ):
                try:
                    storage._OWNERS[selection] = changed
                    refuse()
                finally:
                    storage._OWNERS[selection] = original
            try:
                object.__setattr__(original, "storage", original.component)
                refuse()
            finally:
                object.__setattr__(original, "storage", original_storage)
            with owner._reads():
                selection.require_current()

    def test_mutated_original_payload_witness_refuses_before_any_reread(self):
        from literate_ai.adapters import component_lock_observation as storage
        from literate_ai.adapters import repository_refresh as refresh

        self.external(present=True)
        with self.prepare() as owner:
            selection = preparation._state(owner).authored.selection
            snapshot = storage._OWNERS[selection].snapshot
            original = snapshot.content
            try:
                object.__setattr__(snapshot, "content", b"forged original payload\n")
                with mock.patch.object(
                    refresh,
                    "_raw_file",
                    side_effect=AssertionError("changed witness reached payload read"),
                ) as native:
                    with self.assertRaisesRegex(
                        ValueError, "canonical observation fields"
                    ):
                        with owner._reads():
                            selection.require_current()
                    native.assert_not_called()
            finally:
                object.__setattr__(snapshot, "content", original)

    def test_foreign_active_reader_cannot_close_original_storage_native_facts(self):
        from literate_ai.adapters import bounded_role_observation as reads
        from literate_ai.adapters import retained_layout_git_controls as native_inputs

        self.external(present=True)
        with self.prepare() as owner:
            selection = preparation._state(owner).authored.selection
            with reads.bounded_role_observation(
                budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
            ):
                with mock.patch.object(
                    native_inputs,
                    "_presence",
                    side_effect=AssertionError(
                        "foreign reader reached original native input"
                    ),
                ) as native:
                    with self.assertRaisesRegex(ValueError, "foreign active reader"):
                        selection.close_native()
                    native.assert_not_called()
            owner.require_current()

    def test_bound_selection_cannot_advance_into_another_storage_root(self):
        from literate_ai.adapters import component_lock_observation as storage

        self.external(present=True)
        with self.prepare() as owner:
            selection = preparation._state(owner).authored.selection
            original = storage._OWNERS[selection]
            with owner._reads():
                with self.assertRaisesRegex(ValueError, "immutable"):
                    storage._advance(selection, original, storage=original.component)
                self.assertIs(storage._OWNERS[selection], original)
                selection.require_current()

    def test_external_lock_inside_private_pool_refuses_before_control_acquisition(self):
        pool_root = self.state / "stages"
        pool_root.mkdir(mode=0o700, exist_ok=True)
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(pool_root)}):
            with self.assertRaisesRegex(
                ValueError, "canonical.*private|private.*canonical"
            ):
                with self.prepare() as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail("canonical storage admitted inside private pool")
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_metadata_area_containing_external_storage_refuses_before_writes(self):
        with mock.patch.dict(
            os.environ, {"LITAI_MATRIX_CELL_ROOT": str(self.metadata)}
        ):
            with self.assertRaises(ValueError) as caught:
                with self.prepare() as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with phase.complete_partition(
                                budget=self.input_budget,
                                maximum_metadata_bytes=self.metadata_limit,
                            ):
                                phase.move_source()
                            phase.publish_metadata(self.metadata)
        causes = self.causes(caught.exception)
        self.assertTrue(any("canonical" in str(error) for error in causes))
        self.assertEqual(list(self.metadata.iterdir()), [])
        self.assertTrue((self.destination / "app.py").is_file())

    def test_actual_last_admitted_native_close_revokes_selection_before_move(self):
        from literate_ai.adapters import component_lock_observation as storage

        self.external(present=True)
        revoked = []
        with self.assertRaises(ValueError) as caught:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with phase.complete_partition(
                            budget=self.input_budget,
                            maximum_metadata_bytes=self.metadata_limit,
                        ):
                            original = transaction._close_tree

                            def revoke(tree, native, **kwargs):
                                target = kwargs.get("_admitted_source_phase") is phase
                                if target:
                                    record = admission._phase_record(phase)
                                    self.assertIs(record.span[0], tree)
                                result = original(tree, native, **kwargs)
                                if target and not revoked:
                                    storage._BOUND.pop(owner)
                                    revoked.append(True)
                                return result

                            with mock.patch.object(transaction, "_close_tree", revoke):
                                owner.require_current()
        self.assertEqual(
            revoked,
            [True],
            [str(error) for error in self.causes(caught.exception)],
        )
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_actual_external_edit_after_descriptor_teardown_refuses_terminal_success(
        self,
    ):
        lock = self.external(present=True)
        changed = []

        def edit():
            content = b"foreign teardown edit\n"
            self.assertEqual(lock.write_bytes(content), len(content))
            self.assertEqual(lock.read_bytes(), content)
            changed.append(True)

        with self.assertRaises(Exception) as caught:
            with self.prepare() as owner:
                self.complete(owner, callback=edit)
        self.assertEqual(changed, [True])
        self.assertIs(getattr(caught.exception, "committed", None), True)
        self.assertTrue(
            any(
                "input changed" in str(error) for error in self.causes(caught.exception)
            )
        )
        self.assertEqual(lock.read_bytes(), b"foreign teardown edit\n")
        self.assertTrue((self.destination / "app.py").is_file())

    @staticmethod
    def causes(error):
        result = []
        while error is not None and error not in result:
            result.append(error)
            error = error.__cause__ or error.__context__
        return result
