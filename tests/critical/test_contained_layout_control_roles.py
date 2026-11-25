"""Default conversion's actual contained metadata owns retained-layout controls."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_layout_control_roles as roles
from literate_ai.adapters.conversion_authority import CONVERSION_AUTHORITY_FILE
from literate_ai.projects import (
    PROJECT_FILENAME,
    ProjectConfigurationStore,
    ProjectError,
)
from tests.critical import test_retained_layout_control_roles as legacy
from tests.support.fixtures_test_retained_harness_receipts import (
    _adapter,
    _legacy_project,
    _selectors,
)


@unittest.skipUnless(os.name == "posix", "POSIX staged role acquisition dependency")
class ContainedLayoutControlRoleTests(unittest.TestCase):
    setUp = legacy.RetainedLayoutControlRoleTests.setUp
    pool = legacy.RetainedLayoutControlRoleTests.pool

    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="contained-roles-template-")
        cls.addClassCleanup(temporary.cleanup)
        cls.template = Path(temporary.name).resolve() / "project"
        _legacy_project(cls.template)
        _adapter().initialize(
            cls.template,
            flavor_selectors=_selectors(cls.template),
            source_intelligence_provider="none",
            convert=True,
        )
        if (cls.template / PROJECT_FILENAME).exists():
            raise AssertionError("default conversion created a root manifest")
        if not (cls.template / "litai" / PROJECT_FILENAME).is_file():
            raise AssertionError("default conversion lacks contained manifest")

    def test_00_actual_default_roles_hold_all_real_contained_writer_mutexes(self):
        legacy.RetainedLayoutControlRoleTests.test_no_git_uses_actual_conversion_and_all_canonical_framework_mutexes(
            self
        )
        self.assertFalse(
            (self.project / ("." + PROJECT_FILENAME + ".write.lock")).exists()
        )
        self.assertFalse((self.project / ".litai-locks").exists())
        self.assertFalse((self.project / ".literate").exists())

    def test_roles_target_actual_manifest_and_conversion_not_root_lookalikes(self):
        seed = roles._project_roles(self.project)
        store = ProjectConfigurationStore(self.project)
        self.assertEqual(seed.manifest.path, store.manifest_path(self.project))
        self.assertEqual(
            seed.conversion.path, self.project / "litai" / CONVERSION_AUTHORITY_FILE
        )
        targets = {target.path for target in seed.targets()}
        self.assertIn(store.lock_path(self.project), targets)
        self.assertNotIn(
            self.project / ("." + PROJECT_FILENAME + ".write.lock"), targets
        )

    def test_manifest_replacement_preserves_roles_but_not_initial_bytes(self):
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                path = self.project / "litai" / PROJECT_FILENAME
                original = path.read_bytes()
                replacement = path.with_name("replacement")
                replacement.write_text(
                    json.dumps(json.loads(original), indent=4) + "\n"
                )
                replacement.replace(path)
                lease.require_current()
                with self.assertRaisesRegex(ValueError, "prepared project manifest"):
                    lease.require_initial_inputs()

    def test_equal_bytes_foreign_framework_directory_is_not_original_namespace(self):
        seed = roles._project_roles(self.project)
        framework = self.project / "litai"
        displaced = self.state / "original-framework"
        framework.rename(displaced)
        shutil.copytree(displaced, framework, symlinks=True)
        with self.assertRaisesRegex(ValueError, "control roles changed"):
            seed.require_roles_current()
        self.assertEqual(
            (framework / PROJECT_FILENAME).read_bytes(),
            (displaced / PROJECT_FILENAME).read_bytes(),
        )
        self.assertNotEqual(framework.stat().st_ino, displaced.stat().st_ino)

    def test_final_native_input_closure_binds_framework_directory(self):
        seed = roles._project_roles(self.project)
        framework = self.project / "litai"
        displaced = self.state / "original-framework"
        framework.rename(displaced)
        shutil.copytree(displaced, framework, symlinks=True)
        with self.assertRaisesRegex(ValueError, "final closure"):
            seed.close_native_inputs()

    def test_framework_replacement_during_discovery_refuses_equal_bytes(self):
        actual = roles.load_project
        framework = self.project / "litai"
        displaced = self.state / "original-framework"

        def replace(*args, **kwargs):
            result = actual(*args, **kwargs)
            framework.rename(displaced)
            shutil.copytree(displaced, framework, symlinks=True)
            return result

        with mock.patch.object(roles, "load_project", side_effect=replace):
            with self.assertRaisesRegex(ValueError, "role discovery"):
                roles._project_roles(self.project)

    def test_redirected_framework_refuses_before_metadata_reads(self):
        framework = self.project / "litai"
        displaced = self.state / "original-framework"
        framework.rename(displaced)
        framework.symlink_to(displaced, target_is_directory=True)
        with mock.patch.object(roles, "_file", wraps=roles._file) as reads:
            with self.assertRaises(ProjectError):
                roles._project_roles(self.project)
        reads.assert_not_called()
        self.assertTrue(framework.is_symlink())

    def test_dual_manifest_refuses_without_creating_control_files(self):
        shutil.copyfile(
            self.project / "litai" / PROJECT_FILENAME, self.project / PROJECT_FILENAME
        )
        with self.pool() as (pool, journal):
            with self.assertRaises(ProjectError):
                with roles.acquire_retained_layout_control_roles(self.project, pool):
                    self.fail("ambiguous authority acquired")
            self.assertEqual(journal.events, ())
        self.assertFalse((self.project / ".litai-locks").exists())
