"""Real catalog pair crashes and foreign custody; origin declarations modeled."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from literate_ai.adapters import project_layout_catalog_renewal as renewal
from literate_ai.adapters.project_layout_migration import (
    recover_legacy_layout_migration,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_catalog_renewal as support

CRASH = """
from literate_ai.adapters import project_layout_catalog_renewal as renewal
original_move=renewal._move
count=0
def crash_after_move(*args,**kwargs):
    global count
    result=original_move(*args,**kwargs)
    count+=1
    if count==int(sys.argv[3]):
        os._exit(77)
    return result
renewal._move=crash_after_move
"""

RECOVER = """
import os,sys
from pathlib import Path
from literate_ai.adapters.project_layout_migration import (
    recover_legacy_layout_migration,
)
root=Path(sys.argv[1]); expected=sys.argv[2]
{crash}
recover_legacy_layout_migration(root,expected,acknowledge=True)
"""


class CatalogRenewalControls(unittest.TestCase):
    def fixture(self):
        helper = support.CatalogRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper, *helper.fixture()

    def child(self, program, project, plan, boundary=None):
        repository = Path(__file__).parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")
        arguments = [
            sys.executable,
            "-c",
            program,
            str(project.root),
            plan["plan_identity"],
        ]
        if boundary is not None:
            arguments.append(str(boundary))
        return subprocess.run(
            arguments,
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )

    def renewed(self, project, plan):
        result = self.child(support.CHILD, project, plan)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fresh_process_recovers_each_actual_publication_move_exit(self):
        for boundary in range(1, 5):
            with self.subTest(boundary=boundary):
                helper, project, original, inodes, plan, _journal, _intent = (
                    self.fixture()
                )
                program = support.CHILD.replace(
                    "import json,sys", "import json,sys,os"
                ).replace(
                    "with ProjectConfigurationStore.layout_lock(root):",
                    CRASH + "\nwith ProjectConfigurationStore.layout_lock(root):",
                )
                result = self.child(program, project, plan, boundary)
                self.assertEqual(result.returncode, 77, result.stdout + result.stderr)
                result = self.child(RECOVER.format(crash=""), project, plan)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                helper.recover(project, original, inodes, plan)

    def test_fresh_process_recovers_each_actual_restoration_move_exit(self):
        for boundary in range(1, 5):
            with self.subTest(boundary=boundary):
                helper, project, original, inodes, plan, _journal, _intent = (
                    self.fixture()
                )
                self.renewed(project, plan)
                result = self.child(
                    RECOVER.format(crash=CRASH), project, plan, boundary
                )
                self.assertEqual(result.returncode, 77, result.stdout + result.stderr)
                result = self.child(RECOVER.format(crash=""), project, plan)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                helper.recover(project, original, inodes, plan)

    def test_equal_byte_foreign_inode_is_preserved_on_recovery_refusal(self):
        helper, project, original, inodes, plan, _journal, _intent = self.fixture()
        self.renewed(project, plan)
        target = project.root / "litai/components/peer/component.lock.json"
        content = target.read_bytes()
        saved = project.root / "test-owned-renewed-lock"
        target.rename(saved)
        target.write_bytes(content)
        target.chmod(0o600)
        foreign = target.stat().st_ino
        try:
            with self.assertRaises(ProjectLayoutPlanError):
                recover_legacy_layout_migration(
                    project.root, plan["plan_identity"], acknowledge=True
                )
            self.assertEqual(target.read_bytes(), content)
            self.assertEqual(target.stat().st_ino, foreign)
        finally:
            # Return this fixture's exact saved inode after observing refusal.
            target.unlink()
            saved.rename(target)
        helper.recover(project, original, inodes, plan)

    def test_changed_original_modes_restore_after_ordinary_renewal(self):
        helper, project, original, inodes, plan, _journal, _intent = self.fixture()
        helper.recover(project, original, inodes, plan)
        for name in (
            "component.lock.json",
            "component.resolution-audit.macos-host.json",
        ):
            (project.root / "components/peer" / name).chmod(0o640)
        # A new native plan observes the intentional original metadata change.
        from literate_ai.adapters.project_layout_migration import (
            apply_legacy_layout_migration,
            plan_legacy_layout_migration,
        )

        plan = plan_legacy_layout_migration(
            project.root, (), place_forward_skills=False, place_imported_catalogs=True
        )
        self.assertTrue(plan["applicable"], plan["blocked_references"])
        apply_legacy_layout_migration(
            project.root,
            plan["plan_identity"],
            acknowledge=True,
            references=(),
            place_forward_skills=False,
            place_imported_catalogs=True,
        )
        with ProjectConfigurationStore.layout_lock(project.root):
            result = renewal.renew_placed_catalog_component(
                project.root,
                plan["plan_identity"],
                prepared=helper.prepare(project),
                layout_lease=renewal.current_layout_lease(project.root),
            )
        self.assertTrue(result["writes"])
        for name in (
            "component.lock.json",
            "component.resolution-audit.macos-host.json",
        ):
            self.assertEqual(
                (project.root / "litai/components/peer" / name).stat().st_mode & 0o777,
                0o600,
            )
        helper.recover(project, original, inodes, plan)
        for name in (
            "component.lock.json",
            "component.resolution-audit.macos-host.json",
        ):
            self.assertEqual(
                (project.root / "components/peer" / name).stat().st_mode & 0o777, 0o640
            )
