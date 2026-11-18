"""Actual original-tree closure, including ancestors outside the file inventory."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    capture_materialized_file_stamps,
    capture_materialized_files,
)
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    publish_directory_exclusive,
)


@unittest.skipUnless(os.name == "posix", "requires POSIX original file custody")
class MaterializedFileCustodyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.parent = self.base / "parent"
        self.root = self.parent / "sdk"
        self.root.mkdir(parents=True)
        path = self.root / "value.js"
        path.write_bytes(b"exact\n")
        path.chmod(0o644)
        self.files = (DirectoryExportFile("value.js", b"exact\n", 0o644),)

    def test_original_guard_rejects_ancestor_symlink_to_same_tree(self):
        close = capture_materialized_files(self.root, self.files)
        retained = self.base / "retained"
        self.parent.rename(retained)
        self.parent.symlink_to(retained, target_is_directory=True)
        try:
            with self.assertRaisesRegex(ValueError, "directory changed"):
                close()
        finally:
            self.parent.unlink()
            retained.rename(self.parent)

    def test_original_guard_rejects_ancestor_mode_change(self):
        self.parent.chmod(0o700)
        close = capture_materialized_files(self.root, self.files)
        self.parent.chmod(0o750)
        try:
            with self.assertRaisesRegex(ValueError, "directory changed"):
                close()
        finally:
            self.parent.chmod(0o700)

    def test_unrelated_ancestor_sibling_writes_remain_allowed(self):
        close = capture_materialized_files(self.root, self.files)
        (self.parent / "sibling-file").write_bytes(b"unrelated")
        (self.parent / "sibling-directory").mkdir()
        close()

    def move_original(self, close):
        destination = self.parent / "installed"
        parent = directory_node(self.parent)
        publish_directory_exclusive(
            self.root,
            destination,
            expected_source=directory_node(self.root),
            expected_parent=parent,
        )
        return destination, close.after_owned_move(destination, expected_parent=parent)

    def test_original_metadata_transfers_once_after_actual_exclusive_move(self):
        close = capture_materialized_files(self.root, self.files)
        parent = directory_node(self.parent)
        destination, transferred = self.move_original(close)
        transferred()
        with self.assertRaisesRegex(ValueError, "already consumed"):
            close.after_owned_move(destination, expected_parent=parent)
        path = destination / "value.js"
        before = path.stat()
        path.write_bytes(path.read_bytes())
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "changed before inventory close"):
            transferred()

    def test_transfer_cannot_adopt_foreign_root_child_with_restored_mtime(self):
        close = capture_materialized_files(self.root, self.files)
        destination = self.parent / "installed"
        parent = directory_node(self.parent)
        publish_directory_exclusive(
            self.root,
            destination,
            expected_source=directory_node(self.root),
            expected_parent=parent,
        )
        before = destination.stat()
        foreign = destination / "foreign"
        foreign.write_bytes(b"preserve this peer")
        os.utime(destination, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "foreign child|root changed"):
            close.after_owned_move(destination, expected_parent=parent)
        self.assertEqual(foreign.read_bytes(), b"preserve this peer")

    def test_transfer_cannot_adopt_equal_bytes_from_another_root(self):
        close = capture_materialized_files(self.root, self.files)
        destination = self.parent / "copied-root"
        shutil.copytree(self.root, destination)
        shutil.rmtree(self.root)
        with self.assertRaisesRegex(ValueError, "root changed"):
            close.after_owned_move(
                destination, expected_parent=directory_node(self.parent)
            )
        self.assertEqual((destination / "value.js").read_bytes(), b"exact\n")

    def test_occupied_destination_is_preserved_without_transfer(self):
        close = capture_materialized_files(self.root, self.files)
        destination = self.parent / "installed"
        destination.mkdir()
        (destination / "foreign").write_bytes(b"preserve")
        original = directory_node(destination)
        with self.assertRaises(FileExistsError):
            publish_directory_exclusive(
                self.root,
                destination,
                expected_source=directory_node(self.root),
                expected_parent=directory_node(self.parent),
            )
        close()
        self.assertEqual(directory_node(destination), original)
        self.assertEqual((destination / "foreign").read_bytes(), b"preserve")

    def test_selected_file_guard_allows_later_owned_siblings(self):
        close = capture_materialized_file_stamps(self.root, self.files)
        (self.root / "later-resource").write_bytes(b"owned sibling")
        close()
        path = self.root / "value.js"
        before = path.stat()
        path.write_bytes(path.read_bytes())
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, "changed before inventory close"):
            close()

    def test_selected_file_paths_cannot_escape_the_root(self):
        outside = self.parent / "outside"
        outside.write_bytes(b"outside")
        with self.assertRaises(ValueError):
            capture_materialized_file_stamps(
                self.root, (DirectoryExportFile("../outside", b"outside", 0o644),)
            )
