"""Disposable native seeds stay quiescent despite external Git auto policy."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.support import native_repository as fixtures


class NativeFixtureGitPolicyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        global_config = self.root / "global.gitconfig"
        self.external_policy = b"[maintenance]\n\tauto = true\n[gc]\n\tauto = 1\n"
        global_config.write_bytes(self.external_policy)
        self.global_config = global_config
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        environment.update(
            GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(global_config)
        )
        self.environment = patch.dict(os.environ, environment, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.seed = fixtures.NativeRepositoryFixture("runTest")
        self.addCleanup(self.seed.doCleanups)
        self.seed.setUp()

    def raw_git(self, root, *args):
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            capture_output=True,
            timeout=20,
        ).stdout.strip()

    def test_seed_and_independent_checkout_bind_local_policy_before_copy(self):
        independent = self.root / "independent"
        independent.mkdir()
        (independent / "source").write_bytes(b"retained native source\n")
        fixtures.commit_independent_repository(independent)
        for index, root in enumerate((self.seed.root, independent)):
            with self.subTest(kind=index):
                self.assertEqual(
                    self.raw_git(root, "config", "--bool", "maintenance.auto"), b"false"
                )
                self.assertEqual(self.raw_git(root, "config", "--int", "gc.auto"), b"0")
                copied = self.root / f"copy-{index}"
                shutil.copytree(root, copied)
                self.raw_git(copied, "fsck", "--full")
                self.assertEqual(
                    self.raw_git(root, "rev-parse", "HEAD"),
                    self.raw_git(copied, "rev-parse", "HEAD"),
                )
        self.seed.assert_original()
        self.assertEqual(self.global_config.read_bytes(), self.external_policy)

    def test_command_policy_overrides_contrary_local_values_without_rewriting(self):
        self.raw_git(self.seed.root, "config", "--local", "maintenance.auto", "true")
        self.raw_git(self.seed.root, "config", "--local", "gc.auto", "1")
        original = (self.seed.root / ".git" / "config").read_bytes()
        for name, expected in (("maintenance.auto", "false"), ("gc.auto", "0")):
            with self.subTest(name=name):
                self.assertEqual(self.seed.git("config", "--get", name), expected)
                self.assertEqual(
                    fixtures.git_at(self.seed.root, "config", "--get", name).strip(),
                    expected.encode("ascii"),
                )
        self.assertEqual((self.seed.root / ".git" / "config").read_bytes(), original)
        self.assertEqual(self.global_config.read_bytes(), self.external_policy)
