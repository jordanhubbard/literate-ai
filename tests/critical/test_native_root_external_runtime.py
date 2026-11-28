"""Runtime projection protocols over real typed fixture records.

Producer qualification and live aggregate guards are MODELED in this layer.
The receiving fixture supplies original typed plans, receipts, exports and
package bytes; its generic build commands are explicitly modeled as Cargo for
projection controls. No native producer/consumer or portable replay is claimed.
"""

import hashlib
import os
import shutil
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_runtime as runtime
from literate_ai.adapters.lifecycle.standard_local import (
    LocalStandardLifecycleError,
    LocalStandardLifecyclePorts,
)
from literate_ai.adapters.models.coding_cli import RecipeFlavor
from literate_ai.adapters.native_root_external_libraries import (
    BorrowedExternalQualifiedLibraries,
    borrow_external_qualified_libraries,
)
from literate_ai.adapters.native_root_qualified_provider import (
    hold_native_root_qualified_provider,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components import ComponentCommandPhase
from literate_ai.contracts.executable_components.assets import AuthoredBinaryAsset
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_root_external_libraries import (
    QUALIFIED_LIBRARY_ASSET_ROLE,
    ExternalQualifiedLibrarySelection,
    NativeRootExternalLibrarySelections,
)
from tests.support.fixtures_retained_cargo_receiving_v2 import (
    initialize_retained_cargo_receiving_v2_fixture,
    receive_retained_cargo_fixture,
)


@unittest.skipUnless(
    os.name == "posix" and shutil.which("git") and shutil.which("make"),
    "receiving fixture requires POSIX/Git/Make",
)
class QualifiedLibraryRuntimeProjectionTests(unittest.TestCase):
    def setUp(self):
        initialize_retained_cargo_receiving_v2_fixture(self)
        self.materialized = receive_retained_cargo_fixture(self)
        self.holder = self.enterContext(
            hold_native_root_qualified_provider(self.materialized)
        )
        provider = self.holder.data_projection()
        surface = provider.product.import_surface
        capability = surface.capabilities[0]
        current = self.materialized.current.current
        selection = ExternalQualifiedLibrarySelection(
            "provider",
            provider.binding.component_revision,
            self.materialized.files.reviewed.binding.identity,
            provider.qualification_result.identity,
            provider.run.run_identity,
            provider.product.identity,
            provider.binding.artifact_export_identities,
            surface.identity,
            capability.capability,
            capability.interface_identity,
            current.importer_project_id,
            current.configured_store_id,
            provider.binding.target_profile_identity,
        )
        content = canonical_json_bytes(
            NativeRootExternalLibrarySelections((selection,)).to_dict()
        )
        self.asset = AuthoredBinaryAsset(
            canonical_identity("consumer"),
            "external-libraries",
            "inputs/provider.json",
            QUALIFIED_LIBRARY_ASSET_ROLE,
            provider.binding.target_profile_identity,
            BlobRef(
                hashlib.sha256(content).hexdigest(),
                len(content),
                media_type="application/json",
            ),
            canonical_identity("consumer-lock"),
        )
        self.inputs = self.enterContext(
            borrow_external_qualified_libraries(
                asset=self.asset,
                content=content,
                consumer_revision=self.asset.component_revision,
                consumer_lock_identity=self.asset.authorization_identity,
                target_profile_identity=self.asset.target_identity,
                holders=((selection.selection_id, self.holder),),
            )
        )
        self.data = self.inputs.data_projection()
        self.guard = self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries, "require_current", autospec=True
            )
        )
        self.projection = self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries,
                "data_projection",
                autospec=True,
                return_value=self.data,
            )
        )
        commands = current.current_commands
        modeled = {}
        for revision, command in commands.items():
            modeled[revision] = replace(
                command,
                commands=tuple(
                    replace(
                        row, argv=(*row.argv, "--manifest-path", "source/Cargo.toml")
                    )
                    if row.phase is ComponentCommandPhase.BUILD
                    else row
                    for row in command.commands
                ),
            )
        object.__setattr__(current, "current_commands", modeled)
        self.addCleanup(object.__setattr__, current, "current_commands", commands)
        self.provider = provider

    def project(self):
        return runtime.qualified_library_runtime_data(
            self.inputs, self.asset.component_revision
        )

    def test_original_complete_receipts_manifests_and_direct_siblings_are_reused(self):
        data = self.project()
        self.assertEqual(
            data.direct_exports,
            tuple(
                sorted(
                    self.provider.root_node.exports,
                    key=lambda value: value.identity.uri,
                )
            ),
        )
        self.assertEqual(data.exports, self.data.exports)
        self.assertEqual(data.accepted_receipts, self.data.accepted_receipts)
        self.assertEqual(
            {manifest.component_revision for manifest in data.manifests},
            {receipt.component_revision for receipt in data.accepted_receipts},
        )
        self.assertEqual(
            {
                export.identity
                for manifest in data.manifests
                for export in manifest.exports
            },
            {export.identity for export in data.exports},
        )
        self.assertEqual(set(dict(data.manifest_paths).values()), {"source/Cargo.toml"})
        self.assertEqual(data.qualified_dependencies, (self.provider.binding,))

    def test_bindings_keep_actual_capability_interface_export_and_consumer_pairs(self):
        data = self.project()
        selection = self.data.selections.selections[0]
        for binding in data.consumer_bindings:
            self.assertEqual(
                binding.consumer_component_revision, self.asset.component_revision
            )
            self.assertEqual(
                binding.provider_component_revision,
                selection.provider_component_revision,
            )
            self.assertEqual(
                (binding.capability, binding.interface_identity),
                (selection.capability, selection.interface_identity),
            )
            self.assertIn(
                binding.artifact_identity, {row.identity for row in data.direct_exports}
            )

    def test_every_independent_projection_delegates_again_without_positive_cache(self):
        self.project()
        first = self.guard.call_count, self.projection.call_count
        self.project()
        self.assertEqual(
            (self.guard.call_count, self.projection.call_count),
            (first[0] + 1, first[1] + 1),
        )
        refusal = RuntimeError("original aggregate expired")
        self.guard.side_effect = refusal
        with self.assertRaises(RuntimeError) as caught:
            self.project()
        self.assertIs(caught.exception, refusal)

    def test_original_command_without_manifest_cannot_be_guessed_from_export_filename(
        self,
    ):
        current = self.materialized.current.current
        # Mutate the selected provider root, not an unrelated current command
        # outside this product's accepted BUILD receipt closure.
        revision = self.provider.root_node.component_revision
        self.assertIn(
            revision,
            {row.component_revision for row in self.provider.accepted_receipts},
        )
        command = current.current_commands[revision]
        altered = dict(current.current_commands)
        altered[command.component_revision] = replace(
            command,
            commands=tuple(
                replace(
                    row,
                    argv=(
                        "{tool}",
                        "fixture-build",
                        "{source_root}",
                        "{object_root}",
                        "{export_path}",
                    ),
                )
                if row.phase is ComponentCommandPhase.BUILD
                else row
                for row in command.commands
            ),
        )
        object.__setattr__(current, "current_commands", altered)
        with self.assertRaisesRegex(ValueError, "provider_manifest_required"):
            self.project()

    def test_foreign_consumer_cannot_reuse_selected_provider_records(self):
        with self.assertRaisesRegex(ValueError, "consumer_mismatch"):
            runtime.qualified_library_runtime_data(
                self.inputs, canonical_identity("foreign")
            )

    def test_ambiguous_provider_revisions_cannot_be_silently_overwritten(self):
        self.projection.return_value = replace(
            self.data, providers=(*self.data.providers, self.data.providers[0])
        )
        with self.assertRaisesRegex(ValueError, "ambiguous_provider_revision"):
            self.project()

    def test_configured_role_cannot_silently_fall_back_without_live_inputs(self):
        snapshot = SimpleNamespace(
            require_unchanged=mock.Mock(),
            authority=SimpleNamespace(
                lock=SimpleNamespace(
                    nodes=(object(),),
                    edges=(),
                    root_revision=self.asset.component_revision,
                )
            ),
        )
        with mock.patch.object(
            runtime, "authored_assets_from_lock", return_value=(self.asset,)
        ):
            with self.assertRaisesRegex(ValueError, "configured_inputs_required"):
                runtime.require_qualified_library_inputs(None, snapshot)
            # A pure metadata refusal does not need a filesystem sweep. A real
            # owner still gets fresh opening and closing snapshot guards.
            snapshot.require_unchanged.assert_not_called()
            runtime.require_qualified_library_inputs(self.inputs, snapshot)
            self.assertEqual(snapshot.require_unchanged.call_count, 2)

    def test_recipe_imports_are_bound_without_changing_consumer_lock_membership(self):
        current = self.materialized.current.current
        recipe = current.current_recipes[self.provider.binding.component_revision]
        snapshot = SimpleNamespace(
            require_unchanged=mock.Mock(),
            authority=SimpleNamespace(
                lock=SimpleNamespace(
                    nodes=(object(),),
                    edges=(),
                    root_revision=self.asset.component_revision,
                )
            ),
        )
        # The consumer is a different root with an independently named surface.
        recipe = replace(
            recipe,
            library_import_surface=None,
            library_dependencies=(),
            flavors=(
                RecipeFlavor(
                    "rust",
                    "implementation.language-ecosystem",
                    "rust",
                    recipe.documents,
                ),
            ),
        )
        with mock.patch.object(
            runtime, "authored_assets_from_lock", return_value=(self.asset,)
        ):
            bound = runtime.bind_qualified_library_recipe(
                recipe, self.inputs, snapshot, self.asset.component_revision
            )
        self.assertEqual(len(snapshot.authority.lock.nodes), 1)
        self.assertEqual(bound.component_lock_identity, recipe.component_lock_identity)
        self.assertEqual(bound.library_dependencies, self.project().recipe_dependencies)
        with mock.patch.object(
            runtime, "authored_assets_from_lock", return_value=(self.asset,)
        ):
            with self.assertRaisesRegex(ValueError, "recipe_provider_conflict"):
                runtime.bind_qualified_library_recipe(
                    bound, self.inputs, snapshot, self.asset.component_revision
                )

    def test_external_rust_provider_does_not_select_another_consumer_language(self):
        current = self.materialized.current.current
        recipe = current.current_recipes[self.provider.binding.component_revision]
        recipe = replace(
            recipe,
            flavors=(
                RecipeFlavor(
                    "javascript",
                    "implementation.language-ecosystem",
                    "javascript",
                    recipe.documents,
                ),
            ),
        )
        snapshot = SimpleNamespace(
            require_unchanged=mock.Mock(),
            authority=SimpleNamespace(
                lock=SimpleNamespace(
                    nodes=(object(),),
                    edges=(),
                    root_revision=self.asset.component_revision,
                )
            ),
        )
        with mock.patch.object(
            runtime, "authored_assets_from_lock", return_value=(self.asset,)
        ):
            with self.assertRaisesRegex(ValueError, "rust_consumer_required"):
                runtime.bind_qualified_library_recipe(
                    recipe, self.inputs, snapshot, self.asset.component_revision
                )


