"""A complete native forest shares readonly resource accounting before streaming."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_tree_v2 as trees
from literate_ai.adapters.retained_cargo_native_output_tree import (
    _capture_original_native_output_tree,
    _NativeOutputCensusLedger,
)
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)


class RetainedNativeOutputAggregateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(strict=True)
        self.first, self.second = self.root / "first", self.root / "second"
        self.first.mkdir()
        self.second.mkdir()
        (self.first / "payload").write_bytes(b"1234")
        self.budget = RetainedCargoOutputBudget(4, 4)

    def ledger(self, **kwargs):
        return _NativeOutputCensusLedger(
            self.budget, maximum_metadata_bytes=64 * 1024**2, **kwargs
        )

    def capture(self, root, ledger, **kwargs):
        return _capture_original_native_output_tree(
            root, budget=self.budget, _ledger=ledger, **kwargs
        )

    def test_exact_payload_file_and_entry_caps_still_allow_a_following_empty_root(self):
        ledger = self.ledger(maximum_files=1, maximum_entries=1)
        first = self.capture(self.first, ledger, maximum_files=1, maximum_entries=1)
        second = self.capture(self.second, ledger, maximum_files=1, maximum_entries=1)
        self.assertEqual(ledger.usage[:3], (1, 1, 4))
        self.assertEqual(second.payload_bytes, 0)
        fresh = self.ledger(maximum_files=1, maximum_entries=1)
        first.require_unchanged(_ledger=fresh)
        second.require_unchanged(_ledger=fresh)
        self.assertEqual(fresh.usage, ledger.usage)

    def test_aggregate_byte_overrun_refuses_before_reading_later_payload(self):
        (self.second / "foreign").write_bytes(b"x")
        ledger = self.ledger()
        self.capture(self.first, ledger)
        before = ledger.usage
        with patch.object(trees, "_stream", side_effect=AssertionError("payload read")):
            with self.assertRaisesRegex(ValueError, "aggregate-bytes-limit"):
                self.capture(self.second, ledger)
        self.assertEqual(ledger.usage, before)
        self.assertEqual((self.second / "foreign").read_bytes(), b"x")

    def test_zero_byte_files_still_charge_global_file_and_entry_caps(self):
        (self.second / "empty").write_bytes(b"")
        ledger = self.ledger(maximum_files=1, maximum_entries=2)
        self.capture(self.first, ledger, maximum_files=1, maximum_entries=2)
        with patch.object(trees, "_stream", side_effect=AssertionError("payload read")):
            with self.assertRaisesRegex(ValueError, "aggregate-files-limit"):
                self.capture(self.second, ledger, maximum_files=1, maximum_entries=2)
        self.assertTrue((self.second / "empty").exists())

    def test_directories_charge_aggregate_entries_without_borrowing_file_allowance(
        self,
    ):
        (self.second / "directory").mkdir()
        ledger = self.ledger(maximum_files=1, maximum_entries=1)
        self.capture(self.first, ledger, maximum_files=1, maximum_entries=1)
        with self.assertRaisesRegex(ValueError, "aggregate-entries-limit"):
            self.capture(self.second, ledger, maximum_files=1, maximum_entries=1)
        self.assertTrue((self.second / "directory").is_dir())

    def test_remaining_metadata_is_enforced_before_a_later_root_allocates(self):
        ledger = _NativeOutputCensusLedger(
            self.budget, maximum_metadata_bytes=32 * 1024**2
        )
        self.capture(self.first, ledger)
        self.assertLess(ledger.remaining_metadata, 16 * 1024**2)
        before = ledger.usage
        with patch.object(
            trees, "_directory_access", side_effect=AssertionError("allocation")
        ):
            with self.assertRaisesRegex(ValueError, "metadata-limit"):
                self.capture(self.second, ledger)
        self.assertEqual(ledger.usage, before)

    def test_raw_selector_cost_does_not_replace_original_metadata_configuration(self):
        # Selectors alone grant no output/exclusion authority. This checks only
        # that one pass may narrow transient allocation while retaining its
        # original declared metadata ceiling and original old-file expectations.
        ledger = self.ledger()
        first = self.capture(self.first, ledger, exclusions=("future",))
        second = self.capture(self.second, ledger)
        (self.first / "future").mkdir()
        (self.first / "future" / "inert").write_bytes(b"not a permission")
        fresh = self.ledger()
        first.require_unchanged(_ledger=fresh)
        second.require_unchanged(_ledger=fresh)
        self.assertGreater(fresh.usage[3], ledger.usage[3])
        self.assertEqual(first.maximum_metadata_bytes, 1024**3)
        self.assertEqual(second.maximum_metadata_bytes, 1024**3)

    def test_replacement_or_mismatched_ledger_refuses_before_payload(self):
        ledger = self.ledger()
        original = self.capture(self.first, ledger)
        object.__setattr__(original.budget, "_ledger", self.ledger())
        with patch.object(trees, "_stream", side_effect=AssertionError("payload read")):
            with self.assertRaisesRegex(ValueError, "original-ledger-changed"):
                original.require_unchanged()
        other = _NativeOutputCensusLedger(RetainedCargoOutputBudget(5, 5))
        with self.assertRaisesRegex(ValueError, "aggregate-budget-changed"):
            self.capture(self.second, other)

    def test_requested_invalid_metadata_ceiling_is_not_hidden_by_aggregate_clamping(
        self,
    ):
        for value in (True, 0, 16 * 1024**3 + 1):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "metadata-limit-invalid"):
                    self.capture(
                        self.first, self.ledger(), maximum_metadata_bytes=value
                    )
