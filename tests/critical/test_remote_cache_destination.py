"""Fresh remote accepted-cache destinations never authorize replacing private data."""

from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import remote_execution as remote


class RemoteCacheDestinationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.build = self.root / "build"
        self.build.mkdir()
        self.cache = self.build / "accepted-source-cache"
        self.archive = self.root / "cache.tar.gz"
        with tarfile.open(self.archive, "w:gz") as archive:
            member = tarfile.TarInfo("entries/fixture.json")
            member.size = len(b"fixture bytes")
            archive.addfile(member, io.BytesIO(b"fixture bytes"))

    def refused(self, code):
        with patch.object(
            remote,
            "extract_accepted_source_cache_archive",
            wraps=remote.extract_accepted_source_cache_archive,
        ) as extract:
            with self.assertRaises(remote.RemoteExecutionError) as error:
                remote._restore_accepted_source_cache(self.build, self.archive)
            self.assertEqual(error.exception.code, code)
        extract.assert_not_called()

    def test_00_existing_directory_and_private_inode_survive(self):
        self.cache.mkdir()
        private = self.cache / "private.txt"
        private.write_bytes(b"private cache fixture")
        before = (
            self.cache.stat().st_ino,
            private.stat().st_ino,
            private.stat().st_mode,
        )
        self.refused("execution.remote_accepted_source_cache_exists")
        self.assertEqual(
            (self.cache.stat().st_ino, private.stat().st_ino, private.stat().st_mode),
            before,
        )
        self.assertEqual(private.read_bytes(), b"private cache fixture")

    def test_existing_regular_file_survives(self):
        self.cache.write_bytes(b"private regular fixture")
        inode = self.cache.stat().st_ino
        self.refused("execution.remote_accepted_source_cache_exists")
        self.assertEqual(self.cache.stat().st_ino, inode)
        self.assertEqual(self.cache.read_bytes(), b"private regular fixture")

    def test_existing_live_and_dangling_aliases_are_not_followed(self):
        target = self.root / "private-target"
        target.mkdir()
        private = target / "private.txt"
        private.write_bytes(b"private alias fixture")
        for selected in (target, self.root / "absent-target"):
            with self.subTest(dangling=selected != target):
                self.cache.symlink_to(selected, target_is_directory=True)
                inode = self.cache.lstat().st_ino
                exists = Path.exists

                def guard(path, _exists=exists):
                    if path == self.cache:
                        raise AssertionError("must not follow the existing alias")
                    return _exists(path)

                with patch.object(Path, "exists", guard):
                    self.refused("execution.remote_accepted_source_cache_exists")
                self.assertEqual(self.cache.lstat().st_ino, inode)
                self.cache.unlink()
        self.assertEqual(private.read_bytes(), b"private alias fixture")
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["private.txt"])

    def test_aliased_parent_refuses_before_creating_target_cache(self):
        self.build.rmdir()
        target = self.root / "private-parent"
        target.mkdir()
        self.build.symlink_to(target, target_is_directory=True)
        inode = self.build.lstat().st_ino
        self.refused("execution.remote_accepted_source_cache_destination_invalid")
        self.assertEqual(self.build.lstat().st_ino, inode)
        self.assertEqual(list(target.iterdir()), [])

    def test_original_fresh_destination_restores_real_archive(self):
        remote._restore_accepted_source_cache(self.build, self.archive)
        self.assertEqual(
            (self.cache / "entries/fixture.json").read_bytes(), b"fixture bytes"
        )

    def test_invalid_archive_retains_original_scoped_error_and_no_cache(self):
        self.archive.write_bytes(b"controlled invalid archive fixture")
        with self.assertRaises(remote.RemoteExecutionError) as error:
            remote._restore_accepted_source_cache(self.build, self.archive)
        self.assertEqual(
            error.exception.code, "execution.remote_accepted_source_cache_invalid"
        )
        self.assertFalse(self.cache.exists())
