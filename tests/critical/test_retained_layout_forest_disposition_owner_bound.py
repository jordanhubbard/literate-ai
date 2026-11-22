"""Actual late journal callbacks cannot enlarge a verified descriptor roster."""

from unittest import mock

import tests.critical.test_retained_layout_forest_operation_committed as fixture
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters.retained_layout_forest_observation import _record


class ForestDispositionOwnerBoundTests(fixture.CanonicalCommittedCase):
    def test_last_journal_callback_cannot_enlarge_owner_before_projection(self):
        self.recover_committed_data()
        retirement = self.state / "bounded-owner-disposal"
        retirement.mkdir(mode=0o700)
        with self.canonical_epoch("bounded-owner-stages", bootstrap=True) as (
            observer,
            roles,
            _raw,
        ):
            value = _record(observer)
            owner = disposition.controls._owners(roles)[0]
            original_markers = tuple(owner._markers)
            original = value.journal._raw_documents_from_snapshot
            history, reached = tuple(value.journal._events), []

            def late(snapshot):
                result = original(snapshot)
                if not reached:
                    owner._markers.append(original_markers[0])
                    reached.append(True)
                return result

            try:
                with mock.patch.object(
                    value.journal, "_raw_documents_from_snapshot", late
                ):
                    with mock.patch.object(
                        disposition.controls,
                        "_entries_from_documents",
                        side_effect=AssertionError("unfunded owner projection"),
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "original descriptor descriptions changed"
                        ):
                            disposition.plan_forest_control_disposition(
                                observer, roles, self.quarantine, retirement
                            )
            finally:
                owner._markers[:] = original_markers
            self.assertEqual(reached, [True])
            self.assertEqual(tuple(value.journal._events), history)
            self.assertEqual(tuple(retirement.iterdir()), ())
