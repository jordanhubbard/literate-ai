"""Actual retained controls survive context failure without retaining OS locks."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import _write_reservations as reservations
from literate_ai.adapters.repository_orchestration import OrchestrationInventoryError


class RetainedLayoutReservationRetentionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="layout-res-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        node = self.root.stat()
        self.node = node.st_dev, node.st_ino, node.st_mode

    def target(self, name, *, advisory=False):
        return reservations.WriteReservationTarget(
            self.root / name, self.root, self.node, advisory=advisory
        )

    def acquire(self, *names):
        return reservations.acquire_write_reservations(
            tuple(self.target(name) for name in names)
        )

    def snapshot(self):
        return {
            path.relative_to(self.root).as_posix(): (
                path.stat().st_ino,
                path.read_bytes() if path.is_file() else None,
            )
            for path in self.root.rglob("*")
        }

    def assert_closed(self, descriptors):
        for fd in descriptors:
            with self.assertRaises(OSError):
                os.fstat(fd)

    def test_normal_exit_retains_exact_nodes_and_invalidates_live_owner(self):
        with self.acquire("control/nested/index.lock", "HEAD.lock") as owned:
            owned.retain_for_explicit_recovery()
            owned.retain_for_explicit_recovery()
            before = self.snapshot()
            descriptors = [marker.descriptor for marker in owned._markers]
            self.assertTrue(owned.owns(self.root / "HEAD.lock"))
        self.assertEqual(self.snapshot(), before)
        self.assert_closed(descriptors)
        with self.assertRaises(OrchestrationInventoryError) as caught:
            owned.owns(self.root / "HEAD.lock")
        self.assertEqual(caught.exception.code, "orchestration.reservation_inactive")
        with self.assertRaises(OrchestrationInventoryError):
            with self.acquire("HEAD.lock"):
                self.fail("retained marker stolen")
        self.assertEqual(self.snapshot(), before)

    def test_body_failure_retains_controls_and_original_exception(self):
        original = RuntimeError("transaction requires recovery")
        with self.assertRaises(RuntimeError) as caught:
            with self.acquire("control/index.lock", "HEAD.lock") as owned:
                owned.retain_for_explicit_recovery()
                before = self.snapshot()
                descriptors = [marker.descriptor for marker in owned._markers]
                raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(self.snapshot(), before)
        self.assert_closed(descriptors)

    def test_default_success_and_failure_still_remove_owned_controls(self):
        with self.acquire("control/index.lock") as owned:
            self.assertTrue(owned.owns(self.root / "control/index.lock"))
        self.assertEqual(self.snapshot(), {})
        with self.assertRaisesRegex(RuntimeError, "ordinary"):
            with self.acquire("control/index.lock"):
                raise RuntimeError("ordinary")
        self.assertEqual(self.snapshot(), {})
        with self.assertRaises(OrchestrationInventoryError) as caught:
            owned.retain_for_explicit_recovery()
        self.assertEqual(caught.exception.code, "orchestration.reservation_inactive")

    def test_detected_foreign_change_also_retains_other_owned_controls(self):
        with self.assertRaises(OrchestrationInventoryError) as caught:
            with self.acquire("control/first.lock", "control/second.lock") as owned:
                foreign = self.root / "control/first.lock"
                foreign.write_bytes(b"foreign bytes")
                before = self.snapshot()
                descriptors = [marker.descriptor for marker in owned._markers]
                owned.retain_for_explicit_recovery()
        self.assertEqual(caught.exception.code, "orchestration.reservation_changed")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(foreign.read_bytes(), b"foreign bytes")
        self.assert_closed(descriptors)

    def test_closing_failure_still_attempts_every_descriptor_and_keeps_nodes(self):
        real_close = os.close
        closed = []

        def failing_close(fd):
            real_close(fd)
            if fd in descriptors:
                closed.append(fd)
                if len(closed) == 1:
                    raise OSError("injected close report")

        with self.assertRaises(OrchestrationInventoryError) as caught:
            with mock.patch.object(
                reservations.os, "close", side_effect=real_close
            ) as closer:
                with self.acquire("control/first.lock", "control/second.lock") as owned:
                    owned.retain_for_explicit_recovery()
                    before = self.snapshot()
                    descriptors = [marker.descriptor for marker in owned._markers]
                    closer.side_effect = failing_close
        self.assertEqual(
            caught.exception.code, "orchestration.reservation_cleanup_incomplete"
        )
        self.assertTrue(set(descriptors) <= set(closed))
        self.assert_closed(descriptors)
        self.assertEqual(self.snapshot(), before)

    def test_body_and_release_failures_both_remain_visible(self):
        original = RuntimeError("body failure")
        real_close = os.close

        def reporting_close(fd):
            real_close(fd)
            raise OSError("injected close report")

        with self.assertRaises(BaseExceptionGroup) as caught:
            with mock.patch.object(
                reservations.os, "close", side_effect=real_close
            ) as closer:
                with self.acquire("HEAD.lock") as owned:
                    owned.retain_for_explicit_recovery()
                    before = self.snapshot()
                    closer.side_effect = reporting_close
                    raise original
        self.assertIs(caught.exception.exceptions[0], original)
        self.assertEqual(
            caught.exception.exceptions[1].code,
            "orchestration.reservation_cleanup_incomplete",
        )
        self.assertEqual(self.snapshot(), before)

    def test_retained_advisory_marker_releases_actual_os_mutex(self):
        target = self.target("lifecycle.lock", advisory=True)
        with reservations.acquire_write_reservations((target,)) as owned:
            owned.retain_for_explicit_recovery()
            before = self.snapshot()
            descriptors = [marker.descriptor for marker in owned._markers]
        self.assert_closed(descriptors)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; import sys; "
                "from literate_ai._cache_lock import exclusive_cache_lock; "
                "ctx=exclusive_cache_lock(Path(sys.argv[1]),timeout_seconds=0.1); "
                "ctx.__enter__(); ctx.__exit__(None,None,None)",
                str(target.path),
            ],
            capture_output=True,
            timeout=15,
            env={
                **os.environ,
                "PYTHONPATH": str(Path(reservations.__file__).resolve().parents[2]),
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(OrchestrationInventoryError) as caught:
            with reservations.acquire_write_reservations((target,)):
                self.fail("retained advisory marker admitted")
        self.assertEqual(caught.exception.code, "orchestration.reservation_busy")
        self.assertEqual(self.snapshot(), before)

    def test_close_interruption_still_attempts_every_remaining_descriptor(self):
        interruption = KeyboardInterrupt("release interrupted")
        real_close = os.close
        attempted, descriptors = [], []

        def interrupted_close(fd):
            real_close(fd)
            if fd in descriptors:
                attempted.append(fd)
                if len(attempted) == 1:
                    raise interruption

        try:
            with self.assertRaises(KeyboardInterrupt) as caught:
                with mock.patch.object(
                    reservations.os, "close", side_effect=real_close
                ) as closer:
                    with self.acquire("control/a.lock", "control/b.lock") as owned:
                        owned.retain_for_explicit_recovery()
                        before = self.snapshot()
                        descriptors[:] = [m.descriptor for m in owned._markers]
                        closer.side_effect = interrupted_close
            self.assertIs(caught.exception, interruption)
            self.assertCountEqual(attempted, descriptors)
            self.assert_closed(descriptors)
            self.assertEqual(self.snapshot(), before)
            with self.assertRaises(OrchestrationInventoryError):
                owned.verify_all()
        finally:
            # The predecessor leaks a descriptor; causal fixtures retire it here.
            for fd in descriptors:
                try:
                    os.fstat(fd)
                except OSError:
                    continue
                real_close(fd)

    def test_mixed_release_interruptions_and_body_error_are_all_preserved(self):
        body = RuntimeError("body requires recovery")
        interruption = KeyboardInterrupt("close interrupted")
        close_error = OSError("another close report")
        real_close = os.close
        attempted, descriptors = [], []

        def interrupted_close(fd):
            real_close(fd)
            if fd in descriptors:
                attempted.append(fd)
                raise interruption if len(attempted) == 1 else close_error

        try:
            with self.assertRaises(BaseExceptionGroup) as caught:
                with mock.patch.object(
                    reservations.os, "close", side_effect=real_close
                ) as closer:
                    with self.acquire("a.lock", "b.lock") as owned:
                        owned.retain_for_explicit_recovery()
                        before = self.snapshot()
                        descriptors[:] = [m.descriptor for m in owned._markers]
                        closer.side_effect = interrupted_close
                        raise body
            self.assertIs(caught.exception.exceptions[0], body)
            release = caught.exception.exceptions[1]
            self.assertIsInstance(release, BaseExceptionGroup)
            self.assertEqual(release.exceptions, (interruption, close_error))
            self.assertCountEqual(attempted, descriptors)
            self.assert_closed(descriptors)
            self.assertEqual(self.snapshot(), before)
        finally:
            for fd in descriptors:
                try:
                    os.fstat(fd)
                except OSError:
                    continue
                real_close(fd)
