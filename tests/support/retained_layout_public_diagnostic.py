"""Explicit managed selector for the unchanged public metadata migration case."""

import unittest

from tests.e2e import test_retained_harness_receipts as original


def load_tests(_loader, _tests, _pattern):
    return unittest.TestSuite(
        (
            original.RetainedHarnessReceiptTests(
                "test_public_layout_migration_edits_only_reviewed_link_and_rolls_back"
            ),
        )
    )
