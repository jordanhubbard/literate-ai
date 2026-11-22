"""Actual advisory partial write survives fresh canonical retry."""

import tests.critical.test_retained_layout_forest_disposition_retry as fixture


class ForestPwriteRetryTests(fixture.ForestDispositionRetryFixture):
    def test_actual_pwrite_before_truncate_reacquires_and_completes(self):
        self.run_interruption("pwrite")
