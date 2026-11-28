"""Original allocator completion, independent of body success or path absence."""

from __future__ import annotations

import copy
import os
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import evidence_staging as staging


class StageRetirementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve()

    def test_completion_after_actual_disposal_keeps_closed_writer_closed(self):
        with staging.evidence_staging(self.parent, prefix="stage-") as owner:
            root = owner.path
            owner.write("nested/value", b"original")
            self.assertFalse(owner.retired)
            owner.seal()
            self.assertFalse(owner.retired)
        self.assertTrue(owner.retired)
        self.assertFalse(root.exists())
        with self.assertRaises(staging.EvidenceStagingError):
            owner.write("later", b"denied")
        with self.assertRaises(staging.EvidenceStagingError):
            _ = owner.path
        self.assertTrue(owner.retired)

    def test_original_body_failure_can_still_complete_actual_retirement(self):
        original = RuntimeError("actual body rejection")
        with self.assertRaises(RuntimeError) as raised:
            with staging.evidence_staging(self.parent, prefix="stage-") as owner:
                root = owner.path
                owner.write("value", b"owned")
                raise original
        self.assertIs(raised.exception, original)
        self.assertTrue(owner.retired)
        self.assertFalse(root.exists())

    def test_foreign_state_preserves_original_failure_without_completion(self):
        original = RuntimeError("original conversion refusal")
        with self.assertRaises(RuntimeError) as raised:
            with staging.evidence_staging(self.parent, prefix="stage-") as owner:
                root = owner.path
                owner.write("value", b"owned")
                foreign = root / "private"
                foreign.write_bytes(b"foreign bytes")
                inode = foreign.stat().st_ino
                raise original
        self.assertIs(raised.exception, original)
        self.assertFalse(owner.retired)
        self.assertEqual(foreign.stat().st_ino, inode)
        self.assertEqual(foreign.read_bytes(), b"foreign bytes")
        self.assertTrue(any("Stage disposal refused" in n for n in original.__notes__))

    def test_successful_body_does_not_acknowledge_refused_disposal(self):
        with self.assertRaises(staging.EvidenceStagingError):
            with staging.evidence_staging(self.parent, prefix="stage-") as owner:
                root = owner.path
                (root / "foreign").write_bytes(b"preserve")
        self.assertFalse(owner.retired)
        self.assertEqual((root / "foreign").read_bytes(), b"preserve")

    def test_equal_byte_replacement_cannot_complete_original_retirement(self):
        with self.assertRaises(staging.EvidenceStagingError):
            with staging.evidence_staging(self.parent, prefix="stage-") as owner:
                root = owner.path
                owner.write("value", b"same")
                retained = self.parent / "retained"
                (root / "value").rename(retained)
                (root / "value").write_bytes(b"same")
                inode = (root / "value").stat().st_ino
        self.assertFalse(owner.retired)
        self.assertEqual((root / "value").stat().st_ino, inode)
        self.assertEqual(retained.read_bytes(), b"same")

    def test_partial_disposal_is_never_complete_or_retried_from_observation(self):
        remove = staging._remove_entry
        calls = []

        def interrupted(*args):
            calls.append(args[1])
            if len(calls) == 2:
                raise OSError("controlled disposal interruption")
            return remove(*args)

        with self.assertRaises(staging.EvidenceStagingError):
            with patch.object(staging, "_remove_entry", interrupted):
                with staging.evidence_staging(self.parent, prefix="stage-") as owner:
                    root = owner.path
                    owner.write("a", b"a")
                    owner.write("b", b"b")
        self.assertEqual(len(calls), 2)
        self.assertFalse(owner.retired)
        self.assertFalse(owner.retired)
        self.assertEqual(len(list(root.iterdir())), 1)
        self.assertEqual(len(calls), 2)

    def test_absent_path_does_not_imply_completed_native_teardown(self):
        dispose = staging._dispose

        def reject_after_disposal(owner):
            dispose(owner)
            raise OSError("original disposal did not close normally")

        with self.assertRaises(staging.EvidenceStagingError):
            with patch.object(staging, "_dispose", reject_after_disposal):
                with staging.evidence_staging(self.parent, prefix="stage-") as owner:
                    root = owner.path
                    owner.write("value", b"owned")
        self.assertFalse(root.exists())
        self.assertFalse(owner.retired)

    def test_copied_forged_and_foreign_process_observations_are_refused(self):
        with staging.evidence_staging(self.parent, prefix="stage-") as owner:
            copied = copy.copy(owner)
            forged = object.__new__(staging.EvidenceStage)
            for other in (copied, forged):
                with self.assertRaises(staging.EvidenceStagingError):
                    _ = other.retired
        with patch.object(staging.os, "getpid", return_value=os.getpid() + 1):
            with self.assertRaises(staging.EvidenceStagingError):
                _ = owner.retired
        self.assertTrue(owner.retired)

    def test_completion_does_not_retain_dead_owner_objects(self):
        with staging.evidence_staging(self.parent, prefix="stage-") as owner:
            pass
        self.assertTrue(owner.retired)
        reference = weakref.ref(owner)
        del owner
        self.assertIsNone(reference())

    def test_windows_handle_model_observes_original_completion(self):
        from tests.critical.test_remote_cleanup_windows_handles import WindowsFacade

        with WindowsFacade(self).installed() as model:
            with staging.evidence_staging(self.parent, prefix="stage-") as owner:
                root = owner.path
                owner.write("nested/value", b"original")
                self.assertFalse(owner.retired)
            self.assertTrue(owner.retired)
            self.assertFalse(root.exists())
            self.assertTrue(model.calls)
