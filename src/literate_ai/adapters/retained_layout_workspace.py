"""Faithful disposable source copies for opt-in retained layout execution.

Original project authority is observed completely before producing a private
copy. The copy, CAS and command artifacts are outside the project. They are
retained on failure; this primitive never deletes a project or reconstructs a
live source owner from an inventory/receipt. Enclosing execution authorization
and bounded command admission remain the ordinary harness owner's job.
"""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.retained_layout import _fail
from literate_ai.adapters.retained_layout_partition import (
    _layout_modes,
    _layout_source_identity,
    _require_original,
    capture_retained_layout_source,
)
from literate_ai.adapters.retained_project_inputs import _directory_access
from literate_ai.storage.cas import FileSystemCAS


def _identity(node):
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_nlink,
    )


def _set_mode(root, name, mode, *, symbolic=False):
    """Change only an original private copy node; never follow its leaf alias."""
    if mode & ~0o777:
        _fail(
            "source_mode_unsupported",
            "disposable source execution refuses special permission bits",
        )
    path = root / name
    with _directory_access(root) as access:
        if access is None:
            # Windows needs the original native HANDLE mode/ACL implementation,
            # not this POSIX descriptor operation.
            _fail(
                "native_owner_unavailable",
                "faithful permission copy needs native handles",
            )
        parent = access.parent(path)
        before = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if symbolic:
            if not stat.S_ISLNK(before.st_mode):
                _fail(
                    "copy_changed",
                    "private source alias changed before mode verification",
                )
            if stat.S_IMODE(before.st_mode) != mode:
                os.chmod(path.name, mode, dir_fd=parent, follow_symlinks=False)
        else:
            flags = os.O_RDONLY | os.O_NOFOLLOW
            if stat.S_ISDIR(before.st_mode):
                flags |= os.O_DIRECTORY
            descriptor = os.open(path.name, flags, dir_fd=parent)
            try:
                if _identity(os.fstat(descriptor)) != _identity(before):
                    _fail(
                        "copy_changed",
                        "private source node changed before setting its mode",
                    )
                os.fchmod(descriptor, mode)
                after = os.fstat(descriptor)
                named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                if (
                    after.st_dev,
                    after.st_ino,
                    after.st_uid,
                    after.st_gid,
                    after.st_nlink,
                ) != (
                    before.st_dev,
                    before.st_ino,
                    before.st_uid,
                    before.st_gid,
                    before.st_nlink,
                ) or _identity(named) != _identity(after):
                    _fail("copy_changed", "private source mode target was replaced")
            finally:
                os.close(descriptor)
        actual = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if stat.S_IMODE(actual.st_mode) != mode:
            _fail("copy_changed", "private source mode differs after materialization")


@dataclass(frozen=True, slots=True)
class RetainedLayoutWorkspace:
    """Descriptive current copy result, no restored owner or execution grant."""

    parent: Path
    implementation: Path
    source_identity: str
    tree_identity: str
    modes: tuple[tuple[str, int], ...]


def materialize_retained_layout_workspace(
    context, *, parent, limits, case_sensitive=False
):
    """Copy complete actual source/link geometry into a fresh external workspace.

    The CAS/private parent are retained on failure. The canonical materializer
    still applies its existing cleanup to its own failed unpublished stage.
    """
    from .native_sdk_tree_custody import (
        _capture_composed_native_tree,
        _materialize_native_tree,
    )

    record = _require_original(context)
    parent = Path(parent)
    require_safe_directory(parent)
    if (
        not parent.is_absolute()
        or parent.resolve(strict=True) != parent
        or parent.is_relative_to(record["root"])
    ):
        _fail(
            "workspace_inside_project", "disposable source workspace must be external"
        )
    context.require_framework_current()
    if os.name == "nt":
        _fail(
            "native_owner_unavailable",
            "Windows faithful copy needs its native HANDLE implementation",
        )
    # This helper never reuses an existing stage, cached success or serialized
    # owner. Canonical lifecycle authorization must already precede this write.
    private = Path(tempfile.mkdtemp(prefix="litai-layout-execution-", dir=parent))
    private_node = private.lstat()
    if stat.S_IMODE(private_node.st_mode) not in {0o700, 0o2700}:
        _fail("workspace_unsafe", "fresh execution workspace is not private")
    store = FileSystemCAS(private / "cas")
    tree = _capture_composed_native_tree(
        record["source_root"],
        store=store,
        limits=limits,
        case_sensitive=case_sensitive,
        max_metadata_memory_bytes=record["maximum"],
        layout_custody=context,
        reserved_memory_bytes=record["retained"],
        budget_capture=True,
        retain_payloads=True,
    )
    modes, mode_memory = _layout_modes(context, tree, reserved_memory_bytes=0)
    if any(mode & ~0o777 for _, mode in modes):
        _fail(
            "source_mode_unsupported",
            "disposable execution refuses special permission bits",
        )
    closing = capture_retained_layout_source(
        context,
        limits=limits,
        case_sensitive=case_sensitive,
        reserved_memory_bytes=tree.index.metadata_memory_bound + mode_memory,
    )
    closing_modes, _ = _layout_modes(
        context,
        closing,
        reserved_memory_bytes=tree.index.metadata_memory_bound + mode_memory,
    )
    if closing.identity != tree.identity or closing_modes != modes:
        _fail(
            "source_changed", "source changed while preparing its disposable workspace"
        )
    del closing, closing_modes
    extra = record["retained"] + tree.index.metadata_memory_bound + mode_memory

    def capture(stage, **kwargs):
        return _capture_composed_native_tree(
            stage,
            **kwargs,
            max_metadata_memory_bytes=record["maximum"],
            reserved_memory_bytes=extra,
            budget_capture=True,
        )

    def equal(actual):
        return (
            actual.directories == tree.directories
            and actual.files == tree.files
            and actual.aliases == tree.aliases
            and actual.case_sensitive == tree.case_sensitive
        )

    execution = _materialize_native_tree(
        tree, store=store, limits=limits, parent=private, capture=capture, equal=equal
    )
    mode_map = dict(modes)
    for item in tree.files:
        _set_mode(execution, item.path, mode_map[item.path])
    for item in tree.aliases:
        if item.kind == "symlink":
            _set_mode(execution, item.path, mode_map[item.path], symbolic=True)
    # Children first: a retained read-only parent must not be chmodded before
    # its existing descendants have their own original modes restored.
    for name in sorted(
        tree.directories, key=lambda name: (-len(Path(name).parts), name)
    ):
        _set_mode(execution, name, mode_map[name])
    identity = _layout_source_identity(tree.identity, modes)
    context.require_framework_current(
        reserved_memory_bytes=tree.index.metadata_memory_bound + mode_memory
    )
    if _identity(private.lstat())[:5] != _identity(private_node)[:5]:
        _fail("workspace_changed", "original private workspace root changed")
    return RetainedLayoutWorkspace(
        private, execution, identity.uri, tree.identity.uri, modes
    )
