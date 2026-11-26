"""Original complete source views inside opt-in disposable harness workspaces.

A fresh full capture establishes protected inputs before any pipeline command.
Later additions are command artifacts in this private copy, never exclusions
from the original project's complete source observation. Views are weak-issued,
PID/thread-scoped and retired; neither inventory paths nor saved JSON can create
or revive one. This observer grants no command or filesystem mutation authority.
"""

from __future__ import annotations

import os
import threading
import weakref
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.retained_layout import _fail
from literate_ai.adapters.retained_layout_partition import (
    _layout_source_identity,
    _native_mode_memory,
    _native_modes,
)
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_sdks import NativeSdkFile
from literate_ai.contracts.retained_layout import RetainedLayoutSourcePolicy

_ISSUED = weakref.WeakKeyDictionary()
_CURRENT = ContextVar("retained_layout_execution_source", default=None)
_CONTROL_MEMORY = 64 * 1024


def _admit(policy, retained):
    if retained > policy.maximum_metadata_bytes:
        _fail(
            "metadata_limit", "layout execution source view exceeds its memory policy"
        )


def _capture(root, policy, reserved):
    from .native_sdk_tree_custody import _capture_composed_native_tree

    return _capture_composed_native_tree(
        root,
        store=None,
        limits=policy.limits,
        case_sensitive=policy.case_sensitive,
        max_metadata_memory_bytes=policy.maximum_metadata_bytes,
        reserved_memory_bytes=reserved,
        budget_capture=True,
        retain_payloads=False,
    )


def _modes(root, policy, tree, reserved):
    memory = _native_mode_memory(tree)
    _admit(policy, reserved + tree.index.metadata_memory_bound + memory)
    return _native_modes(root, tree), memory


def _original(owner):
    if type(owner) is not _ExecutionSourceView:
        _fail(
            "original_execution_view_required",
            "original execution source view required",
        )
    record = _ISSUED.get(owner)
    if (
        record is None
        or not record["active"]
        or record["pid"] != os.getpid()
        or record["thread"] is not threading.current_thread()
    ):
        _fail(
            "original_execution_view_required",
            "execution source observation ended or changed",
        )
    require_safe_directory(record["root"])
    node = record["root"].lstat()
    actual = (node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid)
    if actual != record["node"]:
        _fail("workspace_changed", "original execution source root was replaced")
    return record


def _protected(record, actual, modes, retained):
    from .native_tree_shards import prepare_native_tree

    before, policy = record["tree"], record["policy"]
    count = (
        len(actual.directories)
        + len(actual.files)
        + len(actual.aliases)
        + len(before.directories)
        + len(before.files)
        + len(before.aliases)
    )
    # Admit full resolution maps and a simultaneous protected projection BEFORE
    # their allocation, while both original and post-command graphs are live.
    _admit(policy, retained + 2048 * count + before.index.metadata_memory_bound)
    directories = set(actual.directories)
    aliases = {item.path: item for item in actual.aliases}
    files = {item.path: item for item in actual.files}
    modes_by_name = dict(modes)
    if any(name not in directories for name in before.directories):
        _fail(
            "source_changed",
            "protected source directory disappeared or became an alias",
        )
    regular_names = tuple(
        sorted(
            [item.path for item in before.files]
            + [item.path for item in before.aliases if item.kind == "hardlink"]
        )
    )
    for name in regular_names:
        alias = aliases.get(name)
        if name not in files and (alias is None or alias.kind != "hardlink"):
            _fail(
                "source_changed",
                "protected regular source member changed kind or disappeared",
            )
    resolved = dict(zip(regular_names, actual.resolve_all(regular_names), strict=True))
    representatives = {resolved[item.path] for item in before.files}
    if len(representatives) != len(before.files):
        _fail("source_changed", "distinct protected source groups became hardlinked")
    for item in before.aliases:
        if item.kind == "hardlink":
            if resolved[item.path] != resolved[item.target]:
                _fail("source_changed", "protected source hardlink group split")
        elif aliases.get(item.path) != item:
            _fail("source_changed", "protected source symbolic target changed")
    protected_files = tuple(
        NativeSdkFile(
            item.path,
            files[resolved[item.path]].blob,
            bool(modes_by_name[item.path] & 0o111),
        )
        for item in before.files
    )
    index = before.index
    protected = prepare_native_tree(
        before.directories,
        protected_files,
        before.aliases,
        limits=policy.limits,
        case_sensitive=policy.case_sensitive,
        max_descriptor_bytes=index.max_descriptor_bytes,
        max_descriptor_total_bytes=index.max_descriptor_total_bytes,
        max_index_bytes=index.max_index_bytes,
        max_metadata_memory_bytes=policy.maximum_metadata_bytes,
        reserved_memory_bytes=retained + 2048 * count,
    )
    protected_modes = tuple((name, modes_by_name[name]) for name, _ in record["modes"])
    return _layout_source_identity(protected.identity, protected_modes)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class _ExecutionSourceView:
    def __reduce__(self):
        raise TypeError("retained.layout.execution-view-not-transportable")

    def observe(self):
        record = _original(self)
        policy, root = record["policy"], record["root"]
        baseline = record["memory"]
        actual = _capture(root, policy, baseline)
        modes, mode_memory = _modes(root, policy, actual, baseline)
        retained = baseline + actual.index.metadata_memory_bound + mode_memory
        protected = _protected(record, actual, modes, retained)
        closing = _capture(root, policy, retained)
        closing_modes, _ = _modes(root, policy, closing, retained)
        if closing.identity != actual.identity or closing_modes != modes:
            _fail("workspace_changed", "execution workspace changed during observation")
        _original(self)
        if protected != record["identity"]:
            _fail(
                "source_changed",
                "pipeline changed protected source bytes, modes or topology",
            )
        source = {
            "identity": protected.uri,
            "file_count": record["file_count"],
            "missing_count": 0,
            "total_bytes": record["source_bytes"],
            "scope": "complete-retained-layout@1",
        }
        artifact = {
            "identity": _layout_source_identity(actual.identity, modes).uri,
            "file_count": len(actual.files) + len(actual.aliases),
            "missing_count": 0,
            "total_bytes": sum(item.blob.size for item in actual.files)
            + sum(
                len(item.target.encode("utf-8"))
                for item in actual.aliases
                if item.kind == "symlink"
            ),
            "scope": "complete-disposable-layout-workspace@1",
            "excluded": [],
        }
        return {"tree": artifact, "source_tree": source, "excluded": []}


