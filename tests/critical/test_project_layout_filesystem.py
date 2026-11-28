"""Owned temp I/O and modeled Windows dispatch; no native Windows qualification."""

import os
import stat
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import project_layout_filesystem as io


def stamp(node):
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
        node.st_nlink,
    )


def fail(code, message):
    raise ValueError(code + ": " + message)


class MigrationFilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def read(self, path, maximum=1024):
        return io.read_migration_file(
            path, maximum_bytes=maximum, fail=fail, stamp=stamp
        )

    def test_owned_temp_binary_roundtrip_and_exclusive_create(self):
        path = self.root / "record"
        payload = b"\x00\r\n\x1a\xff"
        io.write_migration_file(path, payload, 0o600)
        before = path.stat()
        self.assertEqual(
            self.read(path),
            (
                [before.st_dev, before.st_ino, before.st_mode],
                payload,
                stat.S_IMODE(before.st_mode),
            ),
        )
        with self.assertRaises(FileExistsError):
            io.write_migration_file(path, b"replacement")
        self.assertEqual(path.read_bytes(), payload)
        io.flush_migration_directory(self.root)

    def test_owned_temp_bounds_and_hardlinks_refuse_without_changes(self):
        path = self.root / "record"
        path.write_bytes(b"abcd")
        with self.assertRaisesRegex(ValueError, "path_unsafe"):
            self.read(path, maximum=3)
        linked = self.root / "linked"
        os.link(path, linked)
        with self.assertRaisesRegex(ValueError, "path_unsafe"):
            self.read(path)
        self.assertEqual(linked.read_bytes(), b"abcd")

    @contextmanager
    def windows_model(self, *, drift=False, expire=False):
        events = []

        @contextmanager
        def namespace(path, *, read_only=False):
            events.append(("open", path, read_only))

            def current():
                events.append(("current", path))
                if expire:
                    raise ValueError("original-owner-expired")

            yield current
            current()

        observed = 0

        class Kernel:
            def open_reparse_aware(self, path, **sharing):
                events.append(("leaf", path, sharing))
                return os.open(path, os.O_RDONLY)

            def file_identity(self, descriptor):
                nonlocal observed
                observed += 1
                node = os.fstat(descriptor)
                return (
                    node.st_dev,
                    node.st_ino + int(drift and observed > 1),
                    0,
                )

            def close(self, descriptor):
                os.close(descriptor)

        with (
            patch.object(io, "_windows", return_value=True),
            patch(
                "literate_ai.adapters.qualification_workspace_namespace."
                "hold_qualification_workspace_namespace",
                namespace,
            ),
            patch("literate_ai._cache_lock._Kernel32Windows", Kernel),
            patch.dict(
                sys.modules, {"msvcrt": SimpleNamespace(get_osfhandle=lambda fd: fd)}
            ),
        ):
            yield events

    def test_modeled_windows_reads_hold_original_parent_and_leaf(self):
        path = self.root / "record"
        path.write_bytes(b"\x00\r\n\x1a")
        with self.windows_model() as events:
            self.assertEqual(self.read(path)[1], b"\x00\r\n\x1a")
        self.assertEqual(events[0], ("open", self.root, True))
        leaves = [event for event in events if event[0] == "leaf"]
        self.assertEqual(len(leaves), 2)
        self.assertTrue(
            all(
                not row[2]["share_delete"] and not row[2]["share_write"]
                for row in leaves
            )
        )

    def test_modeled_expired_owner_refuses_before_file_read(self):
        path = self.root / "record"
        path.write_bytes(b"original")
        with self.windows_model(expire=True), patch.object(io, "_read") as reader:
            with self.assertRaisesRegex(ValueError, "original-owner-expired"):
                self.read(path)
        reader.assert_not_called()
        self.assertEqual(path.read_bytes(), b"original")

    def test_modeled_windows_write_uses_writable_original_parent_and_syncs_bytes(self):
        path = self.root / "record"
        with self.windows_model() as events:
            io.write_migration_file(path, b"\r\n\x1a", 0o600)
        self.assertEqual(events[0], ("open", self.root, False))
        self.assertEqual(path.read_bytes(), b"\r\n\x1a")

    def test_modeled_windows_directory_check_never_claims_directory_fsync(self):
        with self.windows_model() as events, patch.object(io.os, "fsync") as sync:
            io.flush_migration_directory(self.root)
        sync.assert_not_called()
        self.assertEqual(events[0], ("open", self.root, True))

    def test_modeled_windows_native_identity_drift_refuses(self):
        path = self.root / "record"
        path.write_bytes(b"original")
        with self.windows_model(drift=True):
            with self.assertRaisesRegex(ValueError, "plan_stale"):
                self.read(path)
        self.assertEqual(path.read_bytes(), b"original")
