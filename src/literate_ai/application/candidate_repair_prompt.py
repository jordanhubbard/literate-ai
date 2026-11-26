"""The unchanged ordinary v2 public repair renderer, without allocation.

The producer retains its original eligibility checks. Closed callers must first
verify their original chain/request/diagnostic/current-authority joins. Rendering
these public bytes neither establishes retryability nor creates a live owner.
No context, complexity budget or decision is reissued or expanded here.
"""

import hashlib
from dataclasses import replace

from literate_ai.contracts import ContentIdentity, HashAlgorithm


def render_candidate_repair_prompt(
    original, diagnostic, predecessor_attempt_identities
):
    """Return exactly the old prompt/request transformation from its ORIGINAL base."""
    prompt = (
        original.prompt
        + (
            "\n\n## Bounded candidate-repair evidence\n"
            f"Failure: {diagnostic.sanitized_text}\n"
            f"Diagnostic identity: {diagnostic.identity.uri}\n"
            "Predecessor candidate attempt identities:\n"
            + "".join(
                f"- {identity.uri}\n" for identity in predecessor_attempt_identities
            )
            + "Produce a complete fresh replacement; do not reuse prior candidate "
            "files.\n"
        ).encode()
    )
    request = replace(
        original.request,
        prompt_identity=ContentIdentity(
            HashAlgorithm.SHA256, hashlib.sha256(prompt).hexdigest()
        ),
    )
    return request, prompt
