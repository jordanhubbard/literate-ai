"""Owned-temp evidence IO controls; Windows API composition is modeled on POSIX."""

from __future__ import annotations

import errno
import hashlib
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import remote_execution as remote


class EvidenceNativeReadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.source = self.base / "source"
        self.source.mkdir()
        self.output = self.base / "output"
        self.files, self.totals = [], [0]

    def copy(self, source=None):
        remote._copy_evidence_tree(
            self.source if source is None else source,
            self.output,
            "object/cache",
            files=self.files,
            totals=self.totals,
        )

    def symlink(self, path, target):
        try:
            path.symlink_to(target, target_is_directory=target.is_dir())
        except OSError as error:
            if os.name == "nt":
                self.skipTest(f"native symlink privilege unavailable: {error}")
            raise

    def deny_target_stat(self, alias):
        original = os.stat

        def guarded(path, *args, **kwargs):
            if not isinstance(path, int):
                value = Path(path)
                if (value == alias and kwargs.get("follow_symlinks", True)) or (
                    value != alias and value.is_relative_to(alias)
                ):
                    raise AssertionError("target-following evidence probe")
            return original(path, *args, **kwargs)

        return patch.object(os, "stat", guarded)

    def test_alias_root_refuses_before_target_following_stat(self):
        alias = self.base / "alias"
        self.symlink(alias, self.source)
        with self.deny_target_stat(alias):
            with self.assertRaises(remote.RemoteExecutionError):
                self.copy(alias)
        self.assertFalse(self.output.exists())

    def test_child_directory_alias_refuses_before_payload_copy(self):
        (self.source / "a.txt").write_bytes(b"known source\n")
        outside = self.base / "owned-private"
        outside.mkdir()
        (outside / "not-admitted.txt").write_bytes(b"private fixture; never read\n")
        alias = self.source / "z-alias"
        self.symlink(alias, outside)
        with self.deny_target_stat(alias):
            with self.assertRaises(remote.RemoteExecutionError):
                self.copy()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.files, [])

    def test_regular_large_stream_and_single_file_preserve_bytes_and_modes(self):
        content = b"x" * (2 * 1024 * 1024 + 17)
        file = self.source / "program.bin"
        file.write_bytes(content)
        file.chmod(0o751)
        self.copy(file)
        self.assertEqual(self.totals, [len(content)])
        self.assertEqual(len(self.files), 1)
        self.assertTrue(self.files[0].executable)
        self.assertEqual(
            self.files[0].identity.uri, "sha256:" + hashlib.sha256(content).hexdigest()
        )
        self.assertEqual(
            (self.output / "object/cache/program.bin").read_bytes(), content
        )
        self.assertEqual(file.read_bytes(), content)

    def test_budget_refuses_before_any_payload_read(self):
        (self.source / "payload.bin").write_bytes(b"12345678")
        with (
            patch.object(remote, "_MAX_EVIDENCE_BYTES", 7),
            patch.object(
                os,
                "read",
                side_effect=AssertionError("payload read before budget admission"),
            ),
        ):
            with self.assertRaises(remote.RemoteExecutionError) as error:
                self.copy()
        self.assertEqual(error.exception.code, "execution.remote_evidence_too_large")
        self.assertFalse(self.output.exists())

    def test_late_leaf_alias_is_not_followed(self):
        if os.name != "posix":
            self.skipTest("POSIX descriptor-relative open interception")
        source = self.source / "payload.bin"
        source.write_bytes(b"original\n")
        outside = self.base / "private-fixture.bin"
        outside.write_bytes(b"never read substituted fixture\n")
        original, changed = os.open, []

        def replacing(path, flags, *args, **kwargs):
            if (
                path == source.name
                and not flags & (os.O_CREAT | os.O_DIRECTORY)
                and not changed
            ):
                source.rename(source.with_name("original.bin"))
                source.symlink_to(outside)
                changed.append(True)
            return original(path, flags, *args, **kwargs)

        with patch.object(os, "open", replacing):
            with self.assertRaises(remote.RemoteExecutionError):
                self.copy()
        self.assertEqual(changed, [True])
        self.assertEqual(self.files, [])
        self.assertEqual(outside.read_bytes(), b"never read substituted fixture\n")

    def test_source_replacement_during_streaming_is_preserved(self):
        source = self.source / "payload.bin"
        source.write_bytes(b"original bytes\n")
        inode = source.stat().st_ino
        original, changed = os.read, []

        def replacing(descriptor, count):
            value = original(descriptor, count)
            if value and os.fstat(descriptor).st_ino == inode and not changed:
                source.rename(source.with_name("original.bin"))
                source.write_bytes(b"foreign content\n")
                changed.append(source.stat().st_ino)
            return value

        with patch.object(os, "read", replacing):
            with self.assertRaises(remote.RemoteExecutionError):
                self.copy()
        self.assertEqual(len(changed), 1)
        self.assertEqual(source.stat().st_ino, changed[0])
        self.assertEqual(source.read_bytes(), b"foreign content\n")
        self.assertEqual(self.files, [])

    def test_changed_output_bytes_are_rejected(self):
        (self.source / "payload.bin").write_bytes(b"expected bytes\n")
        original = os.write

        def corrupt(descriptor, content):
            value = bytes(content)
            return original(descriptor, bytes([value[0] ^ 1]) + value[1:])

        with patch.object(os, "write", corrupt):
            with self.assertRaises(remote.RemoteExecutionError):
                self.copy()
        self.assertEqual(self.files, [])

    def test_hardlink_paths_remain_regular_and_charge_each_path(self):
        first = self.source / "a.bin"
        first.write_bytes(b"data")
        os.link(first, self.source / "b.bin")
        self.copy()
        self.assertEqual(len(self.files), 2)
        self.assertEqual(self.totals, [8])
        self.assertEqual(self.files[0].identity, self.files[1].identity)

    def test_all_original_descriptors_close_after_success(self):
        if os.name != "posix":
            self.skipTest("POSIX descriptor accounting")
        (self.source / "a.bin").write_bytes(b"data")
        original, descriptors = os.open, []

        def opening(*args, **kwargs):
            value = original(*args, **kwargs)
            descriptors.append(value)
            return value

        with patch.object(os, "open", opening):
            self.copy()
        self.assertTrue(descriptors)
        for descriptor in set(descriptors):
            with self.assertRaises(OSError) as error:
                os.fstat(descriptor)
            self.assertEqual(error.exception.errno, errno.EBADF)

    def test_windows_handle_composition_model(self):
        if os.name != "posix":
            self.skipTest("POSIX-backed Windows API model; native Windows is separate")
        from literate_ai.adapters import evidence_files

        class Kernel:
            def __init__(self):
                self.live = set()
                self.calls = []

            def open_reparse_aware(model, path, *, share_delete=True, share_write=True):
                self.assertFalse(share_delete)
                self.assertFalse(share_write)
                node = Path(path).lstat()
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if stat.S_ISDIR(node.st_mode):
                    flags |= os.O_DIRECTORY
                handle = os.open(path, flags)
                model.live.add(handle)
                model.calls.append(path)
                return handle

            def file_identity(model, handle):
                node = os.fstat(handle)
                return node.st_dev, node.st_ino >> 32, node.st_ino & 0xFFFFFFFF

            def close(model, handle):
                model.live.remove(handle)
                os.close(handle)

        kernels = []

        def factory():
            value = Kernel()
            kernels.append(value)
            return value

        def transfer(handle, _flags):
            for kernel in kernels:
                if handle in kernel.live:
                    kernel.live.remove(handle)
                    return handle
            raise AssertionError("native handle transfer was not original")

        (self.source / "a.bin").write_bytes(b"modeled native branch\n")
        with (
            patch("literate_ai._cache_lock._Kernel32Windows", side_effect=factory),
            patch.object(
                evidence_files,
                "_native_access",
                side_effect=evidence_files._WindowsAccess,
            ),
            patch.dict(
                sys.modules,
                {
                    "msvcrt": SimpleNamespace(
                        open_osfhandle=transfer, get_osfhandle=lambda value: value
                    )
                },
            ),
            patch.object(os, "O_BINARY", 0, create=True),
        ):
            self.copy()
        self.assertTrue(kernels)
        self.assertTrue(all(not kernel.live for kernel in kernels))
        self.assertEqual(
            (self.output / "object/cache/a.bin").read_bytes(),
            b"modeled native branch\n",
        )
