"""Typed historical-node decoding only, using existing modeled stage records.

These controls establish parsing, exact identity and constructor invariants.
They do not establish native execution or source/build/history eligibility.
"""

import copy
import unittest
from unittest.mock import patch

from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
    reopen_qualification_lifecycle,
    reopen_qualification_node,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from tests.critical import test_qualification_capture as fixtures


class NativeRootNodeDecoderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = fixtures.QualificationCaptureTests()
        _, captures, cls.entries = fixture.typed_product_fixture()
        reader = cls.reader()
        cls.lifecycle = reopen_qualification_lifecycle(
            reader, captures[0].run.lifecycle_result_identity
        )
        cls.node = cls.lifecycle.node_results[0]

    @classmethod
    def reader(cls, *, extra=(), omit=()):
        records = {key: value for key, value in cls.entries if key not in omit}
        records.update(extra)
        return QualificationEvidenceReader(
            tuple(sorted(records.items(), key=lambda item: item[0].uri)),
            max_bytes=5_000_000,
            max_records=1100,
        )

    def forged(self, document):
        identity = canonical_identity(document)
        return self.reader(
            extra=((identity, canonical_json_bytes(document)),)
        ), identity

    def document(self):
        return copy.deepcopy(self.node.identity_document())

    def test_existing_positive_lifecycle_and_standalone_node_are_identical(self):
        reopened = reopen_qualification_node(self.reader(), self.node.identity)
        self.assertEqual(reopened, self.node)
        self.assertEqual(reopened.identity, self.node.identity)
        self.assertEqual(
            reopened.source_cache_membership, self.node.source_cache_membership
        )

    def test_schema_and_missing_stage_fields_refuse(self):
        for field in ("schema", "build_evidence", "generated_test_evidence"):
            document = self.document()
            if field == "schema":
                document[field] = "unreviewed-node"
            else:
                document.pop(field)
            reader, identity = self.forged(document)
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(QualificationCaptureError, "lifecycle-invalid"),
            ):
                reopen_qualification_node(reader, identity)

    def test_unrecognized_node_field_cannot_survive_exact_identity_reconstruction(self):
        document = self.document()
        document["invented_stage_authority"] = True
        reader, identity = self.forged(document)
        with self.assertRaisesRegex(QualificationCaptureError, "record-mismatch"):
            reopen_qualification_node(reader, identity)

    def test_changed_node_payload_under_original_identity_refuses(self):
        reader = self.reader()
        original_read = reader.read_json
        document = self.document()
        document["index_identity"] = canonical_identity("other-index").uri

        def read(identity):
            return (
                document if identity == self.node.identity else original_read(identity)
            )

        with (
            patch.object(reader, "read_json", side_effect=read),
            self.assertRaisesRegex(QualificationCaptureError, "record-mismatch"),
        ):
            reopen_qualification_node(reader, self.node.identity)

    def test_missing_nested_cache_record_and_mismatched_reference_refuse(self):
        membership = self.node.source_cache_membership
        self.assertIsNotNone(membership)
        with self.assertRaisesRegex(QualificationCaptureError, "record-missing"):
            reopen_qualification_node(
                self.reader(omit=(membership.identity,)), self.node.identity
            )
        document = self.document()
        foreign = canonical_identity("foreign-cache-record")
        document["source_cache_membership_identity"] = foreign.uri
        reader, identity = self.forged(document)
        original_read = reader.read_json
        with (
            patch.object(
                reader,
                "read_json",
                side_effect=lambda key: (
                    membership.to_dict() if key == foreign else original_read(key)
                ),
            ),
            self.assertRaisesRegex(QualificationCaptureError, "record-mismatch"),
        ):
            reopen_qualification_node(reader, identity)

    def test_source_component_and_typed_stage_identity_mismatches_refuse(self):
        for field in (
            "component_revision",
            "build_identity",
            "test_identity",
            "execution_identity",
            "acceptance_identity",
        ):
            self.assertIsNotNone(self.document()[field])
            document = self.document()
            document[field] = canonical_identity(["foreign", field]).uri
            reader, identity = self.forged(document)
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(QualificationCaptureError, "lifecycle-invalid"),
            ):
                reopen_qualification_node(reader, identity)

    def test_failure_code_without_typed_failure_and_false_publication_refuse(self):
        for changes in (
            {"failure_code": "build.failed"},
            {"source_cache_publication_identity": canonical_identity("foreign").uri},
        ):
            reader, identity = self.forged({**self.document(), **changes})
            with (
                self.subTest(changes=changes),
                self.assertRaisesRegex(QualificationCaptureError, "lifecycle-invalid"),
            ):
                reopen_qualification_node(reader, identity)

    def test_coherently_rehashed_stage_claim_still_needs_independent_verifier(self):
        document = self.document()
        foreign = canonical_identity("well-typed-but-unverified-index")
        document["index_identity"] = foreign.uri
        reader, identity = self.forged(document)
        reopened = reopen_qualification_node(reader, identity)
        self.assertEqual(reopened.index_identity, foreign)
        self.assertEqual(reopened.identity, identity)
