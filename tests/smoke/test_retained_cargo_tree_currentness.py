"""Fresh tree observations retain custody while avoiding duplicate CPU work."""

import ctypes
import os
import stat
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_tree_v2 as subject
from literate_ai.adapters.retained_project_inputs import _DirectoryAccess
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


class CargoTreeCurrentnessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.directory = self.root / "source"
        self.directory.mkdir()
        self.payload = self.directory / "input.txt"
        self.payload.write_bytes(b"original payload")
        self.budget = RetainedCargoInputBudget(100, 200, 4096, 409600)

    def capture(self):
        return subject.capture_retained_cargo_tree_v2(
            self.root, budget=self.budget, maximum_metadata_bytes=32 * 1024**2
        )

    @unittest.skipIf(os.name == "nt", "POSIX anchored metadata count")
    def test_initial_census_metadata_is_not_reobserved_before_streaming(self):
        # One directory and N regular files: two censuses each observe N+2
        # nodes, streaming observes 3N, and final physical checks observe N+1.
        count = 8
        for index in range(count - 1):
            (self.directory / str(index)).write_bytes(b"payload")
        calls = []
        original = _DirectoryAccess.metadata

        def observed(access, path):
            calls.append(path)
            return original(access, path)

        with patch.object(_DirectoryAccess, "metadata", observed):
            tree = self.capture()
        self.assertEqual(tree.file_count, count)
        self.assertEqual(len(calls), 6 * count + 5)

    def test_currentness_compares_fresh_values_without_reencoding_both_trees(self):
        tree = self.capture()
        expected = tree.identity
        with patch.object(
            subject, "canonical_identity", wraps=subject.canonical_identity
        ) as canonical:
            tree.require_unchanged()
        self.assertEqual(canonical.call_count, 0)
        self.assertEqual(self.capture().identity, expected)

    def test_changed_content_refuses_on_next_independent_observation(self):
        tree = self.capture()
        self.payload.write_bytes(b"modified payload")
        with self.assertRaises(ValueError):
            tree.require_unchanged()

    def test_altered_expected_digest_cannot_hide_behind_same_physical_metadata(self):
        tree = self.capture()
        name, blob, executable = tree.files[0]
        changed = replace(
            tree, files=((name, BlobRef("0" * 64, blob.size), executable),)
        )
        with self.assertRaises(ValueError):
            changed.require_unchanged()

    @unittest.skipIf(os.name == "nt", "POSIX permission identity")
    def test_mode_change_refuses(self):
        tree = self.capture()
        self.payload.chmod(self.payload.stat().st_mode ^ 0o100)
        with self.assertRaises(ValueError):
            tree.require_unchanged()

    def test_parent_replacement_refuses_even_with_equal_bytes(self):
        tree = self.capture()
        self.directory.rename(self.root / "old")
        self.directory.mkdir()
        self.payload.write_bytes(b"original payload")
        with self.assertRaises(ValueError):
            tree.require_unchanged()

    def test_write_and_restore_after_initial_census_refuses(self):
        original = subject._inventory
        calls = 0
        before = self.payload.stat()

        def census(*args, **kwargs):
            nonlocal calls
            value = original(*args, **kwargs)
            calls += 1
            if calls == 1:
                self.payload.write_bytes(b"temporary change")
                self.payload.write_bytes(b"original payload")
                os.utime(self.payload, ns=(before.st_atime_ns, before.st_mtime_ns))
            return value

        with patch.object(subject, "_inventory", census):
            with self.assertRaises(ValueError):
                self.capture()

    def test_restored_writes_with_creation_only_ctime_refuse_after_either_census(self):
        for after_census in (1, 2):
            with self.subTest(after_census=after_census):
                self._restored_write_with_creation_only_ctime(after_census)

    def _restored_write_with_creation_only_ctime(self, after_census):
        original_inventory = subject._inventory
        original_node = subject._node
        before = self.payload.stat()
        calls = 0
        generation = 0

        def creation_only_node(node):
            value = original_node(node)
            # Model the Windows path-stat creation timestamp. All other
            # physical fields and real streamed bytes remain unchanged.
            return (*value[:5], 0, *value[6:]) if stat.S_ISREG(node.st_mode) else value

        def census(*args, **kwargs):
            nonlocal calls, generation
            result = original_inventory(*args, **kwargs)
            calls += 1
            if calls == after_census:
                self.payload.write_bytes(b"temporary change")
                self.payload.write_bytes(b"original payload")
                os.utime(self.payload, ns=(before.st_atime_ns, before.st_mtime_ns))
                generation += 1
            return result

        with (
            patch.object(subject, "_node", side_effect=creation_only_node),
            patch.object(subject, "_inventory", side_effect=census),
            patch.object(
                subject,
                "_file_change_witness",
                side_effect=lambda *_: generation,
                create=True,
            ),
            self.assertRaises(ValueError),
        ):
            self.capture()

    def test_write_after_closing_census_is_still_checked(self):
        original = subject._inventory
        calls = 0

        def census(*args, **kwargs):
            nonlocal calls
            value = original(*args, **kwargs)
            calls += 1
            if calls == 2:
                self.payload.write_bytes(b"late mutation!!!")
            return value

        with patch.object(subject, "_inventory", census):
            with self.assertRaises(ValueError):
                self.capture()


