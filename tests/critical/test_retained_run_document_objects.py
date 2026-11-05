"""Actual CAS canonical nonobject metadata refuses before historical consumers.

These are typed-receipt/real-CAS reader-boundary negatives, not native execution,
SDK admission or a claim that every public completed-root path was previously
unguarded. Public planning already rejects a nonobject completed root; acceptance
record consumption exposed the uncaught .get AttributeError in the shared reader.
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from literate_ai.adapters.retained_promotion_evidence import HistoricalReadPolicy
from literate_ai.adapters.retained_unit_run_inspection import _Reader
from literate_ai.contracts import canonical_json_bytes
from literate_ai.contracts.retained_project_receipt import (
    RETAINED_RECEIPT_ROOTS,
    RetainedProjectReceipt,
)
from literate_ai.storage.cas import FileSystemCAS


class RetainedRunDocumentObjectTests(unittest.TestCase):
    def reader(self, store, value, *, completed_root):
        ordinary = store.put_bytes(
            canonical_json_bytes({"fixture": "non-authoritative-reader-boundary"}),
            media_type="application/json",
        )
        reference = store.put_bytes(
            canonical_json_bytes(value), media_type="application/json"
        )
        roots = tuple(
            (
                name,
                reference if completed_root and name == "completed-run" else ordinary,
            )
            for name in sorted(RETAINED_RECEIPT_ROOTS)
        )
        refs = {ref.identity: ref for ref in (ordinary, reference)}
        receipt = RetainedProjectReceipt(
            "reader-boundary", roots, tuple(refs[k] for k in sorted(refs)), 1, 0
        )
        inputs = SimpleNamespace(store=store, receipt=receipt)
        return _Reader(inputs, HistoricalReadPolicy(), lambda: None), reference

    def test_canonical_array_and_scalars_refuse_at_completed_document_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FileSystemCAS(Path(directory) / "cas")
            for value in ([], None, "not-an-assertion", 7, False):
                with self.subTest(value=value):
                    reader, reference = self.reader(store, value, completed_root=True)
                    with self.assertRaisesRegex(
                        ValueError, "canonical-run-document-required"
                    ):
                        reader.document(reference)

    def test_actual_acceptance_record_nonobjects_refuse_before_get_consumer(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FileSystemCAS(Path(directory) / "cas")
            for value in ([], None, "not-an-assertion", 7, False):
                with self.subTest(value=value):
                    reader, reference = self.reader(store, value, completed_root=False)
                    with self.assertRaisesRegex(
                        ValueError, "canonical-run-document-required"
                    ):
                        # The old reader returned []/scalars and this real
                        # acceptance consumption raised an untyped AttributeError.
                        observation = reader.record(reference.identity)
                        observation.get("filesystem_observation")

    def test_raw_stream_keeps_canonical_array_and_scalar_bytes_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FileSystemCAS(Path(directory) / "cas")
            for value in ([], None, "not-an-assertion", 7, False):
                with self.subTest(value=value):
                    reader, reference = self.reader(store, value, completed_root=False)
                    self.assertEqual(reader.raw(reference), canonical_json_bytes(value))