@contextmanager
def _observe_layout_execution_source(root, scope, *, expected_source_identity):
    """Issue from fresh actual complete source, never a supplied member list."""
    if not isinstance(expected_source_identity, ContentIdentity):
        raise TypeError("retained.layout.typed-execution-source-identity-required")
    policy = RetainedLayoutSourcePolicy.from_dict(scope)
    root = Path(root)
    require_safe_directory(root)
    if not root.is_absolute() or root.resolve(strict=True) != root:
        _fail("workspace_unsafe", "execution source must be an actual direct root")
    node = root.lstat()
    tree = _capture(root, policy, _CONTROL_MEMORY)
    modes, mode_memory = _modes(root, policy, tree, _CONTROL_MEMORY)
    memory = _CONTROL_MEMORY + tree.index.metadata_memory_bound + mode_memory
    closing = _capture(root, policy, memory)
    closing_modes, _ = _modes(root, policy, closing, memory)
    if closing.identity != tree.identity or closing_modes != modes:
        _fail("source_changed", "execution source changed during original observation")
    identity = _layout_source_identity(tree.identity, modes)
    if identity != expected_source_identity:
        _fail(
            "source_changed",
            "execution source differs from actual admitted project inputs",
        )
    del closing, closing_modes
    owner = _ExecutionSourceView()
    record = {
        "active": True,
        "pid": os.getpid(),
        "thread": threading.current_thread(),
        "root": root,
        "node": (node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid),
        "policy": policy,
        "tree": tree,
        "modes": modes,
        "memory": memory,
        "identity": identity,
        "file_count": len(tree.files) + len(tree.aliases),
        "source_bytes": sum(item.blob.size for item in tree.files)
        + sum(
            len(item.target.encode("utf-8"))
            for item in tree.aliases
            if item.kind == "symlink"
        ),
    }
    _ISSUED[owner] = record
    token = _CURRENT.set(owner)
    try:
        _original(owner)
        yield owner
        owner.observe()
    finally:
        _CURRENT.reset(token)
        record["active"] = False
        _ISSUED.pop(owner, None)


def _current_layout_execution_observation(root, scope):
    owner = _CURRENT.get()
    record = _original(owner)
    policy = RetainedLayoutSourcePolicy.from_dict(scope)
    if Path(root) != record["root"] or policy != record["policy"]:
        _fail(
            "original_execution_view_required",
            "execution source view belongs to another root or policy",
        )
    return owner.observe()
