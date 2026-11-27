"""Injected controller cleanup ordering, not actual SDK runtime qualification."""

import unittest
from unittest import mock

from tests.smoke import test_node_sdk_verifier_runtime_native as fixture
from tests.smoke import test_node_sdk_verifier_scan_diagnostic as driver


class SDKRuntimeControllerCleanupTests(unittest.TestCase):
    def exercise(
        self, *, primary=None, cleanup_error=None, cleanup_success=True, diagnostic=None
    ):
        calls = []

        class Case(unittest.TestCase):
            def _exercise_authored_runtime(self, **kwargs):
                calls.append("body")
                if primary is not None:
                    raise primary

            def doCleanups(self):
                calls.append("cleanup")
                if cleanup_error is not None:
                    raise cleanup_error
                return cleanup_success

        with mock.patch.object(
            fixture.runtime_fixture, "CanonicalSDKRuntimeTests", Case
        ):
            try:
                fixture.NativeRuntimeInspectionEnrollmentTests._exercise_enrolled_runtime(
                    self, diagnostic=diagnostic
                )
            finally:
                self.assertEqual(calls, ["body", "cleanup"])

    def test_body_failure_runs_cleanup_and_preserves_primary(self):
        primary = ValueError("original fixture failure")
        with self.assertRaises(ValueError) as failure:
            self.exercise(primary=primary)
        self.assertIs(failure.exception, primary)

    def test_cleanup_precedes_post_body_assertions(self):
        # This injected body produces no native results. The real controller's
        # original post-body acceptance assertion must still refuse it.
        with self.assertRaisesRegex(AssertionError, "0 != 1"):
            self.exercise()

    def test_cleanup_failure_cannot_replace_body_failure(self):
        primary, cleanup = (
            ValueError("original fixture failure"),
            RuntimeError("cleanup failed"),
        )
        with self.assertRaises(ValueError) as failure:
            self.exercise(primary=primary, cleanup_error=cleanup)
        self.assertIs(failure.exception, primary)

    def test_false_cleanup_result_withholds_success_and_records_failure(self):
        from pathlib import Path

        from tests.support.sdk_runtime_diagnostic import SDKRuntimeDiagnostic

        observer = SDKRuntimeDiagnostic(Path(__file__).resolve().parents[2])
        with observer.observe():
            with self.assertRaisesRegex(AssertionError, "fixture cleanup failed"):
                self.exercise(cleanup_success=False, diagnostic=observer)
        self.assertFalse(observer.snapshot()["cleanup_complete"])
        self.assertTrue(observer.snapshot()["capture_incomplete"])

    def test_cleanup_failure_withholds_controller_success(self):
        cleanup = RuntimeError("cleanup failed")
        with self.assertRaises(RuntimeError) as failure:
            self.exercise(cleanup_error=cleanup)
        self.assertIs(failure.exception, cleanup)


class SDKRuntimeDiagnosticDriverTests(unittest.TestCase):
    def exercise(self, *, primary=None, persistence_error=None, cleanup=True):
        reports = []

        def original_body(test, *, diagnostic):
            diagnostic.record_lifecycle_cleanup(cleanup)
            if primary is not None:
                raise primary

        def persist(root, output, report):
            reports.append(report)
            if persistence_error is not None:
                raise persistence_error

        with (
            mock.patch.dict(
                driver.os.environ,
                {"LITAI_NODE_SDK_RUNTIME_DIAGNOSTIC_OUTPUT": "unused.json"},
            ),
            mock.patch.object(driver, "diagnostic_output_path", return_value=None),
            mock.patch.object(
                driver, "persist_runtime_diagnostic", side_effect=persist
            ),
            mock.patch.object(
                driver.fixture.NativeEnrolledSDKScanTests,
                "_exercise_original_scan",
                original_body,
            ),
            mock.patch("builtins.print", side_effect=KeyboardInterrupt),
        ):
            try:
                driver.NativeSDKScanDiagnosticTests.test_original_scan_diagnostic_without_qualification(
                    self
                )
            finally:
                self.assertEqual(len(reports), 1)
                self.assertIs(reports[0]["qualified"], False)
                self.assertIs(reports[0]["capture_active"], False)
                self.assertIs(reports[0]["lifecycle_cleanup_complete"], cleanup)

    def test_persistence_and_print_failures_preserve_exact_original_exception(self):
        primary = ValueError("original native failure")
        with self.assertRaises(ValueError) as failure:
            self.exercise(primary=primary, persistence_error=SystemExit())
        self.assertIs(failure.exception, primary)

    def test_secondary_failure_cannot_turn_body_success_into_failure(self):
        self.exercise(persistence_error=SystemExit())

    def test_false_lifecycle_cleanup_is_persisted_as_incomplete(self):
        self.exercise(cleanup=False)
