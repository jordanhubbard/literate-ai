"""Closed topology across actual selected source directories, without effects."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import catalog_source_forest as forests
from literate_ai.adapters import retained_cargo_tree_v2 as streams
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.catalog_source_forest import capture_catalog_source_forest
from literate_ai.adapters.retained_layout_transaction import _native_tree
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


class CatalogSourceForestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.a = self.root / "flavors/a"
        self.b = self.root / "flavors/b"
        self.a.mkdir(parents=True)
        self.b.mkdir()
        (self.a / "one").write_bytes(b"original")
        (self.b / "two").write_bytes(b"second")
        self.budget = RetainedCargoInputBudget(128, 512, 1024**2, 16 * 1024**2)

    def capture(self, **changes):
        options = dict(
            selected_roots=("flavors/a", "flavors/b"),
            budget=self.budget,
            maximum_metadata_bytes=64 * 1024**2,
        )
        options.update(changes)
        return capture_catalog_source_forest(self.root, **options)

    def test_complete_selected_union_is_distinct_from_a_project_partition(self):
        forest = self.capture()
        self.assertNotIsInstance(forest.tree, streams.RetainedCargoInputTreeV2)
        self.assertFalse(hasattr(forest, "framework_files"))
        self.assertEqual(forest.tree.selected_roots, ("flavors/a", "flavors/b"))
        self.assertEqual(
            {name for name, _blob, _mode in forest.tree.files},
            {"flavors/a/one", "flavors/b/two"},
        )
        forest.require_unchanged()
        forest.close_native(_native_tree(forest.tree))

    @unittest.skipUnless(os.name == "posix", "native complete link group")
    def test_cross_item_hardlink_and_directory_alias_share_one_observed_graph(self):
        (self.b / "two").unlink()
        os.link(self.a / "one", self.b / "two")
        (self.a / "to-b").symlink_to("../b", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "hardlink-unowned"):
            streams.capture_retained_cargo_tree_v2(self.a, budget=self.budget)
        forest = self.capture()
        self.assertEqual(forest.tree.file_count, 1)
        self.assertEqual(forest.tree.payload_bytes, len(b"original") + len(b"../b"))
        self.assertEqual(
            {(a.path, a.kind) for a in forest.tree.aliases},
            {("flavors/b/two", "hardlink"), ("flavors/a/to-b", "symlink")},
        )
        forest.require_unchanged()

    def test_unselected_large_payload_is_never_streamed_or_treated_as_owned(self):
        outside = self.root / "unselected"
        outside.write_bytes(b"x" * (2 * 1024**2))
        stream = streams._stream
        seen = []

        def read(root, name, *args, **kwargs):
            seen.append(name)
            return stream(root, name, *args, **kwargs)

        with mock.patch.object(streams, "_stream", read):
            forest = self.capture()
            outside.write_bytes(b"changed outside the selected input scope")
            forest.require_unchanged()
        self.assertEqual(set(seen), {"flavors/a/one", "flavors/b/two"})

    def test_later_selected_payload_change_refuses_original_snapshot(self):
        forest = self.capture()
        (self.b / "two").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            forest.require_unchanged()

    def test_new_ignored_looking_selected_file_is_not_hidden(self):
        forest = self.capture()
        (self.a / ".new").write_bytes(b"new member")
        with self.assertRaises(ValueError):
            forest.require_unchanged()

    @unittest.skipUnless(os.name == "posix", "native selected aliases")
    def test_aliases_into_unselected_or_partial_ancestor_scopes_refuse(self):
        (self.root / "unselected").write_bytes(b"outside")
        alias = self.a / "outside"
        for target in ("../../unselected", "..", "../"):
            with self.subTest(target=target):
                alias.symlink_to(target)
                try:
                    with self.assertRaises((ValueError, TypeError)):
                        self.capture()
                finally:
                    alias.unlink()

    @unittest.skipUnless(os.name == "posix", "native incomplete hardlink group")
    def test_hardlink_with_an_unselected_name_refuses(self):
        os.link(self.a / "one", self.root / "outside-group")
        with self.assertRaisesRegex(ValueError, "hardlink-unowned"):
            self.capture()

    def test_overlapping_or_noncanonical_selections_refuse(self):
        for roots in (
            ("flavors", "flavors-a", "flavors/a"),
            ("flavors/a", "flavors/a"),
            ("../outside",),
            ("flavors/b", "flavors/a"),
            (),
        ):
            with self.subTest(roots=roots), self.assertRaises(ValueError):
                self.capture(selected_roots=roots)

    def test_shared_entry_and_payload_limits_apply_before_acceptance(self):
        with self.assertRaises(ValueError):
            self.capture(budget=RetainedCargoInputBudget(3, 3, 1024**2, 16 * 1024**2))
        (self.a / "one").write_bytes(b"x" * (1024**2 + 1))
        with self.assertRaisesRegex(ValueError, "file-limit"):
            self.capture()

    def test_selected_directory_replaced_by_file_during_discovery_refuses(self):
        inventory = streams._inventory
        changed = False

        def replace(*args, **kwargs):
            nonlocal changed
            if not changed:
                changed = True
                self.a.rename(self.root / "retained-original-a")
                self.a.write_bytes(b"new file replacing selected directory")
            return inventory(*args, **kwargs)

        with mock.patch.object(streams, "_inventory", replace):
            with self.assertRaises(ValueError):
                self.capture()
        self.assertTrue(changed)
        self.assertEqual(
            (self.root / "retained-original-a/one").read_bytes(), b"original"
        )

    def test_late_enlarged_namespace_refuses_before_unknown_descendants(self):
        for whole in (False, True):
            with self.subTest(whole=whole):
                self._check_late_enlarged_namespace(whole)

    def _check_late_enlarged_namespace(self, whole):
        if whole:
            tree = streams.capture_retained_cargo_tree_v2(self.root, budget=self.budget)
            module = transaction

            def close(native, original=tree):
                transaction._close_tree(original, native)
        else:
            census = self.capture()
            tree = census.tree
            module = forests
            close = census.close_native
        native = _native_tree(tree)
        inventory = module._inventory
        visited = []
        foreign = self.a / "late-foreign"

        def enlarged(*args, **kwargs):
            (foreign / "nested/deeper").mkdir(parents=True)
            observe = kwargs["observe"]

            def record(name, node):
                visited.append(name)
                observe(name, node)

            kwargs["observe"] = record
            return inventory(*args, **kwargs)

        try:
            with mock.patch.object(module, "_inventory", enlarged):
                with self.assertRaises(ValueError):
                    close(native)
            self.assertFalse(any("late-foreign/" in name for name in visited))
        finally:
            (foreign / "nested/deeper").rmdir()
            (foreign / "nested").rmdir()
            foreign.rmdir()
