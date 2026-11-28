"""Physical roots/callback custody; qualification/live holders are MODELED.

Real typed exports, immutable ZIP blobs and RetainedPackageTree file custody are
used. No fixture here qualifies a native producer or grants consumer execution.
"""

import hashlib
import os
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_libraries as borrowed_bridge
from literate_ai.adapters import native_root_external_runtime as runtime
from literate_ai.adapters import native_root_qualified_provider as held_bridge
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    encode_directory_export,
)
from literate_ai.adapters.lifecycle.standard_local import (
    LocalStandardLifecycleError,
    LocalStandardLifecyclePorts,
)
from literate_ai.adapters.native_root_external_libraries import (
    BorrowedExternalQualifiedLibraries,
)
from literate_ai.adapters.native_root_qualified_provider import (
    HeldNativeRootQualifiedProvider,
)
from literate_ai.adapters.retained_package_tree import RetainedPackageTree
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components import (
    ComponentCommandPhase,
    ComponentCommandRole,
)
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_native_root_external_runtime as runtime_fixture
from tests.support import fixtures_test_qualification_capture as capture_fixture


@contextmanager
def _modeled_path(reader):
    # These existing ports-only protocols model live receiver admission. Keep
    # class descriptors REAL; only the admitted delegate seam is modeled here.
    def original(owner):
        return lambda export: reader(owner, export)

    with mock.patch.object(
        borrowed_bridge, "_original_borrowed_artifact_path", side_effect=original
    ):
        yield reader


class HeldPhysicalRootTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root = self.base / "original-opaque-destination"
        (self.root / "source").mkdir(parents=True)
        self.content = b"pub fn original() -> u32 { 42 }\n"
        source = self.root / "source/lib.rs"
        source.write_bytes(self.content)
        source.chmod(0o644)
        files = (DirectoryExportFile("source/lib.rs", self.content, 0o644),)
        payload = encode_directory_export(files, max_bytes=4096, max_entries=4)
        _, exports, _, _ = capture_fixture.fixture()
        self.export = replace(
            exports.libraries[0].artifact_export,
            blob=BlobRef(
                hashlib.sha256(payload).hexdigest(),
                len(payload),
                media_type=exports.libraries[0].artifact_export.media_type,
            ),
        )
        self.tree = RetainedPackageTree.capture(self.root, files)
        self.holder = object.__new__(HeldNativeRootQualifiedProvider)
        self.holder._artifact_path_function = held_bridge._HELD_ARTIFACT_PATH_FUNCTION
        self.holder._values = SimpleNamespace(exports=(self.export,))
        reviewed = SimpleNamespace(
            project=SimpleNamespace(root=self.base),
            binding=SimpleNamespace(
                common=SimpleNamespace(
                    destinations=((self.export.identity, self.root.name),)
                )
            ),
        )
        self.materialized = SimpleNamespace(
            packages=(self.tree,), files=SimpleNamespace(reviewed=reviewed)
        )
        self.holder._materialized = self.materialized
        self.guard = self.enterContext(
            mock.patch.object(
                HeldNativeRootQualifiedProvider,
                "require_current",
                autospec=True,
                side_effect=lambda holder: self.tree.require_unchanged(),
            )
        )

    def test_exact_original_package_leaf_not_inferred_parent_export_id(self):
        self.assertNotEqual(self.root.name, self.export.export_id)
        path = self.holder.artifact_path(self.export)
        self.assertIs(path, self.tree.root)
        self.assertEqual((path / "source/lib.rs").read_bytes(), self.content)
        self.assertEqual(self.guard.call_count, 2)
        self.assertFalse((path.parent / self.export.export_id).exists())

    def test_package_bytes_changed_before_query_refuse(self):
        (self.root / "source/lib.rs").write_bytes(b"foreign bytes")
        with self.assertRaises(ValueError):
            self.holder.artifact_path(self.export)

    def test_last_guard_cannot_change_original_root_pointer(self):
        original = self.tree.root
        count = 0

        def change(holder):
            nonlocal count
            count += 1
            self.tree.require_unchanged()
            if count == 2:
                object.__setattr__(self.tree, "root", self.base / "foreign")

        self.guard.side_effect = change
        try:
            with self.assertRaisesRegex(ValueError, "artifact_package_changed"):
                self.holder.artifact_path(self.export)
        finally:
            object.__setattr__(self.tree, "root", original)

    def test_unknown_export_does_not_select_same_named_path(self):
        with self.assertRaisesRegex(ValueError, "artifact_not_held"):
            self.holder.artifact_path(replace(self.export, export_id="unknown"))

    def test_original_closing_guard_error_identity_is_preserved(self):
        original = RuntimeError("original provider expired")
        self.guard.side_effect = [None, original]
        with self.assertRaises(RuntimeError) as caught:
            self.holder.artifact_path(self.export)
        self.assertIs(caught.exception, original)


