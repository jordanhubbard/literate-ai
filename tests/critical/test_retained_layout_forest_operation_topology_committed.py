"""Fresh canonical committed recovery retains the complete mixed source forest."""

import tests.critical.test_retained_layout_forest_operation_topology as fixture
from literate_ai.adapters import retained_layout_forest_disposition as disposition


class MixedCanonicalCommittedTests(fixture.MixedForestCase):
    def test_actual_committed_mixed_forest_reopens_and_releases_all_controls(self):
        self.recover_committed_data()
        with self.committed_disposition() as (observer, roles):
            plan = disposition.plan_forest_control_disposition(
                observer, roles, self.quarantine, self.disposal
            )
            result = disposition.apply_forest_control_disposition(
                observer,
                roles,
                plan,
                acknowledged_recovery_identity=plan.identity,
                allow_host_execution=True,
            )
            self.assertTrue(result["controls_released"])
            self.assertFalse(result["qualified"])
        self.assert_source_moved()
