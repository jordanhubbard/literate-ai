"""Original current source-provider joins, independent of receiving language.

The caller owns current generation/native/consumer custody; no archive opts in.
"""

from literate_ai.application.source_promotion import (
    verify_qualified_locked_source_promotion,
)


def verify_current_retained_source_provider(
    binding,
    authority,
    promotion,
    *,
    current_generation_closure,
    current_verifier_identity,
    current_policy_identity,
):
    """Shared current native provider checks, never a binding/plan codec."""
    projection = verify_qualified_locked_source_promotion(
        authority,
        promotion,
        current_generation_closure=current_generation_closure,
        current_verifier_identity=current_verifier_identity,
        current_policy_identity=current_policy_identity,
    )
    if (
        binding.qualification_identity
        != current_generation_closure.qualification_evidence_identity
        or binding.verifier_identity != current_verifier_identity
        or binding.policy_identity != current_policy_identity
    ):
        raise ValueError("retained.cargo.provider-authority-mismatch")
    qualification = promotion.qualification_lifecycle_result
    if qualification is None or not any(
        r.run_identity == binding.run_identity for r in qualification.runs
    ):
        raise ValueError("retained.cargo.provider-run-mismatch")
    roots = set(binding.exports.link_plan.resolved_root_artifact_identities)
    if any(
        p.artifact_export.component_revision != projection.component_revision_identity
        for p in binding.exports.libraries
        if p.artifact_export.identity in roots
    ):
        raise ValueError("retained.cargo.provider-revision-mismatch")
