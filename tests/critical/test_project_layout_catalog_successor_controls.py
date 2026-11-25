"""Actual successor native handoff/refusal and interrupted pair recovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_catalog_renewal as renewal
from literate_ai.adapters import project_layout_continuation as catalog
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_migration import (
    recover_legacy_layout_migration,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_catalog_renewal as standalone
from tests.critical import test_project_layout_mixed_producer_epochs as support


class CatalogSuccessorControls(unittest.TestCase):
    def fixture(self):
        helper = support.MixedProducerEpochTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper, *helper.fixture()

    def test_replaced_successor_guard_is_never_called_or_granted_custody(self):
        helper, project, original, inodes, plan, public = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            snapshot = ProjectConfigurationStore(project.root).read()
            prepared = operations.prepare_component_lock(
                project.root / "litai/components/peer",
                target="macos-host",
                flavors=(),
                flavor_roots=tuple(
                    project.root / value for value in snapshot.definition.flavor_roots
                ),
                planner=FilesystemComponentLockPlanner(),
            )
            calls = []
            with patch.object(framework, "_guard", lambda *_a: calls.append(True)):
                with self.assertRaises(ProjectLayoutPlanError):
                    renewal.renew_placed_catalog_component(
                        project.root,
                        plan["plan_identity"],
                        prepared=prepared,
                        layout_lease=current_layout_lease(project.root),
                        successor_plan_identity=public["plan_identity"],
                    )
            self.assertEqual(calls, [])
        self.assertEqual(
            list((project.root / "litai/.literate").glob("catalog-renewal-*")), []
        )
        helper.recover(project, original, inodes, plan, public)

    def test_original_v1_pair_journal_remains_recoverable_without_a_successor(self):
        helper = standalone.CatalogRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original, inodes, plan, _parent, _intent = helper.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            result = renewal.renew_placed_catalog_component(
                project.root,
                plan["plan_identity"],
                prepared=helper.prepare(project),
                layout_lease=current_layout_lease(project.root),
            )
        path = Path(result["journal"]) / "intent.json"
        record = json.loads(path.read_bytes())
        record.pop("identity")
        self.assertIsNone(record.pop("successor"))
        # Original v1 wire representation over the same genuine native files.
        # It describes custody; no source actor/lease is issued from this data.
        record["schema"] = "literate-ai/catalog-producer-renewal@1"
        record["identity"] = canonical_identity(record).uri
        path.write_bytes(canonical_json_bytes(record) + b"\n")
        helper.recover(project, original, inodes, plan)

    def test_equal_byte_foreign_successor_beforeimage_refuses_before_intent(self):
        helper, project, original, inodes, plan, public = self.fixture()
        frame, intent = framework._decode(project.root, public["plan_identity"])
        row = intent["entries"]["litai/literate.project.json"]
        path = frame / "before" / row["slot"]
        before = path.read_bytes()
        saved = project.root / "test-owned-catalog-metadata"
        path.rename(saved)
        path.write_bytes(before)
        path.chmod(row["mode"])
        foreign = path.stat().st_ino
        try:
            with ProjectConfigurationStore.layout_lock(project.root):
                snapshot = ProjectConfigurationStore(project.root).read()
                prepared = operations.prepare_component_lock(
                    project.root / "litai/components/peer",
                    target="macos-host",
                    flavors=(),
                    flavor_roots=tuple(
                        project.root / value
                        for value in snapshot.definition.flavor_roots
                    ),
                    planner=FilesystemComponentLockPlanner(),
                )
                with self.assertRaisesRegex(
                    ProjectLayoutPlanError, "original framework backup changed"
                ):
                    renewal.renew_placed_catalog_component(
                        project.root,
                        plan["plan_identity"],
                        prepared=prepared,
                        layout_lease=current_layout_lease(project.root),
                        successor_plan_identity=public["plan_identity"],
                    )
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_ino, foreign)
            self.assertEqual(
                list((project.root / "litai/.literate").glob("catalog-renewal-*")), []
            )
        finally:
            path.unlink()  # exact test-created foreign inode only
            saved.rename(path)
        helper.recover(project, original, inodes, plan, public)

    def test_wrong_recovery_order_preserves_live_pair_and_retained_history(self):
        helper, project, original, inodes, plan, public = self.fixture()
        result = helper.child(project, plan, public, "catalog")
        self.assertTrue(result["writes"])
        journal = Path(result["journal"])
        parent, intent = catalog._decode_intent(project.root, plan["plan_identity"])
        component = intent["components"][0]
        _path, record = renewal._decode(project.root, intent, component, "macos-host")
        paths = [project.root / path for path in record["entries"]]
        before = [(path.read_bytes(), path.stat().st_ino) for path in paths]
        history = (parent / "intent.json").read_bytes()
        with self.assertRaisesRegex(
            ProjectLayoutPlanError, "framework successor before"
        ):
            recover_legacy_layout_migration(
                project.root, plan["plan_identity"], acknowledge=True
            )
        self.assertEqual(
            [(path.read_bytes(), path.stat().st_ino) for path in paths], before
        )
        self.assertEqual((parent / "intent.json").read_bytes(), history)
        self.assertFalse((journal / "rolled-back").exists())
        helper.recover(project, original, inodes, plan, public)

    def test_child_exit_after_real_catalog_backup_recovers_after_framework_undo(self):
        helper, project, original, inodes, plan, public = self.fixture()
        injection = """
original_move=catalog._move
def interrupted(*args,**kwargs):
    original_move(*args,**kwargs)
    import os
    os._exit(77)
catalog._move=interrupted
"""
        program = support.CHILD.replace(
            "with ProjectConfigurationStore.layout_lock(root):",
            injection + "\nwith ProjectConfigurationStore.layout_lock(root):",
        )
        repository = Path(__file__).parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")
        request = {
            "scope": "catalog",
            "component": "litai/components/peer",
            "catalog_plan": plan["plan_identity"],
            "framework_plan": public["plan_identity"],
        }
        child = subprocess.run(
            [sys.executable, "-c", program, str(project.root), json.dumps(request)],
            cwd=repository,
            env=environment,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(child.returncode, 77, child.stdout + child.stderr)
        helper.recover(project, original, inodes, plan, public)
