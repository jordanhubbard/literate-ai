from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from literate_ai.adapters.evidence_storage import FileSystemEvidenceStore
from literate_ai.adapters.qualification_archive import (
    encode_qualification_archive,
    reopen_qualification_archive,
)
from literate_ai.adapters.qualification_capture import QualificationEvidenceRecorder
from literate_ai.application.source_promotion import qualify_locked_source_promotion
from literate_ai.cli.source_to_specification import (
    CliFailure,
    _publish_retained_qualification,
)
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.blobs import BlobRef
from literate_ai.source_to_specification.model_workflow import (
    SOURCE_TRANSLATION_RUN_SCHEMA,
)
from literate_ai.source_to_specification.promotion_materialization import (
    REVIEWED_SOURCE_PROMOTION_PROVENANCE_SCHEMA,
    SourcePromotionError,
    verify_source_promotion_evidence,
)
from literate_ai.source_to_specification.static_intake import (
    StaticIntakeFile,
    StaticIntakePlan,
    StaticIntakeValidation,
    sign_static_intake_review,
)
from tests.support import fixtures_test_locked_source_promotion as fixtures
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


class StaticIntakeQualificationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.LockedSourcePromotionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.review = sign_static_intake_review(
            StaticIntakePlan(
                self.fixture.retained.source_snapshot_identity.uri,
                fixtures._identity("origin").uri,
                (
                    StaticIntakeFile(
                        "example.ts",
                        "sha256:" + hashlib.sha256(b"owned").hexdigest(),
                        5,
                        "typescript",
                        "sensitive",
                        "Owned fixture",
                    ),
                ),
            ),
            actor="owned-reviewer",
            authority="human",
            reason="Owned fixture contract",
            key=b"owned-fixture-intake-qualification-key-32-bytes",
        )

    def validation(self, projection=None):
        projection = projection or self.fixture.retained
        return StaticIntakeValidation(
            self.review.source_snapshot_id,
            projection.provenance_reference_identity.uri,
            self.review.identity,
            self.fixture.qualification.identity.uri,
            self.review.key_id,
        )

    def test_retained_intake_publication_reopens_canonical_union_and_keeps_baseline(
        self,
    ):
        qualification = self.fixture.qualification
        recorder = QualificationEvidenceRecorder(max_bytes=1_000_000, max_records=100)
        recorder.remember_json(qualification.to_dict())
        lifecycle = Mock()
        adapter = SimpleNamespace(
            max_capture_bytes=1_000_000,
            evidence_blobs=recorder.entries,
            library_captures=(),
            lifecycle=lifecycle,
        )
        root = Path(self.fixture.temporary.name).resolve()
        baseline = _publish_retained_qualification(
            adapter, qualification, root / "baseline"
        )
        expected = encode_qualification_archive(
            recorder.entries, max_bytes=1_000_000, max_records=100_000
        )
        self.assertEqual(
            baseline["archive"]["digest"], hashlib.sha256(expected).hexdigest()
        )
        validation = self.validation()
        values = [self.review.to_dict(), validation.to_dict()]
        additions = sorted(
            (
                (canonical_identity(value), canonical_json_bytes(value))
                for value in values
            ),
            key=lambda entry: entry[0].uri,
            reverse=True,
        )
        self.assertGreater(additions[0][0].uri, additions[1][0].uri)
        additions.append(additions[0])
        location = root / "with-intake"
        published = _publish_retained_qualification(
            adapter, qualification, location, tuple(additions)
        )
        reference = BlobRef.from_dict(published["archive"])
        retained = reopen_qualification_archive(
            FileSystemEvidenceStore(location).get_bytes(reference),
            reference,
            max_bytes=1_000_000,
            max_records=100_000,
        )
        self.assertEqual(
            retained.read_json(qualification.identity), qualification.to_dict()
        )
        for value in values:
            self.assertEqual(retained.read_json(canonical_identity(value)), value)
        self.assertEqual(len(retained._records), 3)
        self.assertEqual(lifecycle.require_current_authority.call_count, 2)

    def test_retained_intake_conflict_refused_before_store_creation(self):
        qualification = self.fixture.qualification
        recorder = QualificationEvidenceRecorder(max_bytes=1_000_000, max_records=100)
        recorder.remember_json(qualification.to_dict())
        adapter = SimpleNamespace(
            max_capture_bytes=1_000_000,
            evidence_blobs=recorder.entries,
            library_captures=(),
            lifecycle=Mock(),
        )
        location = Path(self.fixture.temporary.name).resolve() / "conflict"
        with self.assertRaises(CliFailure) as raised:
            _publish_retained_qualification(
                adapter,
                qualification,
                location,
                ((qualification.identity, b"foreign bytes"),),
            )
        self.assertEqual(
            raised.exception.code, "qualification.retained_intake_conflict"
        )
        self.assertFalse(location.exists())

    def test_measured_qualification_requires_every_exact_review_binding(self):
        fixture = self.fixture
        with self.assertRaises(SourcePromotionError):
            replace(fixture.evidence, static_intake_review=self.review)
        validation = self.validation()
        evidence = replace(
            fixture.evidence,
            static_intake_review=self.review,
            static_intake_validation=validation,
        )
        self.assertIn(
            validation.identity,
            [item.uri for item in evidence.qualification_evidence_identities],
        )
        projection = qualify_locked_source_promotion(fixture.authority, evidence)
        self.assertIn(
            validation.identity, [item.uri for item in projection.evidence_identities]
        )
        for name in (
            "source_snapshot_id",
            "promotion_reference_id",
            "review_identity",
            "qualification_result_id",
            "trust_key_id",
        ):
            with self.subTest(binding=name), self.assertRaises(SourcePromotionError):
                replace(
                    evidence,
                    static_intake_validation=replace(
                        validation, **{name: fixtures._identity("other").uri}
                    ),
                )
        with self.assertRaises(SourcePromotionError):
            replace(evidence, static_intake_review=None)

    def test_qualified_reader_requires_projection_bound_validation_without_private_key(
        self,
    ):
        fixture = self.fixture
        root = Path(fixture.temporary.name).resolve() / "promoted"
        root.mkdir()
        (root / "component.md").write_bytes(
            (fixture.component / "component.md").read_bytes()
        )
        audit = fixture.evidence.promotion_input_audits[0]
        audit_name = f"generation-input-audits/{audit.identity.split(':')[1]}.json"
        translation = {
            "schema": SOURCE_TRANSLATION_RUN_SCHEMA,
            "mode": "deterministic-static",
            "intelligence": None,
            "journals": [],
        }
        translation_identity = canonical_identity(translation)
        record = {
            "schema": REVIEWED_SOURCE_PROMOTION_PROVENANCE_SCHEMA,
            "source_snapshot_identity": self.review.source_snapshot_id,
            "specification_set_identity": (
                fixture.retained.specification_set_identity.uri
            ),
            "review_identity": fixtures._identity("intent-review").uri,
            "component_graph_identity": fixtures._identity("graph").uri,
            "translation_identity": translation_identity.uri,
            "inverse_evidence_reference": None,
            "authored_asset_bindings": [],
            "static_intake_review_reference": {
                "kind": "static-intake-review",
                "identity": self.review.identity,
                "path": "static-intake-review.json",
            },
            "generation_input_audit_references": [
                {
                    "kind": "generation-input-audit",
                    "identity": audit.identity,
                    "path": audit_name,
                }
            ],
        }
        promotion_identity = canonical_identity(record)
        retained = replace(
            fixture.retained, provenance_reference_identity=promotion_identity
        )
        validation = self.validation(retained)
        evidence = replace(
            fixture.evidence,
            authority_projection=retained,
            static_intake_review=self.review,
            static_intake_validation=validation,
            translation=translation,
            translation_identity=translation_identity,
        )
        projection = qualify_locked_source_promotion(fixture.authority, evidence)
        provenance = root / "provenance/source-promotion" / promotion_identity.digest
        (provenance / "generation-input-audits").mkdir(parents=True)
        for name, value in [
            ("reference.json", record),
            (audit_name, audit.to_dict()),
            ("static-intake-review.json", self.review.to_dict()),
            ("source-translation.json", translation),
        ]:
            (provenance / name).write_text(json.dumps(value))
        qualification_root = root / "provenance/qualification"
        qualification_root.mkdir()
        (
            qualification_root / f"{fixture.qualification.identity.digest}.json"
        ).write_text(json.dumps(fixture.qualification.to_dict()))
        with self.assertRaises(SourcePromotionError) as raised:
            verify_source_promotion_evidence(root, projection)
        self.assertEqual(
            raised.exception.code, "promotion.static_intake_validation_required"
        )
        validation_root = provenance / "static-intake-validations"
        validation_root.mkdir()
        validation_path = validation_root / f"{validation.identity.split(':')[1]}.json"
        original = json.dumps(validation.to_dict()).encode()
        validation_path.write_bytes(original)
        reopened = verify_source_promotion_evidence(root, projection)
        self.assertEqual(reopened.static_intake_validation, validation)
        self.assertEqual(reopened.static_intake_review, self.review)
        self.assertEqual(reopened.qualification_lifecycle_result, fixture.qualification)
        schema = SchemaCatalog(Path(__file__).resolve().parents[2] / "schemas/v2")
        schema.validate(record["schema"], record)
        schema.validate(
            "urn:literate-ai:schema:v1:source-static-intake-review",
            self.review.to_dict(),
        )
        schema.validate(
            "urn:literate-ai:schema:v1:source-static-intake-validation",
            validation.to_dict(),
        )
        for content in [
            json.dumps(
                {
                    **validation.to_dict(),
                    "review_identity": fixtures._identity("other").uri,
                }
            ).encode(),
            original[:-1] + b',"purpose":"local-static-intake"}',
            original.decode().encode("utf-16"),
        ]:
            with self.subTest(content_length=len(content)):
                validation_path.write_bytes(content)
                with self.assertRaises(SourcePromotionError):
                    verify_source_promotion_evidence(root, projection)
        validation_path.write_bytes(original)
        self.assertEqual(
            verify_source_promotion_evidence(root, projection).static_intake_validation,
            validation,
        )
