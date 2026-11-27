"""Actual original-tree closure, including ancestors outside the file inventory."""

import inspect
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    capture_directory_ancestries,
)
from literate_ai.adapters import directory_artifacts as artifacts
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    capture_materialized_file_stamps,
    capture_materialized_files,
    require_materialized_files,
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

    def test_opt_in_release_is_idempotent_and_clears_guard_and_move_cells(self):
        close, release = capture_materialized_files(
            self.root, self.files, _with_release=True
        )
        ancestry = inspect.getclosurevars(close).nonlocals["ancestors_current"]
        close()
        release()
        release()
        with self.assertRaisesRegex(ValueError, "retired"):
            close()
        cells = inspect.getclosurevars(close).nonlocals
        for name in ("stamps", "directory_stamps", "ancestors_current"):
            self.assertIsNone(cells[name])
        moved = inspect.getclosurevars(close.after_owned_move).nonlocals
        for name in (
            "root",
            "stamps",
            "directory_stamps",
            "top_names",
            "transfer_token",
        ):
            self.assertIsNone(moved[name])
        self.assertIsNone(inspect.getclosurevars(ancestry).nonlocals["original"])

    def test_release_selection_requires_exact_bool_before_filesystem_access(self):
        for choice in (None, 0, 1, "yes"):
            with self.subTest(choice=choice):
                with self.assertRaises(TypeError):
                    capture_materialized_files(None, None, _with_release=choice)
                with self.assertRaises(TypeError):
                    capture_directory_ancestries(None, _with_release=choice)

    def test_opt_in_cannot_move_without_descendant_release_ownership(self):
        close, release = capture_materialized_files(
            self.root, self.files, _with_release=True
        )
        with self.assertRaisesRegex(ValueError, "cannot move"):
            close.after_owned_move(self.parent / "unused", expected_parent=(0, 0, 0))
        close()
        release()
        self.assertTrue(self.root.is_dir())

    def test_retained_file_guard_failure_releases_original_metadata(self):
        close, release = capture_materialized_files(
            self.root, self.files, _with_release=True
        )
        (self.root / "value.js").write_bytes(b"other\n")
        retained = None
        try:
            close()
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        release()
        self.assertIsNotNone(retained.__traceback__)
        self.assertIsNone(inspect.getclosurevars(close).nonlocals["stamps"])
        frame = retained.__traceback__
        while frame is not None:
            if frame.tb_frame.f_code.co_name == "require_snapshot":
                for name in ("directory", "path", "expected"):
                    self.assertIsNone(frame.tb_frame.f_locals[name])
            frame = frame.tb_next

    def test_opt_in_ancestry_failure_is_sticky_and_releases_after_restoration(self):
        self.parent.chmod(0o700)
        close, release = capture_directory_ancestries(
            (self.parent,), _with_release=True
        )
        self.parent.chmod(0o750)
        retained = None
        try:
            close()
        except UnsafeFilesystemPathError as error:
            retained = error
        finally:
            self.parent.chmod(0o700)
        self.assertIsNotNone(retained)
        with self.assertRaisesRegex(UnsafeFilesystemPathError, "retired"):
            close()
        release()
        release()
        self.assertIsNone(inspect.getclosurevars(close).nonlocals["original"])
        self.assertIsNotNone(retained.__traceback__)
        frame = retained.__traceback__
        while frame is not None:
            if frame.tb_frame.f_code.co_name == "close":
                for name in ("path", "expected"):
                    self.assertIsNone(frame.tb_frame.f_locals[name])
            frame = frame.tb_next

    def test_materialized_construction_failure_releases_completed_ancestry(self):
        capture = artifacts.capture_directory_ancestries
        observations = []

        def observe(*args, **kwargs):
            guard, release = capture(*args, **kwargs)
            observations.append(guard)
            return guard, release

        failure = ValueError("original materialization read failure")
        retained = None
        with (
            mock.patch.object(
                artifacts, "capture_directory_ancestries", side_effect=observe
            ),
            mock.patch.object(
                artifacts, "_read_materialized_file", side_effect=failure
            ),
        ):
            try:
                capture_materialized_files(self.root, self.files, _with_release=True)
            except ValueError as error:
                retained = error
        self.assertIs(retained, failure)
        self.assertEqual(len(observations), 1)
        self.assertIsNone(inspect.getclosurevars(observations[0]).nonlocals["original"])

    def test_failed_ancestry_construction_clears_partial_factory_frames(self):
        retained = None
        try:
            capture_directory_ancestries(
                (self.parent, self.parent / "missing"), _with_release=True
            )
        except FileNotFoundError as error:
            retained = error
        self.assertIsNotNone(retained)
        frame = retained.__traceback__
        while frame is not None:
            name = frame.tb_frame.f_code.co_name
            if name == "capture_directory_ancestries":
                for field in ("paths", "directories", "rows", "path", "directory"):
                    self.assertIsNone(frame.tb_frame.f_locals[field])
            if name == "identity":
                self.assertIsNone(frame.tb_frame.f_locals["path"])
                self.assertIsNone(frame.tb_frame.f_locals["value"])
            frame = frame.tb_next

    def test_retained_byte_failure_tracebacks_release_original_source(self):
        for capture in (
            capture_materialized_files,
            capture_materialized_file_stamps,
            require_materialized_files,
        ):
            with self.subTest(capture=capture.__name__):
                content = bytes(bytearray(b"exact\n"))
                baseline = sys.getrefcount(content)
                files = (DirectoryExportFile("value.js", content, 0o644),)
                (self.root / "value.js").write_bytes(b"wrong\n")
                retained = None
                try:
                    capture(self.root, files)
                except ValueError as error:
                    retained = error
                self.assertIsNotNone(retained)
                self.assertIsNotNone(retained.__traceback__)
                del files
                self.assertEqual(sys.getrefcount(content), baseline)

    def test_partial_snapshot_failure_releases_prior_source_with_traceback_kept(self):
        content = bytes(bytearray(b"exact\n"))
        baseline = sys.getrefcount(content)
        files = (
            DirectoryExportFile("value.js", content, 0o644),
            DirectoryExportFile("invalid.js", bytearray(b"invalid"), 0o644),
        )
        retained = None
        try:
            capture_materialized_files(self.root, files)
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.assertIsNotNone(retained.__traceback__)
        del files
        self.assertEqual(sys.getrefcount(content), baseline)

    def test_original_cancellation_keeps_identity_without_retaining_source(self):
        content = bytes(bytearray(b"exact\n"))
        baseline = sys.getrefcount(content)
        files = (DirectoryExportFile("value.js", content, 0o644),)
        failure = KeyboardInterrupt("original file-read cancellation")
        retained = None
        with mock.patch(
            "literate_ai.adapters.directory_artifacts.os.open", side_effect=failure
        ):
            try:
                capture_materialized_files(self.root, files)
            except KeyboardInterrupt as error:
                retained = error
        self.assertIs(retained, failure)
        self.assertIsNotNone(retained.__traceback__)
        del files
        self.assertEqual(sys.getrefcount(content), baseline)

    def test_successful_transferable_guard_retains_metadata_without_source(self):
        content = bytes(bytearray(b"exact\n"))
        baseline = sys.getrefcount(content)
        files = (DirectoryExportFile("value.js", content, 0o644),)
        close = capture_materialized_files(self.root, files)
        del files
        close()
        self.assertTrue(callable(close.after_owned_move))
        self.assertEqual(sys.getrefcount(content), baseline)

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
