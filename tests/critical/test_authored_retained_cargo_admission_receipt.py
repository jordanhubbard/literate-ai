"""Untrusted authored admission claims remain distinct and bounded."""

import copy
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jsonschema import ValidationError

from literate_ai.contracts.authored_retained_cargo_admission import (
    AuthoredRetainedCargoAdmissionReceipt as Receipt,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_admission import RetainedCargoAdmissionReceipt
from literate_ai.contracts.retained_cargo_admission_v2 import (
    RetainedCargoAdmissionReceiptV2,
)
from literate_ai.contracts.retained_cargo_test_evidence import (
    RetainedCargoTargetEvidenceV2,
)
from literate_ai.contracts.retained_cargo_test_protocol import RetainedCargoIgnoredCase
from tests.critical import test_authored_retained_cargo_binding as bindings
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture
from tests.support.fixtures_test_component_authoring_lock_contracts import (
    official_validator,
)


class AuthoredAdmissionReceiptTests(unittest.TestCase):
    def setUp(self):
        self.listing = canonical_identity("listing")
        self.execution = canonical_identity("execution")
        self.metadata = canonical_identity("metadata")
        self.outcome = RetainedCargoTargetEvidenceV2(
            "lib",
            "library",
            ("lib",),
            "libtest",
            ("actual_case",),
            (RetainedCargoIgnoredCase("reviewed_ignored", "independent reason"),),
            (self.listing, self.execution),
            None,
        )
        self.receipt = Receipt(
            *(canonical_identity(name) for name in Receipt._IDENTITIES),
            (self.metadata, self.listing, self.execution, self.metadata),
            (self.outcome,),
        )

    def test_ordered_duplicate_metadata_survives_roundtrip_without_source_cast(self):
        wire = self.receipt.to_dict()
        official_validator(Receipt.SCHEMA).validate(wire)
        reopened = Receipt.from_dict(wire)
        self.assertEqual(reopened, self.receipt)
        self.assertEqual(
            reopened.command_observation_identities[0],
            reopened.command_observation_identities[-1],
        )
        self.assertEqual(
            reopened.coverage_counts,
            dict(
                passed_cases=1,
                reviewed_ignored_cases=1,
                custom_commands=0,
                excluded_targets=0,
            ),
        )
        for decoder in (
            RetainedCargoAdmissionReceipt.from_dict,
            RetainedCargoAdmissionReceiptV2.from_dict,
        ):
            with self.subTest(decoder=decoder), self.assertRaises(ValueError):
                decoder(wire)

    def test_forged_counts_unknown_fields_and_source_schema_refuse(self):
        for mutate in (
            lambda wire: wire["coverage_counts"].update(passed_cases=2),
            lambda wire: wire["coverage_counts"].update(passed_cases=True),
            lambda wire: wire.update(accepted=True),
            lambda wire: wire.update(schema=RetainedCargoAdmissionReceiptV2.SCHEMA),
        ):
            wire = copy.deepcopy(self.receipt.to_dict())
            mutate(wire)
            with self.subTest(wire=wire), self.assertRaises(ValueError):
                Receipt.from_dict(wire)

    def test_missing_or_reused_target_phase_observation_refuses(self):
        with self.assertRaises(ValueError):
            replace(self.receipt, command_observation_identities=(self.metadata,))
        other = replace(self.outcome, target_name="other")
        with self.assertRaises(ValueError):
            replace(self.receipt, target_outcomes=(self.outcome, other))

    def test_exclusion_only_cannot_claim_positive_execution(self):
        excluded = RetainedCargoTargetEvidenceV2(
            "lib",
            "excluded",
            ("lib",),
            "excluded",
            (),
            (),
            (),
            canonical_identity("permission"),
        )
        with self.assertRaises(ValueError):
            replace(self.receipt, target_outcomes=(excluded,))
        wire = self.receipt.to_dict()
        wire["target_outcomes"] = [excluded.to_dict()]
        wire["coverage_counts"] = dict(
            passed_cases=0,
            reviewed_ignored_cases=0,
            custom_commands=0,
            excluded_targets=1,
        )
        with self.assertRaises(ValidationError):
            official_validator(Receipt.SCHEMA).validate(wire)

    def test_aggregate_case_limit_is_checked_before_nested_decoding(self):
        wire = self.receipt.to_dict()
        wire["target_outcomes"][0]["passed_cases"] = ["oversized"] * 100001
        with self.assertRaisesRegex(ValueError, "aggregate case allowance"):
            Receipt.from_dict(wire)

    def test_foreign_binding_and_untyped_identity_cannot_enter_declaration_join(self):
        with self.assertRaises(ValueError):
            self.receipt.require_declarations({}, {}, {}, {})
        with self.assertRaises(ValueError):
            replace(self.receipt, provider_reference_identity=True)

    def test_actual_typed_declarations_bind_each_provider_and_consumer_identity(self):
        helper = bindings.AuthoredRetainedCargoBindingTests("runTest")
        helper.setUp()
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(
                Path(directory).resolve(strict=True)
            ) as reviewed:
                binding = replace(
                    helper.binding,
                    importer_project_id=reviewed.policy.importer_project_id,
                    workspace_plan=reviewed.binding.common.workspace_plan,
                    gate_policy=reviewed.binding.gate_policy,
                    test_inventory=reviewed.binding.test_inventory,
                )
                outcomes = tuple(
                    RetainedCargoTargetEvidenceV2(
                        target.package_root,
                        target.target_name,
                        target.target_kinds,
                        "libtest",
                        target.protocol.must_run,
                        target.protocol.ignored,
                        (
                            canonical_identity((target.key, "list")),
                            canonical_identity((target.key, "run")),
                        ),
                        None,
                    )
                    for target in reviewed.inventory.targets
                )
                receipt = replace(
                    self.receipt,
                    binding_identity=binding.identity,
                    provider_reference_identity=binding.provider_reference.identity,
                    selected_run_identity=binding.selected_run_identity,
                    exports_identity=binding.exports.identity,
                    workspace_plan_identity=reviewed.plan.identity,
                    gate_policy_identity=reviewed.policy.identity,
                    test_inventory_identity=reviewed.inventory.identity,
                    input_custody_policy_identity=reviewed.policy.input_custody.identity,
                    command_observation_identities=tuple(
                        identity
                        for outcome in outcomes
                        for identity in outcome.command_observation_identities
                    ),
                    target_outcomes=outcomes,
                )
                receipt.require_declarations(
                    binding, reviewed.plan, reviewed.policy, reviewed.inventory
                )
                for name in (
                    "binding_identity",
                    "provider_reference_identity",
                    "selected_run_identity",
                    "exports_identity",
                    "workspace_plan_identity",
                    "gate_policy_identity",
                    "test_inventory_identity",
                    "input_custody_policy_identity",
                ):
                    with self.subTest(name=name), self.assertRaises(ValueError):
                        replace(
                            receipt, **{name: canonical_identity("foreign")}
                        ).require_declarations(
                            binding, reviewed.plan, reviewed.policy, reviewed.inventory
                        )
