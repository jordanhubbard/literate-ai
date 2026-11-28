"""Real native shadow censuses remain bounded across the accounting callback."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_finite_creations as production


def _foreign_scan(*args, **kwargs):
    raise AssertionError("foreign native scan executed")


class RetainedMetadataAbsenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "original").write_bytes(b"original payload")
        native = self.root.stat()
        self.node = native.st_dev, native.st_ino, native.st_mode

    def test_ledger_charge_precedes_final_callback_free_frontier(self):
        calls = []
        before = production.retained_metadata_absence(
            self.root, self.node, "litai.harness.mk"
        )
        after = production.retained_metadata_absence(
            self.root,
            self.node,
            "litai.harness.mk",
            charge=lambda count, size: calls.append((count, size)),
        )
        self.assertEqual(before, after)
        self.assertEqual(calls, [(3, 2 * (128 + len(os.fsencode("original"))) + 128)])

    def test_accounting_callback_creating_leaf_cannot_return_absence(self):
        target = self.root / "litai.harness.mk"

        def charge(_count, _size):
            target.mkdir()
            (target / "private").write_bytes(b"foreign payload")

        with self.assertRaisesRegex(ValueError, "funded .*bound|already exists"):
            production.retained_metadata_absence(
                self.root, self.node, "litai.harness.mk", charge=charge
            )
        self.assertEqual((target / "private").read_bytes(), b"foreign payload")

    def test_accounting_callback_growing_unrelated_census_refuses(self):
        def charge(_count, _size):
            (self.root / "sibling").write_bytes(b"unrelated")

        with self.assertRaisesRegex(ValueError, "funded entry bound"):
            production.retained_metadata_absence(
                self.root, self.node, "litai.harness.mk", charge=charge
            )

    def test_batch_closes_earlier_frontier_after_single_accounting_callback(self):
        coordinates = (
            "litai.harness.mk",
            "components/legacy-project-wrapper/component.md",
        )
        calls = []

        def charge(count, size):
            calls.append((count, size))
            (self.root / coordinates[0]).write_bytes(b"occupied earlier frontier")

        with self.assertRaises(ValueError):
            production.retained_metadata_absences(
                self.root, self.node, coordinates, charge=charge
            )
        self.assertEqual(len(calls), 1)

    def test_changed_raw_reader_code_is_refused_before_dispatch(self):
        function = production._absence_at
        original = function.__code__
        try:
            function.__code__ = original.replace(co_name="changed")
            with self.assertRaisesRegex(ValueError, "read implementation changed"):
                production.retained_metadata_absence(
                    self.root, self.node, "litai.harness.mk"
                )
        finally:
            function.__code__ = original

    def test_changed_cursor_generator_body_is_refused(self):
        function = production._root_cursor.__wrapped__
        original = function.__code__
        try:
            function.__code__ = original.replace(co_name="changed")
            with self.assertRaisesRegex(ValueError, "read implementation changed"):
                production.retained_metadata_absence(
                    self.root, self.node, "litai.harness.mk"
                )
        finally:
            function.__code__ = original

    def test_changed_native_delegate_is_refused_before_foreign_reader_runs(self):
        calls = []

        def foreign(*args, **kwargs):
            calls.append(True)
            raise AssertionError("foreign native reader executed")

        with patch.object(os, "scandir", foreign):
            with self.assertRaisesRegex(ValueError, "read dependency changed"):
                production.retained_metadata_absence(
                    self.root, self.node, "litai.harness.mk"
                )
        self.assertEqual(calls, [])

    def test_late_builtin_shadow_is_refused_before_it_runs(self):
        calls = []

        def foreign(*args, **kwargs):
            calls.append(True)
            raise AssertionError("foreign builtin shadow executed")

        with patch.object(production, "len", foreign, create=True):
            with self.assertRaisesRegex(ValueError, "read dependency changed"):
                production.retained_metadata_absence(
                    self.root, self.node, "litai.harness.mk"
                )
        self.assertEqual(calls, [])

    def test_changed_scan_keyword_contents_are_refused(self):
        keywords = production._absence_at.__kwdefaults__
        original = keywords["_costs"]
        try:
            keywords["_costs"] = True
            with self.assertRaisesRegex(ValueError, "read implementation changed"):
                production.retained_metadata_absence(
                    self.root, self.node, "litai.harness.mk"
                )
        finally:
            keywords["_costs"] = original

    def test_accounting_callback_cannot_replace_closing_guard_code(self):
        function = production.retained_metadata_absence_guard
        original = function.__code__

        def charge(_count, _size):
            function.__code__ = original.replace(co_name="changed")

        try:
            with self.assertRaisesRegex(ValueError, "read guard changed"):
                production.retained_metadata_absence(
                    self.root, self.node, "litai.harness.mk", charge=charge
                )
        finally:
            function.__code__ = original

    def test_accounting_callback_cannot_change_scan_before_closing_dispatch(self):
        function = production._absence_at
        original = function.__code__

        def charge(_count, _size):
            function.__code__ = _foreign_scan.__code__

        try:
            with self.assertRaisesRegex(ValueError, "read implementation changed"):
                production.retained_metadata_absence(
                    self.root, self.node, "litai.harness.mk", charge=charge
                )
        finally:
            function.__code__ = original
