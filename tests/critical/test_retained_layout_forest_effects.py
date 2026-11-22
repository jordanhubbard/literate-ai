"""Actual private pins and finite allowance data; no canonical phase fixtures."""

from __future__ import annotations

import os
import unittest
from dataclasses import replace

import tests.critical.test_retained_layout_forest_native as fixtures
from literate_ai.adapters import retained_layout_forest_effects as effects
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.exclusive_entry import layout_entry_node
from literate_ai.adapters.retained_layout_control_publication import _pinned_directory
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.adapters.retained_layout_source_forest_movement import (
    _prepare_native_program,
)


@unittest.skipUnless(os.name == "posix", "actual POSIX private effect pins")
class ForestEffectTests(unittest.TestCase):
    setUp = fixtures.NativeForestBatchTests.setUp
    write = fixtures.NativeForestBatchTests.write
    program = fixtures.NativeForestBatchTests.program
    journal = fixtures.NativeForestBatchTests.journal
    execute = fixtures.NativeForestBatchTests.execute

    def pin(self, name):
        root = self.base / name
        root.mkdir(mode=0o700)
        fd, guard = self.enterContext(_pinned_directory(root))
        return effects._Pin(root, fd, guard, layout_entry_node(root), _lineage(root))

    def future(self):
        return effects._Effects(
            self.pin("metadata"),
            self.pin("retirement"),
            self.parking,
            (256, 4096, 65536),
            (1024, 1024**2),
            (12, 8, 1024**2),
            5,
            3,
        )

    def test_exact_pin_refuses_late_foreign_entry_without_cleanup(self):
        pin = self.pin("metadata")
        effects._require_empty(pin)
        foreign = pin.root / "foreign"
        foreign.write_bytes(b"unowned fixture bytes")
        with self.assertRaisesRegex(ValueError, "effect area changed|became occupied"):
            effects._require_empty(pin)
        self.assertEqual(foreign.read_bytes(), b"unowned fixture bytes")

    def test_exact_pin_refuses_replaced_root_and_retains_original(self):
        pin = self.pin("metadata")
        retained = self.base / "original"
        pin.root.rename(retained)
        pin.root.mkdir(mode=0o700)
        try:
            with self.assertRaises(ValueError):
                effects._require_empty(pin)
            self.assertEqual(retained.stat().st_ino, pin.node.inode)
            self.assertNotEqual(pin.root.stat().st_ino, pin.node.inode)
        finally:
            # Restore the held original path so its real factory closes
            # normally; preserve the replacement fixture directory as well.
            pin.root.rename(self.base / "replacement-preserved")
            retained.rename(pin.root)

    def test_area_separation_checks_both_native_containment_directions(self):
        parent = self.pin("parent")
        child = parent.root / "child"
        child.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, "physically overlap"):
            effects._separate(parent.lineage, _lineage(child))
        with self.assertRaisesRegex(ValueError, "physically overlap"):
            effects._separate(_lineage(child), parent.lineage)
        sibling = self.pin("sibling")
        effects._separate(parent.lineage, sibling.lineage)

    def test_binding_rejects_equal_copied_area_and_changed_original_facts(self):
        future = self.future()
        binding = effects._binding(future)
        self.assertTrue(effects._matches(future, binding))
        copied = replace(future, metadata=replace(future.metadata))
        self.assertEqual(copied.document, future.document)
        self.assertFalse(effects._matches(copied, binding))
        original = future.metadata.node
        try:
            object.__setattr__(
                future.metadata, "node", replace(original, inode=original.inode + 1)
            )
            self.assertFalse(effects._matches(future, binding))
        finally:
            object.__setattr__(future.metadata, "node", original)

    def test_future_decode_reserve_refuses_before_any_source_effect(self):
        source = self.write("app.bin")
        program, future = self.program(), self.future()
        ledger = _Observation(self.budget, 2 * 1024**3, (self.root,))
        ledger.charge_records(self.budget.maximum_entries - 256)
        with self.assertRaisesRegex(ValueError, "decoded-record headroom"):
            effects._preflight_decode_headroom(ledger, program, future)
        self.assertTrue(source.exists())
        self.assertFalse(self.parking.exists())

    def test_decode_preflight_leaves_actual_decoding_to_same_ledger(self):
        self.write("app.bin")
        program, future = self.program(), self.future()
        ledger = _Observation(self.budget, 2 * 1024**3, (self.root,))
        before = ledger.records, ledger.charged, ledger.bytes
        effects._preflight_decode_headroom(ledger, program, future)
        self.assertEqual((ledger.records, ledger.charged, ledger.bytes), before)
        ledger.json_value(b'{"actual":"later receipt"}', "future-event")
        self.assertGreater(ledger.records, before[0])
        self.assertGreater(ledger.charged, before[1])

    def test_complete_tail_is_enforced_by_actual_native_journal(self):
        source = self.write("app.bin")
        original, future = self.program(), self.future()
        ledger = _Observation(self.budget, 2 * 1024**3, (self.root,))
        program = _prepare_native_program(
            ledger,
            original.span,
            original.graph,
            self.parking,
            self.phase,
            journal_tail=future.journal_tail,
        )
        self.assertEqual(program.journal_tail, future.journal_tail)
        budget = LayoutJournalBudget(
            program.required_events + future.journal_tail[0] - 1,
            1024**2,
            16 * 1024**2,
            16,
        )
        with self.journal(budget) as journal:
            with self.assertRaisesRegex(ValueError, "following records"):
                with self.execute(program, journal):
                    self.fail("incomplete operation journal accepted")
        self.assertTrue(source.exists())
        self.assertFalse(self.parking.exists())

    def test_compact_decisions_bind_exact_plan_path_and_distinct_state(self):
        import json

        future = self.future()
        intent = effects._decision_document(
            self.phase, future.retirement.root, committed=False
        )
        commit = effects._decision_document(
            self.phase, future.retirement.root, committed=True
        )
        self.assertNotEqual(intent, commit)
        for raw in (intent, commit):
            value = json.loads(raw)
            self.assertEqual(value["source_phase_identity"], self.phase)
            self.assertEqual(value["retirement_root"], str(future.retirement.root))
            self.assertFalse(value["qualified"])
            self.assertLess(effects._document_nodes(raw), 32)
            self.assertLess(len(raw), 1024)

    def test_oversized_known_decision_path_refuses_before_source_effects(self):
        from pathlib import Path

        source = self.write("app.bin")
        with self.assertRaisesRegex(ValueError, "document-limit"):
            effects._decision_document(
                self.phase, Path("/" + "x" * 70000), committed=True
            )
        self.assertTrue(source.exists())
        self.assertFalse(self.parking.exists())

    def test_oversized_control_roster_preview_refuses_before_source_effects(self):
        from types import SimpleNamespace

        from literate_ai.adapters.retained_layout_reservations import (
            _finalization_intent_data,
        )
        from literate_ai.contracts.identity import canonical_json_bytes

        source = self.write("app.bin")
        pin = self.pin("retirement")
        # Pure event descriptions, never acquired controls or a source phase.
        paths = [self.root / (str(i) + "x" * 1000) for i in range(80)]
        markers = [
            SimpleNamespace(
                target=SimpleNamespace(path=p, advisory=False), created=True
            )
            for p in paths
        ]
        raw = canonical_json_bytes(
            _finalization_intent_data(
                pin.root, pin.node, markers, {p: pin.node for p in paths}
            )
        )
        with self.assertRaisesRegex(ValueError, "document-limit"):
            effects._document_nodes(raw)
        self.assertTrue(source.exists())
        self.assertFalse(self.parking.exists())
