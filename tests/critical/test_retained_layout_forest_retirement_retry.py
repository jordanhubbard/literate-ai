"""Actual retirement before durable observation survives canonical retry."""

import tests.critical.test_retained_layout_forest_disposition_retry as fixture


class ForestRetirementRetryTests(fixture.ForestDispositionRetryFixture):
    def test_actual_retirement_before_observed_reacquires_and_completes(self):
        self.run_interruption("retired")