class AggregatePhysicalRootTests(unittest.TestCase):
    setUp = HeldPhysicalRootTests.setUp

    def aggregate(self):
        owner = object.__new__(BorrowedExternalQualifiedLibraries)
        owner._artifact_path_function = borrowed_bridge._BORROWED_ARTIFACT_PATH_FUNCTION
        owner._active, owner._pid, owner._seal = True, os.getpid(), owner
        owner._asset = SimpleNamespace(identity=canonical_identity("asset"))
        owner._asset_identity = owner._asset.identity
        owner._descriptor = SimpleNamespace(identity=canonical_identity("descriptor"))
        owner._descriptor_identity = owner._descriptor.identity
        selection = SimpleNamespace(
            provider_component_revision=self.export.component_revision
        )
        owner._members = owner._original_members = ((selection, self.holder),)
        provider = SimpleNamespace(
            binding=SimpleNamespace(component_revision=self.export.component_revision),
            exports=(self.export,),
        )
        data = SimpleNamespace(exports=(self.export,), providers=(provider,))
        self.projector = self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries, "data_projection", return_value=data
            )
        )
        self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries,
                "require_current",
                autospec=True,
                side_effect=lambda value: value._require_original(),
            )
        )
        return owner

    def test_original_holder_delegation_returns_actual_leaf(self):
        owner = self.aggregate()
        self.assertIs(owner.artifact_path(self.export), self.root)

    def test_projection_substitution_never_invokes_foreign_holder(self):
        owner = self.aggregate()
        foreign = mock.Mock()
        data = self.projector.return_value

        def change():
            owner._members = ((owner._original_members[0][0], foreign),)
            return data

        self.projector.side_effect = change
        with self.assertRaisesRegex(ValueError, "artifact_not_selected"):
            owner.artifact_path(self.export)
        foreign.artifact_path.assert_not_called()
        self.assertFalse(owner._active)