class ExternalExecutableAuthorityBoundaryTests(unittest.TestCase):
    def _blob_ports(self):
        root, lock = canonical_identity("consumer"), canonical_identity("lock")
        reference = BlobRef(hashlib.sha256(b"original").hexdigest(), len(b"original"))
        ports = object.__new__(LocalStandardLifecyclePorts)
        ports.contracts = {
            root.uri: SimpleNamespace(identity=canonical_identity("contract"))
        }
        ports.cargo_targets = {
            root.uri: SimpleNamespace(identity=canonical_identity("cargo-target"))
        }
        ports._checked_runtime_execution_plan = mock.Mock(
            return_value=SimpleNamespace(
                identity=canonical_identity("plan"),
                root_revision=root,
                component_lock_identity=lock,
            )
        )
        ports._exports_by_identity = {}
        owner = object.__new__(BorrowedExternalQualifiedLibraries)
        foreign = object.__new__(BorrowedExternalQualifiedLibraries)
        owner._asset = SimpleNamespace(
            identity=canonical_identity("asset"),
            component_revision=root,
            authorization_identity=lock,
        )
        ports._qualified_library_inputs = owner
        ports._original_qualified_library_inputs = owner
        export = SimpleNamespace(identity=canonical_identity("export"), blob=reference)
        return ports, owner, foreign, reference, SimpleNamespace(exports=(export,))

    def test_absent_asset_and_inputs_do_not_add_legacy_filesystem_guard_calls(self):
        snapshot = SimpleNamespace(
            authority=SimpleNamespace(lock=object()),
            require_unchanged=mock.Mock(
                side_effect=AssertionError("extra legacy scan")
            ),
        )
        with mock.patch.object(runtime, "authored_assets_from_lock", return_value=()):
            runtime.require_qualified_library_inputs(None, snapshot)
        snapshot.require_unchanged.assert_not_called()

    def test_external_metadata_never_becomes_local_executable_contract(self):
        # Protocol values only: this does not construct a qualified input owner.
        root, provider = canonical_identity("consumer"), canonical_identity("provider")
        root_contract = SimpleNamespace(component_revision=root)
        provider_contract = SimpleNamespace(component_revision=provider)
        ports = object.__new__(LocalStandardLifecyclePorts)
        ports.contracts = {root.uri: root_contract}
        ports._qualified_library_data = mock.Mock(
            return_value=SimpleNamespace(contracts=(provider_contract,))
        )
        self.assertIs(ports._contract(root), root_contract)
        with self.assertRaises(LocalStandardLifecycleError):
            ports._contract(provider)
        ports._qualified_library_data.assert_not_called()
        self.assertIs(ports._provider_contract(provider), provider_contract)
        self.assertEqual(ports.contracts, {root.uri: root_contract})
        ports._qualified_library_data.assert_called_once_with()

    def test_projection_callback_substitution_never_dispatches_foreign_blob_reader(
        self,
    ):
        ports, original, foreign, reference, data = self._blob_ports()

        def substitute(*args):
            ports._qualified_library_inputs = foreign
            return data

        with (
            mock.patch.object(
                runtime, "qualified_library_runtime_data", side_effect=substitute
            ),
            mock.patch.object(
                BorrowedExternalQualifiedLibraries, "read_artifact_blob", autospec=True
            ) as reader,
        ):
            with self.assertRaisesRegex(
                LocalStandardLifecycleError, "original external input owner changed"
            ):
                ports.read_artifact_blob(reference)
            reader.assert_not_called()
            self.assertEqual(ports._exports_by_identity, {})

    def test_constructor_owner_cannot_be_replaced_or_removed_before_first_read(self):
        for replacement in ("foreign", "none"):
            with self.subTest(replacement=replacement):
                ports, original, foreign, reference, data = self._blob_ports()
                ports._qualified_library_inputs = (
                    foreign if replacement == "foreign" else None
                )
                with (
                    mock.patch.object(
                        runtime, "qualified_library_runtime_data"
                    ) as projector,
                    mock.patch.object(
                        BorrowedExternalQualifiedLibraries,
                        "read_artifact_blob",
                        autospec=True,
                    ) as reader,
                ):
                    with self.assertRaisesRegex(
                        LocalStandardLifecycleError,
                        "original external input owner changed",
                    ):
                        ports.read_artifact_blob(reference)
                    projector.assert_not_called()
                    reader.assert_not_called()
                    self.assertIs(ports._original_qualified_library_inputs, original)

    def test_original_reader_callback_substitution_is_rejected_on_closing_boundary(
        self,
    ):
        ports, original, foreign, reference, data = self._blob_ports()

        def substitute(owner, requested):
            self.assertIs(owner, original)
            self.assertEqual(requested, reference)
            ports._qualified_library_inputs = foreign
            return b"original"

        with (
            mock.patch.object(
                runtime, "qualified_library_runtime_data", return_value=data
            ),
            mock.patch.object(
                BorrowedExternalQualifiedLibraries,
                "read_artifact_blob",
                autospec=True,
                side_effect=substitute,
            ) as reader,
        ):
            with self.assertRaisesRegex(
                LocalStandardLifecycleError, "original external input owner changed"
            ):
                ports.read_artifact_blob(reference)
            reader.assert_called_once_with(original, reference)
