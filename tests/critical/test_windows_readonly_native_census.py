"""Modeled Win32 API + real owned POSIX tree controls; NO Windows verdict."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai import _cache_lock
from literate_ai.adapters import qualification_workspace_namespace as namespace
from scripts import installed_native_root_inputs as inputs


class NativeKernelModel:
    """Protocol model only: original held IDs differ from current name IDs."""

    def __init__(self):
        self.handles, self.current_names = {}, {}
        self.opened, self.closed = [], []
        self.failure = None
        self.close_failure = None

    def open_reparse_aware(self, path, *, share_delete=True, share_write=True):
        if share_delete is not False or share_write is not False:
            raise AssertionError("readonly scope must deny write/delete sharing")
        parent = str(Path(path).parent)
        if parent != path and parent not in {row[0] for row in self.handles.values()}:
            raise AssertionError("parent must be held before child open")
        identity = self.current_names.setdefault(path, ("volume", path, 0))
        handle = len(self.opened) + 1
        self.opened.append((handle, path))
        self.handles[handle] = (path, identity)
        return handle

    def file_identity(self, handle):
        if self.failure is not None:
            raise self.failure
        return self.handles[handle][1]

    def close(self, handle):
        self.closed.append(handle)
        self.handles.pop(handle)
        if self.close_failure == handle:
            raise OSError("modeled close refusal")


class WindowsReadonlyNativeCensusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.kernel = NativeKernelModel()
        self.stack = []
        for patch in (
            mock.patch.object(namespace, "os", SimpleNamespace(name="nt")),
            mock.patch.object(
                _cache_lock, "_Kernel32Windows", return_value=self.kernel
            ),
            mock.patch.object(
                namespace,
                "require_safe_directory",
                side_effect=AssertionError("full path reader before native holds"),
            ),
        ):
            patch.start()
            self.addCleanup(patch.stop)

    def test_original_owner_holds_parents_and_releases_before_escaped_guard(self):
        with namespace.hold_qualification_workspace_namespace(
            self.root, read_only=True
        ) as current:
            current()
            self.assertTrue(self.kernel.handles)
        self.assertEqual(self.kernel.handles, {})
        calls = len(self.kernel.opened)
        with self.assertRaises(ValueError):
            current()
        self.assertEqual(len(self.kernel.opened), calls)

    def test_native_name_swap_refuses_even_with_unchanged_python_stat(self):
        with namespace.hold_qualification_workspace_namespace(
            self.root, read_only=True
        ) as current:
            before = self.root.lstat()
            self.kernel.current_names[str(self.root)] = (
                "foreign-volume",
                "replacement",
                1,
            )
            self.assertEqual(self.root.lstat().st_ino, before.st_ino)
            with self.assertRaises(ValueError):
                current()
            # Restore model so the independently required normal-exit check can
            # finish; the refusal above, not this cleanup, is the tested result.
            self.kernel.current_names[str(self.root)] = ("volume", str(self.root), 0)

    @unittest.skipUnless(os.name == "posix", "model alias entry needs POSIX symlink")
    def test_reparse_model_never_opens_a_descendant_of_alias(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root / "never-probed", target_is_directory=True)
        with self.assertRaises(ValueError):
            with namespace.hold_qualification_workspace_namespace(
                alias / "child", read_only=True
            ):
                self.fail("alias cannot admit")
        self.assertNotIn(
            str(alias / "child"), [path for _handle, path in self.kernel.opened]
        )
        self.assertEqual(self.kernel.handles, {})

    def test_identity_failure_after_open_still_closes_that_original_handle(self):
        failure = RuntimeError("original native identity refusal")
        self.kernel.failure = failure
        with self.assertRaises(RuntimeError) as caught:
            with namespace.hold_qualification_workspace_namespace(
                self.root, read_only=True
            ):
                self.fail("identity refusal cannot admit")
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.kernel.handles, {})
        self.assertEqual(self.kernel.closed, [1])

    def test_body_error_survives_close_refusal_and_all_handles_attempt(self):
        primary = RuntimeError("original reader failure")
        with self.assertRaises(RuntimeError) as caught:
            with namespace.hold_qualification_workspace_namespace(
                self.root, read_only=True
            ):
                self.kernel.close_failure = max(self.kernel.handles)
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.kernel.handles, {})
        self.assertEqual(len(primary.__notes__), 1)

    def test_readonly_selection_is_exact_boolean(self):
        with self.assertRaises(TypeError):
            with namespace.hold_qualification_workspace_namespace(
                self.root, read_only=1
            ):
                self.fail("decoded truthy selector cannot admit")
        self.assertEqual(self.kernel.opened, [])

    def test_census_uses_original_readonly_scope_and_canonical_members(self):
        (self.root / "child").mkdir()
        (self.root / "child/source.py").write_text("# inert\n")
        (self.root / "ignored.data").write_text("not selected\n")
        files, names = inputs._windows_bounded_census(
            self.root,
            suffix=".py",
            maximum_entries=8,
            maximum_namespace_bytes=4096,
            maximum_depth=4,
            maximum_path_bytes=768,
        )
        self.assertEqual(files, (self.root / "child/source.py",))
        self.assertEqual(
            names,
            (
                ("child", "directory"),
                ("child/source.py", "file"),
                ("ignored.data", "file"),
            ),
        )
        self.assertEqual(self.kernel.handles, {})

    def test_census_counts_ignored_entries_before_further_enumeration(self):
        for number in range(3):
            (self.root / f"ignored-{number}.data").write_bytes(b"inert")
        with self.assertRaises(ValueError):
            inputs._windows_bounded_census(
                self.root,
                suffix=".py",
                maximum_entries=2,
                maximum_namespace_bytes=4096,
                maximum_depth=4,
                maximum_path_bytes=768,
            )
        self.assertEqual(self.kernel.handles, {})

    def test_census_namespace_bound_precedes_child_metadata(self):
        child = self.root / "long-entry.data"
        child.write_bytes(b"inert")
        original = Path.lstat

        def metadata(path, *arguments, **options):
            self.assertNotEqual(path, child)
            return original(path, *arguments, **options)

        with mock.patch.object(Path, "lstat", metadata):
            with self.assertRaises(ValueError):
                inputs._windows_bounded_census(
                    self.root,
                    suffix=".py",
                    maximum_entries=8,
                    maximum_namespace_bytes=1,
                    maximum_depth=4,
                    maximum_path_bytes=768,
                )
        self.assertEqual(self.kernel.handles, {})

    @unittest.skipUnless(os.name == "posix", "model alias entry needs POSIX symlink")
    def test_census_rejects_alias_before_enumerating_its_target(self):
        alias = self.root / "alias"
        alias.symlink_to(self.root / "never-probed", target_is_directory=True)
        original = os.scandir
        scanned = []

        def scan(path):
            self.assertEqual(path, self.root)
            scanned.append(path)
            return original(path)

        with mock.patch.object(inputs, "os", SimpleNamespace(scandir=scan)):
            with self.assertRaises(ValueError):
                inputs._windows_bounded_census(
                    self.root,
                    suffix=".py",
                    maximum_entries=8,
                    maximum_namespace_bytes=4096,
                    maximum_depth=4,
                    maximum_path_bytes=768,
                )
        self.assertEqual(scanned, [self.root])
        self.assertEqual(self.kernel.handles, {})
