"""Actual local adapter input creators and original parent retirement."""

import json
import os
import subprocess
import unittest
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import evidence_staging
from literate_ai.adapters.builders import discover_cpp_toolchain
from literate_ai.adapters.builders.python import BuildError
from literate_ai.adapters.lifecycle import local
from literate_ai.adapters.project_runtime import (
    ProjectRuntimeError,
    allocate_project_runtime,
    close_project_runtime,
    project_runtime_scope,
)
from literate_ai.security import AuthorizationRevocationSet
from tests.critical import test_project_layout_runtime_cli as runtime_fixture
from tests.e2e import test_rust_javascript_builder as authority_fixture


class ContainedBuildInputTests(unittest.TestCase):
    def setUp(self):
        self.f = runtime_fixture.ProjectLayoutRuntimeCliTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.owner = allocate_project_runtime(self.f.project, nested=True)
        self.addCleanup(self.close)
        self.observed = []

    def close(self, *, keep=False):
        if self.owner is not None:
            owner, self.owner = self.owner, None
            close_project_runtime(owner, keep=keep)

    def build(
        self,
        language="rust",
        *,
        after=None,
        before=None,
        invalid=False,
        standalone=False,
    ):
        if language == "python":
            adapter = local.PythonBuildAdapter
            guarded = local.GuardedPythonBuilder
            toolchain = local.discover_python_toolchain()
            files = {"source/main.py": "print(42)\n"}
            outputs = ("python-bytecode",)
        elif language == "cpp":
            adapter = local.CppBuildAdapter
            guarded = local.GuardedCppBuilder
            toolchain = discover_cpp_toolchain()
            files = {
                "source/main.cpp": (
                    '#include <iostream>\nint main() { std::cout << 42 << "\\n"; }\n'
                )
            }
            outputs = ("native-executable",)
        elif language == "swift":
            adapter = local.SwiftBuildAdapter
            guarded = local.GuardedSwiftBuilder
            toolchain = discover_cpp_toolchain({**os.environ, "CXX": "swiftc"})
            files = {"source/main.swift": "print(42)\n"}
            outputs = ("native-executable",)
        elif language == "javascript":
            adapter = local.JavaScriptBuildAdapter
            guarded = local.GuardedJavaScriptBuilder
            toolchain = local.discover_node_toolchain()
            files = {"source/main.js": "console.log(42);\n"}
            outputs = ("javascript-checked-bundle",)
        elif language == "composite":
            adapter = local.RustJavaScriptBuildAdapter
            guarded = local.GuardedRustJavaScriptBuilder
            toolchain = local.discover_rust_javascript_toolchain()
            files = authority_fixture.GuardedRustJavaScriptBuilderTests.files()
            outputs = authority_fixture.FULL_STACK_OUTPUTS
        else:
            adapter = local.RustBuildAdapter
            guarded = local.GuardedRustBuilder
            toolchain = local.discover_rust_toolchain()
            files = {
                "source/main.rs": "fn main() { missing_symbol(); }\n"
                if invalid
                else 'fn main() { println!("42"); }\n'
            }
            outputs = ("native-executable",)
        request, authorization = authority_fixture._request_and_authorization(
            source_digest=authority_fixture._source_digest(files),
            builder_id=guarded.builder_id,
            toolchain_identity=toolchain.identity,
            allowed_outputs=outputs,
        )
        value = {**request.to_dict(), "artifact": {"files": files}}
        original = guarded.build

        def original_build(builder, *args, **kwargs):
            root = Path(kwargs["source_root"])
            self.observed.append(root)
            if before is not None:
                before(root)
            try:
                result = original(builder, *args, **kwargs)
            except BaseException as error:
                if after is not None:
                    after(root, error)
                raise
            if after is not None:
                after(root, result)
            return result

        scope = (
            nullcontext()
            if standalone
            else project_runtime_scope(self.owner, self.f.project)
        )
        store = (
            self.f.framework / "_build/artifacts"
            if standalone
            else self.owner.object_root / "artifacts"
        )
        with scope, patch.object(guarded, "build", original_build):
            result = adapter(
                store,
                toolchain=toolchain,
                clock=lambda: authority_fixture.NOW + timedelta(minutes=1),
                authorization_verifier=AuthorizationRevocationSet(),
            ).build(value, authorization.to_dict())
        return result, toolchain

    def assert_adapter(self, language="rust", *, standalone=False):
        result, toolchain = self.build(language, standalone=standalone)
        root = Path(result["artifact_path"])
        if language == "python":
            command = [*toolchain.command, str(root / "source/main.pyc")]
        elif language == "javascript":
            command = [*toolchain.command, str(root / result["entrypoint_file"])]
        elif language == "composite":
            command = [str(root / result["backend_executable_file"]), '{"value":7}']
        else:
            command = [str(root / result["executable_file"])]
        output = subprocess.run(
            command,
            cwd=root,
            env=authority_fixture.controlled_node_environment(dict(os.environ)),
            capture_output=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(output.returncode, 0, output.stderr)
        if language == "composite":
            self.assertEqual(json.loads(output.stdout), {"echo": {"value": 7}})
        else:
            self.assertEqual(output.stdout, b"42\n")
        self.assertEqual(len(self.observed), 1)
        self.assertTrue(self.observed[0].is_relative_to(self.f.framework / "_build"))
        self.assertFalse(self.observed[0].exists())
        self.assertEqual(self.f.native.read_bytes(), b"original application\n")

    def test_actual_rust_adapter_materializes_inputs_under_litai(self):
        self.assert_adapter()

    def test_actual_python_adapter_materializes_inputs_under_litai(self):
        self.assert_adapter("python")

    def test_actual_cpp_adapter_materializes_inputs_under_litai(self):
        self.assert_adapter("cpp")

    def test_actual_swift_adapter_materializes_inputs_under_litai(self):
        self.assert_adapter("swift")

    def test_actual_javascript_adapter_materializes_inputs_under_litai(self):
        self.assert_adapter("javascript")

    def test_actual_composite_adapter_materializes_inputs_under_litai(self):
        self.assert_adapter("composite")

    def test_actual_standalone_adapter_uses_fresh_project_owner(self):
        self.close()
        self.assert_adapter(standalone=True)

    def test_private_input_keeps_parent_and_expires_original_runtime(self):
        seen = {}

        def private(root, result):
            path = root / "operator-private"
            path.write_bytes(b"preserve private build input")
            seen.update(path=path, inode=path.stat().st_ino)

        with self.assertRaises(BuildError) as caught:
            self.build(after=private)
        self.assertEqual(caught.exception.code, "builder.input_custody")
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
        self.assertEqual(seen["path"].read_bytes(), b"preserve private build input")

    def test_equal_byte_foreign_input_is_not_retired(self):
        seen = {}

        def replace(root, result):
            path = root / "source/main.rs"
            retained = root.parent / "actual-input-original"
            path.rename(retained)
            path.write_bytes(retained.read_bytes())
            seen.update(path=path, retained=retained, inode=path.stat().st_ino)

        with self.assertRaises(BuildError) as caught:
            self.build(after=replace)
        self.assertEqual(caught.exception.code, "builder.input_custody")
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
        self.assertEqual(seen["path"].read_bytes(), seen["retained"].read_bytes())

    def test_actual_compiler_failure_wins_over_input_disposal_conflict(self):
        seen = {}

        def private(root, result):
            self.assertIsInstance(result, BuildError)
            path = root / "operator-private"
            path.write_bytes(b"preserve failing build input")
            seen.update(path=path, inode=path.stat().st_ino)

        with self.assertRaises(BuildError) as caught:
            self.build(after=private, invalid=True)
        self.assertEqual(caught.exception.code, "builder.rust_compile_failed")
        self.assertTrue(
            any("disposal refused" in note for note in caught.exception.__notes__)
        )
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])

    def test_actual_partial_creator_failure_preserves_private_input_and_original_error(
        self,
    ):
        write = evidence_staging.EvidenceStage.write
        seen = {}
        original = OSError(5, "fixture original materializer rejected")

        def rejected(owner, relative, *args, **kwargs):
            result = write(owner, relative, *args, **kwargs)
            if relative == "source/main.rs":
                path = owner.path / "operator-private"
                path.write_bytes(b"preserve partial materialization")
                seen.update(path=path, inode=path.stat().st_ino)
                raise original
            return result

        with patch.object(evidence_staging.EvidenceStage, "write", rejected):
            with self.assertRaises(OSError) as caught:
                self.build()
        self.assertIs(caught.exception, original)
        self.assertFalse(self.observed)
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
