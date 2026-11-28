"""Inherited metadata reuse controls; native qualification/receiving is MODELED.

Reuse the original protocol fixture for typed receipts/contracts/manifests. Its
inert lifecycle projection is explicitly modeled to omit inherited plans, as a
real root-only B lifecycle does. No producer-first native proof is claimed.
"""

import os
import shutil
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_qualification as replay
from literate_ai.adapters import native_root_external_runtime as runtime
from tests.critical import test_native_root_external_runtime as runtime_fixture


@unittest.skipUnless(
    os.name == "posix" and shutil.which("git") and shutil.which("make"),
    "receiving fixture requires POSIX/Git/Make",
)
class InheritedQualifiedMetadataTests(unittest.TestCase):
    setUp = runtime_fixture.QualifiedLibraryRuntimeProjectionTests.setUp
    project = runtime_fixture.QualifiedLibraryRuntimeProjectionTests.project

    def inherited(self):
        original = self.project()
        current = self.materialized.current
        previous = current.qualified_library_inputs
        owner = object()
        object.__setattr__(current, "qualified_library_inputs", owner)
        self.addCleanup(
            object.__setattr__, current, "qualified_library_inputs", previous
        )
        # Only inert lifecycle data is modeled; original typed acceptance,
        # export, contract and realized manifest records are reused unchanged.
        lifecycle = SimpleNamespace(project_build_plan=SimpleNamespace(components=()))
        provider = replace(self.provider, lifecycle=lifecycle)
        self.projection.return_value = replace(self.data, providers=(provider,))
        reader = self.enterContext(
            mock.patch.object(
                replay,
                "read_current_qualified_library_replay_data",
                return_value=original,
            )
        )
        return original, owner, reader

    def test_inherited_records_reused_without_expanding_own_execution_maps(self):
        original, owner, reader = self.inherited()
        current = self.materialized.current.current
        commands = current.current_commands
        with mock.patch.object(runtime, "realize_manifest") as realize:
            data = self.project()
        self.assertEqual(data.contracts, original.contracts)
        self.assertEqual(data.manifests, original.manifests)
        self.assertEqual(data.manifest_paths, original.manifest_paths)
        self.assertEqual(data.accepted_receipts, original.accepted_receipts)
        self.assertEqual(data.products, original.products)
        self.assertIs(current.current_commands, commands)
        reader.assert_called_once_with(owner, component_lock=current.authority.lock)
        realize.assert_not_called()

    def test_missing_original_receipt_refuses_instead_of_using_own_commands(self):
        original, _, reader = self.inherited()
        reader.return_value = replace(original, accepted_receipts=())
        with self.assertRaisesRegex(ValueError, "provider_original_metadata_missing"):
            self.project()

    def test_original_inherited_manifest_path_must_match_contract(self):
        original, _, reader = self.inherited()
        reader.return_value = replace(
            original,
            manifest_paths=tuple(
                (revision, "foreign/Cargo.toml")
                for revision, _ in original.manifest_paths
            ),
        )
        with self.assertRaisesRegex(ValueError, "provider_original_metadata_mismatch"):
            self.project()

    def test_callback_cannot_replace_original_inherited_owner(self):
        original, _, reader = self.inherited()

        def substitute(*args, **kwargs):
            object.__setattr__(
                self.materialized.current, "qualified_library_inputs", object()
            )
            return original

        reader.side_effect = substitute
        with self.assertRaisesRegex(ValueError, "provider_inherited_owner_changed"):
            self.project()
        self.assertEqual(reader.call_count, 1)

    def test_last_outer_guard_cannot_replace_inherited_owner(self):
        self.inherited()

        def substitute(*args):
            object.__setattr__(
                self.materialized.current, "qualified_library_inputs", None
            )

        self.guard.side_effect = substitute
        with self.assertRaisesRegex(ValueError, "provider_inherited_owner_changed"):
            self.project()


class RuntimeRecursionBoundaryTests(unittest.TestCase):
    def test_cycle_refuses_before_reentering_projection_and_context_unwinds(self):
        owner = object()

        def recurse(*args):
            return runtime.qualified_library_runtime_data(owner, None)

        with mock.patch.object(
            runtime, "_qualified_library_runtime_data", side_effect=recurse
        ) as project:
            with self.assertRaisesRegex(ValueError, "provider_owner_cycle_or_depth"):
                runtime.qualified_library_runtime_data(owner, None)
            self.assertEqual(project.call_count, 1)
        self.assertEqual(runtime._ACTIVE_RUNTIME_INPUTS.get(), ())

    def test_depth64_refuses_without_callback_and_preserves_outer_context(self):
        active = tuple(object() for _ in range(64))
        token = runtime._ACTIVE_RUNTIME_INPUTS.set(active)
        try:
            with mock.patch.object(
                runtime, "_qualified_library_runtime_data"
            ) as project:
                with self.assertRaisesRegex(
                    ValueError, "provider_owner_cycle_or_depth"
                ):
                    runtime.qualified_library_runtime_data(object(), None)
                project.assert_not_called()
                self.assertIs(runtime._ACTIVE_RUNTIME_INPUTS.get(), active)
        finally:
            runtime._ACTIVE_RUNTIME_INPUTS.reset(token)

    def test_independent_calls_never_reuse_success(self):
        owner = object()
        with mock.patch.object(
            runtime, "_qualified_library_runtime_data", return_value=object()
        ) as project:
            runtime.qualified_library_runtime_data(owner, None)
            runtime.qualified_library_runtime_data(owner, None)
            self.assertEqual(project.call_count, 2)
