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
                error_prefix="fixture.probe",
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
        row = observer.snapshot()["probes"][0]
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
