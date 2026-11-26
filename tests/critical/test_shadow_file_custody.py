"""Shadow metadata reads bind finite bytes, descriptors and ancestor identity."""

import os
import tempfile
import unittest
from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

from literate_ai.cli.errors import CliFailure
from literate_ai.cli.shadow import _bounded_file


class ShadowFileCustodyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.path = self.root / "metadata.json"
        self.path.write_bytes(b"original")

    def test_empty_and_exact_limit_metadata_return_exact_bytes(self):
        for content in (b"", b"original"):
            with self.subTest(size=len(content)):
                self.path.write_bytes(content)
                self.assertEqual(_bounded_file(self.path, len(content)), content)

    def test_oversize_missing_and_directory_refuse_before_open(self):
        for path, maximum in (
            (self.path, 7),
            (self.root / "missing", 8),
            (self.root, 8),
        ):
            selected = []
            real_open = os.open

            def observe_open(
                candidate,
                *args,
                _path=path,
                _selected=selected,
                _open=real_open,
                **kwargs,
            ):
                if os.fspath(candidate) == os.fspath(_path):
                    _selected.append(candidate)
                return _open(candidate, *args, **kwargs)

            with (
                self.subTest(path=path.name),
                patch("os.open", side_effect=observe_open),
            ):
                with self.assertRaises(CliFailure) as error:
                    _bounded_file(path, maximum)
                self.assertEqual(error.exception.code, "shadow.custody_invalid")
                self.assertEqual(selected, [])

    def test_growth_after_open_reads_at_most_limit_plus_one_and_closes(self):
        read = os.read
        descriptors, consumed = [], []

        def grow(descriptor, count):
            if not descriptors:
                with self.path.open("ab") as stream:
                    stream.write(b"x" * 10000)
            descriptors.append(descriptor)
            chunk = read(descriptor, count)
            consumed.append(len(chunk))
            return chunk

        with patch("os.read", side_effect=grow), self.assertRaises(CliFailure):
            _bounded_file(self.path, 8)
        self.assertLessEqual(sum(consumed), 9)
        self.assertTrue(descriptors)
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    def test_different_descriptor_with_identical_bytes_refuses(self):
        other = self.root / "other.json"
        other.write_bytes(self.path.read_bytes())
        real_open = os.open
        opened = real_open(other, os.O_RDONLY | getattr(os, "O_BINARY", 0))

        def close_owned():
            with suppress(OSError):
                os.close(opened)

        self.addCleanup(close_owned)
        selected = []

        def substitute_leaf(candidate, *args, **kwargs):
            if os.fspath(candidate) == os.fspath(self.path):
                selected.append(candidate)
                return opened
            return real_open(candidate, *args, **kwargs)

        with (
            patch("os.open", side_effect=substitute_leaf),
            self.assertRaises(CliFailure),
        ):
            _bounded_file(self.path, 8)
        self.assertEqual(selected, [self.path])
        with self.assertRaises(OSError):
            os.fstat(opened)

    def test_restored_mtime_write_after_read_refuses(self):
        before = self.path.stat()
        read = os.read
        changed = False

        def overwrite(descriptor, count):
            nonlocal changed
            content = read(descriptor, count)
            if content and not changed:
                changed = True
                self.path.write_bytes(b"modified")
                os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
            return content

        with patch("os.read", side_effect=overwrite), self.assertRaises(CliFailure):
            _bounded_file(self.path, 8)
        self.assertTrue(changed)

    def test_leaf_and_parent_symlinks_refuse(self):
        leaf = self.root / "leaf"
        parent = self.root / "parent"
        try:
            leaf.symlink_to(self.path)
            parent.symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("symbolic-link creation is unavailable")
        for path in (leaf, parent / self.path.name):
            with self.subTest(path=path.name), self.assertRaises(CliFailure):
                _bounded_file(path, 8)

    @unittest.skipIf(os.name == "nt", "open-directory replacement is POSIX-specific")
    def test_ancestor_replacement_preserving_file_inode_refuses(self):
        parent = self.root / "owned"
        parent.mkdir()
        candidate = parent / "metadata.json"
        candidate.write_bytes(b"original")
        original = candidate.stat()
        read = os.read
        changed = False

        def replace_parent(descriptor, count):
            nonlocal changed
            content = read(descriptor, count)
            if content and not changed:
                parent.rename(self.root / "old")
                parent.mkdir()
                (self.root / "old" / candidate.name).rename(candidate)
                changed = True
            return content

        real_stat, real_lstat, real_fstat = os.stat, os.lstat, os.fstat

        def stable_stat(path, *args, **kwargs):
            if path in (candidate, str(candidate)):
                return original
            return real_stat(path, *args, **kwargs)

        def stable_lstat(path, *args, **kwargs):
            if path in (candidate, str(candidate)):
                return original
            return real_lstat(path, *args, **kwargs)

        def stable_fstat(descriptor):
            observed = real_fstat(descriptor)
            if (observed.st_dev, observed.st_ino) == (original.st_dev, original.st_ino):
                return original
            return observed

        # Isolate ancestor identity: preserve all file stamps while observing
        # the real replaced directories and unchanged file bytes/inode.
        with (
            patch("os.read", side_effect=replace_parent),
            patch("os.stat", side_effect=stable_stat),
            patch("os.lstat", side_effect=stable_lstat),
            patch("os.fstat", side_effect=stable_fstat),
            self.assertRaises(CliFailure),
        ):
            _bounded_file(candidate, 8)
        self.assertTrue(changed)
        self.assertEqual(candidate.stat().st_ino, original.st_ino)
