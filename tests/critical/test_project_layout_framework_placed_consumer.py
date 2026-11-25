"""Actual placed stdlib bootstrap consumer; no driver/worker/build execution."""

from __future__ import annotations

import subprocess
import sys
import unittest

from tests.critical import test_project_layout_framework_transaction as support


class PlacedFrameworkConsumerTests(unittest.TestCase):
    def test_transformed_bootstrap_loads_exact_created_helper_and_recovers(self):
        helper = support.FrameworkAuthorityTransactionTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, selected = helper.fixture()
        originals = dict(selected.original_contents)
        helper.apply(project, public, selected)
        # run_path does not invoke __main__. The real relocated script's owner
        # verifies the newly created helper's digest and loads its actual code.
        # No CLI executable discovery, source alignment or version probe runs.
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import runpy, sys; scope = runpy.run_path(sys.argv[1]); "
                "print(scope['_process_owner']().__name__)",
                str(project.root / "litai/scripts/bootstrap_litai.py"),
            ],
            cwd=project.root,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertTrue(result.stdout.strip().startswith("_litai_bootstrap_owner_"))
        helper.recover(project, public)
        for path, content in originals.items():
            self.assertEqual((project.root / path).read_bytes(), content)
