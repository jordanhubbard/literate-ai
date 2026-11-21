"""Exercise completion-wide read bounds across metadata and repeated SDK files."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.native_sdk_completion_packet import _CompletionReads
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.storage import FileSystemCAS
from literate_ai.storage.cas import BlobIntegrityError


class CompletionReadsTests(unittest.TestCase):
    def test_metadata_and_repeated_files_share_one_byte_allowance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            producer = FileSystemCAS(root / "cas")
            file = producer.put_bytes(b"payload")
            metadata = producer.put_manifest({"format": "example"})
            total = metadata.size + file.size
            reads = _CompletionReads(
                root, RetainedProjectLimits(10, total, total), lambda: None
            )
            self.assertEqual(reads.get_manifest(metadata), {"format": "example"})
            reads.verify(file)
            with self.assertRaisesRegex(ValueError, "aggregate cache read budget"):
                reads.verify(file)

    def test_empty_files_still_count_toward_the_entry_allowance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty = FileSystemCAS(root / "cas").put_bytes(b"")
            reads = _CompletionReads(root, RetainedProjectLimits(1, 1, 1), lambda: None)
            reads.verify(empty)
            with self.assertRaisesRegex(ValueError, "aggregate cache read budget"):
                reads.verify(empty)

    def test_duplicate_fields_cannot_replace_a_producer_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            producer = FileSystemCAS(root / "cas")
            ambiguous = producer.put_bytes(b'{"passed":false,"passed":true}')
            reads = _CompletionReads(
                root, RetainedProjectLimits(1, 64, 64), lambda: None
            )
            with self.assertRaisesRegex(ValueError, "canonical JSON object"):
                reads.get_manifest(ambiguous)

    def test_final_verification_detects_drift_in_an_earlier_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            producer = FileSystemCAS(root / "cas")
            first = producer.put_bytes(b"first")
            second = producer.put_bytes(b"second")
            reads = _CompletionReads(
                root, RetainedProjectLimits(4, 6, 22), lambda: None
            )
            reads.verify(first)
            reads.verify(second)
            # Substitute equal-length bytes so a size check alone would pass.
            path = producer.path_for(first)
            replacement = root / "replacement"
            replacement.write_bytes(b"other")
            replacement.replace(path)
            with self.assertRaises(BlobIntegrityError):
                reads.verify_originals()

    def test_deadline_expiring_during_final_read_fails_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file = FileSystemCAS(root / "cas").put_bytes(b"payload")
            expired = False

            def check_deadline():
                if expired:
                    raise TimeoutError("SDK verification deadline")

            reads = _CompletionReads(
                root, RetainedProjectLimits(2, 7, 14), check_deadline
            )
            reads.verify(file)
            verify = FileSystemCAS.verify

            def finish_after_deadline(store, reference):
                nonlocal expired
                verify(store, reference)
                expired = True

            with patch.object(FileSystemCAS, "verify", finish_after_deadline):
                with self.assertRaisesRegex(TimeoutError, "SDK verification deadline"):
                    reads.verify_originals()
