"""Compiler-owner denials and opt-in real SDK compilation, not qualification."""

import base64
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.builders.javascript import discover_node_toolchain
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_tools import node_sdk_tool_environment
from literate_ai.adapters.node_sdk_typescript import (
    NodeSDKTypeScriptCompiler,
    TypeScriptSDK,
    _inventory,
)
from tests.smoke import test_node_sdk_composition as composition_fixtures


def file(name, content):
    return DirectoryExportFile(
        name, content.encode() if isinstance(content, str) else content, 0o644
    )


class TypeScriptInventoryTests(unittest.TestCase):
    def test_closed_portable_inventory_before_execution(self):
        for names in [
            ("a.ts", "A.ts"),
            ("a/B.ts", "A/c.ts"),
            ("a", "a/b.ts"),
            ("CON.ts",),
            ("a.ts ",),
            ("../a.ts",),
            ("a%2fts",),
            ("a#b.ts",),
        ]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                _inventory(tuple(file(name, "text") for name in names), maximum=4096)

    def test_tool_environment_denies_ambient_writers_without_mutating_input(self):
        supplied = {
            "PATH": "/chosen/tools",
            "HOME": "/private/home",
            "NODE_OPTIONS": "preload",
            "node_v8_coverage": "/outside",
            "NODE_REDIRECT_WARNINGS": "/outside",
            "NODE_COMPILE_CACHE": "/outside",
            "NPM_CONFIG_USERCONFIG": "/outside",
            "NPM_TOKEN": "private",
            "NODE_AUTH_TOKEN": "private",
            "NODE_FUTURE_CONTROL": "outside",
        }
        expected = {
            "PATH": "/chosen/tools",
            "HOME": "/private/home",
            "NODE_DISABLE_COMPILE_CACHE": "1",
        }
        self.assertEqual(node_sdk_tool_environment(supplied), expected)
        self.assertIn("NODE_OPTIONS", supplied)

    def test_sdk_identity_covers_all_tool_bytes_and_not_modes(self):
        files = (
            file("package.json", '{"name":"typescript","version":"6.0.3"}'),
            file("lib/typescript.js", 'throw Error("not a compiler fixture");'),
            file("lib/lib.es2022.d.ts", "interface Object {}"),
        )
        first = TypeScriptSDK(files)
        self.assertEqual(first.identity, TypeScriptSDK(tuple(reversed(files))).identity)
        changed = (*files, file("NOTICE", "license bytes"))
        self.assertNotEqual(first.identity, TypeScriptSDK(changed).identity)
        self.assertEqual(first.version, "6.0.3")

    def test_sdk_requires_supported_named_package_and_compiler(self):
        for metadata in [
            "{}",
            "[]",
            '{"name":"other","version":"6.0.3"}',
            '{"name":"typescript","version":"5.7.0"}',
        ]:
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                TypeScriptSDK(
                    (
                        file("package.json", metadata),
                        file("lib/typescript.js", "code"),
                        file("lib/lib.es2022.d.ts", "types"),
                    )
                )


