"""Compiler-owner denials and opt-in real SDK compilation, not qualification."""

import base64
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.builders.javascript import (
    discover_node_toolchain,
    discover_npm_toolchain,
)
from literate_ai.adapters.builders.typescript_sdk import (
    capture_typescript_sdk_toolchain,
)
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_build import compile_node_sdk_plan
from literate_ai.adapters.node_sdk_packaging import (
    pack_node_sdk,
    require_node_sdk_tarball,
)
from literate_ai.adapters.node_sdk_tools import node_sdk_tool_environment
from literate_ai.adapters.node_sdk_typescript import (
    NodeSDKTypeScriptCompiler,
    TypeScriptSDK,
    _inventory,
)
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.storage.cas import FileSystemCAS
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
            '{"name":"typescript","version":"6.0.3","type":"module"}',
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
        # Explicit selection exercises the production custody owner before the
        # real compiler tests; it never installs or discovers an SDK package.
        root = Path(os.environ["LITERATE_TYPESCRIPT_SDK"]).resolve(strict=True)
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.environment = dict(os.environ)
        cls.environment.pop("NODE_OPTIONS", None)
        cls.environment.pop("NODE_PATH", None)
        cls.node = discover_node_toolchain(cls.environment)
        selected = capture_typescript_sdk_toolchain(
            root,
            node=cls.node,
            store=FileSystemCAS(Path(temporary.name) / "cas"),
            constraint_identity=canonical_identity({"test_tool": "typescript"}),
            version_constraint=">=5.8.0",
            environment=cls.environment,
            require_current=lambda: None,
        )
        cls.compiler = selected.compiler

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

    def compile_plan(self, **changes):
        arguments = dict(self.fixture.arguments)
        authority = arguments.pop("source")
        for name in ("compiled", "compiler", "node"):
            del arguments[name]
        arguments.update(changes)
        return compile_node_sdk_plan(
            self.fixture.fixture.consumer,
            source_authority=authority,
            source_files=(self.source,),
            compiler=self.compiler,
            environment=self.environment,
            require_current=lambda: None,
            **arguments,
        )

    def test_shared_compile_plan_rejects_changed_bindings_before_execution(self):
        with patch.object(NodeSDKTypeScriptCompiler, "run") as run:
            with self.assertRaisesRegex(ValueError, "bindings differ"):
                self.compile_plan(build_bindings=())
            run.assert_not_called()

    def test_shared_compile_plan_reopens_provider_before_publication(self):
        original = self.fixture.arguments["read_blob"]
        reads = 0

        def changed(blob):
            nonlocal reads
            reads += 1
            content = original(blob)
            return content if reads == 1 else content + b"changed"

        with self.assertRaisesRegex(ValueError, "differs from pinned bytes"):
            self.compile_plan(read_blob=changed)
        self.assertEqual(reads, 2)

    @unittest.skipUnless(shutil.which("npm"), "requires selected local npm")
    def test_real_shared_compile_pack_relocate_and_type_consumers(self):
        import io
        import subprocess
        import tarfile

        npm = discover_npm_toolchain(
            self.node,
            self.environment,
            version_constraint=">=10.0.0",
            constraint_identity=self.fixture.arguments["packer"].uri,
        )
        compiled = self.compile_plan(packer=ContentIdentity.parse_uri(npm.identity))
        self.assertEqual(compiled.plan.compiler, self.compiler.identity)
        self.assertTrue(
            any(name.endswith(".d.ts") for name in compiled.compiler_inputs)
        )
        packed = pack_node_sdk(
            compiled.plan,
            self.fixture.fixture.root / "compiled-pack",
            npm=npm,
            environment=self.environment,
            require_current=lambda: None,
        )
        require_node_sdk_tarball(compiled.plan, packed.content)
        root = self.fixture.fixture.root / "compiled-relocated"
        package = root / "node_modules/counter-sdk"
        package.mkdir(parents=True)
        files = []
        with tarfile.open(fileobj=io.BytesIO(packed.content), mode="r:gz") as archive:
            for member in archive:
                name = member.name.removeprefix("package/")
                content = archive.extractfile(member).read()
                destination = package / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                files.append(file("node_modules/counter-sdk/" + name, content))
        consumer = (
            "import {CounterError," + self.fixture.symbol + "} from 'counter-sdk';"
            "import {CounterError as Other} from 'counter-sdk/counter';"
            "const e:Error=new Other('bad');const n:number="
            + self.fixture.symbol
            + "(2,3);\n// @ts-expect-error preserve numeric arguments\n"
            + self.fixture.symbol
            + "('bad',3);"
        )
        files.extend((file("consumer.cts", consumer), file("consumer.mts", consumer)))
        checked = self.run_compiler(files, ("consumer.cts", "consumer.mts"))
        self.assertTrue(checked.success, checked.diagnostics)
        for esm in (False, True):
            script = (
                "import * as a from 'counter-sdk';"
                "import * as b from 'counter-sdk/counter';"
                if esm
                else "const a=require('counter-sdk'),b=require('counter-sdk/counter');"
            )
            script += (
                "if(a.CounterError!==b.CounterError||a."
                + self.fixture.symbol
                + "(2,3)!==5)process.exit(1);"
            )
            result = subprocess.run(
                (
                    *self.node.command,
                    *(["--input-type=module"] if esm else []),
                    "--eval",
                    script,
                ),
                cwd=root,
                env=self.environment,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())

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

        packet = json.loads(
            self.compiler._request_packet(
                {
                    "version": 1,
                    "operation": "compile",
                    "roots": ["src/index.ts"],
                    "files": rows((*self.provider_files, self.source)),
                }
            )
        )
        packet["helper"] = helper
        command = (
            *self.compiler.command[:-2],
            hashlib.sha256(helper.encode()).hexdigest(),
            self.compiler.command[-1],
        )
        result = self.raw_packet(packet, command=command)
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

    def raw_packet(self, packet, *, command=None):
        from literate_ai.adapters.builders._process import run_bounded_process

        return run_bounded_process(
            self.compiler.command if command is None else command,
            cwd=None,
            environment=self.environment,
            timeout_seconds=30,
            stdout_limit_bytes=48 * 1024 * 1024,
            stderr_limit_bytes=1024 * 1024,
            error_prefix="compiler protocol test",
            input_bytes=json.dumps(packet).encode(),
            input_limit_bytes=64 * 1024 * 1024,
            terminate_descendants=True,
            trace=False,
        )

    def test_request_is_closed_even_when_calling_bootstrap_directly(self):
        request = {
            "version": 1,
            "operation": "check",
            "files": [],
            "roots": [],
            "compiler_files": [],
            "extra": True,
        }
        result = self.raw_packet(json.loads(self.compiler._request_packet(request)))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"request shape", result.stderr)
        self.assertFalse(result.stdout)

    def test_helper_and_sdk_substitution_cannot_execute_supplied_code(self):
        packet = json.loads(
            self.compiler._request_packet(
                {
                    "version": 1,
                    "operation": "compile",
                    "files": [
                        {
                            "path": "src/index.ts",
                            "content": base64.b64encode(b"export const n=1;").decode(),
                        }
                    ],
                    "roots": ["src/index.ts"],
                }
            )
        )
        changed = dict(packet)
        changed["helper"] += "\nprocess.stdout.write('untrusted helper ran');"
        result = self.raw_packet(changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"helper differs", result.stderr)
        self.assertFalse(result.stdout)
        changed = dict(packet)
        sdk = json.loads(changed["compiler_snapshot"])
        for row in sdk:
            if row["path"] == "lib/typescript.js":
                row["content"] = base64.b64encode(
                    b"process.stdout.write('untrusted SDK ran');"
                ).decode()
        changed["compiler_snapshot"] = json.dumps(
            sdk, sort_keys=True, separators=(",", ":")
        )
        result = self.raw_packet(changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"SDK differs", result.stderr)
        self.assertFalse(result.stdout)
        changed = dict(packet)
        changed["extra"] = True
        result = self.raw_packet(changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(result.stdout)

    def test_worker_command_is_bounded_and_selection_is_identity_bound(self):
        self.assertLessEqual(len(self.compiler.command), 64)
        self.assertTrue(
            all(len(token.encode()) <= 4096 for token in self.compiler.command)
        )
        self.assertEqual(
            self.compiler.command[: len(self.node.command)], self.node.command
        )
        changed = replace(
            self.compiler,
            selection_identity=ContentIdentity.parse_uri(
                self.fixture.arguments["source"].uri
            ),
        )
        self.assertNotEqual(changed.identity, self.compiler.identity)
        self.assertEqual(changed.command, self.compiler.command)
        self.assertEqual(changed.sdk.identity, self.compiler.sdk.identity)

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

    def test_selected_node_flag_is_used_by_real_compiler(self):
        node = discover_node_toolchain(
            self.environment,
            pinned_command=(self.node.command[0], "--no-warnings"),
        )
        compiler = NodeSDKTypeScriptCompiler(self.compiler.sdk, node)
        self.assertEqual(compiler.command[:2], node.command)
        result = compiler.run(
            files=(file("src/index.ts", "export const value: number = 42;"),),
            roots=("src/index.ts",),
            operation="compile",
            environment=self.environment,
            require_current=lambda: None,
        )
        self.assertTrue(result.success, result.diagnostics)
        self.assertEqual(len(result.outputs), 4)
