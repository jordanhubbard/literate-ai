"""Actual descendant timeout regression for the original temporary-checkout caller."""

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as release
from literate_ai.adapters import _processes as processes


class ReleaseGitProcessOwnershipTests(unittest.TestCase):
    def test_original_git_in_timeout_stops_its_actual_descendant(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        counter = root / "child-counter"
        ready = root / "child-ready"
        script = root / "tool.py"
        child = (
            "import pathlib,sys,time\npath=pathlib.Path(sys.argv[1])\ni=0\n"
            "while True:\n i+=1\n path.write_text(str(i))\n time.sleep(0.02)\n"
        )
        script.write_text(
            "import pathlib,subprocess,sys,time\n"
            "root=pathlib.Path(sys.argv[1])\n"
            "child=subprocess.Popen([sys.executable,'-c',"
            + repr(child)
            + ",str(root/'child-counter')],"
            "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
            "while not (root/'child-counter').exists(): time.sleep(0.01)\n"
            "(root/'child-ready').write_text(str(child.pid))\n"
            "time.sleep(30)\n"
        )
        actual = [sys.executable, str(script), str(root)]
        popen = subprocess.Popen
        run = subprocess.run
        owned_run = release.run_with_tree_kill
        create_owner = processes.create_process_tree_ownership
        baseline_owner = create_owner()
        issued = []
        legacy_active = [False]

        def original_popen(*args, **kwargs):
            process = popen(*args, **kwargs)
            if legacy_active[0]:
                # Retain the actual creation handle solely to retire a baseline
                # leaked group; the fixed helper owns its own separate lifetime.
                issued.append(process)
                baseline_owner.bind(process.pid)
            return process

        def legacy(command, **kwargs):
            self.assertEqual(command[:3], ("git", "-C", str(root)))
            kwargs["timeout"] = 1
            legacy_active[0] = True
            try:
                return run(actual, **kwargs, **baseline_owner.popen_options)
            finally:
                legacy_active[0] = False

        def owned(command, **kwargs):
            self.assertEqual(command[:3], ("git", "-C", str(root)))
            kwargs["timeout"] = 1
            return owned_run(actual, **kwargs)

        def retire_fixture():
            # Only a group issued by this fixture is eligible; no PID discovery
            # or unrelated process signal is used for baseline cleanup.
            if issued:
                processes.terminate_process_tree(issued[0], ownership=baseline_owner)
            baseline_owner.release()

        self.addCleanup(retire_fixture)
        with (
            patch.object(subprocess, "Popen", side_effect=original_popen),
            patch.object(release.subprocess, "run", side_effect=legacy),
            patch.object(release, "run_with_tree_kill", side_effect=owned),
        ):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                release._git_in(root, "status", "--porcelain")
        self.assertEqual(caught.exception.code, "release.git_failed")
        self.assertIsInstance(caught.exception.__cause__, subprocess.TimeoutExpired)
        self.assertTrue(ready.is_file(), "actual descendant did not start")
        before = counter.read_bytes()
        time.sleep(0.15)
        self.assertEqual(
            counter.read_bytes(),
            before,
            "actual descendant survived original caller timeout",
        )

    def test_actual_git_capture_and_checked_error_contracts_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            initialized = release._git_in(root, "init", "-b", "main")
            self.assertEqual(initialized.returncode, 0)
            branch = release._git_in(root, "symbolic-ref", "--short", "HEAD")
            self.assertEqual(branch.stdout.strip(), "main")
            self.assertIsInstance(branch.stderr, str)
            missing = release._git_in(
                root, "rev-parse", "--verify", "refs/heads/missing", check=False
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIsInstance(missing.stderr, str)
            with self.assertRaises(release.ProjectReleaseError) as caught:
                release._git_in(root, "rev-parse", "--verify", "refs/heads/missing")
            self.assertEqual(caught.exception.code, "release.git_failed")
            self.assertIsInstance(
                caught.exception.__cause__, subprocess.CalledProcessError
            )
