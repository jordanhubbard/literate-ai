"""Real normal producers, native pair custody and restart recovery.

Initialization lineage/current distribution lookup use the established fixture
seams. No installed/native-build or supported-platform release claim is made.
"""

from __future__ import annotations

import copy
import os
import signal
import time
import traceback
import unittest
from unittest.mock import patch

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_lock_planning import (
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_component_journey as support


class FrameworkProducerRenewalTests(unittest.TestCase):
    def fixture(self, *, alternate=True):
        helper = support.FrameworkComponentJourneyTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, selection = helper.fixture(alternate=alternate)
        (endpoint,) = selection.component_endpoints
        original = dict(selection.original_contents)
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.apply_framework_authority(selection, public["plan_identity"])
        return project, public, endpoint, original

    def prepare(self, project, endpoint, *, alternate=True):
        return operations.prepare_component_lock(
            project.root / endpoint.destination_root,
            target="macos-host",
            flavors=("+flavor://literate-ai/lang-python-alternate",)
            if alternate
            else (),
            flavor_roots=(project.root / "flavors",),
            planner=FilesystemComponentLockPlanner(),
        )

    def renew(self, project, public, endpoint, prepared):
        return renewal.renew_framework_component(
            endpoint,
            ProjectConfigurationStore(project.root).read(),
            prepared=prepared,
            layout_lease=current_layout_lease(project.root),
            plan_identity=public["plan_identity"],
        )

    def recover(self, project, public, original):
        with ProjectConfigurationStore.layout_lock(project.root):
            report = framework.recover_framework_authority(
                project.root, public["plan_identity"]
            )
        self.assertTrue(report["rolled_back"])
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)
        # A renewed-pair journal remains history after the original placement is
        # restored; it must not make idempotent framework recovery adopt a path.
        with ProjectConfigurationStore.layout_lock(project.root):
            self.assertTrue(
                framework.recover_framework_authority(
                    project.root, public["plan_identity"]
                )["rolled_back"]
            )

    def test_real_normal_pair_renewal_has_exact_history_and_framework_recovery(self):
        project, public, endpoint, original = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = self.prepare(project, endpoint)
            result = self.renew(project, public, endpoint, prepared)
            self.assertTrue(result["current"])
            self.assertTrue(result["writes"])
            self.assertFalse(result["finalized"])
            journal, intent = framework._decode(project.root, public["plan_identity"])
            for path, payload in endpoint.original_contents.items():
                self.assertEqual(
                    (journal / "before" / intent["entries"][path]["slot"]).read_bytes(),
                    payload,
                )
            with self.assertRaises(ProjectLayoutPlanError):
                self.renew(project, public, endpoint, prepared)
        self.recover(project, public, original)

    def test_original_current_pair_needs_no_journal_and_no_inode_change(self):
        project, public, endpoint, original = self.fixture(alternate=False)
        before = {
            path: (project.root / ("litai/" + path)).stat().st_ino
            for path in endpoint.records
        }
        with ProjectConfigurationStore.layout_lock(project.root):
            result = self.renew(
                project,
                public,
                endpoint,
                self.prepare(project, endpoint, alternate=False),
            )
        self.assertFalse(result["writes"])
        self.assertIsNone(result["journal"])
        self.assertEqual(
            before,
            {
                path: (project.root / ("litai/" + path)).stat().st_ino
                for path in endpoint.records
            },
        )
        self.recover(project, public, original)

    def test_copied_normal_preparation_cannot_create_intent(self):
        project, public, endpoint, original = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = self.prepare(project, endpoint)
            with self.assertRaises(ComponentLockPlanningError):
                self.renew(project, public, endpoint, copy.copy(prepared))
        self.assertEqual(
            list((project.root / "litai/.literate").glob("framework-renewal-*")), []
        )
        self.recover(project, public, original)

    @unittest.skipUnless(
        hasattr(os, "fork"), "actual POSIX child exit; Windows qualification separate"
    )
    def test_actual_child_exit_after_each_normal_pair_move_recovers_on_parent_restart(
        self,
    ):
        # Every audit-before/audit-after/lock-before/lock-after rename is real.
        # _exit releases the actual child's OS locks without Python unwinding.
        for boundary in range(1, 5):
            with self.subTest(boundary=boundary):
                project, public, endpoint, original = self.fixture()
                pid = os.fork()
                if pid == 0:
                    try:
                        move = renewal._move
                        count = 0

                        def exit_at_boundary(
                            *args, move=move, boundary=boundary, **kwargs
                        ):
                            nonlocal count
                            result = move(*args, **kwargs)
                            count += 1
                            if count == boundary:
                                os._exit(77)
                            return result

                        with ProjectConfigurationStore.layout_lock(project.root):
                            prepared = self.prepare(project, endpoint)
                            with patch.object(renewal, "_move", exit_at_boundary):
                                self.renew(project, public, endpoint, prepared)
                        os._exit(0)
                    except BaseException:
                        traceback.print_exc()
                        os._exit(78)
                deadline = time.monotonic() + 180
                status = None
                while time.monotonic() < deadline:
                    found, value = os.waitpid(pid, os.WNOHANG)
                    if found == pid:
                        status = value
                        break
                    time.sleep(0.05)
                if status is None:
                    os.kill(pid, signal.SIGKILL)  # this test's exact fork child only
                    os.waitpid(pid, 0)
                    self.fail("owned renewal child exceeded declared 180s deadline")
                self.assertTrue(os.WIFEXITED(status))
                self.assertEqual(os.WEXITSTATUS(status), 77)
                self.recover(project, public, original)
