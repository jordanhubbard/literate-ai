"""Actual release-note files and native readers; provider writes are explicit seams."""

import hashlib
import os
import shutil
import subprocess
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai import project_releases as release
from literate_ai.adapters.project_runtime import (
    ProjectRuntimeError,
    allocate_project_runtime,
    close_project_runtime,
    project_runtime_scope,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_runtime_cli as fixture

TEXT = "# Fixture release\n\nOriginal Unicode notes: \u03bb\n"


class ReaderComplete(Exception):
    pass


class ContainedReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ProjectLayoutRuntimeCliTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.project.root
        self.owner = allocate_project_runtime(self.f.project, nested=True)
        self.addCleanup(self.close)

    def close(self):
        if self.owner is not None:
            owner, self.owner = self.owner, None
            close_project_runtime(owner, keep=False)

    def consume(self, path):
        command = [
            sys.executable,
            "-I",
            "-c",
            "import hashlib,pathlib,sys;"
            "data=pathlib.Path(sys.argv[1]).read_bytes();"
            "assert hashlib.sha256(data).hexdigest()==sys.argv[2]",
            str(path),
            hashlib.sha256(TEXT.encode()).hexdigest(),
        ]
        result = subprocess.run(command, capture_output=True, timeout=10, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_tested_provider_notes_are_contained(self):
        seen = {}

        def provider(root, arguments):
            self.assertEqual(root, self.root)
            path = Path(arguments[arguments.index("--notes-file") + 1])
            seen["path"] = path
            self.consume(path)
            self.assertTrue(path.is_relative_to(self.f.framework / "_build"), path)
            self.assertEqual(arguments[:3], ["release", "create", "v1.0.0"])
            self.assertIn("--draft", arguments)
            raise ReaderComplete()

        # Only external provider observation/write and note content are supplied.
        # Original caller, actual stage, project/runtime owner and local reader execute.
        with project_runtime_scope(self.owner, self.f.project):
            with (
                patch.object(release, "_read_tested_github_release", return_value=None),
                patch.object(release, "_tested_release_notes", return_value=TEXT),
                patch.object(release, "_strict_github_write", side_effect=provider),
            ):
                with self.assertRaises(ReaderComplete):
                    release._publish_tested_github_release(
                        self.root,
                        SimpleNamespace(
                            provider_repository="fixture/repository",
                            version_scheme="semver",
                        ),
                        {
                            "tag": "v1.0.0",
                            "version": "1.0.0",
                            "prepared_revision": "0" * 40,
                        },
                        {"files": [{}]},
                        self.root / "unused-qualified-fixture",
                        revalidate=lambda: None,
                    )
        self.assertFalse(seen["path"].exists())

    def test_original_utf8_writer_and_actual_reader_retire_together(self):
        with project_runtime_scope(self.owner, self.f.project):
            with release._release_notes_file(self.root, TEXT) as path:
                self.assertTrue(path.is_relative_to(self.f.framework / "_build"))
                self.consume(path)
        self.assertFalse(path.exists())

    def test_private_note_namespace_survives_refused_parent_runtime_close(self):
        seen = {}
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                with release._release_notes_file(self.root, TEXT) as path:
                    self.consume(path)
                    private = path.parent / "operator-private"
                    private.write_bytes(b"retain private release note state")
                    seen.update(path=private, inode=private.stat().st_ino)
        self.assertEqual(caught.exception.code, "release.notes_staging_unavailable")
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
        self.assertEqual(
            seen["path"].read_bytes(), b"retain private release note state"
        )

    @unittest.skipUnless(os.name == "posix", "POSIX note replacement control")
    def test_equal_byte_foreign_notes_do_not_inherit_creator_custody(self):
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                with release._release_notes_file(self.root, TEXT) as path:
                    original = path.with_name("retained-original")
                    path.rename(original)
                    shutil.copyfile(original, path)
                    before = original.stat().st_ino
                    foreign = path.stat().st_ino
        self.assertEqual(caught.exception.code, "release.notes_staging_unavailable")
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertNotEqual(before, foreign)
        self.assertEqual(path.stat().st_ino, foreign)
        self.assertEqual(original.stat().st_ino, before)
        self.assertEqual(path.read_bytes(), original.read_bytes())

    def test_original_provider_rejection_wins_over_private_disposal_conflict(self):
        rejected = release.ProjectReleaseError(
            "release.provider_fixture_rejection", "original fixture rejection"
        )
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                with release._release_notes_file(self.root, TEXT) as path:
                    self.consume(path)
                    private = path.parent / "operator-private"
                    private.write_bytes(b"retain rejected provider notes")
                    inode = private.stat().st_ino
                    raise rejected
        self.assertIs(caught.exception, rejected)
        self.assertTrue(any("disposal refused" in note for note in rejected.__notes__))
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"retain rejected provider notes")

    def test_original_physical_consumer_error_keeps_its_identity(self):
        rejected = OSError("original physical consumer failure")
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(OSError) as caught:
                with release._release_notes_file(self.root, TEXT) as path:
                    self.consume(path)
                    raise rejected
        self.assertIs(caught.exception, rejected)
        self.assertFalse(path.exists())

    def test_fresh_standalone_notes_use_actual_declared_project(self):
        self.close()
        with release._release_notes_file(self.root, TEXT) as path:
            self.assertTrue(path.is_relative_to(self.f.framework / "_build"))
            self.consume(path)
        self.assertFalse(path.exists())

    def test_other_project_runtime_cannot_supply_notes_stage(self):
        other = self.root.parent / "foreign-notes-project"
        ProjectConfigurationStore(other).create(
            replace(self.f.project.definition, project_id="foreign-notes-project")
        )
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                with release._release_notes_file(other, TEXT):
                    self.fail("foreign project notes stage was admitted")
        self.assertEqual(caught.exception.code, "release.notes_staging_unavailable")
        self.assertFalse((other / "litai/_build").exists())

    def test_00_framework_root_consumer_error_keeps_original_identity(self):
        root = self.root.parent / "root-authoring-notes"
        root.mkdir()
        for rejected in (
            OSError("original authoring consumer error"),
            RuntimeError("original authoring runtime error"),
        ):
            with self.subTest(type=type(rejected).__name__):
                with self.assertRaises(type(rejected)) as caught:
                    with release._release_notes_file(root, TEXT) as path:
                        self.consume(path)
                        raise rejected
                self.assertIs(caught.exception, rejected)
                self.assertFalse(path.exists())
