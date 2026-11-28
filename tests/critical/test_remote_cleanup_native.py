"""Owned local cleanup controls; no configured workers or NAS operations."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import remote_cleanup as cleanup
from literate_ai.adapters import remote_execution as remote
from literate_ai.contracts import (
    RemoteEvidenceFile,
    RemoteLifecycleEvidenceManifest,
    canonical_json_bytes,
)
from tests.critical.test_remote_execution import identity


class NativeCleanupTests(unittest.TestCase):
    def test_00_legacy_ticket_cannot_delete_a_replaced_workspace(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            request, manifest, bundle = identity("1"), identity("2"), identity("3")
            workspace = base / (request.digest[:24] + "-original")
            workspace.mkdir()
            (workspace / "old").write_bytes(b"owned original\n")
            workspace.rename(base / "retained-original")
            workspace.mkdir()
            private = workspace / "private.txt"
            private.write_bytes(b"foreign replacement\n")
            inode = private.stat().st_ino
            ticket = base / "ticket.json"
            ticket.write_bytes(
                canonical_json_bytes(
                    {
                        "schema": "literate-ai/remote-evidence-cleanup-ticket@1",
                        "cleanup_token": "a" * 32,
                        "request_identity": request.uri,
                        "manifest_identity": manifest.uri,
                        "bundle_identity": bundle.uri,
                        "roots": [str(workspace)],
                    }
                )
            )
            with self.assertRaises(remote.RemoteExecutionError):
                remote.acknowledge_remote_evidence_cleanup(
                    ticket,
                    manifest_identity=manifest,
                    bundle_identity=bundle,
                    acknowledgement_root=base / "acks",
                )
            self.assertEqual(private.stat().st_ino, inode)
            self.assertEqual(private.read_bytes(), b"foreign replacement\n")
            self.assertTrue(json.loads(ticket.read_bytes()))

    def prepare(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.workspace = self.base / "workspace"
        self.workspace.mkdir()
        (self.workspace / "first.txt").write_bytes(b"original first\n")
        nested = self.workspace / "child"
        nested.mkdir()
        (nested / "last.txt").write_bytes(b"original last\n")
        self.original_inode = self.workspace.stat().st_ino
        self.ticket = self.base / "ticket.json"
        self.acks = self.base / "acks"
        self.token = uuid.uuid4().hex
        with cleanup.hold_cleanup_root(self.workspace, self.workspace.lstat()) as owner:
            self.intent = cleanup.capture_cleanup_intent(
                (owner,),
                request_identity=identity("1"),
                cleanup_token=self.token,
                ticket=self.ticket,
            )
        data = canonical_json_bytes(self.intent)
        self.manifest = RemoteLifecycleEvidenceManifest(
            *([identity("1")] * 10),
            "test",
            "passed",
            identity("2"),
            identity("3"),
            None,
            None,
            (),
            (
                RemoteEvidenceFile(
                    cleanup.INTENT_PATH,
                    "manifest",
                    len(data),
                    identity_from_bytes(data),
                ),
            ),
            None,
            self.token,
        )
        self.bundle = identity("b")
        cleanup.write_cleanup_ticket(
            self.ticket, self.manifest, self.bundle, self.intent
        )
        self.anchor = Path(self.intent["roots"][0]["retirement"]["path"]) / "root"

    def acknowledge(self):
        return remote.acknowledge_remote_evidence_cleanup(
            self.ticket,
            manifest_identity=self.manifest.identity,
            bundle_identity=self.bundle,
            acknowledgement_root=self.acks,
        )

    def test_native_retirement_and_repeated_ack_keep_original_empty_anchor(self):
        self.prepare()
        acknowledgement = self.acknowledge()
        self.assertFalse(self.workspace.exists())
        self.assertFalse(self.ticket.exists())
        self.assertEqual(self.anchor.stat().st_ino, self.original_inode)
        self.assertEqual(list(self.anchor.iterdir()), [])
        self.assertEqual(self.acknowledge(), acknowledgement)

    def test_replaced_root_preserves_original_and_foreign_payload(self):
        self.prepare()
        old = self.base / "old-root"
        self.workspace.rename(old)
        self.workspace.mkdir()
        private = self.workspace / "private.txt"
        private.write_bytes(b"foreign root\n")
        inode = private.stat().st_ino
        with self.assertRaises(remote.RemoteExecutionError):
            self.acknowledge()
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"foreign root\n")
        self.assertEqual((old / "first.txt").read_bytes(), b"original first\n")

    def test_equal_byte_replaced_child_is_never_deleted(self):
        self.prepare()
        leaf = self.workspace / "first.txt"
        retained = self.base / "retained.txt"
        leaf.rename(retained)
        leaf.write_bytes(retained.read_bytes())
        inode = leaf.stat().st_ino
        with self.assertRaises(remote.RemoteExecutionError):
            self.acknowledge()
        self.assertEqual(leaf.stat().st_ino, inode)
        self.assertEqual(leaf.read_bytes(), retained.read_bytes())
        self.assertFalse(self.anchor.exists())

    def test_added_private_entry_refuses_before_payload_reads_or_root_move(self):
        self.prepare()
        private = self.workspace / "private.txt"
        private.write_bytes(b"private unadmitted fixture\n")
        inode = private.stat().st_ino
        original = os.read

        def guarded(descriptor, count):
            if os.fstat(descriptor).st_ino == inode:
                raise AssertionError("private payload was read")
            return original(descriptor, count)

        with patch.object(os, "read", guarded):
            with self.assertRaises(remote.RemoteExecutionError):
                self.acknowledge()
        self.assertTrue(self.workspace.is_dir())
        self.assertEqual(private.stat().st_ino, inode)
        self.assertFalse(self.anchor.exists())

    def test_changed_intent_is_not_authorized_by_a_canonical_manifest(self):
        self.prepare()
        value = json.loads(self.ticket.read_bytes())
        value["intent"]["roots"][0]["path"] = str(self.base)
        self.ticket.write_bytes(canonical_json_bytes(value))
        with self.assertRaises(remote.RemoteExecutionError):
            self.acknowledge()
        self.assertTrue((self.workspace / "first.txt").is_file())

    def test_equal_byte_foreign_native_anchor_refuses(self):
        self.prepare()
        path = Path(self.intent["journal"]["path"]) / "anchor.json"
        retained = path.with_name("retained.json")
        path.rename(retained)
        path.write_bytes(retained.read_bytes())
        inode = path.stat().st_ino
        with self.assertRaises(remote.RemoteExecutionError):
            self.acknowledge()
        self.assertEqual(path.stat().st_ino, inode)
        self.assertTrue((self.workspace / "first.txt").is_file())

    def test_copied_or_retired_producer_never_seals_cleanup_authority(self):
        self.prepare()
        with cleanup.hold_cleanup_root(self.workspace, self.workspace.lstat()) as owner:
            with self.assertRaises(ValueError):
                cleanup.capture_cleanup_intent(
                    (copy.copy(owner),),
                    request_identity=identity("1"),
                    cleanup_token=self.token,
                    ticket=self.ticket,
                )
        with self.assertRaises(ValueError):
            cleanup.capture_cleanup_intent(
                (owner,),
                request_identity=identity("1"),
                cleanup_token=self.token,
                ticket=self.ticket,
            )

    def test_control_replacement_after_read_refuses_before_move(self):
        self.prepare()
        changed = []

        def replace(phase):
            if phase == "before-move" and not changed:
                self.ticket.rename(self.base / "original-ticket.json")
                self.ticket.write_bytes(b"foreign control\n")
                changed.append(self.ticket.stat().st_ino)

        with patch.object(cleanup, "_boundary", replace):
            with self.assertRaises(remote.RemoteExecutionError):
                self.acknowledge()
        self.assertEqual(len(changed), 1)
        self.assertEqual(self.ticket.stat().st_ino, changed[0])
        self.assertEqual(self.ticket.read_bytes(), b"foreign control\n")
        self.assertTrue((self.workspace / "first.txt").is_file())

    def test_real_process_exits_resume_from_original_native_move_and_partial_delete(
        self,
    ):
        for phase in ("after-move", "after-entry"):
            with self.subTest(phase=phase):
                self.prepare()
                program = (
                    "import os,sys; "
                    "from pathlib import Path; "
                    "from literate_ai.adapters import remote_cleanup as c; "
                    "from literate_ai.adapters.remote_execution import "
                    "acknowledge_remote_evidence_cleanup as ack; "
                    "from literate_ai.contracts import ContentIdentity; "
                    "c._boundary=lambda phase: "
                    "os._exit(73) if phase==sys.argv[4] else None; "
                    "ack(Path(sys.argv[1]),manifest_identity=ContentIdentity.parse_uri(sys.argv[2]),"
                    "bundle_identity=ContentIdentity.parse_uri(sys.argv[3]),acknowledgement_root=Path(sys.argv[5]))"
                )
                environment = dict(os.environ)
                environment["PYTHONPATH"] = str(Path(remote.__file__).parents[2])
                child = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        program,
                        str(self.ticket),
                        self.manifest.identity.uri,
                        self.bundle.uri,
                        phase,
                        str(self.acks),
                    ],
                    env=environment,
                    cwd=self.base,
                    capture_output=True,
                    timeout=20,
                )
                self.assertEqual(child.returncode, 73, child.stderr.decode())
                self.assertFalse(self.workspace.exists())
                self.assertEqual(self.anchor.stat().st_ino, self.original_inode)
                self.acknowledge()
                self.assertEqual(self.anchor.stat().st_ino, self.original_inode)
                self.assertEqual(list(self.anchor.iterdir()), [])
                self.assertFalse(self.ticket.exists())

    def test_new_source_name_after_move_is_preserved(self):
        self.prepare()
        foreign = []

        def replace(phase):
            if phase == "after-move":
                self.workspace.mkdir()
                private = self.workspace / "private.txt"
                private.write_bytes(b"new source owner\n")
                foreign.append(private.stat().st_ino)

        with patch.object(cleanup, "_boundary", replace):
            acknowledgement = self.acknowledge()
        self.assertEqual(len(foreign), 1)
        self.assertEqual((self.workspace / "private.txt").stat().st_ino, foreign[0])
        self.assertEqual(
            (self.workspace / "private.txt").read_bytes(), b"new source owner\n"
        )
        self.assertEqual(self.acknowledge(), acknowledgement)

    def test_late_entry_in_acknowledged_anchor_is_never_deleted(self):
        self.prepare()
        self.acknowledge()
        private = self.anchor / "private.txt"
        private.write_bytes(b"new private note\n")
        inode = private.stat().st_ino
        with self.assertRaises(remote.RemoteExecutionError):
            self.acknowledge()
        self.assertEqual(private.stat().st_ino, inode)
        self.assertEqual(private.read_bytes(), b"new private note\n")

    def test_busy_original_journal_returns_a_scoped_cleanup_error(self):
        from literate_ai._cache_lock import exclusive_cache_lock

        self.prepare()
        journal = Path(self.intent["journal"]["path"])
        with exclusive_cache_lock(journal / "cleanup.lock", timeout_seconds=1):
            with self.assertRaises(remote.RemoteExecutionError) as raised:
                self.acknowledge()
        self.assertEqual(
            raised.exception.code, "execution.remote_cleanup_custody_invalid"
        )
        self.assertTrue((self.workspace / "first.txt").is_file())
        self.assertTrue(self.ticket.is_file())

    def test_late_control_fifo_refuses_without_a_blocking_read(self):
        if os.name != "posix":
            self.skipTest("actual POSIX FIFO substitution")
        self.prepare()
        program = """
