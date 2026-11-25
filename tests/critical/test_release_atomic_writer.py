"""Actual release create/replace/cleanup operations; no write success mocks."""

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as release
from tests.e2e import test_project_releases as release_fixture


class ReleaseAtomicWriterTests(unittest.TestCase):
    def test_foreign_temporary_file_survives_original_replace_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "version.txt"
            target.write_bytes(b"original target")
            target_inode = target.stat().st_ino
            refused = OSError("actual fixture replace refused")
            seen = {}

            def replace(source, destination, **kwargs):
                temporary = root / Path(source)
                original = root / "retained-original-creator"
                temporary.rename(original)
                temporary.write_bytes(b"operator-private replacement")
                seen.update(
                    temporary=temporary,
                    original=original,
                    inode=temporary.stat().st_ino,
                )
                raise refused

            with patch.object(release.os, "replace", side_effect=replace):
                with self.assertRaises(OSError) as caught:
                    release._atomic_write_bytes(target, b"new controlled target")
            self.assertIs(caught.exception, refused)
            self.assertEqual(target.read_bytes(), b"original target")
            self.assertEqual(target.stat().st_ino, target_inode)
            self.assertTrue(
                seen["temporary"].exists(),
                "original cleanup deleted foreign temporary replacement",
            )
            self.assertEqual(seen["temporary"].stat().st_ino, seen["inode"])
            self.assertEqual(
                seen["temporary"].read_bytes(), b"operator-private replacement"
            )
            self.assertEqual(seen["original"].read_bytes(), b"new controlled target")

    def test_actual_success_preserves_bytes_mode_and_retires_original_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "version.txt"
            target.write_bytes(b"before")
            target.chmod(0o751)
            release._atomic_write_bytes(target, b"actual written bytes")
            self.assertEqual(target.read_bytes(), b"actual written bytes")
            if os.name == "posix":
                self.assertEqual(target.stat().st_mode & 0o777, 0o751)
            self.assertEqual(list(root.iterdir()), [target])

    def test_foreign_target_before_publication_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "version.txt"
            target.write_bytes(b"original target")
            original_inode = target.stat().st_ino
            native = release.os.fsync
            seen = {}

            def changed(descriptor):
                native(descriptor)
                retained = root / "original-target"
                target.rename(retained)
                target.write_bytes(b"operator-private target")
                seen.update(retained=retained, inode=target.stat().st_ino)

            with patch.object(release.os, "fsync", side_effect=changed):
                with self.assertRaises(ValueError):
                    release._atomic_write_bytes(target, b"new controlled target")
            self.assertEqual(target.stat().st_ino, seen["inode"])
            self.assertEqual(target.read_bytes(), b"operator-private target")
            self.assertEqual(seen["retained"].stat().st_ino, original_inode)
            self.assertEqual(seen["retained"].read_bytes(), b"original target")

    def test_unverified_original_temp_payload_is_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "version.txt"
            target.write_bytes(b"original target")
            native = release.os.fsync
            seen = {}

            def changed(descriptor):
                native(descriptor)
                temporary = next(root.glob(".version.txt.release-*"))
                temporary.write_bytes(b"operator-private unverified payload")
                seen.update(path=temporary, inode=temporary.stat().st_ino)

            with patch.object(release.os, "fsync", side_effect=changed):
                with self.assertRaises(ValueError):
                    release._atomic_write_bytes(target, b"new")
            self.assertEqual(target.read_bytes(), b"original target")
            self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
            self.assertEqual(
                seen["path"].read_bytes(), b"operator-private unverified payload"
            )

    def test_original_physical_error_and_real_transaction_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            first, second = root / "first.txt", root / "second.txt"
            first.write_bytes(b"first original")
            second.write_bytes(b"second original")
            native = release.os.fsync
            refused = OSError("actual fixture fsync failure")
            count = [0]

            def fail_second(descriptor):
                count[0] += 1
                if count[0] == 2:
                    raise refused
                return native(descriptor)

            with patch.object(release.os, "fsync", side_effect=fail_second):
                with self.assertRaises(release.ProjectReleaseError) as caught:
                    release._write_transaction(
                        ((first, "new first"), (second, "new second"))
                    )
            self.assertEqual(caught.exception.code, "release.prepare_write_failed")
            self.assertIs(caught.exception.__cause__, refused)
            self.assertEqual(first.read_bytes(), b"first original")
            self.assertEqual(second.read_bytes(), b"second original")
            self.assertEqual(list(root.glob(".*.release-*")), [])

    def test_atomic_file_joins_original_live_git_output_before_next_command(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = release_fixture.ReleaseBackportTests("runTest")
            root = fixture.initialize(Path(directory))
            fixture.git(root, "branch", "release/1.0.x", "HEAD")
            with release._release_backport_worktree(root, "release/1.0.x") as worktree:
                release._atomic_write_bytes(
                    worktree / "file.txt", b"actual original writer\n"
                )
                release._git_in(worktree, "add", "file.txt")
                release._git_in(worktree, "commit", "-m", "Actual atomic source")
            self.assertEqual(
                fixture.git(root, "show", "release/1.0.x:file.txt"),
                "actual original writer",
            )
            self.assertEqual((root / "file.txt").read_bytes(), b"base\n")
            self.assertFalse(worktree.parent.exists())

    def test_actual_local_bare_default_advancement_and_clean_retirement(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = release_fixture.ProjectReleaseTests("runTest")
            root, remote = fixture.initialize(Path(directory))
            policy = replace(
                release.ReleasePolicy.from_dict(
                    json.loads((root / "literate.release.json").read_text())
                ),
                default_branch="main",
            )
            original = fixture.git(root, "rev-parse", "HEAD")
            result = release._advance_default_branch_after_publish(
                root,
                policy,
                published_branch="release/1.2.x",
                published_version="1.2.3",
            )
            self.assertEqual(result["action"], "advanced", result)
            self.assertEqual(
                json.loads(fixture.git(remote, "show", "main:project.json"))["version"],
                "1.2.4",
            )
            self.assertIn("1.2.4", fixture.git(remote, "show", "main:version.py"))
            self.assertEqual(fixture.git(root, "rev-parse", "HEAD"), original)
            self.assertEqual(
                json.loads((root / "project.json").read_text())["version"], "1.2.3"
            )
            self.assertEqual(list((root / "_build").glob(".rw-*")), [])

    def test_private_after_actual_default_write_refuses_push_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = release_fixture.ProjectReleaseTests("runTest")
            root, remote = fixture.initialize(Path(directory))
            policy = replace(
                release.ReleasePolicy.from_dict(
                    json.loads((root / "literate.release.json").read_text())
                ),
                default_branch="main",
            )
            original = fixture.git(remote, "rev-parse", "main")
            write = release._atomic_write_bytes
            seen = {}

            def private(path, data):
                write(path, data)
                if not seen:
                    marker = path.parent / "operator-private"
                    marker.write_bytes(b"retain original advancement private state")
                    seen.update(path=marker, inode=marker.stat().st_ino)

            with patch.object(release, "_atomic_write_bytes", side_effect=private):
                result = release._advance_default_branch_after_publish(
                    root,
                    policy,
                    published_branch="release/1.2.x",
                    published_version="1.2.3",
                )
            self.assertEqual(result["action"], "failed", result)
            self.assertEqual(fixture.git(remote, "rev-parse", "main"), original)
            self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
            self.assertEqual(
                seen["path"].read_bytes(), b"retain original advancement private state"
            )
            self.assertIn(
                str(seen["path"].parent),
                fixture.git(root, "worktree", "list", "--porcelain"),
            )

    def test_real_transaction_rollback_preserves_live_output_custody(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = release_fixture.ReleaseBackportTests("runTest")
            root = fixture.initialize(Path(directory))
            fixture.git(root, "branch", "release/1.0.x", "HEAD")
            native = release.os.fsync
            refused = OSError("actual owned transaction fsync failure")
            count = [0]

            def fail_second(descriptor):
                count[0] += 1
                if count[0] == 2:
                    raise refused
                return native(descriptor)

            with release._release_backport_worktree(root, "release/1.0.x") as worktree:
                # Both existing tracked files are actual original Git outputs.
                first, second = (
                    worktree / "file.txt",
                    worktree / "literate.project.json",
                )
                before = first.read_bytes(), second.read_bytes()
                with patch.object(release.os, "fsync", side_effect=fail_second):
                    with self.assertRaises(release.ProjectReleaseError) as caught:
                        release._write_transaction(
                            ((first, "new first"), (second, "new second"))
                        )
                self.assertIs(caught.exception.__cause__, refused)
                self.assertEqual((first.read_bytes(), second.read_bytes()), before)
                self.assertEqual(list(worktree.glob(".*.release-*")), [])
                self.assertEqual(
                    release._git_in(worktree, "status", "--porcelain").stdout.strip(),
                    "",
                )
            self.assertFalse(worktree.parent.exists())

    def test_original_strict_git_prefix_is_preserved_for_detached_creator(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = release_fixture.ReleaseBackportTests("runTest")
            root = fixture.initialize(Path(directory))
            token = release._STRICT_CI_GIT_READS.set(True)
            try:
                with release._release_backport_worktree(
                    root, "HEAD", detached=True
                ) as worktree:
                    release._atomic_write_bytes(
                        worktree / "file.txt", b"actual strict creator\n"
                    )
                    self.assertEqual(
                        release._git_in(worktree, "rev-parse", "HEAD").stdout.strip(),
                        fixture.git(root, "rev-parse", "HEAD"),
                    )
            finally:
                release._STRICT_CI_GIT_READS.reset(token)
            self.assertFalse(worktree.parent.exists())

    def test_isolated_default_helper_skips_an_already_ahead_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = release_fixture.ProjectReleaseTests("runTest")
            root, remote = fixture.initialize(Path(directory))
            policy = replace(
                release.ReleasePolicy.from_dict(
                    json.loads((root / "literate.release.json").read_text())
                ),
                default_branch="main",
            )
            original = fixture.git(remote, "rev-parse", "main")
            result = release._advance_default_branch_after_publish(
                root,
                policy,
                published_branch="release/1.2.x",
                published_version="1.2.2",
            )
            self.assertEqual(result["action"], "skipped", result)
            self.assertEqual(fixture.git(remote, "rev-parse", "main"), original)
            self.assertEqual(list((root / "_build").glob(".rw-*")), [])
