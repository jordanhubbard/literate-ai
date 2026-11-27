"""Standalone digest loading and original release command admission stay distinct."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from contextvars import copy_context
from pathlib import Path
from unittest import mock

from literate_ai import project_releases as release
from literate_ai.adapters import _processes
from literate_ai.adapters import release_worktree_custody as custody
from tests.e2e import test_project_releases as release_fixture
from tests.smoke import test_bootstrap_litai as bootstrap_fixture


class StandaloneProcessCustodyTests(bootstrap_fixture.GeneratedBootstrapFixture):
    def test_digest_checked_synthetic_helper_runs_under_isolated_stdlib_python(self):
        probe = r"""
import json, runpy, subprocess, sys
assert sys.flags.isolated and sys.flags.no_site
assert not any(n == 'literate_ai' or n.startswith('literate_ai.') for n in sys.modules)
bootstrap = runpy.run_path(sys.argv[1], run_name='_standalone_bootstrap_probe')
helper = bootstrap['_process_owner']()
result = helper.run_with_tree_kill(
    [sys.executable, '-I', '-S', '-B', '-c', "print('standalone original runner')"],
    timeout=5, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
)
assert result.stdout == b'standalone original runner\n'
assert result.stderr == b''
assert helper._COMMAND_CUSTODY_OBSERVER.get() is None
assert not any(n == 'literate_ai' or n.startswith('literate_ai.') for n in sys.modules)
print(json.dumps({
    'synthetic_digest_loader': True, 'isolated': True, 'framework_imports': 0,
}))
"""
        result = subprocess.run(
            [sys.executable, "-I", "-S", "-B", "-c", probe, str(self.script)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "synthetic_digest_loader": True,
                "isolated": True,
                "framework_imports": 0,
            },
        )


class ReleaseCommandObserverTests(unittest.TestCase):
    def fixture(self, directory):
        fixture = release_fixture.ReleaseBackportTests("runTest")
        root = fixture.initialize(Path(directory))
        fixture.git(root, "branch", "release/1.0.x", "HEAD")
        return fixture, root

    def test_nested_noop_cannot_replace_active_original_release_observer(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, root = self.fixture(directory)
            before = fixture.git(root, "rev-parse", "HEAD")
            with release._release_backport_worktree(root, "release/1.0.x") as worktree:
                with self.assertRaisesRegex(ValueError, "cannot be replaced"):
                    with _processes._command_custody_scope(lambda _args: None):
                        self.fail("nested observer entered")
                with mock.patch.object(_processes.subprocess, "Popen") as launch:
                    with self.assertRaises(custody.ReleaseWorktreeCustodyError):
                        _processes.run_with_tree_kill(
                            [sys.executable, "-c", "pass"], timeout=5
                        )
                    launch.assert_not_called()
                # The rejected replacement leaves the original scope usable.
                self.assertEqual(
                    release._git_in(worktree, "status", "--porcelain").returncode, 0
                )
            self.assertFalse(worktree.parent.exists())
            self.assertNotIn(
                str(worktree), fixture.git(root, "worktree", "list", "--porcelain")
            )
            self.assertEqual(fixture.git(root, "rev-parse", "HEAD"), before)
            self.assertIsNone(_processes._COMMAND_CUSTODY_OBSERVER.get())

    def test_copied_expired_release_context_refuses_before_process_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture, root = self.fixture(directory)
            with release._release_backport_worktree(root, "release/1.0.x") as worktree:
                inherited = copy_context()
            self.assertFalse(worktree.parent.exists())
            with mock.patch.object(_processes.subprocess, "Popen") as launch:
                with self.assertRaises(custody.ReleaseWorktreeCustodyError):
                    inherited.run(
                        _processes.run_with_tree_kill,
                        ["git", "-C", str(worktree), "status", "--porcelain"],
                        timeout=5,
                    )
                launch.assert_not_called()
            self.assertNotIn(
                str(worktree), fixture.git(root, "worktree", "list", "--porcelain")
            )
            self.assertIsNone(_processes._COMMAND_CUSTODY_OBSERVER.get())
