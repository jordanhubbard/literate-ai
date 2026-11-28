"""Implicit Git discovery stops at a mount; explicit worktree markers still work."""

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import project_layout_planning as layout


class LayoutGitFilesystemBoundaryTests(unittest.TestCase):
    def test_different_device_ancestor_is_not_inspected_or_dispatched(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / "project"
            root.mkdir()
            device = root.lstat().st_dev
            original = Path.lstat

            def observe(path, *args, **kwargs):
                if path == parent:
                    return SimpleNamespace(st_dev=device + 1)
                if path == parent / ".git":
                    raise AssertionError("foreign filesystem marker inspected")
                return original(path, *args, **kwargs)

            with (
                mock.patch.object(Path, "lstat", observe),
                mock.patch.object(
                    layout, "run_bounded_process", side_effect=AssertionError
                ) as run,
            ):
                self.assertIsNone(layout._git_state(root))
            run.assert_not_called()

    def git(self, *arguments, cwd):
        environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        result = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            env=environment,
            capture_output=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return result

    def test_same_filesystem_ancestor_and_local_worktree_file_keep_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            repo = base / "repository"
            self.git("init", "-b", "main", str(repo), cwd=base)
            (repo / "original").write_text("original authority\n")
            self.git("add", "original", cwd=repo)
            self.git(
                "-c",
                "user.name=Git boundary test",
                "-c",
                "user.email=boundary@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "Original authority",
                cwd=repo,
            )
            child = repo / "project"
            child.mkdir()
            original = layout._git_state(repo)
            self.assertIsInstance(original, dict)
            nested = layout._git_state(child)
            self.assertEqual(nested["head"], original["head"])
            actual_index = self.git("ls-files", "--stage", "-z", cwd=child).stdout
            self.assertEqual(
                nested["index"], "sha256:" + hashlib.sha256(actual_index).hexdigest()
            )
            linked = base / "linked"
            self.git("worktree", "add", "--detach", str(linked), "HEAD", cwd=repo)
            self.assertTrue((linked / ".git").is_file())
            self.assertEqual(layout._git_state(linked), original)

    def test_unreadable_same_filesystem_marker_still_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            original = Path.lstat

            def observe(path, *args, **kwargs):
                if path == root / ".git":
                    raise PermissionError("unreadable original marker")
                return original(path, *args, **kwargs)

            with (
                mock.patch.object(Path, "lstat", observe),
                mock.patch.object(
                    layout, "run_bounded_process", side_effect=AssertionError
                ) as run,
            ):
                with self.assertRaises(PermissionError):
                    layout._git_state(root)
            run.assert_not_called()

    @unittest.skipIf(os.name == "nt", "native POSIX symlink marker")
    def test_same_filesystem_redirected_marker_still_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / ".git").symlink_to(root / "unavailable")
            with self.assertRaises(layout.ProjectLayoutPlanError) as caught:
                layout._git_state(root)
            self.assertEqual(caught.exception.code, "project.layout.git_unavailable")
