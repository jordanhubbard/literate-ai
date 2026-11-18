"""Actual bounded POSIX file reads, substitutions and ordinary-reader fallback."""

import os
import stat
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest import mock

from literate_ai import projects
from literate_ai._filesystem import _readonly_directory_batch
from literate_ai.projects import PinnedInputClosure, PinnedInputClosureError


@unittest.skipUnless(
    projects._pinned_read_batch_supported(), "requires native POSIX dir_fd"
)
class PinnedInputBatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def fixture(self, *, directory=None, count=2, maximum=4096):
        directory = directory or self.root
        directory.mkdir(parents=True, exist_ok=True)
        closure = PinnedInputClosure(maximum_file_bytes=maximum)
        paths = []
        for index in range(count):
            path = directory / f"file-{index}"
            path.write_bytes(b"original")
            closure.pin(path, boundary=self.root, label=f"source-{index}")
            paths.append(path)
        return closure, paths

    def fault_on_read(self, closure, target, operation):
        original_read = os.read
        inode = target.stat().st_ino
        changed = []

        def read(descriptor, size):
            content = original_read(descriptor, size)
            if not changed and os.fstat(descriptor).st_ino == inode:
                operation()
                changed.append(True)
            return content

        with mock.patch.object(os, "read", read):
            with self.assertRaises(PinnedInputClosureError):
                closure.require_unchanged()
        self.assertEqual(changed, [True], "fault did not reach actual descriptor read")

    def test_last_read_cannot_replace_or_rewrite_earlier_original(self):
        for kind in ("replacement", "rewrite"):
            with self.subTest(kind=kind):
                closure, paths = self.fixture(directory=self.root / kind)
                earlier, last = paths

                def change(kind=kind, earlier=earlier):
                    if kind == "replacement":
                        peer = earlier.with_name("peer")
                        peer.write_bytes(earlier.read_bytes())
                        peer.replace(earlier)
                    else:
                        before = earlier.stat()
                        earlier.write_bytes(earlier.read_bytes())
                        os.utime(earlier, ns=(before.st_atime_ns, before.st_mtime_ns))

                self.fault_on_read(closure, last, change)
                self.assertEqual(earlier.read_bytes(), b"original")

    def test_parent_alias_cannot_reuse_original_child_inodes(self):
        selected = self.root / "selected"
        closure, paths = self.fixture(directory=selected)
        moved = self.root / "moved"

        def redirect():
            selected.rename(moved)
            selected.symlink_to(moved, target_is_directory=True)

        self.fault_on_read(closure, paths[-1], redirect)
        self.assertTrue(selected.is_symlink())
        self.assertEqual((moved / paths[0].name).read_bytes(), b"original")

    def test_entry_metadata_membership_and_limits_close_after_reads(self):
        for kind in ("labels", "membership", "limits"):
            with self.subTest(kind=kind):
                closure, paths = self.fixture(directory=self.root / kind)

                def change(kind=kind, closure=closure, paths=paths):
                    if kind == "labels":
                        entry = next(iter(closure._entries.values()))
                        object.__setattr__(entry, "labels", ("foreign",))
                    elif kind == "membership":
                        extra = paths[0].with_name("extra")
                        extra.write_bytes(b"extra")
                        closure.pin(extra, boundary=self.root, label="extra")
                    else:
                        closure.maximum_file_bytes += 1

                self.fault_on_read(closure, paths[-1], change)
                if kind == "membership":
                    self.assertEqual(
                        len(closure._entries), 3, "validator rolled back caller state"
                    )

    def test_nonregular_and_oversized_replacements_refuse(self):
        for kind in ("link", "fifo", "directory", "oversized"):
            with self.subTest(kind=kind):
                closure, paths = self.fixture(
                    directory=self.root / kind, count=1, maximum=16
                )
                path = paths[0]
                path.unlink()
                if kind == "link":
                    outside = self.root / "outside"
                    outside.write_bytes(b"original")
                    path.symlink_to(outside)
                elif kind == "fifo":
                    os.mkfifo(path)
                elif kind == "directory":
                    path.mkdir()
                else:
                    path.write_bytes(b"x" * 17)
                with self.assertRaises(PinnedInputClosureError):
                    closure.require_unchanged()

    def test_platform_and_custom_reader_dispatch_keep_ordinary_validation(self):
        closure, paths = self.fixture()
        original_read = PinnedInputClosure._read
        called = []

        def custom(owner, *args, **kwargs):
            called.append(True)
            return original_read(owner, *args, **kwargs)

        with mock.patch.object(
            projects,
            "_readonly_directory_batch",
            side_effect=AssertionError("batch entered"),
        ):
            with mock.patch.object(
                projects, "_pinned_read_batch_supported", return_value=False
            ):
                closure.require_unchanged()
            closure._read = MethodType(custom, closure)
            closure.require_unchanged()
            self.assertEqual(len(called), 2)
            del closure._read
            with mock.patch.object(PinnedInputClosure, "_read", custom):
                closure.require_unchanged()
            self.assertEqual(len(called), 4)
            with mock.patch.object(
                projects, "_pinned_read_batch_supported", return_value=False
            ):
                paths[0].write_bytes(b"different")
                with self.assertRaises(PinnedInputClosureError):
                    closure.require_unchanged()

    def test_capacity_declines_before_open_and_retains_ordinary_byte_check(self):
        with mock.patch.object(
            os, "open", side_effect=AssertionError("opened before capacity refusal")
        ):
            with _readonly_directory_batch((self.root,), maximum_descriptors=1) as view:
                self.assertIsNone(view)
        closure = PinnedInputClosure()
        for index in range(70):
            directory = self.root / str(index)
            directory.mkdir()
            path = directory / "source"
            path.write_bytes(b"original")
            closure.pin(path, boundary=self.root, label=str(index))
        with mock.patch.object(
            projects,
            "_read_pinned_descriptor",
            side_effect=AssertionError("batch read"),
        ):
            closure.require_unchanged()
            path.write_bytes(b"different")
            with self.assertRaises(PinnedInputClosureError):
                closure.require_unchanged()

    def test_unknown_file_identity_declines_before_payload_reads(self):
        closure, paths = self.fixture(count=2)
        original_stat = os.stat

        def observed(path, *args, **kwargs):
            value = original_stat(path, *args, **kwargs)
            if path == paths[-1].name and kwargs.get("dir_fd") is not None:
                fields = {
                    name: getattr(value, name)
                    for name in (
                        "st_dev",
                        "st_ino",
                        "st_mode",
                        "st_nlink",
                        "st_size",
                        "st_mtime_ns",
                        "st_ctime_ns",
                    )
                }
                fields["st_ino"] = 0
                return SimpleNamespace(**fields)
            return value

        # The wrapper preserves the real native operation's capability; this is
        # a controlled identity facade, not native zero-inode qualification.
        with (
            mock.patch.object(
                projects, "_pinned_read_batch_supported", return_value=True
            ),
            mock.patch.object(os, "stat", observed),
            mock.patch.object(
                projects,
                "_read_pinned_descriptor",
                side_effect=AssertionError("batch read"),
            ),
        ):
            closure.require_unchanged()

    @contextmanager
    def descriptors(
        self,
        *,
        fail_open=False,
        fail_close=False,
        fail_directory_open=False,
        fail_directory_close=False,
    ):
        original_open, original_close, original_fstat = os.open, os.close, os.fstat
        live, peak, triggered = set(), [0], []

        def opened(path, *args, **kwargs):
            if (fail_open and str(path) == "file-0") or (
                fail_directory_open and str(path) == self.root.name
            ):
                triggered.append(True)
                raise PermissionError("controlled file-open refusal")
            descriptor = original_open(path, *args, **kwargs)
            live.add(descriptor)
            peak[0] = max(peak[0], len(live))
            return descriptor

        def closed(descriptor):
            directory = fail_directory_close and stat.S_ISDIR(
                original_fstat(descriptor).st_mode
            )
            original_close(descriptor)
            live.remove(descriptor)
            if (fail_close or directory) and not triggered:
                triggered.append(True)
                raise OSError("controlled close refusal")

        with (
            mock.patch.object(
                projects, "_pinned_read_batch_supported", return_value=True
            ),
            mock.patch.object(os, "open", opened),
            mock.patch.object(os, "close", closed),
        ):
            yield live, peak, triggered
        self.assertEqual(live, set(), "owned descriptors leaked")
        self.assertLessEqual(peak[0], 64, "ancestor/file descriptor budget exceeded")

    def test_descriptors_close_on_success_and_open_or_close_errors(self):
        closure, _paths = self.fixture()
        with self.descriptors():
            closure.require_unchanged()
        for kind in ("open", "close"):
            with (
                self.subTest(kind=kind),
                self.descriptors(
                    fail_open=kind == "open", fail_close=kind == "close"
                ) as (_live, _peak, triggered),
            ):
                with self.assertRaises(PinnedInputClosureError):
                    closure.require_unchanged()
                self.assertTrue(triggered)

    def test_unknown_directory_identity_closes_handles_before_fallback(self):
        closure, _paths = self.fixture()
        original_fstat, original_open = os.fstat, Path.open
        inode = self.root.stat().st_ino
        observed = []

        def fstat(descriptor):
            value = original_fstat(descriptor)
            if value.st_ino == inode and stat.S_ISDIR(value.st_mode):
                return SimpleNamespace(st_mode=value.st_mode, st_ino=0)
            return value

        with self.descriptors() as (live, _peak, _triggered):

            def opened(path, *args, **kwargs):
                self.assertEqual(live, set(), "fallback retained batch descriptors")
                observed.append(True)
                return original_open(path, *args, **kwargs)

            with (
                mock.patch.object(os, "fstat", fstat),
                mock.patch.object(Path, "open", opened),
                mock.patch.object(
                    projects,
                    "_read_pinned_descriptor",
                    side_effect=AssertionError("batch read"),
                ),
            ):
                closure.require_unchanged()
        self.assertEqual(len(observed), 2)

    def test_directory_open_and_close_failures_do_not_fall_back(self):
        closure, _paths = self.fixture()
        for kind in ("open", "close"):
            with (
                self.subTest(kind=kind),
                self.descriptors(
                    fail_directory_open=kind == "open",
                    fail_directory_close=kind == "close",
                ) as (_live, _peak, triggered),
            ):
                with self.assertRaises(PinnedInputClosureError):
                    closure.require_unchanged()
                self.assertTrue(triggered)
