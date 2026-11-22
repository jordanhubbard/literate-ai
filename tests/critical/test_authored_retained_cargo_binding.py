"""New authored receiving declarations cannot acquire legacy source authority.

These are inert contract values, not a qualified archive or importer admission.
Full current-owner, all-run reopening and actual consumer controls are separate.
"""

import copy
import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.contracts.authored_qualification_reference import (
    AuthoredQualificationReference,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.qualification_origins import (
    AuthoredQualificationOrigin,
    SourceDerivedQualificationOrigin,
)
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from literate_ai.contracts.retained_cargo_binding_v2 import RetainedCargoBindingV2
from literate_ai.contracts.retained_libraries import RetainedLibraryBinding
from tests.support import fixtures_test_retained_library_binding as fixtures
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


def _json(label):
    content = canonical_json_bytes({"inert-consumer-declaration": label})
    return BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/json"
    )


class AuthoredRetainedCargoBindingTests(unittest.TestCase):
    def setUp(self):
        self.legacy = fixtures.RetainedLibraryBindingTests().fixture()
        identity = canonical_identity
        origin = AuthoredQualificationOrigin(
            *(
                identity(label)
                for label in ("project", "authority", "lock", "authoring")
            )
        )
        reference = AuthoredQualificationReference(
            origin,
            *(
                identity(label)
                for label in ("plan", "result", "products", "intent", "stage")
            ),
            self.legacy.qualification_archive,
            "a" * 32,
        )
        self.binding = AuthoredRetainedCargoBinding(
            "importer",
            "reviewed-artifacts",
            reference,
            identity("selected-authored-run"),
            self.legacy.exports,
            _json("plan"),
            _json("policy"),
            _json("inventory"),
            self.legacy.destinations,
        )

    def test_new_wire_roundtrips_without_reinterpreting_legacy_binding(self):
        original = canonical_json_bytes(self.legacy.to_dict())
        wire = self.binding.to_dict()
        self.assertEqual(AuthoredRetainedCargoBinding.from_dict(wire), self.binding)
        SchemaCatalog().validate(self.binding.SCHEMA, wire)
        self.assertNotEqual(self.binding.identity, self.legacy.identity)
        self.assertEqual(canonical_json_bytes(self.legacy.to_dict()), original)
        for decoder in (
            RetainedLibraryBinding.from_dict,
            RetainedCargoBindingV2.from_dict,
        ):
            with self.subTest(decoder=decoder), self.assertRaises(ValueError):
                decoder(wire)
        with self.assertRaises(ValueError):
            AuthoredRetainedCargoBinding.from_dict(self.legacy.to_dict())

    def test_source_derived_reference_and_unknown_origin_cannot_enter_new_wire(self):
        source = SourceDerivedQualificationOrigin(
            *(
                canonical_identity(label)
                for label in ("projection", "source", "audit", "tree", "promotion")
            )
        )
        for origin in (source.to_dict(), {"origin": "authored", "schema": "unknown"}):
            candidate = copy.deepcopy(self.binding.to_dict())
            candidate["provider_reference"]["origin"] = origin
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                AuthoredRetainedCargoBinding.from_dict(candidate)
        for flag in ("accepted", "qualified", "reviewed", "allow_host_execution"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                AuthoredRetainedCargoBinding.from_dict(
                    {**self.binding.to_dict(), flag: True}
                )

    def test_all_graph_exports_need_unique_portable_nonoverlapping_destinations(self):
        rows = self.binding.destinations
        for destinations in (rows[:-1], rows[::-1], rows + rows[:1]):
            with self.subTest(destinations=destinations), self.assertRaises(ValueError):
                replace(self.binding, destinations=destinations)
        for path in ("../escape", "CON", "lib\\bad", "libs/a."):
            with self.subTest(path=path), self.assertRaises(ValueError):
                replace(self.binding, destinations=((rows[0][0], path), *rows[1:]))
        with self.assertRaises(ValueError):
            replace(
                self.binding,
                destinations=tuple((row[0], "same") for row in rows),
            )

    def test_candidate_cannot_supply_endpoint_or_unbounded_reviewed_documents(self):
        for store in ("", "/ambient/store", "https://candidate.invalid/archive"):
            with self.subTest(store=store), self.assertRaises(ValueError):
                replace(self.binding, evidence_store_id=store)
        for changes in (
            {"selected_run_identity": True},
            {"provider_reference": self.binding.provider_reference.to_dict()},
            {"gate_policy": replace(self.binding.gate_policy, size=0)},
            {
                "test_inventory": replace(
                    self.binding.test_inventory, size=256 * 1024**2 + 1
                )
            },
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.binding, **changes)
        with self.assertRaises(ValueError):
            self.binding.require_declarations({}, {}, {})

    def test_importer_identifier_refuses_control_characters_in_codec_and_schema(self):
        for character in ("\x00", "\x1f", "\x7f"):
            wire = self.binding.to_dict()
            wire["importer_project_id"] = "importer" + character
            with self.subTest(character=repr(character)):
                with self.assertRaises(ValueError):
                    AuthoredRetainedCargoBinding.from_dict(wire)
                with self.assertRaises(AssertionError):
                    SchemaCatalog().validate(self.binding.SCHEMA, wire)

    def test_typed_consumer_declarations_require_exact_importer_plan_and_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(
                Path(directory).resolve(strict=True)
            ) as reviewed:
                plan, policy, inventory = (
                    reviewed.plan,
                    reviewed.policy,
                    reviewed.inventory,
                )
                binding = replace(
                    self.binding,
                    importer_project_id=policy.importer_project_id,
                    workspace_plan=reviewed.binding.common.workspace_plan,
                    gate_policy=reviewed.binding.gate_policy,
                    test_inventory=reviewed.binding.test_inventory,
                )
                self.assertIsNone(binding.require_declarations(plan, policy, inventory))
                foreign = canonical_identity("foreign-consumer-declaration")
                cases = (
                    (
                        replace(binding, importer_project_id="foreign"),
                        policy,
                        inventory,
                    ),
                    (
                        binding,
                        replace(
                            policy,
                            common=replace(
                                policy.common, importer_project_id="foreign"
                            ),
                        ),
                        inventory,
                    ),
                    (
                        binding,
                        policy,
                        replace(inventory, importer_project_id="foreign"),
                    ),
                    (
                        binding,
                        policy,
                        replace(inventory, workspace_plan_identity=foreign),
                    ),
                    (binding, policy, replace(inventory, gate_policy_identity=foreign)),
                )
                for candidate, gate, targets in cases:
                    with self.subTest(
                        candidate=candidate.identity.uri,
                        gate=gate.identity.uri,
                        targets=targets.identity.uri,
                    ):
                        with self.assertRaises(ValueError):
                            candidate.require_declarations(plan, gate, targets)
