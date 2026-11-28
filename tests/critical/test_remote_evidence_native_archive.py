"""Real local archive custody; supported native platforms qualify separately."""

from __future__ import annotations

import errno
import hashlib
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import remote_execution as remote


class NativeEvidenceArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        self.leaf = self.source / "payload.bin"
        self.leaf.write_bytes(b"original payload\n")
        self.output = self.base / "result.tar.gz"

    def write(self, **kwargs):
        return remote._write_deterministic_tar_gz(self.source, self.output, **kwargs)

    def test_00_preexisting_fixed_partial_is_preserved(self):
        partial = self.output.with_name(self.output.name + ".partial")
        partial.write_bytes(b"another writer owns this\n")
        identity = partial.stat().st_ino
        result = self.write()
        self.assertEqual(partial.read_bytes(), b"another writer owns this\n")
        self.assertEqual(partial.stat().st_ino, identity)
        self.assertEqual(
            result.digest, hashlib.sha256(self.output.read_bytes()).hexdigest()
        )

    def test_existing_final_is_never_replaced(self):
        self.output.write_bytes(b"retained completed bundle\n")
        identity = self.output.stat().st_ino
        with self.assertRaises((ValueError, OSError, RuntimeError)):
            self.write()
        self.assertEqual(self.output.read_bytes(), b"retained completed bundle\n")
        self.assertEqual(self.output.stat().st_ino, identity)

    def test_alias_is_rejected_before_target_following_metadata(self):
        alias = self.source / "foreign"
        outside = self.base / "private"
        outside.mkdir()
        (outside / "data").write_bytes(b"private fixture; do not read\n")
        try:
            alias.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            if os.name == "nt":
                self.skipTest(f"native symlink privilege unavailable: {error}")
            raise
        original = os.stat

        def guarded(path, *args, **kwargs):
            if (
                not isinstance(path, int)
                and Path(path) == alias
                and kwargs.get("follow_symlinks", True)
            ):
                raise AssertionError("archive followed an unadmitted alias")
            return original(path, *args, **kwargs)

        with patch.object(os, "stat", guarded):
            with self.assertRaises((ValueError, OSError, RuntimeError)):
                self.write()
        self.assertFalse(self.output.exists())

    def test_deterministic_headers_and_real_consumer(self):
        nested = self.source / "child"
        nested.mkdir()
        executable = nested / "run"
        executable.write_bytes(b"binary\0" * 200000)
        executable.chmod(0o751)
        one = self.write()
        self.output = self.base / "second.tar.gz"
        os.utime(self.leaf, (17, 17))
        two = self.write()
        self.assertEqual(one, two)
        with tarfile.open(self.output, "r:gz") as archive:
            self.assertEqual(archive.getnames(), ["child/run", "payload.bin"])
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertEqual((member.uid, member.gid, member.mtime), (0, 0, 0))
                self.assertEqual((member.uname, member.gname), ("", ""))
                self.assertEqual(
                    archive.extractfile(member).read(),
                    (self.source / member.name).read_bytes(),
                )
            self.assertEqual(archive.getmember("child/run").mode, 0o755)
            self.assertEqual(archive.getmember("payload.bin").mode, 0o644)

    def test_source_replacement_during_streaming_refuses_and_preserves_it(self):
        inode = self.leaf.stat().st_ino
        original, changed = os.read, []

        def replacing(descriptor, count):
            value = original(descriptor, count)
            if value and os.fstat(descriptor).st_ino == inode and not changed:
                self.leaf.rename(self.source / "retained-original.bin")
                self.leaf.write_bytes(b"foreign replacement\n")
                changed.append(self.leaf.stat().st_ino)
            return value

        with patch.object(os, "read", replacing):
            with self.assertRaises((ValueError, OSError, RuntimeError)):
                self.write()
        self.assertEqual(len(changed), 1)
        self.assertEqual(self.leaf.read_bytes(), b"foreign replacement\n")
        self.assertEqual(self.leaf.stat().st_ino, changed[0])
        self.assertFalse(self.output.exists())

    def test_captured_ledger_rejects_changed_bytes_before_publication(self):
        expected = {"payload.bin": (self.leaf.stat().st_size, "0" * 64, False)}
        with self.assertRaises((ValueError, OSError, RuntimeError)):
            self.write(expected=expected)
        self.assertFalse(self.output.exists())

    def test_concurrent_final_is_preserved_at_publication(self):
        original, created = os.link, []

        def raced(source, destination, *args, **kwargs):
            if not created:
                self.output.write_bytes(b"concurrent publisher\n")
                created.append(self.output.stat().st_ino)
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "link", raced):
            with self.assertRaises((ValueError, OSError, RuntimeError)):
                self.write()
        self.assertEqual(len(created), 1)
        self.assertEqual(self.output.stat().st_ino, created[0])
        self.assertEqual(self.output.read_bytes(), b"concurrent publisher\n")

    def test_replaced_partial_is_preserved_and_never_accepted(self):
        original, foreign = os.link, []

        def raced(source, destination, *args, **kwargs):
            path = self.base / Path(source).name
            path.rename(path.with_suffix(".retained"))
            path.write_bytes(b"foreign partial\n")
            foreign.append((path, path.stat().st_ino))
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "link", raced):
            with self.assertRaises((ValueError, OSError, RuntimeError)):
                self.write()
        self.assertEqual(len(foreign), 1)
        path, inode = foreign[0]
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_bytes(), b"foreign partial\n")

    def test_byte_budget_refuses_before_payload_or_output(self):
        from literate_ai.adapters.evidence_files import visit_evidence_files

        with patch.object(
            os, "read", side_effect=AssertionError("unadmitted payload read")
        ):
            with self.assertRaises(ValueError):
                visit_evidence_files(
                    self.source,
                    lambda *args: self.fail("unadmitted consumer"),
                    maximum_files=1,
                    maximum_bytes=1,
                )
        self.assertFalse(self.output.exists())

    def test_corrupted_archive_write_is_not_published(self):
        original = os.write

        def corrupt(descriptor, content):
            value = bytes(content)
            return original(descriptor, bytes([value[0] ^ 1]) + value[1:])

        with patch.object(os, "write", corrupt):
            with self.assertRaises((ValueError, OSError, RuntimeError)):
                self.write()
        self.assertFalse(self.output.exists())
        self.assertTrue(list(self.base.glob(".e-*")))

    def test_parent_replacement_preserves_foreign_directory(self):
        if os.name != "posix":
            self.skipTest("POSIX directory-FD substitution")
        parent = self.base / "output"
        parent.mkdir()
        self.output = parent / self.output.name
        retained = self.base / "retained-output"
        original, changed = os.link, []

        def replacing(source, destination, *args, **kwargs):
            parent.rename(retained)
            parent.mkdir()
            sentinel = parent / "private.txt"
            sentinel.write_bytes(b"foreign directory\n")
            changed.append(sentinel.stat().st_ino)
            return original(source, destination, *args, **kwargs)

        with patch.object(os, "link", replacing):
            with self.assertRaises((ValueError, OSError, RuntimeError)):
                self.write()
        self.assertEqual(len(changed), 1)
        self.assertFalse(self.output.exists())
        self.assertEqual((parent / "private.txt").stat().st_ino, changed[0])
        self.assertEqual((parent / "private.txt").read_bytes(), b"foreign directory\n")
        self.assertTrue(list(retained.iterdir()))

    def test_native_descriptors_close_on_success_and_failure(self):
        if os.name != "posix":
            self.skipTest("POSIX native descriptor accounting")
        original = os.open
        for fail in (False, True):
            with self.subTest(fail=fail):
                descriptors = []
                self.output = self.base / ("fail.tar.gz" if fail else "ok.tar.gz")

                def opening(*args, _owned=descriptors, **kwargs):
                    descriptor = original(*args, **kwargs)
                    _owned.append(descriptor)
                    return descriptor

                with patch.object(os, "open", opening):
                    if fail:
                        with patch.object(
                            os, "link", side_effect=OSError("publication fixture")
                        ):
                            with self.assertRaises(OSError):
                                self.write()
                    else:
                        self.write()
                self.assertTrue(descriptors)
                for descriptor in set(descriptors):
                    with self.assertRaises(OSError) as error:
                        os.fstat(descriptor)
                    self.assertEqual(error.exception.errno, errno.EBADF)

    def test_late_native_leaf_alias_refuses(self):
        if os.name != "posix":
            self.skipTest("POSIX descriptor-relative open control")
        private = self.base / "private.bin"
        private.write_bytes(b"private fixture\n")
        original, changed = os.open, []

        def replacing(path, flags, *args, **kwargs):
            if (
                path == self.leaf.name
                and not flags & (os.O_DIRECTORY | os.O_CREAT)
                and not changed
            ):
                self.leaf.rename(self.source / "retained.bin")
                self.leaf.symlink_to(private)
                changed.append(True)
            return original(path, flags, *args, **kwargs)

        with patch.object(os, "open", replacing):
            with self.assertRaises((ValueError, OSError, RuntimeError)):
                self.write()
        self.assertEqual(changed, [True])
        self.assertFalse(self.output.exists())
        self.assertEqual(private.read_bytes(), b"private fixture\n")
