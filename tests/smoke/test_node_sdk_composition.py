"""Real imports from synthetic compiled SDK fixtures, not lifecycle qualification."""

import hashlib
import json
import os
import shutil
import subprocess
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import directory_artifacts
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_composition import (
    NodeSDKEntrypoint,
    materialize_node_sdk,
    node_sdk_provider_module_paths,
    node_sdk_provider_package_files,
    prepare_node_sdk_composition,
    require_node_sdk_projection,
)
from literate_ai.contracts import BlobRef, LibraryImportSurface, canonical_identity
from literate_ai.contracts.node_sdk import (
    CommonJSModuleDeclaration,
    NodeSDKExportDeclaration,
)
from tests.smoke import test_javascript_library_imports as import_fixtures


class NodeSDKCompositionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = import_fixtures.JavaScriptLibraryImportTests(
            "test_cjs_and_esm_native_imports_after_artifact_relocation"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.symbol = f.capability.symbols[0]
        capability = replace(
            f.capability, symbols=tuple(sorted((self.symbol, "CounterError")))
        )
        declaration = CommonJSModuleDeclaration(
            capability.module,
            "source/" + capability.module + ".js",
            "source/" + capability.module + ".d.ts",
        )
        surface = replace(
            f.surface, capabilities=(capability,), declarations=(declaration,)
        )
        self.provider_contract = replace(f.contract, library_import_surface=surface)
        body = (
            "exports.CounterError=class CounterError extends Error{};exports."
            + self.symbol
            + "=(a,b)=>a+b;"
        )
        types = (
            "export declare class CounterError extends Error{}\n"
            "export declare function " + self.symbol + "(a:number,b:number):number;"
        )
        self.artifact, self.binding = f.provider(
            self.provider_contract,
            body,
            extra=(
                DirectoryExportFile(
                    declaration.declaration, types.encode(), f.file_mode
                ),
            ),
        )
        self.relative = (
            "../" + node_sdk_provider_module_paths(self.artifact, declaration)[0]
        )
        cjs = "module.exports=require(" + json.dumps(self.relative) + ");"
        esm = (
            "import provider from "
            + json.dumps(self.relative)
            + ";export const CounterError=provider.CounterError;export const "
            + self.symbol
            + "=provider."
            + self.symbol
            + ";"
        )
        dts = (
            "export {CounterError,"
            + self.symbol
            + "} from "
            + json.dumps(self.relative)
            + ";"
        )
        compiled = tuple(
            DirectoryExportFile(
                directory + "/index" + suffix, data.encode(), f.file_mode
            )
            for directory, runtime in (("cjs", cjs), ("esm", esm))
            for suffix, data in ((".js", runtime), (".d.ts", dts))
        )
        # Synthetic generated-SDK output authority. This fixture still has no
        # real generation/profile/provider-acceptance receipt.
        sdk_surface = LibraryImportSurface(
            "typescript",
            "counter-sdk",
            (replace(capability, module="counter-sdk"),),
            node_sdk_exports=(
                NodeSDKExportDeclaration("counter-sdk", "index"),
                NodeSDKExportDeclaration("counter-sdk/counter", "index"),
            ),
        )
        f.consumer = replace(f.consumer, library_import_surface=sdk_surface)
        self.arguments = dict(
            source=canonical_identity("TypeScript source fixture"),
            compiler=canonical_identity("selected compiler"),
            node=canonical_identity("selected Node"),
            packer=canonical_identity("selected npm"),
            name="counter-sdk",
            version="1.0.0",
            entrypoints=(
                NodeSDKEntrypoint(".", "index"),
                NodeSDKEntrypoint("./counter", "index"),
            ),
            compiled=compiled,
            licenses=(
                DirectoryExportFile("LICENSE", b"fixture license\n", f.file_mode),
            ),
            providers=(self.artifact,),
            generation_bindings=(self.binding,),
            build_bindings=(self.binding,),
            contracts={
                self.provider_contract.component_revision.uri: self.provider_contract
            },
            read_blob=lambda blob: f.blobs[blob.identity],
            builtin_modules=f.builtins,
        )

    def prepare(self, **changes):
        return prepare_node_sdk_composition(
            self.fixture.consumer, **dict(self.arguments, **changes)
        )

    def prepare_provider_mode(self, mode):
        original = self.fixture.blobs[self.artifact.blob.identity]
        files = directory_artifacts.read_directory_export(
            original, self.artifact.blob, max_bytes=1048576, max_entries=1000
        )
        content = directory_artifacts.encode_directory_export(
            tuple(replace(file, mode=mode) for file in files),
            max_bytes=1048576,
            max_entries=1000,
        )
        artifact = replace(
            self.artifact,
            blob=BlobRef(
                hashlib.sha256(content).hexdigest(),
                len(content),
                media_type=self.artifact.blob.media_type,
            ),
        )
        self.fixture.blobs[artifact.blob.identity] = content
        binding = replace(self.binding, artifact_identity=artifact.identity)
        return self.prepare(
            providers=(artifact,),
            generation_bindings=(binding,),
            build_bindings=(binding,),
        )

    @unittest.skipUnless(os.name == "posix", "requires POSIX private source modes")
    def test_private_provider_copy_preserves_sealed_input_and_distinguishes_identity(
        self,
    ):
        ordinary = self.prepare()
        private = self.prepare_provider_mode(0o600)
        package = private.providers.packages[0]
        before = dict(self.fixture.blobs)
        self.assertTrue(all(file.mode == 0o600 for file in package.files))
        self.assertEqual(private.files, ordinary.files)
        self.assertNotEqual(private.identity, ordinary.identity)
        self.assertNotEqual(package.provider.identity, self.artifact.identity)
        self.assertEqual(
            private.to_dict()["provider_import_policy"],
            "artifact-bytes-preserving-npm-modes-cjs-forwarders@2",
        )
        projected = node_sdk_provider_package_files(
            package.provider, package.surface, package.files
        )
        prefix = (
            "_providers/" + package.provider.component_revision.digest + "/artifact/"
        )
        for file in package.files:
            self.assertIn(
                DirectoryExportFile(prefix + file.path, file.content, 0o644), projected
            )
        self.assertEqual(self.fixture.blobs, before)
        self.assertTrue(all(file.mode == 0o600 for file in package.files))
        with self.assertRaisesRegex(ValueError, "regular portable files"):
            replace(
                private,
                files=(replace(private.files[0], mode=0o600), *private.files[1:]),
            )

    @unittest.skipUnless(os.name == "posix", "requires POSIX private source modes")
    def test_private_provider_projection_still_refuses_other_source_modes(self):
        plan = self.prepare_provider_mode(0o600)
        package = plan.providers.packages[0]
        for mode in (0o400, 0o444, 0o666, 0o700, 0o777, 0o4644):
            with self.subTest(mode=oct(mode)), self.assertRaises(ValueError):
                node_sdk_provider_package_files(
                    package.provider,
                    package.surface,
                    (replace(package.files[0], mode=mode), *package.files[1:]),
                )

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_private_provider_copy_mode_drift_in_closing_callback_is_refused(self):
        plan = self.prepare_provider_mode(0o600)
        root = self.fixture.root / "private-mode-cut"
        materialize_node_sdk(plan, root, require_current=lambda: None)
        target = next(file for file in plan.files if "/artifact/" in file.path)
        calls = []

        def current():
            calls.append(True)
            if len(calls) == 2:
                (root / target.path).chmod(0o600)

        with self.assertRaisesRegex(ValueError, "changed before inventory close"):
            require_node_sdk_projection(plan, root, require_current=current)
        self.assertEqual(len(calls), 2)

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_relocated_cjs_esm_root_subpath_and_error_identity(self):
        plan = self.prepare()
        before = dict(self.fixture.blobs)
        root = self.fixture.root / "projection"
        materialize_node_sdk(plan, root, require_current=lambda: None)
        moved = self.fixture.root / "app/node_modules/counter-sdk"
        moved.parent.mkdir(parents=True)
        root.rename(moved)
        for esm in [False, True]:
            code = (
                "import * as root from 'counter-sdk';"
                "import * as sub from 'counter-sdk/counter';"
                if esm
                else "const root=require('counter-sdk'),"
                "sub=require('counter-sdk/counter');"
            )
            code += (
                "if(root.CounterError!==sub.CounterError || "
                "!(new root.CounterError() instanceof sub.CounterError))"
                "throw Error('identity');console.log(root." + self.symbol + "(2,3));"
            )
            file = moved.parent.parent / ("consumer.mjs" if esm else "consumer.cjs")
            file.write_text(code)
            result = subprocess.run(
                [shutil.which("node"), str(file)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "5")
        self.assertEqual(before, self.fixture.blobs)
        require_node_sdk_projection(plan, moved, require_current=lambda: None)

    def test_input_drift_changes_plan_and_wrong_bindings_fail(self):
        plan = self.prepare()
        self.assertNotEqual(
            plan.identity,
            self.prepare(compiler=canonical_identity("other compiler")).identity,
        )
        self.assertNotEqual(
            plan.identity,
            self.prepare(source=canonical_identity("other source")).identity,
        )
        for changes in [
            dict(generation_bindings=()),
            dict(build_bindings=()),
            dict(
                build_bindings=(
                    replace(
                        self.binding,
                        interface_identity=canonical_identity("other interface"),
                    ),
                )
            ),
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.prepare(**changes)

    def test_missing_declarations_format_halves_and_collisions_fail(self):
        for changes in [
            dict(compiled=self.arguments["compiled"][:-1]),
            dict(name=self.provider_contract.library_import_surface.package),
            dict(entrypoints=(NodeSDKEntrypoint("./only", "index"),)),
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.prepare(**changes)

    def test_application_fixture_keeps_provider_namespace_collision_denial(self):
        # The internal owner is shared with separately admitted retained SDKs.
        # This synthetic application contract grants no retained admission.
        self.fixture.consumer = replace(
            self.fixture.consumer,
            library_import_surface=None,
            artifact_export=replace(
                self.fixture.consumer.artifact_export, role="application"
            ),
        )
        with self.assertRaisesRegex(ValueError, "collides"):
            self.prepare(name=self.provider_contract.library_import_surface.package)

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_complete_inventory_rejects_extra_missing_or_substituted_bytes(self):
        plan = self.prepare()
        for change in ["extra", "missing", "changed"]:
            root = self.fixture.root / change
            materialize_node_sdk(plan, root, require_current=lambda: None)
            if change == "extra":
                (root / "unexpected.js").write_text("module.exports=1")
            elif change == "missing":
                (root / "LICENSE").unlink()
            else:
                (root / "cjs/index.js").write_text("module.exports={}")
            with self.subTest(change=change), self.assertRaises(ValueError):
                require_node_sdk_projection(plan, root, require_current=lambda: None)

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_live_owner_cut_retains_partial_projection(self):
        plan = self.prepare()
        root = self.fixture.root / "interrupted"
        calls = []

        def current():
            calls.append(True)
            if len(calls) == 3:
                raise RuntimeError("owner cut")

        with self.assertRaisesRegex(RuntimeError, "owner cut"):
            materialize_node_sdk(plan, root, require_current=current)
        self.assertTrue(root.exists())
        with self.assertRaises(FileExistsError):
            materialize_node_sdk(plan, root, require_current=lambda: None)

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_final_projection_owner_cannot_rewrite_equal_bytes(self):
        plan = self.prepare()
        root = self.fixture.root / "final-callback"
        materialize_node_sdk(plan, root, require_current=lambda: None)
        calls = []

        def current():
            calls.append(True)
            if len(calls) == 2:
                path = root / "cjs/index.js"
                before = path.stat()
                path.write_bytes(path.read_bytes())
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))

        with self.assertRaisesRegex(ValueError, "changed before inventory close"):
            require_node_sdk_projection(plan, root, require_current=current)
        self.assertEqual(len(calls), 2)

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_materializer_owner_cannot_adopt_rewritten_earlier_file(self):
        plan = self.prepare()
        root = self.fixture.root / "staging-callback"
        changed = []

        def current():
            path = root / plan.files[0].path
            if path.exists() and not changed:
                before = path.stat()
                path.write_bytes(path.read_bytes())
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                changed.append(True)

        with self.assertRaisesRegex(ValueError, "changed before inventory close"):
            materialize_node_sdk(plan, root, require_current=current)
        self.assertEqual(changed, [True])

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_callback_plan_retargeting_refuses_before_materialization(self):
        plan = self.prepare()
        root = self.fixture.root / "retargeted-plan"
        changed = []

        def current():
            if not changed:
                object.__setattr__(plan.files[0], "content", b"substituted")
                changed.append(True)

        with self.assertRaisesRegex(ValueError, "plan changed"):
            materialize_node_sdk(plan, root, require_current=current)
        self.assertEqual(changed, [True])
        self.assertFalse(root.exists())

    def test_unsupported_projection_custody_refuses_before_stage(self):
        plan = self.prepare()
        root = self.fixture.root / "unsupported"
        with patch("literate_ai.adapters.node_sdk_composition.os.name", "nt"):
            with self.assertRaisesRegex(ValueError, "POSIX"):
                materialize_node_sdk(plan, root, require_current=lambda: None)
        self.assertFalse(root.exists())

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_late_namespace_addition_is_seen_by_closing_fence(self):
        plan = self.prepare()
        root = self.fixture.root / "late-addition"
        materialize_node_sdk(plan, root, require_current=lambda: None)
        original = directory_artifacts.os.scandir

        @contextmanager
        def scan(path):
            with original(path) as entries:
                yield entries
            if path == root:
                (root / "late.js").write_text("unexpected")

        with (
            patch.object(directory_artifacts.os, "scandir", scan),
            self.assertRaisesRegex(ValueError, "directory changed"),
        ):
            require_node_sdk_projection(plan, root, require_current=lambda: None)

    @unittest.skipUnless(os.name == "posix", "requires strong projection custody")
    def test_directory_replacement_is_seen_by_closing_fence(self):
        plan = self.prepare()
        root = self.fixture.root / "directory-replacement"
        materialize_node_sdk(plan, root, require_current=lambda: None)
        original = directory_artifacts.os.scandir

        @contextmanager
        def scan(path):
            with original(path) as entries:
                yield entries
            if path == root / "cjs":
                retained = self.fixture.root / "retained-cjs"
                path.rename(retained)
                shutil.copytree(retained, path)

        with (
            patch.object(directory_artifacts.os, "scandir", scan),
            self.assertRaisesRegex(ValueError, "directory changed"),
        ):
            require_node_sdk_projection(plan, root, require_current=lambda: None)

    def test_nested_dependency_namespaces_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "reserved"):
            NodeSDKEntrypoint("./node_modules/private", "index")
        with self.assertRaisesRegex(ValueError, "reserved"):
            NodeSDKEntrypoint(".", "node_modules/private")
        compiled = self.arguments["compiled"] + (
            DirectoryExportFile(
                "cjs/node_modules/hidden.js",
                b"module.exports=1",
                self.fixture.file_mode,
            ),
        )
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.prepare(compiled=compiled)
