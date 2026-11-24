"""Owned-temp no-follow context ordering; no protected/NAS targets or native claims."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.contracts import canonical_json_bytes
from literate_ai.projects import (
    PROJECT_FILENAME,
    ProjectConfigurationStore,
    ProjectError,
)


class ProjectContextNoFollowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name).resolve()
        self.root = self.parent / "app"
        self.root.mkdir()
        self.definition = json.loads(
            (Path(__file__).resolve().parents[2] / PROJECT_FILENAME).read_bytes()
        )

    def manifest(self, directory, contained):
        directory.mkdir(parents=True, exist_ok=True)
        value = dict(self.definition)
        value.pop("framework_directory", None)
        if contained:
            value["framework_directory"] = "litai"
        (directory / PROJECT_FILENAME).write_bytes(canonical_json_bytes(value) + b"\n")

    @contextmanager
    def prohibit_target_probe(self, alias):
        original = Path.stat
        probes = []

        def checked(path, *, follow_symlinks=True):
            if (path == alias and follow_symlinks) or (
                path != alias and path.is_relative_to(alias)
            ):
                probes.append(str(path))
                raise AssertionError("redirected ancestry was probed")
            return original(path, follow_symlinks=follow_symlinks)

        with patch.object(Path, "stat", checked):
            yield probes

    def symlink(self, path, target):
        try:
            path.symlink_to(target, target_is_directory=True)
        except OSError as error:
            if os.name == "nt":
                self.skipTest(f"native symlink privilege unavailable: {error}")
            raise

    def test_contained_alias_refuses_before_any_target_stat_or_manifest_probe(self):
        outside = self.parent / "owned-outside"
        self.manifest(outside, True)
        alias = self.root / "litai"
        self.symlink(alias, outside)
        with self.prohibit_target_probe(alias) as probes:
            with self.assertRaises(ProjectError) as caught:
                ProjectConfigurationStore.context(self.root)
        self.assertEqual(caught.exception.code, "project.framework_directory_unsafe")
        self.assertEqual(probes, [])

    def test_entry_named_litai_alias_refuses_before_direct_manifest_stat(self):
        outside = self.parent / "owned-outside"
        self.manifest(outside, True)
        alias = self.root / "litai"
        self.symlink(alias, outside)
        with self.prohibit_target_probe(alias) as probes:
            with self.assertRaises(ProjectError):
                ProjectConfigurationStore.context(alias)
        self.assertEqual(probes, [])

    def test_contained_project_does_not_inspect_unrelated_application_metadata(self):
        self.manifest(self.root / "litai", True)
        outside = self.parent / "owned-application-state"
        outside.mkdir()
        alias = self.root / ".literate"
        self.symlink(alias, outside)
        original = Path.lstat
        calls = []

        def lstat(path):
            if path == alias or path.is_relative_to(alias):
                calls.append(path)
                raise AssertionError("application-owned unrelated metadata inspected")
            return original(path)

        with patch.object(Path, "lstat", lstat):
            context = ProjectConfigurationStore.context(self.root)
        self.assertEqual(context.framework_root, self.root / "litai")
        self.assertEqual(calls, [])

    def test_legacy_marker_unsafe_ancestry_refuses_without_target_probe(self):
        self.manifest(self.root, False)
        outside = self.parent / "owned-outside"
        outside.mkdir()
        alias = self.root / ".literate"
        self.symlink(alias, outside)
        with self.prohibit_target_probe(alias) as probes:
            with self.assertRaises(ProjectError):
                ProjectConfigurationStore.context(self.root)
        self.assertEqual(probes, [])

    def test_legacy_pending_marker_and_original_writer_bypass(self):
        self.manifest(self.root, False)
        marker = self.root / ".literate/retained-harness-readmission/active.json"
        marker.parent.mkdir(parents=True)
        marker.write_bytes(b"pending data\n")
        with self.assertRaises(ProjectError) as caught:
            ProjectConfigurationStore.context(self.root)
        self.assertEqual(
            caught.exception.code, "project.retained_readmission_recovery_required"
        )
        with patch(
            "literate_ai.projects.scoped_writer_permits_project_read", return_value=True
        ):
            context = ProjectConfigurationStore.context(self.root)
        self.assertEqual(context.framework_root, self.root)
        self.assertEqual(marker.read_bytes(), b"pending data\n")

    def test_independent_child_uses_own_context_not_parent_marker(self):
        self.manifest(self.root, False)
        child = self.root / "litai"
        self.manifest(child, False)
        marker = self.root / ".literate/retained-harness-readmission/active.json"
        marker.parent.mkdir(parents=True)
        marker.write_bytes(b"parent pending\n")
        context = ProjectConfigurationStore.context(child)
        self.assertEqual(context.root, child)
        self.assertEqual(context.framework_root, child)

    def test_unmanaged_metadata_alias_falls_back_without_descent(self):
        outside = self.parent / "owned-state"
        outside.mkdir()
        alias = self.root / ".literate"
        self.symlink(alias, outside)
        with self.prohibit_target_probe(alias) as probes:
            context = ProjectConfigurationStore.context(self.root)
        self.assertEqual(context.root, self.root)
        self.assertEqual(context.framework_root, self.root)
        self.assertEqual(probes, [])

    def test_contained_root_and_descendant_coordinate_have_same_direct_binding(self):
        self.manifest(self.root / "litai", True)
        root_context = ProjectConfigurationStore.context(self.root)
        child_context = ProjectConfigurationStore.context(self.root / "litai")
        self.assertEqual(root_context, child_context)
        self.assertIsNotNone(root_context.directory_binding)

    def test_missing_unmanaged_root_has_no_implicit_directory_creation(self):
        missing = self.parent / "not-created"
        context = ProjectConfigurationStore.context(missing)
        self.assertEqual(context.root, missing)
        self.assertIsNone(context.directory_binding)
        self.assertFalse(missing.exists())
