"""Explicit single-case diagnosis; the complete public cohort remains required."""

from __future__ import annotations

import unittest

from tests.critical import test_project_layout_framework_cli as original


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(
        (
            original.FrameworkMigrationCliTests(
                "test_public_plan_descendant_apply_and_repeated_recovery"
            ),
        )
    )
