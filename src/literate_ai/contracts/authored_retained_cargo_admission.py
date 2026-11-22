"""Authored consumer admission claims; decoding never restores live authority.

The provider reference binds the actual authored origin and complete published
plan/result/products/archive chain. These claims contain no source-promotion
facade. Only the owning admission operation may report successful completion.
"""

from dataclasses import dataclass
from typing import ClassVar

from ._validation import contract_fields, fail, list_value
from .identity import ContentIdentity, canonical_identity
from .retained_cargo_authored import AuthoredRetainedCargoBinding
from .retained_cargo_test_evidence import (
    RetainedCargoTargetEvidenceV2,
    require_retained_cargo_coverage,
)


@dataclass(frozen=True, slots=True)
class AuthoredRetainedCargoAdmissionReceipt:
    binding_identity: ContentIdentity
    reviewed_inputs_identity: ContentIdentity
    provider_reference_identity: ContentIdentity
    selected_run_identity: ContentIdentity
    exports_identity: ContentIdentity
    workspace_plan_identity: ContentIdentity
    gate_policy_identity: ContentIdentity
    test_inventory_identity: ContentIdentity
    source_retirement_identity: ContentIdentity
    consumer_inventory_identity: ContentIdentity
    original_source_scope_identity: ContentIdentity
    consumer_inputs_identity: ContentIdentity
    input_custody_policy_identity: ContentIdentity
    command_observation_identities: tuple[ContentIdentity, ...]
    target_outcomes: tuple[RetainedCargoTargetEvidenceV2, ...]

    SCHEMA: ClassVar[str] = "literate-ai/authored-retained-cargo-admission-receipt@1"
    _IDENTITIES: ClassVar[tuple[str, ...]] = (
        "binding_identity",
        "reviewed_inputs_identity",
        "provider_reference_identity",
        "selected_run_identity",
        "exports_identity",
        "workspace_plan_identity",
        "gate_policy_identity",
        "test_inventory_identity",
        "source_retirement_identity",
        "consumer_inventory_identity",
        "original_source_scope_identity",
        "consumer_inputs_identity",
        "input_custody_policy_identity",
    )

    def __post_init__(self):
        for name in self._IDENTITIES:
            if not isinstance(getattr(self, name), ContentIdentity):
                fail(self.__class__.__name__, "requires typed declaration identities")
        values = self.command_observation_identities
        if (
            not isinstance(values, tuple)
            or not 1 <= len(values) <= 100000
            or any(not isinstance(item, ContentIdentity) for item in values)
        ):
            fail(self.__class__.__name__, "requires bounded command identities")
        # Repeated metadata phases may have the same content identity. Keep the
        # complete ordered sequence rather than deduplicating actual commands.
        if (
            not isinstance(self.target_outcomes, tuple)
            or not 1 <= len(self.target_outcomes) <= 4096
            or any(
                type(x) is not RetainedCargoTargetEvidenceV2
                for x in self.target_outcomes
            )
        ):
            fail(self.__class__.__name__, "requires bounded typed target outcomes")
        keys = tuple(x.key for x in self.target_outcomes)
        if keys != tuple(sorted(set(keys))):
            fail(self.__class__.__name__, "requires unique targets in canonical order")
        count = sum(
            len(x.passed_cases) + len(x.ignored_cases) for x in self.target_outcomes
        )
        if count > 100000:
            fail(self.__class__.__name__, "aggregate case allowance exceeded")
        if not any(
            x.passed_cases or x.kind == "custom-harness" for x in self.target_outcomes
        ):
            fail(self.__class__.__name__, "requires positive execution coverage")
        phases = tuple(
            identity
            for x in self.target_outcomes
            for identity in x.command_observation_identities
        )
        if len(set(phases)) != len(phases) or not set(phases) <= set(
            self.command_observation_identities
        ):
            fail(
                self.__class__.__name__,
                "requires distinct bound target phase observations",
            )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    @property
    def coverage_counts(self):
        return {
            "passed_cases": sum(len(x.passed_cases) for x in self.target_outcomes),
            "reviewed_ignored_cases": sum(
                len(x.ignored_cases) for x in self.target_outcomes
            ),
            "custom_commands": sum(
                x.kind == "custom-harness" for x in self.target_outcomes
            ),
            "excluded_targets": sum(x.kind == "excluded" for x in self.target_outcomes),
        }

    def require_declarations(self, binding, plan, policy, inventory):
        if type(binding) is not AuthoredRetainedCargoBinding:
            fail(self.__class__.__name__, "requires the exact authored binding")
        binding.require_declarations(plan, policy, inventory)
        if (
            self.binding_identity != binding.identity
            or self.provider_reference_identity != binding.provider_reference.identity
            or self.selected_run_identity != binding.selected_run_identity
            or self.exports_identity != binding.exports.identity
            or self.workspace_plan_identity != plan.identity
            or self.gate_policy_identity != policy.identity
            or self.test_inventory_identity != inventory.identity
            or self.input_custody_policy_identity != policy.input_custody.identity
        ):
            fail(self.__class__.__name__, "receipt declaration identities differ")
        require_retained_cargo_coverage(self.target_outcomes, inventory)

    def to_dict(self):
        return {
            "schema": self.SCHEMA,
            **{name: getattr(self, name).to_dict() for name in self._IDENTITIES},
            "command_observation_identities": [
                item.to_dict() for item in self.command_observation_identities
            ],
            "target_outcomes": [item.to_dict() for item in self.target_outcomes],
            "coverage_counts": self.coverage_counts,
        }

    @classmethod
    def from_dict(cls, value):
        data = contract_fields(
            value,
            path=cls.__name__,
            schema_uri=cls.SCHEMA,
            required=frozenset(cls._IDENTITIES)
            | {"command_observation_identities", "target_outcomes", "coverage_counts"},
        )
        outcomes = list_value(data["target_outcomes"], cls.__name__)
        observations = list_value(data["command_observation_identities"], cls.__name__)
        if not 1 <= len(outcomes) <= 4096 or not 1 <= len(observations) <= 100000:
            fail(cls.__name__, "receipt record allowance exceeded")
        count = 0
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                fail(cls.__name__, "requires target outcome records")
            count += len(list_value(outcome.get("passed_cases"), cls.__name__))
            count += len(list_value(outcome.get("ignored_cases"), cls.__name__))
            if count > 100000:
                fail(cls.__name__, "aggregate case allowance exceeded")
        result = cls(
            *(ContentIdentity.from_dict(data[name]) for name in cls._IDENTITIES),
            tuple(ContentIdentity.from_dict(item) for item in observations),
            tuple(RetainedCargoTargetEvidenceV2.from_dict(item) for item in outcomes),
        )
        counts = data["coverage_counts"]
        if (
            not isinstance(counts, dict)
            or counts.keys() != result.coverage_counts.keys()
            or any(type(item) is not int for item in counts.values())
            or counts != result.coverage_counts
        ):
            fail(cls.__name__, "coverage counts differ from explicit target outcomes")
        return result
