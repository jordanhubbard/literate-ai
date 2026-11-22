"""Source-v2 exact file observations; no publication or admission permission."""

from dataclasses import dataclass, field

from literate_ai.adapters.retained_cargo_files_core import (
    _ConsumerFileObservationMethods,
    _read_consumer_file_observations,
)
from literate_ai.adapters.retained_cargo_review_v2 import RetainedCargoReviewedFilesV2
from literate_ai.projects import PinnedInputClosure


@dataclass(frozen=True, slots=True)
class RetainedCargoFileSnapshotV2(_ConsumerFileObservationMethods):
    reviewed: RetainedCargoReviewedFilesV2
    manifest_state: str
    package_state: str
    absent_paths: tuple[str, ...]
    _inputs: PinnedInputClosure = field(repr=False, compare=False)


def read_retained_cargo_files_v2(
    reviewed: RetainedCargoReviewedFilesV2,
    *,
    manifest_state: str,
    package_state: str = "present",
    maximum_file_bytes: int = 16 * 1024**2,
    maximum_total_bytes: int = 64 * 1024**2,
) -> RetainedCargoFileSnapshotV2:
    """Preserve the source-v2 exact type gate and original file-state meanings."""
    if type(reviewed) is not RetainedCargoReviewedFilesV2:
        raise ValueError("retained.cargo.v2-reviewed-files-required")
    absent, inputs = _read_consumer_file_observations(
        reviewed,
        manifest_state=manifest_state,
        package_state=package_state,
        maximum_file_bytes=maximum_file_bytes,
        maximum_total_bytes=maximum_total_bytes,
    )
    result = RetainedCargoFileSnapshotV2(
        reviewed, manifest_state, package_state, absent, inputs
    )
    result.require_unchanged()
    return result
