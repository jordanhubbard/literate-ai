"""Actual raw layout namespace custody does not confer movement authority."""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.retained_layout import RetainedLayoutError
from literate_ai.adapters.retained_layout_partition import (
    capture_retained_layout_partition,
)
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


class RetainedLayoutPartitionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.budget = RetainedCargoInputBudget(128, 256, 1024**2, 16 * 1024**2)

    def capture(self, framework=()):
        return capture_retained_layout_partition(
            self.root,
            framework_files=framework,
            budget=self.budget,
            maximum_metadata_bytes=32 * 1024**2,
        )

    def write(self, name, content=b"raw\r\n\x00bytes"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def symlink(self, name, target, *, directory=False):
        try:
            (self.root / name).symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(
                f"actual symbolic link facility unavailable: {type(exc).__name__}"
            )

    def test_complete_namespace_keeps_ignored_names_and_shared_ancestors(self):
        self.write("components/framework/component.md")
        self.write("components/application/input.bin")
        self.write(".ignored/source.bin")
        self.write(".git/control.bin")
        (self.root / "empty").mkdir()
        before = {
            p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file()
        }
        census = self.capture(("components/framework/component.md",))
        self.assertEqual(
            census.other_files,
            (
                ".git/control.bin",
                ".ignored/source.bin",
                "components/application/input.bin",
            ),
        )
        self.assertEqual(census.shared_directories, (".", "components"))
        self.assertIn("empty", census.tree.directories)
        self.assertEqual(census.tree.exclusions, ())
        self.assertEqual(
            before,
            {
                p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob("*")
                if p.is_file()
            },
        )
        census.require_unchanged()

    def test_new_input_byte_mode_or_physical_replacement_refuses_currentness(self):
        for mutation in ("new", "bytes", "replace"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory).resolve()
                source = root / "source.bin"
                source.write_bytes(b"original")
                census = capture_retained_layout_partition(
                    root,
                    framework_files=(),
                    budget=self.budget,
                    maximum_metadata_bytes=32 * 1024**2,
                )
                if mutation == "new":
                    (root / ".ignored-new").write_bytes(b"new")
                elif mutation == "bytes":
                    source.write_bytes(b"modified")
                else:
                    source.unlink()
                    source.write_bytes(b"original")
                with self.assertRaises(ValueError):
                    census.require_unchanged()

    @unittest.skipUnless(os.name == "posix", "native executable mode bits required")
    def test_changed_executable_mode_refuses_currentness(self):
        source = self.write("source")
        census = self.capture()
        source.chmod(source.stat().st_mode ^ 0o100)
        with self.assertRaises(ValueError):
            census.require_unchanged()

    def test_labels_bind_identity_and_cannot_name_directories_or_missing_files(self):
        self.write("nested/input")
        unlabeled = self.capture()
        labeled = self.capture(("nested/input",))
        self.assertNotEqual(unlabeled.identity, labeled.identity)
        self.assertEqual(unlabeled.tree.identity, labeled.tree.identity)
        for names in (("nested",), ("missing",), ("nested/input", "nested/input")):
            with self.subTest(names=names), self.assertRaises(RetainedLayoutError):
                self.capture(names)

    def test_complete_hardlinks_preserve_internal_topology_and_refuse_cross_partition(
        self,
    ):
        original = self.write("one")
        os.link(original, self.root / "two")
        census = self.capture()
        self.assertEqual(len(census.tree.files), 1)
        self.assertEqual(
            [(a.path, a.target, a.kind) for a in census.tree.aliases],
            [("two", "one", "hardlink")],
        )
        with self.assertRaises(RetainedLayoutError):
            self.capture(("one",))
        self.capture(("one", "two")).require_unchanged()

    def test_external_hardlink_group_cannot_be_silently_captured(self):
        original = self.write("one")
        self.capture().require_unchanged()
        with tempfile.TemporaryDirectory() as directory:
            os.link(original, Path(directory) / "outside")
            with self.assertRaises(RetainedLayoutError):
                self.capture()

    def test_aliases_preserve_source_topology_and_refuse_framework_or_shared_targets(
        self,
    ):
        self.write("mixed/framework")
        self.write("mixed/source")
        self.symlink("source-alias", "mixed/source")
        self.capture(("mixed/framework",)).require_unchanged()
        self.symlink("framework-alias", "mixed/framework")
        with self.assertRaises(RetainedLayoutError):
            self.capture(("mixed/framework",))
        (self.root / "framework-alias").unlink()
        self.symlink("shared-alias", "mixed", directory=True)
        with self.assertRaises(RetainedLayoutError):
            self.capture(("mixed/framework",))

    def test_alias_traversal_through_another_partition_refuses_even_same_final_role(
        self,
    ):
        self.write("source")
        self.symlink("zzz-middle", "source")
        self.symlink("aaa-outer", "zzz-middle")
        with self.assertRaisesRegex(RetainedLayoutError, "traverses"):
            self.capture(("zzz-middle",))

    def test_portable_alias_and_finite_byte_budget_refuse_without_changes(self):
        self.write("source", b"12345")
        before = (self.root / "source").read_bytes()
        with self.assertRaises(RetainedLayoutError):
            capture_retained_layout_partition(
                self.root,
                framework_files=(),
                budget=RetainedCargoInputBudget(1, 2, 4, 4),
                maximum_metadata_bytes=32 * 1024**2,
            )
        self.assertEqual((self.root / "source").read_bytes(), before)
        with self.assertRaises(RetainedLayoutError):
            self.capture(("../source",))

    def test_parent_replacement_preserving_source_inodes_refuses_currentness(self):
        parent = self.root / "parent"
        root = parent / "source"
        root.mkdir(parents=True)
        (root / "input").write_bytes(b"original")
        census = capture_retained_layout_partition(
            root,
            framework_files=(),
            budget=self.budget,
            maximum_metadata_bytes=32 * 1024**2,
        )
        parent_inode, root_inode = parent.stat().st_ino, root.stat().st_ino
        parent.rename(self.root / "old-parent")
        parent.mkdir()
        (self.root / "old-parent/source").rename(root)
        self.assertNotEqual(parent.stat().st_ino, parent_inode)
        self.assertEqual(root.stat().st_ino, root_inode)
        with self.assertRaises(RetainedLayoutError):
            census.require_unchanged()

    def test_identical_byte_replacement_changes_physical_census_identity(self):
        root = self.root / "tree"
        root.mkdir()
        source = root / "input"
        source.write_bytes(b"original")

        def capture():
            return capture_retained_layout_partition(
                root,
                framework_files=(),
                budget=self.budget,
                maximum_metadata_bytes=32 * 1024**2,
            )

        before = capture()
        source.rename(self.root / "saved")
        source.write_bytes(b"original")
        after = capture()
        self.assertEqual(before.tree.identity, after.tree.identity)
        self.assertNotEqual(before.identity, after.identity)

    def test_wide_native_node_ids_keep_exact_custody_identity_precision(self):
        self.write("source")
        census = self.capture()

        # Encoding-port control only: these immutable facts grant no authority
        # and do not assert actual native Windows or other-host execution.
        def with_inode(inode):
            original_root, entries = census.tree._physical
            root = (original_root[0], inode, *original_root[2:])
            tree = replace(census.tree, _physical=(root, entries))
            last = census._lineage[-1]
            lineage = (*census._lineage[:-1], (last[0], last[1], inode, *last[3:]))
            return replace(census, tree=tree, _lineage=lineage)

        first = with_inode(2**100)
        second = with_inode(2**100 + 1)
        self.assertEqual(first.identity, first.identity)
        self.assertNotEqual(first.identity, second.identity)
        self.assertNotEqual(first.identity, census.identity)
