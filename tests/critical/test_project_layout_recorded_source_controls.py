"""Actual control-only closing and rollback; historical execution modeled.

The application directory is never a closing object. Native POSIX handles here
are source evidence, not installed or supported-platform release qualification.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from literate_ai.adapters import component_locks
from literate_ai.adapters import project_layout_framework_finalization as finalization
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_source_controls as controls
from literate_ai.adapters import project_layout_framework_transaction as frame
from literate_ai.adapters.component_locks import ComponentLockStoreError
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_cli as support


@unittest.skipUnless(
    os.name == "posix", "actual POSIX control handles; Windows remains required"
)
class RecordedSourceControlTests(unittest.TestCase):
    def fixture(self):
        helper = support.FrameworkMigrationCliTests("runTest")
        self.addCleanup(helper.doCleanups)
        project = helper.fixture()
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        (endpoint,) = selected.component_endpoints
        original = dict(selected.original_contents)
        with ProjectConfigurationStore.layout_lock(project.root):
            frame.apply_framework_authority(selected, public["plan_identity"])
        journal, intent = frame._decode(project.root, public["plan_identity"])
        native = {
            path: (project.root / path).stat().st_ino
            for path in endpoint.coordination_paths
        }
        return project, public, endpoint, original, journal, intent, native

    def finish(self, project, public):
        with ProjectConfigurationStore.layout_lock(project.root):
            return finalization.finalize_framework_components(
                project.root, public["plan_identity"]
            )

    def recover(self, project, public, original, native):
        for _repeat in range(2):
            with ProjectConfigurationStore.layout_lock(project.root):
                self.assertTrue(
                    frame.recover_framework_authority(
                        project.root, public["plan_identity"]
                    )["rolled_back"]
                )
        for path, content in original.items():
            self.assertEqual((project.root / path).read_bytes(), content)
        for path, inode in native.items():
            self.assertEqual((project.root / path).stat().st_ino, inode)

    def test_actual_controls_close_restart_and_restore_without_app_directory_move(self):
        project, public, endpoint, original, journal, intent, before = self.fixture()
        source = project.root / endpoint.source_root
        implementation = source / "implementation/main.py"
        private = source / ".env"
        private.write_bytes(b"synthetic private fixture, never credentials\n")
        nodes = source.stat().st_ino, implementation.stat().st_ino
        history = (journal / "intent.json").read_bytes()
        real = controls.os.open
        opened = []

        def guarded(path, *args, **kwargs):
            if str(path) in (str(private), private.name):
                opened.append(path)
                raise AssertionError("application private file opened")
            return real(path, *args, **kwargs)

        with patch.object(controls.os, "open", guarded):
            for _restart in range(2):
                result = self.finish(project, public)
                self.assertTrue(result["components_finalized"])
                self.assertFalse(result["full_containment"])
                self.assertEqual(result["normal_producers"], [])
        self.assertEqual(opened, [])
        self.assertEqual((source.stat().st_ino, implementation.stat().st_ino), nodes)
        self.assertEqual((journal / "intent.json").read_bytes(), history)
        ((record, path, rows),) = controls.records(project.root, journal, intent)
        self.assertTrue(all(archived for _, _, archived in rows))
        self.assertEqual(record["source_root"], endpoint.source_root)
        for coordinate, actual, _archived in rows:
            self.assertEqual(actual.stat().st_ino, before[coordinate])
            self.assertFalse((project.root / coordinate).exists())
        with patch.object(
            component_locks,
            "exclusive_cache_lock",
            side_effect=AssertionError("retired normal store creating open"),
        ) as opener:
            with self.assertRaises(ComponentLockStoreError):
                with endpoint.original_lock_store.operation():
                    self.fail("retired original store accepted")
        opener.assert_not_called()
        self.assertTrue(all(not (project.root / name).exists() for name in before))
        self.recover(project, public, original, before)
        self.assertEqual(
            private.read_bytes(), b"synthetic private fixture, never credentials\n"
        )
        self.assertEqual((source.stat().st_ino, implementation.stat().st_ino), nodes)

    def test_equal_byte_foreign_control_does_not_replace_archived_inode(self):
        project, public, endpoint, original, journal, intent, before = self.fixture()
        self.finish(project, public)
        ((record, _path, rows),) = controls.records(project.root, journal, intent)
        coordinate, archive, _ = rows[0]
        foreign = project.root / coordinate
        payload = archive.read_bytes()
        foreign.write_bytes(payload)
        node = foreign.stat().st_ino
        with self.assertRaises(ProjectLayoutPlanError):
            self.finish(project, public)
        self.assertEqual(foreign.read_bytes(), payload)
        self.assertEqual(foreign.stat().st_ino, node)
        self.assertEqual(archive.stat().st_ino, before[coordinate])
        foreign.unlink()  # only this test's synthetic foreign leaf
        self.recover(project, public, original, before)

    def test_new_source_git_boundary_refuses_before_control_archive_creation(self):
        project, public, endpoint, original, journal, intent, before = self.fixture()
        boundary = project.root / endpoint.source_root / ".git"
        boundary.mkdir()
        path = controls._path(
            project.root,
            controls._expected(project.root, intent, intent["components"][0]),
        )
        with self.assertRaises(ProjectLayoutPlanError):
            self.finish(project, public)
        self.assertFalse(path.exists())
        for coordinate, inode in before.items():
            self.assertEqual((project.root / coordinate).stat().st_ino, inode)
        boundary.rmdir()  # only this test's synthetic marker
        self.recover(project, public, original, before)
