"""Actual retained upload-copy lifetime; no provider or wheel qualification claim."""

import hashlib
import shutil
import subprocess
import sys
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai import release_files as release
from literate_ai.adapters.project_runtime import (
    ProjectRuntimeError,
    allocate_project_runtime,
    close_project_runtime,
    project_runtime_scope,
)
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_runtime_cli as fixture

DATA = b"opaque retained release fixture bytes\n"


class ContainedStagedReleaseFileTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ProjectLayoutRuntimeCliTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.root = self.f.project.root
        self.source = self.f.framework / "_build/qualified/artifact.bin"
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(DATA)
        self.inode = self.source.stat().st_ino
        self.item = {
            "role": "package",
            "path": self.source.relative_to(self.root).as_posix(),
            "size": len(DATA),
            "identity": "sha256:" + hashlib.sha256(DATA).hexdigest(),
        }
        self.owner = allocate_project_runtime(self.f.project, nested=True)
        self.addCleanup(self.close)

    def close(self):
        if self.owner is not None:
            owner, self.owner = self.owner, None
            close_project_runtime(owner, keep=False)

    def consume(self, path):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import hashlib,pathlib,sys;"
                "data=pathlib.Path(sys.argv[1]).read_bytes();"
                "assert 'sha256:'+hashlib.sha256(data).hexdigest()==sys.argv[2]",
                str(path),
                self.item["identity"],
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_upload_copy_is_contained_readonly_and_retires(self):
        with project_runtime_scope(self.owner, self.f.project):
            with release.staged_release_file(self.root, self.item) as path:
                self.consume(path)
                self.assertTrue(path.is_relative_to(self.f.framework / "_build"), path)
                self.assertEqual(path.stat().st_mode & 0o222, 0)
        self.assertFalse(path.exists())
        self.assertEqual(self.source.stat().st_ino, self.inode)
        self.assertEqual(self.source.read_bytes(), DATA)

    def test_private_consumer_state_survives_refused_parent_runtime_close(self):
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(ValueError):
                with release.staged_release_file(self.root, self.item) as path:
                    self.consume(path)
                    private = path.parent / "operator-private"
                    private.write_bytes(b"retain private publisher state")
                    inode = private.stat().st_ino
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"retain private publisher state")
        self.assertEqual(self.source.stat().st_ino, self.inode)

    def test_equal_byte_foreign_copy_does_not_inherit_retirement(self):
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(ValueError):
                with release.staged_release_file(self.root, self.item) as path:
                    original = self.root / "retained-original-upload"
                    path.rename(original)
                    shutil.copyfile(original, path)
                    foreign, native = path.stat().st_ino, original.stat().st_ino
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertNotEqual(foreign, native)
        self.assertEqual(path.stat().st_ino, foreign)
        self.assertEqual(original.stat().st_ino, native)
        self.assertEqual(path.read_bytes(), original.read_bytes())

    def test_original_consumer_rejection_wins_over_private_disposal(self):
        refused = RuntimeError("original fixture publisher rejection")
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(RuntimeError) as caught:
                with release.staged_release_file(self.root, self.item) as path:
                    private = path.parent / "operator-private"
                    private.write_bytes(b"retain rejected publisher state")
                    inode = private.stat().st_ino
                    raise refused
        self.assertIs(caught.exception, refused)
        self.assertTrue(any("disposal refused" in note for note in refused.__notes__))
        with self.assertRaises(ProjectRuntimeError):
            self.close()
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"retain rejected publisher state")

    def test_actual_partial_copy_failure_preserves_error_and_retires_owned_bytes(self):
        from literate_ai.adapters.evidence_archive import _ArchiveBytes

        write = _ArchiveBytes.write
        refused = OSError("actual fixture copy write failure")

        def partial(writer, data):
            write(writer, data[:5])
            raise refused

        with project_runtime_scope(self.owner, self.f.project):
            runtime = self.owner.path
            with patch.object(_ArchiveBytes, "write", partial):
                with self.assertRaises(OSError) as caught:
                    with release.staged_release_file(self.root, self.item):
                        self.fail("partial copy admitted")
            self.assertIs(caught.exception, refused)
            self.assertEqual(list(runtime.glob(".rf-*")), [])
        self.assertEqual(self.source.stat().st_ino, self.inode)
        self.assertEqual(self.source.read_bytes(), DATA)

    def test_same_size_wrong_digest_still_refuses_before_handoff(self):
        item = {**self.item, "identity": "sha256:" + "0" * 64}
        with project_runtime_scope(self.owner, self.f.project):
            runtime = self.owner.path
            with self.assertRaises(ValueError):
                with release.staged_release_file(self.root, item):
                    self.fail("digest mismatch admitted")
            self.assertEqual(list(runtime.glob(".rf-*")), [])

    def test_fresh_standalone_capture_uses_actual_declared_receiver(self):
        self.close()
        with release.staged_release_file(self.root, self.item) as path:
            self.consume(path)
            self.assertTrue(path.is_relative_to(self.f.framework / "_build"))
        self.assertFalse(path.exists())
        self.assertEqual(self.source.stat().st_ino, self.inode)

    def test_foreign_active_runtime_cannot_supply_receiver_stage(self):
        other = self.root.parent / "foreign-release-receiver"
        ProjectConfigurationStore(other).create(
            replace(self.f.project.definition, project_id="foreign-release-receiver")
        )
        (other / "artifact.bin").write_bytes(DATA)
        item = {**self.item, "path": "artifact.bin"}
        with project_runtime_scope(self.owner, self.f.project):
            with self.assertRaises(ValueError):
                with release.staged_release_file(other, item):
                    self.fail("foreign receiver admitted")
        self.assertFalse((other / "litai/_build").exists())
