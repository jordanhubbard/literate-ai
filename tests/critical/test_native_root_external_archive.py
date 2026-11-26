"""Archive-copy protocols with MODELED live holder/qualification guards.

The archive codec and finite byte/record checks are real. The input proof is
explicitly modeled; arbitrary digest-named history below is not qualification.
No filesystem, executable, credential store or network reader is opened.
"""

import hashlib
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_archive as archives
from literate_ai.adapters.native_root_external_libraries import (
    BorrowedExternalQualifiedLibraries,
)
from literate_ai.adapters.native_root_qualified_provider import (
    HeldNativeRootQualifiedProvider,
)
from literate_ai.adapters.qualification_archive import encode_qualification_archive
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity, canonical_identity


class QualifiedLibraryOriginalArchiveTests(unittest.TestCase):
    def setUp(self):
        records = (b"original source record", b"original measured process bytes")
        # Evidence identities hash raw bytes, not canonical JSON strings.
        self.records = tuple(
            sorted(
                (
                    (
                        ContentIdentity.parse_uri(
                            "sha256:" + hashlib.sha256(value).hexdigest()
                        ),
                        value,
                    )
                    for value in records
                ),
                key=lambda row: row[0].uri,
            )
        )
        self.payload = encode_qualification_archive(
            self.records, max_bytes=16384, max_records=10
        )
        self.reference = BlobRef(
            hashlib.sha256(self.payload).hexdigest(),
            len(self.payload),
            media_type="application/zip",
        )
        self.binding = SimpleNamespace(
            identity=canonical_identity("reviewed-v2-binding"),
            common=SimpleNamespace(
                source_store_id="original-store", qualification_archive=self.reference
            ),
        )
        self.holder = object.__new__(HeldNativeRootQualifiedProvider)
        self.holder._materialized = SimpleNamespace(
            files=SimpleNamespace(reviewed=SimpleNamespace(binding=self.binding))
        )
        self.inputs = object.__new__(BorrowedExternalQualifiedLibraries)
        self.selection = SimpleNamespace(
            provider_component_revision=canonical_identity("provider")
        )
        self.inputs._members = ((self.selection, self.holder),)
        self.data = SimpleNamespace(
            providers=(
                SimpleNamespace(
                    binding=SimpleNamespace(
                        component_revision=self.selection.provider_component_revision,
                        identity=canonical_identity("original-qualified-binding"),
                    )
                ),
            )
        )
        self.guard = self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries, "require_current", autospec=True
            )
        )
        self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries,
                "data_projection",
                autospec=True,
                return_value=self.data,
            )
        )
        self.reader = mock.Mock(return_value=self.payload)

    def capture(self, **overrides):
        arguments = dict(
            read_archive=self.reader,
            max_archive_bytes=16384,
            max_records=10,
            max_total_bytes=65536,
        )
        arguments.update(overrides)
        return archives.read_qualified_library_archives(self.inputs, **arguments)

    def test_explicit_reader_receives_only_original_store_ref_and_bound(self):
        (result,) = self.capture()
        self.reader.assert_called_once_with("original-store", self.reference, 16384)
        self.assertEqual(result.records, self.records)
        self.assertEqual(result.payload, self.payload)
        self.assertEqual(result.reviewed_binding_identity, self.binding.identity)
        self.assertEqual(
            result.qualified_dependency_binding_identity,
            self.data.providers[0].binding.identity,
        )
        self.assertFalse(hasattr(result, "require_current"))
        self.assertFalse(hasattr(result, "qualified"))

    def test_missing_explicit_archive_reader_refuses_capture(self):
        with self.assertRaisesRegex(ValueError, "provider_archive_reader_required"):
            self.capture(read_archive=None)
        self.reader.assert_not_called()

    def test_reference_budget_precedes_callback_and_no_path_is_inferred(self):
        with self.assertRaisesRegex(ValueError, "provider_archive_limit"):
            self.capture(max_total_bytes=self.reference.size - 1)
        self.reader.assert_not_called()

    def test_transport_integrity_cannot_replace_original_archive_subject(self):
        self.reader.return_value = self.payload + b"changed"
        with self.assertRaisesRegex(ValueError, "provider_archive_changed"):
            self.capture()

    def test_original_guard_failure_after_callback_preserves_original_error(self):
        refusal = RuntimeError("original receiving owner expired")

        def expired(*args):
            self.guard.side_effect = refusal
            return self.payload

        self.reader.side_effect = expired
        with self.assertRaises(RuntimeError) as caught:
            self.capture()
        self.assertIs(caught.exception, refusal)

    def test_callback_cannot_replace_original_archive_reference(self):
        def substitute(*args):
            self.binding.common.qualification_archive = replace(
                self.reference, digest="0" * 64
            )
            return self.payload

        self.reader.side_effect = substitute
        with self.assertRaisesRegex(ValueError, "archive_owner_changed"):
            self.capture()

    def test_shared_original_holder_is_captured_once_without_extra_archive_read(self):
        self.inputs._members = (
            (self.selection, self.holder),
            (self.selection, self.holder),
        )
        self.assertEqual(len(self.capture()), 1)
        self.assertEqual(self.reader.call_count, 1)

    def test_record_membership_is_bounded_by_original_archive_decoder(self):
        with self.assertRaises(ValueError):
            self.capture(max_records=1)
