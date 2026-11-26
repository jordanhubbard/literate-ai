"""Initial scratch ownership inside a current retained Cargo wrapper.

Only fresh, absent roots are provisioned here. Existing outputs require separate
current package/provenance reopening; ignored files never supply that authority.
No native package, manifest edit, execution or admission is authorized here.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import unicodedata
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters._write_reservations import (
    WriteReservationTarget,
    acquire_write_reservations,
)
from literate_ai.adapters.builders import run_bounded_process
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from literate_ai.adapters.retained_cargo_wrapper_v2 import RetainedCargoWrapperContextV2
from literate_ai.adapters.retained_package_tree import write_staged_package
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

_CREATION_KEY = object()


def _initial_member_contents(declarations, supplied, *, maximum_files, maximum_bytes):
    """Freeze finite staging data before observing or creating scratch paths."""
    if (
        type(maximum_files) is not int
        or not 0 < maximum_files <= RetainedCargoInputBudget.MAXIMUM_FILES
        or type(maximum_bytes) is not int
        or not 0 < maximum_bytes <= RetainedCargoInputBudget.MAXIMUM_TOTAL_BYTES
    ):
        raise ValueError("retained.cargo.v2-initial-package-limits-invalid")
    if supplied is None:
        return {}
    members = {item.path for item in declarations if item.kind == "member-packages"}
    if not isinstance(supplied, Mapping) or len(supplied) > len(members):
        raise ValueError("retained.cargo.v2-initial-package-roots-invalid")
    result = {}
    count, size = 0, 0
    for index, coordinate in enumerate(supplied):
        if index >= len(members) or coordinate not in members or coordinate in result:
            raise ValueError("retained.cargo.v2-initial-package-roots-invalid")
        files = supplied[coordinate]
        if type(files) is not tuple or not files or len(files) > maximum_files - count:
            raise ValueError("retained.cargo.v2-initial-package-files-invalid")
        frozen = []
        for item in files:
            if (
                type(item) is not DirectoryExportFile
                or type(item.content) is not bytes
                or len(item.content) > RetainedCargoInputBudget.MAXIMUM_FILE_BYTES
                or type(item.mode) is not int
                or not 0 <= item.mode <= 0o777
                or type(item.path) is not str
            ):
                raise ValueError("retained.cargo.v2-initial-package-file-invalid")
            count += 1
            size += len(item.content)
            if count > maximum_files or size > maximum_bytes:
                raise ValueError("retained.cargo.v2-initial-package-limit-exceeded")
            frozen.append(DirectoryExportFile(item.path, item.content, item.mode))
        paths = canonical_relative_posix_paths(
            (item.path for item in frozen), label="initial Cargo member files"
        )
        prefixes = {}
        for path in paths:
            for depth in range(1, len(path.parts) + 1):
                prefix = "/".join(path.parts[:depth])
                alias = unicodedata.normalize("NFC", prefix.casefold())
                if prefixes.setdefault(alias, prefix) != prefix:
                    raise ValueError("retained.cargo.v2-initial-package-path-alias")
        result[coordinate] = tuple(frozen)
    return result


def _ignored(context, paths):
    executable = shutil.which("git")
    if executable is None:
        raise ValueError("retained.cargo.v2-scratch-git-required")
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    root = context.reviewed.project.root

    def run(arguments, content=None):
        return run_bounded_process(
            (executable, "-c", "core.excludesFile=" + os.devnull, *arguments),
            cwd=root,
            environment=environment,
            timeout_seconds=10,
            stdout_limit_bytes=65536,
            stderr_limit_bytes=4096,
            input_bytes=content,
            error_prefix="retained.cargo.v2-scratch-git",
        )

    repository = run(("rev-parse", "--show-toplevel"))
    reported = Path(os.fsdecode(repository.stdout).rstrip("\r\n"))
    if (
        repository.returncode
        or reported != root
        or directory_node(reported) != directory_node(root)
    ):
        raise ValueError("retained.cargo.v2-scratch-project-git-required")
    names = tuple(path.relative_to(root).as_posix() + "/" for path in paths)
    content = b"".join(os.fsencode(name) + b"\0" for name in names)
    result = run(("check-ignore", "--no-index", "-z", "--stdin"), content)
    if result.returncode or result.stdout != content:
        raise ValueError("retained.cargo.v2-scratch-ignore-required")


def _require_absent(path, *, maximum_entries):
    require_safe_directory(path.parent)
    alias = unicodedata.normalize("NFC", path.name.casefold())
    for index, entry in enumerate(path.parent.iterdir()):
        if index >= maximum_entries:
            raise ValueError("retained.cargo.v2-scratch-parent-limit")
        if unicodedata.normalize("NFC", entry.name.casefold()) == alias:
            raise ValueError("retained.cargo.v2-scratch-existing-root")
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise ValueError("retained.cargo.v2-scratch-existing-root")


@dataclass(slots=True)
class _ScratchLifetime:
    active: bool = True


@dataclass(init=False, frozen=True, eq=False)
class RetainedCargoScratchScopeV2:
    """Live reservations and current source custody, never a saved capability."""

    def __init__(
        self, *, key, context, reservations, nodes, source, lifetime, trees=()
    ):
        if key is not _CREATION_KEY:
            raise TypeError("retained.cargo.v2-live-scratch-required")
        for name, value in (
            ("context", context),
            ("_reservations", reservations),
            ("_nodes", nodes),
            ("source", source),
            ("_lifetime", lifetime),
            ("_trees", trees),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("retained.cargo.v2-scratch-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.cargo.v2-scratch-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.cargo.v2-scratch-not-serializable")

    def __getstate__(self):
        raise TypeError("retained.cargo.v2-scratch-not-serializable")

    @property
    def workspace_exclusions(self):
        self.require_unchanged()
        return tuple(root.path for root in self.context.reviewed.plan.scratch_roots)

    def require_unchanged(self):
        if not self._lifetime.active:
            raise ValueError("retained.cargo.v2-scratch-operation-ended")
        self.context.require_unchanged()
        self._reservations.verify_all()
        for tree in self._trees:
            tree.require_unchanged()
        if any(directory_node(path) != node for path, node in self._nodes):
            raise ValueError("retained.cargo.v2-scratch-root-changed")
        _ignored(self.context, tuple(path for path, _ in self._nodes))
        self.source.require_unchanged()
        for tree in self._trees:
            tree.require_unchanged()
        if any(directory_node(path) != node for path, node in self._nodes):
            raise ValueError("retained.cargo.v2-scratch-root-changed")
        self._reservations.verify_all()
        self.context.require_unchanged()


@contextmanager
def reserve_retained_cargo_scratch_v2(
    context: RetainedCargoWrapperContextV2,
    *,
    maximum_metadata_bytes: int = 1024 * 1024 * 1024,
    initial_contents: Mapping[str, tuple[DirectoryExportFile, ...]] | None = None,
    maximum_initial_files: int = 10000,
    maximum_initial_bytes: int = 64 * 1024**2,
    publication_guard: Callable[[], None] | None = None,
):
    """Prove complete source and absence before creating any excluded root.

    All destination parents must already exist. No authored namespace is created
    on the way to an output. Identified private staging inodes are published
    exclusively; public paths are never adopted after an unguarded mkdir.
    Roots and private stages are retained when the scope ends, including empty
    roots. Reuse and recovery require separate current provenance, never a
    check-then-delete operation on a public name.
    Existing packages and outputs cannot be reopened through this initial path.

    A separate archive verifier may supply bounded initial member-root bytes.
    They are written only into the original private stages and move with those
    stages; no public empty root is replaced or populated after publication.
    These data-only bytes supply no package qualification or execution authority.
    Populated member roots retain complete byte, mode and namespace custody for
    the entire live scope. Cargo-output roots still start empty.
    """
    if type(context) is not RetainedCargoWrapperContextV2:
        raise TypeError("retained.cargo.v2-live-wrapper-required")
    if publication_guard is not None and not callable(publication_guard):
        raise TypeError("retained.cargo.v2-publication-guard-invalid")
    context.require_unchanged()
    reviewed = context.reviewed
    declarations = reviewed.plan.scratch_roots
    if not declarations:
        raise ValueError("retained.cargo.v2-scratch-declaration-required")
    contents = _initial_member_contents(
        declarations,
        initial_contents,
        maximum_files=maximum_initial_files,
        maximum_bytes=maximum_initial_bytes,
    )
    roots = tuple(context.workspace / item.path for item in declarations)
    budget = next(
        item.budget
        for item in reviewed.plan.input_custody.owners
        if item.scope == "workspace"
    )
    for path in roots:
        _require_absent(path, maximum_entries=budget.maximum_entries + len(roots))
    _ignored(context, roots)
    before = capture_retained_cargo_tree_v2(
        context.workspace,
        budget=budget,
        maximum_metadata_bytes=maximum_metadata_bytes,
    )
    context.require_unchanged()
    root = reviewed.project.root
    anchor = directory_node(root)
    targets = tuple(
        WriteReservationTarget(
            root
            / ".litai-locks"
            / (
                "cargo-scratch-"
                + hashlib.sha256(
                    path.relative_to(root).as_posix().casefold().encode()
                ).hexdigest()[:32]
                + ".lock"
            ),
            root,
            anchor,
        )
        for path in roots
    )
    stage_parent = (
        root / ".litai-locks" / ("cargo-scratch-stage-" + secrets.token_hex(12))
    )
    targets += (WriteReservationTarget(stage_parent / "owner.lock", root, anchor),)
    nodes, trees = [], []
    lifetime = _ScratchLifetime()
    with acquire_write_reservations(targets) as reservations:
        try:
            before.require_unchanged()
            context.require_unchanged()
            if not reservations.owns_directory(stage_parent):
                raise ValueError("retained.cargo.v2-scratch-private-parent-required")
            private_parent_node = directory_node(stage_parent)
            for index, path in enumerate(roots):
                reservations.verify_all()
                _require_absent(
                    path, maximum_entries=budget.maximum_entries + len(roots)
                )
                stage = stage_parent / ("s" + str(index))
                stage.mkdir(mode=0o700)
                stage_node = directory_node(stage)
                if any(stage.iterdir()):
                    raise ValueError("retained.cargo.v2-scratch-stage-not-empty")
                content = contents.get(declarations[index].path)
                tree = None if content is None else write_staged_package(stage, content)
                if tree is not None:
                    tree.require_unchanged()
                if directory_node(stage) != stage_node:
                    raise ValueError("retained.cargo.v2-scratch-stage-changed")
                reservations.verify_all()
                context.require_unchanged()
                if publication_guard is not None:
                    publication_guard()
                publish_directory_between_owned_parents_exclusive(
                    stage,
                    path,
                    expected_source=stage_node,
                    expected_source_parent=private_parent_node,
                    expected_destination_parent=directory_node(path.parent),
                )
                if publication_guard is not None:
                    publication_guard()
                if directory_node(path) != stage_node:
                    raise ValueError("retained.cargo.v2-scratch-publication-changed")
                if tree is None:
                    if any(path.iterdir()):
                        raise ValueError(
                            "retained.cargo.v2-scratch-publication-changed"
                        )
                else:
                    trees.append(tree.relocated(path))
                nodes.append((path, stage_node))
            source = capture_retained_cargo_tree_v2(
                context.workspace,
                budget=budget,
                exclusions=tuple(item.path for item in declarations),
                maximum_metadata_bytes=maximum_metadata_bytes,
            )
            if any(
                getattr(before, name) != getattr(source, name)
                for name in ("directories", "files", "aliases", "_physical")
            ):
                raise ValueError("retained.cargo.v2-scratch-source-changed")
            scope = RetainedCargoScratchScopeV2(
                key=_CREATION_KEY,
                context=context,
                reservations=reservations,
                nodes=tuple(nodes),
                source=source,
                lifetime=lifetime,
                trees=tuple(trees),
            )
            scope.require_unchanged()
            yield scope
            scope.require_unchanged()
        finally:
            lifetime.active = False
            # Preserve stages, public roots and replacements. The reservation
            # owner may retire only its marker, never public scratch contents.
            reservations.transfer_committed_directories((stage_parent,))