import os,sys
from pathlib import Path
from unittest.mock import patch
from literate_ai.adapters.remote_execution import (
    acknowledge_remote_evidence_cleanup, RemoteExecutionError,
)
from literate_ai.contracts import ContentIdentity
ticket = Path(sys.argv[1])
original = os.open
changed = []
def replace(path, flags, *args, **kwargs):
    if (path == ticket.name
        and not flags & (os.O_CREAT | os.O_DIRECTORY) and not changed):
        ticket.rename(ticket.with_name('retained-ticket.json'))
        os.mkfifo(ticket)
        changed.append(True)
    return original(path, flags, *args, **kwargs)
with patch.object(os, 'open', replace):
    try:
        acknowledge_remote_evidence_cleanup(
            ticket, manifest_identity=ContentIdentity.parse_uri(sys.argv[2]),
            bundle_identity=ContentIdentity.parse_uri(sys.argv[3]),
            acknowledgement_root=Path(sys.argv[4]),
        )
    except RemoteExecutionError:
        sys.exit(0 if changed else 5)
sys.exit(6)
"""
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(Path(remote.__file__).parents[2])
        child = subprocess.run(
            [
                sys.executable,
                "-c",
                program,
                str(self.ticket),
                self.manifest.identity.uri,
                self.bundle.uri,
                str(self.acks),
            ],
            env=environment,
            cwd=self.base,
            capture_output=True,
            timeout=5,
        )
        self.assertEqual(child.returncode, 0, child.stderr.decode())
        self.assertTrue((self.workspace / "first.txt").is_file())
        self.assertTrue((self.base / "retained-ticket.json").is_file())


def identity_from_bytes(data):
    from literate_ai.contracts import ContentIdentity, HashAlgorithm

    return ContentIdentity(HashAlgorithm.SHA256, hashlib.sha256(data).hexdigest())
