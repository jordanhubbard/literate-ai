"""Failure notes preserve the original native cleanup refusal and observations."""

import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import remote_cleanup as cleanup
from literate_ai.contracts import canonical_json_bytes


class CleanupOpenDiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name).resolve() / "control.json"
        self.data = canonical_json_bytes({"original": "preserve"})
        self.path.write_bytes(self.data)
        self.before = self.path.stat()

    def exercise(self, *, native_transform=None, signature_transform=None):
        original_native = cleanup._descriptor_identity
        original_signature = cleanup._signature
        original_fail = cleanup._fail
        descriptors, signatures, failures = [], [], []

        def native(access, descriptor):
            observed = original_native(access, descriptor)
            descriptors.append(descriptor)
            return native_transform(observed) if native_transform else observed

        def signature(node):
            observed = original_signature(node)
            signatures.append(observed)
            if signature_transform and len(signatures) == 1:
                return signature_transform(observed)
            return observed

        def fail(message):
            try:
                original_fail(message)
            except BaseException as exc:
                failures.append(exc)
                raise

        with (
            patch.object(
                cleanup, "_descriptor_identity", side_effect=native
            ) as identities,
            patch.object(
                cleanup, "_signature", side_effect=signature
            ) as signature_calls,
            patch.object(cleanup, "_fail", side_effect=fail),
            patch.object(cleanup.os, "read", wraps=os.read) as reads,
        ):
            yielded = False
            try:
                with cleanup._control(self.path) as (value, _facts, _guard):
                    yielded = True
                    self.assertEqual(value, {"original": "preserve"})
            except cleanup.RemoteCleanupError as exc:
                error = exc
            else:
                error = None
            counts = (
                identities.call_count,
                signature_calls.call_count,
                reads.call_count,
            )
        self.assertEqual(len(descriptors), 1)
        with self.assertRaises(OSError) as closed:
            os.fstat(descriptors[0])
        self.assertEqual(closed.exception.errno, errno.EBADF)
        after = self.path.stat()
        self.assertEqual(
            (after.st_dev, after.st_ino), (self.before.st_dev, self.before.st_ino)
        )
        self.assertEqual(self.path.read_bytes(), self.data)
        if error is not None:
            self.assertFalse(yielded)
            self.assertEqual(len(failures), 1)
            self.assertIs(error, failures[0])
            self.assertEqual(str(error), "remote cleanup: control changed during open")
        return error, counts, signatures

    @staticmethod
    def changed_native(row):
        return (*row[:-1], row[-1] + 1)

    @staticmethod
    def changed_ctime(row):
        return (*row[:5], row[5] + 1, row[6])

    def notes(self, error):
        notes = error.__notes__
        self.assertEqual(len(notes), 1)
        self.assertLessEqual(len(notes[0]), 2048)
        self.assertNotIn(str(self.path), notes[0])
        self.assertNotIn("preserve", notes[0])
        return notes[0]

    def test_original_success_observation_counts_and_closed_descriptor(self):
        error, counts, _ = self.exercise()
        self.assertIsNone(error)
        self.assertEqual(counts, (1, 10, 2))

    def test_native_mismatch_preserves_short_circuit_and_original_error(self):
        error, counts, _ = self.exercise(native_transform=self.changed_native)
        self.assertEqual(counts, (1, 0, 0))
        note = self.notes(error)
        self.assertIn("branch=native-identity", note)
        self.assertNotIn("signature=", note)

    def test_signature_mismatch_uses_original_opened_then_named_observations(self):
        error, counts, observed = self.exercise(signature_transform=self.changed_ctime)
        self.assertEqual(counts, (1, 2, 0))
        self.assertEqual(observed[0], observed[1])
        note = self.notes(error)
        self.assertIn("branch=named/fd-signature", note)
        self.assertIn("fields=('ctime_ns',)", note)
        self.assertIn(f"named_signature={observed[1]}", note)
        self.assertIn(f"opened_signature={self.changed_ctime(observed[0])}", note)

    def test_foreign_tuple_cannot_dispatch_formatting_from_native_note(self):
        callbacks = []

        class ForeignTuple(tuple):
            def __repr__(self):
                callbacks.append("repr")
                raise AssertionError("foreign formatter must not run")

        error, counts, _ = self.exercise(
            native_transform=lambda row: ForeignTuple(self.changed_native(row))
        )
        self.assertEqual(counts, (1, 0, 0))
        self.assertFalse(hasattr(error, "__notes__"))
        self.assertEqual(callbacks, [])

    def test_foreign_signature_cannot_dispatch_formatting_from_note(self):
        callbacks = []

        class ForeignTuple(tuple):
            def __repr__(self):
                callbacks.append("repr")
                raise AssertionError("foreign formatter must not run")

        error, counts, _ = self.exercise(
            signature_transform=lambda row: ForeignTuple(self.changed_ctime(row))
        )
        self.assertEqual(counts, (1, 2, 0))
        self.assertFalse(hasattr(error, "__notes__"))
        self.assertEqual(callbacks, [])

    def test_foreign_metaclass_equality_is_not_invoked_by_note_validation(self):
        callbacks = []

        class ForeignType(type):
            def __eq__(cls, other):
                callbacks.append("type equality")
                return False

        class ForeignTuple(tuple, metaclass=ForeignType):
            pass

        error, counts, _ = self.exercise(
            native_transform=lambda row: ForeignTuple(self.changed_native(row))
        )
        self.assertEqual(counts, (1, 0, 0))
        self.assertFalse(hasattr(error, "__notes__"))
        self.assertEqual(callbacks, [])

    def test_supported_wide_native_integer_is_preserved_exactly_in_note(self):
        for value in ((1 << 128) - 1, -((1 << 128) - 1)):
            with self.subTest(value=value):
                error, counts, _ = self.exercise(
                    native_transform=lambda row, observed=value: (*row[:-1], observed)
                )
                self.assertEqual(counts, (1, 0, 0))
                self.assertIn(str(value), self.notes(error))

    def test_oversized_native_integer_omits_note_without_changing_refusal(self):
        error, counts, _ = self.exercise(
            native_transform=lambda row: (*row[:-1], 1 << 128)
        )
        self.assertEqual(counts, (1, 0, 0))
        self.assertFalse(hasattr(error, "__notes__"))

    def test_oversized_signature_integer_omits_note_without_changing_refusal(self):
        error, counts, _ = self.exercise(
            signature_transform=lambda row: (*row[:5], -(1 << 128), row[6])
        )
        self.assertEqual(counts, (1, 2, 0))
        self.assertFalse(hasattr(error, "__notes__"))
