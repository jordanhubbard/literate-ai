"""Finite original artifact stamps close late callbacks without adopting drift."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    capture_materialized_files,
    require_materialized_files,
)


class MaterializedFileCustodyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve()
        self.root = self.parent / "artifact"
        self.root.mkdir()
        self.path = self.root / "nested/api.js"
        self.path.parent.mkdir()
        self.path.write_bytes(b"exports.value = 3;\n")
        self.mode = 0o666 if os.name == "nt" else 0o644
        self.path.chmod(self.mode)
        self.files = (
            DirectoryExportFile("nested/api.js", self.path.read_bytes(), self.mode),
        )

    def test_existing_wrapper_returns_none(self):
        self.assertIsNone(require_materialized_files(self.root, self.files))

    def test_unsupported_change_timestamps_refuse_long_lived_custody(self):
        with patch("literate_ai.adapters.directory_artifacts.os.name", "nt"):
            with self.assertRaisesRegex(ValueError, "POSIX change timestamps"):
                capture_materialized_files(self.root, self.files)

    @unittest.skipUnless(os.name == "posix", "requires POSIX change timestamps")
    def test_guard_retains_original_stamps(self):
        guard = capture_materialized_files(self.root, self.files)
        self.assertIsNone(guard())
        self.assertIsNone(guard())

    @unittest.skipUnless(os.name == "posix", "requires POSIX change timestamps")
    def test_late_changed_bytes_cannot_be_adopted_even_after_restore(self):
        guard = capture_materialized_files(self.root, self.files)
        self.path.write_bytes(b"changed")
        with self.assertRaises(ValueError):
            guard()
        self.path.write_bytes(self.files[0].content)
        with self.assertRaises(ValueError):
            guard()

    @unittest.skipUnless(os.name == "posix", "requires POSIX change timestamps")
    def test_same_size_rewrite_with_restored_mtime_is_refused(self):
        guard = capture_materialized_files(self.root, self.files)
        before = self.path.stat()
        changed = self.files[0].content.replace(b"3", b"4")
        self.assertEqual(len(changed), before.st_size)
        self.path.write_bytes(changed)
        os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.path.stat().st_mtime_ns, before.st_mtime_ns)
        with self.assertRaises(ValueError):
            guard()

    @unittest.skipUnless(os.name == "posix", "requires POSIX change timestamps")
    def test_identical_copy_of_root_or_file_does_not_preserve_custody(self):
        for kind in ("root", "file"):
            with self.subTest(kind=kind):
                guard = capture_materialized_files(self.root, self.files)
                original = self.root if kind == "root" else self.path
                backup = self.parent / (kind + "-original")
                original.rename(backup)
                try:
                    if kind == "root":
                        shutil.copytree(backup, original)
                    else:
                        shutil.copy2(backup, original)
                    with self.assertRaises(ValueError):
                        guard()
                finally:
                    if kind == "root":
                        shutil.rmtree(original)
                    else:
                        original.unlink()
                    backup.rename(original)

    @unittest.skipUnless(os.name == "posix", "requires POSIX change timestamps")
    def test_added_then_removed_namespace_does_not_restore_original_guard(self):
        guard = capture_materialized_files(self.root, self.files)
        extra = self.path.parent / "foreign.js"
        extra.write_bytes(b"foreign")
        with self.assertRaises(ValueError):
            guard()
        extra.unlink()
        with self.assertRaises(ValueError):
            guard()

    @unittest.skipIf(os.name == "nt", "POSIX mode bits")
    def test_late_mode_and_link_changes_are_refused(self):
        guard = capture_materialized_files(self.root, self.files)
        self.path.chmod(0o755)
        with self.assertRaises(ValueError):
            guard()
        self.path.chmod(self.mode)
        guard = capture_materialized_files(self.root, self.files)
        link = self.parent / "hardlink"
        os.link(self.path, link)
        with self.assertRaises(ValueError):
            guard()
