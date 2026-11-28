"""Held lifecycle bytes use their original owner, including Windows read denial."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import native_project_removal as removal
from literate_ai.projects import ProjectConfigurationStore


class NativeRemovalLockObservationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.path = self.root / "lifecycle.lock"
        self.path.write_bytes(b"\0\r\n\x1a")

    def test_owner_read_survives_second_handle_denial_and_expires(self):
        expected = removal._worktree(self.root, self.path.name)
        original_read = os.read
        descriptors = set()

        def read(descriptor, limit):
            descriptors.add(descriptor)
            return original_read(descriptor, limit)

        with removal._runtime_lock(self.path, existing_only=True) as observe:
            with (
                patch.object(
                    ProjectConfigurationStore,
                    "_read_manifest",
                    side_effect=PermissionError("held Windows byte range"),
                ),
                patch.object(removal.os, "read", side_effect=read),
            ):
                self.assertEqual(observe(), expected)
                self.assertEqual(len(descriptors), 1)
                descriptor = next(iter(descriptors))
                os.lseek(descriptor, 2, os.SEEK_SET)
                self.assertEqual(observe(), expected)
            self.assertEqual(len(descriptors), 1)
            self.assertEqual(os.lseek(descriptor, 0, os.SEEK_CUR), 2)
        with self.assertRaisesRegex(removal.NativeProjectRemovalError, "unavailable"):
            observe()
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    @unittest.skipIf(os.name == "nt", "requires POSIX replacement of an open inode")
    def test_equal_byte_replacement_is_refused_and_foreign_file_survives(self):
        content = self.path.read_bytes()
        before = self.path.stat()
        saved = self.root / "original.lock"
        with removal._runtime_lock(self.path, existing_only=True) as observe:
            self.path.rename(saved)
            self.path.write_bytes(content)
            os.chmod(self.path, before.st_mode)
            os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
            with self.assertRaisesRegex(removal.NativeProjectRemovalError, "custody"):
                observe()
            self.assertEqual(self.path.read_bytes(), content)
            self.assertEqual(saved.read_bytes(), content)

    @unittest.skipIf(os.name == "nt", "requires a POSIX concurrent writer")
    def test_growth_during_original_descriptor_read_refuses_and_preserves(self):
        original_read = os.read
        changed = False

        def read(descriptor, limit):
            nonlocal changed
            value = original_read(descriptor, limit)
            if not changed:
                changed = True
                with self.path.open("ab") as output:
                    output.write(b"foreign growth")
            return value

        with removal._runtime_lock(self.path, existing_only=True) as observe:
            with patch.object(removal.os, "read", side_effect=read):
                with self.assertRaisesRegex(
                    removal.NativeProjectRemovalError, "changed"
                ):
                    observe()
            self.assertTrue(self.path.read_bytes().endswith(b"foreign growth"))

    def test_native_identity_and_byte_ceiling_refuse_before_payload_read(self):
        with removal._runtime_lock(self.path, existing_only=True) as observe:
            with (
                patch.object(removal, "_identity_matches", return_value=False),
                patch.object(removal.os, "read") as read,
            ):
                with self.assertRaises(removal.NativeProjectRemovalError):
                    observe()
                read.assert_not_called()
        self.path.write_bytes(b"x" * (256 * 1024 + 1))
        with removal._runtime_lock(self.path, existing_only=True) as observe:
            with patch.object(removal.os, "read") as read:
                with self.assertRaises(removal.NativeProjectRemovalError):
                    observe()
                read.assert_not_called()

    def test_final_native_probe_cannot_replace_bytes_with_restored_timestamp(self):
        before = self.path.stat()
        original = removal._identity_matches
        calls = 0

        def identity(path, named, descriptor, held):
            nonlocal calls
            matched = original(path, named, descriptor, held)
            calls += 1
            if calls == 2:
                position = os.lseek(descriptor, 0, os.SEEK_CUR)
                os.lseek(descriptor, 0, os.SEEK_SET)
                os.write(descriptor, b"F" * before.st_size)
                os.lseek(descriptor, position, os.SEEK_SET)
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            return matched

        with removal._runtime_lock(self.path, existing_only=True) as observe:
            with patch.object(removal, "_identity_matches", side_effect=identity):
                with self.assertRaisesRegex(
                    removal.NativeProjectRemovalError, "changed"
                ):
                    observe()
        self.assertEqual(self.path.read_bytes(), b"F" * before.st_size)

    def test_primary_read_failure_survives_offset_restoration_failure(self):
        class Cancelled(BaseException):
            pass

        primary = Cancelled("original cancellation")
        original_seek = os.lseek
        calls = 0

        def seek(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("restore failed")
            return original_seek(*args)

        with removal._runtime_lock(self.path, existing_only=True) as observe:
            with (
                patch.object(removal.os, "lseek", side_effect=seek),
                patch.object(removal.os, "read", side_effect=primary),
            ):
                with self.assertRaises(Cancelled) as caught:
                    observe()
                self.assertIs(caught.exception, primary)

    def test_offset_restoration_failure_without_primary_is_reported(self):
        original_seek = os.lseek
        failure = OSError("restore failed")
        calls = 0

        def seek(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise failure
            return original_seek(*args)

        with removal._runtime_lock(self.path, existing_only=True) as observe:
            with patch.object(removal.os, "lseek", side_effect=seek):
                with self.assertRaises(OSError) as caught:
                    observe()
                self.assertIs(caught.exception, failure)

    def test_ambient_exception_cannot_hide_offset_restoration_failure(self):
        original_seek = os.lseek
        failure = OSError("restore failed")
        calls = 0

        def seek(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise failure
            return original_seek(*args)

        with removal._runtime_lock(self.path, existing_only=True) as observe:
            try:
                raise LookupError("unrelated caller error")
            except LookupError as ambient:
                with patch.object(removal.os, "lseek", side_effect=seek):
                    with self.assertRaises(OSError) as caught:
                        observe()
                    self.assertIs(caught.exception, failure)
                self.assertFalse(hasattr(ambient, "__notes__"))
