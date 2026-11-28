"""Actual packaged callback custody with modeled stages, never native success.

The executor entry is controlled and stopped after exercising its actual supplied
source/package callback. No native command, outcome or qualification is produced.
"""

import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from literate_ai.adapters import rust_library_harness_execution as execution
from literate_ai.adapters.lifecycle.standard_local import (
    LocalComponentToolBinding,
    local_tree_identity,
)
from tests.critical import test_native_root_adapter_custody as custody_fixture
from tests.critical import test_native_root_binding as binding_fixture


class _ExecutorBoundary(RuntimeError):
    pass


@unittest.skipUnless(os.name == "posix", "owned local POSIX protocol fixture")
class NativeRootPackagedGuardTests(unittest.TestCase):
    setUp = binding_fixture.NativeRootBindingTests.setUp
    observe = binding_fixture.NativeRootBindingTests.observe
    metadata = binding_fixture.NativeRootBindingTests.metadata
    library_current = binding_fixture.NativeRootBindingTests.library_current
    native_protocol = binding_fixture.NativeRootBindingTests.native_protocol
    opened = binding_fixture.NativeRootBindingTests.opened
    modeled_registered_candidate = (
        binding_fixture.NativeRootBindingTests.modeled_registered_candidate
    )
    late_controller = custody_fixture.NativeRootAdapterCustodyTests.late_controller

    @contextmanager
    def subject(self):
        with self.late_controller() as (controller, arguments):
            custody = arguments[1]
            custody.root = self.fixture.export
            custody.tree_identity = local_tree_identity(custody.root)
            export = self.ports._planned_exports[self.lock.root_revision.uri]
            custody.artifact_paths = {export.identity.uri: custody.root}
            yield controller, arguments

    def invoke(self, controller, arguments, action=None):
        calls = []

        @contextmanager
        def controlled_executor(*_args, **kwargs):
            current = kwargs["require_library_current"]
            current()
            calls.append(True)
            if action is not None:
                action(controller, arguments[1])
            current()
            calls.append(True)
            raise _ExecutorBoundary("controlled executor entry; no native observation")
            yield  # pragma: no cover - makes this a context-manager protocol

        with mock.patch.object(
            execution, "_observe_rust_library_harness_outcome", controlled_executor
        ):
            self.ports._accept_library_observed(
                *arguments, controller.contexts, _native_root_controller=controller
            )
        return calls

    def test_original_callback_has_fresh_custody_without_ambient_native_probes(self):
        with self.subject() as (controller, arguments):
            with (
                mock.patch.object(
                    LocalComponentToolBinding,
                    "require_unchanged",
                    side_effect=AssertionError("ambient observer must not run"),
                ) as ambient,
                self.assertRaises(_ExecutorBoundary),
            ):
                self.invoke(controller, arguments)
            ambient.assert_not_called()

    def test_later_real_package_byte_change_refuses(self):
        with self.subject() as (controller, arguments):

            def change(_controller, custody):
                (custody.root / "src/lib.rs").write_bytes(b"// changed package bytes\n")

            with self.assertRaisesRegex(RuntimeError, "immutable package custody"):
                self.invoke(controller, arguments, change)

    def test_later_original_command_byte_change_refuses(self):
        with self.subject() as (controller, arguments):

            def change(_controller, _custody):
                path = Path(self.cargo.command[0])
                self.assertTrue(path.is_relative_to(self.root))
                path.write_bytes(b"changed owned command bytes\n")

            with self.assertRaises(RuntimeError) as caught:
                self.invoke(controller, arguments, change)
            self.assertNotIsInstance(caught.exception, _ExecutorBoundary)

    def test_later_controller_package_binding_change_refuses(self):
        with self.subject() as (controller, arguments):

            def change(original, _custody):
                custody_fixture.NativeRootAdapterCustodyTests.replace_package_result(
                    self, original
                )

            with self.assertRaisesRegex(RuntimeError, "controller changed"):
                self.invoke(controller, arguments, change)

    def test_noncontroller_keeps_original_ambient_observer(self):
        with self.subject() as (_controller, arguments):
            failure = _ExecutorBoundary("legacy ambient observation")
            with (
                mock.patch.object(
                    LocalComponentToolBinding, "require_unchanged", side_effect=failure
                ) as ambient,
                self.assertRaises(_ExecutorBoundary) as caught,
            ):
                self.ports._accept_library_observed(*arguments, _controller.contexts)
            self.assertIs(caught.exception, failure)
            ambient.assert_called_once()
