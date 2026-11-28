"""Shared retained DATA preserves fresh canonical ancestry observation."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import bounded_role_observation as reads
from literate_ai.adapters import retained_layout_partition as partition
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


class RoleLineageRetentionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="role-lineage-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.child = self.root / "child"
        self.child.mkdir()

    def scope(self):
        return reads.bounded_role_observation(
            budget=RetainedCargoInputBudget(32, 2048, 1024, 32768),
            maximum_metadata_bytes=64 * 1024**2,
        )

    def test_shared_rows_and_endpoint_reuse_keep_every_fresh_native_probe(self):
        native = Path.lstat
        calls = []

        def observe(path, *args, **kwargs):
            calls.append(str(path))
            return native(path, *args, **kwargs)

        with self.scope() as reader:
            parent = partition._lineage(self.root)
            before = reader._ledger.records
            with mock.patch.object(Path, "lstat", observe):
                first = partition._lineage(self.child)
                first_probes = tuple(calls)
                calls.clear()
                second = partition._lineage(self.child)
                self.assertEqual(tuple(calls), first_probes)
                self.assertGreaterEqual(len(calls), len(first))
            self.assertIs(first, second)
            self.assertEqual(first[:-1], parent)
            self.assertTrue(
                all(a is b for a, b in zip(first[:-1], parent, strict=True))
            )
            self.assertLess(reader._ledger.records - before, 2 * len(self.child.parts))
            self.assertIs(reader._lineage_rows[str(self.child)], first[-1])

    def test_prepaid_rows_are_not_observations_and_need_no_after_creation_funding(self):
        target = self.child / "future"
        with self.scope() as reader:
            partition._lineage(self.child)
            with mock.patch.object(Path, "lstat", side_effect=AssertionError("probe")):
                reader.reserve_lineage(target)
            self.assertIsNone(reader._lineage_rows[str(target)])
            before = reader._ledger.records
            target.mkdir()
            value = partition._lineage(target)
            self.assertEqual(reader._ledger.records, before)
            self.assertIs(reader._lineage_rows[str(target)], value[-1])

    def test_future_shared_prefix_slots_are_funded_once_before_native_effects(self):
        future = self.child / "future"
        left, right = future / "left", future / "right"
        with self.scope() as reader:
            partition._lineage(self.child)
            with mock.patch.object(Path, "lstat", side_effect=AssertionError("probe")):
                reader.reserve_lineage(left)
                before = reader._ledger.records
                reader.reserve_lineage(right)
            self.assertIsNone(reader._lineage_rows[str(future)])
            self.assertIsNone(reader._lineage_rows[str(left)])
            self.assertIsNone(reader._lineage_rows[str(right)])
            self.assertLess(reader._ledger.records - before, 2 * len(right.parts))

    def test_shared_data_does_not_hide_real_directory_replacement(self):
        with self.assertRaisesRegex(ValueError, "ancestry changed"):
            with self.scope() as reader:
                partition._lineage(self.child)
                self.child.rename(self.root / "old-child")
                self.child.mkdir()
                partition._lineage(self.child)
        self.assertTrue(reader._poisoned)

    def test_foreign_row_never_runs_comparison_callback(self):
        calls = []

        class Foreign:
            def __eq__(self, other):
                calls.append("foreign equality")
                raise AssertionError("foreign row")

        with self.assertRaisesRegex(ValueError, "ancestry changed"):
            with self.scope() as reader:
                partition._lineage(self.child)
                reader._lineage_rows[str(self.child)] = Foreign()
                partition._lineage(self.child)
        self.assertEqual(calls, [])

    def test_replaced_row_table_refuses_before_foreign_lookup(self):
        calls = []

        class Foreign:
            def __contains__(self, value):
                calls.append("foreign lookup")
                raise AssertionError("foreign table")

        with self.assertRaisesRegex(ValueError, "canonical read policy changed"):
            with self.scope() as reader:
                reader._lineage_rows = Foreign()
                partition._lineage(self.child)
        self.assertEqual(calls, [])
