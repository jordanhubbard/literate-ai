"""Real mixed producer ownership across ordered native metadata epochs.

Historical initialization/import origin declarations remain fixture data. Native
journals, normal factories, fresh processes and original inode recovery are real.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_catalog_renewal as catalog_renewal
from literate_ai.adapters import project_layout_continuation as catalog
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
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
from literate_ai.adapters import project_layout_catalog_renewal as catalog
from literate_ai.adapters import project_layout_framework_renewal as framework
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.projects import ProjectConfigurationStore
root=Path(sys.argv[1]); request=json.loads(sys.argv[2])
with ProjectConfigurationStore.layout_lock(root):
    snapshot=ProjectConfigurationStore(root).read()
    prepared=operations.prepare_component_lock(root/request['component'],
        target='macos-host',
        flavors=('+flavor://literate-ai/lang-python-alternate',),
        flavor_roots=tuple(root/path for path in
            (*snapshot.definition.flavor_roots,'local-flavor-fixture')),
        planner=FilesystemComponentLockPlanner())
    lease=current_layout_lease(root)
    if request['scope']=='catalog':
        result=catalog.renew_placed_catalog_component(root,request['catalog_plan'],
            prepared=prepared,layout_lease=lease,
            successor_plan_identity=request['framework_plan'])
    else:
        result=framework.renew_placed_framework_component(root,
            request['framework_plan'],prepared=prepared,layout_lease=lease)
print(json.dumps(result))
"""


class MixedProducerEpochTests(unittest.TestCase):
    def fixture(self):
        helper = support.MixedComponentChannelTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original, inodes = helper.fixture()
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
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.apply_framework_authority(selected, public["plan_identity"])
        alternate = project.root / "local-flavor-fixture/lang-python-alternate"
        _flavor_variant(
            project.root / "flavors/lang-python",
            alternate,
            name="lang-python-alternate",
            value="python",
        )
        self.authored = {
            path: path.read_bytes() for path in alternate.rglob("*") if path.is_file()
        }
        return project, original, inodes, plan, public

    def child(self, project, plan, public, scope):
        repository = Path(__file__).parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")
        request = {
            "scope": scope,
            "component": "litai/components/peer"
            if scope == "catalog"
            else "litai/samples/hello-component",
            "catalog_plan": plan["plan_identity"],
            "framework_plan": public["plan_identity"],
        }
        result = subprocess.run(
            [sys.executable, "-c", CHILD, str(project.root), json.dumps(request)],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def recover(self, project, original, inodes, plan, public):
        for _repeat in range(2):
            with ProjectConfigurationStore.layout_lock(project.root):
                framework.recover_framework_authority(
                    project.root, public["plan_identity"]
                )
        for _repeat in range(2):
            recover_legacy_layout_migration(
                project.root, plan["plan_identity"], acknowledge=True
            )
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)
            self.assertEqual((project.root / path).stat().st_ino, inodes[path])
        for path, content in self.authored.items():
            self.assertEqual(path.read_bytes(), content)

    def test_fresh_normal_owners_join_both_epochs_and_restore_original_inodes(self):
        project, original, inodes, plan, public = self.fixture()
        journal, intent = catalog._decode_intent(project.root, plan["plan_identity"])
        frame, _frame_intent = framework._decode(project.root, public["plan_identity"])
        history = (
            (journal / "intent.json").read_bytes(),
            (frame / "intent.json").read_bytes(),
        )
        copied = {
            journal / "history" / row["slot"]: (
                (journal / "history" / row["slot"]).read_bytes(),
                (journal / "history" / row["slot"]).stat().st_ino,
            )
            for row in intent["history"].values()
        }
        with ProjectConfigurationStore.layout_lock(project.root):
            snapshot = ProjectConfigurationStore(project.root).read()
            prepared = operations.prepare_component_lock(
                project.root / "litai/components/peer",
                target="macos-host",
                flavors=(),
                flavor_roots=tuple(
                    project.root / path for path in snapshot.definition.flavor_roots
                ),
                planner=FilesystemComponentLockPlanner(),
            )
            # An old owner must keep refusing metadata now held by another
            # actual journal. Explicit successor identity is a separate join.
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "catalog entry has an unresolved state"
            ):
                catalog_renewal.renew_placed_catalog_component(
                    project.root,
                    plan["plan_identity"],
                    prepared=prepared,
                    layout_lease=current_layout_lease(project.root),
                )
        self.assertEqual(
            list((project.root / "litai/.literate").glob("catalog-renewal-*")), []
        )
        for scope in ("catalog", "framework"):
            result = self.child(project, plan, public, scope)
            self.assertTrue(result["current"])
            self.assertTrue(result["writes"])
            self.assertFalse(result["qualification"])
        self.assertEqual((journal / "intent.json").read_bytes(), history[0])
        self.assertEqual((frame / "intent.json").read_bytes(), history[1])
        for path, (content, inode) in copied.items():
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_ino, inode)
        self.recover(project, original, inodes, plan, public)
