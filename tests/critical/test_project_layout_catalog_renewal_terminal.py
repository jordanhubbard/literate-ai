"""A real catalog-only change renews the audit and preserves the current lock."""

import json
import unittest

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_catalog_renewal as renewal
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_catalog_renewal as support


class CatalogRenewalTerminalTests(unittest.TestCase):
    def test_unselected_catalog_change_renews_only_audit_and_remains_terminal(self):
        helper = support.CatalogRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original, inodes, plan, _journal, _intent = helper.fixture()
        lock = project.root / "litai/components/peer/component.lock.json"
        audit = lock.with_name("component.resolution-audit.macos-host.json")
        lock_bytes, lock_inode = lock.read_bytes(), lock.stat().st_ino
        audit_bytes = audit.read_bytes()
        with ProjectConfigurationStore.layout_lock(project.root):
            # The fixture adds a real alternate candidate after original lock
            # creation. Default resolution still selects the original Flavor.
            prepared = operations.prepare_component_lock(
                lock.parent,
                target="macos-host",
                flavors=(),
                flavor_roots=(project.root / "flavors",),
                planner=FilesystemComponentLockPlanner(),
            )
            self.assertEqual(
                prepared.result.lock.identity,
                canonical_identity(json.loads(lock_bytes)),
            )
            self.assertNotEqual(
                prepared.result.catalog_audit.identity,
                canonical_identity(json.loads(audit_bytes)),
            )
            result = renewal.renew_placed_catalog_component(
                project.root,
                plan["plan_identity"],
                prepared=prepared,
                layout_lease=current_layout_lease(project.root),
            )
            self.assertTrue(result["current"])
            self.assertTrue(result["writes"])
            self.assertEqual(lock.read_bytes(), lock_bytes)
            self.assertEqual(lock.stat().st_ino, lock_inode)
            self.assertNotEqual(audit.read_bytes(), audit_bytes)
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "normal catalog intent exists"
            ):
                renewal.renew_placed_catalog_component(
                    project.root,
                    plan["plan_identity"],
                    prepared=prepared,
                    layout_lease=current_layout_lease(project.root),
                )
        helper.recover(project, original, inodes, plan)
