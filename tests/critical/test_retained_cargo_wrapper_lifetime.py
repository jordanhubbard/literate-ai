"""Actual source wrapper lifetime; modeled Cargo/provider declarations only."""

import copy
import hashlib
import os
import select
import shutil
import signal
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from literate_ai.adapters import retained_cargo_scratch_v2 as scratch_owner
from literate_ai.adapters.retained_cargo_wrapper_v2 import (
    retained_cargo_wrapper_context_v2,
)
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


@unittest.skipUnless(
    os.name != "nt" and shutil.which("git") and shutil.which("make"),
    "requires actual POSIX adoption and native Git/Make",
)
class RetainedCargoWrapperLifetimeTests(unittest.TestCase):
    def test_ended_original_wrapper_cannot_be_rearmed(self):
        base = Path(
            self.enterContext(tempfile.TemporaryDirectory(prefix="cw-"))
        ).resolve()
        reviewed = self.enterContext(scratch_review_fixture(base))
        with retained_cargo_wrapper_context_v2(reviewed) as context:
            context.require_unchanged()
            lifetime = context._lifetime
        lifetime.active = True
        try:
            with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                context.require_unchanged()
        finally:
            lifetime.active = False

    def test_wrapper_context_lifetime_cannot_be_rearmed_copied_or_crossed(self):
        base = Path(
            self.enterContext(tempfile.TemporaryDirectory(prefix="cx-"))
        ).resolve()
        self.reviewed = self.enterContext(scratch_review_fixture(base))

        def snapshot():
            result = {}
            for path in self.reviewed.project.root.rglob("*"):
                node = path.lstat()
                name = path.relative_to(self.reviewed.project.root).as_posix()
                if path.is_symlink():
                    content = os.fsencode(os.readlink(path))
                elif path.is_file():
                    content = path.read_bytes()
                else:
                    content = b""
                result[name] = (node.st_mode, hashlib.sha256(content).hexdigest())
            return result

        with retained_cargo_wrapper_context_v2(self.reviewed) as context:
            original_identity = context.identity
            active_before = snapshot()
            for copy_method in (copy.copy, copy.deepcopy):
                with self.subTest(copy_method=copy_method.__name__):
                    with self.assertRaisesRegex(TypeError, "not-copyable"):
                        copy_method(context)
            # A copied set of actual fields is data, not original issuance.
            for original in (context, context._core):
                forged = object.__new__(type(original))
                forged.__dict__.update(original.__dict__)
                with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                    forged.require_unchanged()

            thread_outcome = []

            def foreign_thread():
                try:
                    context.require_unchanged()
                except ValueError as exc:
                    thread_outcome.append(str(exc))
                else:
                    thread_outcome.append("accepted foreign thread")

            thread = threading.Thread(target=foreign_thread, daemon=True)
            thread.start()
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive(), "foreign-thread check did not finish")
            self.assertEqual(
                thread_outcome, ["retained.cargo.v2-wrapper-operation-ended"]
            )
            self.assertEqual(context.identity, original_identity)

            if hasattr(os, "fork"):
                read_fd, write_fd = os.pipe()
                child = os.fork()
                if child == 0:
                    os.close(read_fd)
                    try:
                        context.require_unchanged()
                    except ValueError as exc:
                        outcome = str(exc).encode("utf-8")
                    except BaseException as exc:
                        outcome = (type(exc).__name__ + ": " + str(exc)).encode("utf-8")
                    else:
                        outcome = b"accepted foreign process"
                    try:
                        os.write(write_fd, outcome[:1024])
                    finally:
                        os._exit(0)
                os.close(write_fd)
                reaped = False
                deadline = time.monotonic() + 10
                try:
                    ready = select.select([read_fd], [], [], 10)[0]
                    self.assertTrue(ready, "forked source check did not report")
                    outcome = os.read(read_fd, 1024)
                    while time.monotonic() < deadline:
                        observed, status = os.waitpid(child, os.WNOHANG)
                        if observed == child:
                            reaped = True
                            break
                        time.sleep(0.01)
                    self.assertTrue(reaped, "forked source check did not exit")
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                    self.assertEqual(
                        outcome, b"retained.cargo.v2-wrapper-operation-ended"
                    )
                finally:
                    os.close(read_fd)
                    if not reaped:
                        observed, _ = os.waitpid(child, os.WNOHANG)
                        if observed == 0:
                            # This is our actual unreaped child: its PID cannot
                            # be reused before waitpid, not a saved PID claim.
                            os.kill(child, signal.SIGKILL)
                            os.waitpid(child, 0)
                self.assertEqual(context.identity, original_identity)
            self.assertEqual(snapshot(), active_before)
            lifetime = context._lifetime

        retired_before = snapshot()
        lifetime.active = True
        try:
            with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                context.require_unchanged()
            with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                _ = context.identity
            with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                with scratch_owner.reserve_retained_cargo_scratch_v2(context):
                    self.fail("retired wrapper context obtained scratch ownership")
            object.__setattr__(context._core, "_lifetime", SimpleNamespace(active=True))
            with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                context.require_unchanged()
        finally:
            lifetime.active = False
            object.__setattr__(context._core, "_lifetime", lifetime)
        self.assertEqual(snapshot(), retired_before)
