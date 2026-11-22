"""Reopen real persisted journals with fresh read budgets, never phase rights."""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_native as fixtures
from literate_ai.adapters import retained_layout_forest_native as native
from literate_ai.adapters import retained_layout_forest_recovery_read as recovery
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.retained_layout_partition import _lineage


@unittest.skipUnless(os.name == "posix", "actual fresh native journal reader")
class ForestRecoveryReadTests(unittest.TestCase):
    setUp = fixtures.NativeForestBatchTests.setUp
    write = fixtures.NativeForestBatchTests.write
    program = fixtures.NativeForestBatchTests.program
    journal = fixtures.NativeForestBatchTests.journal
    execute = fixtures.NativeForestBatchTests.execute

    def allowance(self):
        return _Observation(self.budget, 2 * 1024**3, ())

    def read(self, journal, program, *, allowance=None, lineage=None):
        return recovery.read_native_forest_frontier(
            journal,
            program,
            allowance=self.allowance() if allowance is None else allowance,
            parking_parent_lineage=(
                _lineage(self.parking.parent) if lineage is None else lineage
            ),
        )

    def completed(self, *, wrapped=False):
        self.write("source/app.bin")
        program = self.program("source", "source/new/implementation")
        with self.journal() as journal:
            if wrapped:
                # Marker-name selection fixture only: these plain diagnostic
                # bodies deliberately claim no successful canonical source join.
                journal.append("forest-source-intent", b'{"fixture":true}')
            with self.execute(program, journal) as owner:
                owner.run()
                final = owner._span
            if wrapped:
                journal.append("forest-source-observed", b'{"fixture":true}')
        return program, final

    def test_fresh_actual_writer_reads_completed_history_without_effect_calls(self):
        program, final = self.completed()
        with self.journal(recover=True) as journal:
            before = tuple(journal._known.items())
            with (
                mock.patch.object(
                    type(journal), "append", side_effect=AssertionError("write effect")
                ),
                mock.patch.object(
                    type(journal),
                    "store_payload",
                    side_effect=AssertionError("write effect"),
                ),
                mock.patch.object(
                    native,
                    "move_layout_entry_exclusive",
                    side_effect=AssertionError("move"),
                ),
            ):
                found = self.read(journal, program)
            self.assertTrue(found.complete)
            self.assertIsNone(found.pending)
            self.assertEqual(found.span, final)
            self.assertEqual(tuple(journal._known.items()), before)

    def test_ended_journal_refuses_before_any_guard_or_descriptor_read(self):
        program, _ = self.completed()
        with self.journal(recover=True) as journal:
            pass
        lineage = _lineage(self.parking.parent)
        with (
            mock.patch.object(
                journal, "_guard", side_effect=AssertionError("ended guard")
            ),
            mock.patch.object(os, "open", side_effect=AssertionError("ended FD")),
        ):
            with self.assertRaisesRegex(ValueError, "actual current journal"):
                self.read(journal, program, lineage=lineage)

    def test_fresh_small_policy_refuses_before_first_guard_or_descriptor_read(self):
        program, _ = self.completed()
        small = _Observation(
            replace(
                self.budget,
                maximum_files=4,
                maximum_entries=4,
                maximum_total_bytes=4 * 1024**2,
            ),
            128 * 1024**2,
            (),
        )
        lineage = _lineage(self.parking.parent)
        with self.journal(recover=True) as journal:
            with (
                mock.patch.object(
                    journal,
                    "require_current",
                    side_effect=AssertionError("unfunded traversal"),
                ),
                mock.patch.object(
                    os, "open", side_effect=AssertionError("unfunded FD")
                ),
            ):
                with self.assertRaisesRegex(ValueError, "allowance exhausted"):
                    self.read(journal, program, allowance=small, lineage=lineage)

    def test_source_join_marker_names_are_not_native_envelopes(self):
        program, final = self.completed(wrapped=True)
        with self.journal(recover=True) as journal:
            self.assertEqual(self.read(journal, program).span, final)

    def test_fresh_file_count_and_per_file_limits_apply_before_first_traversal(self):
        program, _ = self.completed()
        lineage = _lineage(self.parking.parent)
        for budget in (
            replace(self.budget, maximum_files=2, maximum_total_bytes=2 * 1024**2),
            replace(self.budget, maximum_file_bytes=64, maximum_total_bytes=4096 * 64),
        ):
            with self.subTest(budget=budget), self.journal(recover=True) as journal:
                allowance = _Observation(budget, 2 * 1024**3, ())
                with mock.patch.object(
                    journal,
                    "require_current",
                    side_effect=AssertionError("unfunded traversal"),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "allowance exhausted|per-file"
                    ):
                        self.read(
                            journal, program, allowance=allowance, lineage=lineage
                        )

    def test_closing_traversal_debits_cumulative_fresh_file_and_byte_limits(self):
        program, _ = self.completed()
        with self.journal(recover=True) as journal:
            count = len(journal._known)
            total = sum(len(row[1]) for row in journal._known.values())
            for budget in (
                replace(self.budget, maximum_files=2 * count - 1),
                replace(
                    self.budget,
                    maximum_total_bytes=self.budget.maximum_file_bytes + 2 * total - 1,
                ),
            ):
                allowance = _Observation(budget, 2 * 1024**3, ())
                require = journal.require_current
                with (
                    self.subTest(budget=budget),
                    mock.patch.object(
                        journal, "require_current", wraps=require
                    ) as guarded,
                ):
                    with self.assertRaisesRegex(ValueError, "allowance exhausted"):
                        self.read(journal, program, allowance=allowance)
                    self.assertEqual(guarded.call_count, 1)

    def test_final_native_callback_cannot_replace_original_event_order(self):
        program, _ = self.completed()
        with self.journal(recover=True) as journal:
            original, require, count = (
                tuple(journal._events),
                journal.require_current,
                0,
            )

            def change_at_final_close(**keywords):
                nonlocal count
                count += 1
                require(**keywords)
                if count == 2:
                    journal._events.reverse()

            try:
                with mock.patch.object(
                    journal, "require_current", side_effect=change_at_final_close
                ):
                    with self.assertRaisesRegex(ValueError, "roster changed"):
                        self.read(journal, program)
                self.assertEqual(count, 2)
            finally:
                journal._events[:] = original

    def test_final_native_callback_cannot_change_original_program(self):
        program, _ = self.completed()
        with self.journal(recover=True) as journal:
            original = program.source_phase_identity
            require, count = journal.require_current, 0

            def change_at_final_close(**keywords):
                nonlocal count
                count += 1
                require(**keywords)
                if count == 2:
                    object.__setattr__(program, "source_phase_identity", "changed")

            try:
                with mock.patch.object(
                    journal, "require_current", side_effect=change_at_final_close
                ):
                    with self.assertRaisesRegex(ValueError, "roster changed"):
                        self.read(journal, program)
            finally:
                object.__setattr__(program, "source_phase_identity", original)

    def test_unobserved_real_move_remains_pending_after_fresh_journal_open(self):
        self.write("source/app.bin")
        program = self.program("source", "retained")
        emit = native._NativeForest._event

        def stop_after_effect(owner, kind, data):
            if kind == "forest-entry-observed":
                raise RuntimeError("fixture stop after native move")
            emit(owner, kind, data)

        with self.assertRaisesRegex(RuntimeError, "fixture stop"):
            with self.journal() as journal:
                with mock.patch.object(
                    native._NativeForest, "_event", stop_after_effect
                ):
                    with self.execute(program, journal) as owner:
                        owner.run()
        self.assertFalse((self.root / "source").exists())
        self.assertTrue((self.parking / "c-0000/app.bin").is_file())
        with self.journal(recover=True) as journal:
            found = self.read(journal, program)
        self.assertFalse(found.complete)
        self.assertEqual(found.pending[0], "forest-entry-intent")
        intent = json.loads(found.pending[1])
        self.assertEqual(intent["source"], str(self.root / "source"))
        # The recorded predecessor remains at source; fresh endpoint
        # reclassification must still resolve the actual post-intent move.
        self.assertIn("source", dict(found.span.roots[0].native))
        self.assertNotIn("c-0000", dict(found.span.roots[1].native))

    def test_non_native_record_cannot_interrupt_unfinished_native_schedule(self):
        self.write("app.bin")
        program = self.program()
        emit = native._NativeForest._event

        def stop_after_parking_intent(owner, kind, data):
            emit(owner, kind, data)
            if kind == "forest-parking-intent":
                raise RuntimeError("fixture stop before parking")

        with self.assertRaisesRegex(RuntimeError, "fixture stop"):
            with self.journal() as journal:
                with mock.patch.object(
                    native._NativeForest, "_event", stop_after_parking_intent
                ):
                    with self.execute(program, journal):
                        self.fail("interrupted factory yielded")
        with self.journal(recover=True) as journal:
            journal.append("foreign-operation", b"{}")
            with self.assertRaisesRegex(ValueError, "interrupts the native"):
                self.read(journal, program)

    def test_later_metadata_record_is_allowed_only_after_native_completion(self):
        program, final = self.completed()
        with self.journal(recover=True) as journal:
            journal.append("metadata-fixture", b"{}")
            self.assertEqual(self.read(journal, program).span, final)
            journal.append("forest-foreign", b"{}")
            with self.assertRaisesRegex(ValueError, "single contiguous prefix"):
                self.read(journal, program)
