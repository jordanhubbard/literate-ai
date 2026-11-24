"""Actual bounded local source capture; no migration/runtime/remote claims."""

from __future__ import annotations

import os
import stat
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_observation as production
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_project_layout_catalog_continuation as support


class FrameworkSourceObservationTests(unittest.TestCase):
    def fixture(self):
        project = support.CatalogContinuationTests("runTest")
        project.setUp()
        self.addCleanup(project.doCleanups)
        return project

    def capture(self, project):
        return production.capture_framework_source_scope(
            project.snapshot, project.context
        )

    def test_actual_source_bytes_and_native_fields_without_effects(self):
        project = self.fixture()
        nodes, contents, held = self.capture(project)
        self.assertEqual(contents["application/main.py"], b"print('untouched')\n")
        self.assertEqual(
            nodes["application/main.py"]["size"], len(contents["application/main.py"])
        )
        self.assertEqual(len(nodes["application"]["stamp"]), 7)
        self.assertFalse(any(path.startswith("litai/") for path in contents))
        self.assertTrue(
            any(row["path"] == "litai" and not row["source"] for row in held)
        )

    def test_excluded_output_and_private_state_are_not_even_statted(self):
        project = self.fixture()
        outside = project.root / "unopened-target"
        outside.mkdir()
        (project.root / "_build").symlink_to(outside, target_is_directory=True)
        project.write(".ENV", b"must not read")
        project.write("session.sqlite", b"must not read")
        original = production._named

        def named(cursor, name):
            if name in {"_build", ".ENV", "session.sqlite"}:
                raise AssertionError("opaque member probed")
            return original(cursor, name)

        with patch.object(production, "_named", named):
            _nodes, contents, held = self.capture(project)
        self.assertNotIn(".ENV", contents)
        self.assertTrue(
            {"_build", ".ENV", "session.sqlite"}.issubset({row["path"] for row in held})
        )

    def test_private_families_and_database_sidecars_are_held_before_stat(self):
        project = self.fixture()
        names = {
            ".env.local",
            ".ENV.production",
            ".ssh",
            ".aws",
            ".azure",
            ".gnupg",
            "session.sqlite-wal",
            "session.sqlite3-shm",
            "session.db-journal",
        }
        for name in names:
            project.write(name, b"owned opaque fixture bytes")
        project.write("environment.py", b"# ordinary application source\n")
        original = production._named

        def named(cursor, name):
            if name in names:
                raise AssertionError("private family member was probed")
            return original(cursor, name)

        with patch.object(production, "_named", named):
            _nodes, contents, held = self.capture(project)
        self.assertFalse(names.intersection(contents))
        self.assertIn("environment.py", contents)
        self.assertTrue(
            names.issubset(
                {row["path"] for row in held if row["kind"] == "private-state"}
            )
        )

    def test_source_symlink_target_is_never_opened(self):
        project = self.fixture()
        project.write("target.txt", b"not followed")
        (project.root / "alias.py").symlink_to(project.root / "target.txt")
        original = production._read

        def read(cursor, name, path, before):
            if name == "alias.py":
                raise AssertionError("alias target opened")
            return original(cursor, name, path, before)

        with patch.object(production, "_read", read):
            _nodes, contents, held = self.capture(project)
        self.assertNotIn("alias.py", contents)
        self.assertTrue(
            any(row["path"] == "alias.py" and row["kind"] == "alias" for row in held)
        )

    def test_foreign_device_is_held_before_directory_entry(self):
        project = self.fixture()
        project.write("mounted/secret.py", b"unopened")
        original_named, original_child = production._named, production._child_cursor

        def named(cursor, name):
            value = original_named(cursor, name)
            if name != "mounted":
                return value
            attributes = {
                key: getattr(value, key)
                for key in (
                    "st_dev",
                    "st_ino",
                    "st_mode",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                    "st_nlink",
                )
            }
            attributes["st_dev"] += 1
            return SimpleNamespace(
                **attributes
            )  # explicit modeled native metadata boundary

        def child(cursor, name, path, expected):
            if name == "mounted":
                raise AssertionError("foreign mount entered")
            return original_child(cursor, name, path, expected)

        with (
            patch.object(production, "_named", named),
            patch.object(production, "_child_cursor", child),
        ):
            _nodes, contents, held = self.capture(project)
        self.assertNotIn("mounted/secret.py", contents)
        self.assertTrue(
            any(row["path"] == "mounted" and row["kind"] == "mount" for row in held)
        )

    def test_large_sparse_file_is_not_opened(self):
        project = self.fixture()
        with (project.root / "large.bin").open("wb") as stream:
            stream.truncate(production._MAX_FILE + 1)
        original = production._read

        def read(cursor, name, path, before):
            if name == "large.bin":
                raise AssertionError("large source opened")
            return original(cursor, name, path, before)

        with patch.object(production, "_read", read):
            _nodes, contents, held = self.capture(project)
        self.assertNotIn("large.bin", contents)
        self.assertTrue(
            any(
                row["path"] == "large.bin" and row["kind"] == "byte-bound"
                for row in held
            )
        )

    def test_independent_git_subtree_is_not_read(self):
        project = self.fixture()
        project.write("child/.git", b"gitdir: not opened\n")
        project.write("child/source.py", b"not opened")
        original = production._named

        def named(cursor, name):
            if name in {".git", "source.py"}:
                raise AssertionError("independent repository contents probed")
            return original(cursor, name)

        with patch.object(production, "_named", named):
            _nodes, contents, held = self.capture(project)
        self.assertNotIn("child/source.py", contents)
        self.assertTrue(
            any(
                row["path"] == "child" and row["kind"] == "independent-git"
                for row in held
            )
        )

    @unittest.skipIf(
        os.name == "nt", "POSIX fd boundary; Windows native protocol separate"
    )
    def test_file_mutation_during_actual_descriptor_read_refuses(self):
        project = self.fixture()
        original = os.fstat
        changed = False

        def fstat(descriptor):
            nonlocal changed
            value = original(descriptor)
            if stat.S_ISREG(value.st_mode) and not changed:
                changed = True
                # Test owns all fixture sources; force actual current bytes/stat
                # divergence at a real descriptor boundary, no process execution.
                for path in (
                    project.root / "application/main.py",
                    project.root / "docs/guide.md",
                    project.root / "skills/demo/SKILL.md",
                ):
                    path.write_bytes(path.read_bytes() + b"changed\n")
            return value

        with patch.object(os, "fstat", fstat):
            with self.assertRaises(ProjectLayoutPlanError):
                self.capture(project)
        self.assertTrue(changed)

    @unittest.skipIf(
        os.name == "nt", "POSIX fd cleanup; Windows native handles separate"
    )
    def test_owned_descriptors_close_on_original_read_refusal(self):
        project = self.fixture()
        opened = set()
        actual_open, actual_close = os.open, os.close

        def open_file(*args, **kwargs):
            value = actual_open(*args, **kwargs)
            opened.add(value)
            return value

        def close_file(value):
            opened.discard(value)
            return actual_close(value)

        refusal = ProjectLayoutPlanError("controlled", "original read refused")
        with (
            patch.object(os, "open", open_file),
            patch.object(os, "close", close_file),
            patch.object(production, "_read", side_effect=refusal),
        ):
            with self.assertRaises(ProjectLayoutPlanError) as raised:
                self.capture(project)
        self.assertIs(raised.exception, refusal)
        self.assertEqual(opened, set())

    def test_windows_directory_protocol_uses_no_reparse_delete_denial_and_closes(self):
        from literate_ai import _cache_lock

        project = self.fixture()
        opened, closed = [], []

        class Kernel:
            def open_reparse_aware(self, path, *, share_delete, share_write):
                self_test.assertFalse(share_delete)
                self_test.assertTrue(share_write)
                opened.append(path)
                return len(opened)

            def close(self, handle):
                closed.append(handle)

        self_test = self
        expected = production._identity(project.root.lstat())
        with patch.object(
            _cache_lock, "_default_windows_kernel32", return_value=Kernel()
        ):
            with production._windows_directory(project.root, expected):
                self.assertTrue(opened)
        self.assertEqual(closed, list(reversed(range(1, len(opened) + 1))))

    def test_windows_cleanup_refusal_preserves_original_body_error(self):
        from literate_ai import _cache_lock

        project = self.fixture()
        primary = RuntimeError("original source refused")
        handles = []

        class Kernel:
            def open_reparse_aware(self, *_args, **_kwargs):
                handles.append(len(handles) + 1)
                return handles[-1]

            def close(self, _handle):
                raise OSError("modeled native close refusal")

        with patch.object(
            _cache_lock, "_default_windows_kernel32", return_value=Kernel()
        ):
            with self.assertRaises(RuntimeError) as raised:
                with production._windows_directory(
                    project.root, production._identity(project.root.lstat())
                ):
                    raise primary
        self.assertIs(raised.exception, primary)
