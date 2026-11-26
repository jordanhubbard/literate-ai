"""Original run context needed by the committed bounded-process consumer."""

import threading
import unittest

from literate_ai.application import native_root_run as run
from tests.critical import test_native_root_run as fixture


class NativeRootContextTests(unittest.TestCase):
    setUp = fixture.NativeRootRunTests.setUp
    open = fixture.NativeRootRunTests.open

    def test_no_context_preserves_the_original_operation_cap(self):
        self.assertIsNone(run.current_native_root_run())
        self.assertEqual(run.native_root_timeout(41), 41)

    def test_original_owner_and_decreasing_budget_propagate_without_reset(self):
        with self.open() as owner:
            with run.activate_native_root_run(owner):
                self.assertIs(run.current_native_root_run(), owner)
                self.assertEqual(run.native_root_timeout(60), 10)
                self.utc += 3_000_000_000
                self.monotonic += 3_000_000_000
                with run.activate_native_root_run(owner):
                    self.assertIs(run.current_native_root_run(), owner)
                    self.assertEqual(run.native_root_timeout(60), 7)
                self.assertEqual(run.native_root_timeout(2), 2)
            self.assertIsNone(run.current_native_root_run())
            self.assertEqual(owner.remaining(), 7)

    def test_exception_restores_context_without_replacing_the_live_owner(self):
        with self.open() as owner:
            with self.assertRaisesRegex(ValueError, "original failure"):
                with run.activate_native_root_run(owner):
                    raise ValueError("original failure")
            self.assertIsNone(run.current_native_root_run())
            self.assertEqual(owner.remaining(), 10)

    def test_different_owner_cannot_replace_the_active_original(self):
        with self.open() as original, self.open() as other:
            with run.activate_native_root_run(original):
                with self.assertRaises(run.NativeRootRunError) as caught:
                    with run.activate_native_root_run(other):
                        self.fail("foreign owner entered")
                self.assertEqual(
                    caught.exception.code, "native_root_run.owner_mismatch"
                )
                self.assertIs(run.current_native_root_run(), original)

    def test_expired_context_refuses_and_unwinds_to_no_context(self):
        with self.open() as owner:
            with run.activate_native_root_run(owner):
                self.monotonic += 10_000_000_000
                with self.assertRaises(run.NativeRootRunError) as caught:
                    run.current_native_root_run()
                self.assertEqual(caught.exception.code, "native_root_run.expired")
                with self.assertRaises(run.NativeRootRunError):
                    run.native_root_timeout(60)
            self.assertIsNone(run.current_native_root_run())

    def test_thread_without_context_does_not_acquire_host_run_authority(self):
        observed = []
        with self.open() as owner, run.activate_native_root_run(owner):
            thread = threading.Thread(
                target=lambda: observed.append(run.current_native_root_run())
            )
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(observed, [None])
            self.assertIs(run.current_native_root_run(), owner)
