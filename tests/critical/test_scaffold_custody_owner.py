"""Native creator custody refuses foreign postimages and replayed writers."""

from __future__ import annotations

import contextvars
import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai._atomic_publication import publish_atomic_file_if_scoped
from literate_ai.adapters import scaffold_custody as custody


class ScaffoldCustodyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_real_creators_replace_owned_file_then_retire_only_owned_outputs(self):
        original = self.root / "original"
        original.write_bytes(b"application")
        inode = original.stat().st_ino
        with custody.scaffold_custody(self.root) as owner:
            file = self.root / "litai/nested/value"
            custody.scaffold_write_bytes(file, b"first")
            mode = file.stat().st_mode
            publish_atomic_file_if_scoped(file, b"second", preserve_mode=True)
            self.assertEqual(file.read_bytes(), b"second")
            self.assertEqual(file.stat().st_mode, mode)
            owner.rollback()
            with self.assertRaises(custody.ScaffoldCustodyError):
                custody.scaffold_write_bytes(self.root / "later", b"denied")
        self.assertEqual(list(self.root.iterdir()), [original])
        self.assertEqual(original.stat().st_ino, inode)

    def test_private_symlink_and_target_are_preserved_without_reading_target(self):
        outside = self.root / "outside"
        outside.write_bytes(b"private target")
        with custody.scaffold_custody(self.root) as owner:
            file = self.root / "litai/value"
            custody.scaffold_write_bytes(file, b"owned")
            private = file.parent / "private"
            private.symlink_to(outside)
            inode = private.lstat().st_ino
            with self.assertRaises(custody.ScaffoldCustodyError):
                owner.rollback()
            self.assertEqual(file.read_bytes(), b"owned")
            self.assertEqual(private.lstat().st_ino, inode)
        self.assertEqual(outside.read_bytes(), b"private target")

    def test_equal_byte_foreign_replacement_cannot_be_written_or_retired(self):
        with custody.scaffold_custody(self.root) as owner:
            file = self.root / "litai/value"
            custody.scaffold_write_bytes(file, b"same")
            retained = self.root / "retained"
            file.rename(retained)
            file.write_bytes(b"same")
            inode = file.stat().st_ino
            with self.assertRaises(custody.ScaffoldCustodyError):
                custody.scaffold_write_bytes(file, b"denied")
            with self.assertRaises(custody.ScaffoldCustodyError):
                owner.rollback()
            self.assertEqual(file.stat().st_ino, inode)
            self.assertEqual(file.read_bytes(), retained.read_bytes())

    def test_changed_parent_is_not_followed_or_adopted(self):
        with custody.scaffold_custody(self.root) as owner:
            parent = self.root / "litai"
            custody.scaffold_mkdir(parent)
            retained = self.root / "retained"
            parent.rename(retained)
            parent.mkdir()
            with self.assertRaises(custody.ScaffoldCustodyError):
                custody.scaffold_write_bytes(parent / "denied", b"denied")
            with self.assertRaises(custody.ScaffoldCustodyError):
                owner.rollback()
            self.assertEqual(list(parent.iterdir()), [])
            self.assertTrue(retained.is_dir())

    def test_existing_foreign_directory_is_not_adopted_by_exist_ok(self):
        parent = self.root / "litai"
        parent.mkdir()
        inode = parent.stat().st_ino
        with custody.scaffold_custody(self.root) as owner:
            with self.assertRaises(FileExistsError):
                custody.scaffold_mkdir(parent, parents=True, exist_ok=True)
            owner.rollback()
        self.assertEqual(parent.stat().st_ino, inode)

    def test_partial_native_write_is_retired_by_its_original_creator(self):
        write = os.write
        calls = []

        def reject(descriptor, payload):
            calls.append(descriptor)
            if len(calls) == 1:
                return write(descriptor, payload[:3])
            raise RuntimeError("original partial writer rejection")

        with custody.scaffold_custody(self.root) as owner:
            with self.assertRaisesRegex(RuntimeError, "original partial"):
                with patch.object(custody.os, "write", reject):
                    custody.scaffold_write_bytes(self.root / "value", b"payload")
            self.assertEqual(len(list(self.root.iterdir())), 1)
            owner.rollback()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_primary_write_rejection_survives_closure_refusal(self):
        original = RuntimeError("original writer rejection")
        entry = custody._entry

        def refuse(access, parts):
            if parts[-1].startswith(".s-"):
                raise OSError("controlled writer closure refusal")
            return entry(access, parts)

        with custody.scaffold_custody(self.root) as owner:
            with self.assertRaises(RuntimeError) as caught:
                with (
                    patch.object(custody.os, "write", side_effect=original),
                    patch.object(custody, "_entry", refuse),
                ):
                    custody.scaffold_write_bytes(self.root / "value", b"payload")
            self.assertIs(caught.exception, original)
            self.assertTrue(any("closure" in note for note in original.__notes__))
            with self.assertRaises(custody.ScaffoldCustodyError):
                custody.scaffold_write_bytes(self.root / "later", b"denied")
            with self.assertRaises(custody.ScaffoldCustodyError):
                owner.rollback()
        self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_copied_closed_context_foreign_process_and_wrong_root_refuse(self):
        with custody.scaffold_custody(self.root) as owner:
            copied = copy.copy(owner)
            with self.assertRaises(custody.ScaffoldCustodyError):
                copied.rollback()
            with self.assertRaises(custody.ScaffoldCustodyError):
                custody.current_scaffold_custody(self.root.parent)
            with patch.object(custody.os, "getpid", return_value=os.getpid() + 1):
                with self.assertRaises(custody.ScaffoldCustodyError):
                    custody.scaffold_write_bytes(self.root / "denied", b"denied")
            saved = contextvars.copy_context()
        with self.assertRaises(custody.ScaffoldCustodyError):
            owner.rollback()
        with self.assertRaises(custody.ScaffoldCustodyError):
            saved.run(custody.scaffold_write_bytes, self.root / "denied", b"denied")
        self.assertFalse((self.root / "denied").exists())

    def test_new_canonical_publication_has_private_mode(self):
        if os.name != "posix":
            self.skipTest("POSIX permission bits")
        with custody.scaffold_custody(self.root):
            file = self.root / "litai/manifest.json"
            self.assertTrue(publish_atomic_file_if_scoped(file, b"{}"))
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
