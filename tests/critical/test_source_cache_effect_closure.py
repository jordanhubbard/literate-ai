"""Actual owner-callback cuts immediately before immutable filesystem effects."""

import inspect
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.cache import FileSystemSourceCache, SourceCacheError
from literate_ai.adapters.cache import filesystem as owner
from tests.critical import test_source_cache_retirement as retirement_fixture


class SourceCacheEffectClosureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.cache = FileSystemSourceCache("effect-fixture", self.root / "cache")

    @unittest.skipUnless(os.name == "posix", "requires owned symlink mutation")
    def test_publish_rejects_destination_parent_redirection_before_link(self):
        parent = self.cache.entries
        retained = parent.with_name("retained")
        outside = self.root / "outside"
        outside.mkdir()
        calls = []

        def current():
            calls.append(True)
            if len(calls) == 2:
                parent.rename(retained)
                parent.symlink_to(outside, target_is_directory=True)

        try:
            with self.assertRaises(SourceCacheError):
                self.cache._publish_immutable_bytes(
                    parent / "entry.json", b"exact", require_current=current
                )
            self.assertFalse((outside / "entry.json").exists())
        finally:
            if parent.is_symlink():
                parent.unlink()
                retained.rename(parent)

    def test_publish_rejects_staged_payload_change_before_link(self):
        destination = self.cache.entries / "entry.json"
        calls = []

        def current():
            calls.append(True)
            if len(calls) == 2:
                (temporary,) = self.cache.staging.glob(".publish-*")
                temporary.write_bytes(b"foreign payload")

        with self.assertRaises(SourceCacheError):
            self.cache._publish_immutable_bytes(
                destination, b"exact", require_current=current
            )
        self.assertFalse(destination.exists())

    @unittest.skipUnless(os.name == "posix", "requires an actual named-file swap")
    def test_refusal_preserves_foreign_staging_replacement(self):
        destination = self.cache.entries / "entry.json"
        calls, foreign = [], []

        def current():
            calls.append(True)
            if len(calls) == 2:
                (temporary,) = self.cache.staging.glob(".publish-*")
                temporary.rename(self.root / "retained-stage")
                temporary.write_bytes(b"foreign staging file")
                foreign.append(temporary)

        with self.assertRaises(SourceCacheError):
            self.cache._publish_immutable_bytes(
                destination, b"exact", require_current=current
            )
        self.assertFalse(destination.exists())
        self.assertEqual(foreign[0].read_bytes(), b"foreign staging file")

    def test_callback_cannot_retarget_cache_configuration(self):
        destination = self.cache.entries / "entry.json"
        outside = self.root / "outside"
        outside.mkdir()
        calls = []

        def current():
            calls.append(True)
            if len(calls) == 2:
                self.cache.root = outside

        with self.assertRaises(SourceCacheError):
            self.cache._publish_immutable_bytes(
                destination, b"exact", require_current=current
            )
        self.assertEqual(self.cache.root, outside)
        self.assertFalse(destination.exists())

    @unittest.skipUnless(os.name == "posix", "requires an actual named-file swap")
    def test_existing_entry_final_callback_cannot_adopt_equal_byte_replacement(self):
        destination = self.cache.entries / "entry.json"
        destination.write_bytes(b"exact")
        calls = []

        def current():
            calls.append(True)
            if len(calls) == 2:
                destination.rename(self.root / "retained-entry")
                destination.write_bytes(b"exact")

        with self.assertRaises(SourceCacheError):
            self.cache._publish_immutable_bytes(
                destination, b"exact", require_current=current
            )
        self.assertEqual(destination.read_bytes(), b"exact")
        self.assertEqual((self.root / "retained-entry").read_bytes(), b"exact")

    @unittest.skipUnless(os.name == "posix", "requires an actual named-file swap")
    def test_new_entry_final_callback_cannot_replace_published_object(self):
        destination = self.cache.entries / "entry.json"
        calls = []

        def current():
            calls.append(True)
            if len(calls) == 3:
                destination.rename(self.root / "retained-published")
                destination.write_bytes(b"foreign published object")

        with self.assertRaises(SourceCacheError):
            self.cache._publish_immutable_bytes(
                destination, b"exact", require_current=current
            )
        self.assertEqual(len(calls), 3)
        self.assertEqual(destination.read_bytes(), b"foreign published object")
        self.assertEqual((self.root / "retained-published").read_bytes(), b"exact")

    @unittest.skipUnless(
        os.name == "posix", "controlled Windows facade uses POSIX descriptors"
    )
    def test_windows_native_identity_branch_handles_zero_python_inode(self):
        # Controlled native-handle facade on this host; not native Windows evidence.
        real_fstat, real_lstat = os.fstat, Path.lstat

        class Kernel:
            def open_reparse_aware(self, path, **_sharing):
                return os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))

            def file_identity(self, handle):
                value = real_fstat(handle)
                return value.st_dev, 0, value.st_ino

            def close(self, handle):
                os.close(handle)

        def no_inode(path):
            value = real_lstat(path)
            return SimpleNamespace(
                **{
                    name: getattr(value, name)
                    for name in (
                        "st_dev",
                        "st_mode",
                        "st_nlink",
                        "st_size",
                        "st_mtime_ns",
                        "st_ctime_ns",
                    )
                },
                st_ino=0,
            )

        destination = self.cache.entries / "native-identity.json"
        with (
            mock.patch.object(owner, "_is_windows", return_value=True),
            mock.patch.object(
                owner, "_default_windows_kernel32", return_value=Kernel()
            ),
            mock.patch.object(
                owner, "_default_get_osfhandle", side_effect=lambda value: value
            ),
            mock.patch.object(Path, "lstat", no_inode),
        ):
            self.cache._publish_immutable_bytes(destination, b"exact")
            self.assertEqual(destination.read_bytes(), b"exact")
            calls = []

            def current():
                calls.append(True)
                if len(calls) == 2:
                    destination.rename(self.root / "retained-native")
                    destination.write_bytes(b"exact")

            with self.assertRaises(SourceCacheError):
                self.cache._publish_immutable_bytes(
                    destination, b"exact", require_current=current
                )
        self.assertEqual(len(calls), 2)
        self.assertEqual(destination.read_bytes(), b"exact")

    @unittest.skipUnless(
        os.name == "posix", "controlled Windows facade uses POSIX descriptors"
    )
    def test_unavailable_native_identity_refuses_without_inode_fallback(self):
        handles = set()

        class Kernel:
            def open_reparse_aware(self, path, **_sharing):
                descriptor = os.open(path, os.O_RDONLY)
                handles.add(descriptor)
                return descriptor

            def file_identity(self, _handle):
                return 0, 0, 0

            def close(self, handle):
                os.close(handle)
                handles.remove(handle)

        destination = self.cache.entries / "unknown-identity.json"
        with (
            mock.patch.object(owner, "_is_windows", return_value=True),
            mock.patch.object(
                owner, "_default_windows_kernel32", return_value=Kernel()
            ),
        ):
            with self.assertRaises(SourceCacheError) as error:
                self.cache._publish_immutable_bytes(destination, b"exact")
        self.assertEqual(
            error.exception.code, "source-cache.effect-identity-unavailable"
        )
        self.assertFalse(destination.exists())
        self.assertEqual(handles, set())

    @unittest.skipUnless(os.name == "posix", "requires an actual named-file swap")
    def test_retirement_callback_cannot_unlink_foreign_membership(self):
        self._refuse_foreign_retirement(callback_ordinal=1)

    def test_retirement_first_native_callback_preserves_original_read(self):
        self._refuse_foreign_retirement(callback_ordinal=2)

    def _refuse_foreign_retirement(self, *, callback_ordinal):
        cache, key, first, second = (
            retirement_fixture.SourceCacheRetirementTests().populate(
                self.root / "retirement-cache"
            )
        )
        directory = cache.keys / key.accepted_source_lookup_identity.digest
        membership = directory / (first.identity.digest + ".json")
        retired = directory / ".retired" / membership.name
        changed = []
        cuts = []

        def current():
            frame = inspect.currentframe()
            names = []
            cursor = frame.f_back
            while cursor is not None:
                names.append(cursor.f_code.co_name)
                cursor = cursor.f_back
            at_unlink = (
                "_retire_other_memberships_unlocked" in names
                and "_publish_immutable_bytes" not in names
            )
            del frame, cursor
            if retired.exists() and at_unlink:
                cuts.append(True)
            if len(cuts) == callback_ordinal and at_unlink and not changed:
                membership.rename(self.root / "retained-membership")
                membership.write_bytes(b"foreign membership")
                changed.append(True)

        error = None
        try:
            cache.retire_other_memberships(
                key, keep=second.identity, require_current=current
            )
        except SourceCacheError as caught:
            error = caught
        self.assertEqual(changed, [True])
        self.assertEqual(membership.read_bytes(), b"foreign membership")
        self.assertTrue((self.root / "retained-membership").exists())
        self.assertIsNotNone(error)
