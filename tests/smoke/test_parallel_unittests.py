"""Real subprocess coverage for checkpointed module scheduling and repair."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.project_lifecycle_driver import (
    lifecycle_driver_implementation_identity,
)
from literate_ai.evidence_ledger import open_run
from literate_ai.evidence_timing import summarize_module_timing
from literate_ai.parallel_unittest_timing import FILENAME, read_module_timing
from literate_ai.parallel_unittests import available_workers
from literate_ai.projects import LoadedProject, ProjectConfigurationStore

SOURCE = Path(__file__).resolve().parents[2] / "src"


class ParallelUnittestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.environment = dict(os.environ, PYTHONPATH=str(SOURCE))
        self.state = self.root / "state.json"
        self.report = self.root / "report.json"

    def module(self, name: str, source: str) -> None:
        (self.root / f"test_{name}.py").write_text(
            textwrap.dedent(source), encoding="utf-8"
        )

    def run_suite(
        self,
        workers: int = 2,
        timeout: float = 20,
        extra: tuple[str, ...] = (),
        timing_write_failure: bool = False,
        scratch_cleanup: str | None = None,
        before_runner: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        entry = ["-m", "literate_ai.test_checkpointing"]
        if timing_write_failure:
            entry = [
                "-c",
                "import runpy; from unittest.mock import patch; "
                "patch('literate_ai.parallel_unittest_timing.MAX_RECORD_BYTES', "
                "1).start(); "
                "runpy.run_module('literate_ai.test_checkpointing', "
                "run_name='__main__')",
            ]
        if scratch_cleanup is not None:
            entry = [
                "-c",
                "import runpy, time\n"
                "from pathlib import Path\n"
                "import literate_ai.parallel_unittests as runner\n"
                "original = runner.shutil.rmtree\n"
                "def cleanup(path, *args, **kwargs):\n"
                "    if Path(path).name.startswith('litai-pt-'):\n"
                + (
                    "        raise OSError('controlled scratch cleanup failure')\n"
                    if scratch_cleanup == "failure"
                    else (
                        "        until = time.monotonic_ns() + 300_000_000\n"
                        "        while (left := until - time.monotonic_ns()) > 0:\n"
                        "            time.sleep(left / 1e9)\n"
                    )
                )
                + "    return original(path, *args, **kwargs)\n"
                "runner.shutil.rmtree = cleanup\n"
                "runpy.run_module('literate_ai.test_checkpointing', "
                "run_name='__main__')",
            ]
        if before_runner is not None:
            entry = [
                "-c",
                "import runpy\n"
                + textwrap.dedent(before_runner)
                + "\nrunpy.run_module('literate_ai.test_checkpointing', "
                "run_name='__main__')",
            ]
        return subprocess.run(
            [
                sys.executable,
                *entry,
                "python",
                "--state",
                str(self.state),
                "--start-directory",
                ".",
                "--report",
                str(self.report),
                "--workers",
                str(workers),
                "--worker-timeout",
                str(timeout),
                *extra,
            ],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_timing_observes_barriers_crash_and_cancellation_without_owning_results(
        self,
    ):
        for name, other in (("a", "b"), ("b", "a")):
            self.module(
                name,
                f'''
                import time, unittest
                from pathlib import Path
                class Tests(unittest.TestCase):
                    def test_overlap(self):
                        Path("{name}.ready").touch()
                        deadline = time.monotonic() + 20
                        while not Path("{other}.ready").exists():
                            self.assertLess(time.monotonic(), deadline)
                            time.sleep(.01)
                    @classmethod
                    def tearDownClass(cls):
                        Path("{name}.finished").touch()
            ''',
            )
        self.module(
            "c",
            """
            import unittest
            from pathlib import Path
            LITAI_TEST_SERIAL = True
            class Tests(unittest.TestCase):
                def test_barrier(self):
                    self.assertTrue(Path("a.finished").exists())
                    self.assertTrue(Path("b.finished").exists())
                    self.assertFalse(Path("e.ready").exists())
        """,
        )
        self.module(
            "d",
            """
            import os, time, unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_crash(self):
                    deadline = time.monotonic() + 20
                    while not Path("e.ready").exists():
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(.01)
                    os._exit(23)
        """,
        )
        self.module(
            "e",
            """
            import time, unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_cancelled(self):
                    Path("e.ready").touch()
                    time.sleep(30)
        """,
        )
        self.module(
            "f",
            """
            import unittest
            from pathlib import Path
            LITAI_TEST_SERIAL = True
            class Tests(unittest.TestCase):
                def test_never_started(self):
                    Path("f.started").touch()
        """,
        )
        completed = self.run_suite()
        self.assertEqual(completed.returncode, 1, completed.stderr)
        report = json.loads(self.report.read_text())
        artifacts = list(self.root.rglob(FILENAME))
        self.assertEqual(len(artifacts), 1)
        path = artifacts[0]
        records, issues, size = read_module_timing(
            path.parent.resolve(), path.parent.name
        )
        self.assertEqual(issues, [])
        summary = summarize_module_timing(records, invocation=path.parent.name)
        self.assertEqual(summary["issues"], [])
        self.assertEqual(summary["coverage"], "complete")
        self.assertEqual(summary["selected_modules"], 6)
        self.assertEqual(summary["observed_peak_module_overlap"], 2)
        rows = {row["module"]: row for row in summary["modules"]}
        offsets = {name: row["offsets_seconds"] for name, row in rows.items()}
        for name in ("test_a", "test_b"):
            self.assertLessEqual(
                offsets[name]["cleanup_complete"], offsets["test_c"]["setup_begin"]
            )
        for name in ("test_d", "test_e"):
            self.assertLessEqual(
                offsets["test_c"]["cleanup_complete"], offsets[name]["setup_begin"]
            )
        self.assertEqual(rows["test_d"]["disposition"], "worker-error")
        self.assertEqual(rows["test_e"]["disposition"], "peer-cancelled")
        self.assertEqual(rows["test_f"]["disposition"], "not-started-after-failure")
        self.assertIsNone(rows["test_f"]["elapsed_seconds"])
        self.assertFalse((self.root / "f.started").exists())
        self.assertLess(len(records), 64)
        self.assertLess(size, 64 * 8192)
        for name in ("a.ready", "b.ready", "a.finished", "b.finished", "e.ready"):
            (self.root / name).unlink()
        self.state.unlink()
        self.report.unlink()
        failed_diagnostics = self.run_suite(timing_write_failure=True)
        self.assertEqual(failed_diagnostics.returncode, completed.returncode)
        self.assertEqual(failed_diagnostics.stderr.count("module timing incomplete"), 1)
        repeated_report = json.loads(self.report.read_text())
        self.assertEqual(repeated_report["summary"], report["summary"])
        self.assertEqual(repeated_report["outcomes"], report["outcomes"])

    def test_worker_count_validation(self) -> None:
        for invalid in (0, -1, True, "2.5", "01", "invalid"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                available_workers(invalid)
        self.assertEqual(available_workers("3"), 3)
        self.assertGreaterEqual(available_workers("auto"), 1)

    def test_spawn_return_timing_is_sampled_before_bind_and_written_after_it(self):
        self.module(
            "one",
            """
            import unittest
            class Tests(unittest.TestCase):
                def test_pass(self):
                    self.assertTrue(True)
        """,
        )
        completed = self.run_suite(
            before_runner="""
            import json, time
            from pathlib import Path
            from literate_ai.adapters._processes import ProcessTreeOwnership
            from literate_ai.parallel_unittest_timing import ModuleTiming
            original_bind = ProcessTreeOwnership.bind
            original_emit = ModuleTiming.emit
            observations = {}
            def bind(owner, pid):
                observations["bind_started_ns"] = time.monotonic_ns()
                original_bind(owner, pid)
                observations["bind_finished_ns"] = time.monotonic_ns()
            def emit(writer, kind, **values):
                if kind == "spawn_returned":
                    offset = values.get("offset_ns")
                    Path("bind-observation.json").write_text(json.dumps({
                        "bound_before_diagnostic": "bind_finished_ns" in observations,
                        "sample_precedes_bind": (isinstance(offset, int)
                            and offset + writer.origin
                                <= observations["bind_started_ns"]),
                    }))
                original_emit(writer, kind, **values)
            ProcessTreeOwnership.bind = bind
            ModuleTiming.emit = emit
        """
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            json.loads((self.root / "bind-observation.json").read_text()),
            {"bound_before_diagnostic": True, "sample_precedes_bind": True},
        )

    def test_timing_includes_scratch_cleanup_and_keeps_failed_deletion_open(self):
        self.module(
            "one",
            """
            import unittest
            class Tests(unittest.TestCase):
                def test_pass(self):
                    self.assertTrue(True)
        """,
        )
        for mode in ("delay", "failure"):
            with self.subTest(mode=mode):
                before = set(self.root.rglob(FILENAME))
                self.state.unlink(missing_ok=True)
                completed = self.run_suite(scratch_cleanup=mode)
                paths = set(self.root.rglob(FILENAME)) - before
                self.assertEqual(len(paths), 1)
                path = paths.pop()
                request = json.loads((path.parent / "0/request.json").read_text())
                self.addCleanup(shutil.rmtree, request["scratch"], ignore_errors=True)
                records, issues, _ = read_module_timing(
                    path.parent.resolve(), path.parent.name
                )
                self.assertEqual(issues, [])
                result = summarize_module_timing(records, invocation=path.parent.name)
                row = result["modules"][0]
                if mode == "delay":
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    self.assertEqual(result["coverage"], "complete")
                    # Require the full injected interval in the same clock's
                    # integer observations; Windows tick quantization and float
                    # subtraction cannot shorten the fixture's promised span.
                    offsets = {
                        record["kind"]: record["offset_ns"] for record in records
                    }
                    for field, begin in (
                        ("scratch_cleanup_seconds", "scratch_removal_begin"),
                        ("cleanup_seconds", "cleanup_begin"),
                    ):
                        elapsed_ns = offsets["scratch_removed"] - offsets[begin]
                        self.assertGreaterEqual(elapsed_ns, 300_000_000)
                        self.assertAlmostEqual(row[field], elapsed_ns / 1e9, places=9)
                    self.assertEqual(row["scratch_disposition"], "removed")
                    self.assertEqual(
                        row["elapsed_seconds"],
                        row["offsets_seconds"]["scratch_removed"]
                        - row["offsets_seconds"]["setup_begin"],
                    )
                else:
                    self.assertNotEqual(completed.returncode, 0)
                    self.assertIn("unclosed_invocation", result["issues"])
                    self.assertIsNone(row["elapsed_seconds"])
                    self.assertIsNone(row["cleanup_seconds"])
                    self.assertEqual(row["scratch_disposition"], "unknown")

    def test_timing_registers_once_with_the_owning_evidence_run(self):
        from literate_ai.parallel_unittest_timing import ROLE, registered_module_timings

        self.module(
            "one",
            """
            import unittest
            class Tests(unittest.TestCase):
                def test_pass(self):
                    self.assertTrue(True)
        """,
        )
        with patch.dict(os.environ, {"OBJ_DIR": str(self.root / "objects")}):
            evidence = open_run(self.root, operation="timing-control")
            self.assertIsNotNone(evidence)
            self.environment["OBJ_DIR"] = str(self.root / "objects")
            self.environment["LITAI_EVIDENCE_RUN"] = str(evidence.root)
            completed = self.run_suite()
            self.assertEqual(completed.returncode, 0, completed.stderr)
            index = evidence.reduced()
            pointers = [
                output
                for node in index["nodes"]
                for output in node["outputs"]
                if output["role"] == ROLE
            ]
            self.assertEqual(len(pointers), 1)
            result = registered_module_timings(index, evidence.root)
            self.assertEqual(result["issues"], [])
            self.assertEqual(len(result["invocations"]), 1)
            self.assertEqual(result["invocations"][0]["coverage"], "complete")
            self.assertEqual(result["invocations"][0]["selected_modules"], 1)
            # CI uploads only the evidence directory. Reopen that exact archive
            # after removing the original evidence and private worker spool.
            archive = shutil.make_archive(
                str(self.root / "evidence-export"),
                "zip",
                root_dir=evidence.root.parent,
            )
            shutil.rmtree(evidence.root.parent)
            shutil.rmtree(self.root / "workers")
            downloaded = (self.root / "downloaded").resolve()
            shutil.unpack_archive(archive, downloaded)
            relocated = downloaded / evidence.root.name
            exported_index = json.loads((relocated / "index.json").read_bytes())
            exported = registered_module_timings(exported_index, relocated)
            self.assertEqual(exported, result)
            self.assertFalse(Path(pointers[0]["path"]).is_absolute())

    def test_modules_overlap_with_private_directories(self) -> None:
        for name, other in (("a", "b"), ("b", "a")):
            self.module(
                name,
                f'''
                import os, tempfile, time, unittest
                from pathlib import Path
                class Tests(unittest.TestCase):
                    def test_overlap(self):
                        Path("{name}.ready").write_text("ready")
                        deadline = time.monotonic() + 20
                        while not Path("{other}.ready").exists():
                            self.assertLess(time.monotonic(), deadline)
                            time.sleep(.01)
                        temporary = Path(tempfile.gettempdir())
                        self.assertEqual(temporary, Path(os.environ["TMPDIR"]))
                        self.assertNotEqual(temporary, Path(os.environ["OBJ_DIR"]))
                        self.assertFalse(temporary.is_relative_to(Path.cwd()))
                        self.assertTrue(Path(os.environ["LITAI_CONFIG_DIR"]).is_dir())
                        paths = str(temporary) + "\\n" + os.environ["OBJ_DIR"]
                        Path("{name}.paths").write_text(paths)
            ''',
            )
        result = self.run_suite()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(
            (self.root / "a.paths").read_text(), (self.root / "b.paths").read_text()
        )
        report = json.loads(self.report.read_text())
        self.assertEqual(report["summary"]["passed"], 2)

    def test_serial_module_is_an_exclusive_barrier(self) -> None:
        for name in ("a", "b", "c"):
            self.module(
                name,
                f'''
                import time, unittest
                from pathlib import Path
                LITAI_TEST_SERIAL = {name == "b"}
                class Tests(unittest.TestCase):
                    def test_exclusive(self):
                        if "{name}" == "b":
                            self.assertTrue(Path("a.finished").exists())
                            self.assertFalse(Path("c.started").exists())
                        Path("{name}.started").touch()
                        time.sleep(.05)
                        Path("{name}.finished").touch()
            ''',
            )
        result = self.run_suite()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_priority_dispatch_preserves_groups_ties_and_serial_barriers(self) -> None:
        for name in "abcdefg":
            priority = 100 if name == "d" else 10 if name in "cfg" else 0
            self.module(
                name,
                f'''
                import unittest
                from pathlib import Path
                LITAI_TEST_PRIORITY = {priority}
                LITAI_TEST_SERIAL = {name == "d"}
                class Tests(unittest.TestCase):
                    def test_01(self):
                        if "{name}" == "d":
                            for before in "abc":
                                self.assertEqual(
                                    Path(before + ".sequence").read_text(), "12"
                                )
                            for after in "efg":
                                self.assertFalse(Path(after + ".sequence").exists())
                        elif "{name}" in "efg":
                            self.assertEqual(Path("d.sequence").read_text(), "12")
                        Path("{name}.sequence").write_text("1")
                        with Path("starts").open("a") as output:
                            output.write("{name}\\n")
                    def test_02(self):
                        self.assertEqual(Path("{name}.sequence").read_text(), "1")
                        Path("{name}.sequence").write_text("12")
                ''',
            )
        completed = self.run_suite()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(self.report.read_text())["summary"]["passed"], 14)
        paths = list(self.root.rglob(FILENAME))
        self.assertEqual(len(paths), 1)
        records, issues, _size = read_module_timing(
            paths[0].parent.resolve(), paths[0].parent.name
        )
        self.assertEqual(issues, [])
        names = {
            row["module_id"]: row["module"]
            for row in records
            if row["kind"] == "selected"
        }
        self.assertEqual(
            [
                names[row["module_id"]]
                for row in records
                if row["kind"] == "setup_begin"
            ],
            ["test_c", "test_a", "test_b", "test_d", "test_f", "test_g", "test_e"],
        )
        workers = self.root / "workers"
        before = set(workers.iterdir())
        for name in "abcdefg":
            (self.root / (name + ".sequence")).unlink()
        (self.root / "starts").unlink()
        serial = self.run_suite(workers=1)
        self.assertEqual(serial.returncode, 0, serial.stderr)
        self.assertEqual(
            (self.root / "starts").read_text().splitlines(), list("abcdefg")
        )
        original = (self.root / "test_c.py").read_text()
        self.report.unlink()
        for invalid in ("True", "101", "-1", '"10"'):
            with self.subTest(invalid=invalid):
                (self.root / "test_c.py").write_text(
                    original.replace(
                        "LITAI_TEST_PRIORITY = 10", "LITAI_TEST_PRIORITY = " + invalid
                    )
                )
                rejected = self.run_suite()
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn("LITAI_TEST_PRIORITY must be an integer", rejected.stderr)
                self.assertEqual(set(workers.iterdir()), before)
                self.assertFalse(self.report.exists())

    def _declare_checkpoint_authority(self) -> None:
        source = ProjectConfigurationStore(SOURCE.parent).read().definition
        (self.root / "driver.py").write_text("# Immutable fixture driver authority.\n")
        (self.root / "SKILL.md").write_text(
            "---\nname: checkpoint-fixture\n"
            "description: Exercise parallel checkpoints.\n---\n"
        )
        (self.root / "docs").mkdir()
        driver = replace(source.lifecycle_driver, implementation_paths=("driver.py",))
        definition = replace(
            source,
            project_id="checkpoint-fixture",
            agent_skill="SKILL.md",
            component_roots=(),
            flavor_roots=(),
            skill_roots=(),
            workflow_roots=(),
            routing_roots=(),
            mcp_roots=(),
            documentation_roots=("docs",),
            test_receipt=None,
            test_receipt_policy=None,
            default_flavor_selectors=(),
            component_flavor_selectors={},
            lifecycle_driver=driver,
        )
        identity = lifecycle_driver_implementation_identity(
            LoadedProject(self.root.resolve(), definition), driver
        )
        ProjectConfigurationStore(self.root).create(
            replace(
                definition,
                lifecycle_driver=replace(driver, implementation_identity=identity),
            )
        )

    def test_fail_fast_and_repair_out_of_order(self) -> None:
        base = self.root
        for declared in (True, False):
            with self.subTest(declared_authority=declared):
                self.root = base / ("declared" if declared else "unmanaged")
                self.root.mkdir()
                self.state, self.report = (
                    self.root / "state.json",
                    self.root / "report.json",
                )
                if declared:
                    self._declare_checkpoint_authority()
                self._repair_out_of_order(declared)

    def _repair_out_of_order(self, declared: bool) -> None:
        self.module(
            "a",
            """
            import time, unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_a_pass(self):
                    with Path("a.executions").open("a") as log:
                        log.write("a\\n")
                def test_repair(self):
                    # Fail only after the other worker has flushed its report.
                    # A fixed sleep races process startup on a busy host.
                    deadline = time.monotonic() + 20
                    while not Path("b.finished").exists():
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(.01)
                    self.assertTrue(Path("fixed").exists())
        """,
        )
        self.module(
            "b",
            """
            import atexit, unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_fast(self):
                    atexit.register(Path("b.finished").touch)
                    with Path("executions").open("a") as log:
                        log.write("b\\n")
                @unittest.skip("intentional repair skip")
                def test_skip(self): pass
        """,
        )
        first = self.run_suite()
        self.assertEqual(first.returncode, 1, first.stderr)
        (self.root / "fixed").touch()
        repair = self.run_suite()
        self.assertEqual(repair.returncode, 2 if declared else 0, repair.stderr)
        executions = 1 if declared else 2
        self.assertEqual((self.root / "a.executions").read_text(), "a\n" * executions)
        self.assertEqual(json.loads(self.report.read_text())["summary"]["skipped"], 1)
        self.assertEqual((self.root / "executions").read_text(), "b\n" * executions)
        fresh = self.run_suite()
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertEqual(
            (self.root / "executions").read_text(), "b\n" * (executions + 1)
        )

    def test_worker_crash_is_nonpassing_and_does_not_reuse_partial_module(self) -> None:
        self.module(
            "a",
            """
            import os, unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_a_pass(self):
                    with Path("executions").open("a") as log:
                        log.write("a\\n")
                def test_b_crash(self):
                    if Path("fail-before-crash").exists():
                        self.addCleanup(lambda: os._exit(7))
                        self.fail("body failed before cleanup crashed")
                    if not Path("fixed").exists():
                        os._exit(7)
        """,
        )
        result = self.run_suite()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("without a complete report", result.stderr)
        failed = json.loads(self.report.read_text())["outcomes"]
        self.assertEqual(len(failed), 1)
        self.assertTrue(failed[0]["test_key"].endswith("test_b_crash"))
        (self.root / "fixed").touch()
        result = self.run_suite()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "executions").read_text(), "a\na\n")
        (self.root / "fail-before-crash").touch()
        result = self.run_suite()
        self.assertEqual(result.returncode, 1, result.stderr)
        failed = json.loads(self.report.read_text())["outcomes"]
        self.assertEqual(len(failed), 1)
        self.assertTrue(failed[0]["test_key"].endswith("test_b_crash"))

    def test_deadline_is_nonpassing(self) -> None:
        self.module(
            "a",
            """
            import time, unittest
            class Tests(unittest.TestCase):
                def test_hang(self):
                    time.sleep(30)
        """,
        )
        result = self.run_suite(timeout=0.3)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("finite deadline", result.stderr)

    def test_subtest_failure_is_in_checkpoint_report(self) -> None:
        self.module(
            "a",
            """
            import unittest
            class Tests(unittest.TestCase):
                def test_subtest(self):
                    with self.subTest(value=1):
                        self.fail("subtest failure")
        """,
        )
        result = self.run_suite()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("(value=1)", result.stderr)
        self.assertEqual(json.loads(self.report.read_text())["summary"]["failed"], 1)

    def test_fail_fast_stops_owned_descendants_and_pending_dispatch(self) -> None:
        self.module(
            "a",
            """
            import time, unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_fail(self):
                    deadline = time.monotonic() + 20
                    while not Path("heartbeat").exists():
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(.01)
                    self.fail("stop all workers")
        """,
        )
        self.module(
            "b",
            """
            import subprocess, sys, time, unittest
            class Tests(unittest.TestCase):
                def test_child(self):
                    code = ("import time; from pathlib import Path; "
                            "p=Path('heartbeat'); "
                            "exec('while True: "
                            "p.write_text(str(time.time_ns())); time.sleep(.02)')")
                    subprocess.Popen([sys.executable, "-c", code])
                    time.sleep(30)
        """,
        )
        self.module(
            "c",
            """
            import unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_pending(self): Path("unexpected-dispatch").touch()
        """,
        )
        result = self.run_suite()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.root / "unexpected-dispatch").exists())
        heartbeat = self.root / "heartbeat"
        self.assertTrue(heartbeat.exists(), result.stderr)
        before = heartbeat.read_text()
        time.sleep(0.15)
        self.assertEqual(heartbeat.read_text(), before)

    def test_malformed_worker_events_fail_closed(self) -> None:
        self.module(
            "a",
            """
            import os, sys, unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_corrupt(self):
                    events = Path(sys.argv[1]).parent / "events.jsonl"
                    with events.open("a") as stream:
                        stream.write('{"schema":"wrong"}\\n')
                    os._exit(0)
        """,
        )
        result = self.run_suite()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("invalid worker event schema", result.stderr)
        self.assertEqual(json.loads(self.report.read_text())["summary"]["failed"], 1)

    def test_duplicate_instance_occurrences_are_counted_in_both_modes(self) -> None:
        self.module(
            "duplicates",
            """
            import unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_case(self):
                    with Path("executions").open("a") as stream:
                        stream.write("once\\n")
        """,
        )
        observed = []
        for workers in (1, 2):
            self.state.unlink(missing_ok=True)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"""
