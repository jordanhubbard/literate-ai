"""Private bounded consumer file observations, never receiving permission.

Exact nominal public readers select one closed reviewed declaration type. Present
bytes and absent paths retain their original before/after/provision semantics.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.authored_retained_cargo_review import (
    AuthoredRetainedCargoReviewedFiles,
)
from literate_ai.adapters.retained_cargo_files import _require_absent
from literate_ai.adapters.retained_cargo_review_v2 import RetainedCargoReviewedFilesV2
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.projects import PinnedInputClosure


def _consumer_destinations(reviewed):
    if type(reviewed) is RetainedCargoReviewedFilesV2:
        return reviewed.binding.common.destinations
    if type(reviewed) is AuthoredRetainedCargoReviewedFiles:
        return reviewed.binding.destinations
    raise TypeError("retained.cargo.consumer-reviewed-files-required")


class _ConsumerFileObservationMethods:
    __slots__ = ()
    _IDENTITY_SCHEMA = "literate-ai/retained-cargo-file-snapshot@2"

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": self._IDENTITY_SCHEMA,
                "reviewed": self.reviewed.identity.uri,
                "manifest_state": self.manifest_state,
                "package_state": self.package_state,
                "present_files": self._inputs.identity,
                "absent_paths": list(self.absent_paths),
            }
        )

    def require_authored_unchanged(self):
        self.reviewed.require_unchanged()
        self._inputs.require_unchanged()
        destinations = {path for _, path in _consumer_destinations(self.reviewed)}
        for path in self.absent_paths:
            if path not in destinations:
                _require_absent(self.reviewed.project.root, path)
        self._inputs.require_unchanged()

    def require_unchanged(self):
        self.require_authored_unchanged()
        destinations = {path for _, path in _consumer_destinations(self.reviewed)}
        for path in self.absent_paths:
            if path in destinations:
                _require_absent(self.reviewed.project.root, path)
        self.reviewed.require_unchanged()
        self._inputs.require_unchanged()


def _read_consumer_file_observations(
    reviewed,
    *,
    manifest_state: str,
    package_state: str = "present",
    maximum_file_bytes: int = 16 * 1024**2,
    maximum_total_bytes: int = 64 * 1024**2,
):
    """Reopen exact before/after files without confusing a v1 plan or binding.

    During absent/provision phases, manifests inside absent package destinations
    are deferred to the native qualified archive checker, not accepted from the
    plan alone. All other present and absent authored files remain pinned.
    """
    if type(reviewed) not in (
        RetainedCargoReviewedFilesV2,
        AuthoredRetainedCargoReviewedFiles,
    ):
        raise ValueError("retained.cargo.consumer-reviewed-files-required")
    if manifest_state not in {"before", "after"}:
        raise ValueError("retained.cargo.manifest-state-invalid")
    if package_state not in {"present", "absent", "provision"} or (
        package_state != "present" and manifest_state != "after"
    ):
        raise ValueError("retained.cargo.package-state-invalid")
    if (
        type(maximum_file_bytes) is not int
        or type(maximum_total_bytes) is not int
        or not 0 < maximum_file_bytes <= 256 * 1024**2
        or not maximum_file_bytes <= maximum_total_bytes <= 1024**3
    ):
        raise ValueError("retained.cargo.v2-manifest-limits-invalid")
    reviewed.require_unchanged()
    plan = reviewed.plan.common
    root = reviewed.project.root
    manifests = tuple(
        (str(PurePosixPath(plan.workspace_root) / item.path), item)
        for item in plan.manifests
    )
    canonical_relative_posix_paths(
        (*reviewed.document_paths, *(path for path, _ in manifests)),
        label="disjoint reviewed Cargo v2 inputs",
    )
    destinations = tuple(
        PurePosixPath(path) for _, path in _consumer_destinations(reviewed)
    )
    absent, absent_destinations = set(), set()
    if package_state in {"absent", "provision"}:
        for destination in destinations:
            if package_state == "provision":
                try:
                    (root / destination).lstat()
                except FileNotFoundError:
                    pass
                else:
                    require_safe_directory(root / destination)
                    continue
            _require_absent(root, str(destination))
            absent.add(str(destination))
            absent_destinations.add(destination)
    inputs = PinnedInputClosure(
        maximum_files=4096,
        maximum_file_bytes=maximum_file_bytes,
        maximum_total_bytes=maximum_total_bytes,
    )
    for relative, item in manifests:
        if any(
            PurePosixPath(relative).is_relative_to(path) for path in absent_destinations
        ):
            continue
        reference = getattr(item, manifest_state)
        if reference is None:
            _require_absent(root, relative)
            absent.add(relative)
        else:
            if not 0 < reference.size <= maximum_file_bytes:
                raise ValueError("retained.cargo.v2-manifest-size-invalid")
            content = inputs.pin(
                root / relative,
                boundary=root,
                label=relative,
                expected_identity=reference.identity,
            )
            if len(content) != reference.size:
                raise ValueError("retained.cargo.v2-manifest-size-mismatch")
    return tuple(sorted(absent)), inputs
