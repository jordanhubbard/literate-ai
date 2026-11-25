"""Original registered rebind controls in a declared contained metadata context."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import native_project_updates as updates
from literate_ai.application.standard_lifecycle_rebind import (
    StandardLifecycleRebindError,
)
from tests.smoke import test_native_project_updates as original
from tests.support.fixtures_test_repository_orchestration import snapshot


class ContainedNativeProjectUpdateTests(original.NativeProjectUpdateTests):
    framework_directory = "litai"

    def test_00_original_rebind_accepts_declared_framework_coordinates(self):
        parent = self.parent / "litai"
        child = self.child / "litai"
        plan = updates.plan_registered_standard_rebind(parent, child, **self.observers)
        self.assertEqual(plan["schema"], "literate-ai/registered-child-rebind-plan@2")
        self.assertEqual(
            plan["registration"]["child_path"],
            self.child.relative_to(self.parent).as_posix(),
        )
        result = updates.apply_registered_standard_rebind(
            parent, child, plan, authorize_rebind=True, **self.observers
        )
        self.assertTrue(
            result["recovery"]["path"].startswith("litai/.literate/native-updates/")
        )
        self.assertTrue((self.parent / result["recovery"]["path"]).is_file())
        self.assertEqual(updates.registered_parent_for_child(child), self.parent)

    def test_private_application_metadata_is_not_read_or_written(self):
        private = self.parent / ".literate"
        private.mkdir()
        (private / "native-projects.json").write_bytes(b"private registry fixture")
        (private / "native-updates").mkdir()
        (private / "native-updates/private").write_bytes(b"private history fixture")
        before = snapshot(private)
        self.apply(self.plan())
        self.assertEqual(snapshot(private), before)

    def test_application_metadata_alias_is_not_opened(self):
        private = self.parent / ".literate"
        target = self.parent.parent / "private-metadata"
        target.mkdir()
        (target / "private").write_bytes(b"private fixture")
        private.symlink_to(target, target_is_directory=True)
        before = snapshot(target)
        original_open = Path.open

        def guard(path, *args, **kwargs):
            if path == private or path.is_relative_to(private):
                raise AssertionError("application metadata alias opened")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", guard):
            self.apply(self.plan())
        self.assertTrue(private.is_symlink())
        self.assertEqual(snapshot(target), before)

    def test_framework_changed_during_capture_refuses(self):
        original_roots = updates._native_project_roots
        retained = self.parent.parent / "original-framework"

        def replace(parent):
            roots = original_roots(parent)
            self.framework.rename(retained)
            shutil.copytree(retained, self.framework, symlinks=True)
            return roots

        with patch.object(updates, "_native_project_roots", replace):
            with self.assertRaises(StandardLifecycleRebindError):
                self.plan()
        self.assertTrue((retained / "literate.project.json").is_file())

    def test_reviewed_plan_cannot_cross_equal_byte_framework_replacement(self):
        plan = self.plan()
        retained = self.parent.parent / "original-framework"
        self.framework.rename(retained)
        shutil.copytree(retained, self.framework, symlinks=True)
        current = self.plan()
        self.assertNotEqual(plan["registration"], current["registration"])
        before = snapshot(self.parent)
        with self.assertRaises(StandardLifecycleRebindError):
            self.apply(plan)
        self.assertEqual(snapshot(self.parent), before)