@unittest.skipUnless(
    os.environ.get("LITERATE_TYPESCRIPT_SDK") and shutil.which("node"),
    "requires explicitly selected LITERATE_TYPESCRIPT_SDK and Node",
)
class TypeScriptCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only test setup reads this explicit tool fixture. Production owners must
        # supply their separately admitted immutable compiler package snapshot.
        root = Path(os.environ["LITERATE_TYPESCRIPT_SDK"]).resolve(strict=True)
        files = []
        total = 0
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("test compiler SDK contains a link")
            if path.is_file():
                if path.stat().st_size > 16 * 1024 * 1024 or len(files) >= 1024:
                    raise ValueError("test compiler SDK exceeds its bound")
                content = path.read_bytes()
                total += len(content)
                if total > 32 * 1024 * 1024:
                    raise ValueError("test compiler SDK exceeds its bound")
                files.append(file(path.relative_to(root).as_posix(), content))
        cls.environment = dict(os.environ)
        cls.environment.pop("NODE_OPTIONS", None)
        cls.environment.pop("NODE_PATH", None)
        cls.node = discover_node_toolchain(cls.environment)
        cls.compiler = NodeSDKTypeScriptCompiler(TypeScriptSDK(tuple(files)), cls.node)

    def setUp(self):
        self.fixture = composition_fixtures.NodeSDKCompositionTests(
            "test_relocated_cjs_esm_root_subpath_and_error_identity"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        plan = f.prepare()
        self.provider_files = tuple(
            item for item in plan.files if item.path.startswith("_providers/")
        )
        self.source = file(
            "src/index.ts",
            "import provider from "
            + json.dumps(f.relative)
            + ";export const "
            + f.symbol
            + "=provider."
            + f.symbol
            + ";export const CounterError=provider.CounterError;",
        )

    def run_compiler(self, files, roots, operation="check", **kwargs):
        return self.compiler.run(
            files=tuple(files),
            roots=roots,
            operation=operation,
            environment=self.environment,
            require_current=lambda: None,
            **kwargs,
        )

    def package(self):
        compiled = self.run_compiler(
            (*self.provider_files, self.source), ("src/index.ts",), operation="compile"
        )
        self.assertTrue(compiled.success, compiled.diagnostics)
        self.assertEqual(
            {item.path for item in compiled.outputs},
            {
                directory + "/index" + suffix
                for directory in ("cjs", "esm")
                for suffix in (".js", ".d.ts")
            },
        )
        plan = self.fixture.prepare(
            compiled=compiled.outputs, compiler=self.compiler.identity
        )
        consumer = (
            "import {CounterError," + self.fixture.symbol + "} from 'counter-sdk';"
            "import {CounterError as SubError} from 'counter-sdk/counter';"
            "const n:number="
            + self.fixture.symbol
            + "(2,3);const error:Error=new SubError('bad');\n"
            "// @ts-expect-error public arguments must remain numeric\n"
            + self.fixture.symbol
            + "('bad',3);\n"
        )
        return (
            *tuple(
                file("node_modules/counter-sdk/" + item.path, item.content)
                for item in plan.files
            ),
            file("consumer.cts", consumer),
            file("consumer.mts", consumer),
        )

    def test_actual_dual_compilation_and_four_consumer_combinations(self):
        result = self.run_compiler(self.package(), ("consumer.cts", "consumer.mts"))
        self.assertTrue(result.success, result.diagnostics)
        self.assertFalse(result.outputs)
        self.assertTrue(any(name.endswith("cjs/index.d.ts") for name in result.inputs))
        self.assertTrue(any(name.endswith("esm/index.d.ts") for name in result.inputs))

    def test_any_weakened_public_declarations_are_rejected(self):
        files = tuple(
            file(
                item.path,
                "export declare const CounterError:any;export declare const "
                + self.fixture.symbol
                + ":any;",
            )
            if item.path
            in {
                "node_modules/counter-sdk/cjs/index.d.ts",
                "node_modules/counter-sdk/esm/index.d.ts",
            }
            else item
            for item in self.package()
        )
        result = self.run_compiler(files, ("consumer.cts", "consumer.mts"))
        self.assertFalse(result.success)
        self.assertTrue(any(item["code"] == 2578 for item in result.diagnostics))
        self.assertFalse(result.outputs)

    def test_sealed_provider_imports_and_references_cannot_escape(self):
        for directive in [
            'export type {Outside} from "outside";\n',
            '/// <reference path="/etc/host-private.d.ts" />\n',
            '/// <reference types="outside" />\n',
        ]:
            with self.subTest(directive=directive):
                files = []
                for item in (*self.provider_files, self.source):
                    files.append(
                        file(item.path, directive.encode() + item.content)
                        if item.path.endswith(".d.ts")
                        else item
                    )
                files.extend(
                    (
                        file(
                            "node_modules/outside/package.json",
                            '{"name":"outside","types":"index.d.ts"}',
                        ),
                        file(
                            "node_modules/outside/index.d.ts",
                            "export interface Outside {}",
                        ),
                    )
                )
                with self.assertRaisesRegex(ValueError, "sealed provider"):
                    self.run_compiler(files, ("src/index.ts",), operation="compile")

    def test_candidate_cannot_expand_selected_standard_libraries(self):
        for provider in (False, True):
            files = []
            for item in (*self.provider_files, self.source):
                selected = (
                    item.path.endswith(".d.ts")
                    if provider
                    else item.path == "src/index.ts"
                )
                files.append(
                    file(item.path, b'/// <reference lib="dom" />\n' + item.content)
                    if selected
                    else item
                )
            with (
                self.subTest(provider=provider),
                self.assertRaisesRegex(ValueError, "cannot expand selected ES2022"),
            ):
                self.run_compiler(files, ("src/index.ts",), operation="compile")

    def test_absolute_provider_reference_cannot_use_a_relative_decoy(self):
        files = []
        declaration = next(
            item for item in self.provider_files if item.path.endswith(".d.ts")
        )
        for item in (*self.provider_files, self.source):
            files.append(
                file(
                    item.path,
                    b'/// <reference path="/__literate_sdk__/outside.d.ts" />\n'
                    + item.content,
                )
                if item.path == declaration.path
                else item
            )
        # path.join(directory, absolute) preserves the directory, whereas TS
        # resolves the absolute target. Supply both paths to expose that mismatch.
        decoy = declaration.path.rsplit("/", 1)[0] + "/__literate_sdk__/outside.d.ts"
        files.extend(
            (
                file(decoy, "declare interface Outside {}"),
                file("outside.d.ts", "declare interface Outside {}"),
            )
        )
        with self.assertRaisesRegex(ValueError, "sealed provider reference"):
            self.run_compiler(files, ("src/index.ts",), operation="compile")

    def test_compiler_sdk_cannot_be_imported_as_candidate_type_authority(self):
        cases = (
            (
                '/// <reference path="/__literate_compiler__/lib/lib.dom.d.ts" />\n'
                "export const body=document.body;",
                "candidate reference",
            ),
            (
                'import "/__literate_compiler__/lib/lib.dom";'
                "export const body=document.body;",
                "no physical resolution",
            ),
            (
                '/// <reference types="/__literate_compiler__/lib/lib.dom" />\n'
                "export const body=document.body;",
                "type directive has no physical resolution",
            ),
        )
        for source, error in cases:
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, error):
                self.run_compiler(
                    (file("src/index.ts", source),),
                    ("src/index.ts",),
                    operation="compile",
                )

    def test_missing_module_does_not_use_an_ambient_declaration(self):
        files = (
            file("src/index.ts", 'import {value} from "phantom";export const n=value;'),
            file(
                "ambient.d.ts", 'declare module "phantom" {export const value:number;}'
            ),
        )
        with self.assertRaisesRegex(ValueError, "no physical resolution"):
            self.run_compiler(files, ("src/index.ts", "ambient.d.ts"))

    def test_virtual_paths_ignore_platform_native_path_operations(self):
        # Fault-inject Windows native path operations on this host. This is a
        # real compiler control, not evidence of native Windows qualification.
        import subprocess

        helper = self.compiler._helper.replace(
            "const path = require('node:path');",
            "const path = {...require('node:path').win32, "
            "posix: require('node:path').posix};",
        )
        self.assertNotEqual(helper, self.compiler._helper)

        def rows(files):
            return [
                {"path": item.path, "content": base64.b64encode(item.content).decode()}
                for item in files
            ]

        packet = {
            "version": 1,
            "operation": "compile",
            "roots": ["src/index.ts"],
            "files": rows((*self.provider_files, self.source)),
            "compiler_files": rows(self.compiler.sdk.files),
        }
        result = subprocess.run(
            (*self.node.command, "--max-old-space-size=512", "--eval", helper),
            input=json.dumps(packet).encode(),
            capture_output=True,
            timeout=30,
            env=self.environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        response = json.loads(result.stdout)
        self.assertTrue(response["success"], response["diagnostics"])
        self.assertEqual(len(response["outputs"]), 4)

    def test_owner_cut_prevents_process_start(self):
        def stopped():
            raise RuntimeError("owner ended")

        with patch(
            "literate_ai.adapters.node_sdk_typescript.run_bounded_process"
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "owner ended"):
                self.compiler.run(
                    files=(self.source,),
                    roots=("src/index.ts",),
                    operation="compile",
                    environment=self.environment,
                    require_current=stopped,
                )
            run.assert_not_called()

    def test_ambient_coverage_cannot_write_outside_compilation_custody(self):
        outside = self.fixture.fixture.root / "outside-coverage"
        result = self.compiler.run(
            files=(file("src/index.ts", "export const n=1;"),),
            roots=("src/index.ts",),
            operation="compile",
            environment={**self.environment, "NODE_V8_COVERAGE": str(outside)},
            require_current=lambda: None,
        )
        self.assertTrue(result.success, result.diagnostics)
        self.assertFalse(outside.exists())

    def test_owner_cut_terminates_inflight_compiler(self):
        sdk = TypeScriptSDK(
            (
                file("package.json", '{"name":"typescript","version":"6.0.3"}'),
                file("lib/typescript.js", "while(true){}"),
                file("lib/lib.es2022.d.ts", "interface Object {}"),
            )
        )
        compiler = NodeSDKTypeScriptCompiler(sdk, self.node)
        checks = 0

        def current():
            nonlocal checks
            checks += 1
            if checks >= 3:
                raise RuntimeError("compiler owner ended in flight")

        with self.assertRaisesRegex(RuntimeError, "owner ended in flight"):
            compiler.run(
                files=(self.source,),
                roots=("src/index.ts",),
                operation="compile",
                environment=self.environment,
                require_current=current,
            )
        self.assertGreaterEqual(checks, 3)

    def test_request_is_closed_even_when_calling_helper_directly(self):
        import subprocess

        packet = {
            "version": 1,
            "operation": "check",
            "files": [],
            "roots": [],
            "compiler_files": [],
            "extra": True,
        }
        result = subprocess.run(
            (*self.node.command, "--eval", self.compiler._helper),
            input=json.dumps(packet).encode(),
            capture_output=True,
            timeout=10,
            env=self.environment,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"request shape", result.stderr)

    def test_snapshot_bytes_are_executed_without_compiler_path_lookup(self):
        sdk = TypeScriptSDK(
            (
                file("package.json", '{"name":"typescript","version":"6.0.3"}'),
                file("lib/typescript.js", 'throw Error("selected snapshot reached");'),
                file("lib/lib.es2022.d.ts", "interface Object {}"),
            )
        )
        compiler = NodeSDKTypeScriptCompiler(sdk, self.node)
        with self.assertRaisesRegex(ValueError, "selected snapshot reached"):
            compiler.run(
                files=(file("src/index.ts", "export const n=1;"),),
                roots=("src/index.ts",),
                operation="compile",
                environment=self.environment,
                require_current=lambda: None,
            )
