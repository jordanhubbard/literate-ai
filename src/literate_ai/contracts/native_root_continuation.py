"""Closed native-root continuation data; never live execution authority.

These records distinguish original node observations from later packaged-root
decisions. Pure joins check retained identities and budget consistency. They do
not restore a verifier, deadline, prepared source owner or permission to run.
The existing v2 candidate-repair contracts keep their separate interpretation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from functools import cache
from types import UnionType
from typing import Any, ClassVar, get_args, get_origin, get_type_hints

from ._validation import contract_fields, fail
from ._validation import fields as closed_fields
from .identity import ContentIdentity, contract_identity

_MAX_INT = 2**63 - 1
_NANOSECONDS = 1_000_000_000
# New local whole-run policy ceiling, independent of the shipped 1800s default
# and of each operation's tighter phase cap. No historical deadline is implied.
NATIVE_ROOT_RUN_MAX_DURATION_SECONDS = 86_400
_NONCE = re.compile(r"[0-9a-f]{32}\Z")
_CODE = re.compile(r"[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?\Z")
NATIVE_ROOT_RESULT_MISMATCH = "component_acceptance.rust_harness_result_mismatch"
NATIVE_ROOT_REPAIR_MESSAGE = (
    "the independent native library verifier rejected the generated public "
    "behavior; produce a complete fresh replacement from the approved public "
    "specifications and interfaces"
)


@cache
def _annotations(cls):
    return get_type_hints(cls)


def _integer(value, path, minimum=0, maximum=_MAX_INT):
    if type(value) is not int or not minimum <= value <= maximum:
        fail(path, f"must be an integer in {minimum}..{maximum}")


def _choice(value, choices, path):
    if type(value) is not str or value not in choices:
        fail(path, "unsupported exact value")


def _nonce(value, path):
    if type(value) is not str or not _NONCE.fullmatch(value):
        fail(path, "must be 32 lowercase hexadecimal characters")


def _ids(values, path, *, canonical=False, length=None):
    if type(values) is not tuple or any(type(v) is not ContentIdentity for v in values):
        fail(path, "must be an immutable tuple of ContentIdentity values")
    if len(set(values)) != len(values):
        fail(path, "identities must be unique")
    if length is not None and len(values) != length:
        fail(path, "must contain the exact predecessor prefix")
    if canonical and values != tuple(sorted(values, key=lambda v: v.uri)):
        fail(path, "identities must be in canonical order")


def _check_type(annotation, value, path):
    if get_origin(annotation) is UnionType:
        choices = get_args(annotation)
        if value is None and type(None) in choices:
            return
        other = tuple(choice for choice in choices if choice is not type(None))
        if len(other) == 1:
            return _check_type(other[0], value, path)
    if get_origin(annotation) is tuple:
        if type(value) is not tuple:
            fail(path, "must be an immutable tuple")
        for index, item in enumerate(value):
            _check_type(get_args(annotation)[0], item, f"{path}[{index}]")
        return
    if type(value) is not annotation:
        fail(path, f"must be an exact {annotation.__name__}")
    if annotation is int:
        _integer(value, path)
    elif annotation is ContentIdentity:
        value.__post_init__()
    elif isinstance(value, _ClosedValue):
        value.__post_init__()


def _decode(annotation, value, path):
    if get_origin(annotation) is UnionType:
        if value is None:
            return None
        annotation = next(v for v in get_args(annotation) if v is not type(None))
    if get_origin(annotation) is tuple:
        if type(value) is not list:
            fail(path, "wire arrays must be JSON lists")
        return tuple(
            _decode(get_args(annotation)[0], item, f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if annotation is ContentIdentity or issubclass(annotation, _ClosedValue):
        return annotation.from_dict(value, path=path)
    _check_type(annotation, value, path)
    return value


def _encode(value):
    if isinstance(value, (ContentIdentity, _ClosedValue)):
        return value.to_dict()
    if type(value) is tuple:
        return [_encode(item) for item in value]
    return value


class _ClosedValue:
    SCHEMA: ClassVar[str | None] = None

    def _check(self):
        annotations = _annotations(type(self))
        for field in fields(self):
            _check_type(
                annotations[field.name],
                getattr(self, field.name),
                f"{type(self).__name__}.{field.name}",
            )

    @property
    def identity(self) -> ContentIdentity:
        return contract_identity(self)

    def to_dict(self) -> dict[str, object]:
        self.__post_init__()
        result = {} if self.SCHEMA is None else {"schema": self.SCHEMA}
        result.update(
            (field.name, _encode(getattr(self, field.name))) for field in fields(self)
        )
        return result

    @classmethod
    def from_dict(cls, value: Any, *, path: str | None = None):
        path = path or cls.__name__
        if type(value) is not dict:
            fail(path, "must be a JSON object")
        required = frozenset(field.name for field in fields(cls))
        data = (
            closed_fields(value, path=path, required=required)
            if cls.SCHEMA is None
            else contract_fields(
                value, path=path, schema_uri=cls.SCHEMA, required=required
            )
        )
        annotations = _annotations(cls)
        return cls(
            **{
                name: _decode(annotations[name], data[name], f"{path}.{name}")
                for name in required
            }
        )


@dataclass(frozen=True, slots=True)
class NativeRootRunPolicy(_ClosedValue):
    max_duration_seconds: int
    candidate_limit: int
    SCHEMA: ClassVar[str] = "literate-ai/native-root-run-policy@1"

    def __post_init__(self):
        self._check()
        _integer(
            self.max_duration_seconds,
            "NativeRootRunPolicy.max_duration_seconds",
            1,
            NATIVE_ROOT_RUN_MAX_DURATION_SECONDS,
        )
        _integer(self.candidate_limit, "NativeRootRunPolicy.candidate_limit", 3, 3)


@dataclass(frozen=True, slots=True)
class NativeRootRunDeadline(_ClosedValue):
    run_nonce: str
    policy_identity: ContentIdentity
    started_utc_ns: int
    expires_utc_ns: int
    SCHEMA: ClassVar[str] = "literate-ai/native-root-run-deadline@1"

    def __post_init__(self):
        self._check()
        _nonce(self.run_nonce, "NativeRootRunDeadline.run_nonce")
        if not (
            0
            < self.expires_utc_ns - self.started_utc_ns
            <= NATIVE_ROOT_RUN_MAX_DURATION_SECONDS * _NANOSECONDS
        ):
            fail(
                "NativeRootRunDeadline",
                "expiry must follow start within the local whole-run ceiling",
            )

    def require_policy(self, policy: NativeRootRunPolicy) -> None:
        """Check a data join; this does not select a policy or observe a clock."""
        _check_type(NativeRootRunPolicy, policy, "NativeRootRunDeadline.policy")
        if (
            self.policy_identity != policy.identity
            or self.expires_utc_ns - self.started_utc_ns
            > policy.max_duration_seconds * _NANOSECONDS
        ):
            fail("NativeRootRunDeadline", "deadline differs from its explicit policy")


@dataclass(frozen=True, slots=True)
class NativeRootPackageBinding(_ClosedValue):
    """Closed inline package coordinates, not an independently versioned record."""

    artifact_graph_identity: ContentIdentity
    link_plan_identity: ContentIdentity
    package_plan_identity: ContentIdentity
    package_result_identity: ContentIdentity
    root_generated_test_identity: ContentIdentity
    packaged_execution_identity: ContentIdentity

    def __post_init__(self):
        self._check()


@dataclass(frozen=True, slots=True)
class NativeRootQualifiedDependencyBinding(_ClosedValue):
    component_revision: ContentIdentity
    acceptance_identity: ContentIdentity
    qualified_product_identity: ContentIdentity
    source_provenance_identity: ContentIdentity
    artifact_export_identities: tuple[ContentIdentity, ...]
    target_profile_identity: ContentIdentity
    toolchain_binding_identities: tuple[ContentIdentity, ...]
    sdk_binding_identities: tuple[ContentIdentity, ...]
    SCHEMA: ClassVar[str] = "literate-ai/native-root-qualified-dependency-binding@1"

    def __post_init__(self):
        self._check()
        for name in (
            "artifact_export_identities",
            "toolchain_binding_identities",
            "sdk_binding_identities",
        ):
            _ids(getattr(self, name), name, canonical=True)
        if not self.artifact_export_identities:
            fail(
                "NativeRootQualifiedDependencyBinding", "qualified exports are required"
            )


@dataclass(frozen=True, slots=True)
class NativeRootRunBinding(_ClosedValue):
    run_nonce: str
    project_definition_identity: ContentIdentity
    project_authority_identity: ContentIdentity
    root_revision: ContentIdentity
    component_lock_identity: ContentIdentity
    execution_plan_identity: ContentIdentity
    original_recipe_identity: ContentIdentity
    original_generation_plan_identity: ContentIdentity
    original_bounded_request_identity: ContentIdentity
    framework_distribution_identity: ContentIdentity
    lifecycle_policy_identity: ContentIdentity
    target_profile_identity: ContentIdentity
    verifier_profile_identity: ContentIdentity
    oracle_identity: ContentIdentity
    original_deadline_identity: ContentIdentity
    qualified_dependency_binding_identities: tuple[ContentIdentity, ...]
    candidate_limit: int
    SCHEMA: ClassVar[str] = "literate-ai/native-root-run-binding@1"

    def __post_init__(self):
        self._check()
        _nonce(self.run_nonce, "NativeRootRunBinding.run_nonce")
        _integer(self.candidate_limit, "NativeRootRunBinding.candidate_limit", 3, 3)
        _ids(
            self.qualified_dependency_binding_identities, "dependencies", canonical=True
        )

    def require_records(
        self,
        policy,
        deadline,
        dependencies=(),
        *,
        project_definition_identity,
        project_authority_identity,
    ) -> None:
        """Join closed records only; qualified/live dependency authority is separate."""
        _check_type(
            ContentIdentity, project_definition_identity, "project_definition_identity"
        )
        _check_type(
            ContentIdentity, project_authority_identity, "project_authority_identity"
        )
        _check_type(NativeRootRunDeadline, deadline, "deadline")
        deadline.require_policy(policy)
        _check_type(
            tuple[NativeRootQualifiedDependencyBinding, ...],
            dependencies,
            "dependencies",
        )
        if (
            self.project_definition_identity != project_definition_identity
            or self.project_authority_identity != project_authority_identity
            or deadline.run_nonce != self.run_nonce
            or deadline.identity != self.original_deadline_identity
            or self.qualified_dependency_binding_identities
            != tuple(sorted((d.identity for d in dependencies), key=lambda v: v.uri))
            or len({d.component_revision for d in dependencies}) != len(dependencies)
            or any(
                d.component_revision == self.root_revision
                or d.target_profile_identity != self.target_profile_identity
                for d in dependencies
            )
        ):
            fail("NativeRootRunBinding", "run/deadline/held dependency records differ")


@dataclass(frozen=True, slots=True)
class NativeRootAcceptanceRejection(_ClosedValue):
    run_binding_identity: ContentIdentity
    candidate_ordinal: int
    component_revision: ContentIdentity
    bounded_generation_request_identity: ContentIdentity
    source_output_identity: ContentIdentity
    source_tree_identity: ContentIdentity
    workspace_allocation_identity: ContentIdentity
    node_lifecycle_result_identity: ContentIdentity
    build_plan_identity: ContentIdentity
    build_result_identity: ContentIdentity
    artifact_export_identity: ContentIdentity
    verifier_profile_identity: ContentIdentity
    oracle_identity: ContentIdentity
    native_execution_evidence_identity: ContentIdentity
    native_executable_identity: ContentIdentity
    tool_observation_identities: tuple[ContentIdentity, ...]
    target_profile_identity: ContentIdentity
    original_deadline_identity: ContentIdentity
    acceptance_scope: str
    packaged_binding: NativeRootPackageBinding | None
    decision: str
    public_code: str
    SCHEMA: ClassVar[str] = "literate-ai/native-root-acceptance-rejection@1"

    def __post_init__(self):
        self._check()
        _integer(self.candidate_ordinal, "candidate_ordinal", 0, 2)
        _ids(
            self.tool_observation_identities,
            "tool_observation_identities",
            canonical=True,
        )
        if not self.tool_observation_identities:
            fail(
                "NativeRootAcceptanceRejection", "native tool observations are required"
            )
        _choice(
            self.acceptance_scope, {"node-native-precheck", "packaged-root"}, "scope"
        )
        _choice(self.decision, {"result-values-differ"}, "decision")
        _choice(self.public_code, {NATIVE_ROOT_RESULT_MISMATCH}, "public_code")
        if (self.packaged_binding is not None) != (
            self.acceptance_scope == "packaged-root"
        ):
            fail(
                "NativeRootAcceptanceRejection", "package coordinates differ from scope"
            )

    def require_binding(self, run: NativeRootRunBinding) -> None:
        _check_type(NativeRootRunBinding, run, "run")
        if (
            self.run_binding_identity != run.identity
            or self.component_revision != run.root_revision
            or self.verifier_profile_identity != run.verifier_profile_identity
            or self.oracle_identity != run.oracle_identity
            or self.target_profile_identity != run.target_profile_identity
            or self.original_deadline_identity != run.original_deadline_identity
        ):
            fail("NativeRootAcceptanceRejection", "rejection names another run")


@dataclass(frozen=True, slots=True)
class NativeRootRepairDiagnostic(_ClosedValue):
    component_revision: ContentIdentity
    acceptance_rejection_identity: ContentIdentity
    code: str
    classification: str
    sanitized_text: str
    SCHEMA: ClassVar[str] = "literate-ai/native-root-repair-diagnostic@1"

    def __post_init__(self):
        self._check()
        _choice(self.code, {NATIVE_ROOT_RESULT_MISMATCH}, "code")
        _choice(self.classification, {"retryable"}, "classification")
        _choice(self.sanitized_text, {NATIVE_ROOT_REPAIR_MESSAGE}, "sanitized_text")

    def require_rejection(self, rejection: NativeRootAcceptanceRejection) -> None:
        _check_type(NativeRootAcceptanceRejection, rejection, "rejection")
        if (
            self.component_revision != rejection.component_revision
            or self.acceptance_rejection_identity != rejection.identity
        ):
            fail("NativeRootRepairDiagnostic", "diagnostic names another rejection")


@dataclass(frozen=True, slots=True)
class NativeRootRepairRequest(_ClosedValue):
    run_binding_identity: ContentIdentity
    candidate_ordinal: int
    original_recipe_identity: ContentIdentity
    predecessor_root_attempt_identities: tuple[ContentIdentity, ...]
    diagnostic_identity: ContentIdentity
    acceptance_rejection_identity: ContentIdentity | None
    bounded_generation_request_identity: ContentIdentity
    workspace_allocation_identity: ContentIdentity
    cause_kind: str
    failure_evidence_identity: ContentIdentity
    SCHEMA: ClassVar[str] = "literate-ai/native-root-repair-request@1"

    def __post_init__(self):
        self._check()
        _integer(self.candidate_ordinal, "candidate_ordinal", 1, 2)
        _ids(
            self.predecessor_root_attempt_identities,
            "predecessors",
            length=self.candidate_ordinal,
        )
        _choice(self.cause_kind, {"node-build-test", "native-acceptance"}, "cause_kind")
        if (self.acceptance_rejection_identity is not None) != (
            self.cause_kind == "native-acceptance"
        ):
            fail("NativeRootRepairRequest", "cause and rejection binding differ")
        if (
            self.cause_kind == "native-acceptance"
            and self.failure_evidence_identity != self.acceptance_rejection_identity
        ):
            fail("NativeRootRepairRequest", "native failure must be exact rejection")

    def require_records(self, run, predecessors, diagnostic, *, rejection=None) -> None:
        from .executable_components.candidate_repair import (
            CandidateFailureClassification,
            CandidateRepairDiagnostic,
        )
        from .standard_lifecycle_membership import StandardNodeFailurePhase

        _check_type(NativeRootRunBinding, run, "run")
        _run_prefix(predecessors, run)
        if self.cause_kind == "native-acceptance":
            _check_type(NativeRootRepairDiagnostic, diagnostic, "diagnostic")
        else:
            _check_type(CandidateRepairDiagnostic, diagnostic, "diagnostic")
        if (
            self.run_binding_identity != run.identity
            or self.original_recipe_identity != run.original_recipe_identity
            or self.predecessor_root_attempt_identities
            != tuple(p.identity for p in predecessors)
            or any(p.run_binding_identity != run.identity for p in predecessors)
            or not predecessors
            or predecessors[-1].retryability != "retryable"
            or self.diagnostic_identity != diagnostic.identity
            or self.bounded_generation_request_identity
            in {p.bounded_generation_request_identity for p in predecessors}
            or self.workspace_allocation_identity
            in {p.workspace_allocation_identity for p in predecessors}
        ):
            fail("NativeRootRepairRequest", "replacement differs from original prefix")
        last = predecessors[-1]
        if (
            self.failure_evidence_identity != last.failure_evidence_identity
            or self.diagnostic_identity != last.diagnostic_identity
        ):
            fail("NativeRootRepairRequest", "replacement does not bind last failure")
        if self.cause_kind == "native-acceptance":
            _check_type(NativeRootAcceptanceRejection, rejection, "rejection")
            rejection.require_binding(run)
            diagnostic.require_rejection(rejection)
            if (
                rejection.identity != self.acceptance_rejection_identity
                or rejection.candidate_ordinal != last.ordinal
                or rejection.source_output_identity != last.source_output_identity
                or rejection.bounded_generation_request_identity
                != last.bounded_generation_request_identity
                or rejection.workspace_allocation_identity
                != last.workspace_allocation_identity
                or rejection.node_lifecycle_result_identity
                != last.node_lifecycle_result_identity
                or rejection.packaged_binding != last.final_packaged_binding
                or last.outcome
                != (
                    "package-rejected"
                    if rejection.acceptance_scope == "packaged-root"
                    else "native-precheck-rejected"
                )
            ):
                fail(
                    "NativeRootRepairRequest",
                    "native rejection names another candidate",
                )
        else:
            if (
                rejection is not None
                or last.outcome != "node-rejected"
                or diagnostic.phase
                not in {StandardNodeFailurePhase.BUILD, StandardNodeFailurePhase.TEST}
                or diagnostic.classification
                is not CandidateFailureClassification.RETRYABLE
                or diagnostic.component_revision != run.root_revision
                or diagnostic.failure_evidence_identity
                != self.failure_evidence_identity
            ):
                fail(
                    "NativeRootRepairRequest",
                    "only genuine v2 build/test diagnostics fit",
                )


@dataclass(frozen=True, slots=True)
class NativeRootCandidateAttempt(_ClosedValue):
    run_binding_identity: ContentIdentity
    ordinal: int
    predecessor_root_attempt_identities: tuple[ContentIdentity, ...]
    incoming_request_kind: str
    incoming_request_identity: ContentIdentity | None
    bounded_generation_request_identity: ContentIdentity
    workspace_allocation_identity: ContentIdentity
    source_output_identity: ContentIdentity | None
    node_lifecycle_result_identity: ContentIdentity | None
    legacy_node_chain_identity: ContentIdentity | None
    legacy_node_attempt_index: int | None
    outcome: str
    failure_evidence_identity: ContentIdentity | None
    diagnostic_identity: ContentIdentity | None
    retryability: str
    actual_packaged_acceptance_identity: ContentIdentity | None
    final_packaged_binding: NativeRootPackageBinding | None
    SCHEMA: ClassVar[str] = "literate-ai/native-root-candidate-attempt@1"

    def __post_init__(self):
        self._check()
        _integer(self.ordinal, "ordinal", 0, 2)
        _ids(
            self.predecessor_root_attempt_identities,
            "predecessors",
            length=self.ordinal,
        )
        _choice(
            self.incoming_request_kind,
            {"initial", "legacy-node-repair", "native-root-repair"},
            "incoming_request_kind",
        )
        if (self.ordinal == 0) != (self.incoming_request_kind == "initial") or (
            self.incoming_request_identity is None
        ) != (self.ordinal == 0):
            fail("NativeRootCandidateAttempt", "incoming request differs from ordinal")
        if (self.legacy_node_chain_identity is None) != (
            self.legacy_node_attempt_index is None
        ):
            fail(
                "NativeRootCandidateAttempt",
                "legacy chain and index must occur together",
            )
        if self.legacy_node_attempt_index is not None:
            _integer(self.legacy_node_attempt_index, "legacy_node_attempt_index", 0, 2)
        _choice(
            self.outcome,
            {
                "node-rejected",
                "native-precheck-rejected",
                "package-rejected",
                "root-accepted",
                "root-terminal",
                "terminal-before-node",
            },
            "outcome",
        )
        _choice(self.retryability, {"none", "retryable", "terminal"}, "retryability")
        accepted = self.outcome == "root-accepted"
        if accepted:
            if (
                self.retryability != "none"
                or self.failure_evidence_identity is not None
                or self.diagnostic_identity is not None
                or self.actual_packaged_acceptance_identity is None
                or self.final_packaged_binding is None
            ):
                fail(
                    "NativeRootCandidateAttempt",
                    "acceptance needs exact final package evidence",
                )
        elif (
            self.retryability == "none"
            or self.failure_evidence_identity is None
            or self.actual_packaged_acceptance_identity is not None
            or (self.retryability == "retryable" and self.diagnostic_identity is None)
        ):
            fail(
                "NativeRootCandidateAttempt", "rejected attempt cannot claim acceptance"
            )
        if self.outcome == "root-terminal" and self.retryability != "terminal":
            fail(
                "NativeRootCandidateAttempt", "post-node root failure must be terminal"
            )
        if self.outcome == "terminal-before-node":
            if (
                self.retryability != "terminal"
                or self.source_output_identity is not None
                or self.node_lifecycle_result_identity is not None
                or self.legacy_node_chain_identity is not None
            ):
                fail(
                    "NativeRootCandidateAttempt",
                    "pre-node failure has no manufactured node",
                )
        elif (
            self.source_output_identity is None
            or self.node_lifecycle_result_identity is None
        ):
            fail("NativeRootCandidateAttempt", "completed node observation is required")
        if self.outcome != "root-terminal" and (
            (self.final_packaged_binding is not None)
            != (self.outcome in {"package-rejected", "root-accepted"})
        ):
            fail(
                "NativeRootCandidateAttempt", "package coordinates differ from outcome"
            )


def _attempt_prefix(attempts, run_binding_identity):
    _check_type(tuple[NativeRootCandidateAttempt, ...], attempts, "attempts")
    if len(attempts) > 3:
        fail("NativeRootContinuationLedger", "at most three candidates are permitted")
    for name in (
        "bounded_generation_request_identity",
        "workspace_allocation_identity",
    ):
        if len({getattr(a, name) for a in attempts}) != len(attempts):
            fail(
                "NativeRootContinuationLedger",
                "candidates must use fresh requests/workspaces",
            )
    for index, attempt in enumerate(attempts):
        if (
            attempt.run_binding_identity != run_binding_identity
            or attempt.ordinal != index
            or attempt.predecessor_root_attempt_identities
            != tuple(p.identity for p in attempts[:index])
            or (index < len(attempts) - 1 and attempt.retryability != "retryable")
        ):
            fail("NativeRootContinuationLedger", "candidate prefix is not exact")


def _run_prefix(attempts, run):
    _attempt_prefix(attempts, run.identity)
    if attempts and (
        attempts[0].bounded_generation_request_identity
        != run.original_bounded_request_identity
    ):
        fail(
            "NativeRootContinuationLedger", "initial candidate changed original request"
        )


@dataclass(frozen=True, slots=True)
class NativeRootContinuationStop(_ClosedValue):
    """A terminal boundary failure that did not allocate another candidate."""

    run_binding_identity: ContentIdentity
    before_candidate_ordinal: int
    last_attempt_identity: ContentIdentity | None
    failure_evidence_identity: ContentIdentity
    stage: str
    code: str
    SCHEMA: ClassVar[str] = "literate-ai/native-root-continuation-stop@1"

    def __post_init__(self):
        self._check()
        _integer(self.before_candidate_ordinal, "before_candidate_ordinal", 0, 3)
        if (self.last_attempt_identity is None) != (self.before_candidate_ordinal == 0):
            fail("NativeRootContinuationStop", "stop must name exact existing prefix")
        for name in ("stage", "code"):
            value = getattr(self, name)
            if not _CODE.fullmatch(value):
                fail(
                    f"NativeRootContinuationStop.{name}",
                    "must be a portable failure name",
                )

    def require_prefix(self, run_binding_identity, attempts) -> None:
        _check_type(ContentIdentity, run_binding_identity, "run_binding_identity")
        _attempt_prefix(attempts, run_binding_identity)
        if (
            self.run_binding_identity != run_binding_identity
            or self.before_candidate_ordinal != len(attempts)
            or self.last_attempt_identity
            != (attempts[-1].identity if attempts else None)
        ):
            fail("NativeRootContinuationStop", "stop changed or invented a candidate")


@dataclass(frozen=True, slots=True)
class NativeRootContinuationLedger(_ClosedValue):
    run_binding_identity: ContentIdentity
    attempts: tuple[NativeRootCandidateAttempt, ...]
    historical_legacy_node_chain_identities: tuple[ContentIdentity, ...]
    disposition: str
    terminal_stop_identity: ContentIdentity | None
    SCHEMA: ClassVar[str] = "literate-ai/native-root-continuation-ledger@1"

    def __post_init__(self):
        self._check()
        if len(self.attempts) > 3:
            fail(
                "NativeRootContinuationLedger", "one run owns at most three candidates"
            )
        _ids(
            self.historical_legacy_node_chain_identities,
            "historical chains",
            canonical=True,
        )
        _choice(
            self.disposition,
            {"pending", "accepted", "terminal", "exhausted"},
            "disposition",
        )
        _attempt_prefix(self.attempts, self.run_binding_identity)
        for name in (
            "bounded_generation_request_identity",
            "workspace_allocation_identity",
        ):
            if len({getattr(a, name) for a in self.attempts}) != len(self.attempts):
                fail(
                    "NativeRootContinuationLedger",
                    "candidates must use fresh requests/workspaces",
                )
        if set(self.historical_legacy_node_chain_identities) != {
            a.legacy_node_chain_identity
            for a in self.attempts
            if a.legacy_node_chain_identity is not None
        }:
            fail(
                "NativeRootContinuationLedger",
                "history must be exact referenced legacy chains",
            )
        last = self.attempts[-1] if self.attempts else None
        expected = (
            "terminal"
            if self.terminal_stop_identity is not None
            else "pending"
            if last is None
            else "accepted"
            if last.outcome == "root-accepted"
            else "terminal"
            if last.retryability == "terminal"
            else "exhausted"
            if len(self.attempts) == 3
            else "pending"
        )
        if self.disposition != expected:
            fail(
                "NativeRootContinuationLedger",
                "disposition differs from actual global budget",
            )

    @property
    def consumed_candidates(self) -> int:
        return len(self.attempts)

    def require_records(self, run, *, historical_chains=(), terminal_stop=None) -> None:
        from .executable_components.candidate_repair import (
            CandidateAttemptChain,
            CandidateAttemptDisposition,
        )
        from .standard_lifecycle_membership import StandardNodeFailurePhase

        _check_type(NativeRootRunBinding, run, "run")
        _run_prefix(self.attempts, run)
        _check_type(tuple[CandidateAttemptChain, ...], historical_chains, "history")
        if (
            self.run_binding_identity != run.identity
            or set(self.historical_legacy_node_chain_identities)
            != {c.identity for c in historical_chains}
            or len(historical_chains)
            != len(self.historical_legacy_node_chain_identities)
        ):
            fail(
                "NativeRootContinuationLedger",
                "run or actual historical records differ",
            )
        if self.terminal_stop_identity is None:
            if terminal_stop is not None:
                fail("NativeRootContinuationLedger", "unbound terminal stop")
        else:
            _check_type(NativeRootContinuationStop, terminal_stop, "terminal_stop")
            terminal_stop.require_prefix(self.run_binding_identity, self.attempts)
            if terminal_stop.identity != self.terminal_stop_identity:
                fail("NativeRootContinuationLedger", "stop identity differs")
        for chain in historical_chains:
            selected = [
                a
                for a in self.attempts
                if a.legacy_node_chain_identity == chain.identity
            ]
            if chain.component_revision != run.root_revision or sorted(
                a.legacy_node_attempt_index for a in selected
            ) != list(range(len(chain.attempts))):
                fail(
                    "NativeRootContinuationLedger",
                    "legacy history hid or repeated candidates",
                )
            for attempt in selected:
                legacy = chain.attempts[attempt.legacy_node_attempt_index]
                if (
                    legacy.generation_request_identity
                    != attempt.bounded_generation_request_identity
                    or legacy.workspace_allocation_identity
                    != attempt.workspace_allocation_identity
                    or legacy.generation_response_identity
                    != attempt.source_output_identity
                    or legacy.lifecycle_result_identity
                    != attempt.node_lifecycle_result_identity
                ):
                    fail(
                        "NativeRootContinuationLedger",
                        "legacy observation was rewritten",
                    )
                if legacy.disposition is CandidateAttemptDisposition.ACCEPTED:
                    if attempt.outcome in {"node-rejected", "terminal-before-node"}:
                        fail(
                            "NativeRootContinuationLedger",
                            "accepted node history was relabelled",
                        )
                elif (
                    attempt.outcome != "node-rejected"
                    or legacy.diagnostic.phase
                    not in {
                        StandardNodeFailurePhase.BUILD,
                        StandardNodeFailurePhase.TEST,
                    }
                    or attempt.diagnostic_identity != legacy.diagnostic.identity
                    or attempt.failure_evidence_identity
                    != legacy.diagnostic.failure_evidence_identity
                    or attempt.retryability != legacy.diagnostic.classification.value
                ):
                    fail(
                        "NativeRootContinuationLedger",
                        "legacy rejection history differs",
                    )
                if attempt.incoming_request_kind == "legacy-node-repair" and (
                    legacy.repair_request is None
                    or attempt.incoming_request_identity
                    != legacy.repair_request.identity
                ):
                    fail(
                        "NativeRootContinuationLedger", "legacy repair request differs"
                    )


@dataclass(frozen=True, slots=True)
class NativeRootAcceptanceClosure(_ClosedValue):
    run_binding_identity: ContentIdentity
    ledger_identity: ContentIdentity
    actual_independent_acceptance_identity: ContentIdentity
    final_source_output_identity: ContentIdentity
    package_plan_identity: ContentIdentity
    package_result_identity: ContentIdentity
    SCHEMA: ClassVar[str] = "literate-ai/native-root-acceptance-closure@1"

    def __post_init__(self):
        self._check()

    def require_records(self, run, ledger) -> None:
        _check_type(NativeRootRunBinding, run, "run")
        _check_type(NativeRootContinuationLedger, ledger, "ledger")
        _run_prefix(ledger.attempts, run)
        if ledger.disposition != "accepted":
            fail("NativeRootAcceptanceClosure", "only accepted root ledger can close")
        last = ledger.attempts[-1]
        package = last.final_packaged_binding
        if (
            self.run_binding_identity != run.identity
            or ledger.run_binding_identity != run.identity
            or self.ledger_identity != ledger.identity
            or self.actual_independent_acceptance_identity
            != last.actual_packaged_acceptance_identity
            or self.final_source_output_identity != last.source_output_identity
            or self.package_plan_identity != package.package_plan_identity
            or self.package_result_identity != package.package_result_identity
        ):
            fail(
                "NativeRootAcceptanceClosure",
                "closure differs from final actual candidate",
            )


@dataclass(frozen=True, slots=True)
class NativeRootExecutionResult(_ClosedValue):
    run_binding_identity: ContentIdentity
    ledger_identity: ContentIdentity
    final_lifecycle_result_identity: ContentIdentity
    acceptance_closure_identity: ContentIdentity | None
    status: str
    SCHEMA: ClassVar[str] = "literate-ai/native-root-execution-result@1"

    def __post_init__(self):
        self._check()
        _choice(self.status, {"accepted", "terminal", "exhausted"}, "status")
        if (self.acceptance_closure_identity is not None) != (
            self.status == "accepted"
        ):
            fail(
                "NativeRootExecutionResult", "only success binds an acceptance closure"
            )

    def require_records(self, run, ledger, *, closure=None) -> None:
        _check_type(NativeRootRunBinding, run, "run")
        _check_type(NativeRootContinuationLedger, ledger, "ledger")
        _run_prefix(ledger.attempts, run)
        if (
            self.run_binding_identity != run.identity
            or ledger.run_binding_identity != run.identity
            or self.ledger_identity != ledger.identity
            or self.status != ledger.disposition
        ):
            fail("NativeRootExecutionResult", "result differs from exact root ledger")
        if self.status == "accepted":
            _check_type(NativeRootAcceptanceClosure, closure, "closure")
            closure.require_records(run, ledger)
            if self.acceptance_closure_identity != closure.identity:
                fail("NativeRootExecutionResult", "acceptance closure identity differs")
        elif closure is not None:
            fail("NativeRootExecutionResult", "failed result cannot claim acceptance")
