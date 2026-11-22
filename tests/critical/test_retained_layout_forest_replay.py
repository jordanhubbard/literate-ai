"""Real unmanaged native journal prefixes; no reconstructed canonical rights."""

from __future__ import annotations

import hashlib
import json
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_native as fixtures
from literate_ai.adapters import retained_layout_forest_native as native
from literate_ai.adapters import retained_layout_forest_replay as replay
from literate_ai.adapters.catalog_copy_plan import _Observation
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual native journal receipt prefixes")
class ForestReplayTests(unittest.TestCase):
    setUp = fixtures.NativeForestBatchTests.setUp
    write = fixtures.NativeForestBatchTests.write
    program = fixtures.NativeForestBatchTests.program
    journal = fixtures.NativeForestBatchTests.journal
    execute = fixtures.NativeForestBatchTests.execute

    def capture(self, program):
        emit, snapshots = native._NativeForest._event, []

        def capture_event(owner, kind, data):
            emit(owner, kind, data)
            snapshots.append(owner._span)

        with self.journal() as journal:
            with mock.patch.object(native._NativeForest, "_event", capture_event):
                with self.execute(program, journal) as owner:
                    owner.run()
                    final = owner._span
            records = tuple(
                (
                    event["kind"],
                    canonical_json_bytes(event["data"]),
                    journal.read_payload(event["data"]["payload_digest"]),
                )
                for event in journal.events
            )
        return records, tuple(snapshots), final

    def read(self, program, records, *, allowance=None, lineage=None):
        return replay.replay_native_forest(
            program,
            records,
            allowance=allowance or _Observation(self.budget, 2 * 1024**3, ()),
            parking_parent_lineage=(
                _lineage(self.parking.parent) if lineage is None else lineage
            ),
        )

    def assert_prefixes(self, program, records, snapshots):
        empty = self.read(program, ())
        self.assertIs(empty.span, program.span)
        self.assertFalse(empty.complete)
        self.assertIsNone(empty.pending)
        for length in range(1, len(records) + 1):
            with self.subTest(prefix=length, kind=records[length - 1][0]):
                found = self.read(program, records[:length])
                expected = snapshots[length - 1]
                self.assertEqual(found.consumed, length)
                self.assertEqual(found.complete, length == len(records))
                self.assertEqual(
                    found.pending is not None,
                    records[length - 1][0].endswith("-intent"),
                )
                dirty = set(found.refresh_directories)
                for area, (recorded, actual) in enumerate(
                    zip(found.span.roots, expected.roots, strict=True)
                ):
                    self.assertEqual(recorded.payloads, actual.payloads)
                    self.assertEqual(recorded.links, actual.links)
                    self.assertEqual(recorded.lineage, actual.lineage)
                    actual_nodes = dict(actual.native)
                    self.assertEqual(set(dict(recorded.native)), set(actual_nodes))
                    for name, node in recorded.native:
                        if (area, name) in dirty:
                            self.assertEqual(
                                node.directory_identity,
                                actual_nodes[name].directory_identity,
                            )
                        else:
                            self.assertEqual(node, actual_nodes[name])

    def test_every_actual_root_prefix_preserves_hardlinks_and_raw_symlinks(self):
        source = self.write("dir/app.bin")
        os.link(source, self.root / "z-hard.bin")
        (self.root / "alias").symlink_to("dir/app.bin")
        program = self.program()
        records, snapshots, final = self.capture(program)
        self.assert_prefixes(program, records, snapshots)
        found = self.read(program, records)
        self.assertEqual(found.span, final)
        self.assertEqual(found.refresh_directories, ())

    def test_every_nested_stage_and_mode_prefix_has_exact_recorded_predecessor(self):
        self.write("source/app.bin")
        program = self.program("source", "source/new/implementation")
        records, snapshots, final = self.capture(program)
        self.assert_prefixes(program, records, snapshots)
        self.assertEqual(self.read(program, records).span, final)
        stage = next(
            i + 1
            for i, row in enumerate(records)
            if row[0] == "forest-directory-observed"
        )
        self.assertEqual(
            self.read(program, records[:stage]).refresh_directories, ((1, ""),)
        )

    def test_every_ancestor_merge_prefix_retains_empty_original_containers(self):
        self.write("a/fixed.bin")
        self.write("source/a/app.bin")
        program = self.program("source", ".")
        records, snapshots, final = self.capture(program)
        self.assert_prefixes(program, records, snapshots)
        self.assertEqual(self.read(program, records).span, final)
        self.assertGreaterEqual(len(final.roots[1].native), 3)

    def test_reordered_or_duplicated_events_refuse_before_any_native_access(self):
        self.write("app.bin")
        program = self.program()
        records, _, _ = self.capture(program)
        lineage = _lineage(self.parking.parent)
        with mock.patch.object(os, "open", side_effect=AssertionError("native access")):
            for changed in ((records[1], records[0]), (records[0], records[0])):
                with self.assertRaisesRegex(ValueError, "reordered, duplicated"):
                    self.read(program, changed, lineage=lineage)

    def test_wrong_original_or_payload_digest_never_rebinds_program(self):
        self.write("app.bin")
        program = self.program()
        records, _, _ = self.capture(program)
        for key in ("program_identity", "source_phase_identity", "payload_digest"):
            envelope = json.loads(records[0][1])
            envelope[key] = "sha256:" + "0" * 64
            changed = (records[0][0], canonical_json_bytes(envelope), records[0][2])
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "not bound"):
                self.read(program, (changed,))

    def mutate(self, records, index, change):
        kind, envelope_raw, payload = records[index]
        data = json.loads(payload)
        change(data)
        payload = canonical_json_bytes(data)
        envelope = json.loads(envelope_raw)
        envelope["payload_digest"] = hashlib.sha256(payload).hexdigest()
        return (*records[:index], (kind, canonical_json_bytes(envelope), payload))

    def test_semantically_wrong_receipt_refuses_even_with_matching_digest(self):
        self.write("source/app.bin")
        program = self.program("source", "source/new/implementation")
        records, _, _ = self.capture(program)
        for kind, field, value in (
            ("forest-entry-intent", "destination", str(self.root / "foreign")),
            ("forest-native-complete", "state", "qualified"),
        ):
            index = next(i for i, row in enumerate(records) if row[0] == kind)
            changed = self.mutate(
                records,
                index,
                lambda data, field=field, value=value: data.update({field: value}),
            )
            with (
                self.subTest(kind=kind),
                self.assertRaisesRegex(ValueError, "contradicts"),
            ):
                self.read(program, changed)
        index = next(
            i for i, row in enumerate(records) if row[0] == "forest-entry-observed"
        )
        changed = self.mutate(
            records, index, lambda data: data["node"].update(inode=17)
        )
        with self.assertRaisesRegex(ValueError, "moved node differs"):
            self.read(program, changed)

    def test_low_fresh_policy_refuses_before_decoding_or_native_access(self):
        self.write("app.bin")
        program = self.program()
        records, _, _ = self.capture(program)
        allowance = _Observation(
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
        with (
            mock.patch.object(
                _Observation,
                "json_value",
                side_effect=AssertionError("unfunded decode"),
            ),
            mock.patch.object(os, "open", side_effect=AssertionError("native access")),
        ):
            with self.assertRaisesRegex(ValueError, "allowance exhausted"):
                self.read(program, records, allowance=allowance, lineage=lineage)
        self.assertEqual(allowance.budget.maximum_entries, 4)

    def test_wrong_parking_shared_ancestry_refuses_without_substitute_observation(self):
        self.write("app.bin")
        program = self.program()
        records, _, _ = self.capture(program)
        lineage = list(_lineage(self.parking.parent))
        row = lineage[0]
        lineage[0] = (row[0], row[1], row[2] + 1, *row[3:])
        with self.assertRaisesRegex(ValueError, "shared ancestors"):
            self.read(program, records, lineage=tuple(lineage))

    def test_new_parking_cannot_borrow_original_or_parent_directory_inode(self):
        self.write("source/nested/app.bin")
        program = self.program("source", "retained")
        records, _, _ = self.capture(program)
        index = next(
            i for i, row in enumerate(records) if row[0] == "forest-parking-observed"
        )
        originals = dict(program.span.roots[0].native)
        for device, inode in (
            (originals["source/nested"].device, originals["source/nested"].inode),
            _lineage(self.parking.parent)[-1][1:3],
        ):
            changed = self.mutate(
                records,
                index,
                lambda data, device=device, inode=inode: data["node"].update(
                    device=device, inode=inode
                ),
            )
            with (
                self.subTest(inode=inode),
                self.assertRaisesRegex(ValueError, "parking.*aliases"),
            ):
                self.read(program, changed)

    def test_changed_program_schedule_cannot_be_replayed(self):
        self.write("app.bin")
        program = self.program()
        records, _, _ = self.capture(program)
        changed = replace(program, actions=tuple(reversed(program.actions)))
        with self.assertRaisesRegex(ValueError, "deterministic schedule"):
            self.read(changed, records)