import io, unittest
from pathlib import Path
from literate_ai.test_checkpointing import run_unittest_suite
from test_duplicates import Tests
test = Tests('test_case')
raise SystemExit(run_unittest_suite(unittest.TestSuite([test, test]),
    state_path=Path('state.json'), stream=io.StringIO(),
    report_path=Path('report.json'), workers={workers}))
""",
                ],
                cwd=self.root,
                env=self.environment,
                text=True,
                capture_output=True,
                timeout=20,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(self.report.read_text())
            observed.append((report["summary"], report["outcomes"]))
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(observed[0][0]["passed"], 2)
        self.assertEqual(
            (self.root / "executions").read_text(), "once\nonce\nonce\nonce\n"
        )

    def test_known_failures_context_and_release_evidence_keep_their_semantics(
        self,
    ) -> None:
        base = self.root
        for declared in (True, False):
            with self.subTest(declared_authority=declared):
                self.root = base / ("declared" if declared else "unmanaged")
                self.root.mkdir()
                self.state, self.report = (
                    self.root / "state.json",
                    self.root / "report.json",
                )
                if declared:
                    self._declare_checkpoint_authority()
                self._known_failure_semantics(declared)

    def _known_failure_semantics(self, declared: bool) -> None:
        from literate_ai.contracts.identity import ContentIdentity, canonical_identity
        from literate_ai.contracts.known_test_failures import (
            KnownTestFailureAnnotation,
            KnownTestFailureCause,
            KnownTestFailurePolicy,
        )
        from literate_ai.known_failure_checkpoints import annotate_known_failure

        self.module(
            "a",
            """
            import unittest
            from pathlib import Path
            class Tests(unittest.TestCase):
                def test_case(self):
                    with Path("executions").open("a") as stream:
                        stream.write("once\\n")
                    self.assertTrue(Path("fixed").exists())
        """,
        )
        context = canonical_identity({"worker": "a"})
        arguments = ("--context-identity", context.uri)
        result = self.run_suite(extra=arguments)
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(self.report.read_text())
        annotate_known_failure(
            self.state,
            "python-unittest",
            KnownTestFailureAnnotation(
                pin_identity=ContentIdentity.from_dict(report["pin_identity"]),
                test_key=report["outcomes"][0]["test_key"],
                cause=KnownTestFailureCause.AUTHENTICATION_REQUIRED,
                context_identity=context,
                universal_authority=None,
                failure_identity=ContentIdentity.from_dict(
                    report["outcomes"][0]["failure_identity"]
                ),
                evidence_run_identity=canonical_identity({"evidence": "observed"}),
                evidence_node_id="n1",
                reason="Fixture requires an external acknowledgement",
                policy=KnownTestFailurePolicy.MANUAL_REVALIDATION,
            ),
        )
        result = self.run_suite(extra=arguments)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            json.loads(self.report.read_text())["summary"]["known_failed"],
            1 if declared else 0,
        )
        self.assertEqual(
            (self.root / "executions").read_text(), "once\n" * (1 if declared else 2)
        )
        result = self.run_suite(
            extra=("--context-identity", canonical_identity({"worker": "b"}).uri)
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(
            json.loads(self.report.read_text())["summary"]["known_failed"], 0
        )
        (self.root / "fixed").touch()
        result = self.run_suite(extra=(*arguments, "--release-evidence"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.report.read_text())["summary"]["passed"], 1)
        self.assertEqual(
            (self.root / "executions").read_text(), "once\n" * (3 if declared else 4)
        )

    def test_windows_gate_exposes_parallel_fail_fast_and_serial_debugging(self) -> None:
        from scripts import windows_release_gate as gate

        for workers, expected in (("auto", "auto"), ("3", "3"), ("1", "0")):
            with (
                self.subTest(workers=workers),
                patch.object(gate, "_windows", return_value=False),
                patch.object(gate, "_template_commands", return_value=[]),
                patch.object(
                    gate, "_environment_python", return_value=Path(sys.executable)
                ),
                patch.object(gate, "_run") as execute,
            ):
                self.assertEqual(
                    gate.main(["--only", "tests", "--test-workers", workers]), 0
                )
                argv = execute.call_args.args[0]
                self.assertEqual(argv[argv.index("-n") + 1], expected)
                self.assertIn("--dist=loadfile", argv)
                self.assertIn("--maxfail=1", argv)
                self.assertTrue(any(item.startswith("--junitxml=") for item in argv))
        with patch.object(gate, "_run") as execute, self.assertRaises(SystemExit):
            gate.main(["--only", "tests", "--test-workers", "0"])
        execute.assert_not_called()

    def test_busy_result_stream_does_not_starve_a_reported_failure(self) -> None:
        from literate_ai.parallel_unittests import ParallelSuite

        names = ["fair_a_" + uuid.uuid4().hex[:8], "fair_b_" + uuid.uuid4().hex[:8]]
        self.module(
            names[0],
            """
            import unittest
            from pathlib import Path
            class Cases(unittest.TestCase):
                @classmethod
                def tearDownClass(cls): Path("all-passes-reported").touch()
            def succeed(self): pass
            for index in range(100):
                setattr(Cases, f"test_{index:03d}", succeed)
        """,
        )
        self.module(
            names[1],
            """
            import time, unittest
            from pathlib import Path
            class Cases(unittest.TestCase):
                def test_failure(self):
                    deadline = time.monotonic() + 20
                    while not Path("recording-started").exists():
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(.001)
                    self.fail("fail fast")
                def tearDown(self):
                    # addFailure has flushed the worker event before teardown.
                    Path("failure-reported").touch()
        """,
        )
        tests = []
        for name in names:
            module_name = "test_" + name
            specification = importlib.util.spec_from_file_location(
                module_name, self.root / (module_name + ".py")
            )
            module = importlib.util.module_from_spec(specification)
            sys.modules[module_name] = module
            self.addCleanup(sys.modules.pop, module_name, None)
            specification.loader.exec_module(module)
            tests.extend(unittest.defaultTestLoader.loadTestsFromTestCase(module.Cases))
        passed = []
        observed_at_failure = []

        def record(index, event):
            if index == 0:
                (self.root / "recording-started").touch()
                deadline = time.monotonic() + 20
                while not all(
                    (self.root / name).exists()
                    for name in ("failure-reported", "all-passes-reported")
                ):
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.001)
            if event["status"] == "passed":
                passed.append(index)
            else:
                observed_at_failure.append(len(passed))

        suite = ParallelSuite(
            tests,
            root=self.root,
            directory=self.root / "logs",
            workers=2,
            stream=io.StringIO(),
            verbosity=0,
            outcome=record,
            invalidate=lambda _indices: None,
        )
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertEqual(len(result.failures), 1)
        self.assertIn("AssertionError: fail fast", result.failures[0][1])
        self.assertEqual(result.errors, [])
        self.assertEqual(len(observed_at_failure), 1)
        self.assertLessEqual(observed_at_failure[0], 8)
        self.assertEqual(passed, list(range(100)))

    def test_serial_parallel_outcome_parity(self) -> None:
        fixtures = {
            "success": """
                class Tests(unittest.TestCase):
                    def test_pass(self): pass
                    @unittest.skip("intentional")
                    def test_skip(self): pass
                    @unittest.expectedFailure
                    def test_xfail(self): self.fail("expected")
                    def test_subskip(self):
                        with self.subTest(part=1): self.skipTest("part")
            """,
            "setup_skip": """
                class Tests(unittest.TestCase):
                    @classmethod
                    def setUpClass(cls): raise unittest.SkipTest("class skip")
                    def test_a(self): pass
                    def test_b(self): pass
            """,
            "module_skip": """
                def setUpModule(): raise unittest.SkipTest("module skip")
                class Tests(unittest.TestCase):
                    def test_a(self): pass
                    def test_b(self): pass
            """,
            "setup_error": """
                class Tests(unittest.TestCase):
                    @classmethod
                    def setUpClass(cls): raise RuntimeError("setup")
                    def test_a(self): pass
                    def test_b(self): pass
            """,
            "class_teardown_skip": """
                class Tests(unittest.TestCase):
                    @classmethod
                    def tearDownClass(cls): raise unittest.SkipTest("teardown skip")
                    def test_a(self): pass
                    def test_b(self): pass
            """,
            "module_teardown_skip": """
                def tearDownModule(): raise unittest.SkipTest("module teardown skip")
                class Tests(unittest.TestCase):
                    def test_a(self): pass
                    def test_b(self): pass
            """,
            "failure_and_class_teardown_skip": """
                class Tests(unittest.TestCase):
                    @classmethod
                    def tearDownClass(cls): raise unittest.SkipTest("teardown skip")
                    def test_a(self): self.fail("body")
                    def test_b(self): pass
            """,
            "teardown_error": """
                class Tests(unittest.TestCase):
                    @classmethod
                    def tearDownClass(cls): raise RuntimeError("teardown")
                    def test_a(self): pass
                    def test_b(self): pass
            """,
            "subtest_failure": """
                class Tests(unittest.TestCase):
                    def test_a(self):
                        with self.subTest(part=1): self.fail("subtest")
            """,
            "failure_and_teardown_error": """
                class Tests(unittest.TestCase):
                    def tearDown(self): raise RuntimeError("teardown")
                    def test_a(self): self.fail("body")
            """,
            "failure_and_teardown_skip": """
                class Tests(unittest.TestCase):
                    def tearDown(self): self.skipTest("teardown skip")
                    def test_a(self): self.fail("body")
            """,
            "multiple_cleanup_errors": """
                class Tests(unittest.TestCase):
                    def test_a(self):
                        self.addCleanup(lambda: self.fail("cleanup one"))
                        self.addCleanup(lambda: self.fail("cleanup two"))
            """,
            "unexpected_success": """
                class Tests(unittest.TestCase):
                    @unittest.expectedFailure
                    def test_a(self): pass
            """,
        }
        for name, source in fixtures.items():
            with self.subTest(fixture=name):
                self.module("parity", "import unittest\n" + textwrap.dedent(source))
                observed = []
                for workers in (1, 2):
                    self.state.unlink(missing_ok=True)
                    result = self.run_suite(workers=workers)
                    report = json.loads(self.report.read_text())
                    observed.append(
                        (
                            result.returncode,
                            report["summary"],
                            report["outcomes"],
                            result.stderr.strip().splitlines()[-1],
                        )
                    )
                self.assertEqual(observed[0], observed[1])


if __name__ == "__main__":
    unittest.main()
