"""Typed decoding and real new-process loading, without an old native owner."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_native as fixtures
import tests.critical.test_retained_layout_forest_recovery_read as readers
from literate_ai.adapters import retained_layout_forest_program_read as programs
from literate_ai.adapters import retained_layout_forest_recovery_read as recovery
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.retained_layout_forest_native import _wire
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual persisted native program loading")
class ForestProgramReadTests(unittest.TestCase):
    setUp = fixtures.NativeForestBatchTests.setUp
    write = fixtures.NativeForestBatchTests.write
    program = fixtures.NativeForestBatchTests.program
    journal = fixtures.NativeForestBatchTests.journal
    execute = fixtures.NativeForestBatchTests.execute
    completed = readers.ForestRecoveryReadTests.completed

    def allowance(self):
        return _Observation(self.budget, 2 * 1024**3, ())

    def encoded(self, program):
        return canonical_json_bytes(_wire({"program": program.document}))

    def load(self, journal):
        return recovery.load_native_forest_frontier(
            journal,
            allowance=self.allowance(),
            parking_parent_lineage=_lineage(self.parking.parent),
        )

    def test_decode_preserves_all_original_types_without_native_access(self):
        source = self.write("dir/app.bin")
        os.link(source, self.root / "z-hard.bin")
        (self.root / "alias").symlink_to("dir/app.bin")
        program = self.program()
        raw, allowance = self.encoded(program), self.allowance()
        with mock.patch.object(
            os, "open", side_effect=AssertionError("decoder native I/O")
        ):
            loaded = programs.decode_native_forest_start(raw, allowance=allowance)
        self.assertEqual(loaded, program)
        self.assertIsNot(loaded, program)
        self.assertIsNot(loaded.span, program.span)
        self.assertIsNot(
            loaded.span.roots[0].native[0][1], program.span.roots[0].native[0][1]
        )
        self.assertEqual(loaded.identity, program.identity)
        self.assertGreater(allowance.records, 0)

    def test_loaded_program_replays_actual_completed_journal(self):
        program, final = self.completed()
        with self.journal(recover=True) as journal:
            loaded, frontier = self.load(journal)
        self.assertIsNot(loaded, program)
        self.assertEqual(loaded, program)
        self.assertEqual(frontier.span, final)
        self.assertTrue(frontier.complete)

    def test_new_process_loads_program_only_from_retained_journal(self):
        program, final = self.completed()
        script = """
import json, sys
from pathlib import Path
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.retained_layout_forest_recovery_read import (
    load_native_forest_frontier,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget, retained_layout_journal,
)
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.adapters.repository_refresh_reservations import _custody_wire
with retained_layout_journal(
    Path(sys.argv[1]), canonical_binding=bytes.fromhex(sys.argv[2]),
    budget=LayoutJournalBudget(128, 1024**2, 16*1024**2, 16), recover=True,
) as journal:
    allowance = _Observation(
        RetainedCargoInputBudget(4096,131072,1024**2,16*1024**2), 2*1024**3, (),
    )
    program, frontier = load_native_forest_frontier(
        journal, allowance=allowance,
        parking_parent_lineage=_lineage(Path(sys.argv[3])),
    )
    print(json.dumps({
        'program':program.identity.uri,
        'span':canonical_identity(_custody_wire(frontier.span)).uri,
        'complete':frontier.complete,
    }))
"""
        child = subprocess.run(
            [
                sys.executable,
                "-B",
                "-c",
                script,
                str(self.base / "journal"),
                canonical_json_bytes({"source_phase_identity": self.phase}).hex(),
                str(self.parking.parent),
            ],
            env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(child.returncode, 0, child.stderr)
        from literate_ai.adapters.repository_refresh_reservations import _custody_wire
        from literate_ai.contracts.identity import canonical_identity

        self.assertEqual(
            json.loads(child.stdout),
            {
                "program": program.identity.uri,
                "span": canonical_identity(_custody_wire(final)).uri,
                "complete": True,
            },
        )

    def test_low_fresh_budget_refuses_before_json_decode(self):
        self.write("app.bin")
        raw = self.encoded(self.program())
        budget = replace(
            self.budget,
            maximum_files=4,
            maximum_entries=4,
            maximum_total_bytes=4 * 1024**2,
        )
        allowance = _Observation(budget, 128 * 1024**2, ())
        with mock.patch.object(
            _Observation, "json_value", side_effect=AssertionError("unfunded decode")
        ):
            with self.assertRaisesRegex(ValueError, "allowance exhausted"):
                programs.decode_native_forest_start(raw, allowance=allowance)

    def test_changed_actions_fields_schema_and_path_do_not_reconstruct(self):
        self.write("app.bin")
        raw = self.encoded(self.program())
        changes = (
            lambda body: body["program"]["program"]["actions"].reverse(),
            lambda body: body["program"]["program"].update(extra=True),
            lambda body: body["program"].update(schema="unsupported"),
            lambda body: body["program"]["program"].update(
                private_root=str(self.parking) + "/"
            ),
        )
        for change in changes:
            data = json.loads(raw)
            change(data)
            with self.subTest(change=change), self.assertRaises(ValueError):
                programs.decode_native_forest_start(
                    canonical_json_bytes(data), allowance=self.allowance()
                )

    def test_missing_or_duplicate_native_start_is_not_a_program(self):
        self.write("app.bin")
        program = self.program()
        with self.journal() as journal:
            with self.assertRaisesRegex(ValueError, "one durable native program"):
                self.load(journal)
            with self.execute(program, journal) as owner:
                owner.run()
            start = journal.events[0]
            journal.append(start["kind"], canonical_json_bytes(start["data"]))
            with self.assertRaisesRegex(ValueError, "one durable native program"):
                self.load(journal)

    def test_loader_rejects_program_from_another_header_phase(self):
        program, _ = self.completed()
        from literate_ai.adapters.retained_layout_journal import (
            LayoutJournalBudget,
            retained_layout_journal,
        )
        from literate_ai.contracts.identity import canonical_identity

        with retained_layout_journal(
            self.base / "other-journal",
            budget=LayoutJournalBudget(128, 1024**2, 16 * 1024**2, 16),
            canonical_binding=canonical_json_bytes(
                {"source_phase_identity": canonical_identity({"other": True}).uri}
            ),
        ) as other:
            raw = self.encoded(program)
            digest = other.store_payload(raw)
            other.append(
                "forest-native-start",
                canonical_json_bytes(
                    {
                        "source_phase_identity": program.source_phase_identity,
                        "program_identity": program.identity.uri,
                        "payload_digest": digest,
                    }
                ),
            )
            with self.assertRaisesRegex(ValueError, "original journal phase"):
                self.load(other)
