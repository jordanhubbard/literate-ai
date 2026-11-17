"""Real imports from synthetic compiled SDK fixtures, not lifecycle qualification."""

import json
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
    prepare_node_sdk_composition,
    require_node_sdk_projection,
)
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.node_sdk import CommonJSModuleDeclaration
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
            "../_providers/"
            + self.artifact.component_revision.digest
            + "/artifact/"
            + declaration.runtime
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

    def test_relocated_cjs_esm_root_subpath_and_error_identity(self):
        plan = self.prepare()
        before = dict(self.fixture.blobs)
        root = self.fixture.root / "projection"
        checks = []
        materialize_node_sdk(plan, root, require_current=lambda: checks.append(True))
        moved = self.fixture.root / "app/node_modules/counter-sdk"
        moved.parent.mkdir(parents=True)
        root.rename(moved)
        self.assertGreater(len(checks), len(plan.files))
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
