"""Actual guarded compilers, closing output custody and runtime lifetime."""

import json
import os
import subprocess
import sys
import time
import unittest
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.builders import _process, go, rust, rust_javascript
from literate_ai.adapters.builders.python import BuildError, canonical_tree_digest
from literate_ai.adapters.project_runtime import (
    allocate_project_runtime,
    close_project_runtime,
    project_runtime_scope,
)
from literate_ai.security import AuthorizationRevocationSet
from tests.critical import test_go_runtime_source as go_fixture
from tests.critical import test_guarded_rust_builder as rust_fixture
from tests.critical import test_project_layout_runtime_cli as runtime_fixture
from tests.e2e import test_rust_javascript_builder as composite_fixture


class ContainedCompilerWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.f = runtime_fixture.ProjectLayoutRuntimeCliTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.project = self.f.project
        self.owner = allocate_project_runtime(self.project, nested=True)
        self.addCleanup(self.close)
        self.observed = []

    def close(self):
        if self.owner is not None:
            owner, self.owner = self.owner, None
            close_project_runtime(owner, keep=False)

    def build(self, *, language="rust", callback=None, invalid=False, standalone=False):
        scope = (
            nullcontext()
            if standalone
            else project_runtime_scope(self.owner, self.project)
        )
        with scope:
            generated = (
                (self.project.framework_root / "_build" / "standalone-source")
                if standalone
                else self.owner.path / "generated"
            )
            artifacts = (
                generated.parent / "artifacts"
                if standalone
                else self.owner.object_root / "artifacts"
            )
            if language == "rust-javascript":
                files = composite_fixture.GuardedRustJavaScriptBuilderTests.files()
                module = rust_javascript
                toolchain = module.discover_rust_javascript_toolchain()
                builder_type = module.GuardedRustJavaScriptBuilder
                outputs = composite_fixture.FULL_STACK_OUTPUTS
            elif language == "go":
                files = {
                    "source/main.go": go_fixture._MAIN,
                    "source/tests/litai_runtime.go": go_fixture._TESTS,
                    "source/tests/manifest.json": '{"cases":[]}',
                }
                module = go
                toolchain = module.discover_go_toolchain()
                builder_type = module.GuardedGoBuilder
                outputs = ("native-executable",)
            else:
                files = {
                    "source/main.rs": "fn main() { missing_symbol(); }\n"
                    if invalid
                    else 'fn main() { println!("42"); }\n'
                }
                module = rust
                toolchain = rust_fixture.GuardedRustBuilderTests.toolchain()
                builder_type = module.GuardedRustBuilder
                outputs = ("native-executable",)
            for relative, content in files.items():
                path = generated / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            request, authorization = composite_fixture._request_and_authorization(
                source_digest=canonical_tree_digest(generated),
                builder_id=builder_type.builder_id,
                toolchain_identity=toolchain.identity,
                allowed_outputs=outputs,
            )
            run = module._run_bounded_process

            def original_command(command, **kwargs):
                output = None
                if "--out-dir" in command:
                    output = Path(command[command.index("--out-dir") + 1])
                elif language == "go" and "build" in command and "-o" in command:
                    output = Path(command[command.index("-o") + 1]).parent
                if output is not None:
                    self.observed.append(output)
                result = run(command, **kwargs)
                if output is not None and callback is not None:
                    callback(output, result)
                return result

            with patch.object(
                module, "_run_bounded_process", side_effect=original_command
            ):
                artifact = builder_type(toolchain, AuthorizationRevocationSet()).build(
                    request,
                    authorization,
                    source_root=generated,
                    artifact_store=artifacts,
                    now=composite_fixture.NOW + timedelta(minutes=1),
                    lifecycle_consumed_files=("source/tests/manifest.json",)
                    if language == "go"
                    else (),
                )
            return artifact

    def assert_native_output(self, artifact, *, composite=False, go_output=False):
        filename = (
            artifact.backend_executable_file if composite else artifact.executable_file
        )
        executable = artifact.artifact_path / filename
        arguments = [str(executable), '{"value":7}'] if composite else [str(executable)]
        if go_output:
            arguments.append("--litai-smoke")
        result = subprocess.run(arguments, capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        if composite:
            self.assertEqual(json.loads(result.stdout), {"echo": {"value": 7}})
        elif go_output:
            self.assertEqual(json.loads(result.stdout), {"status": "ok"})
        else:
            self.assertEqual(result.stdout, b"42\n")
        self.assertEqual(len(self.observed), 1)
        self.assertTrue(
            self.observed[0].is_relative_to(self.project.framework_root / "_build")
        )
        self.assertFalse(self.observed[0].exists())

    def test_actual_authorized_rust_compiler_output_is_contained(self):
        self.assert_native_output(self.build())

    def test_actual_authorized_go_compiler_output_is_contained(self):
        self.assert_native_output(self.build(language="go"), go_output=True)

    def test_actual_authorized_composite_backend_output_is_contained(self):
        self.assert_native_output(
            self.build(language="rust-javascript"), composite=True
        )

    def test_foreign_native_output_survives_original_runtime_cleanup(self):
        seen = {}

        def foreign(root, result):
            path = root / "operator-private"
            path.write_bytes(b"preserve compiler private state")
            seen.update(path=path, inode=path.stat().st_ino)

        with self.assertRaises(BuildError) as caught:
            self.build(callback=foreign)
        self.assertEqual(caught.exception.code, "builder.output_custody")
        self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
        self.assertEqual(seen["path"].read_bytes(), b"preserve compiler private state")
        self.assertEqual(self.f.native.read_bytes(), b"original application\n")

    def test_actual_compiler_rejection_wins_over_private_cleanup_refusal(self):
        seen = {}

        def foreign(root, result):
            self.assertNotEqual(result.returncode, 0)
            path = root / "operator-private"
            path.write_bytes(b"preserve failed compiler private state")
            seen.update(path=path, inode=path.stat().st_ino)

        with self.assertRaises(BuildError) as caught:
            self.build(callback=foreign, invalid=True)
        self.assertEqual(caught.exception.code, "builder.rust_compile_failed")
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
        self.assertTrue(
            any("disposal refused" in note for note in caught.exception.__notes__)
        )

    def test_equal_byte_executable_replacement_refuses(self):
        seen = {}

        def foreign(root, result):
            path = root / "sample"
            retained = root / "actual-original"
            path.rename(retained)
            path.write_bytes(retained.read_bytes())
            seen.update(path=path, inode=path.stat().st_ino, retained=retained)

        with self.assertRaises(BuildError) as caught:
            self.build(callback=foreign)
        self.assertEqual(caught.exception.code, "builder.output_custody")
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
        self.assertEqual(seen["path"].read_bytes(), seen["retained"].read_bytes())

    def test_postprocess_trace_cannot_enroll_private_output(self):
        seen = {}

        def trace(command, **kwargs):
            if "status" in kwargs and "--out-dir" in command:
                path = Path(command[command.index("--out-dir") + 1]) / "trace-private"
                path.write_bytes(b"trace callback is not the compiler producer")
                seen.update(path=path, inode=path.stat().st_ino)

        with patch.object(_process, "trace_subprocess", side_effect=trace):
            with self.assertRaises(BuildError) as caught:
                self.build()
        self.assertEqual(caught.exception.code, "builder.output_custody")
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])

    def run_owned_process(self, command, *, timeout=10):
        from literate_ai.adapters.project_runtime import project_compiler_workspace

        with project_runtime_scope(self.owner, self.project):
            source = self.owner.path / "process-input"
            source.mkdir()
            with project_compiler_workspace(
                self.owner.object_root, source, prefix="compiler-test-"
            ) as output:
                self.process_output = output
                return _process.run_bounded_process(
                    command,
                    cwd=source,
                    environment=dict(os.environ),
                    timeout_seconds=timeout,
                    stdout_limit_bytes=4096,
                    stderr_limit_bytes=4096,
                    error_prefix="compiler_fixture",
                    trace=False,
                )

    def test_actual_owned_timeout_keeps_original_error_and_retires_partial(self):
        with self.assertRaises(BuildError) as caught:
            self.run_owned_process(
                [sys.executable, "-B", "-c", "import time; time.sleep(30)"], timeout=0.1
            )
        self.assertEqual(caught.exception.code, "compiler_fixture_timeout")
        self.assertFalse(self.process_output.exists())

    def test_actual_failed_launch_retires_original_empty_workspace(self):
        with self.assertRaises(BuildError) as caught:
            self.run_owned_process([str(self.owner.path / "absent-compiler")])
        self.assertEqual(caught.exception.code, "compiler_fixture_launch_failed")
        self.assertFalse(self.process_output.exists())

    def test_actual_live_owned_descendant_refuses_and_is_stopped_before_release(self):
        stop = _process._terminate_process_tree
        observed = []

        def original_stop(process, **kwargs):
            observed.append(process)
            return stop(process, **kwargs)

        child = "import time; time.sleep(30)"
        parent = (
            "import subprocess,sys; subprocess.Popen([sys.executable,'-B','-c',"
            + repr(child)
            + (
                "],stdin=subprocess.DEVNULL,"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
            )
        )
        with patch.object(
            _process, "_terminate_process_tree", side_effect=original_stop
        ):
            with self.assertRaises(BuildError) as caught:
                self.run_owned_process([sys.executable, "-B", "-c", parent])
        self.assertEqual(caught.exception.code, "builder.output_custody")
        self.assertTrue(
            observed, "original owned group was released without stopping its child"
        )
        self.assertEqual(observed[0].returncode, 0)
        deadline = time.monotonic() + 5
        while True:
            try:
                os.killpg(observed[0].pid, 0)
            except ProcessLookupError:
                break
            if time.monotonic() >= deadline:
                self.fail("owned descendant group remains after original cleanup")
            time.sleep(0.01)
        self.assertTrue(self.process_output.is_dir())

    def test_actual_standalone_contained_project_issues_fresh_compiler_owner(self):
        self.close()
        self.assert_native_output(self.build(standalone=True))
