"""Actual process death between original wrapper control-file moves.

Native read instrumentation calls the real primitive before exiting. Fixtures
model historical conversion execution; these are not platform attestations.
"""

from __future__ import annotations

import os
import signal
import time
import traceback
import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_source_controls as controls
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_recorded_source_controls as support


@unittest.skipUnless(
    hasattr(os, "fork"), "actual POSIX exits; Windows remains required"
)
class RecordedSourceControlCrashTests(unittest.TestCase):
    def fixture(self):
        helper = support.RecordedSourceControlTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, endpoint, original, journal, intent, native = helper.fixture()
        record = controls._expected(project.root, intent, intent["components"][0])
        archive = controls._path(project.root, record)
        self.assertGreater(len(record["controls"]), 1)
        return (
            helper,
            project,
            public,
            endpoint,
            original,
            journal,
            intent,
            native,
            record,
            archive,
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
        self.fail("owned control-move child exceeded declared 180s deadline")

    def exit_during_move(self, helper, project, public, record, archive, *, restore):
        pid = os.fork()
        if pid == 0:
            try:
                real = controls.physical._file_record

                def exit_after_real_native_read(fd):
                    result = real(fd)
                    count = sum(
                        (archive / "controls" / row["slot"]).exists()
                        for row in record["controls"].values()
                    )
                    if 0 < count < len(record["controls"]):
                        os._exit(77)
                    return result

                with patch.object(
                    controls.physical, "_file_record", exit_after_real_native_read
                ):
                    if restore:
                        with ProjectConfigurationStore.layout_lock(project.root):
                            framework.recover_framework_authority(
                                project.root, public["plan_identity"]
                            )
                    else:
                        helper.finish(project, public)
                os._exit(0)
            except BaseException:
                traceback.print_exc()
                os._exit(78)
        self.wait_child(pid)

    def assert_partial(self, project, journal, intent, native):
        ((record, _archive, rows),) = controls.records(project.root, journal, intent)
        self.assertGreater(sum(archived for _, _, archived in rows), 0)
        self.assertLess(sum(archived for _, _, archived in rows), len(rows))
        for coordinate, actual, _archived in rows:
            self.assertEqual(actual.stat().st_ino, native[coordinate])
        self.assertEqual(set(record["controls"]), set(native))

    def test_partial_close_process_exit_restores_original_control_inodes(self):
        (
            helper,
            project,
            public,
            endpoint,
            original,
            journal,
            intent,
            native,
            record,
            archive,
        ) = self.fixture()
        source = project.root / endpoint.source_root
        implementation = source / "implementation/main.py"
        before = source.stat().st_ino, implementation.stat().st_ino
        self.exit_during_move(helper, project, public, record, archive, restore=False)
        self.assert_partial(project, journal, intent, native)
        helper.recover(project, public, original, native)
        self.assertEqual((source.stat().st_ino, implementation.stat().st_ino), before)

    def test_partial_restore_process_exit_resumes_before_generic_fences(self):
        (
            helper,
            project,
            public,
            _endpoint,
            original,
            journal,
            intent,
            native,
            record,
            archive,
        ) = self.fixture()
        helper.finish(project, public)
        ((_, _, rows),) = controls.records(project.root, journal, intent)
        self.assertTrue(all(archived for _, _, archived in rows))
        self.exit_during_move(helper, project, public, record, archive, restore=True)
        self.assert_partial(project, journal, intent, native)
        helper.recover(project, public, original, native)
