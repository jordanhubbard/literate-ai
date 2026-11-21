"""Authored receiving consumer file observations, without artifact permission.

Absent package paths remain deferred to the independently reopened exact native
exports. Existing packages are not adopted by these passive observations.
"""

from dataclasses import dataclass, field

from literate_ai.adapters.authored_retained_cargo_review import (
    AuthoredRetainedCargoReviewedFiles,
)
from literate_ai.adapters.retained_cargo_files_core import (
    _ConsumerFileObservationMethods,
    _read_consumer_file_observations,
)
from literate_ai.projects import PinnedInputClosure


@dataclass(frozen=True, slots=True)
class AuthoredRetainedCargoFileSnapshot(_ConsumerFileObservationMethods):
    _IDENTITY_SCHEMA = "literate-ai/authored-retained-cargo-file-snapshot@1"

    reviewed: AuthoredRetainedCargoReviewedFiles
    manifest_state: str
    package_state: str
    absent_paths: tuple[str, ...]
    _inputs: PinnedInputClosure = field(repr=False, compare=False)


def read_authored_retained_cargo_files(
    reviewed: AuthoredRetainedCargoReviewedFiles,
    *,
    manifest_state: str,
    package_state: str = "present",
    maximum_file_bytes: int = 16 * 1024**2,
    maximum_total_bytes: int = 64 * 1024**2,
) -> AuthoredRetainedCargoFileSnapshot:
    """Reopen exact consumer manifest states for the authored receiving variant."""
    if type(reviewed) is not AuthoredRetainedCargoReviewedFiles:
        raise ValueError("retained.cargo.authored-reviewed-files-required")
    absent, inputs = _read_consumer_file_observations(
        reviewed,
        manifest_state=manifest_state,
        package_state=package_state,
        maximum_file_bytes=maximum_file_bytes,
        maximum_total_bytes=maximum_total_bytes,
    )
    result = AuthoredRetainedCargoFileSnapshot(
        reviewed, manifest_state, package_state, absent, inputs
    )
    result.require_unchanged()
    return result
