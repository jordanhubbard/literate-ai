"""Actual forest observer and journal; internal cache scope, never source effects.

A harmless ordinary journal note exercises conservative compact detection. It is
not fabricated disposition evidence. The full canonical G2 test owns that proof.
"""

import inspect
import os
import unittest
from contextvars import copy_context
from unittest import mock

import tests.critical.test_retained_layout_forest_observation as fixture
from literate_ai.adapters import retained_layout_disposition_history as history
from literate_ai.adapters import retained_layout_disposition_read as reader
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_forest_original_read as original_read
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_journal import _LayoutJournalWriter
from literate_ai.contracts.identity import canonical_json_bytes


class ControlPlanHistoryTests(unittest.TestCase):
    git = fixture.ForestObservationTests.git
    init_git = fixture.ForestObservationTests.init_git
    prepare = fixture.ForestObservationTests.prepare
    pool = fixture.ForestObservationTests.pool
    persist_guarded_root = fixture.ForestObservationTests.persist_guarded_root
    reopen = fixture.ForestObservationTests.reopen
    run_unmanaged = fixture.ForestObservationTests.run_unmanaged
    retain = fixture.ForestObservationTests.retain
    setUp = fixture.ForestObservationTests.setUp

    def observing(self, pool):
        return observation.observed_forest_recovery(
            pool,
            self.parking.parent,
            budget=self.fresh_budget,
            maximum_metadata_bytes=16 * 1024**3,
        )

    @classmethod
    def setUpClass(cls):
        fixture.ForestObservationTests.setUpClass.__func__(cls)

    def test_actual_scope_reuses_semantics_but_reads_native_bytes_and_fresh_views(self):
        self.retain()
        with (
            self.reopen() as journal,
            staged_layout_controls(self.fresh, journal) as pool,
        ):
            with (
                mock.patch.object(
                    original_read, "_saved_seal", wraps=original_read._saved_seal
                ) as saved_seal,
                self.observing(pool) as owner,
                owner._reads(),
            ):
                self.assertEqual(saved_seal.call_count, 1)
                journal.append(
                    "history-read-note",
                    canonical_json_bytes({"text": "recovery-control-batch-"}),
                )
                snapshots = []
                actual_snapshot = _LayoutJournalWriter._raw_documents_from_snapshot

                def snapshot(*args, **kwargs):
                    snapshots.append(True)
                    return actual_snapshot(*args, **kwargs)

                with mock.patch.object(
                    history, "expand_history", wraps=history.expand_history
                ) as decode:
                    with mock.patch.object(
                        _LayoutJournalWriter, "_raw_documents_from_snapshot", snapshot
                    ):
                        with reader.control_plan_history(pool):
                            first = reader.control_history(pool)
                            self.assertIs(first, reader.control_history(pool))
                            mutable = reader.control_events(pool)
                            mutable[-1]["data"]["text"] = "foreign mutable view"
                            self.assertEqual(
                                reader.control_events(pool)[-1]["data"]["text"],
                                "recovery-control-batch-",
                            )
                            expired = copy_context()
                        self.assertEqual(decode.call_count, 1)
                        self.assertEqual(len(snapshots), 4)
                        with mock.patch.object(
                            os, "fstat", side_effect=AssertionError("expired native FD")
                        ):
                            with self.assertRaisesRegex(
                                ValueError, "plan lifetime ended"
                            ):
                                expired.run(reader.control_history, pool)
                        with reader.control_plan_history(pool):
                            self.assertEqual(reader.control_history(pool), first)
                        self.assertEqual(decode.call_count, 2)

    def test_actual_final_parent_callback_cannot_append_after_the_last_decode(self):
        self.retain()
        with (
            self.reopen() as journal,
            staged_layout_controls(self.fresh, journal) as pool,
        ):
            with self.observing(pool) as owner, owner._reads():
                journal.append(
                    "history-read-note",
                    canonical_json_bytes({"text": "recovery-control-batch-"}),
                )
                actual_record = observation._record
                body_finished, reached = [], []
                factory_code = reader.control_plan_history.__wrapped__.__code__

                def last_callback(*args, **kwargs):
                    value = actual_record(*args, **kwargs)
                    if (
                        body_finished
                        and not reached
                        and inspect.currentframe().f_back.f_code is factory_code
                    ):
                        reached.append(True)
                        journal.append(
                            "history-late-note",
                            canonical_json_bytes(
                                {"text": "actual late native publication"}
                            ),
                        )
                    return value

                with mock.patch.object(observation, "_record", last_callback):
                    with self.assertRaisesRegex(ValueError, "plan snapshot changed"):
                        with reader.control_plan_history(pool):
                            reader.control_history(pool)
                            body_finished.append(True)
                self.assertEqual(reached, [True])

    def test_original_plan_state_and_history_cannot_change_after_native_callbacks(self):
        self.retain()
        with (
            self.reopen() as journal,
            staged_layout_controls(self.fresh, journal) as pool,
        ):
            with self.observing(pool) as owner, owner._reads():
                journal.append(
                    "history-read-note",
                    canonical_json_bytes({"text": "recovery-control-batch-"}),
                )
                # Each negative starts from a separate actual factory; no
                # fabricated history or observer grants a successful plan.
                for field in ("snapshot", "history"):
                    with self.subTest(field=field):
                        with self.assertRaisesRegex(ValueError, "plan.*changed"):
                            with reader.control_plan_history(pool):
                                found = reader.control_history(pool)
                                state = reader._active_plan()
                                if field == "snapshot":
                                    object.__setattr__(state, "snapshot", None)
                                else:
                                    object.__setattr__(
                                        found, "open_batch", ("foreign", None)
                                    )

    def test_selected_views_skip_unneeded_json_but_authenticate_complete_history(self):
        self.retain()
        with (
            self.reopen() as journal,
            staged_layout_controls(self.fresh, journal) as pool,
        ):
            with self.observing(pool) as owner, owner._reads():
                journal.append(
                    "history-unselected-note",
                    canonical_json_bytes(
                        {"text": "recovery-control-batch-", "unused": list(range(256))}
                    ),
                )
                journal.append(
                    "history-selected-note", canonical_json_bytes({"text": "original"})
                )
                with reader.control_plan_history(pool):
                    # Prime only the immutable, completely validated history.
                    semantic = reader.control_history(pool)
                    expected = tuple(
                        dict(sequence=i, kind=kind, data=reader.json.loads(raw))
                        for i, (_, kind, raw) in enumerate(semantic.records)
                        if kind == "history-selected-note"
                    )
                    selected_raw = next(
                        raw
                        for _, kind, raw in semantic.records
                        if kind == "history-selected-note"
                    )
                    actual_snapshot = _LayoutJournalWriter._raw_documents_from_snapshot
                    with (
                        mock.patch.object(
                            reader.json, "loads", wraps=reader.json.loads
                        ) as decode,
                        mock.patch.object(
                            _LayoutJournalWriter,
                            "_raw_documents_from_snapshot",
                            autospec=True,
                            side_effect=actual_snapshot,
                        ) as native,
                    ):
                        selected = reader.control_events(
                            pool, kinds=frozenset({"history-selected-note"})
                        )
                        self.assertEqual(selected, expected)
                        self.assertEqual(
                            decode.call_args_list, [mock.call(selected_raw)]
                        )
                        self.assertEqual(native.call_count, 1)
                        complete_roster = native.call_args.kwargs["_expected"]
                        self.assertEqual(complete_roster, tuple(journal._known.items()))
                    selected[0]["data"]["text"] = "changed local view"
                    self.assertEqual(
                        reader.control_events(
                            pool, kinds=frozenset({"history-selected-note"})
                        ),
                        expected,
                    )
                    before = observation._record(owner, reading=True).ledger.charged
                    reader.control_events(pool, kinds=frozenset())
                    selected_cost = (
                        observation._record(owner, reading=True).ledger.charged - before
                    )
                    before = observation._record(owner, reading=True).ledger.charged
                    reader.control_events(pool)
                    complete_cost = (
                        observation._record(owner, reading=True).ledger.charged - before
                    )
                    self.assertLess(selected_cost, complete_cost)
