"""Actual local fd-census controls, not native or installed release evidence."""

import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.projects import PinnedInputClosureError
from scripts import installed_native_root_inputs as inputs
from tests.critical import test_installed_native_root_qualification_gate as fixtures

SUPPORTED = (
    os.name == "posix"
    and getattr(os, "O_NOFOLLOW", 0)
    and getattr(os, "O_DIRECTORY", 0)
    and os.scandir in os.supports_fd
    and os.open in os.supports_dir_fd
)


@unittest.skipUnless(SUPPORTED, "requires actual POSIX no-follow fd census")
class InstalledNativeInputCensusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def _fixture(self):
        fixture = fixtures.InstalledNativeRootInputTests(
            "test_real_input_closure_refuses_changed_original_archive"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        return fixture

    @contextmanager
    def _watch_native(self, *, scan=None):
        original_open, original_scan = os.open, os.scandir
        original_fd, original_dir_fd = os.supports_fd, os.supports_dir_fd
        opened, scanned = [], []

        def open_native(path, flags, *arguments, **options):
            self.assertTrue(flags & os.O_NOFOLLOW)
            self.assertTrue(flags & os.O_DIRECTORY)
            opened.append((path, flags, options.get("dir_fd")))
            return original_open(path, flags, *arguments, **options)

        def scan_native(descriptor):
            self.assertIs(type(descriptor), int)
            scanned.append(descriptor)
            return original_scan(descriptor) if scan is None else scan(descriptor)

        with (
            mock.patch.object(os, "open", open_native),
            mock.patch.object(os, "scandir", scan_native),
            mock.patch.object(os, "supports_fd", {*original_fd, scan_native}),
            mock.patch.object(os, "supports_dir_fd", {*original_dir_fd, open_native}),
        ):
            yield opened, scanned

    def test_tests_root_alias_refuses_before_enumeration_without_target_access(self):
        fixture = self._fixture()
        tests = fixture.repository / "tests"
        tests.rename(fixture.repository / "old-tests")
        # Intentionally nonexistent. NO target metadata/open is permitted by
        # this control: every ancestry open MUST have O_NOFOLLOW before OS use.
        tests.symlink_to(fixture.repository / "never-probed", target_is_directory=True)
        with self._watch_native() as (opened, scanned):
            with self.assertRaises(ValueError):
                inputs.capture_inputs(fixture.repository, fixture.archives)
            self.assertTrue(opened)
            self.assertEqual(scanned, [])

    def test_closing_alias_refuses_before_file_guard_or_enumeration(self):
        fixture = self._fixture()
        _record, pins = inputs.capture_inputs(fixture.repository, fixture.archives)
        tests = fixture.repository / "tests"
        tests.rename(fixture.repository / "old-tests")
        tests.symlink_to(fixture.repository / "never-probed", target_is_directory=True)
        with (
            self._watch_native() as (_opened, scanned),
            mock.patch.object(
                pins._pins,
                "require_unchanged",
                side_effect=AssertionError("file guard reached first"),
            ) as reader,
        ):
            with self.assertRaises(ValueError):
                pins.require_unchanged()
            reader.assert_not_called()
            self.assertEqual(scanned, [])

    def test_nonmatching_files_and_directories_spend_entry_budget(self):
        files, directories = self.root / "files", self.root / "directories"
        files.mkdir()
        for number in range(3):
            (files / f"ignored-{number}.data").write_bytes(b"unselected")
        (directories / "one/two/three").mkdir(parents=True)
        for root in (files, directories):
            with self.assertRaises(ValueError):
                inputs.bounded_census(
                    root, suffix=".py", maximum_entries=2, maximum_namespace_bytes=4096
                )

    def test_infinite_nonmatching_stream_is_stopped_before_unbounded_sort(self):
        (self.root / "ignored.data").write_bytes(b"inert")

        class Endless:
            count = 0
            closed = False

            def __enter__(self):
                return self

            def __exit__(self, *_arguments):
                self.closed = True

            def __iter__(self):
                return self

            def __next__(self):
                self.count += 1
                return SimpleNamespace(name="ignored.data")

        stream = Endless()
        with self._watch_native(scan=lambda _descriptor: stream):
            with self.assertRaises(ValueError):
                inputs.bounded_census(
                    self.root,
                    suffix=".py",
                    maximum_entries=2,
                    maximum_namespace_bytes=4096,
                )
        self.assertEqual(stream.count, 3)
        self.assertTrue(stream.closed)

    def test_namespace_bytes_refuse_before_entry_metadata(self):
        (self.root / "long-entry.data").write_bytes(b"inert")
        with mock.patch.object(
            os, "stat", side_effect=AssertionError("metadata read too early")
        ) as metadata:
            with self.assertRaises(ValueError):
                inputs.bounded_census(
                    self.root,
                    suffix=".py",
                    maximum_entries=8,
                    maximum_namespace_bytes=1,
                )
            metadata.assert_not_called()

    def test_directory_depth_is_bounded_before_further_descent(self):
        (self.root / "one/two/three").mkdir(parents=True)
        with self.assertRaises(ValueError):
            inputs.bounded_census(
                self.root,
                suffix=".py",
                maximum_entries=8,
                maximum_namespace_bytes=4096,
                maximum_depth=1,
            )

    def test_nonmatching_namespace_addition_invalidates_original_closure(self):
        fixture = self._fixture()
        _record, pins = inputs.capture_inputs(fixture.repository, fixture.archives)
        (fixture.repository / "tests/new-unselected.data").write_bytes(b"new member")
        with self.assertRaises(ValueError):
            pins.require_unchanged()

    def test_existing_byte_budget_survives_bounded_census(self):
        fixture = self._fixture()
        (fixture.repository / "tests/oversized.py").write_bytes(
            b"#" + b"x" * (8 * 1024**2)
        )
        with self.assertRaises(PinnedInputClosureError):
            inputs.capture_inputs(fixture.repository, fixture.archives)


class NativeInputDescriptorCleanupTests(unittest.TestCase):
    def test_every_owned_descriptor_is_attempted_without_replacing_primary(self):
        primary = RuntimeError("original census refusal")
        with mock.patch.object(
            os, "close", side_effect=[OSError("one"), None, OSError("two")]
        ) as close:
            inputs._close_owned((3, 4, 5), primary)
        self.assertEqual(
            close.call_args_list, [mock.call(5), mock.call(4), mock.call(3)]
        )
        self.assertEqual(len(primary.__notes__), 2)

    def test_cleanup_only_failure_retains_first_exact_error_after_all_attempts(self):
        first = OSError("original cleanup refusal")
        with mock.patch.object(
            os, "close", side_effect=[first, OSError("later"), None]
        ) as close:
            with self.assertRaises(OSError) as caught:
                inputs._close_owned((3, 4, 5), None)
        self.assertIs(caught.exception, first)
        self.assertEqual(
            close.call_args_list, [mock.call(5), mock.call(4), mock.call(3)]
        )
