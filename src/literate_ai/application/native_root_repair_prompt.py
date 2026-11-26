"""Exact public root-repair rendering shared by runtime and closed verification.

This is pure data transformation, never proof that a diagnostic/rejection permits
another candidate. Callers must validate original authority, full predecessor
lineage and the actual failure before rendering. No owner or workspace is opened.
Ordinary v2 candidate repair keeps its separate unchanged renderer.
"""

import hashlib
from dataclasses import replace

from literate_ai.application.component_generation_context import (
    PreparedComponentGenerationRequest,
)
from literate_ai.contracts.executable_components import CandidateRepairDiagnostic
from literate_ai.contracts.executable_components.context import (
    BoundedComponentGenerationRequest,
    deterministic_token_estimate,
)
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_root_continuation import (
    NATIVE_ROOT_REPAIR_MESSAGE,
    NativeRootCandidateAttempt,
    NativeRootRepairDiagnostic,
)


def render_native_root_repair_prompt(
    original: PreparedComponentGenerationRequest,
    predecessors: tuple[NativeRootCandidateAttempt, ...],
    diagnostic: NativeRootRepairDiagnostic | CandidateRepairDiagnostic,
) -> tuple[BoundedComponentGenerationRequest, bytes]:
    """Append the original fixed suffix; preserve context, budget and decision.

    Always pass the ORIGINAL prepared request, including for candidate three.
    Historical verification must independently establish that original identity;
    this function cannot infer it from arbitrary caller-supplied prompt bytes.
    """
    if (
        type(original) is not PreparedComponentGenerationRequest
        or type(original.request) is not BoundedComponentGenerationRequest
        or type(original.prompt) is not bytes
        or not original.prompt
    ):
        raise TypeError("original public bounded request and exact prompt required")
    original.request.__post_init__()
    if (
        ContentIdentity.parse_uri(
            "sha256:" + hashlib.sha256(original.prompt).hexdigest()
        )
        != original.request.prompt_identity
    ):
        raise ValueError("original public prompt differs from its bounded identity")
    if type(predecessors) is not tuple or not 1 <= len(predecessors) <= 2:
        raise ValueError("the complete finite original predecessor prefix is required")
    for index, attempt in enumerate(predecessors):
        if type(attempt) is not NativeRootCandidateAttempt:
            raise TypeError("typed original root predecessor attempts required")
        attempt.__post_init__()
        if (
            attempt.ordinal != index
            or attempt.predecessor_root_attempt_identities
            != tuple(prior.identity for prior in predecessors[:index])
        ):
            raise ValueError("root repair predecessor prefix changed")
    if type(diagnostic) is NativeRootRepairDiagnostic:
        diagnostic.__post_init__()
        message = NATIVE_ROOT_REPAIR_MESSAGE
    elif type(diagnostic) is CandidateRepairDiagnostic:
        diagnostic.__post_init__()
        message = diagnostic.sanitized_text
    else:
        raise TypeError("validated native or build/test diagnostic required")
    suffix = (
        "\n\n## Bounded root candidate-repair evidence\n"
        f"Failure: {message}\n"
        f"Diagnostic identity: {diagnostic.identity.uri}\n"
        "Predecessor root candidate attempt identities:\n"
        + "".join(f"- {attempt.identity.uri}\n" for attempt in predecessors)
        + "Produce a complete fresh replacement; do not reuse prior candidate "
        "files.\n"
    ).encode()
    prompt = original.prompt + suffix
    budget = original.request.budget
    if (
        len(prompt) > budget.max_prompt_bytes
        or max(
            original.request.context_manifest.estimated_tokens
            + deterministic_token_estimate(len(suffix)),
            deterministic_token_estimate(len(prompt)),
        )
        > budget.max_estimated_tokens
    ):
        raise ValueError("root repair evidence exceeds the original prompt budget")
    request = replace(
        original.request,
        prompt_identity=ContentIdentity.parse_uri(
            "sha256:" + hashlib.sha256(prompt).hexdigest()
        ),
    )
    if request.identity in {
        attempt.bounded_generation_request_identity for attempt in predecessors
    }:
        raise ValueError("root repair must change its bounded generation request")
    return request, prompt
