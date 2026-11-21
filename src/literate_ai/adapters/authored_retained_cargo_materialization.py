"""Exclusive package publication within original authored receiving scopes.

This initial transaction never adopts existing packages. It grants no consumer
execution, source retirement, admission receipt or saved reopening permission.
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.authored_retained_cargo_files import (
    AuthoredRetainedCargoFileSnapshot,
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    CurrentAuthoredRetainedCargoInputs,
)
from literate_ai.adapters.authored_retained_cargo_scratch import (
    AuthoredRetainedCargoScratchScope,
)
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    publish_directory_exclusive,
)
from literate_ai.adapters.retained_cargo_package_values import (
    _read_consumer_package_values,
)
from literate_ai.adapters.retained_package_tree import (
    RetainedPackageTree,
    write_staged_package,
)

_CREATION_KEY = object()


@dataclass(init=False, frozen=True, eq=False)
class AuthoredRetainedCargoMaterialization:
    """Original consumer scratch and current authored product/package custody."""

    files: AuthoredRetainedCargoFileSnapshot = field(repr=False)
    scratch: AuthoredRetainedCargoScratchScope = field(repr=False)
    current: CurrentAuthoredRetainedCargoInputs = field(repr=False)
    packages: tuple[RetainedPackageTree, ...]

    def __init__(self, *, key, files, scratch, current, packages):
        if key is not _CREATION_KEY:
            raise TypeError("retained.cargo.authored-live-materialization-required")
        for name, value in (
            ("files", files),
            ("scratch", scratch),
            ("current", current),
            ("packages", packages),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("retained.cargo.authored-materialization-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.cargo.authored-materialization-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.cargo.authored-materialization-not-serializable")

    def require_unchanged(self):
        self.scratch.require_unchanged()
        self.files.require_authored_unchanged()
        self.current.require_unchanged()
        for package in self.packages:
            package.require_unchanged()
        self.current.require_unchanged()
        # External tool/provider callbacks must precede the final consumer
        # source and package observations, just as in the source receiving path.
        self.files.require_authored_unchanged()
        self.scratch.require_unchanged()
        for package in self.packages:
            package.require_unchanged()


def materialize_authored_retained_cargo_packages(
    files: AuthoredRetainedCargoFileSnapshot,
    *,
    scratch: AuthoredRetainedCargoScratchScope,
    current: CurrentAuthoredRetainedCargoInputs,
    max_package_bytes: int = 256 * 1024**2,
    max_records: int = 100_000,
) -> AuthoredRetainedCargoMaterialization:
    """Publish complete native exports beneath the live owned package roots.

    Actual input, wrapper and scratch contexts must remain open. Fresh review
    objects, matching DTOs, saved directories and ignored outputs cannot replace
    those original owners. Failure retains foreign or uncertain filesystem data.
    """
    if (
        type(files) is not AuthoredRetainedCargoFileSnapshot
        or type(scratch) is not AuthoredRetainedCargoScratchScope
        or type(current) is not CurrentAuthoredRetainedCargoInputs
        or files.manifest_state != "after"
        or files.package_state not in {"absent", "provision"}
        or scratch.context.reviewed is not files.reviewed
        or current.reviewed is not files.reviewed
    ):
        raise ValueError("retained.cargo.authored-current-scratch-files-required")
    if (
        type(max_package_bytes) is not int
        or not 0 < max_package_bytes <= 256 * 1024**2
        or type(max_records) is not int
        or not 0 < max_records <= 100_000
    ):
        raise ValueError("retained.cargo.authored-materialization-limits-invalid")

    def guard():
        scratch.require_unchanged()
        files.require_authored_unchanged()
        current.require_unchanged()
        files.require_authored_unchanged()
        scratch.require_unchanged()

    # Caller observations are passive data. Reopen the actual reviewed after-
    # manifests and absent package destinations internally; a hand-constructed
    # snapshot with an empty closure cannot stand in for those observations.
    files.require_unchanged()
    caller_files = files
    files = read_authored_retained_cargo_files(
        current.reviewed,
        manifest_state="after",
        package_state="absent",
        maximum_file_bytes=16 * 1024**2,
        maximum_total_bytes=64 * 1024**2,
    )
    caller_files.require_unchanged()
    guard()
    reviewed = files.reviewed
    packages = _read_consumer_package_values(
        reviewed.project.root,
        scratch.context.workspace,
        reviewed.plan.scratch_roots,
        reviewed.binding.exports,
        reviewed.binding.destinations,
        current.products.blobs,
        max_package_bytes=max_package_bytes,
        max_records=max_records,
    )
    staged, published = [], []
    try:
        for destination, content in packages:
            guard()
            if destination.exists() or destination.is_symlink():
                raise ValueError("retained.cargo.authored-package-destination-present")
            require_safe_directory(destination.parent)
            stage = tempfile.mkdtemp(prefix=".rp-", dir=destination.parent)
            staged.append((destination, write_staged_package(Path(stage), content)))
        files.require_unchanged()
        guard()
        for destination, tree in staged:
            guard()
            tree.require_unchanged()
            publish_directory_exclusive(
                tree.root,
                destination,
                expected_source=directory_node(tree.root),
                expected_parent=directory_node(destination.parent),
            )
            published.append((destination, tree))
            tree.relocated(destination).require_unchanged()
            guard()
        result = AuthoredRetainedCargoMaterialization(
            key=_CREATION_KEY,
            files=files,
            scratch=scratch,
            current=current,
            packages=tuple(tree.relocated(path) for path, tree in published),
        )
        result.require_unchanged()
        return result
    except BaseException:
        for destination, tree in reversed(published):
            try:
                scratch.require_unchanged()
                tree.relocated(destination).require_unchanged()
                publish_directory_exclusive(
                    destination,
                    tree.root,
                    expected_source=directory_node(destination),
                    expected_parent=directory_node(destination.parent),
                )
            except (OSError, ValueError, RuntimeError):
                # Only exact still-owned trees can move. Never delete or adopt a
                # foreign replacement or uncertain output during rollback.
                pass
        raise