class WindowsChangeTimeInterfaceTests(unittest.TestCase):
    def test_observed_regular_reparse_file_refuses_before_open(self):
        before = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_file_attributes=0x400)
        with (
            patch.object(subject.os, "open") as opened,
            self.assertRaisesRegex(ValueError, "change-time-unsafe"),
        ):
            subject._windows_file_change_witness(Path("unused"), before)
        opened.assert_not_called()

    def test_native_api_uses_basic_info_and_preserves_full_change_time(self):
        def query(handle, information_class, output, size):
            self.assertEqual(handle, 2**48 + 17)
            self.assertEqual(information_class, 0)
            self.assertEqual(size, 40)
            output._obj.ChangeTime = 133_000_000_000_000_001
            output._obj.FileAttributes = 0x20
            return 1

        kernel = SimpleNamespace(GetFileInformationByHandleEx=query)
        observed = subject._windows_change_time(
            19, kernel32=kernel, get_osfhandle=lambda descriptor: 2**48 + descriptor - 2
        )
        self.assertEqual(observed, 133_000_000_000_000_001)
        self.assertEqual(query.argtypes[0], ctypes.c_void_p)

    def test_native_api_failure_and_unsafe_metadata_refuse(self):
        for succeeds, attributes, change_time in (
            (False, 0x20, 100),
            (True, 0x400, 100),
            (True, 0x10, 100),
            (True, 0x20, 0),
        ):
            with self.subTest(
                succeeds=succeeds, attributes=attributes, change_time=change_time
            ):

                def query(
                    _handle,
                    _kind,
                    output,
                    _size,
                    *,
                    expected_time=change_time,
                    expected_attributes=attributes,
                    expected_success=succeeds,
                ):
                    output._obj.ChangeTime = expected_time
                    output._obj.FileAttributes = expected_attributes
                    return expected_success

                with self.assertRaises(ValueError):
                    subject._windows_change_time(
                        19,
                        kernel32=SimpleNamespace(GetFileInformationByHandleEx=query),
                        get_osfhandle=lambda _: 23,
                    )

    def test_bound_descriptor_is_closed_on_success_and_native_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "payload"
            path.write_bytes(b"owned bytes")
            for times in ([100, 100], [100, 101]):
                with self.subTest(times=times):
                    descriptors = []

                    def identity(_path, descriptor, *, observed=descriptors):
                        observed.append(descriptor)
                        return True

                    with (
                        patch.object(
                            subject, "_windows_identity_matches", side_effect=identity
                        ),
                        patch.object(
                            subject, "_windows_change_time", side_effect=times
                        ),
                    ):
                        if times[0] == times[1]:
                            self.assertEqual(
                                subject._windows_file_change_witness(
                                    path, path.lstat()
                                ),
                                100,
                            )
                        else:
                            with self.assertRaisesRegex(ValueError, "binding-changed"):
                                subject._windows_file_change_witness(path, path.lstat())
                    self.assertEqual(len(descriptors), 1)
                    with self.assertRaises(OSError):
                        os.fstat(descriptors[0])
                    self.assertEqual(path.read_bytes(), b"owned bytes")

    def test_uncertain_handle_binding_refuses_before_reading_native_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "payload"
            path.write_bytes(b"owned bytes")
            with (
                patch.object(subject, "_windows_identity_matches", return_value=False),
                patch.object(subject, "_windows_change_time") as query,
                self.assertRaisesRegex(ValueError, "binding-changed"),
            ):
                subject._windows_file_change_witness(path, path.lstat())
            query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
