"""Actual replacement Git FDs precede fresh canonical Git role validation."""

import tests.critical.test_retained_layout_forest_operation_recovery as fixture


class CanonicalForestBootstrapTests(fixture.CanonicalForestRecoveryCase):
    def test_real_replacement_git_descriptors_reenter_without_early_git_observation(
        self,
    ):
        self.run_original()
        with self.canonical_epoch("publish-replacement", missing=True) as (
            _observer,
            roles,
            raw,
        ):
            self.assertEqual(len(raw), 1)
            self.assertIsNotNone(roles.reservations._incoming)
            inventory = roles.reservations._inventory
            public = {
                path: (path.stat().st_ino, path.read_bytes())
                for path, _marker, _fd, _node, target, _content in inventory
                if path == target.path and not target.advisory
            }
            self.assertTrue(public)
        with self.canonical_epoch("acquire-replacement", bootstrap=True) as (
            _observer,
            roles,
            raw,
        ):
            self.assertEqual(len(raw), 2)
            self.assertIsNone(roles.reservations._incoming)
            # This is the normal creating canonical lease, after genuine G1
            # raw acquisition, not a permission inferred from request labels.
            roles.require_initial_inputs()
            roles.require_current()
        self.assertEqual(
            {path: (path.stat().st_ino, path.read_bytes()) for path in public}, public
        )
