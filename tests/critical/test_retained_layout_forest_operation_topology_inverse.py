"""Actual interrupted mixed forest restores every alias and shared ancestor."""

import tests.critical.test_retained_layout_forest_operation_topology as fixture
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters import retained_layout_forest_recovery as recovery
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)


class MixedCanonicalInverseTests(fixture.MixedForestCase):
    def test_actual_interrupted_mixed_forest_restores_complete_source_and_aliases(self):
        self.run_original(interrupt=True)
        quarantine = self.state / "mixed-inverse-quarantine"
        quarantine.mkdir(mode=0o700)
        with self.canonical_epoch("mixed-inverse") as (observer, roles, _raw):
            plan = recovery.plan_forest_data_recovery(observer, roles, quarantine)
            self.assertFalse(plan.committed)
            self.assertTrue(plan.actions)
            result = recovery.apply_forest_data_recovery(
                observer,
                roles,
                plan,
                acknowledged_recovery_identity=plan.identity,
                allow_host_execution=True,
            )
            self.assertTrue(result["data_verified"])
            self.assertFalse(result["qualified"])
        disposal = self.state / "mixed-inverse-disposal"
        disposal.mkdir(mode=0o700)
        with self.canonical_epoch("mixed-inverse-release") as (observer, roles, _raw):
            plan = disposition.plan_forest_control_disposition(
                observer, roles, quarantine, disposal
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
        self.assert_source_at(self.project)
        self.assertFalse(self.destination.exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())
