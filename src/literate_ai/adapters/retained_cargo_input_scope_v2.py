"""Complete explicit Cargo input roots under the original source-v2 facade."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai.adapters.retained_cargo_input_owners_v2 import (
    RetainedCargoInputOwnersV2,
)
from literate_ai.adapters.retained_cargo_input_scope_core import (
    _capture_consumer_input_scope,
    _CargoConsumerInputScopeMethods,
    _prepare_consumer_input_scope,
)
from literate_ai.adapters.retained_cargo_scratch_v2 import RetainedCargoScratchScopeV2
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.retained_cargo_policy import RetainedLibraryGatePolicyV2


@dataclass(frozen=True, slots=True)
class RetainedCargoInputScopeV2(_CargoConsumerInputScopeMethods):
    policy: RetainedLibraryGatePolicyV2
    environment_identity: ContentIdentity
    owners: RetainedCargoInputOwnersV2
    roots: tuple[tuple[str, Path], ...]
    _scratch: RetainedCargoScratchScopeV2 | None = field(
        default=None, repr=False, compare=False
    )


def capture_retained_cargo_input_scope_v2(
    workspace: Path,
    *,
    policy: RetainedLibraryGatePolicyV2,
    environment: Mapping[str, str],
    maximum_metadata_bytes: int = 1024 * 1024 * 1024,
    scratch: RetainedCargoScratchScopeV2 | None = None,
) -> RetainedCargoInputScopeV2:
    """Capture entire declared roots, including previously unknown home entries.

    No exclusions are inferred from Git ignore status, Cargo conventions or a
    serialized workspace plan. Only the exact live scratch owner can supply its
    workspace output exclusions; it must outlive this capture's use.
    The caller must separately capture configuration outside these roots.
    """
    live_environment = environment
    environment_identity, environment = _prepare_consumer_input_scope(
        workspace, policy, environment
    )
    if scratch is not None and type(scratch) is not RetainedCargoScratchScopeV2:
        raise TypeError("retained.cargo.v2-live-scratch-required")
    owners, roots = _capture_consumer_input_scope(
        workspace,
        policy=policy,
        environment=environment,
        maximum_metadata_bytes=maximum_metadata_bytes,
        scratch=scratch,
    )
    result = RetainedCargoInputScopeV2(
        policy, environment_identity, owners, roots, scratch
    )
    result.require_unchanged(environment=live_environment)
    return result
