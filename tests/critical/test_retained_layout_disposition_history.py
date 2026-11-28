"""Actual journal boundaries bind compact descriptions and abandoned heads."""

from __future__ import annotations

import unittest
from unittest import mock

import tests.critical.test_retained_layout_disposition_compact as fixture
from literate_ai.adapters import retained_layout_disposition_compact as compact
from literate_ai.adapters import retained_layout_disposition_history as history
from literate_ai.adapters import retained_layout_disposition_read as reader
from literate_ai.adapters import retained_layout_disposition_recording as recording
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


class CompactHistoryTests(unittest.TestCase):
    setUp = fixture.CompactDispositionTests.setUp
    keep = fixture.CompactDispositionTests.keep
    action = fixture.CompactDispositionTests.action
    manifest = fixture.CompactDispositionTests.manifest
    data = fixture.CompactDispositionTests.data
    step = fixture.CompactDispositionTests.step
    pair = fixture.CompactDispositionTests.pair

    def journal(self):
        return retained_layout_journal(
            self.root / "journal",
            canonical_binding=b"{}",
            budget=LayoutJournalBudget(
                maximum_payload_bytes=self.options["maximum"],
                maximum_storage_bytes=self.options["storage_limit"],
            ),
        )

    def allowance(self):
        return _Observation(
            RetainedCargoInputBudget(65536, 4_000_000, 1024**2, 2 * 1024**3),
            1024**3,
            (),
        )

    def publish(self, writer):
        for _digest, raw in self.payloads:
            writer.store_payload(raw)

    def begin(self, writer, manifest):
        self.publish(writer)
        writer.store_payload(manifest.raw)
        writer.append(compact.BEGIN, history.batch_boundary(manifest.digest))

    def snapshot(self, writer):
        names = tuple(writer._events)
        events, payloads = writer._raw_documents_from_snapshot(
            (names, tuple(writer._known[name] for name in names))
        )
        return history.expand_history(
            events, payloads, **self.options, expanded_limit=16 * 1024**2
        )

    def test_real_three_event_journal_expands_without_writing_or_changing_source(self):
        manifest = self.manifest()
        head = self.pair(manifest)
        with self.journal() as writer:
            self.begin(writer, manifest)
            writer.append(
                compact.DECISION, history.batch_boundary(manifest.digest, head=None)
            )
            writer.append(
                compact.COMPLETE, history.batch_boundary(manifest.digest, head=head)
            )
            roster = tuple(writer._known.items())
            with mock.patch.object(
                type(writer),
                "append",
                side_effect=AssertionError("semantic reads cannot write"),
            ):
                found = reader.read_history(writer, self.allowance())
            self.assertEqual(len(writer.events), 3)
            self.assertEqual(len(found.records), 5)
            self.assertIsNone(found.open_batch)
            self.assertEqual(
                found.bindings,
                ((manifest.identity, manifest.epoch, manifest.namespace),),
            )
            self.assertEqual(tuple(writer._known.items()), roster)
            self.assertEqual(self.barrier.read_bytes(), b"pending")

    def test_actual_acquisition_anchors_empty_prefix_and_observation_exactly(self):
        manifest = self.manifest()
        with self.journal() as writer:
            self.begin(writer, manifest)
            found = self.snapshot(writer)
            self.assertEqual(found.open_batch, (manifest.digest, None))
            raw = history.acquisition_bytes("sha256:" + "7" * 64, found.open_batch)
            writer.append(history.RAW_INTENT, raw)
            writer.append(history.RAW_OBSERVED, raw)
            found = self.snapshot(writer)
            self.assertIsNone(found.open_batch)
            self.assertEqual(
                [kind for _, kind, _ in found.records],
                [
                    "recovery-control-disposition-intent",
                    history.RAW_INTENT,
                    history.RAW_OBSERVED,
                ],
            )
            for _, _kind, body in found.records[-2:]:
                self.assertEqual(
                    body,
                    canonical_json_bytes(dict(recovery_identity="sha256:" + "7" * 64)),
                )

    def test_receipt_added_after_durable_acquisition_cannot_reinterpret_old_prefix(
        self,
    ):
        manifest = self.manifest()
        with self.journal() as writer:
            self.begin(writer, manifest)
            # Intent durable, then scope ends; no pending-control decision exists.
            intent = self.data(self.actions[0])
            # Even a correctly hashed native-intent payload cannot be added to
            # this already anchored empty prefix on a subsequent process read.
            raw = history.acquisition_bytes(
                "sha256:" + "7" * 64, (manifest.digest, None)
            )
            writer.append(history.RAW_INTENT, raw)
            writer.append(history.RAW_OBSERVED, raw)
            self.step(manifest, 0, None, intent)
            self.publish(writer)
            with self.assertRaisesRegex(ValueError, "durable decision|freeze exact"):
                self.snapshot(writer)

    def test_missing_anchor_and_changed_observation_refuse(self):
        manifest = self.manifest()
        with self.journal() as writer:
            self.begin(writer, manifest)
            writer.append(
                history.RAW_INTENT,
                history.acquisition_bytes("sha256:" + "7" * 64, None),
            )
            with self.assertRaisesRegex(ValueError, "must anchor"):
                self.snapshot(writer)

    def test_unpaired_physical_boundaries_and_foreign_events_refuse(self):
        manifest = self.manifest()
        with self.journal() as writer:
            self.publish(writer)
            writer.append(
                compact.COMPLETE, history.batch_boundary(manifest.digest, head=None)
            )
            with self.assertRaisesRegex(ValueError, "actual manifest intent"):
                self.snapshot(writer)

    def test_prepay_refuses_before_any_native_snapshot_callback(self):
        manifest = self.manifest()
        with self.journal() as writer:
            self.begin(writer, manifest)
            allowance = self.allowance()
            allowance.records = allowance.budget.maximum_entries
            with mock.patch.object(
                type(writer),
                "_raw_documents_from_snapshot",
                side_effect=AssertionError("unfunded native read"),
            ):
                with self.assertRaises(ValueError):
                    reader.read_history(writer, allowance)

    def test_native_file_count_total_and_per_file_limits_precede_snapshot_reads(self):
        manifest = self.manifest()
        with self.journal() as writer:
            self.begin(writer, manifest)
            total = sum(len(raw) for _node, raw in writer._known.values())
            peak = max(len(raw) for _node, raw in writer._known.values())
            policies = (
                RetainedCargoInputBudget(1, 4_000_000, 1024**2, 1024**2),
                RetainedCargoInputBudget(65536, 4_000_000, 1, 65536),
                RetainedCargoInputBudget(65536, 4_000_000, peak, 2 * total),
            )
            for policy in policies:
                allowance = _Observation(policy, 1024**3, ())
                with self.subTest(policy=policy):
                    with mock.patch.object(
                        type(writer),
                        "_raw_documents_from_snapshot",
                        side_effect=AssertionError("unfunded native IO"),
                    ):
                        with self.assertRaises(ValueError):
                            reader.read_history(writer, allowance)

    def test_native_read_counters_cover_both_complete_journal_passes(self):
        manifest = self.manifest()
        with self.journal() as writer:
            self.begin(writer, manifest)
            allowance = self.allowance()
            count = len(writer._known)
            total = sum(len(raw) for _node, raw in writer._known.values())
            reader.read_history(writer, allowance)
            self.assertEqual(allowance.files, 2 * count)
            self.assertEqual(allowance.bytes, 2 * total)

    def test_independent_reads_decode_again_and_fund_every_native_comparison(self):
        manifest = self.manifest()
        with self.journal() as writer:
            self.begin(writer, manifest)
            allowance = self.allowance()
            count = len(writer._known)
            total = sum(len(raw) for _node, raw in writer._known.values())
            with mock.patch.object(
                history, "expand_history", wraps=history.expand_history
            ) as decoder:
                first = reader.read_history(writer, allowance)
                second = reader.read_history(writer, allowance)
            self.assertEqual(decoder.call_count, 2)
            self.assertEqual(first, second)
            self.assertIsNot(first, second)
            self.assertEqual(allowance.files, 4 * count)
            self.assertEqual(allowance.bytes, 4 * total)

    def test_a_descriptive_or_unregistered_plan_cannot_borrow_parent_callbacks(self):
        with self.assertRaises(TypeError):
            reader._ControlPlanRead(object())
        for candidate in (object(), {"cached_history": "not authority"}):
            token = reader._PLAN.set(candidate)
            try:
                with mock.patch(
                    "literate_ai.adapters.retained_layout_forest_observation._record",
                    side_effect=AssertionError("unregistered scope borrowed parent"),
                ):
                    with self.assertRaisesRegex(ValueError, "plan lifetime ended"):
                        reader.control_history(object())
            finally:
                reader._PLAN.reset(token)

    def test_direct_recording_helpers_cannot_borrow_a_journal_or_effect(self):
        with self.assertRaisesRegex(ValueError, "actual live journal"):
            reader.has_compact(object())
        with self.assertRaisesRegex(ValueError, "registered forest"):
            recording.prepare(object())
        # A hashable arbitrary object is no descriptor/effect capability.
        with self.assertRaisesRegex(ValueError, "recording dispatch"):
            recording.record(object(), "recovery-control-disposition-intent", {})
