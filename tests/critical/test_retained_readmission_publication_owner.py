"""Native metadata custody survives failure without adopting foreign inodes."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from contextvars import copy_context
from pathlib import Path
from unittest import mock

from literate_ai import _atomic_publication as port
from literate_ai.adapters import retained_readmission_publication as publication
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore, ProjectError


class RetainedReadmissionPublicationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / publication.HISTORY).mkdir(parents=True)
        self.before = {"a.json": b"original a\n", "b.json": b"original b\n"}
        for name, content in self.before.items():
            (self.root / name).write_bytes(content)
        self.original = {name: (self.root / name).stat().st_ino for name in self.before}

    def create(self, **kwargs):
        return publication.ReadmissionPublication.create(
            self.root,
            before=self.before,
            writable=tuple(self.before),
            plan_identity=canonical_identity({"plan": "test fixture"}).uri,
            maximum_total_bytes=1024,
            maximum_steps=8,
            **kwargs,
        )

    def publish(self, owner, name="a.json", content=b"changed a\n", callback=None):
        owner.publish(
            self.root / name,
            content,
            require_current=callback,
            preserve_mode=True,
        )

    def assert_original(self):
        for name, content in self.before.items():
            path = self.root / name
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_ino, self.original[name])
            self.assertEqual(path.stat().st_nlink, 1)

    def test_reopen_requires_current_acknowledgement_and_restores_original_inode(self):
        owner = self.create()
        self.publish(owner)
        reopened = publication.ReadmissionPublication.open_pending(self.root)
        plan = reopened.recovery_plan()
        self.assertTrue(plan["can_rollback"])
        self.assertFalse(plan["qualification_granted"])
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "acknowledgement"
        ):
            reopened.rollback()
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "fresh_execution"
        ):
            reopened.commit()
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "fresh_execution"
        ):
            self.publish(reopened)
        reopened.rollback(acknowledgement=plan["identity"])
        self.assert_original()
        self.assertFalse((self.root / publication.ACTIVE).exists())
        self.assertTrue((owner.attempt / "rolled-back.json").is_file())

    def test_current_writer_rollback_restores_exact_nodes_after_multiple_writes(self):
        owner = self.create()
        self.publish(owner)
        self.publish(owner, content=b"second a\n")
        self.publish(owner, name="b.json", content=b"changed b\n")
        owner.rollback()
        self.assert_original()

    def test_owner_edit_before_next_publication_is_never_overwritten(self):
        owner = self.create()
        self.publish(owner)
        target = self.root / "b.json"
        changed = b"concurrent owner edit before next write\n"
        target.write_bytes(changed)
        inode = target.stat().st_ino
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "foreign_node"
        ):
            self.publish(owner, name="b.json", content=b"must not overwrite owner\n")
        self.assertEqual(target.read_bytes(), changed)
        self.assertEqual(target.stat().st_ino, inode)
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "recovery_required"
        ):
            owner.rollback()
        self.assertEqual(target.read_bytes(), changed)
        self.assertEqual(target.stat().st_ino, inode)
        first = self.root / "a.json"
        self.assertEqual(first.read_bytes(), self.before["a.json"])
        self.assertEqual(first.stat().st_ino, self.original["a.json"])

    def test_same_byte_foreign_node_survives_while_owned_companion_is_restored(self):
        owner = self.create()
        self.publish(owner)
        self.publish(owner, name="b.json", content=b"changed b\n")
        path = self.root / "a.json"
        foreign = self.root / "foreign"
        foreign.write_bytes(path.read_bytes())
        inode = foreign.stat().st_ino
        foreign.replace(path)
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "recovery_required"
        ):
            owner.rollback()
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_bytes(), b"changed a\n")
        self.assertEqual((self.root / "b.json").stat().st_ino, self.original["b.json"])
        self.assertTrue((self.root / publication.ACTIVE).is_file())

    def test_commit_releases_live_aliases_and_retains_history(self):
        owner = self.create()
        self.publish(owner)
        owner.commit()
        self.assertEqual((self.root / "a.json").read_bytes(), b"changed a\n")
        self.assertEqual((self.root / "a.json").stat().st_nlink, 1)
        self.assertEqual((self.root / "b.json").stat().st_nlink, 1)
        self.assertFalse((self.root / publication.ACTIVE).exists())
        self.assertTrue((owner.attempt / "b000.bytes").is_file())
        self.assertTrue((owner.attempt / "committed.json").is_file())

    def test_producer_currentness_refusal_precedes_canonical_effect(self):
        owner = self.create()
        observed = []

        def refuse():
            observed.append((self.root / "a.json").read_bytes())
            raise ValueError("producer inputs changed")

        with self.assertRaisesRegex(ValueError, "producer inputs changed"):
            self.publish(owner, callback=refuse)
        self.assertEqual(observed, [self.before["a.json"]])
        owner.rollback()
        self.assert_original()

    def test_recovery_restores_missing_owned_target_without_new_execution(self):
        owner = self.create()
        self.publish(owner)
        (self.root / "a.json").unlink()
        reopened = publication.ReadmissionPublication.open_pending(self.root)
        plan = reopened.recovery_plan()
        self.assertTrue(plan["can_rollback"])
        reopened.rollback(acknowledgement=plan["identity"])
        self.assert_original()

    def test_same_byte_active_marker_replacement_refuses_without_effects(self):
        owner = self.create()
        active = self.root / publication.ACTIVE
        replacement = self.root / "replacement"
        replacement.write_bytes(active.read_bytes())
        replacement.replace(active)
        with self.assertRaises(publication.ReadmissionPublicationError):
            self.publish(owner)
        for name in self.before:
            self.assertEqual((self.root / name).stat().st_ino, self.original[name])

    def test_foreign_restore_temporary_is_preserved(self):
        owner = self.create()
        self.publish(owner)
        temporary = self.root / owner.before["a.json"]["temporary"]
        temporary.write_bytes(b"foreign temporary\n")
        inode = temporary.stat().st_ino
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "recovery_required"
        ):
            owner.rollback()
        self.assertEqual(temporary.read_bytes(), b"foreign temporary\n")
        self.assertEqual(temporary.stat().st_ino, inode)
        self.assertTrue((self.root / publication.ACTIVE).exists())

    def test_payload_limit_precedes_canonical_write(self):
        owner = self.create()
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "payload_limit"
        ):
            self.publish(owner, content=b"x" * 1025)
        self.assertEqual(owner.steps, [])
        owner.rollback()
        self.assert_original()

    def test_pending_project_is_unreadable_outside_the_finite_original_writer(self):
        owner = self.create()
        with self.assertRaises(ProjectError):
            ProjectConfigurationStore.context(self.root)
        with port.atomic_publication_scope(owner):
            ProjectConfigurationStore.context(self.root)
            copied = copy_context()
            # Exercise the real manifest physical writer through the scoped port.
            ProjectConfigurationStore._replace(
                self.root / "a.json", b"through producer\n"
            )
        with self.assertRaises(port.AtomicPublicationScopeError):
            copied.run(ProjectConfigurationStore.context, self.root)
        with self.assertRaises(ProjectError):
            ProjectConfigurationStore.context(self.root)
        owner.rollback()
        self.assert_original()
        ProjectConfigurationStore.context(self.root)

    def test_real_process_exit_before_and_after_replace_reopens_for_rollback(self):
        script = """
