"""Bounded closed native-root binding checks, never acceptance or live authority.

The caller must first select policy and authority independently of the archive,
and reopen the original lifecycle/root/node/source using the existing strict
verifiers. This helper checks their continuation joins. It does NOT validate
historical source trees, allocations, native executable/tool custody, private
oracle cases or native value-mismatch semantics. Those checks remain mandatory
before acceptance; a returned audit is only closed correlation data.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, fields

from literate_ai.contracts.executable_components.candidate_repair import (
    CandidateAttemptChain,
    CandidateRepairDiagnostic,
    CandidateRepairRequest,
)
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceClosure,
    NativeRootAcceptanceRejection,
    NativeRootCandidateAttempt,
    NativeRootContinuationLedger,
    NativeRootContinuationStop,
    NativeRootExecutionResult,
    NativeRootPackageBinding,
    NativeRootQualifiedDependencyBinding,
    NativeRootRepairDiagnostic,
    NativeRootRepairRequest,
    NativeRootRunBinding,
    NativeRootRunDeadline,
    NativeRootRunPolicy,
)
from literate_ai.contracts.standard_root_integration import (
    StandardRootIntegrationEvidence,
)


class NativeRootReplayError(ValueError):
    """A required closed continuation record or join is absent or inconsistent."""


@dataclass(frozen=True, slots=True)
class NativeRootReplayAuthority:
    """Caller-derived expectations; never populate these from archive assertions."""

    project_definition_identity: ContentIdentity
    project_authority_identity: ContentIdentity
    framework_distribution_identity: ContentIdentity
    lifecycle_policy_identity: ContentIdentity
    component_lock_identity: ContentIdentity
    root_revision: ContentIdentity
    original_recipe_identity: ContentIdentity
    original_generation_plan_identity: ContentIdentity
    original_bounded_request_identity: ContentIdentity
    execution_plan_identity: ContentIdentity
    target_profile_identity: ContentIdentity
    oracle_identity: ContentIdentity
    verifier_profile_identity: ContentIdentity

    def __post_init__(self):
        for field in fields(self):
            identity = getattr(self, field.name)
            if type(identity) is not ContentIdentity:
                raise TypeError(
                    "trusted replay expectations require ContentIdentity values"
                )
            identity.__post_init__()


@dataclass(frozen=True, slots=True)
class NativeRootReplaySubject:
    """Coordinates from the caller's already strictly reopened original subject."""

    lifecycle_identity: ContentIdentity
    root_integration: StandardRootIntegrationEvidence
    final_node_identity: ContentIdentity
    final_source_output_identity: ContentIdentity

    def __post_init__(self):
        if type(self.root_integration) is not StandardRootIntegrationEvidence:
            raise TypeError("the original reopened root integration is required")
        self.root_integration.__post_init__()
        for name in (
            "lifecycle_identity",
            "final_node_identity",
            "final_source_output_identity",
        ):
            value = getattr(self, name)
            if type(value) is not ContentIdentity:
                raise TypeError(
                    "original replay coordinates require ContentIdentity values"
                )
            value.__post_init__()


