"""Exact post-publication metadata projection; never a replay/acceptance grant.

Only current-qualified-result-anchored Standard publication attestations are
used. No actual persisted cache-entry bytes are claimed or required here. The
caller must already pass current Standard execution verification for this run.
No ledger, closure, positive root, audit or lifecycle identity is rewritten.
"""

from dataclasses import dataclass, fields

from literate_ai.contracts.identity import ContentIdentity, canonical_identity


class NativeRootPublicationProjectionError(ValueError):
    """An exact original publication projection or attestation is missing."""


def _require(condition, label):
    if not condition:
        raise NativeRootPublicationProjectionError("native_root_publication." + label)


@dataclass(frozen=True, slots=True)
class NativeRootPublicationProjection:
    """Comparison coordinates only; construction authenticates no provenance."""

    qualification_result_identity: ContentIdentity
    qualification_run_identity: ContentIdentity
    lifecycle_identity: ContentIdentity
    published_node_identity: ContentIdentity
    prepublication_node_identity: ContentIdentity
    source_output_identity: ContentIdentity
    publication_identity: ContentIdentity

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if type(value) is not ContentIdentity:
                raise TypeError("exact publication projection identities required")
            value.__post_init__()


def recheck_native_root_publication_projection(
    *,
    read_json,
    projection,
    lifecycle_identity,
    published_node_identity,
    prepublication_node_identity,
    source_output_identity,
):
    """Independently recheck complete records on the core's bounded reader.

    A caller-provided pair of IDs or Boolean never bypasses the exact canonical
    known-field transformation and current-qualified membership attestations.
    """
    from literate_ai.adapters.qualification_capture import _decode_qualification_node
    from literate_ai.application.standard_project_lifecycle import (
        StandardAcceptedSourcePublication,
    )
    from literate_ai.contracts.executable_components import SourceGenerationDisposition
    from literate_ai.contracts.standard_lifecycle_membership import (
        StandardAggregateReceipt,
        StandardNodeCacheOutcome,
        StandardProjectLifecycleMembership,
    )
    from literate_ai.contracts.testing import ProjectTestReceipt
    from literate_ai.source_to_specification.qualification_lifecycle import (
        QualificationLifecycleResult,
    )

    if type(projection) is not NativeRootPublicationProjection or not callable(
        read_json
    ):
        raise TypeError(
            "explicit exact publication projection and bounded reader required"
        )
    projection.__post_init__()
    _require(
        (
            projection.lifecycle_identity,
            projection.published_node_identity,
            projection.prepublication_node_identity,
            projection.source_output_identity,
        )
        == (
            lifecycle_identity,
            published_node_identity,
            prepublication_node_identity,
            source_output_identity,
        ),
        "subject_changed",
    )

    def document(identity):
        value = read_json(identity)
        _require(
            type(value) is dict and canonical_identity(value) == identity,
            "document_changed",
        )
        return value

    def read(reference, decode):
        if reference is None:
            return None
        identity = ContentIdentity.parse_uri(reference)
        value = decode(document(identity))
        _require(value.identity == identity, "typed_document_changed")
        return value

    result = read(
        projection.qualification_result_identity.uri,
        QualificationLifecycleResult.from_dict,
    )
    members = tuple(
        member
        for member in result.runs
        if member.run_identity == projection.qualification_run_identity
    )
    _require(
        len(members) == 1
        and members[0].lifecycle_result_identity == lifecycle_identity,
        "qualification_membership_changed",
    )
    member = members[0]
    lifecycle = document(lifecycle_identity)
    _require(
        lifecycle.get("schema") == "literate-ai/standard-project-lifecycle-result@4"
        and type(lifecycle.get("node_results")) is list
        and lifecycle["node_results"].count(published_node_identity.uri) == 1,
        "lifecycle_changed",
    )
    final = document(published_node_identity)
    before = document(prepublication_node_identity)
    _require(
        final.get("schema") == "literate-ai/standard-node-lifecycle-result@4"
        and before.get("schema") == final["schema"]
        and "source_cache_publication_identity" in final
        and before.get("source_cache_publication_identity", "missing") is None
        and final["source_cache_publication_identity"]
        == projection.publication_identity.uri
        and {**final, "source_cache_publication_identity": None} == before
        and canonical_identity({**final, "source_cache_publication_identity": None})
        == prepublication_node_identity,
        "node_projection_changed",
    )
    final_node = _decode_qualification_node(final, read=read)
    before_node = _decode_qualification_node(before, read=read)
    _require(
        final_node.source_output is not None
        and final_node.source_output.identity == source_output_identity
        and final_node.source_generation.disposition
        is SourceGenerationDisposition.GENERATED
        and final_node.source_output.provenance.retained_source_identity is None
        and before_node.source_output == final_node.source_output
        and final_node.source_cache_membership is not None
        and final_node.source_cache_publication_identity
        == final_node.source_cache_membership.identity
        == projection.publication_identity,
        "publication_changed",
    )
    nodes = tuple(
        _decode_qualification_node(
            document(ContentIdentity.parse_uri(identity)), read=read
        )
        for identity in lifecycle["node_results"]
    )
    membership = read(
        lifecycle["lifecycle_membership_identity"],
        StandardProjectLifecycleMembership.from_dict,
    )
    aggregate = read(
        lifecycle["aggregate_receipt_identity"], StandardAggregateReceipt.from_dict
    )
    receipt = read(member.project_receipt_identity.uri, ProjectTestReceipt.from_dict)
    _require(
        membership.execution_plan_identity.uri == lifecycle["execution_plan_identity"]
        and tuple(node.identity for node in nodes)
        == membership.lifecycle_result_identities
        and tuple(aggregate.lifecycle_result_identities)
        == membership.lifecycle_result_identities
        and aggregate.lifecycle_membership_identity == membership.identity
        and aggregate.execution_plan_identity == membership.execution_plan_identity
        and aggregate.identity.uri == lifecycle["receipt_identity"]
        and aggregate.admission_identity.uri == lifecycle["admission_identity"]
        and [value.uri for value in aggregate.context_prompt_journal_identities]
        == lifecycle["context_prompt_journal_identities"]
        and [value.uri for value in aggregate.context_benchmark_record_identities]
        == lifecycle["context_benchmark_record_identities"]
        and aggregate.context_cache_report_identity.uri
        == lifecycle["context_cache_report_identity"]
        and aggregate.root_integration_evidence_identity.uri
        == lifecycle["root_integration_evidence_identity"]
        and receipt.result_identity == lifecycle_identity
        and receipt.subject_identity == aggregate.identity,
        "aggregate_changed",
    )
    for node, decision in zip(nodes, membership.cache_decisions, strict=True):
        _require(
            node.source_generation.disposition is SourceGenerationDisposition.GENERATED
            and node.source_output.provenance.retained_source_identity is None,
            "fresh_qualification_required",
        )
        publication = StandardAcceptedSourcePublication(
            node.component_revision,
            node.build_plan_identity,
            node.source_output,
            node.exports,
            node.index_identity,
            node.authorization_identity,
            node.source_cache_membership,
            node.build_evidence,
            node.generated_test_evidence,
            node.execution_evidence,
            node.acceptance_evidence,
        )
        _require(
            decision.component_revision == node.component_revision
            and decision.generation_plan_identity
            == node.source_generation.generation_plan_identity
            and decision.generation_key_identity
            == node.source_generation.generation_key_identity
            and decision.lifecycle_result_identity == node.identity
            and decision.outcome
            in {
                StandardNodeCacheOutcome.MISS,
                StandardNodeCacheOutcome.FORCED_REGENERATION,
            }
            and decision.input_membership_identity is None
            and decision.failure_identity is None
            and decision.publication_identity
            == decision.accepted_membership_identity
            == publication.membership.identity
            == node.source_cache_publication_identity,
            "cache_decision_changed",
        )

    def ordered(values):
        return tuple(sorted(values, key=lambda value: value.uri))

    _require(
        member.cache_decision_identities
        == ordered(row.identity for row in membership.cache_decisions)
        and member.source_tree_identities
        == ordered(node.source_output.candidate.tree_identity for node in nodes)
        and member.source_index_identities
        == ordered(node.index_identity for node in nodes)
        and member.build_evidence_identities
        == ordered(node.build_evidence.identity for node in nodes)
        and member.generated_test_evidence_identities
        == ordered(node.generated_test_evidence.identity for node in nodes)
        and member.resolved_sbom_identities
        == ordered(node.build_evidence.resolved_sbom.bom_identity for node in nodes)
        and member.generated_test_suite_identities
        == ordered(
            node.generated_test_evidence.generated_test_suite_identity for node in nodes
        )
        and member.generated_test_case_identities
        == ordered(
            {
                case.case_identity
                for node in nodes
                for case in node.generated_test_evidence.cases
            }
        )
        and member.generated_test_total
        == sum(node.generated_test_evidence.executed_count for node in nodes)
        == receipt.summary.total
        and member.acceptance_evidence_identities
        == ordered(node.acceptance_evidence.identity for node in nodes)
        and member.node_workspace_identities
        == ordered(
            node.source_output.candidate.workspace_allocation_identity for node in nodes
        ),
        "source_receipt_membership_changed",
    )


