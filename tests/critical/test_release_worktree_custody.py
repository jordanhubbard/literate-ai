"""Actual Git worktree cleanup; project discovery is an explicit fixture seam."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai import project_releases as release
from tests.e2e import test_project_releases as release_fixture


class ReleaseWorktreeCustodyTests(unittest.TestCase):
    def check_private_backport(self, ignored):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = release_fixture.ReleaseBackportTests("runTest")
            root = fixture.initialize(Path(temporary))
            if ignored:
                fixture.commit_file(
                    root,
                    ".gitignore",
                    "operator-private\n",
                    "Ignore fixture private path",
                )
            fixture.git(root, "branch", "release/1.0.x", "HEAD")
            commit = fixture.commit_file(
                root,
                "feature.txt",
                "actual cherry-picked feature\n",
                "Add fixture feature",
            )
            original_head = fixture.git(root, "rev-parse", "HEAD")
            original_git = release._git_in
            seen = {}

            def git(directory, *arguments, **kwargs):
                result = original_git(directory, *arguments, **kwargs)
                if arguments[:1] == ("cherry-pick",) and result.returncode == 0:
                    private = directory / "operator-private"
                    private.write_bytes(b"retain original operator private bytes")
                    seen.update(path=private, inode=private.stat().st_ino)
                return result

            failure = None
            # Like the maintained release fixture, discovery supplies only a
            # framework-authoring profile. Git/source/checkout/cleanup are real.
            with (
                patch.object(
                    release,
                    "discover_project",
                    return_value=SimpleNamespace(
                        root=root,
                        definition=SimpleNamespace(
                            framework_directory=None,
                            repository_policy=SimpleNamespace(default_branch="main"),
                        ),
                    ),
                ),
                patch.object(release, "_git_in", side_effect=git),
            ):
                try:
                    release.backport_commits(
                        root,
                        commits=(commit,),
                        to_branch="release/1.0.x",
                        create_from=None,
                    )
                except release.ProjectReleaseError as error:
                    failure = error
            self.assertEqual(fixture.git(root, "rev-parse", "HEAD"), original_head)
            self.assertEqual(
                fixture.git(root, "symbolic-ref", "--short", "HEAD"), "main"
            )
            self.assertEqual((root / "file.txt").read_bytes(), b"base\n")
            self.assertTrue(
                seen["path"].is_file(), "original cleanup deleted operator-private file"
            )
            self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
            self.assertEqual(
                seen["path"].read_bytes(), b"retain original operator private bytes"
            )
            self.assertIn(
                str(seen["path"].parent),
                fixture.git(root, "worktree", "list", "--porcelain"),
            )
            self.assertIsNotNone(
                failure, "private cleanup conflict must refuse success"
            )

    def test_original_backport_retains_private_after_actual_cherry_pick(self):
        self.check_private_backport(ignored=False)

    def test_original_backport_retains_ignored_private_after_actual_cherry_pick(self):
        self.check_private_backport(ignored=True)

    def test_actual_clean_backport_retires_checkout_and_git_registration(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = release_fixture.ReleaseBackportTests("runTest")
            root = fixture.initialize(Path(temporary))
            fixture.git(root, "branch", "release/1.0.x", "HEAD")
            commit = fixture.commit_file(
                root, "feature.txt", "actual feature\n", "Add actual feature"
            )
            with release._release_backport_worktree(root, "release/1.0.x") as worktree:
                self.assertTrue(
                    worktree.is_relative_to(release._release_build_root(root))
                )
                release._git_in(worktree, "cherry-pick", "-x", commit)
                admin = Path(fixture.git(worktree, "rev-parse", "--absolute-git-dir"))
                self.assertTrue(admin.is_dir())
            self.assertFalse(worktree.parent.exists())
            self.assertFalse(admin.exists())
            self.assertEqual(
                fixture.git(root, "show", "release/1.0.x:feature.txt"), "actual feature"
            )
            self.assertEqual(
                fixture.git(root, "symbolic-ref", "--short", "HEAD"), "main"
            )
            self.assertEqual(
                fixture.git(root, "worktree", "list", "--porcelain").count("worktree "),
                1,
            )

    def test_original_error_wins_when_private_worktree_disposal_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = release_fixture.ReleaseBackportTests("runTest")
            root = fixture.initialize(Path(temporary))
            fixture.git(root, "branch", "release/1.0.x", "HEAD")
            rejected = release.ProjectReleaseError(
                "release.fixture_rejected", "actual caller rejection"
            )
            with self.assertRaises(release.ProjectReleaseError) as caught:
                with release._release_backport_worktree(
                    root, "release/1.0.x"
                ) as worktree:
                    private = worktree / "operator-private"
                    private.write_bytes(b"retain original caller failure private state")
                    inode = private.stat().st_ino
                    raise rejected
            self.assertIs(caught.exception, rejected)
            self.assertTrue(
                any("disposal refused" in note for note in rejected.__notes__)
            )
            self.assertEqual(private.stat().st_ino, inode)
            self.assertEqual(
                private.read_bytes(), b"retain original caller failure private state"
            )
            self.assertIn(
                str(worktree), fixture.git(root, "worktree", "list", "--porcelain")
            )

    def test_native_file_and_admin_replacements_do_not_inherit_cleanup(self):
        for changed in ("checkout", "admin-file", "admin-private"):
            with (
                self.subTest(changed=changed),
                tempfile.TemporaryDirectory() as temporary,
            ):
                fixture = release_fixture.ReleaseBackportTests("runTest")
                root = fixture.initialize(Path(temporary))
                fixture.git(root, "branch", "release/1.0.x", "HEAD")
                commit = fixture.commit_file(
                    root, "feature.txt", "actual feature\n", "Add actual feature"
                )
                with self.assertRaises(release.ProjectReleaseError):
                    with release._release_backport_worktree(
                        root, "release/1.0.x"
                    ) as worktree:
                        release._git_in(worktree, "cherry-pick", "-x", commit)
                        admin = Path(
                            fixture.git(worktree, "rev-parse", "--absolute-git-dir")
                        )
                        if changed == "admin-private":
                            foreign = admin / "operator-private"
                            foreign.write_bytes(b"retain private Git admin state")
                            original = None
                        else:
                            foreign = (
                                worktree / "feature.txt"
                                if changed == "checkout"
                                else admin / "HEAD"
                            )
                            original = Path(temporary) / "original-native-file"
                            foreign.rename(original)
                            foreign.write_bytes(original.read_bytes())
                        inode, content = foreign.stat().st_ino, foreign.read_bytes()
                self.assertEqual(foreign.stat().st_ino, inode)
                self.assertEqual(foreign.read_bytes(), content)
                if original is not None:
                    self.assertNotEqual(original.stat().st_ino, inode)
                    self.assertEqual(original.read_bytes(), content)
                self.assertIn(
                    str(worktree), fixture.git(root, "worktree", "list", "--porcelain")
                )

    def test_conflict_keeps_original_error_when_private_abort_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = release_fixture.ReleaseBackportTests("runTest")
            root = fixture.initialize(Path(temporary))
            fixture.git(root, "branch", "release/1.0.x", "HEAD")
            fixture.commit_file(
                root, "file.txt", "intermediate main\n", "Intermediate change"
            )
            commit = fixture.commit_file(
                root, "file.txt", "conflicting main\n", "Conflicting change"
            )
            original_git = release._git_in
            seen = {}

            def git(directory, *arguments, **kwargs):
                result = original_git(directory, *arguments, **kwargs)
                if arguments[:1] == ("cherry-pick",) and result.returncode:
                    private = directory / "operator-private"
                    private.write_bytes(
                        b"retain actual failed cherry-pick private state"
                    )
                    seen.update(path=private, inode=private.stat().st_ino)
                return result

            with (
                patch.object(
                    release,
                    "discover_project",
                    return_value=SimpleNamespace(
                        root=root,
                        definition=SimpleNamespace(
                            framework_directory=None,
                            repository_policy=SimpleNamespace(default_branch="main"),
                        ),
                    ),
                ),
                patch.object(release, "_git_in", side_effect=git),
                self.assertRaises(release.ProjectReleaseError) as caught,
            ):
                release.backport_commits(
                    root, commits=(commit,), to_branch="release/1.0.x", create_from=None
                )
            self.assertEqual(caught.exception.code, "release.backport_conflict")
            self.assertTrue(
                any("abort refused" in note for note in caught.exception.__notes__)
            )
            self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
            self.assertEqual(
                seen["path"].read_bytes(),
                b"retain actual failed cherry-pick private state",
            )

    @unittest.skipUnless(os.name == "posix", "actual POSIX Git hook/group control")
    def test_successful_git_parent_cannot_leave_an_active_descendant(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = release_fixture.ReleaseBackportTests("runTest")
            parent = Path(temporary)
            root = fixture.initialize(parent)
            fixture.git(root, "branch", "release/1.0.x", "HEAD")
            counter, ready = parent / "counter", parent / "ready"
            child = (
                "import pathlib,sys,time\np=pathlib.Path(sys.argv[1])\ni=0\n"
                "while True:\n i+=1\n p.write_text(str(i))\n time.sleep(0.02)\n"
            )
            hook = root / ".git/hooks/post-checkout"
            hook.write_text(
                "#!" + sys.executable + "\nimport pathlib,subprocess,sys,time\n"
                "counter=pathlib.Path(" + repr(str(counter)) + ")\n"
                "child=subprocess.Popen([sys.executable,'-c',"
                + repr(child)
                + ",str(counter)],stdin=subprocess.DEVNULL,"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                "while not counter.exists(): time.sleep(0.01)\n"
                "pathlib.Path(" + repr(str(ready)) + ").write_text(str(child.pid))\n"
            )
            hook.chmod(0o755)
            with self.assertRaises(release.ProjectReleaseError) as caught:
                with release._release_backport_worktree(root, "release/1.0.x"):
                    self.fail("unquiesced original Git group was admitted")
            self.assertEqual(
                caught.exception.code, "release.worktree_custody_unavailable"
            )
            self.assertTrue(ready.exists())
            before = counter.read_bytes()
            time.sleep(0.15)
            self.assertEqual(counter.read_bytes(), before)
            self.assertEqual(len(list((root / "_build").glob(".rw-*"))), 1)
            self.assertIn("rw-", fixture.git(root, "worktree", "list", "--porcelain"))
