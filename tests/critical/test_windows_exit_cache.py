"""A cached CPython exit code must not replace the caller's kernel wait.

The model follows CPython v3.12.10 Lib/subprocess.py terminate/_wait: the
PermissionError branch can cache GetExitCodeProcess before the object signals.
Native Windows confirmation uses the actual owned process handle, without the
job-observation hooks. These are separate kinds of evidence.
"""

import ctypes
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from literate_ai.adapters import _processes
from literate_ai.project_template.scripts import _bootstrap_processes


class _WindowsExitModel:
    pid = 1729

    def __init__(self):
        self.returncode = None
        self.terminating = False
        self.kernel_signaled = False
        self.kernel_waits = 0
        self.kill_calls = 0

    def terminate_job(self):
        self.terminating = True
        return True

    def poll(self):
        if self.returncode is None and self.kernel_signaled:
            self.returncode = 1
        return self.returncode

    def kill(self):
        if self.returncode is not None:
            return
        self.kill_calls += 1
        try:
            if self.terminating:
                raise PermissionError("already terminating")
            self.terminating = True
        except PermissionError:
            # Modeled GetExitCodeProcess: status visible, object not signaled.
            self.returncode = 1

    def wait(self, timeout):
        if self.returncode is None:
            self.kernel_waits += 1
            if not self.terminating:
                raise subprocess.TimeoutExpired("modeled root", timeout)
            self.kernel_signaled = True
            self.returncode = 1
        return self.returncode


class WindowsExitCacheTests(unittest.TestCase):
    def test_confirmed_job_preserves_the_callers_actual_kernel_wait(self):
        for module in (_processes, _bootstrap_processes):
            with self.subTest(module=module.__name__):
                process = _WindowsExitModel()
                job = mock.Mock()
                job.terminate.side_effect = process.terminate_job
                owner = module.ProcessTreeOwnership({}, job)
                with (
                    mock.patch.object(
                        module, "windows_taskkill_executable"
                    ) as taskkill,
                    mock.patch.object(module.subprocess, "Popen") as spawn,
                ):
                    for _ in range(2):
                        module.terminate_process_tree(
                            process, platform_name="nt", ownership=owner
                        )
                    self.assertEqual(process.wait(timeout=5), 1)
                self.assertTrue(process.kernel_signaled)
                self.assertEqual(process.kernel_waits, 1)
                self.assertEqual(process.kill_calls, 0)
                taskkill.assert_not_called()
                spawn.assert_not_called()
                job.terminate.assert_called_once_with()
                job.close.assert_called_once_with()

    def test_exit_cache_without_kernel_completion_is_a_model_counterexample(self):
        process = _WindowsExitModel()
        process.terminate_job()
        process.kill()
        self.assertEqual(process.poll(), 1)
        self.assertEqual(process.wait(timeout=5), 1)
        self.assertFalse(process.kernel_signaled)
        self.assertEqual(process.kernel_waits, 0)

    def test_unconfirmed_job_preserves_root_fallback_and_caller_wait(self):
        for module in (_processes, _bootstrap_processes):
            for role in ("missing", "failed"):
                with self.subTest(module=module.__name__, role=role):
                    process = _WindowsExitModel()
                    job = None if role == "missing" else mock.Mock()
                    if job is not None:
                        job.terminate.return_value = False
                    owner = module.ProcessTreeOwnership({}, job)
                    module.terminate_process_tree(
                        process, platform_name="nt", ownership=owner, environment={}
                    )
                    self.assertEqual(process.wait(timeout=5), 1)
                    self.assertTrue(process.kernel_signaled)
                    self.assertEqual(process.kill_calls, 1)
                    self.assertEqual(process.kernel_waits, 1)


@unittest.skipUnless(os.name == "nt", "requires native Windows process signal")
class NativeWindowsExitCacheTests(unittest.TestCase):
    def test_caller_wait_returns_only_after_the_owned_kernel_object_signals(self):
        kernel = ctypes.WinDLL("kernel32.dll", winmode=0x800, use_last_error=True)
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel.WaitForSingleObject.restype = ctypes.c_uint32
        with tempfile.TemporaryDirectory() as temporary:
            owner = _processes.create_process_tree_ownership()
            self.assertIsNotNone(owner.job, "native Job setup unavailable")
            process = None
            try:
                process = subprocess.Popen(
                    [sys.executable, "-c", "import time; time.sleep(60)"],
                    cwd=temporary,
                    **owner.popen_options,
                )
                owner.bind(process.pid)
                self.assertIsNotNone(owner.job, "native Job assignment failed")
                _processes.terminate_process_tree(process, ownership=owner)
                process.wait(timeout=5)
                self.assertEqual(kernel.WaitForSingleObject(int(process._handle), 0), 0)
            finally:
                owner.release()
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                    # Independent fixture cleanup cannot trust the cached exit
                    # whose distinction this control is intended to measure.
                    self.assertEqual(
                        kernel.WaitForSingleObject(int(process._handle), 5000), 0
                    )
