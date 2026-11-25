"""Actual catalog pair renewal in a fresh process and native original recovery.

Fixture declarations model historical initialization/import origin. Production
normal factories, journals, publication, checks and native inodes are real.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_catalog_renewal as renewal
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters.component_lock_planning import (
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_migration import (
    apply_legacy_layout_migration,
    plan_legacy_layout_migration,
    recover_legacy_layout_migration,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_mixed_component_channels as support
from tests.support.fixtures_test_component_lock_planning import _flavor_variant

CHILD = """
import json,sys
from pathlib import Path
from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters.project_layout_catalog_renewal import (
    renew_placed_catalog_component,
)
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.projects import ProjectConfigurationStore
root=Path(sys.argv[1]); expected=sys.argv[2]
with ProjectConfigurationStore.layout_lock(root):
    prepared=operations.prepare_component_lock(root/'litai/components/peer',
        target='macos-host',flavors=('+flavor://literate-ai/lang-python-alternate',),
        flavor_roots=(root/'flavors',),
        planner=FilesystemComponentLockPlanner())
    result=renew_placed_catalog_component(root,expected,prepared=prepared,
        layout_lease=current_layout_lease(root))
print(json.dumps(result))
"""


class CatalogRenewalTests(unittest.TestCase):
    def fixture(self, *, alternate=True):
        helper = support.MixedComponentChannelTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original, inodes = helper.fixture()
        if alternate:
            _flavor_variant(
                project.root / "flavors/lang-python",
                project.root / "flavors/lang-python-alternate",
                name="lang-python-alternate",
                value="python",
            )
        plan = plan_legacy_layout_migration(
            project.root, (), place_forward_skills=False, place_imported_catalogs=True
        )
        self.assertTrue(plan["applicable"], plan["blocked_references"])
        result = apply_legacy_layout_migration(
            project.root,
            plan["plan_identity"],
            acknowledge=True,
            references=(),
            place_forward_skills=False,
            place_imported_catalogs=True,
        )
        self.assertTrue(result["applied"])
        journal, intent = native._decode_intent(project.root, plan["plan_identity"])
        return project, original, inodes, plan, journal, intent

    def prepare(self, project):
        return operations.prepare_component_lock(
            project.root / "litai/components/peer",
            target="macos-host",
            flavors=("+flavor://literate-ai/lang-python-alternate",),
            flavor_roots=(project.root / "flavors",),
            planner=FilesystemComponentLockPlanner(),
        )

    def recover(self, project, original, inodes, plan):
        for _repeat in range(2):
            recover_legacy_layout_migration(
                project.root, plan["plan_identity"], acknowledge=True
            )
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)
            self.assertEqual((project.root / path).stat().st_ino, inodes[path])

    def test_fresh_process_renews_actual_pair_without_rebasing_original_history(self):
        project, original, inodes, plan, journal, intent = self.fixture()
        history = (journal / "intent.json").read_bytes()
        historical = {
            row["slot"]: (
                (journal / "history" / row["slot"]).read_bytes(),
                (journal / "history" / row["slot"]).stat().st_ino,
            )
            for row in intent["history"].values()
        }
        environment = dict(os.environ)
        repository = Path(__file__).parents[2]
        environment["PYTHONPATH"] = str(repository / "src")
        process = subprocess.run(
            [sys.executable, "-c", CHILD, str(project.root), plan["plan_identity"]],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout)
        self.assertTrue(result["current"])
        self.assertTrue(result["writes"])
        self.assertFalse(result["qualification"])
        self.assertEqual((journal / "intent.json").read_bytes(), history)
        for slot, (payload, inode) in historical.items():
            self.assertEqual((journal / "history" / slot).read_bytes(), payload)
            self.assertEqual((journal / "history" / slot).stat().st_ino, inode)
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = self.prepare(project)
            planner, target, flavors, roots = (
                operations.require_original_prepared_component_lock(prepared)
            )
            checked, status = operations.operate_component_lock(
                prepared,
                target=target,
                flavors=flavors,
                flavor_roots=roots,
                planner=planner,
                check=True,
                difference=False,
            )
            self.assertEqual(status, 0)
            self.assertTrue(checked["current"])
        self.recover(project, original, inodes, plan)

    def test_fresh_current_pair_preserves_inodes_without_a_renewal_journal(self):
        project, original, inodes, plan, _journal, _intent = self.fixture(
            alternate=False
        )
        paths = [
            project.root / "litai/components/peer" / name
            for name in (
                "component.lock.json",
                "component.resolution-audit.macos-host.json",
            )
        ]
        native = [path.stat().st_ino for path in paths]
        environment = dict(os.environ)
        repository = Path(__file__).parents[2]
        environment["PYTHONPATH"] = str(repository / "src")
        program = CHILD.replace(
            "flavors=('+flavor://literate-ai/lang-python-alternate',)", "flavors=()"
        )
        result = subprocess.run(
            [sys.executable, "-c", program, str(project.root), plan["plan_identity"]],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["current"])
        self.assertFalse(report["writes"])
        self.assertIsNone(report["journal"])
        self.assertEqual([path.stat().st_ino for path in paths], native)
        self.recover(project, original, inodes, plan)

    def test_copied_preparation_and_new_git_boundary_refuse_before_intent(self):
        project, original, inodes, plan, journal, intent = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = self.prepare(project)
            with self.assertRaises(ComponentLockPlanningError):
                renewal.renew_placed_catalog_component(
                    project.root,
                    plan["plan_identity"],
                    prepared=copy.copy(prepared),
                    layout_lease=current_layout_lease(project.root),
                )
            marker = prepared.component_root / ".git"
            marker.mkdir()
            try:
                with self.assertRaises(ProjectLayoutPlanError):
                    renewal.renew_placed_catalog_component(
                        project.root,
                        plan["plan_identity"],
                        prepared=prepared,
                        layout_lease=current_layout_lease(project.root),
                    )
            finally:
                marker.rmdir()  # exact synthetic boundary, no other content
        self.assertEqual(
            list((project.root / "litai/.literate").glob("catalog-renewal-*")), []
        )
        self.recover(project, original, inodes, plan)
