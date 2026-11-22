"""Actual committed canonical operation, fresh recovery, and control release."""

from contextlib import contextmanager

import tests.critical.test_retained_layout_forest_operation_recovery as fixture
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters import retained_layout_forest_recovery as recovery
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)


class CanonicalCommittedCase(fixture.CanonicalForestRecoveryCase):
    def recover_committed_data(self):
        self.run_original()
        self.quarantine = self.state / "committed-quarantine"
        self.quarantine.mkdir(mode=0o700)
        with self.canonical_epoch("committed-data", missing=True) as (
            observer,
            roles,
            _raw,
        ):
            plan = recovery.plan_forest_data_recovery(observer, roles, self.quarantine)
            self.assertTrue(plan.committed)
            self.assertEqual(plan.actions, ())
            result = recovery.apply_forest_data_recovery(
                observer,
                roles,
                plan,
                acknowledged_recovery_identity=plan.identity,
                allow_host_execution=True,
            )
            self.assertTrue(result["data_verified"])
            self.assertFalse(result["qualified"])

    @contextmanager
    def committed_disposition(self, *, metadata_limit=16 * 1024**3):
        self.disposal = self.state / "committed-disposal"
        self.disposal.mkdir(mode=0o700)
        # All original data-recovery owners have ended. Reopen real G0/G1
        # descriptors and rederive canonical Git under the replacement FDs.
        with self.canonical_epoch(
            "committed-release", bootstrap=True, metadata_limit=metadata_limit
        ) as (observer, roles, raw):
            self.assertEqual(len(raw), 2)
            self.assertIsNone(roles.reservations._incoming)
            yield observer, roles


class CanonicalCommittedTests(CanonicalCommittedCase):
    def test_actual_committed_recovery_releases_controls_in_separate_fresh_epoch(self):
        app = self.project / "app.py"
        index = self.project / ".git/index"
        before = app.stat().st_ino, app.read_bytes()
        git_before = index.stat().st_ino, index.read_bytes()
        roots = self.project.stat().st_ino, (self.project / ".git").stat().st_ino
        self.recover_committed_data()
        moved = self.destination / "app.py"
        self.assertEqual((moved.stat().st_ino, moved.read_bytes()), before)
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
        self.assertEqual((moved.stat().st_ino, moved.read_bytes()), before)
        self.assertEqual((index.stat().st_ino, index.read_bytes()), git_before)
        self.assertEqual(
            (self.project.stat().st_ino, (self.project / ".git").stat().st_ino), roots
        )
        self.assertFalse(app.exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())
