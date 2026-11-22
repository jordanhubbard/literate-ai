"""Native-output byte domains retain readonly closed trees without source uplift."""

import copy
import os
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.retained_cargo_native_output_tree import (
    _capture_original_native_output_tree,
)
from literate_ai.adapters.retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from literate_ai.storage.cas import FileSystemCAS


class RetainedNativeOutputCensusTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve(strict=True)
        self.root = self.parent / "old-output"
        self.root.mkdir()
        self.file = self.root / "payload"
        self.file.write_bytes(b"original native payload")
        self.budget = RetainedCargoOutputBudget(1024**2, 4 * 1024**2)

    def capture(self, **kwargs):
        return _capture_original_native_output_tree(
            self.root, budget=self.budget, **kwargs
        )

    def test_readonly_comparison_runs_no_process_cas_write_or_execution(self):
        trap = AssertionError("readonly native census copied or executed payload")
        with (
            patch("subprocess.run", side_effect=trap),
            patch("subprocess.Popen", side_effect=trap),
            patch.object(FileSystemCAS, "put_file", side_effect=trap),
            patch.object(FileSystemCAS, "put_bytes", side_effect=trap),
        ):
            original = self.capture()
            original.require_unchanged()
        self.assertEqual(original.payload_bytes, len(self.file.read_bytes()))
        self.assertEqual(original.exclusions, ())
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(TypeError):
                    operation(original)

    def test_large_native_member_does_not_relax_source_budget_or_copy_payload(self):
        size = 257 * 1024**2
        with self.file.open("wb") as stream:
            stream.truncate(size)
        source_budget = RetainedCargoInputBudget(1, 1, 256 * 1024**2, 256 * 1024**2)
        with self.assertRaisesRegex(ValueError, "input-file-limit"):
            capture_retained_cargo_tree_v2(self.root, budget=source_budget)
        native = RetainedCargoOutputBudget(258 * 1024**2, 300 * 1024**2)
        with patch.object(
            FileSystemCAS, "put_file", side_effect=AssertionError("CAS copy")
        ):
            original = _capture_original_native_output_tree(self.root, budget=native)
            original.require_unchanged()
        self.assertEqual(original.payload_bytes, size)
        self.assertEqual(source_budget.maximum_file_bytes, 256 * 1024**2)
        self.assertEqual(self.file.stat().st_size, size)

    def test_original_native_bytes_cannot_change_and_foreign_change_is_preserved(self):
        original = self.capture()
        changed = b"preserve changed native payload"
        self.file.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "original-tree-changed"):
            original.require_unchanged()
        self.assertEqual(self.file.read_bytes(), changed)

    def test_new_unobserved_namespace_entry_refuses_without_removal(self):
        original = self.capture()
        foreign = self.root / "foreign"
        foreign.write_bytes(b"preserve foreign member")
        with self.assertRaisesRegex(ValueError, "original-tree-changed"):
            original.require_unchanged()
        self.assertEqual(foreign.read_bytes(), b"preserve foreign member")

    def test_same_bytes_in_replaced_original_directory_refuse(self):
        directory = self.root / "nested"
        directory.mkdir()
        (directory / "file").write_bytes(b"same native bytes")
        original = self.capture()
        saved = self.parent / "preserved-original"
        directory.rename(saved)
        directory.mkdir()
        (directory / "file").write_bytes(b"same native bytes")
        with self.assertRaisesRegex(ValueError, "original-tree-changed"):
            original.require_unchanged()
        self.assertEqual((saved / "file").read_bytes(), b"same native bytes")

    def test_complete_hardlink_group_is_charged_once_and_external_alias_refuses(self):
        alias = self.root / "alias"
        os.link(self.file, alias)
        original = self.capture()
        self.assertEqual(original.file_count, 1)
        self.assertEqual(len(original.aliases), 1)
        self.assertEqual(original.payload_bytes, len(self.file.read_bytes()))
        outside = self.parent / "outside-alias"
        os.link(self.file, outside)
        with self.assertRaises(ValueError):
            original.require_unchanged()
        self.assertTrue(outside.samefile(self.file))

    def test_byte_and_entry_aggregate_overruns_refuse_without_changing_payload(self):
        self.file.write_bytes(b"1234")
        second = self.root / "second"
        second.write_bytes(b"5678")
        with self.assertRaisesRegex(ValueError, "input-total-limit"):
            _capture_original_native_output_tree(
                self.root, budget=RetainedCargoOutputBudget(4, 6)
            )
        with self.assertRaisesRegex(ValueError, "input-entry-limit"):
            self.capture(maximum_files=1, maximum_entries=1)
        self.assertEqual(self.file.read_bytes(), b"1234")
        self.assertEqual(second.read_bytes(), b"5678")

    def test_metadata_allowance_and_native_type_are_not_inferred_from_source(self):
        with self.assertRaisesRegex(ValueError, "input-metadata-limit"):
            self.capture(maximum_metadata_bytes=16 * 1024**2)
        with self.assertRaisesRegex(TypeError, "native-budget-required"):
            _capture_original_native_output_tree(
                self.root, budget=RetainedCargoInputBudget(1, 1, 1024, 1024)
            )
        for kwargs in (
            {"maximum_files": True},
            {"maximum_files": 100001},
            {"maximum_entries": 400001},
            {"maximum_files": 2, "maximum_entries": 1},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "namespace-limits-invalid"):
                    self.capture(**kwargs)

    def test_native_and_source_observations_have_distinct_identities(self):
        native = self.capture()
        source = capture_retained_cargo_tree_v2(
            self.root, budget=RetainedCargoInputBudget(10, 10, 1024**2, 4 * 1024**2)
        )
        self.assertEqual(native.files, source.files)
        self.assertEqual(native.directories, source.directories)
        self.assertNotEqual(native.identity, source.identity)

    def test_original_native_resource_values_cannot_be_rebaselined_before_recheck(self):
        original = self.capture()
        changed = self.budget.maximum_total_bytes + 1
        object.__setattr__(self.budget, "maximum_total_bytes", changed)
        with patch(
            "literate_ai.adapters.retained_cargo_native_output_tree._capture_original_native_output_tree",
            side_effect=AssertionError("recaptured with changed allowance"),
        ):
            with self.assertRaisesRegex(ValueError, "original-budget-changed"):
                original.require_unchanged()
        self.assertEqual(self.budget.maximum_total_bytes, changed)
