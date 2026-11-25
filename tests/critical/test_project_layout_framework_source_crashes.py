"""Actual process exits at source-close/restore durability boundaries.

Only native descriptor read/release boundaries are instrumented, always after
calling the real primitive. Source facts, normal producers and moves are real.
"""

from __future__ import annotations

import os
import signal
import time
import traceback
import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_finalization as finalization
from literate_ai.adapters import project_layout_framework_source_closure as closing
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_producer_renewal as support


@unittest.skipUnless(
    hasattr(os, "fork"), "actual POSIX exits; Windows remains required"
)
class FrameworkSourceCrashTests(unittest.TestCase):
    def fixture(self):
        helper = support.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, endpoint, original = helper.fixture(alternate=False)
        journal, intent = framework._decode(project.root, public["plan_identity"])
        record = closing._expected(
            project.root, journal, intent, intent["components"][0]
        )
        return (
            helper,
            project,
            public,
            original,
            closing._paths(project.root, journal, record),
        )

    def wait_child(self, pid):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            found, status = os.waitpid(pid, os.WNOHANG)
            if found == pid:
                self.assertTrue(os.WIFEXITED(status))
                self.assertEqual(os.WEXITSTATUS(status), 77)
                return
            time.sleep(0.05)
        os.kill(pid, signal.SIGKILL)  # only this test's exact fork child
        os.waitpid(pid, 0)
        self.fail("owned source-close child exceeded declared180s deadline")

    def test_close_pending_intent_and_retired_native_states_recover(self):
        for phase in ("pending", "intent", "retired"):
            with self.subTest(phase=phase):
                helper, project, public, original, (source, archive, record) = (
                    self.fixture()
                )
                pid = os.fork()
                if pid == 0:
                    try:
                        real = closing.physical._file_record

                        def exit_at_native_read(
                            fd,
                            real=real,
                            phase=phase,
                            record=record,
                            source=source,
                            archive=archive,
                        ):
                            result = real(fd)
                            reached = (
                                any(record.parent.glob(".*.pending-*"))
                                and not record.exists()
                                if phase == "pending"
                                else record.exists()
                                and source.exists()
                                and not archive.exists()
                                if phase == "intent"
                                else archive.exists() and not source.exists()
                            )
                            if reached:
                                os._exit(77)
                            return result

                        with ProjectConfigurationStore.layout_lock(project.root):
                            with patch.object(
                                closing.physical, "_file_record", exit_at_native_read
                            ):
                                finalization.finalize_framework_components(
                                    project.root, public["plan_identity"]
                                )
                        os._exit(0)
                    except BaseException:
                        traceback.print_exc()
                        os._exit(78)
                self.wait_child(pid)
                helper.recover(project, public, original)

    def test_exit_after_source_restore_releases_kernel_controls_and_recovers(self):
        helper, project, public, original, (source, archive, _record) = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            finalization.finalize_framework_components(
                project.root, public["plan_identity"]
            )
        self.assertFalse(source.exists())
        pid = os.fork()
        if pid == 0:
            try:
                real = closing._release

                def exit_after_release(fd):
                    real(fd)
                    if source.exists() and not archive.exists():
                        os._exit(77)

                with ProjectConfigurationStore.layout_lock(project.root):
                    with patch.object(closing, "_release", exit_after_release):
                        framework.recover_framework_authority(
                            project.root, public["plan_identity"]
                        )
                os._exit(0)
            except BaseException:
                traceback.print_exc()
                os._exit(78)
        self.wait_child(pid)
        helper.recover(project, public, original)
