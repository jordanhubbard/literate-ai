"""Original local staging creation, copy/archive joins and disposal ownership."""

from __future__ import annotations

import copy
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import remote_execution as remote
from tests.critical import test_project_layout_receiver_runtime as journeys


class EvidenceStagingOwnerTests(unittest.TestCase):
    def journey(self):
        journey = journeys.ReceiverRuntimeTests("runTest")
        journey.setUp()
        self.addCleanup(journey.doCleanups)
        return journey

    def test_00_unrecorded_private_entry_after_archive_is_preserved(self):
        journey = self.journey()
        observed = []
        original = remote._write_deterministic_tar_gz

        def archive(source, *args, **kwargs):
            identity = original(source, *args, **kwargs)
            private = source / "private-note.txt"
            private.write_bytes(b"unrecorded private fixture; preserve\n")
            observed.append((private, private.stat().st_ino))
            return identity

        with (
            patch.object(remote, "_write_deterministic_tar_gz", archive),
            patch.object(
                remote,
                "resolve_host_paths",
                return_value=SimpleNamespace(
                    temporary_root=str(journey.f.base / "host-stage")
                ),
            ),
            self.assertRaises(remote.RemoteExecutionError),
        ):
            journey.test_archive_evidence_import_has_disjoint_scopes_and_no_live_control_token()
        self.assertEqual(len(observed), 1)
        private, inode = observed[0]
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(
            private.read_bytes(), b"unrecorded private fixture; preserve\n"
        )

    def parent(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name).resolve()

    def test_original_self_and_copy_writers_archive_and_retire_native_stage(self):
        from literate_ai.adapters.evidence_staging import evidence_staging

        parent = self.parent()
        source = parent / "input"
        source.mkdir()
        payload = b"actual stream\n" * 100000
        (source / "a.bin").write_bytes(payload)
        (source / "a.bin").chmod(0o751)
        os.link(source / "a.bin", source / "b.bin")
        with evidence_staging(parent, prefix="stage-") as stage:
            path = stage.path
            row = stage.write("manifest/result.json", b'{"fixture":true}')
            files, totals = [], [0]
            remote._copy_evidence_tree(
                source,
                path,
                "object/cache",
                files=files,
                totals=totals,
                _output_owner=stage,
            )
            self.assertEqual(totals, [2 * len(payload)])
            stage.seal()
            archive = parent / "result.tar.gz"
            remote._write_deterministic_tar_gz(path, archive, _source_owner=stage)
            with tarfile.open(archive, "r:gz") as bundle:
                self.assertEqual(
                    bundle.getnames(),
                    [row.relative, "object/cache/a.bin", "object/cache/b.bin"],
                )
                self.assertEqual(
                    bundle.extractfile("object/cache/a.bin").read(), payload
                )
                self.assertEqual(bundle.getmember("object/cache/a.bin").mode, 0o755)
        self.assertFalse(path.exists())
        self.assertEqual((source / "a.bin").read_bytes(), payload)

    def test_equal_byte_foreign_postimage_after_archive_is_preserved(self):
        journey = self.journey()
        original = remote._write_deterministic_tar_gz
        observed = []
        retained = journey.f.base / "retained-result.json"

        def replace(source, *args, **kwargs):
            identity = original(source, *args, **kwargs)
            file = source / "manifest/lifecycle-result.json"
            file.rename(retained)
            file.write_bytes(retained.read_bytes())
            observed.append((file, file.stat().st_ino))
            return identity

        with patch.object(remote, "_write_deterministic_tar_gz", replace):
            with self.assertRaises(remote.RemoteExecutionError):
                journey.test_archive_evidence_import_has_disjoint_scopes_and_no_live_control_token()
        self.assertEqual(len(observed), 1)
        file, inode = observed[0]
        self.assertEqual(file.stat().st_ino, inode)
        self.assertEqual(file.read_bytes(), retained.read_bytes())

    def test_original_rejection_survives_stage_disposal_conflict(self):
        from literate_ai.adapters.evidence_staging import evidence_staging

        parent = self.parent()
        with self.assertRaisesRegex(RuntimeError, "original rejection") as raised:
            with evidence_staging(parent, prefix="stage-") as stage:
                path = stage.path
                stage.write("result", b"owned bytes")
                stage.seal()
                private = path / "private"
                private.write_bytes(b"private fixture")
                inode = private.stat().st_ino
                raise RuntimeError("original rejection")
        self.assertTrue(
            any("Stage disposal refused" in note for note in raised.exception.__notes__)
        )
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"private fixture")

    def test_copied_or_retired_stage_cannot_create_files(self):
        from literate_ai.adapters.evidence_staging import (
            EvidenceStagingError,
            evidence_staging,
        )

        parent = self.parent()
        with evidence_staging(parent, prefix="stage-") as stage:
            path = stage.path
            with self.assertRaises(EvidenceStagingError):
                copy.copy(stage).write("foreign", b"denied")
            self.assertFalse((path / "foreign").exists())
        with self.assertRaises(EvidenceStagingError):
            stage.write("foreign", b"denied")
        self.assertFalse(path.exists())

    def test_original_partial_writer_is_owned_and_retired_on_failure(self):
        from literate_ai.adapters.evidence_staging import evidence_staging

        parent = self.parent()
        original, writes = os.write, []

        def fail(descriptor, payload):
            if not writes:
                writes.append(True)
                return original(descriptor, payload[:3])
            raise OSError("controlled original writer failure")

        with self.assertRaisesRegex(OSError, "controlled original writer failure"):
            with evidence_staging(parent, prefix="stage-") as stage:
                path = stage.path
                with patch.object(os, "write", fail):
                    stage.write("payload", b"original bytes")
        self.assertEqual(writes, [True])
        self.assertFalse(path.exists())

    def test_contained_receiver_stage_uses_original_reserved_parent(self):
        journey = self.journey()
        original, seen = remote._write_deterministic_tar_gz, []

        def observe(source, *args, **kwargs):
            self.assertIn("litai", source.parts)
            self.assertIn("_build", source.parts)
            self.assertTrue(source.parent.name.startswith(".rt-"))
            seen.append(source)
            return original(source, *args, **kwargs)

        with patch.object(remote, "_write_deterministic_tar_gz", observe):
            journey.test_archive_evidence_import_has_disjoint_scopes_and_no_live_control_token()
        self.assertEqual(len(seen), 1)
        self.assertFalse(seen[0].exists())

    def test_windows_api_model_original_stage_writers_disposal_and_receiver(self):
        from literate_ai.adapters.evidence_staging import evidence_staging
        from tests.critical.test_remote_cleanup_windows_handles import WindowsFacade

        parent = self.parent()
        with WindowsFacade(self).installed() as model:
            with evidence_staging(parent, prefix="stage-") as stage:
                path = stage.path
                stage.write("manifest/result.json", b'{"owned":true}')
                stage.seal()
                remote._write_deterministic_tar_gz(
                    path, parent / "evidence.tar.gz", _source_owner=stage
                )
            self.assertFalse(path.exists())
            self.assertTrue(model.calls)
            journey = self.journey()
            journey.test_archive_evidence_import_has_disjoint_scopes_and_no_live_control_token()

    def test_primary_writer_rejection_survives_final_read_handle_close_failure(self):
        from literate_ai.adapters import evidence_staging as staging

        parent = self.parent()
        identify, close = staging._descriptor_identity, os.close
        readers, observed = [], []

        def identity(access, descriptor):
            value = identify(access, descriptor)
            observed.append(descriptor)
            if len(observed) == 2:
                readers.append(descriptor)
            return value

        def close_reader(descriptor):
            close(descriptor)
            if readers and descriptor == readers[0]:
                readers.clear()
                raise OSError("controlled final read handle close failure")

        with self.assertRaisesRegex(
            RuntimeError, "original writer rejection"
        ) as raised:
            with staging.evidence_staging(parent, prefix="stage-") as stage:
                path = stage.path
                with (
                    patch.object(staging, "_descriptor_identity", identity),
                    patch.object(os, "close", close_reader),
                    patch.object(
                        os,
                        "write",
                        side_effect=RuntimeError("original writer rejection"),
                    ),
                ):
                    stage.write("payload", b"original bytes")
        self.assertFalse(readers)
        self.assertTrue(
            any("read handle" in note for note in raised.exception.__notes__)
        )
        self.assertTrue(path.exists())
