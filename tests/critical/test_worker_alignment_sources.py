"""Local file stalls cannot strand alignment or prepare worker destinations."""

from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import alignment_file_source as sources
from literate_ai.adapters.worker_alignment import (
    AlignedFile,
    UserAlignment,
    WorkerAligner,
    WorkerAlignmentError,
    WorkerTemplate,
)
from literate_ai.contracts import (
    ExecutionRequirements,
    ExecutionWorker,
    ExecutionWorkerKind,
)


def worker():
    return ExecutionWorker(
        worker_id="source-fixture",
        kind=ExecutionWorkerKind.SSH,
        endpoint="user@worker.invalid",
        workspace="~/work",
        transport="ssh",
        requirements=ExecutionRequirements(os_family="linux"),
    )


def aligner(root, source):
    return WorkerAligner(
        WorkerTemplate({}),
        UserAlignment((AlignedFile(source, "~/.config/provider", True, ("linux",)),)),
        coding_cli=None,
        model=None,
        cwd=root,
    )


class WorkerAlignmentSourceTests(unittest.TestCase):
    def test_private_capture_retains_original_bytes_and_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "operator-file"
            original = b"private-fixture-value\n"
            source.write_bytes(original)
            with sources.capture_alignment_source(source) as (captured, digest):
                self.assertNotEqual(captured, source)
                self.assertEqual(captured.read_bytes(), original)
                self.assertEqual(digest, hashlib.sha256(original).hexdigest())
                if os.name == "posix":
                    self.assertEqual(captured.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(captured.parent.stat().st_mode & 0o777, 0o700)
                source.write_bytes(b"later operator revision")
                self.assertEqual(captured.read_bytes(), original)
            self.assertFalse(captured.parent.exists())
            self.assertEqual(source.read_bytes(), b"later operator revision")

    def test_missing_directory_and_oversized_sources_refuse_without_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            large = root / "large"
            with large.open("wb") as stream:
                stream.truncate(sources.MAX_SOURCE_BYTES + 1)
            # Windows can reject directory open before fstat; both are refusals.
            for source, codes in (
                (root / "missing", {"source-missing"}),
                (root, {"source-not-regular", "source-unreadable"}),
                (large, {"source-too-large"}),
            ):
                with self.subTest(source=source.name):
                    with self.assertRaises(sources.AlignmentSourceError) as caught:
                        with sources.capture_alignment_source(source):
                            self.fail("invalid source yielded a capture")
                    self.assertIn(caught.exception.code, codes)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "native FIFO support")
    def test_fifo_without_writer_refuses_instead_of_waiting_for_payload(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source-pipe"
            os.mkfifo(source)
            with self.assertRaises(sources.AlignmentSourceError) as caught:
                with sources.capture_alignment_source(source):
                    self.fail("a pipe cannot be an alignment file")
            self.assertEqual(caught.exception.code, "source-not-regular")

    @unittest.skipUnless(os.name == "posix", "native process absence observation")
    def test_stalled_reader_has_deadline_cleanup_and_no_secret_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pid_file = root / "reader-pid"
            code = (
                "import os,pathlib,sys,time;"
                f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()));"
                "print('private-fixture-value',file=sys.stderr,flush=True);"
                "time.sleep(30)"
            )
            # Only tighten the production deadline. A real child waits, and the
            # ordinary bounded process owner must retire it before returning.
            with (
                patch.object(sources, "_CAPTURE", code),
                patch.object(sources, "SOURCE_TIMEOUT_SECONDS", 1),
                self.assertRaises(sources.AlignmentSourceError) as caught,
            ):
                with sources.capture_alignment_source(root / "unused"):
                    self.fail("stalled child yielded a capture")
            self.assertEqual(caught.exception.code, "source-timeout")
            self.assertNotIn("private-fixture-value", str(caught.exception))
            pid = int(pid_file.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_inspection_reports_source_failure_without_alignment_or_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inspector = aligner(root, root / "absent")
            observed = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            with (
                patch.object(inspector, "_run", return_value=observed),
                patch.object(inspector, "_sync_file") as synchronize,
            ):
                result = inspector.align((worker(),), apply=True)
            self.assertFalse(result["aligned"])
            self.assertEqual(
                result["workers"][0]["findings"][0]["state"], "source-missing"
            )
            synchronize.assert_not_called()

    def test_sync_capture_failure_precedes_destination_preparation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inspector = aligner(root, root / "absent")
            with (
                patch.object(inspector, "_run") as execute,
                self.assertRaises(WorkerAlignmentError) as caught,
            ):
                inspector._sync_file(worker(), inspector.user.files[0], "fixture")
            self.assertEqual(
                caught.exception.code, "worker_alignment.source_unavailable"
            )
            execute.assert_not_called()

    def test_sync_upload_uses_capture_when_original_changes_during_prepare(self):
        from literate_ai.adapters.remote_transport import RemoteWorkerTransport

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "operator-file"
            source.write_bytes(b"original-fixture")
            inspector = aligner(root, source)
            observed = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
            uploaded = []

            def execute(*_args):
                source.write_bytes(b"later-fixture")
                return observed

            def upload(_transport, selected, *_args, **_kwargs):
                self.assertNotEqual(selected, source)
                self.assertEqual(selected.read_bytes(), b"original-fixture")
                uploaded.append(selected)
                return observed

            with (
                patch.object(inspector, "_run", side_effect=execute),
                patch.object(RemoteWorkerTransport, "upload", upload),
            ):
                inspector._sync_file(worker(), inspector.user.files[0], "fixture")
            self.assertEqual(len(uploaded), 1)
            self.assertFalse(uploaded[0].parent.exists())
            self.assertEqual(source.read_bytes(), b"later-fixture")
