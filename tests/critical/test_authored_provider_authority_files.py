"""Original provider files using actual authored authority and persisted stores.

No model, native build, SDK, provider replay or consumer admission is qualified.
"""

import copy
import os
import pickle
import shutil
import unittest
from unittest.mock import patch

from literate_ai.adapters.authored_provider_authority_files import (
    _capture_authored_provider_authority_files,
)
from literate_ai.adapters.authored_qualification_authority import (
    CurrentAuthoredQualificationAuthority,
)
from literate_ai.adapters.authority import (
    AuthorityProjectionStoreError,
    FileAuthorityProjectionStore,
)
from literate_ai.adapters.component_lock_planning import (
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
    ComponentResolutionAuditStoreError,
)
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthoritySnapshot,
)
from literate_ai.projects import PinnedInputClosureError, ProjectConfigurationStore
from tests.critical import test_authored_qualification_authority as fixtures


class AuthoredProviderAuthorityFilesTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AuthoredQualificationAuthorityTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.authority = self.fixture.read()

    def capture(self):
        return _capture_authored_provider_authority_files(self.authority)

    def test_original_files_need_no_full_authority_planner_new_store_or_command(self):
        files = self.capture()
        trap = AssertionError(
            "raw authority comparison invoked new authority or commands"
        )
        with (
            patch.object(
                CurrentAuthoredQualificationAuthority,
                "require_unchanged",
                side_effect=trap,
            ),
            patch.object(
                LockedGenerationAuthoritySnapshot, "require_unchanged", side_effect=trap
            ),
            patch.object(
                FilesystemComponentLockPlanner, "plan_snapshot", side_effect=trap
            ),
            patch.object(ComponentLockStore, "__init__", side_effect=trap),
            patch.object(ComponentResolutionAuditStore, "__init__", side_effect=trap),
            patch.object(FileAuthorityProjectionStore, "__init__", side_effect=trap),
            patch("subprocess.run", side_effect=trap),
            patch("subprocess.Popen", side_effect=trap),
        ):
            files.require_original_files()
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(TypeError):
                    operation(files)

    def test_changed_original_selected_authoring_bytes_refuse_and_are_preserved(self):
        files = self.capture()
        path = self.fixture.component / "component.md"
        changed = path.read_bytes() + b"\n"
        path.write_bytes(changed)
        with self.assertRaises(PinnedInputClosureError):
            files.require_original_files()
        self.assertEqual(path.read_bytes(), changed)

    def test_new_unselected_catalog_member_refuses_and_is_preserved(self):
        files = self.capture()
        path = self.fixture.component / "unselected/component.md"
        path.parent.mkdir()
        content = (self.fixture.component / "component.md").read_bytes()
        path.write_bytes(content)
        with self.assertRaises(ComponentLockPlanningError):
            files.require_original_files()
        self.assertEqual(path.read_bytes(), content)

    def test_original_audit_canonical_bytes_remain_required(self):
        files = self.capture()
        path = self.authority.locked._resolution_audit_store.path
        changed = path.read_bytes() + b" "
        path.write_bytes(changed)
        with self.assertRaises(ComponentResolutionAuditStoreError):
            files.require_original_files()
        self.assertEqual(path.read_bytes(), changed)

    def test_selected_source_projection_cannot_appear_after_capture(self):
        files = self.capture()
        coordinate = self.authority.locked.authority.root_authoring.coordinate.uri
        store = FileAuthorityProjectionStore(self.fixture.root)
        store.append(self.fixture.projection(coordinate))
        with self.assertRaisesRegex(ValueError, "source-authority-present"):
            files.require_original_files()
        self.assertIn(coordinate, store.coordinates())

    def test_new_unrelated_projection_preserves_original_selected_absence_semantics(
        self,
    ):
        files = self.capture()
        store = FileAuthorityProjectionStore(self.fixture.root)
        coordinate = "component://unselected/retained"
        store.append(self.fixture.projection(coordinate))
        files.require_original_files()
        self.assertIn(coordinate, store.coordinates())

    def test_same_bytes_in_replaced_original_projection_directory_refuse(self):
        store = FileAuthorityProjectionStore(self.fixture.root)
        store.append(self.fixture.projection("component://unselected/retained"))
        files = self.capture()
        path = self.fixture.root / "provenance/component-authority"
        originals = {p.relative_to(path): p.read_bytes() for p in path.rglob("*.json")}
        moved = path.with_name("component-authority-original")
        path.rename(moved)
        shutil.copytree(moved, path)
        with self.assertRaisesRegex(ValueError, "authority-directory-changed"):
            files.require_original_files()
        for relative, content in originals.items():
            self.assertEqual((path / relative).read_bytes(), content)
            self.assertEqual((moved / relative).read_bytes(), content)

    def test_corrupt_new_unrelated_projection_is_not_reinterpreted_as_absence(self):
        files = self.capture()
        store = FileAuthorityProjectionStore(self.fixture.root)
        store.append(self.fixture.projection("component://unselected/retained"))
        path = next(
            (self.fixture.root / "provenance/component-authority").glob(
                "*/current.json"
            )
        )
        path.write_bytes(b"not JSON")
        with self.assertRaises(AuthorityProjectionStoreError):
            files.require_original_files()
        self.assertEqual(path.read_bytes(), b"not JSON")

    def test_matrix_selector_change_refuses_without_creating_new_storage(self):
        files = self.capture()
        path = self.fixture.root / "new-matrix"
        with patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(path)}):
            with self.assertRaisesRegex(ValueError, "authority-matrix-changed"):
                files.require_original_files()
        self.assertFalse(path.exists())

    def test_new_nested_project_cannot_retarget_original_component_ownership(self):
        files = self.capture()
        ProjectConfigurationStore(self.fixture.component).create(
            self.authority.project.definition
        )
        with self.assertRaisesRegex(ValueError, "authority-project-changed"):
            files.require_original_files()
        self.assertTrue((self.fixture.component / "literate.project.json").is_file())
