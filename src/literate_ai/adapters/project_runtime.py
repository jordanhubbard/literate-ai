"""Fresh contained runtime custody, separate from authored project authority.

Only the original live native reservation admits its exact generated-source root.
Neither a saved path/identity nor a copied Python handle restores that ownership.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from weakref import WeakKeyDictionary

from literate_ai._cache_lock import cache_lock_path, exclusive_cache_lock
from literate_ai._filesystem import (
    ensure_safe_directory,
    require_safe_directory,
    stat_identity_value,
)
from literate_ai.cache_directories import resolve_cache_directories
from literate_ai.contracts import canonical_identity
from literate_ai.projects import LoadedProject, ProjectConfigurationStore

from ._write_reservations import (
    WriteReservationSet,
    WriteReservationTarget,
    acquire_write_reservations,
)

_ISSUER = object()
_LIVE = WeakKeyDictionary()


class ProjectRuntimeError(ValueError):
    """The actual current project/runtime owner is absent or changed."""


def _node(path):
    require_safe_directory(path)
    node = path.lstat()
    return node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid


def _manifest_node(path):
    node = path.lstat()
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
    )


@dataclass(frozen=True, slots=True)
class _RuntimeState:
    project: LoadedProject
    snapshot: object
    context: object
    object_root: Path
    object_node: tuple
    path: Path
    path_node: tuple
    manifest_node: tuple
    reservation: WriteReservationSet
    stack: ExitStack
    cache_stack: ExitStack


class ContainedProjectRuntime:
    __slots__ = ("__weakref__",)

    def __init__(self, issuer):
        if issuer is not _ISSUER:
            raise TypeError("project runtime must be freshly allocated")

    @property
    def path(self):
        return _state(self).path

    @property
    def identity(self):
        state = _state(self)
        return canonical_identity(
            {
                "schema": "literate-ai/contained-runtime-custody@1",
                "project": str(state.project.root),
                "manifest": state.snapshot.content_identity.uri,
                "path": str(state.path),
                "object_node": [stat_identity_value(x) for x in state.object_node],
                "runtime_node": [stat_identity_value(x) for x in state.path_node],
            }
        )

    def close(self, *, keep: bool):
        if type(keep) is not bool:
            raise TypeError("runtime retention must be explicit")
        state = _state(self)
        try:
            try:
                _guard(state)
            finally:
                # Retire the handle and close original reservation descriptors
                # even on conflicts. Keep the object-cache lock through deletion.
                del _LIVE[self]
                state.stack.close()
            if not keep:
                if _node(state.path) != state.path_node:
                    raise ProjectRuntimeError("runtime replaced before cleanup")
                shutil.rmtree(state.path)
        finally:
            state.cache_stack.close()


def _state(owner):
    if type(owner) is not ContainedProjectRuntime:
        raise ProjectRuntimeError("original live project runtime required")
    state = _LIVE.get(owner)
    if state is None:
        raise ProjectRuntimeError("project runtime is not original and live")
    return state


def _guard(state):
    try:
        _guard_inputs(state)
    except ProjectRuntimeError:
        raise
    except (ValueError, OSError, RuntimeError) as exc:
        raise ProjectRuntimeError(
            "runtime native custody is unavailable or changed"
        ) from exc


def _guard_inputs(state):
    if ProjectConfigurationStore.context(state.project.root) != state.context:
        raise ProjectRuntimeError("runtime project context changed")
    current = ProjectConfigurationStore(state.project.root).read()
    if (
        current.content != state.snapshot.content
        or current.manifest_path != state.snapshot.manifest_path
        or _manifest_node(current.manifest_path) != state.manifest_node
        or current.definition != state.project.definition
    ):
        raise ProjectRuntimeError("runtime project authority changed")
    if _node(state.object_root) != state.object_node:
        raise ProjectRuntimeError("runtime object directory changed")
    directories = resolve_cache_directories(state.project.root, environment={})
    if (
        directories.obj_dir != state.object_root
        or _node(state.object_root) != state.object_node
        or _node(state.path) != state.path_node
    ):
        raise ProjectRuntimeError("runtime native directory custody changed")
    WriteReservationSet.verify_all(state.reservation)


def require_project_runtime(owner, project, source_root=None):
    """Check original native custody, never invoke a callback from a claim."""
    state = _state(owner)
    if project != state.project:
        raise ProjectRuntimeError("runtime belongs to a different project")
    _guard(state)
    if source_root is not None:
        if source_root != state.path / "sources":
            raise ProjectRuntimeError("runtime source coordinate differs")
        require_safe_directory(source_root, allow_missing=True)
    return owner


def allocate_project_runtime(project):
    """Allocate only a new private namespace under actual contained object state.

    Existing object-directory contents are never adopted, inventoried or deleted.
    Its canonical cache owner independently refuses overlap with declared authority.
    """
    if type(project) is not LoadedProject:
        raise TypeError("actual LoadedProject required")
    context = ProjectConfigurationStore.context(project.root)
    snapshot = ProjectConfigurationStore(project.root).read()
    if (
        snapshot.definition != project.definition
        or snapshot.definition.framework_directory != "litai"
        or context.root != project.root
        or context.framework_root != project.framework_root
    ):
        raise ProjectRuntimeError("current contained project authority required")
    # Refuse redirected object ancestry before the resolver can follow it.
    require_safe_directory(context.framework_root / "_build", allow_missing=True)
    directories = resolve_cache_directories(project.root, environment={})
    stack = ExitStack()
    cache_stack = ExitStack()
    try:
        cache_stack.enter_context(
            exclusive_cache_lock(
                cache_lock_path(project.root, directories.obj_dir, "lifecycle.lock")
            )
        )
        ensure_safe_directory(directories.obj_dir)
        object_node = _node(directories.obj_dir)
        path = Path(tempfile.mkdtemp(prefix=".rt-", dir=directories.obj_dir))
        path_node = _node(path)
        reservation = stack.enter_context(
            acquire_write_reservations(
                (WriteReservationTarget(path / ".runtime.write", path, path_node[:3]),)
            )
        )
        state = _RuntimeState(
            project,
            snapshot,
            context,
            directories.obj_dir,
            object_node,
            path,
            path_node,
            _manifest_node(snapshot.manifest_path),
            reservation,
            stack,
            cache_stack,
        )
        _guard(state)
        owner = ContainedProjectRuntime(_ISSUER)
        _LIVE[owner] = state
        return owner
    except BaseException:
        # Preserve partially created namespaces on refusal; no path-only cleanup.
        try:
            stack.close()
        finally:
            cache_stack.close()
        raise


def close_project_runtime(owner, *, keep):
    """Retire original custody without hiding an active rebuild rejection."""
    active_error = sys.exception()
    try:
        ContainedProjectRuntime.close(owner, keep=keep)
    except Exception as cleanup_error:
        if active_error is None:
            raise
        active_error.add_note(
            "Contained runtime custody retired; conflicting runtime state preserved: "
            + str(cleanup_error)
        )
