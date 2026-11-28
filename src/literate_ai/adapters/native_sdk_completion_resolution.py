"""Portable resolution evidence collected from a completed SDK source build."""

from literate_ai.adapters.native_sdk_recipes import _selected_sdk_build_plan
from literate_ai.application.repository_sources import (
    RepositoryBuildApproval,
    RepositoryBuildVerification,
    RepositorySourceIndexBinding,
    RepositorySourceResolution,
    RepositorySourceResolver,
)
from literate_ai.contracts import (
    ContentIdentity,
    RepositoryBuildOutput,
    RepositoryBuildPlan,
    RepositorySourceAdmission,
    RepositorySourceLock,
)
from literate_ai.contracts._validation import (
    bool_value,
    contract_fields,
    fields,
    parse_tuple,
    string_tuple,
)


def resolution_document(resolution: RepositorySourceResolution) -> dict[str, object]:
    """Preserve the actual build decision and observations for independent checking."""
    approval = resolution.build_approval
    verification = resolution.build_verification
    return {
        "lock": resolution.lock.to_dict(),
        "index_binding": resolution.index_binding.to_dict(),
        "build_plan": resolution.build_plan.to_dict(),
        "approval": {
            "source_lock": approval.source_lock.to_dict(),
            "build_plan": approval.build_plan.to_dict(),
            "classification": approval.classification.to_dict(),
            "authorization": approval.authorization.to_dict(),
        },
        "verification": {
            "source_lock": verification.source_lock.to_dict(),
            "build_plan": verification.build_plan.to_dict(),
            "build_approval": verification.build_approval.to_dict(),
            "build_result": verification.build_result.to_dict(),
            "expected_outputs": list(verification.expected_outputs),
            "build_outputs": [item.to_dict() for item in verification.build_outputs],
            "passed": verification.passed,
        },
        "admission": resolution.admission.to_dict(),
        "cache_record": resolution.cache_record.to_dict(),
    }


def require_resolution_relationships(
    resolution: RepositorySourceResolution,
    *,
    selection,
    toolchains,
) -> None:
    """Check recorded relationships against independently selected current inputs."""
    lock = resolution.lock
    if lock != selection.source_lock:
        raise ValueError("SDK completion describes a different repository lock")
    binding = resolution.index_binding
    plan = resolution.build_plan
    approval = resolution.build_approval
    verification = resolution.build_verification
    RepositorySourceResolver._require_index_binding(lock, binding)
    if plan != _selected_sdk_build_plan(selection, binding.identity, toolchains):
        raise ValueError("SDK completion plan differs from the current authored recipe")
    RepositorySourceResolver._require_approval(lock, plan, approval)
    RepositorySourceResolver._require_verification(lock, plan, approval, verification)
    expected_admission = RepositorySourceAdmission.create(
        dependency_id=lock.dependency.dependency_id,
        source_lock=lock.identity,
        source_snapshot=lock.source_snapshot,
        source_tree=lock.source_tree,
        effective_revision=selection.component_revision,
        flavor_set=selection.target_identity,
        index_binding=binding.identity,
        build_plan=plan.identity,
        classification=approval.classification,
        authorization=approval.authorization,
        build_result=verification.build_result,
        expected_outputs=plan.expected_outputs,
        build_outputs=verification.build_outputs,
    )
    if resolution.admission != expected_admission:
        raise ValueError("SDK completion admission differs from verified build records")


def decode_resolution(value: object) -> RepositorySourceResolution:
    """Decode portable evidence before checking it against current authority."""
    row = fields(
        value,
        path="resolution",
        required=frozenset(
            {
                "lock",
                "index_binding",
                "build_plan",
                "approval",
                "verification",
                "admission",
                "cache_record",
            }
        ),
    )
    index_fields = ("source_snapshot", "source_tree", "provider", "index")
    index = contract_fields(
        row["index_binding"],
        path="resolution.index_binding",
        schema_uri="urn:literate-ai:schema:v1:repository-source-index-binding",
        required=frozenset(index_fields),
    )
    approval_fields = ("source_lock", "build_plan", "classification", "authorization")
    approval = fields(
        row["approval"], path="resolution.approval", required=frozenset(approval_fields)
    )
    verification_fields = (
        "source_lock",
        "build_plan",
        "build_approval",
        "build_result",
    )
    verification = fields(
        row["verification"],
        path="resolution.verification",
        required=frozenset(
            (*verification_fields, "expected_outputs", "build_outputs", "passed")
        ),
    )
    return RepositorySourceResolution(
        lock=RepositorySourceLock.from_dict(row["lock"]),
        index_binding=RepositorySourceIndexBinding(
            **{key: ContentIdentity.from_dict(index[key]) for key in index_fields}
        ),
        build_plan=RepositoryBuildPlan.from_dict(row["build_plan"]),
        build_approval=RepositoryBuildApproval(
            **{key: ContentIdentity.from_dict(approval[key]) for key in approval_fields}
        ),
        build_verification=RepositoryBuildVerification(
            **{
                key: ContentIdentity.from_dict(verification[key])
                for key in verification_fields
            },
            expected_outputs=string_tuple(
                verification["expected_outputs"], "verification.expected_outputs"
            ),
            build_outputs=parse_tuple(
                verification["build_outputs"],
                "verification.build_outputs",
                RepositoryBuildOutput.from_dict,
            ),
            passed=bool_value(verification["passed"], "verification.passed"),
        ),
        admission=RepositorySourceAdmission.from_dict(row["admission"]),
        cache_record=ContentIdentity.from_dict(row["cache_record"]),
    )
