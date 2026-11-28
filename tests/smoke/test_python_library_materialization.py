"""Isolated real imports from fixture export DATA; no provider admission claim."""

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from dataclasses import fields, replace
from pathlib import Path

from literate_ai.adapters.action_build_limits import MAX_BUILD_ARCHIVE_BYTES
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    directory_export_bytes,
    encode_directory_export,
)
from literate_ai.adapters.lifecycle.python_libraries import (
    capture_python_library_runtime,
    materialize_python_library_imports,
    prepare_python_library_imports,
    python_library_materialization_files,
    verify_python_library_materialization,
)
from literate_ai.adapters.lifecycle.standard_runtime import (
    STANDARD_PYTHON_RUNTIME_DRIVER,
)
from literate_ai.adapters.qualification_python import (
    python_bindings_from_recipe_document,
)
from literate_ai.adapters.standard_project import (
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts import (
    ArtifactExport,
    BlobRef,
    LibraryConsumerBinding,
    canonical_identity,
)
from tests.support.fixtures_test_standard_command_projection import (
    _locked_snapshot,
    _observation,
    _tool,
)


class PythonLibraryMaterializationTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name).resolve()
        _, snapshot, execution = _locked_snapshot(
            self.root, language="python", no_entrypoint=True
        )
        # This supplies typed command DATA, with the existing modeled tool/platform
        # fixture. The actual child below is this host's isolated Python. The full
        # producer fixture separately owns original native lifecycle acceptance.
        self.contract = project_locked_standard_toolchain_closure(
            snapshot,
            execution,
            host_platform="macos",
            toolchain_discoverer=lambda n, c, e: _tool(n),
            dependency_observer=_observation,
        ).contracts[0]
        self.consumer = replace(
            self.contract, component_revision=canonical_identity("consumer")
        )
        probe = self.root / "mode"
        probe.touch()
        probe.chmod(0o644)
        self.mode = stat.S_IMODE(probe.stat().st_mode)
        probe.unlink()
        self.blobs = {}
        self.known = {}
        self.contracts = {self.contract.component_revision.uri: self.contract}
        cap = self.contract.library_import_surface.capabilities[0]
        self.artifact, self.binding = self.provider(
            self.contract, f"def {cap.symbols[0]}(argument): return argument+1\n"
        )

    def provider(self, contract, body, *, dependencies=(), content=None, consumer=None):
        cap = contract.library_import_surface.capabilities[0]
        if content is None:
            content = encode_directory_export(
                (
                    DirectoryExportFile(
                        "source/" + cap.module.replace(".", "/") + ".py",
                        body.encode(),
                        self.mode,
                    ),
                    DirectoryExportFile(
                        "source/main.py",
                        b"# private generated-test wrapper\n",
                        self.mode,
                    ),
                ),
                max_bytes=1048576,
                max_entries=1000,
            )
        declaration = contract.artifact_export
        artifact = ArtifactExport(
            **{f.name: getattr(declaration, f.name) for f in fields(declaration)},
            component_revision=contract.component_revision,
            source_tree_identity=canonical_identity("fixture-source"),
            toolchain_identity=contract.language_compiler_identity,
            authorization_identity=canonical_identity("fixture-authorization"),
            dependency_artifact_identities=dependencies,
            blob=BlobRef(
                hashlib.sha256(content).hexdigest(),
                len(content),
                media_type=declaration.media_type,
            ),
        )
        self.blobs[artifact.blob.identity] = content
        self.known[artifact.identity] = artifact
        self.contracts[contract.component_revision.uri] = contract
        binding = LibraryConsumerBinding(
            (consumer or self.consumer).component_revision,
            artifact.component_revision,
            cap.capability,
            cap.interface_identity,
            artifact.identity,
            contract.library_import_surface.identity,
            artifact.target_identity,
            dependencies,
        )
        return artifact, binding

    def prepare(self, *, consumer=None, artifacts=None, bindings=None, reader=None):
        return prepare_python_library_imports(
            consumer or self.consumer,
            (self.artifact,) if artifacts is None else artifacts,
            (self.binding,) if bindings is None else bindings,
            self.contracts,
            reader or (lambda ref: self.blobs[ref.identity]),
            dependency_exports=self.known,
        )

    def export(self, imports, module, symbol):
        export = self.root / "consumer-export"
        (export / "source").mkdir(parents=True)
        (export / "source/main.py").write_text(
            f"from {module} import {symbol}\nprint({symbol}(6))\n"
        )
        materialize_python_library_imports(imports, export)
        return export

    def run_export(self, export):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                STANDARD_PYTHON_RUNTIME_DRIVER,
                str(export.parent),
                str(export),
                "tree",
                "source/main.py",
                "--litai-smoke",
            ],
            cwd=self.root,
            env={**os.environ, "PYTHONPATH": str(self.root / "ambient")},
            text=True,
            capture_output=True,
            timeout=30,
        )

    def test_inert_replay_requires_exact_private_bytes_modes_and_coverage(self):
        imports = self.prepare()
        runtime = (
            DirectoryExportFile(
                "site/poison.py", b"raise RuntimeError('never execute')\n", 0o644
            ),
        )
        runtime_identity = canonical_identity("original-runtime-evidence")
        expected = python_library_materialization_files(
            imports, runtime=runtime, runtime_identity=runtime_identity
        )
        verify_python_library_materialization(
            imports, expected, runtime=runtime, runtime_identity=runtime_identity
        )
        manifest = next(
            item for item in expected if item.path.endswith("/imports.json")
        )
        variants = (
            (),
            expected[:-1],
            (*expected, DirectoryExportFile(".litai-python/foreign.py", b"", 0o644)),
            tuple(
                replace(item, content=item.content + b" ") if item is manifest else item
                for item in expected
            ),
            tuple(
                replace(item, mode=0o755) if item is manifest else item
                for item in expected
            ),
        )
        for index, candidate in enumerate(variants):
            with (
                self.subTest(index=index),
                self.assertRaisesRegex(ValueError, "differs from original"),
            ):
                verify_python_library_materialization(
                    imports,
                    candidate,
                    runtime=runtime,
                    runtime_identity=runtime_identity,
                )
        # Expected absence comes from original inputs, never candidate presence.
        empty = replace(imports, packages=())
        verify_python_library_materialization(empty, ())
        with self.assertRaisesRegex(ValueError, "differs from original"):
            verify_python_library_materialization(empty, expected)
        with self.assertRaisesRegex(ValueError, "differs from original"):
            verify_python_library_materialization(
                imports,
                expected,
                runtime=runtime,
                runtime_identity=canonical_identity("foreign-runtime-evidence"),
            )

    def test_reserved_namespace_aliases_refuse_even_when_originally_absent(self):
        empty = replace(self.prepare(), packages=())
        for alias in (".LITAI-PYTHON", ".Litai-Python", ".litai-python"):
            for suffix in ("", "/imports.json"):
                path = alias + suffix
                files = (DirectoryExportFile(path, b"{}", self.mode),)
                with (
                    self.subTest(path=path),
                    self.assertRaisesRegex(ValueError, "differs from original"),
                ):
                    verify_python_library_materialization(empty, files)
        for alias in (
            ".LITAI-PYTHON/imports.json",
            ".Litai-Python/runtime/site/foreign.py",
            ".litai-python",
        ):
            content = encode_directory_export(
                (
                    DirectoryExportFile(alias, b"{}", self.mode),
                    DirectoryExportFile("source/value.py", b"VALUE = 1\n", self.mode),
                ),
                max_bytes=1048576,
                max_entries=1000,
            )
            artifact, binding = self.provider(self.contract, "", content=content)
            with (
                self.subTest(provider_alias=alias),
                self.assertRaisesRegex(ValueError, "aliased reserved"),
            ):
                self.prepare(artifacts=(artifact,), bindings=(binding,))

    def test_aliased_reserved_destinations_refuse_before_writing(self):
        imports = self.prepare()
        for index, alias in enumerate((".LITAI-PYTHON", ".Litai-Python")):
            export = self.root / f"occupied-{index}"
            destination = export / alias
            destination.mkdir(parents=True)
            marker = destination / "keep"
            marker.write_bytes(b"owned by caller")
            with (
                self.subTest(alias=alias),
                self.assertRaisesRegex(ValueError, "occupied"),
            ):
                materialize_python_library_imports(imports, export)
            self.assertEqual(marker.read_bytes(), b"owned by caller")
            self.assertEqual(tuple(export.iterdir()), (destination,))

    def test_manifest_permissions_follow_explicit_target_and_actual_writer(self):
        imports = self.prepare()
        for windows, mode in ((False, 0o644), (True, 0o666)):
            projected = python_library_materialization_files(imports, windows=windows)
            manifest = next(
                item for item in projected if item.path == ".litai-python/imports.json"
            )
            self.assertEqual(manifest.mode, mode)
            verify_python_library_materialization(imports, projected, windows=windows)
            with self.assertRaisesRegex(ValueError, "differs from original"):
                verify_python_library_materialization(
                    imports, projected, windows=not windows
                )
        export = self.root / "permission-readback"
        export.mkdir()
        materialize_python_library_imports(imports, export)
        verify_python_library_materialization(
            imports, capture_python_library_runtime(export), windows=os.name == "nt"
        )

    def test_provider_free_file_export_is_preserved_and_dependencies_refuse(self):
        imports = self.prepare()
        empty = replace(imports, packages=())
        export = self.root / "application.py"
        original = b"print('standalone')\n"
        export.write_bytes(original)
        materialize_python_library_imports(empty, export)
        self.assertEqual(export.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "require a directory export"):
            materialize_python_library_imports(imports, export)
        self.assertEqual(export.read_bytes(), original)

    def test_original_recipe_mappings_require_separate_build_artifact_authority(self):
        surface = self.contract.library_import_surface
        capability = surface.capabilities[0]
        document = {
            "library_dependencies": [
                {
                    "provider_component_revision": (
                        self.contract.component_revision.to_dict()
                    ),
                    "capability": capability.capability,
                    "interface_identity": capability.interface_identity.to_dict(),
                    "import_surface": surface.to_dict(),
                }
            ]
        }
        arguments = dict(
            recipe_identity=canonical_identity(document),
            consumer=self.consumer,
            contracts=self.contracts,
        )
        self.assertEqual(
            python_bindings_from_recipe_document(
                document, providers=(self.artifact,), **arguments
            ),
            (self.binding,),
        )
        self.assertEqual(
            python_bindings_from_recipe_document(document, providers=(), **arguments),
            (),
        )
        with self.assertRaisesRegex(ValueError, "preimage"):
            python_bindings_from_recipe_document(
                {}, providers=(self.artifact,), **arguments
            )
        with self.assertRaisesRegex(ValueError, "lacks its selected"):
            python_bindings_from_recipe_document(
                {},
                recipe_identity=canonical_identity({}),
                consumer=self.consumer,
                providers=(self.artifact,),
                contracts=self.contracts,
            )
        with self.assertRaisesRegex(ValueError, "original provider"):
            python_bindings_from_recipe_document(
                document,
                providers=(self.artifact,),
                **{
                    **arguments,
                    "contracts": {
                        self.contract.component_revision.uri: replace(
                            self.contract,
                            library_import_surface=replace(surface, package="foreign"),
                        )
                    },
                },
            )

    def test_build_provider_contract_cannot_be_mapped_under_another_revision(self):
        document = {}
        foreign = replace(
            self.contract, component_revision=canonical_identity("foreign")
        )
        with self.assertRaisesRegex(ValueError, "original command contract"):
            python_bindings_from_recipe_document(
                document,
                recipe_identity=canonical_identity(document),
                consumer=self.consumer,
                providers=(self.artifact,),
                contracts={self.contract.component_revision.uri: foreign},
            )

    def test_direct_import_survives_relocation_and_ignores_ambient_shadow(self):
        cap = self.contract.library_import_surface.capabilities[0]
        imports = self.prepare()
        export = self.export(imports, cap.module, cap.symbols[0])
        ambient = self.root / "ambient" / (cap.module.replace(".", "/") + ".py")
        ambient.parent.mkdir(parents=True)
        ambient.write_text("raise RuntimeError('ambient provider executed')\n")
        moved = self.root / "relocated"
        shutil.move(export, moved)
        self.blobs.clear()
        completed = self.run_export(moved)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "7")

    def test_real_transitive_import_uses_original_nested_export_bytes(self):
        leaf = self.artifact
        leaf_cap = self.contract.library_import_surface.capabilities[0]
        surface = replace(
            self.contract.library_import_surface,
            package="middle",
            capabilities=(replace(leaf_cap, module="middle.value"),),
        )
        middle = replace(
            self.contract,
            component_revision=canonical_identity("middle"),
            library_import_surface=surface,
        )
        imports = self.prepare(
            consumer=middle,
            bindings=(
                replace(
                    self.binding, consumer_component_revision=middle.component_revision
                ),
            ),
        )
        tree = self.root / "middle-export"
        (tree / "source/middle").mkdir(parents=True)
        (tree / "source/middle/value.py").write_text(
            f"from {leaf_cap.module} import {leaf_cap.symbols[0]} as base\n"
            f"def {leaf_cap.symbols[0]}(argument): return base(argument)\n"
        )
        (tree / "source/main.py").write_text("# middle private test wrapper\n")
        materialize_python_library_imports(imports, tree)
        artifact, binding = self.provider(
            middle,
            "",
            dependencies=(leaf.identity,),
            content=directory_export_bytes(tree),
        )
        prepared = self.prepare(artifacts=(artifact,), bindings=(binding,))
        export = self.export(prepared, "middle.value", leaf_cap.symbols[0])
        shutil.rmtree(tree)
        self.blobs.clear()
        completed = self.run_export(export)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "7")

    def test_wrong_binding_interface_and_target_refuse_before_blob_read(self):
        def forbidden(_reference):
            self.fail("invalid binding reached blob reader")

        for change in (
            dict(interface_identity=canonical_identity("foreign-interface")),
            dict(target_identity=canonical_identity("foreign-target")),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.prepare(
                    bindings=(replace(self.binding, **change),), reader=forbidden
                )

    def test_oversized_held_blob_refuses_before_read_or_filesystem_effect(self):
        artifact = replace(
            self.artifact,
            blob=replace(self.artifact.blob, size=MAX_BUILD_ARCHIVE_BYTES + 1),
        )
        binding = replace(self.binding, artifact_identity=artifact.identity)

        def forbidden(_reference):
            self.fail("oversized export reached reader")

        with self.assertRaises(ValueError):
            self.prepare(artifacts=(artifact,), bindings=(binding,), reader=forbidden)
        self.assertFalse((self.root / "consumer-export").exists())

    def test_mutated_nested_payload_refuses_before_import(self):
        cap = self.contract.library_import_surface.capabilities[0]
        export = self.export(self.prepare(), cap.module, cap.symbols[0])
        retained = (
            export
            / ".litai-python"
            / self.artifact.identity.digest
            / "source"
            / (cap.module.replace(".", "/") + ".py")
        )
        retained.write_text("raise RuntimeError('changed provider executed')\n")
        completed = self.run_export(export)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("sealed Python library imports differ", completed.stderr)
        self.assertNotIn("changed provider executed", completed.stderr)

    def test_reserved_destination_is_preserved_on_refusal(self):
        export = self.root / "occupied"
        (export / ".litai-python").mkdir(parents=True)
        sentinel = export / ".litai-python/unknown"
        sentinel.write_bytes(b"preserve")
        with self.assertRaises(ValueError):
            materialize_python_library_imports(self.prepare(), export)
        self.assertEqual(sentinel.read_bytes(), b"preserve")
