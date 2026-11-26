"""Original method descriptor custody; qualification/receiving is MODELED."""

import unittest
from unittest import mock

from literate_ai.adapters import native_root_external_libraries as borrowed
from literate_ai.adapters import native_root_external_runtime as runtime
from literate_ai.adapters import native_root_qualified_provider as held
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    RetainedCargoMaterializationV2,
)
from tests.critical import test_native_root_external_physical_roots as physical


class BorrowedMethodCustodyTests(unittest.TestCase):
    def setUp(self):
        self.ports, self.owner, self.foreign, self.export, self.data = (
            physical.PortsPhysicalRootTests.ports(self)
        )

    def test_original_helper_binds_exact_factory_method_without_dynamic_lookup(self):
        actual = borrowed._original_borrowed_artifact_path(self.owner)
        self.assertIs(actual.__self__, self.owner)
        self.assertIs(actual.__func__, borrowed._BORROWED_ARTIFACT_PATH_FUNCTION)

    def test_class_swap_before_first_ports_call_refuses_without_foreign_dispatch(self):
        foreign = mock.Mock()
        with (
            mock.patch.object(
                borrowed.BorrowedExternalQualifiedLibraries, "artifact_path", foreign
            ),
            mock.patch.object(runtime, "qualified_library_runtime_data") as projector,
        ):
            with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                self.ports.artifact_path(self.export)
            projector.assert_not_called()
            foreign.assert_not_called()

    def test_callback_class_swap_refuses_this_and_next_ports_operation(self):
        foreign = mock.Mock()
        patcher = mock.patch.object(
            borrowed.BorrowedExternalQualifiedLibraries, "artifact_path", foreign
        )
        started = False

        def change(*args):
            nonlocal started
            patcher.start()
            started = True
            return self.data

        try:
            with mock.patch.object(
                runtime, "qualified_library_runtime_data", side_effect=change
            ) as projector:
                with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                    self.ports.artifact_path(self.export)
                with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                    self.ports.artifact_path(self.export)
                self.assertEqual(projector.call_count, 1)
                foreign.assert_not_called()
        finally:
            if started:
                patcher.stop()

    def test_owner_function_slot_cannot_become_a_new_baseline(self):
        foreign = mock.Mock()
        self.owner._artifact_path_function = foreign
        with mock.patch.object(runtime, "qualified_library_runtime_data") as projector:
            with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                self.ports.artifact_path(self.export)
            projector.assert_not_called()
            foreign.assert_not_called()

    def test_factory_refuses_modified_descriptor_before_admitting_any_input(self):
        foreign = mock.Mock()
        with mock.patch.object(
            borrowed.BorrowedExternalQualifiedLibraries, "artifact_path", foreign
        ):
            with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                with borrowed.borrow_external_qualified_libraries(
                    asset=object(),
                    content=b"",
                    consumer_revision=None,
                    consumer_lock_identity=None,
                    target_profile_identity=None,
                    holders=(),
                ):
                    self.fail("must not enter")
            foreign.assert_not_called()


class HeldMethodCustodyTests(unittest.TestCase):
    setUp = physical.AggregatePhysicalRootTests.setUp
    aggregate = physical.AggregatePhysicalRootTests.aggregate

    def test_aggregate_callback_class_swap_never_invokes_foreign_holder(self):
        owner = self.aggregate()
        foreign = mock.Mock()
        patcher = mock.patch.object(
            held.HeldNativeRootQualifiedProvider, "artifact_path", foreign
        )
        data = self.projector.return_value
        started = False

        def change():
            nonlocal started
            patcher.start()
            started = True
            return data

        self.projector.side_effect = change
        try:
            with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                owner.artifact_path(self.export)
            self.guard.assert_not_called()
            foreign.assert_not_called()
            self.assertFalse(owner._active)
            with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                held._original_held_artifact_path(self.holder)
        finally:
            if started:
                patcher.stop()

    def test_captured_original_bound_method_still_checks_current_descriptor(self):
        original = held._original_held_artifact_path(self.holder)
        foreign = mock.Mock()
        with mock.patch.object(
            held.HeldNativeRootQualifiedProvider, "artifact_path", foreign
        ):
            with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                original(self.export)
            self.guard.assert_not_called()
            foreign.assert_not_called()

    def test_factory_refuses_modified_descriptor_before_foreign_current_callback(self):
        materialized = object.__new__(RetainedCargoMaterializationV2)
        foreign = mock.Mock()
        with (
            mock.patch.object(
                held.HeldNativeRootQualifiedProvider, "artifact_path", foreign
            ),
            mock.patch.object(
                RetainedCargoMaterializationV2, "require_unchanged"
            ) as current,
        ):
            with self.assertRaisesRegex(ValueError, "artifact_path_method_changed"):
                with held.hold_native_root_qualified_provider(materialized):
                    self.fail("must not enter")
            foreign.assert_not_called()
            current.assert_not_called()
