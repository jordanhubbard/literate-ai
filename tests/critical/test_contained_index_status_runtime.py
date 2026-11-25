"""Real SQLite/source shadow custody with an explicit fixture status-command port."""

from __future__ import annotations

import sqlite3

# Reuse the original ordinary project fixture, not its test cases.
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.project_source_index import (
    ProjectSourceIntelligenceError,
    _CodeGraphCommandEngine,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_contained_project_source_index as original


class ContainedIndexStatusRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = original.ContainedProjectSourceIndexTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.shadows = []

    def project(self, *, contained=True):
        self.fixture._project(contained=contained)
        metadata = "litai" if contained else ".codegraph"
        directory = self.root / metadata
        directory.mkdir(exist_ok=True)
        with sqlite3.connect(directory / "codegraph.db") as connection:
            connection.execute("CREATE TABLE fixture(value TEXT)")
            connection.execute("INSERT INTO fixture VALUES ('original index')")
        (self.root / "sample.py").write_bytes(b"answer = 42\n")
        self.engine = _CodeGraphCommandEngine(
            "fixture-not-executed", timeout_seconds=60, metadata_directory=metadata
        )

    def status(self, shadow):
        self.shadows.append(shadow)
        self.assertEqual((shadow / "sample.py").read_bytes(), b"answer = 42\n")
        with sqlite3.connect(
            (shadow / self.engine.metadata_directory / "codegraph.db").as_uri()
            + "?mode=ro",
            uri=True,
        ) as connection:
            self.assertEqual(
                connection.execute("SELECT value FROM fixture").fetchone(),
                ("original index",),
            )
        return dict(
            initialized=True,
            projectPath=str(shadow),
            indexPath=str(shadow / self.engine.metadata_directory),
            version="1.6.0",
            pendingChanges=dict(added=0, modified=0, removed=0),
            worktreeMismatch=None,
            fileCount=1,
            nodeCount=1,
            edgeCount=0,
            index=dict(
                builtWithVersion="1.6.0",
                builtWithExtractionVersion=1,
                currentExtractionVersion=1,
                reindexRecommended=False,
            ),
        )

    def capture(self, callback=None):
        with (
            patch.object(
                self.engine, "preflight", return_value=("1.6.0", "sha256:" + "a" * 64)
            ),
            patch.object(self.engine, "_git_visible_paths", return_value=None),
            patch.object(self.engine, "_status", side_effect=callback or self.status),
            patch.object(
                self.engine,
                "_run",
                side_effect=AssertionError("fixture must not execute CodeGraph"),
            ),
        ):
            return self.engine.capture(self.root, synchronize=False)

    def test_00_actual_status_shadow_is_under_selected_contained_object_state(self):
        self.project()
        result = self.capture()
        self.assertEqual(result.file_count, 1)
        self.assertTrue(self.shadows[0].is_relative_to(self.root / "litai/_build"))
        self.assertFalse(self.shadows[0].parent.exists())
        self.assertEqual(
            sorted(p.name for p in self.root.iterdir()), ["litai", "sample.py"]
        )

    def test_original_status_error_survives_normal_owned_disposal(self):
        self.project()
        error = RuntimeError("original fixture status rejection")

        def reject(shadow):
            self.status(shadow)
            raise error

        with self.assertRaises(RuntimeError) as caught:
            self.capture(reject)
        self.assertIs(caught.exception, error)
        self.assertFalse(self.shadows[0].parent.exists())

    def test_unknown_private_entry_is_retained_without_payload_read(self):
        self.project()
        error = RuntimeError("original fixture status rejection")
        private = []

        def reject(shadow):
            self.status(shadow)
            private.append(shadow.parent / "private")
            private[0].write_bytes(b"private fixture")
            raise error

        read = Path.read_bytes

        def guarded(path):
            if path in private:
                raise AssertionError("private payload read")
            return read(path)

        with patch.object(Path, "read_bytes", guarded):
            with self.assertRaises(RuntimeError) as caught:
                self.capture(reject)
        self.assertIs(caught.exception, error)
        self.assertTrue(
            any("retained" in note for note in getattr(error, "__notes__", ()))
        )
        self.assertEqual(private[0].read_bytes(), b"private fixture")
        self.assertTrue((self.shadows[0] / "sample.py").exists())

    def test_equal_byte_foreign_snapshot_replacement_refuses_disposal(self):
        self.project()
        replacement = []

        def replace(shadow):
            result = self.status(shadow)
            source = shadow / "sample.py"
            before = source.stat().st_ino
            source.rename(self.root / "litai/saved-original-snapshot")
            source.write_bytes(b"answer = 42\n")
            self.assertNotEqual(before, source.stat().st_ino)
            replacement.append((source, source.stat().st_ino))
            return result

        with self.assertRaises(ProjectSourceIntelligenceError):
            self.capture(replace)
        self.assertEqual(replacement[0][0].stat().st_ino, replacement[0][1])
        self.assertTrue((self.root / "litai/saved-original-snapshot").exists())

    def test_status_created_provider_sidecar_is_not_implicitly_adopted_for_cleanup(
        self,
    ):
        self.project()
        sidecars = []

        def extra(shadow):
            result = self.status(shadow)
            sidecars.append(shadow / self.engine.metadata_directory / "errors.log")
            sidecars[0].write_bytes(b"fixture provider output")
            return result

        with self.assertRaises(ProjectSourceIntelligenceError):
            self.capture(extra)
        self.assertEqual(sidecars[0].read_bytes(), b"fixture provider output")

    def test_original_project_guard_rejects_status_time_manifest_change(self):
        self.project()

        def change(shadow):
            from dataclasses import replace

            result = self.status(shadow)
            store = ProjectConfigurationStore(self.root)
            current = store.read()
            store.update(current, replace(current.definition, version="99.0.0"))
            return result

        with self.assertRaises(ProjectSourceIntelligenceError) as caught:
            self.capture(change)
        self.assertEqual(
            caught.exception.code, "project.source_intelligence_context_changed"
        )

    def test_unsafe_contained_object_ancestor_refuses_before_status_or_target_reads(
        self,
    ):
        self.project()
        target = self.root / "private-cache"
        target.mkdir()
        (self.root / "litai/_build").symlink_to(target, target_is_directory=True)
        with self.assertRaises(ProjectSourceIntelligenceError) as caught:
            self.capture()
        self.assertEqual(
            caught.exception.code, "project.source_intelligence_path_unsafe"
        )
        self.assertEqual(self.shadows, [])
        self.assertEqual(list(target.iterdir()), [])

    def test_actual_current_runtime_is_reused_without_reacquiring_its_cache_lock(self):
        from literate_ai.adapters.project_runtime import (
            allocate_project_runtime,
            close_project_runtime,
            project_runtime_scope,
        )
        from literate_ai.projects import load_project

        self.project()
        project = load_project(self.root)
        owner = allocate_project_runtime(project, nested=True)
        runtime = owner.path
        try:
            with project_runtime_scope(owner, project):
                result = self.capture()
                self.assertEqual(result.file_count, 1)
                self.assertTrue(self.shadows[0].is_relative_to(runtime))
                self.assertFalse(self.shadows[0].parent.exists())
        finally:
            close_project_runtime(owner, keep=False)
        self.assertFalse(runtime.parent.exists())

    def test_legacy_status_keeps_original_temporary_workspace_behavior(self):
        self.project(contained=False)
        result = self.capture()
        self.assertEqual(result.file_count, 1)
        self.assertFalse(self.shadows[0].is_relative_to(self.root))
        self.assertFalse(self.shadows[0].parent.exists())
