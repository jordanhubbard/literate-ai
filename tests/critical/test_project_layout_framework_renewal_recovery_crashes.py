"""Actual child exit during recovery; no in-memory renewal owner in the parent."""

from __future__ import annotations

import os
import signal
import time
import traceback
import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_producer_renewal as support


@unittest.skipUnless(
    hasattr(os, "fork"), "actual POSIX process exits; Windows qualification separate"
)
class FrameworkRenewalRecoveryCrashes(unittest.TestCase):
    def test_parent_recovers_after_each_actual_child_recovery_move(self):
        for boundary in range(1, 5):
            with self.subTest(boundary=boundary):
                helper = support.FrameworkProducerRenewalTests("runTest")
                self.addCleanup(helper.doCleanups)
                project, public, endpoint, original = helper.fixture()
                with ProjectConfigurationStore.layout_lock(project.root):
                    result = helper.renew(
                        project, public, endpoint, helper.prepare(project, endpoint)
                    )
                self.assertTrue(result["current"])
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
                            with patch.object(renewal, "_move", exit_at_boundary):
                                framework.recover_framework_authority(
                                    project.root, public["plan_identity"]
                                )
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
                    os.kill(pid, signal.SIGKILL)  # only this test's exact child
                    os.waitpid(pid, 0)
                    self.fail("owned recovery child exceeded its 180s deadline")
                self.assertTrue(os.WIFEXITED(status))
                self.assertEqual(os.WEXITSTATUS(status), 77)
                helper.recover(project, public, original)
