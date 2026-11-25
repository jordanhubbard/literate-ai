"""Real retained native pair/foreign inode controls; initialization lineage modeled."""

from __future__ import annotations

import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_producer_renewal as support


class FrameworkProducerRenewalControls(unittest.TestCase):
    def fixture(self):
        helper = support.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper, *helper.fixture()

    def test_foreign_equal_byte_producer_inode_refuses_without_reclaiming_it(self):
        helper, project, public, endpoint, original = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            helper.renew(project, public, endpoint, helper.prepare(project, endpoint))
        target = project.root / endpoint.destination_root / "component.lock.json"
        content = target.read_bytes()
        saved = project.root / "test-owned-renewed-lock"
        target.rename(saved)
        target.write_bytes(content)
        target.chmod(0o600)
        foreign_inode = target.stat().st_ino
        with ProjectConfigurationStore.layout_lock(project.root):
            try:
                with self.assertRaises(ProjectLayoutPlanError):
                    framework.recover_framework_authority(
                        project.root, public["plan_identity"]
                    )
            finally:
                self.assertEqual(target.read_bytes(), content)
                self.assertEqual(target.stat().st_ino, foreign_inode)
        # Test-only repair returns the exact inode held by this test. Production
        # refusal did not delete the foreign file or reconstruct the owned file.
        target.unlink()
        saved.rename(target)
        helper.recover(project, public, original)

    def test_substituted_local_admission_cannot_create_any_renewal_intent(self):
        helper, project, public, endpoint, original = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = helper.prepare(project, endpoint)
            calls = []
            with patch.object(renewal, "_ADMIT", lambda *_a: calls.append(True)):
                with self.assertRaises(ProjectLayoutPlanError):
                    helper.renew(project, public, endpoint, prepared)
            self.assertEqual(calls, [])
        self.assertEqual(
            list((project.root / "litai/.literate").glob("framework-renewal-*")), []
        )
        helper.recover(project, public, original)

    def test_ordinary_replacement_mode_and_exact_original_modes_both_survive(self):
        helper, project, _public, _endpoint, _original = self.fixture()
        # The first fixture is already placed. Roll it back, choose native old
        # producer modes, and obtain a fresh ORIGINAL read selection after that
        # intentional change. No copied or decoded source proof is readmitted.
        helper.recover(project, _public, _original)
        for path in _endpoint.records:
            (project.root / path).chmod(0o640)
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        (endpoint,) = selected.component_endpoints
        original = dict(selected.original_contents)
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.apply_framework_authority(selected, public["plan_identity"])
            result = helper.renew(
                project, public, endpoint, helper.prepare(project, endpoint)
            )
        self.assertTrue(result["current"])
        for path in endpoint.records:
            self.assertEqual(
                stat.S_IMODE((project.root / ("litai/" + path)).stat().st_mode), 0o600
            )
        self.assertTrue(Path(result["journal"]).is_dir())
        helper.recover(project, public, original)
        for path in endpoint.records:
            self.assertEqual(stat.S_IMODE((project.root / path).stat().st_mode), 0o640)
