"""Distinct authored receiving observations of complete native consumer inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai.adapters.authored_retained_cargo_scratch import (
    AuthoredRetainedCargoScratchScope,
)
from literate_ai.adapters.retained_cargo_input_owners_v2 import (
    RetainedCargoInputOwnersV2,
)
from literate_ai.adapters.retained_cargo_input_scope_core import (
    _capture_consumer_input_scope,
    _CargoConsumerInputScopeMethods,
    _prepare_consumer_input_scope,
)
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.retained_cargo_policy import RetainedLibraryGatePolicyV2


@dataclass(frozen=True, slots=True)
class AuthoredRetainedCargoInputScope(_CargoConsumerInputScopeMethods):
    _IDENTITY_SCHEMA = "literate-ai/authored-retained-cargo-input-scope@1"

    policy: RetainedLibraryGatePolicyV2
    environment_identity: ContentIdentity
    owners: RetainedCargoInputOwnersV2
    roots: tuple[tuple[str, Path], ...]
    _scratch: AuthoredRetainedCargoScratchScope = field(repr=False, compare=False)


def capture_authored_retained_cargo_input_scope(
    workspace: Path,
    *,
    policy: RetainedLibraryGatePolicyV2,
    environment: Mapping[str, str],
    scratch: AuthoredRetainedCargoScratchScope,
    maximum_metadata_bytes: int = 1024 * 1024 * 1024,
) -> AuthoredRetainedCargoInputScope:
    """Capture whole consumer roots; saved observations grant no execution.

    Actual authored receiving scratch must remain live. No exclusions follow
    from a serialized plan or ignored outputs; provisioning precedes this read.
    """
    live_environment = environment
    environment_identity, environment = _prepare_consumer_input_scope(
        workspace, policy, environment
    )
    if type(scratch) is not AuthoredRetainedCargoScratchScope:
        raise TypeError("retained.cargo.authored-live-scratch-required")
    owners, roots = _capture_consumer_input_scope(
        workspace,
        policy=policy,
        environment=environment,
        maximum_metadata_bytes=maximum_metadata_bytes,
        scratch=scratch,
    )
    result = AuthoredRetainedCargoInputScope(
        policy, environment_identity, owners, roots, scratch
    )
    result.require_unchanged(environment=live_environment)
    return result
