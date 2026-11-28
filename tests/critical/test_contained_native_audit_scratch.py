"""Original registry/history with actual audit copies and an explicit verifier port."""

from __future__ import annotations

import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import native_child_replacement as audit
from literate_ai.adapters import native_project_updates as updates
from literate_ai.contracts import canonical_identity
from literate_ai.projects import ProjectConfigurationStore, load_project
from literate_ai.source_to_specification.promotion_materialization import (
    SourcePromotionError,
)
from tests.smoke import test_native_project_updates as original
from tests.support.fixtures_test_repository_orchestration import snapshot


class ContainedNativeAuditScratchTests(unittest.TestCase):
    def fixture(self, *, contained=True):
        f = original.NativeProjectUpdateTests("runTest")
        f.framework_directory = "litai" if contained else None
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f = f
        self.views = []
        (f.child / "empty").mkdir()
        (f.child / "tool").write_bytes(b"not executed audit fixture\n")
        (f.child / "tool").chmod(0o755)
        (f.child / "readonly").write_bytes(b"read only audit fixture\n")
        (f.child / "readonly").chmod(0o444)
        self.projection = SimpleNamespace(
            identity=canonical_identity({"fixture": "audit-projection"})
        )
        return f

    def observe(self, view, projection):
        self.assertIs(projection, self.projection)
        self.views.append(view)
        self.assertEqual((view / "tool").read_bytes(), b"not executed audit fixture\n")
        self.assertTrue((view / "empty").is_dir())

    def run_audit(self, verify=None):
        captured = updates._capture(self.f.parent, self.f.child)
        with (
            patch.object(audit, "_unqualified", return_value=(self.projection,)),
            patch.object(
                audit,
                "verify_source_promotion_evidence",
                side_effect=verify or self.observe,
            ),
        ):
            return audit._promotion_custody(captured, audit._tree(self.f.child))

    def test_00_actual_copy_is_contained_and_original_child_bytes_modes_are_unchanged(
        self,
    ):
        f = self.fixture()
        before = snapshot(f.child)
        result = self.run_audit()
        self.assertEqual(result["historical_rebind_records"], [])
        self.assertTrue(self.views[0].is_relative_to(f.framework / "_build"))
        self.assertFalse(self.views[0].parent.exists())
        self.assertEqual(snapshot(f.child), before)
        self.assertEqual(stat.S_IMODE((f.child / "tool").stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((f.child / "readonly").stat().st_mode), 0o444)

    def test_each_actual_recorded_historical_candidate_gets_a_fresh_owned_view(self):
        f = self.fixture()
        old = f.manifest.read_bytes()
        f.apply(f.plan())
        current = f.manifest.read_bytes()
        self.assertNotEqual(old, current)
        before = snapshot(f.child)

        def verify(view, projection):
            self.observe(view, projection)
            manifest = ProjectConfigurationStore.manifest_path(view).read_bytes()
            if manifest == current:
                raise SourcePromotionError(
                    "fixture.current-audit-rejected", "original fixture rejection"
                )
            self.assertEqual(manifest, old)

        result = self.run_audit(verify)
        self.assertEqual(len(result["historical_rebind_records"]), 1)
        self.assertEqual(len(self.views), 2)
        self.assertNotEqual(self.views[0], self.views[1])
        self.assertTrue(all(not view.parent.exists() for view in self.views))
        self.assertEqual(snapshot(f.child), before)

    def test_original_verification_error_survives_normal_disposal(self):
        self.fixture()
        error = SourcePromotionError(
            "fixture.original-rejection", "original fixture rejection"
        )

        def reject(view, projection):
            self.observe(view, projection)
            raise error

        with self.assertRaises(SourcePromotionError) as caught:
            self.run_audit(reject)
        self.assertIs(caught.exception, error)
        self.assertFalse(self.views[0].parent.exists())

    def test_unknown_private_entry_retains_original_error_and_stops_history_fallback(
        self,
    ):
        f = self.fixture()
        f.apply(f.plan())
        private = []
        error = SourcePromotionError(
            "fixture.original-rejection", "original fixture rejection"
        )

        def reject(view, projection):
            self.observe(view, projection)
            private.append(view.parent / "private")
            private[-1].write_bytes(b"private fixture")
            raise error

        read = Path.read_bytes

        def guarded(path):
            if path in private:
                raise AssertionError("private payload read")
            return read(path)

        with patch.object(Path, "read_bytes", guarded):
            with self.assertRaises(SourcePromotionError) as caught:
                self.run_audit(reject)
        self.assertIs(caught.exception, error)
        self.assertEqual(len(self.views), 1)
        self.assertTrue(
            any("retained" in note for note in getattr(error, "__notes__", ()))
        )
        self.assertEqual(private[0].read_bytes(), b"private fixture")
        self.assertTrue((self.views[0] / "tool").exists())

    def test_equal_byte_foreign_snapshot_is_preserved_and_refuses_success(self):
        f = self.fixture()
        replacements = []

        def replace(view, projection):
            self.observe(view, projection)
            path = view / "tool"
            path.rename(f.parent.parent / "original-audit-tool")
            path.write_bytes(b"not executed audit fixture\n")
            replacements.append((path, path.stat().st_ino))

        with self.assertRaises(audit.NativeChildReplacementError):
            self.run_audit(replace)
        self.assertEqual(replacements[0][0].stat().st_ino, replacements[0][1])
        self.assertTrue((f.parent.parent / "original-audit-tool").exists())

    def test_actual_current_runtime_is_reused_without_reacquiring_its_lock(self):
        from literate_ai.adapters.project_runtime import (
            allocate_project_runtime,
            close_project_runtime,
            project_runtime_scope,
        )

        f = self.fixture()
        project = load_project(f.parent)
        owner = allocate_project_runtime(project, nested=True)
        runtime = owner.path
        try:
            with project_runtime_scope(owner, project):
                self.run_audit()
                self.assertTrue(self.views[0].is_relative_to(runtime))
        finally:
            close_project_runtime(owner, keep=False)
        self.assertFalse(runtime.parent.exists())

    def test_unsafe_object_parent_refuses_without_touching_alias_target(self):
        f = self.fixture()
        private = f.parent.parent / "private-cache"
        private.mkdir()
        (f.framework / "_build").symlink_to(private, target_is_directory=True)
        with self.assertRaises(audit.NativeChildReplacementError):
            self.run_audit()
        self.assertEqual(self.views, [])
        self.assertEqual(list(private.iterdir()), [])

    def test_framework_replacement_during_verification_keeps_original_error(self):
        import shutil

        from literate_ai.application.standard_lifecycle_rebind import (
            StandardLifecycleRebindError,
        )

        f = self.fixture()
        original_framework = f.parent.parent / "original-framework"

        def replace(view, projection):
            self.observe(view, projection)
            f.framework.rename(original_framework)
            shutil.copytree(original_framework, f.framework)

        with self.assertRaises(StandardLifecycleRebindError):
            self.run_audit(replace)
        self.assertTrue(original_framework.is_dir())

    def test_inspection_copy_is_private_inert_and_live_modes_remain_original(self):
        f = self.fixture()
        before = snapshot(f.child)

        def verify(view, projection):
            self.observe(view, projection)
            self.assertEqual(stat.S_IMODE((view / "tool").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((view / "empty").stat().st_mode), 0o700)
            self.assertEqual(
                (view / "readonly").read_bytes(), (f.child / "readonly").read_bytes()
            )

        self.run_audit(verify)
        self.assertEqual(snapshot(f.child), before)

    def test_equal_byte_parent_manifest_replacement_revokes_original_inspection(self):
        f = self.fixture()
        manifest = ProjectConfigurationStore.manifest_path(f.parent)
        original = f.parent.parent / "original-parent-manifest"

        def replace(view, projection):
            self.observe(view, projection)
            manifest.rename(original)
            manifest.write_bytes(original.read_bytes())

        with self.assertRaises(audit.NativeChildReplacementError):
            self.run_audit(replace)
        self.assertEqual(manifest.read_bytes(), original.read_bytes())
        self.assertNotEqual(manifest.stat().st_ino, original.stat().st_ino)

    def test_legacy_audit_keeps_original_host_temporary_placement(self):
        f = self.fixture(contained=False)
        before = snapshot(f.child)
        self.run_audit()
        self.assertFalse(self.views[0].is_relative_to(f.parent))
        self.assertFalse(self.views[0].parent.exists())
        self.assertEqual(snapshot(f.child), before)
