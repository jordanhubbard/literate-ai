"""Insufficient declared workspace refuses before canonical control effects."""

from unittest import mock

import tests.critical.test_retained_layout_forest_operation_committed as fixture
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters.retained_layout_forest_observation import _record


class CanonicalDispositionCapacityTests(fixture.CanonicalCommittedCase):
    def test_declared_smaller_workspace_refuses_before_disposition_intent(self):
        self.recover_committed_data()
        moved = self.destination / "app.py"
        before = moved.stat().st_ino, moved.read_bytes()
        reached, refused = [], []
        prepay = disposition._prepay

        def paid(value, plan, owners):
            # Call the actual preflight, on the actual creating ledger. Never
            # alter the policy, charges, factories, or native-effect methods.
            reached.append(value.ledger.metadata)
            try:
                return prepay(value, plan, owners)
            except ValueError as error:
                self.assertIn("allowance exhausted", str(error))
                refused.append(error)
                raise

        with self.assertRaisesRegex(ValueError, "allowance exhausted"):
            with self.committed_disposition(metadata_limit=14 * 1024**3) as (
                observer,
                roles,
            ):
                value = _record(observer)
                history = tuple(value.journal._events)
                public = {
                    path: (path.stat().st_ino, path.read_bytes())
                    for path, _marker, _fd, _node, _target, _content in (
                        roles.reservations._inventory
                    )
                }
                try:
                    with mock.patch.object(disposition, "_prepay", paid):
                        disposition.plan_forest_control_disposition(
                            observer, roles, self.quarantine, self.disposal
                        )
                finally:
                    self.assertEqual(tuple(value.journal._events), history)
                    self.assertEqual(
                        {
                            path: (path.stat().st_ino, path.read_bytes())
                            for path in public
                        },
                        public,
                    )
                    self.assertEqual(tuple(self.disposal.iterdir()), ())
        self.assertEqual(reached, [14 * 1024**3])
        self.assertEqual(len(refused), 1)
        self.assertEqual((moved.stat().st_ino, moved.read_bytes()), before)