@dataclass(frozen=True, slots=True)
class NativeRootReplayLimits:
    maximum_records: int = 64
    maximum_record_bytes: int = 16 * 1024**2
    maximum_total_bytes: int = 64 * 1024**2

    def __post_init__(self):
        for name, ceiling in (
            ("maximum_records", 4096),
            ("maximum_record_bytes", 256 * 1024**2),
            ("maximum_total_bytes", 1024**3),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError("closed replay limits must be finite bounded integers")
        if self.maximum_record_bytes > self.maximum_total_bytes:
            raise ValueError("record limit exceeds aggregate replay limit")


def _require(condition, label):
    if not condition:
        raise NativeRootReplayError("native_root_replay." + label)


class _Records:
    def __init__(self, read, limits):
        self.read = read
        self.limits = limits
        self.count = self.size = 0

    def json(self, identity):
        _require(type(identity) is ContentIdentity, "identity_invalid")
        self.count += 1
        _require(self.count <= self.limits.maximum_records, "records_exceeded")
        # The caller's reader must bound acquisition itself. These limits also
        # bound parsing and aggregate material retained by this helper.
        payload = self.read(identity)
        _require(type(payload) is bytes, "bytes_required")
        self.size += len(payload)
        _require(
            len(payload) <= self.limits.maximum_record_bytes
            and self.size <= self.limits.maximum_total_bytes,
            "bytes_exceeded",
        )
        value = json.loads(payload)
        _require(type(value) is dict, "object_required")
        _require(canonical_json_bytes(value) == payload, "noncanonical_record")
        _require(canonical_identity(value) == identity, "record_identity_changed")
        return value

    def typed(self, identity, kind):
        record = kind.from_dict(self.json(identity))
        _require(record.identity == identity, "typed_identity_changed")
        return record


def verify_closed_native_root_bindings(
    *,
    read_record: Callable[[ContentIdentity], bytes],
    selected_policy: NativeRootRunPolicy,
    authority: NativeRootReplayAuthority,
    subject: NativeRootReplaySubject,
    qualified_dependencies: tuple[NativeRootQualifiedDependencyBinding, ...],
    limits: NativeRootReplayLimits | None = None,
    publication_projection=None,
) -> NativeRootExecutionResult:
    """Require the closure selected by trusted policy; do not infer opt-in.

    No scanning or optional-record fallback occurs. Dependency rows must equal
    the caller's independently trusted set; reopening them proves no qualification.
    Legacy v2 verification is unchanged and remains the caller's responsibility.
    """
    if limits is None:
        limits = NativeRootReplayLimits()
    if (
        type(selected_policy) is not NativeRootRunPolicy
        or type(authority) is not NativeRootReplayAuthority
        or type(subject) is not NativeRootReplaySubject
        or type(limits) is not NativeRootReplayLimits
        or not callable(read_record)
    ):
        raise TypeError(
            "explicit trusted policy, authority, subject and bounded reader required"
        )
    selected_policy.__post_init__()
    authority.__post_init__()
    subject.__post_init__()
    limits.__post_init__()
    if type(qualified_dependencies) is not tuple or any(
        type(item) is not NativeRootQualifiedDependencyBinding
        for item in qualified_dependencies
    ):
        raise TypeError("explicit trusted qualified dependency bindings required")
    records = _Records(read_record, limits)
    root = subject.root_integration
    _require(
        records.typed(root.identity, StandardRootIntegrationEvidence) == root,
        "root_changed",
    )
    closure = records.typed(
        root.independent_acceptance_identity, NativeRootAcceptanceClosure
    )
    run = records.typed(closure.run_binding_identity, NativeRootRunBinding)
    for field in fields(authority):
        _require(
            getattr(run, field.name) == getattr(authority, field.name),
            "authority_changed",
        )
    policy = records.typed(selected_policy.identity, NativeRootRunPolicy)
    _require(policy == selected_policy, "policy_changed")
    deadline = records.typed(run.original_deadline_identity, NativeRootRunDeadline)
    dependencies = tuple(
        records.typed(identity, NativeRootQualifiedDependencyBinding)
        for identity in run.qualified_dependency_binding_identities
    )
    expected_dependencies = tuple(
        sorted(qualified_dependencies, key=lambda item: item.identity.uri)
    )
    _require(dependencies == expected_dependencies, "dependencies_changed")
    run.require_records(
        policy,
        deadline,
        dependencies,
        project_definition_identity=authority.project_definition_identity,
        project_authority_identity=authority.project_authority_identity,
    )
    ledger = records.typed(closure.ledger_identity, NativeRootContinuationLedger)
    chains = tuple(
        records.typed(identity, CandidateAttemptChain)
        for identity in ledger.historical_legacy_node_chain_identities
    )
    stop = (
        None
        if ledger.terminal_stop_identity is None
        else records.typed(ledger.terminal_stop_identity, NativeRootContinuationStop)
    )
    ledger.require_records(run, historical_chains=chains, terminal_stop=stop)
    closure.require_records(run, ledger)
    for attempt in ledger.attempts:
        _require(
            records.typed(attempt.identity, NativeRootCandidateAttempt) == attempt,
            "attempt_changed",
        )
        if attempt.incoming_request_kind == "native-root-repair":
            request = records.typed(
                attempt.incoming_request_identity, NativeRootRepairRequest
            )
            diagnostic_type = (
                NativeRootRepairDiagnostic
                if request.cause_kind == "native-acceptance"
                else CandidateRepairDiagnostic
            )
            diagnostic = records.typed(request.diagnostic_identity, diagnostic_type)
            rejection = (
                None
                if request.acceptance_rejection_identity is None
                else records.typed(
                    request.acceptance_rejection_identity, NativeRootAcceptanceRejection
                )
            )
            request.require_records(
                run, ledger.attempts[: attempt.ordinal], diagnostic, rejection=rejection
            )
            _require(
                request.candidate_ordinal == attempt.ordinal
                and request.bounded_generation_request_identity
                == attempt.bounded_generation_request_identity
                and request.workspace_allocation_identity
                == attempt.workspace_allocation_identity,
                "repair_allocation_changed",
            )
        elif attempt.incoming_request_kind == "legacy-node-repair":
            request = records.typed(
                attempt.incoming_request_identity, CandidateRepairRequest
            )
            _require(
                request.original_recipe_identity == authority.original_recipe_identity,
                "legacy_recipe_changed",
            )
            # ledger.require_records joins the exact embedded legacy request.
            _require(
                any(
                    entry.repair_request == request
                    for chain in chains
                    for entry in chain.attempts
                    if entry.generation_request_identity
                    == attempt.bounded_generation_request_identity
                ),
                "legacy_request_changed",
            )
    final = ledger.attempts[-1]
    package = NativeRootPackageBinding(
        root.artifact_graph.identity,
        root.link_plan.identity,
        root.package_plan.identity,
        root.package_result.identity,
        root.root_generated_integration_test_identity,
        root.packaged_execution_identity,
    )
    _require(final.final_packaged_binding == package, "final_package_changed")
    ledger_node_identity = subject.final_node_identity
    if publication_projection is not None:
        from .native_root_publication_projection import (
            recheck_native_root_publication_projection,
        )

        recheck_native_root_publication_projection(
            read_json=records.json,
            projection=publication_projection,
            lifecycle_identity=subject.lifecycle_identity,
            published_node_identity=subject.final_node_identity,
            prepublication_node_identity=final.node_lifecycle_result_identity,
            source_output_identity=subject.final_source_output_identity,
        )
        ledger_node_identity = publication_projection.prepublication_node_identity
    _require(
        root.component_lock_identity == authority.component_lock_identity
        and root.execution_plan_identity == authority.execution_plan_identity
        and root.package_plan.root_component_revision == authority.root_revision
        and root.package_plan.target_identity == authority.target_profile_identity
        and final.node_lifecycle_result_identity == ledger_node_identity
        and final.source_output_identity == subject.final_source_output_identity,
        "final_subject_changed",
    )
    lifecycle = records.json(subject.lifecycle_identity)
    _require(
        lifecycle.get("schema") == "literate-ai/standard-project-lifecycle-result@4"
        and lifecycle.get("root_integration_evidence_identity") == root.identity.uri
        and lifecycle.get("execution_plan_identity")
        == authority.execution_plan_identity.uri
        and type(lifecycle.get("node_results")) is list
        and lifecycle["node_results"].count(subject.final_node_identity.uri) == 1,
        "lifecycle_changed",
    )
    node = records.json(ledger_node_identity)
    source = records.json(subject.final_source_output_identity)
    _require(
        node.get("schema") == "literate-ai/standard-node-lifecycle-result@4"
        and node.get("component_revision") == authority.root_revision.uri
        and node.get("failure_code") is None
        and node.get("source_output") == source,
        "final_node_changed",
    )
    audit = NativeRootExecutionResult(
        run.identity,
        ledger.identity,
        subject.lifecycle_identity,
        closure.identity,
        "accepted",
    )
    audit.require_records(run, ledger, closure=closure)
    _require(
        records.typed(audit.identity, NativeRootExecutionResult) == audit,
        "audit_changed",
    )
    return audit
