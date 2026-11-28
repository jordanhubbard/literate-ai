"""Raced private entries refuse inside the prepaid current-area roster."""

from unittest import mock

import tests.critical.test_retained_layout_forest_operation_committed as fixture
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters.retained_layout_forest_observation import _record


class ForestDispositionAreaBoundTests(fixture.CanonicalCommittedCase):
    def test_foreign_private_entry_refuses_before_new_plan_or_intent(self):
        self.recover_committed_data()
        retirement = self.state / "bounded-area-disposal"
        retirement.mkdir(mode=0o700)
        original = disposition.controls._entries
        inserted = []

        def entries(pool, owners, **kwargs):
            result = original(pool, owners, **kwargs)
            root = next(
                root
                for owner in owners
                if type(owner) is disposition.controls._RecoveredControlSet
                for root in (
                    *(area.root for area in owner._plan.recovery_areas),
                    *(
                        (owner._plan.retirement_root,)
                        if owner._plan.retirement_root
                        else ()
                    ),
                )
            )
            foreign = root / "foreign-after-sizing"
            self.assertFalse(foreign.exists())
            foreign.write_bytes(b"foreign data must survive refusal\n")
            inserted.append(foreign)
            return result

        with self.assertRaisesRegex(
            ValueError, "retirement namespace exceeds its bound"
        ):
            with self.canonical_epoch("bounded-area-stages", bootstrap=True) as (
                observer,
                roles,
                _raw,
            ):
                value = _record(observer)
                history = tuple(value.journal._events)
                try:
                    with mock.patch.object(disposition.controls, "_entries", entries):
                        disposition.plan_forest_control_disposition(
                            observer, roles, self.quarantine, retirement
                        )
                finally:
                    self.assertEqual(len(inserted), 1)
                    self.assertEqual(tuple(value.journal._events), history)
                    self.assertEqual(tuple(retirement.iterdir()), ())
                    self.assertEqual(
                        inserted[0].read_bytes(), b"foreign data must survive refusal\n"
                    )
        self.assertEqual(len(inserted), 1)
