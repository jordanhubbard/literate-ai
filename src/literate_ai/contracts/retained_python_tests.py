"""Reviewed complete Python gate classification; no execution or admission grant."""

from dataclasses import dataclass
from typing import ClassVar

from ._validation import contract_fields, fail, fields, list_value, string_value
from .blobs import BlobRef
from .identity import ContentIdentity, canonical_identity
from .paths import canonical_relative_posix_path
from .retained_libraries import RetainedLibraryGatePolicy
from .retained_project_tests import (
    RetainedProjectExpectedCase,
    RetainedProjectTestReport,
)
from .retained_test_cases import validate_retained_test_cases


@dataclass(frozen=True, slots=True)
class RetainedPythonTestInventory:
    """Bind original expected cases and classify every independently reviewed gate.

    The record deliberately does not reference a workspace plan: that plan names
    these bytes. Current source/harness custody and actual execution must still
    establish that this reviewed inventory covers the consumer being admitted.
    """

    importer_project_id: str
    wrapper_component: str
    harness_inventory: BlobRef
    source_scope_identity: ContentIdentity
    gate_policy_identity: ContentIdentity
    cases: tuple[RetainedProjectExpectedCase, ...]
    non_test_steps: tuple[tuple[str, str], ...]

    SCHEMA: ClassVar[str] = "literate-ai/retained-python-test-inventory@1"
    MAX_CASES: ClassVar[int] = 100000
    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "importer_project_id",
            "wrapper_component",
            "harness_inventory",
            "source_scope_identity",
            "gate_policy_identity",
            "cases",
            "non_test_steps",
        }
    )

    def __post_init__(self):
        label = type(self).__name__
        string_value(self.importer_project_id, label, max_length=256)
        if any(ord(c) < 32 or ord(c) == 127 for c in self.importer_project_id):
            fail(label, "requires a printable importer identifier")
        canonical_relative_posix_path(self.wrapper_component, label=label)
        if len(self.wrapper_component) > 128:
            fail(label, "wrapper path exceeds its bound")
        if (
            type(self.harness_inventory) is not BlobRef
            or self.harness_inventory.media_type != "application/json"
            or not 0 < self.harness_inventory.size <= 16 * 1024**2
            or type(self.source_scope_identity) is not ContentIdentity
            or type(self.gate_policy_identity) is not ContentIdentity
        ):
            fail(label, "requires exact bounded current inventory references")
        if (
            type(self.cases) is not tuple
            or not 1 <= len(self.cases) <= self.MAX_CASES
            or any(type(c) is not RetainedProjectExpectedCase for c in self.cases)
        ):
            fail(label, "requires bounded typed original cases")
        validate_retained_test_cases(tuple(c.case_id for c in self.cases))
        if not any(c.skip_reason is None for c in self.cases):
            fail(label, "requires positive original execution coverage")
        if type(self.non_test_steps) is not tuple or len(self.non_test_steps) > 128:
            fail(label, "requires bounded non-test gate classifications")
        names = []
        for row in self.non_test_steps:
            if type(row) is not tuple or len(row) != 2:
                fail(label, "requires typed non-test gate classifications")
            name, reason = row
            string_value(name, label, max_length=128)
            string_value(reason, label, max_length=1024)
            if not reason.strip() or any(ord(c) < 32 or ord(c) == 127 for c in reason):
                fail(label, "requires an explicit printable non-test reason")
            names.append(name)
        if tuple(names) != tuple(sorted(set(names))) or set(names) & {
            c.action_id for c in self.cases
        }:
            fail(label, "requires disjoint unique gate classifications")

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def require_policy(self, policy):
        if type(policy) is not RetainedLibraryGatePolicy or (
            policy.importer_project_id != self.importer_project_id
            or policy.identity != self.gate_policy_identity
        ):
            fail(type(self).__name__, "current gate policy mismatch")
        classified = {c.action_id for c in self.cases} | {
            name for name, _ in self.non_test_steps
        }
        if classified != {command.step_id for command in policy.commands}:
            fail(type(self).__name__, "must classify every original gate exactly once")

    def require_reports(self, reports):
        """Match all original cases; missing/extra/zero or undeclared skips refuse.

        The caller owns the actual sealed report bytes and current full gates.
        Supplying decoded reports here establishes only their semantic match.
        """
        if type(reports) is not tuple or any(
            type(report) is not RetainedProjectTestReport for report in reports
        ):
            fail(type(self).__name__, "requires typed original test reports")
        names = tuple(report.action_id for report in reports)
        expected = {c.case_id: c for c in self.cases}
        if len(names) != len(set(names)) or set(names) != {
            c.action_id for c in self.cases
        }:
            fail(type(self).__name__, "complete original reports required")
        for report in reports:
            if {c.case_id for c in report.cases} != {
                c.case_id for c in self.cases if c.action_id == report.action_id
            }:
                fail(type(self).__name__, "complete original case membership required")
            for case in report.cases:
                original = expected[case.case_id]
                if case.outcome == "failed" or (
                    case.outcome == "skipped"
                    and (
                        original.skip_reason is None
                        or case.reason != original.skip_reason
                    )
                ):
                    fail(type(self).__name__, "original test outcome refused")
        if not sum(report.passed for report in reports):
            fail(type(self).__name__, "positive original execution required")

    def to_dict(self):
        return {
            "schema": self.SCHEMA,
            "importer_project_id": self.importer_project_id,
            "wrapper_component": self.wrapper_component,
            "harness_inventory": self.harness_inventory.to_dict(),
            "source_scope_identity": self.source_scope_identity.to_dict(),
            "gate_policy_identity": self.gate_policy_identity.to_dict(),
            "cases": [case.to_dict() for case in self.cases],
            "non_test_steps": [
                {"step_id": name, "reason": reason}
                for name, reason in self.non_test_steps
            ],
        }

    @classmethod
    def from_dict(cls, value):
        data = contract_fields(
            value, path=cls.__name__, schema_uri=cls.SCHEMA, required=cls._FIELDS
        )
        cases = list_value(data["cases"], cls.__name__)
        steps = list_value(data["non_test_steps"], cls.__name__)
        if not 1 <= len(cases) <= cls.MAX_CASES or len(steps) > 128:
            fail(cls.__name__, "original inventory allowance exceeded")
        non_test = []
        for row in steps:
            row = fields(
                row, path=cls.__name__, required=frozenset({"step_id", "reason"})
            )
            non_test.append((row["step_id"], row["reason"]))
        return cls(
            data["importer_project_id"],
            data["wrapper_component"],
            BlobRef.from_dict(data["harness_inventory"]),
            ContentIdentity.from_dict(data["source_scope_identity"]),
            ContentIdentity.from_dict(data["gate_policy_identity"]),
            tuple(RetainedProjectExpectedCase.from_dict(case) for case in cases),
            tuple(non_test),
        )
