"""Observer controls using original process operations; no native SDK qualification."""

import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from literate_ai.adapters import process_liveness
from literate_ai.adapters.builders import javascript
from tests.support.sdk_probe_timing import SDKProbeTiming


class SDKProbeTimingTests(unittest.TestCase):
    def test_original_process_identity_calls_and_return_values_are_preserved(self):
        processes, returned = [], []

        def create(*args, **kwargs):
            child = subprocess.Popen(*args, **kwargs)
            processes.append(child)
            return child

        def original_probe(*args, **kwargs):
            result = javascript._run_bounded_process(
                (sys.executable, "-I", "-c", "print('controlled probe')"),
                cwd=None,
                environment={},
                timeout_seconds=15,
                stdout_limit_bytes=4096,
                stderr_limit_bytes=4096,
                error_prefix="builder.node_version",
                process_factory=create,
            )
            returned.append(result)
            return result

        observer = SDKProbeTiming()
        original_guard = process_liveness._LiveGuard.require_current
        original_run = javascript._run_bounded_process
        with patch.object(javascript, "_probe_node_command", original_probe):
            with observer.observe(), process_liveness.process_liveness(lambda: None):
                result = javascript._probe_node_command()
            self.assertIs(javascript._probe_node_command, original_probe)
        self.assertIs(result, returned[0])
        self.assertEqual(result.stdout, b"controlled probe\n")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(processes), 1)
        self.assertNotIn("wait", processes[0].__dict__)
        self.assertNotIn("poll", processes[0].__dict__)
        self.assertIs(javascript._run_bounded_process, original_run)
        self.assertIs(process_liveness._LiveGuard.require_current, original_guard)
        self.assertEqual(len(observer.snapshot()["probes"]), 1)
        row = observer.snapshot()["probes"][0]
        self.assertEqual(row["kind"], "node-version")
        self.assertEqual(row["measurement_scope"], "whole-node-probe")
        self.assertEqual(row["factory_calls"], 1)
        self.assertGreaterEqual(row["wait_calls"], 1)
        self.assertGreater(row["guard_calls"], 0)
        self.assertGreaterEqual(
            row["guard_inclusive_seconds"], row["guard_outer_seconds"]
        )
        self.assertGreaterEqual(
            row["wait_first_entry_seconds"], row["factory_first_return_seconds"]
        )
        self.assertFalse(observer.active)

    def test_direct_npm_probes_keep_original_children_returns_and_scopes(self):
        prefixes = {
            "builder.node_version": "node-version",
            "builder.npm_version": "npm-version",
            "builder.npm_dependency_resolution": "npm-dependencies",
            "builder.npm_literal_dependency_resolution": "npm-literal-dependencies",
        }
        original_run = javascript._run_bounded_process
        for prefix, kind in prefixes.items():
            with self.subTest(prefix=prefix):
                children = []

                def create(*args, collected=children, **kwargs):
                    child = subprocess.Popen(*args, **kwargs)
                    collected.append(child)
                    return child

                # Keep actual bounded-process logic, changing only its fixed
                # command to an inert local child. This is observer evidence.
                observer = SDKProbeTiming()
                with (
                    observer.observe(),
                    process_liveness.process_liveness(lambda: None),
                ):
                    result = javascript._run_bounded_process(
                        (sys.executable, "-I", "-c", "print('inert child')"),
                        cwd=None,
                        environment={},
                        timeout_seconds=15,
                        stdout_limit_bytes=4096,
                        stderr_limit_bytes=4096,
                        error_prefix=prefix,
                        process_factory=create,
                    )
                self.assertIs(javascript._run_bounded_process, original_run)
                self.assertEqual(result.stdout, b"inert child\n")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(len(children), 1)
                self.assertNotIn("wait", children[0].__dict__)
                self.assertNotIn("poll", children[0].__dict__)
                rows = observer.snapshot()["probes"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["kind"], kind)
                self.assertEqual(rows[0]["measurement_scope"], "bounded-subprocess")
                self.assertEqual(rows[0]["factory_calls"], 1)
                self.assertGreater(rows[0]["guard_calls"], 0)

    def test_direct_subprocess_failure_preserves_original_exception_and_arguments(self):
        failure, returned = RuntimeError("original subprocess failure"), object()
        calls = []

        def original_run(*args, process_factory=subprocess.Popen, **kwargs):
            calls.append((args, kwargs))
            if kwargs["error_prefix"] == "builder.npm_literal_dependency_resolution":
                raise failure
            return returned

        observer = SDKProbeTiming()
        environment = {"PRIVATE_TEST_VALUE": "never captured"}
        with patch.object(javascript, "_run_bounded_process", original_run):
            with observer.observe():
                with self.assertRaises(RuntimeError) as raised:
                    javascript._run_bounded_process(
                        ("private-command",),
                        environment=environment,
                        timeout_seconds=15,
                        stdout_limit_bytes=27,
                        error_prefix="builder.npm_literal_dependency_resolution",
                    )
                result = javascript._run_bounded_process(
                    ("private-command",),
                    error_prefix="builder.npm_dependency_resolution",
                )
            self.assertIs(javascript._run_bounded_process, original_run)
        self.assertIs(raised.exception, failure)
        self.assertIs(result, returned)
        self.assertEqual(len(calls), 2)
        self.assertIs(calls[0][1]["environment"], environment)
        self.assertEqual(calls[0][0], (("private-command",),))
        self.assertEqual(calls[0][1]["timeout_seconds"], 15)
        self.assertEqual(calls[0][1]["stdout_limit_bytes"], 27)
        report = observer.snapshot()
        self.assertEqual(report["probes"][0]["failure_type"], "RuntimeError")
        self.assertEqual(report["capture_errors"], 0)
        for private in ("private-command", "PRIVATE_TEST_VALUE", "never captured"):
            self.assertNotIn(private, json.dumps(report))
        self.assertIsNone(observer._row.get())
        self.assertIsNone(observer._probe_stack.get())

    def test_unknown_and_application_prefixes_are_not_new_probe_rows(self):
        calls, returned = [], object()

        def original_run(*args, process_factory=subprocess.Popen, **kwargs):
            calls.append(kwargs)
            return returned

        observer = SDKProbeTiming()
        with (
            patch.object(javascript, "_run_bounded_process", original_run),
            observer.observe(),
        ):
            for prefix in (
                "builder.javascript_check",
                "unknown",
                "builder.npm_version.extra",
                None,
                [],
            ):
                self.assertIs(
                    javascript._run_bounded_process(error_prefix=prefix), returned
                )
        self.assertEqual(len(calls), 5)
        self.assertEqual(observer.snapshot()["probes"], [])

    def test_direct_npm_overflow_keeps_recent_failure_and_fixed_labels(self):
        calls = []
        failure = RuntimeError("recent subprocess failure")

        def original_run(*args, process_factory=subprocess.Popen, **kwargs):
            calls.append(kwargs["error_prefix"])
            if len(calls) == 40:
                raise failure
            return failure

        observer = SDKProbeTiming()
        with (
            patch.object(javascript, "_run_bounded_process", original_run),
            observer.observe(),
        ):
            for _ in range(39):
                self.assertIs(
                    javascript._run_bounded_process(
                        error_prefix="builder.npm_dependency_resolution"
                    ),
                    failure,
                )
            with self.assertRaises(RuntimeError) as raised:
                javascript._run_bounded_process(
                    error_prefix="builder.npm_literal_dependency_resolution"
                )
        self.assertIs(raised.exception, failure)
        report = observer.snapshot()
        self.assertEqual(len(calls), 40)
        self.assertEqual(len(report["probes"]), 32)
        self.assertEqual(report["dropped_probes"], 8)
        self.assertEqual(report["probes"][-1]["kind"], "npm-literal-dependencies")
        self.assertEqual(report["probes"][-1]["failure_type"], "RuntimeError")
        self.assertLessEqual(len(json.dumps(report).encode()), 32768)

    def test_original_exception_and_restoration_survive_failed_probe(self):
        original = RuntimeError("controlled original failure")
        calls = []

        def failing_probe():
            calls.append(True)
            raise original

        observer = SDKProbeTiming()
        prior = javascript._run_bounded_process
        with patch.object(javascript, "_probe_node_command", failing_probe):
            with self.assertRaises(RuntimeError) as raised:
                with observer.observe():
                    javascript._probe_node_command()
            self.assertIs(javascript._probe_node_command, failing_probe)
        self.assertIs(raised.exception, original)
        self.assertIs(javascript._run_bounded_process, prior)
        self.assertEqual(calls, [True])
        self.assertEqual(
            observer.snapshot()["probes"][0]["failure_type"], "RuntimeError"
        )
        self.assertFalse(observer.active)

    def test_probe_overflow_keeps_recent_failure_and_bounded_serialization(self):
        calls = []
        original = RuntimeError("last original failure")

        def probe():
            calls.append(True)
            if len(calls) == 40:
                raise original
            return original

        observer = SDKProbeTiming()
        with patch.object(javascript, "_probe_node_command", probe), observer.observe():
            for _ in range(39):
                self.assertIs(javascript._probe_node_command(), original)
            with self.assertRaises(RuntimeError) as raised:
                javascript._probe_node_command()
        self.assertIs(raised.exception, original)
        report = observer.snapshot()
        self.assertEqual(len(calls), 40)
        self.assertLessEqual(len(report["probes"]), 32)
        self.assertGreaterEqual(report["dropped_probes"], 8)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["probes"][-1]["failure_type"], "RuntimeError")
        self.assertLessEqual(len(json.dumps(report).encode()), 32768)
        self.assertIs(report["qualified"], False)
        self.assertIs(report["instrumentation_active"], True)

    def test_restore_failure_after_restoring_cannot_mask_original_probe_failure(self):
        from contextlib import ExitStack

        from tests.support import sdk_probe_timing as timing

        original = RuntimeError("original probe failure")
        children = []

        class FailingRestore(ExitStack):
            def close(self):
                super().close()
                raise RuntimeError("controlled post-restoration failure")

        def create(*args, **kwargs):
            child = subprocess.Popen(*args, **kwargs)
            children.append(child)
            return child

        def probe():
            javascript._run_bounded_process(
                (sys.executable, "-I", "-c", "pass"),
                cwd=None,
                environment={},
                timeout_seconds=15,
                stdout_limit_bytes=4096,
                stderr_limit_bytes=4096,
                error_prefix="fixture.probe",
                process_factory=create,
            )
            raise original

        observer = SDKProbeTiming()
        prior = javascript._run_bounded_process
        guard = process_liveness._LiveGuard.require_current
        with (
            patch.object(timing, "ExitStack", FailingRestore),
            patch.object(javascript, "_probe_node_command", probe),
        ):
            with self.assertRaises(RuntimeError) as raised:
                with observer.observe():
                    javascript._probe_node_command()
            self.assertIs(javascript._probe_node_command, probe)
        self.assertIs(raised.exception, original)
        self.assertIs(javascript._run_bounded_process, prior)
        self.assertIs(process_liveness._LiveGuard.require_current, guard)
        self.assertIsNone(observer._row.get())
        self.assertIsNone(observer._probe_stack.get())
        self.assertNotIn("wait", children[0].__dict__)
        self.assertNotIn("poll", children[0].__dict__)
        self.assertTrue(observer.snapshot()["capture_incomplete"])

    def test_bookkeeping_failure_does_not_replace_original_return(self):
        returned = object()
        observer = SDKProbeTiming()
        with (
            patch.object(
                javascript, "_probe_node_command", return_value=returned
            ) as original,
            patch.object(
                observer,
                "_record",
                side_effect=ValueError("controlled capture failure"),
            ),
        ):
            with observer.observe():
                self.assertIs(javascript._probe_node_command(), returned)
        original.assert_called_once_with()
        self.assertTrue(observer.snapshot()["capture_incomplete"])

    def test_snapshot_failure_is_unknown_and_single_use_is_explicit(self):
        observer = SDKProbeTiming()
        with observer.observe():
            pass
        with patch("tests.support.sdk_probe_timing.json", None):
            self.assertEqual(observer.snapshot()["state"], "unknown")
        with self.assertRaisesRegex(ValueError, "single-use"):
            with observer.observe():
                self.fail("observer reopened")
