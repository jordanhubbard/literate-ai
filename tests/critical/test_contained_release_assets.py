"""Actual local downloader processes/files; no HTTP or real GitHub qualification."""

import hashlib
import shutil
import subprocess
import sys
import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai import project_releases as release
from literate_ai.adapters import builders
from literate_ai.adapters.project_runtime import (
    allocate_project_runtime,
    close_project_runtime,
    project_runtime_scope,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_runtime_cli as fixture

DATA = b"actual fixture release asset payload\n"
NAME = "fixture-release.bin"


class ContainedReleaseAssetTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ProjectLayoutRuntimeCliTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.project.root
        self.tools = self.root / "fixture-tools"
        self.tools.mkdir()
        self.gh = self.tools / "gh.py"
        self.write_downloader()
        self.owner = allocate_project_runtime(self.f.project, nested=True)
        self.addCleanup(self.close)
        self.seen = []
        self.artifacts = {
            "files": [
                {
                    "path": "litai/_build/" + NAME,
                    "size": len(DATA),
                    "identity": "sha256:" + hashlib.sha256(DATA).hexdigest(),
                }
            ]
        }

    def write_downloader(self, extra=""):
        self.gh.write_text(
            "import pathlib,sys\n"
            "args=sys.argv[1:]\n"
            "assert args[:2]==['release','download']\n"
            "directory=pathlib.Path(args[args.index('--dir')+1])\n"
            "name=args[args.index('--pattern')+1]\n"
            "(directory/name).write_bytes(" + repr(DATA) + ")\n" + extra
        )

    def close(self):
        if self.owner is not None:
            owner, self.owner = self.owner, None
            close_project_runtime(owner, keep=False)

    def observe(self, original, after=None):
        def run(command, *args, **kwargs):
            directory = None
            if command[0] == "gh":
                directory = Path(command[command.index("--dir") + 1])
                self.seen.append(directory)
            # Supply only the local downloader transport. The original runner
            # creates/owns the real child and observes its actual output files.
            actual = (
                [sys.executable, str(self.gh), *command[1:]]
                if directory is not None
                else command
            )
            result = original(actual, *args, **kwargs)
            if directory is not None and after is not None:
                after(directory)
            return result

        return run

    def verify(self, after=None, root=None):
        scope = (
            project_runtime_scope(self.owner, self.f.project)
            if self.owner is not None
            else nullcontext()
        )
        with scope:
            # Both ports delegate to their actual original process creator.
            # Legacy and contained paths differ, but neither result is supplied.
            with (
                patch.object(
                    release.subprocess, "run", self.observe(subprocess.run, after)
                ),
                patch.object(
                    builders,
                    "run_bounded_process",
                    self.observe(builders.run_bounded_process, after),
                ),
            ):
                release._verify_release_file_assets(
                    self.root if root is None else root,
                    "fixture/repository",
                    "v1.0.0",
                    self.artifacts,
                )

    def test_00_original_downloader_output_is_contained_and_retired(self):
        self.verify()
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(
            self.seen[0].is_relative_to(self.f.framework / "_build"), self.seen[0]
        )
        self.assertFalse(self.seen[0].exists())

    def test_original_size_and_same_size_digest_mismatches_still_refuse(self):
        original = dict(self.artifacts["files"][0])
        for changed in (
            {**original, "size": len(DATA) + 1},
            {**original, "identity": "sha256:" + "0" * 64},
        ):
            with self.subTest(changed=changed):
                self.artifacts["files"][0] = changed
                with self.assertRaises(release.ProjectReleaseError) as caught:
                    self.verify()
                self.assertEqual(
                    caught.exception.code, "release.published_artifact_mismatch"
                )
                self.assertFalse(self.seen[-1].exists())

    def test_actual_nonzero_downloader_retains_original_mismatch_error(self):
        self.write_downloader("sys.exit(7)\n")
        with self.assertRaises(release.ProjectReleaseError) as caught:
            self.verify()
        self.assertEqual(caught.exception.code, "release.published_artifact_mismatch")
        self.assertFalse(self.seen[-1].exists())

    def test_private_after_actual_process_is_preserved_through_runtime_close(self):
        seen = {}

        def private(directory):
            path = directory / "operator-private"
            path.write_bytes(b"retain native readback private state")
            seen.update(path=path, inode=path.stat().st_ino)

        with self.assertRaises(release.ProjectReleaseError):
            self.verify(private)
        self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])
        self.assertEqual(
            seen["path"].read_bytes(), b"retain native readback private state"
        )

    def test_equal_byte_replacement_after_actual_process_keeps_both_inodes(self):
        seen = {}

        def replace_file(directory):
            path = directory / NAME
            original = self.root / "original-downloaded-fixture"
            path.rename(original)
            shutil.copyfile(original, path)
            seen.update(
                path=path,
                original=original,
                original_inode=original.stat().st_ino,
                foreign_inode=path.stat().st_ino,
            )

        with self.assertRaises(release.ProjectReleaseError):
            self.verify(replace_file)
        self.close()
        self.assertNotEqual(seen["original_inode"], seen["foreign_inode"])
        self.assertEqual(seen["path"].stat().st_ino, seen["foreign_inode"])
        self.assertEqual(seen["original"].stat().st_ino, seen["original_inode"])
        self.assertEqual(seen["path"].read_bytes(), seen["original"].read_bytes())

    def test_actual_rejection_wins_over_private_disposal_conflict(self):
        self.write_downloader("sys.exit(9)\n")
        seen = {}

        def private(directory):
            path = directory / "operator-private"
            path.write_bytes(b"retain failed readback private state")
            seen.update(path=path, inode=path.stat().st_ino)

        with self.assertRaises(release.ProjectReleaseError) as caught:
            self.verify(private)
        self.assertEqual(caught.exception.code, "release.published_artifact_mismatch")
        self.assertTrue(
            any("disposal refused" in note for note in caught.exception.__notes__)
        )
        self.close()
        self.assertEqual(seen["path"].stat().st_ino, seen["inode"])

    def test_actual_downloader_deadline_is_enforced_by_original_process_owner(self):
        self.write_downloader("import time; time.sleep(30)\n")
        original = builders.run_bounded_process

        def short(command, **kwargs):
            kwargs["timeout_seconds"] = 0.25
            return original(command, **kwargs)

        with patch.object(builders, "run_bounded_process", side_effect=short):
            with self.assertRaises(release.ProjectReleaseError) as caught:
                self.verify()
        self.assertEqual(caught.exception.code, "release.published_artifact_mismatch")
        self.assertEqual(
            caught.exception.__cause__.code, "release.asset_download_timeout"
        )
        self.assertFalse(self.seen[-1].exists())

    def test_fresh_standalone_readback_uses_actual_declared_project(self):
        self.close()
        self.verify()
        self.assertTrue(self.seen[-1].is_relative_to(self.f.framework / "_build"))
        self.assertFalse(self.seen[-1].exists())

    def test_foreign_runtime_cannot_issue_download_workspace(self):
        other = self.root.parent / "foreign-asset-project"
        ProjectConfigurationStore(other).create(
            replace(self.f.project.definition, project_id="foreign-asset-project")
        )
        with self.assertRaises(release.ProjectReleaseError) as caught:
            self.verify(root=other)
        self.assertEqual(caught.exception.code, "release.asset_staging_unavailable")
        self.assertEqual(self.seen, [])
        self.assertFalse((other / "litai/_build").exists())

    def test_actual_downloader_link_never_reads_external_private_target(self):
        target = self.root / "operator-private-target"
        target.write_bytes(b"retain external private asset target")
        inode = target.stat().st_ino
        self.write_downloader(
            "(directory/name).unlink()\n(directory/name).symlink_to("
            + repr(str(target))
            + ")\n"
        )
        with self.assertRaises(release.ProjectReleaseError):
            self.verify()
        self.assertEqual(target.stat().st_ino, inode)
        self.assertEqual(target.read_bytes(), b"retain external private asset target")
