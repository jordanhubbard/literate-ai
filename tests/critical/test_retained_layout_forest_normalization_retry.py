"""Actual normalization before durable observation survives canonical retry."""

import tests.critical.test_retained_layout_forest_disposition_retry as fixture


class ForestNormalizationRetryTests(fixture.ForestDispositionRetryFixture):
    def test_actual_normalization_before_observed_reacquires_and_completes(self):
        self.run_interruption("normalized")