class PortsPhysicalRootTests(unittest.TestCase):
    def ports(self):
        ports, owner, foreign, _, _ = (
            runtime_fixture.ExternalExecutableAuthorityBoundaryTests._blob_ports(self)
        )
        _, exports, _, _ = capture_fixture.fixture()
        export = exports.libraries[0].artifact_export
        owner._artifact_path_function = borrowed_bridge._BORROWED_ARTIFACT_PATH_FUNCTION
        ports._artifact_paths = {}
        data = SimpleNamespace(exports=(export,))
        return ports, owner, foreign, export, data

    def test_packaging_accessor_uses_original_owner_not_shadowed_local_path(self):
        ports, owner, _, export, data = self.ports()
        original_path = Path("/actual/original/held-root")
        ports._artifact_paths[export.identity.uri] = Path("/must-not-resolve")
        with (
            mock.patch.object(
                runtime, "qualified_library_runtime_data", return_value=data
            ),
            _modeled_path(mock.Mock(return_value=original_path)) as path,
        ):
            self.assertIs(ports.artifact_path(export), original_path)
            path.assert_called_once_with(owner, export)
        self.assertEqual(set(ports.contracts), {owner._asset.component_revision.uri})
        self.assertEqual(
            set(ports.cargo_targets), {owner._asset.component_revision.uri}
        )
        self.assertEqual(
            ports._artifact_paths[export.identity.uri], Path("/must-not-resolve")
        )

    def test_before_first_substitution_refuses_projection_and_path_dispatch(
        self,
    ):
        ports, _, foreign, export, _ = self.ports()
        ports._qualified_library_inputs = foreign
        with (
            mock.patch.object(runtime, "qualified_library_runtime_data") as data,
            _modeled_path(mock.Mock()) as path,
        ):
            with self.assertRaises(LocalStandardLifecycleError):
                ports.artifact_path(export)
            data.assert_not_called()
            path.assert_not_called()

    def test_projection_callback_substitution_never_dispatches_a_foreign_path_reader(
        self,
    ):
        ports, _, foreign, export, data = self.ports()

        def change(*args):
            ports._qualified_library_inputs = foreign
            return data

        with (
            mock.patch.object(
                runtime, "qualified_library_runtime_data", side_effect=change
            ),
            _modeled_path(mock.Mock()) as path,
        ):
            with self.assertRaises(LocalStandardLifecycleError):
                ports.artifact_path(export)
            path.assert_not_called()

    def test_path_callback_owner_substitution_refuses_at_closing_boundary(self):
        ports, owner, foreign, export, data = self.ports()

        def change(actual, selected):
            self.assertIs(actual, owner)
            ports._qualified_library_inputs = foreign
            return Path("/original/held")

        with (
            mock.patch.object(
                runtime, "qualified_library_runtime_data", return_value=data
            ),
            _modeled_path(mock.Mock(side_effect=change)) as path,
        ):
            with self.assertRaises(LocalStandardLifecycleError):
                ports.artifact_path(export)
            path.assert_called_once_with(owner, export)

    def test_used_external_provider_role_returns_exact_leaf_local_role_keeps_old_root(
        self,
    ):
        ports, _, _, export, data = self.ports()
        with tempfile.TemporaryDirectory() as directory:
            local_root = Path(directory).resolve()
            local = replace(export, export_id="local")
            ports._artifact_paths[local.identity.uri] = local_root
            held_root = Path("/actual/held-destination")
            with (
                mock.patch.object(
                    runtime, "qualified_library_runtime_data", return_value=data
                ),
                _modeled_path(mock.Mock(return_value=held_root)),
            ):
                self.assertEqual(
                    ports._provider_roots((export, local)),
                    (str(held_root), str(local_root)),
                )

    def test_unused_provider_role_does_not_resolve_any_provider_path(self):
        ports = object.__new__(LocalStandardLifecyclePorts)
        ports.python_targets = {}
        tool = canonical_identity("tool")
        binding = SimpleNamespace(
            command=("native-tool",), require_unchanged=mock.Mock()
        )
        ports.tool_bindings = {tool.uri: binding}
        command = SimpleNamespace(
            roles=(ComponentCommandRole.TOOL,),
            substitute=lambda values: values[ComponentCommandRole.TOOL],
        )
        contract = SimpleNamespace(
            component_revision=canonical_identity("root"),
            command=lambda phase: command,
            tool_binding=lambda phase: SimpleNamespace(toolchain_identity=tool),
        )
        ports._provider_roots = mock.Mock(
            side_effect=AssertionError("unused role queried")
        )
        path = Path("/not-opened")
        self.assertEqual(
            ports._locked_argv(
                contract,
                ComponentCommandPhase.TEST,
                source_root=path,
                object_root=path,
                artifact_root=path,
                export_path=path,
                providers=(object(),),
            ),
            ("native-tool",),
        )
        ports._provider_roots.assert_not_called()
