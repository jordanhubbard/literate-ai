"""New authored Python wire is explicit and does not reinterpret prior origins.

Inert declaration fixtures only: no provider reopening or native admission.
"""

import copy
import hashlib
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.qualification_origins import SourceDerivedQualificationOrigin
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from literate_ai.contracts.retained_libraries import RetainedLibraryBinding
from literate_ai.contracts.retained_python_authored import AuthoredRetainedPythonBinding
from literate_ai.schema_catalog import verify_schema_catalog
from tests.critical import test_authored_retained_cargo_binding as authored
from tests.critical import test_retained_python_workspace_plan as plans
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


class RetainedPythonAuthoredSchemaTests(unittest.TestCase):
    def setUp(self):
        fixture = authored.AuthoredRetainedCargoBindingTests("runTest")
        fixture.setUp()
        self.old_source = fixture.legacy
        self.old_cargo = fixture.binding
        self.plan = plans.RetainedPythonWorkspacePlanTests().plan()
        content = canonical_json_bytes(self.plan.to_dict())
        self.binding = AuthoredRetainedPythonBinding(
            self.plan.importer_project_id,
            self.old_cargo.evidence_store_id,
            self.old_cargo.provider_reference,
            self.old_cargo.selected_run_identity,
            self.plan.exports,
            BlobRef(
                hashlib.sha256(content).hexdigest(),
                len(content),
                media_type="application/json",
            ),
            self.plan.destinations,
        )

    def test_canonical_catalog_codec_and_exact_plan_join(self):
        wire = self.binding.to_dict()
        SchemaCatalog().validate(self.binding.SCHEMA, wire)
        verify_schema_catalog("v2", Path(__file__).parents[2] / "schemas/v2")
        self.assertEqual(AuthoredRetainedPythonBinding.from_dict(wire), self.binding)
        self.binding.require_declarations(self.plan)
        with self.assertRaises(ValueError):
            self.binding.require_declarations(
                replace(self.plan, importer_project_id="foreign")
            )

    def test_unknown_mixed_version_and_missing_fields_refuse(self):
        wire = self.binding.to_dict()
        variants = [
            {**wire, "schema": "literate-ai/authored-retained-python-binding@2"},
            {**wire, "gate_policy": self.old_cargo.gate_policy.to_dict()},
            {
                **wire,
                "qualification_identity": (
                    self.old_source.qualification_identity.to_dict()
                ),
            },
            {k: v for k, v in wire.items() if k != "provider_reference"},
        ]
        for candidate in variants:
            with self.subTest(keys=tuple(candidate)):
                with self.assertRaises(ValueError):
                    AuthoredRetainedPythonBinding.from_dict(candidate)
                with self.assertRaises(AssertionError):
                    SchemaCatalog().validate(self.binding.SCHEMA, candidate)

    def test_no_prior_source_or_cargo_codec_accepts_new_binding(self):
        source_before = canonical_json_bytes(self.old_source.to_dict())
        cargo_before = canonical_json_bytes(self.old_cargo.to_dict())
        for decoder in (RetainedLibraryBinding, AuthoredRetainedCargoBinding):
            with self.subTest(decoder=decoder), self.assertRaises(ValueError):
                decoder.from_dict(self.binding.to_dict())
        for old in (self.old_source, self.old_cargo):
            with self.subTest(schema=old.SCHEMA), self.assertRaises(ValueError):
                AuthoredRetainedPythonBinding.from_dict(old.to_dict())
        self.assertEqual(canonical_json_bytes(self.old_source.to_dict()), source_before)
        self.assertEqual(canonical_json_bytes(self.old_cargo.to_dict()), cargo_before)

    def test_source_origin_and_bad_reviewed_plan_bound_refuse(self):
        source_origin = SourceDerivedQualificationOrigin(
            *(
                canonical_identity(label)
                for label in ("projection", "source", "audit", "tree", "promotion")
            )
        )
        for mutate in (
            lambda w: w["provider_reference"].update(
                {"origin": source_origin.to_dict()}
            ),
            lambda w: w["provider_reference"].update({"origin": {"schema": "unknown"}}),
            lambda w: w["workspace_plan"].update({"size": 16 * 1024**2 + 1}),
            lambda w: w["workspace_plan"].update({"media_type": "application/zip"}),
        ):
            wire = copy.deepcopy(self.binding.to_dict())
            mutate(wire)
            with self.assertRaises(ValueError):
                AuthoredRetainedPythonBinding.from_dict(wire)
            with self.assertRaises(AssertionError):
                SchemaCatalog().validate(self.binding.SCHEMA, wire)
