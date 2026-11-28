"""Actual inert scanner bounds preserve existing below-limit identities."""

import unittest
from unittest import mock

from literate_ai.security import (
    RuleBasedSourceScanner,
    SourceModule,
    baseline_python_rules,
    scanning,
)


class BoundedSourceScanningTests(unittest.TestCase):
    def scanner(self, **kwargs):
        return RuleBasedSourceScanner(
            "scanner:bounded-fixture@1", baseline_python_rules(), **kwargs
        )

    def test_default_and_bounded_reports_keep_the_same_identity(self):
        modules = (
            SourceModule.create("src/input.py", b"exec(value)\npickle.loads(data)\n"),
        )
        original = self.scanner().scan(modules)
        bounded = self.scanner(maximum_findings=2).scan(modules)
        self.assertEqual(original, bounded)
        self.assertEqual(original.digest, bounded.digest)
        self.assertEqual(original.rule_set_digest, bounded.rule_set_digest)

    def test_limit_refuses_before_allocating_another_finding(self):
        modules = (SourceModule.create("src/input.py", b"exec(first)\nexec(second)\n"),)
        original = scanning.SecurityFinding
        counts = None
        with mock.patch.object(scanning, "SecurityFinding", wraps=original) as allocate:
            try:
                self.scanner(maximum_findings=1).scan(modules)
            except ValueError as error:
                self.assertIn("finding budget exceeded", str(error))
                frame = error.__traceback__
                try:
                    while frame is not None:
                        if frame.tb_frame.f_code.co_name == "scan":
                            counts = (
                                len(frame.tb_frame.f_locals["observed"]),
                                len(frame.tb_frame.f_locals["findings"]),
                            )
                        frame = frame.tb_next
                finally:
                    frame = None
            else:
                self.fail(
                    "overflow must refuse instead of returning a truncated report"
                )
            self.assertEqual(allocate.call_count, 1)
        self.assertEqual(counts, (1, 1))

    def test_duplicate_content_does_not_spend_another_finding(self):
        content = b"exec(first)\n"
        modules = tuple(SourceModule.create(name, content) for name in ("a.py", "b.py"))
        report = self.scanner(maximum_findings=1).scan(modules)
        self.assertEqual(len(report.findings), 1)
        self.assertEqual(report, self.scanner().scan(modules))

    def test_invalid_limits_refuse_including_bool_and_late_mutation(self):
        for value in (False, True, 0, -1, 1.0, "1", object()):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    self.scanner(maximum_findings=value)
                scanner = self.scanner(maximum_findings=1)
                scanner.maximum_findings = value
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    scanner.scan(())
