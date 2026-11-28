"""Real Linux child/launcher counters and observation-only descriptor lifetime.

These exercise the production bounded launcher, not a receiver, reservation,
subtree attribution, remote transport or installed/native cross-platform proof.
"""

import dataclasses
import hashlib
import os
import pickle
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import worker_telemetry_processes as native
from literate_ai.adapters.builders import run_bounded_process

_CHILD = r"""
import ctypes, os, sys, time
ctypes.CDLL(None).prctl(15, b"secret) \nname", 0, 0, 0)
payload = bytearray(4 * 1024 * 1024)
for offset in range(0, len(payload), 4096):
    payload[offset] = 17
with open(sys.argv[2], "wb") as output:
    output.write(payload)
    output.flush()
    os.fsync(output.fileno())
until = time.process_time() + 0.06
while time.process_time() < until:
    sum(range(1000))
print("ready", flush=True)
os.read(int(sys.argv[1]), 1)
print("complete", flush=True)
"""


class _ReadySink:
    def __init__(self):
        self.ready = threading.Event()
        self.data = bytearray()

    def writable(self):
        return True

    def write(self, value):
        self.data.extend(value)
        if b"ready\n" in self.data:
            self.ready.set()
        return len(value)


class _NativeJob:
    def __init__(self, root):
        self.root = root
        self.payload = root / "owned-payload.bin"
        self.sink = _ReadySink()
        self.result = {}
        owners = queue.Queue(maxsize=1)
        read_end, self.write_end = os.pipe()

        def spawn(*args, **kwargs):
            try:
                return subprocess.Popen(*args, **kwargs, pass_fds=(read_end,))
            finally:
                os.close(read_end)

        def execute():
            try:
                with native.observe_original_process_launches() as owner:
                    owners.put(owner)
                    self.result["value"] = run_bounded_process(
                        [
                            sys.executable,
                            "-c",
                            _CHILD,
                            str(read_end),
                            str(self.payload),
                        ],
                        cwd=root,
                        environment=dict(os.environ),
                        timeout_seconds=15,
                        stdout_limit_bytes=4096,
                        stderr_limit_bytes=4096,
                        error_prefix="native_observation_fixture",
                        process_factory=spawn,
                        stdout_sink=self.sink,
                        trace=False,
                    )
            except Exception as error:
                self.result["error"] = error
                self.sink.ready.set()

        self.thread = threading.Thread(target=execute, daemon=True)
        self.thread.start()
        self.owner = owners.get(timeout=10)

    def ready(self):
        if not self.sink.ready.wait(timeout=10):
            raise AssertionError("native fixture did not reach ready")
        if "error" in self.result:
            raise AssertionError("native fixture failed") from self.result["error"]

    def finish(self):
        if self.write_end is not None:
            with suppress(OSError):
                os.write(self.write_end, b"G")
            os.close(self.write_end)
            self.write_end = None
        self.thread.join(timeout=20)
        if self.thread.is_alive():
            raise AssertionError("original native job did not finish")


