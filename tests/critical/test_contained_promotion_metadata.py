"""Real persisted source-promotion metadata controls, without qualification claims."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.authority import FileAuthorityProjectionStore
from literate_ai.authority import ComponentAuthorityLifecycle
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.projects import ProjectConfigurationStore
from literate_ai.source_to_specification.promotion_materialization import (
    SOURCE_PROMOTION_PROVENANCE_SCHEMA,
    PromotionInputKind,
    SourcePromotionInput,
    SourcePromotionMaterializer,
    verify_source_promotion_evidence,
)
from tests.support import fixtures_test_project_configuration


class ContainedPromotionMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def _project(self, contained):
        definition = fixtures_test_project_configuration._definition()
        if contained:
            definition = replace(definition, framework_directory="litai")
        return ProjectConfigurationStore(self.root).create(definition)

    def _source_promotion(self, contained):
        snapshot = self._project(contained)
        relative = snapshot.manifest_path.relative_to(self.root).as_posix()
        identity = "sha256:" + hashlib.sha256(snapshot.content).hexdigest()
        audit = SourcePromotionMaterializer().audit(
            (
                SourcePromotionInput(
                    kind=PromotionInputKind.PROJECT_CONFIGURATION,
                    source_root=self.root,
                    source_root_label="actual-owned-project",
                    source_path=relative,
                    target_path=relative,
                    expected_content_identity=identity,
                ),
            )
        )
        digest = ContentIdentity.parse_uri("sha256:" + "a" * 64)
        record = {
            "schema": SOURCE_PROMOTION_PROVENANCE_SCHEMA,
            "source_snapshot_identity": digest.uri,
            "specification_set_identity": digest.uri,
            "review_identity": digest.uri,
            "component_graph_identity": digest.uri,
            "translation_identity": None,
            "inverse_evidence_reference": None,
            "generation_input_audit_references": [
                {
                    "kind": "generation-input-audit",
                    "identity": audit.identity,
                    "path": "generation-input-audits/"
                    + ContentIdentity.parse_uri(audit.identity).digest
                    + ".json",
                }
            ],
        }
        record_id = canonical_identity(record)
        projection = ComponentAuthorityLifecycle.inventory(
            component_coordinate="component://fixture/metadata",
            source_snapshot_identity=digest,
            provenance_reference_identity=record_id,
            evidence_identities=(digest,),
        )
        metadata = ProjectConfigurationStore.context(self.root).framework_root
        directory = metadata / "provenance/source-promotion" / record_id.digest
        (directory / "generation-input-audits").mkdir(parents=True)
        (directory / "reference.json").write_text(json.dumps(record))
        (directory / record["generation_input_audit_references"][0]["path"]).write_text(
            json.dumps(audit.to_dict())
        )
        return projection, audit, metadata

    def test_actual_contained_source_evidence_reopens_against_app_relative_audit(self):
        projection, audit, metadata = self._source_promotion(True)
        # An unowned root decoy cannot override selected framework evidence.
        (self.root / "provenance").mkdir()
        (self.root / "provenance/foreign.txt").write_bytes(b"application-owned")
        result = verify_source_promotion_evidence(self.root, projection)
        self.assertEqual(result.promotion_input_audits, (audit,))
        self.assertEqual(audit.entries[0].target_path, "litai/literate.project.json")
        self.assertEqual(
            (self.root / "provenance/foreign.txt").read_bytes(), b"application-owned"
        )
        stored = FileAuthorityProjectionStore(self.root).append(projection)
        self.assertTrue(
            stored.is_relative_to(metadata / "provenance/component-authority")
        )
        self.assertFalse((self.root / "provenance/component-authority").exists())

    def test_actual_legacy_source_evidence_and_store_keep_original_coordinates(self):
        projection, audit, metadata = self._source_promotion(False)
        self.assertEqual(metadata, self.root)
        result = verify_source_promotion_evidence(self.root, projection)
        self.assertEqual(result.promotion_input_audits, (audit,))
        self.assertEqual(audit.entries[0].target_path, "literate.project.json")
        stored = FileAuthorityProjectionStore(self.root).append(projection)
        self.assertTrue(
            stored.is_relative_to(self.root / "provenance/component-authority")
        )

    def test_contained_audit_still_refuses_application_manifest_byte_drift(self):
        projection, _, _ = self._source_promotion(True)
        path = self.root / "litai/literate.project.json"
        value = json.loads(path.read_bytes())
        value["version"] = "99.0.0"
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            verify_source_promotion_evidence(self.root, projection)
