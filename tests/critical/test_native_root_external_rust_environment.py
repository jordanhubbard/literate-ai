"""External compile imports are not process capabilities; currentness modeled."""

import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_runtime as runtime
from literate_ai.adapters.lifecycle.standard_local import (
    LocalStandardLifecycleError,
    LocalStandardLifecyclePorts,
)
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_native_root_external_physical_roots as roots_fixture


class ExternalRustEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.ports, self.owner, self.foreign, self.export, self.data = (
            roots_fixture.PortsPhysicalRootTests.ports(self)
        )
        self.contract = SimpleNamespace(
            component_revision=self.export.component_revision,
            is_library=True,
            library_import_surface=SimpleNamespace(language="rust"),
        )
        self.data.contracts = (self.contract,)
        self.ports.provider_environment = {}
        self.projector = self.enterContext(
            mock.patch.object(
                runtime, "qualified_library_runtime_data", return_value=self.data
            )
        )

    def test_exact_selected_rust_import_needs_no_runtime_environment_binding(self):
        self.assertEqual(self.ports._provider_environment_values((self.export,)), {})
        self.assertEqual(self.ports.provider_environment, {})
        self.assertEqual(self.ports._artifact_paths, {})
        self.assertEqual(
            set(self.ports.contracts), {self.owner._asset.component_revision.uri}
        )
        self.assertEqual(
            set(self.ports.cargo_targets), {self.owner._asset.component_revision.uri}
        )

    def test_absent_original_owner_keeps_old_unbound_provider_error(self):
        self.ports._qualified_library_inputs = (
            self.ports._original_qualified_library_inputs
        ) = None
        with self.assertRaisesRegex(LocalStandardLifecycleError, "no runtime binding"):
            self.ports._provider_environment_values((self.export,))
        self.projector.assert_not_called()

    def test_nonselected_library_cannot_hide_an_unbound_runtime_provider(self):
        foreign = replace(self.export, export_id="unselected")
        with self.assertRaisesRegex(LocalStandardLifecycleError, "no runtime binding"):
            self.ports._provider_environment_values((foreign,))

    def test_non_rust_projection_is_refused_instead_of_skipped(self):
        self.contract.library_import_surface.language = "python"
        with self.assertRaisesRegex(
            LocalStandardLifecycleError, "native Rust import authority"
        ):
            self.ports._provider_environment_values((self.export,))

    def test_owner_substitution_during_projection_refuses_without_path_lookup(self):
        def change(*args):
            self.ports._qualified_library_inputs = self.foreign
            return self.data

        self.projector.side_effect = change
        with self.assertRaisesRegex(
            LocalStandardLifecycleError, "original external input owner changed"
        ):
            self.ports._provider_environment_values((self.export,))
        self.assertEqual(self.ports._artifact_paths, {})

    def test_empty_provider_list_preserves_no_observation_legacy_behavior(self):
        ports = object.__new__(LocalStandardLifecyclePorts)
        self.assertEqual(ports._provider_environment_values(()), {})
        self.projector.assert_not_called()

    def test_transitive_selected_exports_all_use_their_original_native_import_channel(
        self,
    ):
        child = replace(
            self.export,
            component_revision=canonical_identity("child"),
            export_id="child",
        )
        root = replace(self.export, dependency_artifact_identities=(child.identity,))
        self.data.exports = (root, child)
        self.data.contracts = (
            self.contract,
            SimpleNamespace(
                component_revision=child.component_revision,
                is_library=True,
                library_import_surface=SimpleNamespace(language="rust"),
            ),
        )
        self.assertEqual(self.ports._provider_environment_values((root,)), {})
        self.assertEqual(
            set(self.ports._exports_by_identity),
            {root.identity.uri, child.identity.uri},
        )
        self.assertEqual(self.ports.provider_environment, {})