def verify_native_root_publication_projection(
    reader,
    *,
    expected_qualification_result,
    member,
    lifecycle,
    prepublication_node_identity,
):
    """Build comparison data after current Standard execution verification.

    `expected_qualification_result` is the independently current promotion value;
    it must not be selected from the candidate archive. Its bytes are required at
    its exact CID. Returning this value grants no acceptance or live authority.
    """
    from literate_ai.adapters.qualification_capture import QualificationEvidenceReader
    from literate_ai.application.standard_project_lifecycle import (
        StandardProjectLifecycleResult,
    )
    from literate_ai.source_to_specification.qualification_lifecycle import (
        QualificationLifecycleResult,
    )

    if (
        not isinstance(reader, QualificationEvidenceReader)
        or type(expected_qualification_result) is not QualificationLifecycleResult
        or type(lifecycle) is not StandardProjectLifecycleResult
    ):
        raise TypeError("current qualification and bounded original reader required")
    _require(
        reader.read_json(expected_qualification_result.identity)
        == expected_qualification_result.to_dict()
        and sum(run == member for run in expected_qualification_result.runs) == 1
        and member.lifecycle_result_identity == lifecycle.identity,
        "current_qualification_changed",
    )
    _require(lifecycle.root_integration is not None, "final_root_missing")
    nodes = tuple(
        node
        for node in lifecycle.node_results
        if node.component_revision
        == lifecycle.root_integration.package_plan.root_component_revision
    )
    _require(
        len(nodes) == 1 and nodes[0].source_output is not None, "final_node_missing"
    )
    node = nodes[0]
    projection = NativeRootPublicationProjection(
        expected_qualification_result.identity,
        member.run_identity,
        lifecycle.identity,
        node.identity,
        prepublication_node_identity,
        node.source_output.identity,
        node.source_cache_publication_identity,
    )
    recheck_native_root_publication_projection(
        read_json=reader.read_json,
        projection=projection,
        lifecycle_identity=lifecycle.identity,
        published_node_identity=node.identity,
        prepublication_node_identity=prepublication_node_identity,
        source_output_identity=node.source_output.identity,
    )
    return projection