@unittest.skipUnless(
    sys.platform.startswith("linux") and hasattr(os, "pidfd_open"),
    "requires actual Linux pidfd process ownership",
)
class WorkerTelemetryProcessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native-telemetry-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def job(self):
        job = _NativeJob(self.root)
        self.addCleanup(job.finish)
        job.ready()
        return job

    def test_original_launcher_exposes_real_single_process_cpu_memory_and_io_counters(
        self,
    ):
        job = self.job()
        self.assertFalse(job.owner.registration_failed)
        probes = job.owner.active()
        self.assertEqual(len(probes), 1)
        first = probes[0].sample()
        second = probes[0].sample()
        self.assertEqual(first.launch_identity, probes[0].identity)
        self.assertEqual(second.process_start_identity, first.process_start_identity)
        self.assertGreater(first.user_cpu_time_ns + first.system_cpu_time_ns, 0)
        self.assertGreaterEqual(second.user_cpu_time_ns, first.user_cpu_time_ns)
        self.assertGreater(first.rss_estimate_bytes, 4 * 1024 * 1024)
        self.assertGreaterEqual(first.storage_write_accounted_bytes, 4 * 1024 * 1024)
        self.assertGreater(second.observed_monotonic_ns, first.observed_monotonic_ns)
        self.assertEqual(job.payload.stat().st_size, 4 * 1024 * 1024)
        self.assertNotIn("secret", repr(dataclasses.asdict(first)))
        self.assertFalse(hasattr(first, "pid"))
        self.assertFalse(hasattr(first, "command"))
        self.assertFalse(hasattr(first, "network_in_bytes"))

    def test_observer_close_preserves_live_job_output_bytes_and_normal_completion(self):
        job = self.job()
        probe = job.owner.active()[0]
        before = hashlib.sha256(job.payload.read_bytes()).hexdigest()
        job.owner.close()
        self.assertTrue(job.thread.is_alive())
        with self.assertRaisesRegex(
            native.NativeProcessObservationError, "unavailable"
        ):
            probe.sample()
        self.assertEqual(hashlib.sha256(job.payload.read_bytes()).hexdigest(), before)
        job.finish()
        self.assertEqual(job.result["value"].returncode, 0)
        self.assertEqual(bytes(job.sink.data), b"ready\ncomplete\n")
        self.assertEqual(hashlib.sha256(job.payload.read_bytes()).hexdigest(), before)

    def test_counter_file_reads_never_run_in_the_original_launch_thread(self):
        original = native._read_record
        threads = []

        def observed(*args):
            threads.append(threading.get_ident())
            return original(*args)

        with mock.patch.object(native, "_read_record", side_effect=observed):
            job = self.job()
            self.assertEqual(threads, [])
            job.owner.active()[0].sample()
            self.assertEqual(threads, [threading.get_ident()] * 3)

    def test_slow_collector_cannot_block_original_job_cleanup_or_keep_native_fds(self):
        job = self.job()
        probe = job.owner.active()[0]
        entered, resume = threading.Event(), threading.Event()
        original = native._read_record
        result = {}

        def stalled(*args):
            entered.set()
            if not resume.wait(timeout=10):
                raise RuntimeError("collector fixture deadline")
            return original(*args)

        def collect():
            try:
                result["sample"] = probe.sample()
            except native.NativeProcessObservationError as error:
                result["error"] = str(error)

        with mock.patch.object(native, "_read_record", side_effect=stalled):
            collector = threading.Thread(target=collect, daemon=True)
            collector.start()
            try:
                self.assertTrue(entered.wait(timeout=10))
                job.finish()
                self.assertEqual(job.result["value"].returncode, 0)
                self.assertTrue(probe.closed)
                self.assertTrue(collector.is_alive())
            finally:
                resume.set()
                collector.join(timeout=10)
        self.assertFalse(collector.is_alive())
        self.assertNotIn("sample", result)
        self.assertEqual(result["error"], "worker.telemetry_process_unavailable")
        self.assertIsNone(probe._directory)
        self.assertIsNone(probe._pidfd)

    def test_native_probe_uses_only_bounded_safe_files_under_its_original_descriptor(
        self,
    ):
        job = self.job()
        probe = job.owner.active()[0]
        original = os.open
        with mock.patch.object(native.os, "open", wraps=original) as opened:
            probe.sample()
        self.assertEqual(
            [call.args[0] for call in opened.call_args_list], ["stat", "io", "stat"]
        )
        for call in opened.call_args_list:
            self.assertEqual(call.kwargs["dir_fd"], probe._directory)
            self.assertTrue(call.args[1] & os.O_NOFOLLOW)

    def test_observer_close_during_native_registration_cannot_leave_a_live_probe(self):
        original = native._capture_original_launch
        captured = []

        def closing(*args):
            probe = original(*args)
            captured.append(probe)
            native._CURRENT.get().close()
            return probe

        with mock.patch.object(native, "_capture_original_launch", side_effect=closing):
            job = self.job()
        self.assertTrue(job.thread.is_alive())
        self.assertTrue(job.owner.registration_failed)
        self.assertEqual(len(captured), 1)
        self.assertTrue(captured[0].closed)
        self.assertIsNone(captured[0]._directory)
        self.assertIsNone(captured[0]._pidfd)
        job.finish()
        self.assertEqual(job.result["value"].returncode, 0)

    def test_saved_pid_and_identity_records_cannot_register_an_original_process(self):
        with native.observe_original_process_launches() as owner:
            for value in ({"pid": os.getpid()}, SimpleNamespace(pid=os.getpid()), 1):
                self.assertIsNone(native.register_original_process_launch(value))
            self.assertTrue(owner.registration_failed)
            self.assertEqual(owner.active(), ())
            with self.assertRaises(TypeError):
                pickle.dumps(owner)
        job = self.job()
        with self.assertRaises(TypeError):
            pickle.dumps(job.owner.active()[0])

    def test_observation_registration_failure_is_safe_and_does_not_fail_the_job(self):
        with mock.patch.object(
            native,
            "_capture_original_launch",
            side_effect=OSError("private-secret-path"),
        ):
            job = self.job()
            self.assertTrue(job.owner.registration_failed)
            self.assertEqual(job.owner.active(), ())
            job.finish()
        self.assertEqual(job.result["value"].returncode, 0)
        self.assertEqual(job.result["value"].stderr, b"")
        self.assertEqual(bytes(job.sink.data), b"ready\ncomplete\n")

    def test_live_owner_does_not_transfer_to_a_new_registry_or_survive_retirement(self):
        job = self.job()
        probe = job.owner.active()[0]
        fresh = native.OriginalProcessObservations()
        self.addCleanup(fresh.close)
        self.assertNotEqual(fresh.epoch, job.owner.epoch)
        self.assertEqual(fresh.active(), ())
        job.finish()
        with self.assertRaisesRegex(
            native.NativeProcessObservationError, "unavailable"
        ):
            probe.sample()
        self.assertIsNone(probe._directory)
        self.assertIsNone(probe._pidfd)

    def test_native_metadata_limit_refuses_without_leaking_private_content(self):
        job = self.job()
        probe = job.owner.active()[0]
        with mock.patch.object(native.os, "read", return_value=b"private" * 700):
            with self.assertRaises(native.NativeProcessObservationError) as error:
                probe.sample()
        self.assertEqual(str(error.exception), "worker.telemetry_process_unavailable")
        self.assertTrue(job.thread.is_alive())

    def test_registry_capacity_cannot_be_unbounded_or_disable_the_limit(self):
        for value in (0, 65, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                native.OriginalProcessObservations(maximum_processes=value)
