"""Real configured local driver rejection and persistent log; no provider action."""

import copy
import os
import shutil
import subprocess
import sys
import unittest
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai._cache_lock import cache_lock_path, exclusive_cache_lock
from literate_ai.adapters import driver_diagnostics as retention
from literate_ai.adapters import project_lifecycle_driver as driver
from literate_ai.adapters.evidence_files import _PosixAccess
from literate_ai.adapters.project_runtime import (
    ProjectRuntimeError,
    allocate_project_runtime,
    close_project_runtime,
    project_runtime_scope,
)
from literate_ai.adapters.repository_orchestration import OrchestrationInventoryError
from literate_ai.contracts import (
    MINIMUM_PROJECT_REBUILD_PHASES,
    ProjectLifecycleDriver,
    canonical_identity,
)
from literate_ai.evidence_ledger import open_run
from literate_ai.projects import LoadedProject, serialize_project_configuration
from tests.critical import test_project_layout_runtime_cli as fixture

DATA = "complete local fixture diagnostic\n" * 80 + "fatal: original driver rejection\n"


class ContainedDriverDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ProjectLayoutRuntimeCliTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.project.root
        self.script = self.root / "driver.py"
        self.script.write_text(
            "import os,sys,time\n"
            "if os.environ.get('LITAI_FIXTURE_SLEEP')=='1': time.sleep(60)\n"
            "if '--allow-host-execution' not in sys.argv: sys.exit(0)\n"
            "sys.stderr.write(" + repr(DATA) + ")\nsys.exit(7)\n"
        )
        provisional = ProjectLifecycleDriver(
            driver_id="fixture",
            version="1.0.0",
            implementation_paths=("driver.py",),
            implementation_identity=canonical_identity({"provisional": True}),
            argv=(
                "{python}",
                "driver.py",
                "{project}",
                "{specification}",
                "{runtime_root}",
                "{candidate_receipt}",
                "{project_revision_identity}",
                "{lifecycle_request_identity}",
                "{flavor_args}",
                "{allow_host_execution}",
            ),
            environment_keys=("PATH",),
            phases=MINIMUM_PROJECT_REBUILD_PHASES,
            specification_scope="project",
        )
        configured = replace(
            provisional,
            implementation_identity=driver.lifecycle_driver_implementation_identity(
                self.f.project, provisional
            ),
        )
        definition = replace(self.f.project.definition, lifecycle_driver=configured)
        self.project = LoadedProject(self.root, definition)
        (self.f.framework / "literate.project.json").write_bytes(
            serialize_project_configuration(definition)
        )
        self.binding = driver.bind_external_project_lifecycle_driver(
            self.project,
            configured,
            {"PATH": os.environ.get("PATH", ""), "CODING_CLI": "codex"},
        )
        self.owner = allocate_project_runtime(self.project, nested=True)
        self.addCleanup(self.close)
        self.ledger = None
        self.reported = []

    def close(self):
        if self.owner is not None:
            owner, self.owner = self.owner, None
            close_project_runtime(owner, keep=False)

    def execute(
        self,
        *,
        after=None,
        reporter=None,
        allow_host_execution=True,
        timeout=None,
        environment=None,
    ):
        runtime = (
            self.owner.path
            if self.owner is not None
            else self.f.framework / "_build/external-runtime"
        )
        if self.owner is None:
            runtime.mkdir(exist_ok=True)
        argv = self.binding.command(
            specification=self.root,
            runtime_root=runtime,
            candidate_receipt=runtime / "candidate.json",
            project_revision=canonical_identity({"fixture": "project"}),
            request_identity=canonical_identity({"fixture": "request"}),
            flavor_selectors=(),
            allow_host_execution=allow_host_execution,
        )
        original = driver.run_bounded_process

        def run(*args, **kwargs):
            result = original(*args, **kwargs)
            if after is not None:
                after()
            return result

        def report(message):
            self.reported.append(message)
            if reporter is not None:
                reporter(message)

        scope = (
            project_runtime_scope(self.owner, self.project)
            if self.owner is not None
            else nullcontext()
        )
        with scope:
            # Only ambient metadata/reporting ports are supplied. Original native
            # child creation, stderr, file writers and readback still execute.
            with (
                patch.object(driver, "attach_run", return_value=self.ledger),
                patch.object(driver, "report_progress", side_effect=report),
                patch.object(driver, "run_bounded_process", side_effect=run),
            ):
                self.binding.run(argv, timeout_seconds=timeout, environment=environment)

    def fail_driver(self, **kwargs):
        with self.assertRaises(driver.ProjectLifecycleDriverAdapterError) as caught:
            self.execute(**kwargs)
        self.assertEqual(caught.exception.code, "rebuild.driver_failed")
        self.assertIn("fatal: original driver rejection", caught.exception.message)
        return caught.exception

    def test_original_failed_driver_retains_complete_contained_log_after_runtime(self):
        error = self.fail_driver()
        path = Path(error.message.rsplit("; complete driver output: ", 1)[1])
        self.assertEqual(path.read_text(), DATA)
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                (
                    "import pathlib,sys;"
                    "assert pathlib.Path(sys.argv[1]).read_text()==sys.argv[2]"
                ),
                str(path),
                DATA,
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.close()
        self.assertEqual(path.read_text(), DATA)
        self.assertTrue(path.is_relative_to(self.f.framework / "_build"), path)

    def test_success_creates_no_diagnostic_and_releases_native_capture(self):
        self.execute(allow_host_execution=False)
        self.assertEqual(list((self.f.framework / "_build").glob(".df-*.log")), [])
        self.assertEqual(self.reported, [])
        self.close()

    def test_actual_partial_writer_failure_keeps_driver_error_and_original_partial(
        self,
    ):
        original = retention._write_payload

        def partial(descriptor, payload):
            original(descriptor, payload[:5])
            raise OSError("physical fixture diagnostic write failure")

        with patch.object(retention, "_write_payload", side_effect=partial):
            error = self.fail_driver()
        self.assertNotIn("; complete driver output:", error.message)
        self.assertTrue(
            any(
                "diagnostic custody unavailable" in n.casefold()
                for n in error.__notes__
            )
        )
        logs = list((self.f.framework / "_build").glob(".df-*.log"))
        self.assertEqual(len(logs), 1)
        inode = logs[0].stat().st_ino
        self.close()
        self.assertEqual(logs[0].stat().st_ino, inode)
        self.assertEqual(logs[0].read_bytes(), DATA.encode()[:5])

    @unittest.skipUnless(os.name == "posix", "actual POSIX competing exclusive creator")
    def test_actual_exclusive_collision_preserves_competing_private_file(self):
        original = _PosixAccess.open
        paths = []

        def competing(access, parts, flags, mode=0o600):
            if flags & os.O_CREAT and parts[-1].startswith(".df-"):
                descriptor = original(access, parts, flags, mode)
                try:
                    os.write(descriptor, b"private competing diagnostic state")
                finally:
                    os.close(descriptor)
                path = access.root / parts[-1]
                paths.append((path, path.stat().st_ino))
            return original(access, parts, flags, mode)

        with patch.object(_PosixAccess, "open", competing):
            error = self.fail_driver()
        self.assertNotIn("; complete driver output:", error.message)
        self.assertEqual(len(paths), 1)
        path, inode = paths[0]
        self.close()
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_bytes(), b"private competing diagnostic state")

    def test_private_neighbor_and_log_survive_original_runtime_close(self):
        saved = []

        def report(message):
            path = Path(message.rsplit(": ", 1)[1])
            private = path.with_name(path.name + ".operator-private")
            with private.open("xb") as output:
                output.write(b"retain private diagnostic neighbor")
            saved.append((private, private.stat().st_ino))

        error = self.fail_driver(reporter=report)
        path = Path(error.message.rsplit("; complete driver output: ", 1)[1])
        self.close()
        private, inode = saved[0]
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"retain private diagnostic neighbor")
        self.assertEqual(path.read_text(), DATA)

    def test_equal_byte_foreign_diagnostic_is_not_published_or_removed(self):
        saved = []

        def report(message):
            path = Path(message.rsplit(": ", 1)[1])
            original = self.root / "retained-original-diagnostic"
            if os.name == "nt":
                with self.assertRaises(PermissionError):
                    path.rename(original)
                saved.append((path, path.stat().st_ino, None, None))
                return
            path.rename(original)
            shutil.copyfile(original, path)
            shutil.copystat(original, path)
            saved.append((path, path.stat().st_ino, original, original.stat().st_ino))

        error = self.fail_driver(reporter=report)
        self.close()
        path, inode, original, native = saved[0]
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_text(), DATA)
        if original is not None:
            self.assertNotIn("; complete driver output:", error.message)
            self.assertNotEqual(inode, native)
            self.assertEqual(original.stat().st_ino, native)
            self.assertEqual(original.read_text(), DATA)

    def test_manifest_change_after_original_process_cannot_mint_log_authority(self):
        manifest = self.f.framework / "literate.project.json"
        changed = serialize_project_configuration(
            replace(self.project.definition, project_id="changed-driver-project")
        )

        def change():
            manifest.write_bytes(changed)

        error = self.fail_driver(after=change)
        self.assertNotIn("; complete driver output:", error.message)
        self.assertEqual(list((self.f.framework / "_build").glob(".df-*.log")), [])
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(manifest.read_bytes(), changed)

    def test_parent_substitution_preserves_both_namespaces(self):
        parent = self.f.framework / "_build"
        original_inode = parent.stat().st_ino
        original = self.root / "retained-original-build"
        saved = []

        def change():
            if os.name == "nt":
                with self.assertRaises(PermissionError):
                    parent.rename(original)
                return
            parent.rename(original)
            parent.mkdir()
            private = parent / "operator-private"
            private.write_bytes(b"retain replaced output parent")
            saved.append((private, private.stat().st_ino))

        error = self.fail_driver(after=change)
        if os.name == "nt":
            self.assertIn("; complete driver output:", error.message)
            return
        self.assertNotIn("; complete driver output:", error.message)
        with self.assertRaises(OrchestrationInventoryError) as refused:
            self.close()
        self.assertEqual(
            refused.exception.code, "orchestration.reservation_cleanup_incomplete"
        )
        private, inode = saved[0]
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"retain replaced output parent")
        self.assertTrue(original.is_dir())
        self.assertEqual(original.stat().st_ino, original_inode)
        self.assertNotEqual(parent.stat().st_ino, original_inode)
        self.assertEqual(list(parent.glob(".df-*.log")), [])
        self.assertEqual(list(original.glob(".df-*.log")), [])

    def test_standalone_capture_does_not_hold_driver_lifecycle_mutex(self):
        self.close()
        acquired = []
        lock = cache_lock_path(self.root, self.f.framework / "_build", "lifecycle.lock")

        def probe():
            with exclusive_cache_lock(lock, timeout_seconds=0.2):
                acquired.append(True)

        error = self.fail_driver(after=probe)
        self.assertEqual(acquired, [True])
        path = Path(error.message.rsplit("; complete driver output: ", 1)[1])
        self.assertTrue(path.is_relative_to(self.f.framework / "_build"))
        self.assertEqual(path.read_text(), DATA)

    def test_aliased_output_parent_never_receives_diagnostic_or_global_fallback(self):
        self.close()
        parent = self.f.framework / "_build"
        parent.rename(self.root / "retained-build-before-alias")
        target = self.root / "private-target"
        target.mkdir()
        private = target / "private"
        private.write_bytes(b"retain aliased target")
        inode = private.stat().st_ino
        parent.symlink_to(target, target_is_directory=True)
        # No fixture runtime allocation through the alias: supply only an
        # existing separate runtime argument to the original driver command.
        runtime = self.root / "separate-driver-runtime"
        runtime.mkdir()
        argv = self.binding.command(
            specification=self.root,
            runtime_root=runtime,
            candidate_receipt=runtime / "candidate.json",
            project_revision=canonical_identity({"fixture": "project"}),
            request_identity=canonical_identity({"fixture": "request"}),
            flavor_selectors=(),
        )
        original_mkstemp = driver.tempfile.mkstemp

        def refuse_global(*args, **kwargs):
            if (
                kwargs.get("prefix") == "litai-driver-failure-"
                and kwargs.get("dir") is None
            ):
                raise AssertionError("global diagnostic fallback")
            return original_mkstemp(*args, **kwargs)

        with patch.object(driver.tempfile, "mkstemp", side_effect=refuse_global):
            with self.assertRaises(driver.ProjectLifecycleDriverAdapterError) as caught:
                self.binding.run(argv)
        self.assertEqual(caught.exception.code, "rebuild.driver_failed")
        self.assertNotIn("; complete driver output:", caught.exception.message)
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"retain aliased target")
        self.assertEqual(list(target.iterdir()), [private])

    def test_timeout_keeps_original_code_without_diagnostic_output(self):
        environment = {**self.binding.environment, "LITAI_FIXTURE_SLEEP": "1"}
        with self.assertRaises(driver.ProjectLifecycleDriverAdapterError) as caught:
            self.execute(timeout=0.1, environment=environment)
        self.assertEqual(caught.exception.code, "rebuild.driver_timeout")
        self.assertEqual(list((self.f.framework / "_build").glob(".df-*.log")), [])
        self.close()

    def test_optional_ledger_records_original_file_instead_of_copying_it(self):
        with patch.dict(os.environ, {"OBJ_DIR": str(self.f.framework / "_build")}):
            os.environ.pop("LITAI_EVIDENCE_PARENT", None)
            self.ledger = open_run(self.root, operation="fixture.driver")
            self.assertIsNotNone(self.ledger)
            error = self.fail_driver()
        path = Path(error.message.rsplit("; complete driver output: ", 1)[1])
        ledger = self.ledger.ledger_path.read_text()
        self.assertIn("driver-diagnostic", ledger)
        self.assertIn(path.name, ledger)
        self.assertEqual(list(self.ledger.root.rglob("driver.log")), [])
        self.close()
        self.assertEqual(path.read_text(), DATA)

    def test_copied_and_expired_capture_cannot_create_another_file(self):
        actual = retention.driver_diagnostic_capture
        saved = []

        @contextmanager
        def observe(*args, **kwargs):
            with actual(*args, **kwargs) as capture:
                saved.append(capture)
                with self.assertRaises((TypeError, ValueError)):
                    copy.copy(capture).retain(DATA)
                yield capture

        with patch.object(retention, "driver_diagnostic_capture", observe):
            self.fail_driver()
        with self.assertRaises(ValueError):
            saved[0].retain(DATA)
        self.assertEqual(len(list((self.f.framework / "_build").glob(".df-*.log"))), 1)