import os, sys
from pathlib import Path
from literate_ai.adapters.retained_readmission_publication import ReadmissionPublication
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
root = Path(sys.argv[1])
owner = ReadmissionPublication.create(
    root, before={name: (root/name).read_bytes() for name in ('a.json','b.json')},
    writable=('a.json','b.json'),
    plan_identity=canonical_identity({'plan':'crash'}).uri,
    maximum_total_bytes=1024, maximum_steps=8)
owner.publish(root/'a.json', b'crash stage\\n', preserve_mode=True,
    require_current=(lambda: os._exit(73)) if sys.argv[2]=='intent' else None)
os._exit(73)
"""
        for boundary in ("intent", "replaced"):
            with self.subTest(boundary=boundary):
                result = subprocess.run(
                    [sys.executable, "-c", script, str(self.root), boundary],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 73, result.stderr)
                reopened = publication.ReadmissionPublication.open_pending(self.root)
                plan = reopened.recovery_plan()
                self.assertTrue(plan["can_rollback"])
                reopened.rollback(acknowledgement=plan["identity"])
                self.assert_original()

    def test_changed_saved_header_refuses_a_live_writer(self):
        owner = self.create()
        header = owner.attempt / "header.json"
        header.write_bytes(header.read_bytes().replace(b'"steps":8', b'"steps":7'))
        with self.assertRaises(publication.ReadmissionPublicationError):
            self.publish(owner)
        for name in self.before:
            self.assertEqual((self.root / name).stat().st_ino, self.original[name])

    def test_public_recovery_reads_invalid_manifest_and_requires_exact_ack(self):
        owner = self.create()
        self.publish(owner)
        (self.root / "literate.project.json").write_bytes(b"invalid manifest\n")
        command = [
            sys.executable,
            "-m",
            "literate_ai.cli",
            "project",
            "retained-harness",
            "recover",
            "--project",
            str(self.root),
        ]
        planned = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(planned.returncode, 0, planned.stderr + planned.stdout)
        plan = json.loads(planned.stdout)["result"]
        self.assertTrue(plan["can_rollback"])
        self.assertTrue((self.root / publication.ACTIVE).exists())
        refused = subprocess.run(
            [
                *command,
                "--apply",
                "--acknowledge",
                "--expected-plan-identity",
                canonical_identity({"wrong": "ack"}).uri,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual((self.root / "a.json").read_bytes(), b"changed a\n")
        restored = subprocess.run(
            [
                *command,
                "--apply",
                "--acknowledge",
                "--expected-plan-identity",
                plan["identity"],
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(restored.returncode, 0, restored.stderr + restored.stdout)
        self.assertTrue(json.loads(restored.stdout)["result"]["rolled_back"])
        self.assert_original()

    def test_unknown_step_grant_is_rejected_before_any_recovery_effect(self):
        owner = self.create()
        self.publish(owner)
        step = owner.attempt / "s0000.json"
        document = json.loads(step.read_bytes())
        document["execution_allowed"] = True
        step.write_bytes(canonical_json_bytes(document) + b"\n")
        inode = (self.root / "a.json").stat().st_ino
        with self.assertRaises(publication.ReadmissionPublicationError):
            publication.ReadmissionPublication.open_pending(self.root)
        self.assertEqual((self.root / "a.json").stat().st_ino, inode)
        self.assertTrue((self.root / publication.ACTIVE).exists())

    def test_missing_original_pin_cannot_be_reconstructed_from_saved_bytes(self):
        owner = self.create()
        self.publish(owner)
        (self.root / owner.before["a.json"]["pin"]).unlink()
        reopened = publication.ReadmissionPublication.open_pending(self.root)
        plan = reopened.recovery_plan()
        self.assertFalse(plan["can_rollback"])
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "recovery_required"
        ):
            reopened.rollback(acknowledgement=plan["identity"])
        self.assertEqual((self.root / "a.json").read_bytes(), b"changed a\n")
        self.assertTrue((self.root / publication.ACTIVE).exists())

    def test_old_reader_refuses_after_original_writer_adds_another_step(self):
        owner = self.create()
        self.publish(owner)
        reopened = publication.ReadmissionPublication.open_pending(self.root)
        plan = reopened.recovery_plan()
        self.publish(owner, name="b.json", content=b"changed b\n")
        with self.assertRaisesRegex(
            publication.ReadmissionPublicationError, "record_changed"
        ):
            reopened.rollback(acknowledgement=plan["identity"])
        self.assertEqual((self.root / "b.json").read_bytes(), b"changed b\n")
        owner.rollback()
        self.assert_original()

    def test_evidence_publication_preserves_a_concurrent_empty_destination(self):
        history = self.root / publication.HISTORY / "before.evidence"
        actual = publication.publish_directory_exclusive
        foreign = []
        staging = []

        def occupied(source, destination, **kwargs):
            destination.mkdir()
            foreign.append(destination.stat().st_ino)
            staging.append(source)
            return actual(source, destination, **kwargs)

        with mock.patch.object(
            publication, "publish_directory_exclusive", side_effect=occupied
        ):
            with self.assertRaisesRegex(
                publication.ReadmissionPublicationError, "history_collision"
            ):
                publication.publish_readmission_evidence(
                    history, self.before, maximum_total_bytes=1024
                )
        self.assertEqual(history.stat().st_ino, foreign[0])
        self.assertEqual(tuple(history.iterdir()), ())
        self.assertTrue(staging[0].is_dir())
        self.assertEqual((staging[0] / "a.json").read_bytes(), self.before["a.json"])

    def test_existing_evidence_reopens_without_deleting_foreign_extra_files(self):
        history = self.root / publication.HISTORY / "before.evidence"
        self.assertTrue(
            publication.publish_readmission_evidence(
                history, self.before, maximum_total_bytes=1024
            )
        )
        foreign = history / "foreign-note.txt"
        foreign.write_bytes(b"foreign history annotation\n")
        inode = foreign.stat().st_ino
        self.assertFalse(
            publication.publish_readmission_evidence(
                history, self.before, maximum_total_bytes=1024
            )
        )
        self.assertEqual(foreign.stat().st_ino, inode)
        self.assertEqual(foreign.read_bytes(), b"foreign history annotation\n")
