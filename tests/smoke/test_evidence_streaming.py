"""Live evidence output, complete-stream redaction and finalization ownership."""

import hashlib
import io
import os
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai import evidence_ledger as ledger


class EvidenceStreamingTests(unittest.TestCase):
    def _configured_runner(self, subprocess_module=None, **overrides):
        if subprocess_module is not None:
            overrides["subprocess"] = subprocess_module

        def run(*args, **kwargs):
            with patch.multiple(ledger, **overrides):
                return ledger._run_streaming(*args, **kwargs)

        return run

    def test_flushed_prefix_is_live_and_persistence_waits_for_redaction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, release, output = (
                root / value for value in ("ready", "release", "stdout")
            )
            secret = "fixture-only-secret-token"
            prefix = secret[:12]
            observed = threading.Event()

            class Console(io.StringIO):
                def write(self, value):
                    count = super().write(value)
                    if prefix in self.getvalue():
                        observed.set()
                    return count

            console = Console()
            outcome, errors = [], []
            stats = {}
            child = (
                "import os,sys,time; from pathlib import Path; "
                "token=os.environ['TEE_PROBE_TOKEN']; "
                "sys.stdout.write(token[:12]); sys.stdout.flush(); "
                "Path(sys.argv[1]).touch(); deadline=time.monotonic()+6\n"
                "while not Path(sys.argv[2]).exists() "
                "and time.monotonic()<deadline: time.sleep(.01)\n"
                "sys.stdout.write(token[12:]+'\\n'); sys.stdout.flush()"
            )

            def controller():
                try:
                    outcome.append(
                        ledger._run_streaming(
                            [sys.executable, "-c", child, str(ready), str(release)],
                            cwd=root,
                            environment={**os.environ, "TEE_PROBE_TOKEN": secret},
                            timeout=8,
                            stdout_file=output,
                            stderr_file=None,
                            pointer_stats=stats,
                            tee=True,
                        )
                    )
                except BaseException as error:
                    errors.append(error)

            with patch.object(ledger.sys, "stdout", console):
                thread = threading.Thread(
                    target=controller, name="Aviation tee fixture"
                )
                thread.start()
                try:
                    deadline = time.monotonic() + 3
                    while not ready.exists() and time.monotonic() < deadline:
                        threading.Event().wait(0.01)
                    self.assertTrue(
                        ready.exists(), "child must flush before evaluating its tee"
                    )
                    before_release = observed.wait(0.5)
                    if before_release:
                        self.assertEqual(output.read_bytes(), b"")
                finally:
                    release.touch()
                    thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            self.assertFalse(errors)
            self.assertEqual(len(outcome), 1)
            self.assertEqual(outcome[0].returncode, 0)
            persisted = output.read_bytes()
            self.assertEqual(stats["stdout"][1], len(persisted))
            self.assertEqual(
                stats["stdout"][0].hexdigest(), hashlib.sha256(persisted).hexdigest()
            )
            leaked = secret in persisted.decode()
            self.assertTrue(before_release)
            self.assertFalse(leaked)

    def test_utf8_crlf_and_pointer_bytes_in_both_tee_modes(self):
        fixed = ledger._run_streaming
        for tee in (False, True):
            with self.subTest(tee=tee), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                stats = {}
                child = (
                    "import os,time; os.write(1,b'prefix \\xc3'); time.sleep(.03); "
                    "os.write(1,b'\\xa9\\r\\n'); os.write(2,b'error\\r\\n')"
                )
                with (
                    patch.object(ledger.sys, "stdout", io.StringIO()),
                    patch.object(ledger.sys, "stderr", io.StringIO()),
                ):
                    result = fixed(
                        [sys.executable, "-c", child],
                        cwd=root,
                        environment=dict(os.environ),
                        timeout=5,
                        stdout_file=root / "stdout",
                        stderr_file=root / "stderr",
                        pointer_stats=stats,
                        tee=tee,
                    )
                self.assertEqual(result.returncode, 0)
                expected = "prefix é\r\n" if tee else "prefix é\n"
                self.assertEqual(result.stdout, expected)
                self.assertEqual(result.stderr, "error\r\n" if tee else "error\n")
                for label in ("stdout", "stderr"):
                    data = (root / label).read_bytes()
                    self.assertEqual(data, getattr(result, label).encode())
                    self.assertEqual(stats[label][1], len(data))
                    self.assertEqual(
                        stats[label][0].hexdigest(), hashlib.sha256(data).hexdigest()
                    )

    def test_original_cancellation_reaps_child_and_redacts_retained_output(self):
        self._cancelled_case()

    def test_primary_cancellation_survives_persistence_baseexception(self):
        def failed_redaction(*_args):
            raise SystemExit("secondary persistence failure")

        self._cancelled_case(redact_secrets=failed_redaction)

    def _cancelled_case(self, **overrides):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready = root / "ready"
            primary = KeyboardInterrupt("original controlled cancellation")
            children = []

            def factory(*args, **kwargs):
                process = subprocess.Popen(*args, **kwargs)
                children.append(process)
                wait = process.wait
                pending = True

                def cancelled_wait(*args, **kwargs):
                    nonlocal pending
                    if pending:
                        pending = False
                        deadline = time.monotonic() + 2
                        while not ready.exists() and time.monotonic() < deadline:
                            threading.Event().wait(0.01)
                        raise primary
                    return wait(*args, **kwargs)

                process.wait = cancelled_wait
                return process

            module = types.SimpleNamespace(
                Popen=factory,
                TimeoutExpired=subprocess.TimeoutExpired,
                CompletedProcess=subprocess.CompletedProcess,
                DEVNULL=subprocess.DEVNULL,
                PIPE=subprocess.PIPE,
            )
            releases = []
            original_owner = ledger.create_process_tree_ownership

            def create_owner():
                owner = original_owner()
                release = owner.release

                def tracked_release():
                    release()
                    releases.append(True)

                owner.release = tracked_release
                return owner

            fixed = self._configured_runner(
                subprocess_module=module,
                create_process_tree_ownership=create_owner,
                **overrides,
            )
            child = (
                "import os,time; from pathlib import Path; "
                "print(os.environ['TEE_PROBE_TOKEN'],flush=True); Path("
                + repr(str(ready))
                + ").touch(); time.sleep(8)"
            )
            stats = {}
            with (
                patch.object(ledger.sys, "stdout", io.StringIO()),
                patch.object(ledger.sys, "stderr", io.StringIO()),
            ):
                with self.assertRaises(KeyboardInterrupt) as failure:
                    fixed(
                        [sys.executable, "-c", child],
                        cwd=root,
                        environment={
                            **os.environ,
                            "TEE_PROBE_TOKEN": "fixture-only-secret-token",
                        },
                        timeout=5,
                        stdout_file=root / "stdout",
                        stderr_file=None,
                        pointer_stats=stats,
                        tee=True,
                    )
            self.assertIs(failure.exception, primary)
            self.assertTrue(ready.exists())
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())
            self.assertEqual(releases, [True])
            self.assertTrue(children[0].stdout.closed)
            self.assertTrue(children[0].stderr.closed)
            data = (root / "stdout").read_bytes()
            if overrides:
                self.assertEqual(data, b"")
                self.assertNotIn("stdout", stats)
                return
            self.assertIn(b"<redacted>", data)
            self.assertNotIn(b"fixture-only-secret-token", data)
            self.assertEqual(stats["stdout"][1], len(data))
            self.assertEqual(
                stats["stdout"][0].hexdigest(), hashlib.sha256(data).hexdigest()
            )

    def test_finalization_cancellation_and_close_failure_still_release_owner(self):
        for fail_redaction in (True, False):
            with (
                self.subTest(fail_redaction=fail_redaction),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                primary = KeyboardInterrupt("finalization cancellation")
                close_error = SystemExit("secondary close failure")
                opened, released = [], []
                original_open = Path.open

                class Output:
                    def __init__(self, stream):
                        self.stream = stream

                    def write(self, data):
                        return self.stream.write(data)

                    def close(self, close_error=close_error):
                        self.stream.close()
                        raise close_error

                def open_output(
                    path, *args, original_open=original_open, opened=opened, **kwargs
                ):
                    stream = original_open(path, *args, **kwargs)
                    opened.append(stream)
                    return Output(stream)

                original_owner = ledger.create_process_tree_ownership

                def create_owner(*, original_owner=original_owner, released=released):
                    owner = original_owner()
                    release = owner.release

                    def tracked_release():
                        release()
                        released.append(True)

                    owner.release = tracked_release
                    return owner

                original_redact = ledger.redact_secrets

                def redaction(
                    text,
                    environment,
                    *,
                    fail_redaction=fail_redaction,
                    primary=primary,
                    original_redact=original_redact,
                ):
                    if fail_redaction:
                        raise primary
                    return original_redact(text, environment)

                fixed = self._configured_runner(
                    create_process_tree_ownership=create_owner, redact_secrets=redaction
                )
                with (
                    patch.object(Path, "open", open_output),
                    patch.object(ledger.sys, "stdout", io.StringIO()),
                ):
                    with self.assertRaises(BaseException) as failure:
                        fixed(
                            [sys.executable, "-c", "print('fixture')"],
                            cwd=root,
                            environment=dict(os.environ),
                            timeout=5,
                            stdout_file=root / "stdout",
                            stderr_file=None,
                            tee=True,
                        )
                self.assertIs(
                    failure.exception, primary if fail_redaction else close_error
                )
                self.assertTrue(opened and all(stream.closed for stream in opened))
                self.assertEqual(released, [True])

    def test_outer_except_does_not_suppress_new_finalization_cancellation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            primary = KeyboardInterrupt("new finalization cancellation")
            released = []

            def redaction(*_args):
                raise primary

            original_owner = ledger.create_process_tree_ownership

            def create_owner():
                owner = original_owner()
                release = owner.release

                def tracked_release():
                    release()
                    released.append(True)

                owner.release = tracked_release
                return owner

            fixed = self._configured_runner(
                create_process_tree_ownership=create_owner, redact_secrets=redaction
            )
            try:
                raise RuntimeError("unrelated already-handled caller exception")
            except RuntimeError:
                with patch.object(ledger.sys, "stdout", io.StringIO()):
                    with self.assertRaises(KeyboardInterrupt) as failure:
                        fixed(
                            [sys.executable, "-c", "print('fixture')"],
                            cwd=root,
                            environment=dict(os.environ),
                            timeout=5,
                            stdout_file=root / "stdout",
                            stderr_file=None,
                            tee=True,
                        )
                self.assertIs(failure.exception, primary)
            self.assertEqual(released, [True])
