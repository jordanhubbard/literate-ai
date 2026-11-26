"""Initial v2 native-package materialization within live retained scratch custody.

Archive verification and current independent provider authority precede every
publication. The returned owner lasts only for this operation; it is neither an
admission receipt nor permission to reopen existing output directories.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    read_directory_export,
)
from literate_ai.adapters.qualification_capture import QualificationRunCapture
from literate_ai.adapters.retained_cargo_files_v2 import RetainedCargoFileSnapshotV2
from literate_ai.adapters.retained_cargo_import_v2 import (
    RetainedCargoCurrentInputsV2,
    verify_retained_cargo_archive_v2,
)
from literate_ai.adapters.retained_cargo_scratch_v2 import (
    RetainedCargoScratchScopeV2,
    reserve_retained_cargo_scratch_v2,
)
from literate_ai.adapters.retained_cargo_wrapper_v2 import (
    retained_cargo_wrapper_context_v2,
)
from literate_ai.adapters.retained_package_tree import RetainedPackageTree
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.retained_cargo_workspace_v2 import (
    RetainedCargoWorkspacePlanV2,
)


@dataclass(frozen=True, slots=True, eq=False)
class RetainedCargoScratchMaterializationV2:
    plan: RetainedCargoWorkspacePlanV2
    capture: QualificationRunCapture
    packages: tuple[RetainedPackageTree, ...]
    _files: RetainedCargoFileSnapshotV2 = field(repr=False)
    _current: RetainedCargoCurrentInputsV2 = field(repr=False)
    _scratch: RetainedCargoScratchScopeV2 = field(repr=False)
    _read_current: Callable[[], RetainedCargoCurrentInputsV2] = field(repr=False)
    _max_plan_bytes: int = field(repr=False)

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.cargo.v2-materialization-not-serializable")

    def require_unchanged(self):
        self._scratch.require_unchanged()
        self._files.require_authored_unchanged()
        self._current.require_unchanged()
        latest = self._read_current()
        if type(latest) is not RetainedCargoCurrentInputsV2:
            raise TypeError("retained.cargo.v2-current-inputs-required")
        latest.preflight(max_plan_bytes=self._max_plan_bytes)
        if latest != self._current:
            raise ValueError("retained.materialize.current-inputs-changed")
        for package in self.packages:
            package.require_unchanged()
        self._files.require_authored_unchanged()
        self._current.require_unchanged()
        self._scratch.require_unchanged()


def _verified_member_contents(reviewed, capture, *, max_records, max_package_bytes):
    """Join every verified export to exactly one declared member-root coordinate."""
    workspace = PurePosixPath(reviewed.plan.common.workspace_root)
    roots = tuple(
        PurePosixPath(item.path)
        for item in reviewed.plan.scratch_roots
        if item.kind == "member-packages"
    )
    contents = {root.as_posix(): [] for root in roots}
    destinations = dict(reviewed.binding.common.destinations)
    blobs = dict(capture.blobs)
    packages = []
    remaining_bytes, remaining_entries = max_package_bytes, max_records
    for manifest in capture.exports.graph.manifests:
        for export in manifest.exports:
            destination = PurePosixPath(destinations[export.identity])
            relative = destination.relative_to(workspace)
            matches = tuple(root for root in roots if relative.is_relative_to(root))
            if len(matches) != 1:
                raise ValueError("retained.cargo.v2-package-scratch-root-required")
            root = matches[0]
            files = read_directory_export(
                blobs[export.blob],
                export.blob,
                max_bytes=remaining_bytes,
                max_entries=remaining_entries,
            )
            remaining_bytes -= export.blob.size
            remaining_entries -= len(files)
            prefix = relative.relative_to(root)
            contents[root.as_posix()].extend(
                DirectoryExportFile(
                    (prefix / item.path).as_posix(), item.content, item.mode
                )
                for item in files
            )
            packages.append((reviewed.project.root / destination, files))
    if not packages or not roots or any(not files for files in contents.values()):
        raise ValueError("retained.cargo.v2-scratch-export-coverage-required")
    return (
        {
            root: tuple(sorted(files, key=lambda item: item.path))
            for root, files in contents.items()
        },
        tuple(sorted(packages, key=lambda item: str(item[0]))),
    )


@contextmanager
def materialize_initial_retained_cargo_scratch_v2(
    files: RetainedCargoFileSnapshotV2,
    *,
    read_current: Callable[[], RetainedCargoCurrentInputsV2],
    read_archive: Callable[[str, BlobRef, int], bytes],
    max_plan_bytes: int,
    max_archive_bytes: int,
    max_records: int,
    max_package_bytes: int,
    maximum_metadata_bytes: int = 1024 * 1024**2,
):
    """Keep fresh reservations, source and qualified packages live through use.

    Authored manifests must already match their reviewed after-state. Only the
    separately declared absent scratch roots are published here. Native commands,
    test coverage, source retirement and receiving admission remain separate.
    Existing roots are never adopted from ignore status or saved assertions.
    """
    if (
        type(files) is not RetainedCargoFileSnapshotV2
        or files.manifest_state != "after"
        or files.package_state not in {"absent", "provision"}
    ):
        raise ValueError("retained.materialize.v2-initial-after-state-required")
    files.require_unchanged()
    observed = []

    def current():
        value = read_current()
        if (
            type(value) is not RetainedCargoCurrentInputsV2
            or value.reviewed != files.reviewed
        ):
            raise ValueError("retained.materialize.v2-review-changed")
        observed.append(value)
        return value

    plan, capture = verify_retained_cargo_archive_v2(
        read_current=current,
        read_archive=read_archive,
        max_plan_bytes=max_plan_bytes,
        max_archive_bytes=max_archive_bytes,
        max_records=max_records,
        max_package_bytes=max_package_bytes,
    )
    if plan != files.reviewed.plan:
        raise ValueError("retained.materialize.plan-changed")
    baseline = observed[-1]
    baseline.require_unchanged()
    contents, destinations = _verified_member_contents(
        files.reviewed,
        capture,
        max_records=max_records,
        max_package_bytes=max_package_bytes,
    )
    files.require_unchanged()

    def publication_current():
        baseline.require_unchanged()
        files.require_authored_unchanged()
        latest = read_current()
        if type(latest) is not RetainedCargoCurrentInputsV2:
            raise TypeError("retained.cargo.v2-current-inputs-required")
        latest.preflight(max_plan_bytes=max_plan_bytes)
        if latest != baseline:
            raise ValueError("retained.materialize.current-inputs-changed")
        baseline.require_unchanged()
        files.require_authored_unchanged()

    with retained_cargo_wrapper_context_v2(files.reviewed) as context:
        baseline.require_unchanged()
        files.require_unchanged()
        with reserve_retained_cargo_scratch_v2(
            context,
            initial_contents=contents,
            maximum_initial_files=max_records,
            maximum_initial_bytes=max_package_bytes,
            maximum_metadata_bytes=maximum_metadata_bytes,
            publication_guard=publication_current,
        ) as scratch:
            result = RetainedCargoScratchMaterializationV2(
                plan,
                capture,
                tuple(
                    RetainedPackageTree.capture(Path(destination), content)
                    for destination, content in destinations
                ),
                files,
                baseline,
                scratch,
                read_current,
                max_plan_bytes,
            )
            result.require_unchanged()
            yield result
            result.require_unchanged()
