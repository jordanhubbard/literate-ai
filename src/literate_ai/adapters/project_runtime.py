"""Fresh contained runtime custody, separate from authored project authority.

Only the original live native reservation admits its exact generated-source root.
Neither a saved path/identity nor a copied Python handle restores that ownership.
"""

from __future__ import annotations

import os
import secrets
import shutil
import sys
import tempfile
import threading
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
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
from .evidence_staging import evidence_staging

_ISSUER = object()
_LIVE = WeakKeyDictionary()
_CURRENT = ContextVar("contained_project_runtime", default=None)
_CURRENT_INSPECTION = ContextVar("contained_project_inspection", default=None)
_CURRENT_EXECUTION = ContextVar("original_inspection_execution", default=None)


@dataclass(frozen=True, slots=True)
class _InspectionScope:
    project: LoadedProject
    stage: object
    parent: Path
    native_parent: Path
    runtime_owner: object
    require_current: object
    execution_lock: object
    closed: object
    receiver: int


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
    runtime_path: Path | None = None
    runtime_node: tuple | None = None
    inspection_children: set = field(default_factory=set)
    inspection_lock: object = field(default_factory=threading.Lock)
    closing: bool = False


class ContainedProjectRuntime:
    __slots__ = ("__weakref__",)

    def __init__(self, issuer):
        if issuer is not _ISSUER:
            raise TypeError("project runtime must be freshly allocated")

    @property
    def path(self):
        state = _state(self)
        return state.runtime_path or state.path

    @property
    def candidate_receipt(self):
        state = _state(self)
        if state.runtime_path is None:
            raise ProjectRuntimeError("nested runtime output custody required")
        return state.path / "candidate.json"

    @property
    def object_root(self):
        state = _state(self)
        if state.runtime_path is None:
            raise ProjectRuntimeError("nested runtime output custody required")
        return state.path / "objects"

    @property
    def identity(self):
        state = _state(self)
        return canonical_identity(
            {
                "schema": "literate-ai/contained-runtime-custody@1",
                "project": str(state.project.root),
                "manifest": state.snapshot.content_identity.uri,
                "path": str(state.path),
                **(
                    {"runtime_path": str(state.runtime_path)}
                    if state.runtime_path is not None
                    else {}
                ),
                "object_node": [stat_identity_value(x) for x in state.object_node],
                "runtime_node": [stat_identity_value(x) for x in state.path_node],
            }
        )

    def close(self, *, keep: bool):
        if type(keep) is not bool:
            raise TypeError("runtime retention must be explicit")
        state = _state(self)
        with state.inspection_lock:
            object.__setattr__(state, "closing", True)
        try:
            try:
                _guard(state)
                with state.inspection_lock:
                    if not keep and state.inspection_children:
                        raise ProjectRuntimeError(
                            "original inspection child retirement is unproven; "
                            "preserve enclosing runtime"
                        )
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
    if (
        state.runtime_path is not None
        and _node(state.runtime_path) != state.runtime_node
    ):
        raise ProjectRuntimeError("nested runtime directory changed")
    WriteReservationSet.verify_all(state.reservation)


def require_project_runtime(owner, project, source_root=None):
    """Check original native custody, never invoke a callback from a claim."""
    state = _state(owner)
    if project != state.project:
        raise ProjectRuntimeError("runtime belongs to a different project")
    _guard(state)
    if source_root is not None:
        if source_root != (state.runtime_path or state.path) / "sources":
            raise ProjectRuntimeError("runtime source coordinate differs")
        require_safe_directory(source_root, allow_missing=True)
    return owner


def allocate_project_runtime(project, *, nested=False):
    """Allocate only a new private namespace under actual contained object state.

    Existing object-directory contents are never adopted, inventoried or deleted.
    Its canonical cache owner independently refuses overlap with declared authority.
    """
    if type(nested) is not bool:
        raise TypeError("nested runtime selection must be boolean")
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
        runtime_path = None
        runtime_node = None
        if nested:
            runtime_path = path / "runtime"
            runtime_path.mkdir()
            runtime_node = _node(runtime_path)
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
            runtime_path,
            runtime_node,
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
        return False
    return True


def require_runtime_candidate(owner, project, path, *, absent=True):
    require_project_runtime(owner, project)
    if path != ContainedProjectRuntime.candidate_receipt.__get__(owner):
        raise ProjectRuntimeError("candidate differs from original runtime custody")
    try:
        path.lstat()
    except FileNotFoundError:
        return path
    if absent:
        raise ProjectRuntimeError("runtime candidate destination is already occupied")
    return path


def current_project_runtime(project=None):
    owner = _CURRENT.get()
    if owner is not None:
        state = _state(owner)
        require_project_runtime(owner, state.project if project is None else project)
    return owner


@contextmanager
def project_inspection_staging(project, *, prefix):
    """Fresh native scratch custody under the original contained project owner.

    A live rebuild runtime supplies its already-held lock and namespace; standalone
    inspection holds the default object lifecycle lock through stage disposal.
    Neither retained metadata nor an ambient path can issue the staging actor.
    """
    if type(project) is not LoadedProject:
        raise TypeError("actual LoadedProject required")
    context = ProjectConfigurationStore.context(project.root)
    snapshot = ProjectConfigurationStore(project.root).read()
    manifest_node = _manifest_node(snapshot.manifest_path)
    if (
        snapshot.definition != project.definition
        or snapshot.definition.framework_directory != "litai"
        or context.root != project.root
        or context.framework_root != project.framework_root
    ):
        raise ProjectRuntimeError("current contained inspection project required")
    owner = current_project_runtime(project)
    enclosing = _CURRENT_INSPECTION.get()
    if enclosing is not None and enclosing.project.root != project.root:
        enclosing = None

    def require_current():
        if enclosing is not None:
            _require_inspection_scope(enclosing)
        if ProjectConfigurationStore.context(project.root) != context:
            raise ProjectRuntimeError("inspection project context changed")
        current = ProjectConfigurationStore(project.root).read()
        if (
            current.content != snapshot.content
            or current.manifest_path != snapshot.manifest_path
            or _manifest_node(current.manifest_path) != manifest_node
        ):
            raise ProjectRuntimeError("inspection project authority changed")
        if owner is not None:
            require_project_runtime(owner, project)

    require_current()
    require_safe_directory(context.framework_root / "_build", allow_missing=True)
    with ExitStack() as locks:
        if enclosing is not None:
            if enclosing.closed.is_set() or enclosing.project != project:
                raise ProjectRuntimeError("original enclosing inspection changed")
            _require_inspection_scope(enclosing)
            parent = enclosing.parent
            native_parent = enclosing.native_parent
            runtime_owner = enclosing.runtime_owner
        elif owner is not None:
            parent = ContainedProjectRuntime.path.__get__(owner)
            native_parent = _state(owner).object_root
            runtime_owner = owner
        else:
            directories = resolve_cache_directories(project.root, environment={})
            from .scaffold_custody import prepare_scaffold_inspection_control

            lock_path = cache_lock_path(
                project.root, directories.obj_dir, "lifecycle.lock"
            )
            prepare_scaffold_inspection_control(
                project.root, directories.obj_dir, lock_path
            )
            locks.enter_context(exclusive_cache_lock(lock_path))
            parent = directories.obj_dir
            native_parent = directories.obj_dir
            runtime_owner = None
        require_current()
        # The original parent registers admission before any child allocation.
        # Only the actual allocator's completed native retirement clears a slot.
        runtime_state = None if runtime_owner is None else _state(runtime_owner)
        child = object()
        if runtime_state is not None:
            with runtime_state.inspection_lock:
                if runtime_state.closing:
                    raise ProjectRuntimeError("enclosing runtime is already closing")
                runtime_state.inspection_children.add(child)
        stage = None
        try:
            with evidence_staging(parent, prefix=prefix) as stage:
                require_current()
                scope = _InspectionScope(
                    project,
                    stage,
                    parent,
                    native_parent,
                    runtime_owner,
                    require_current,
                    threading.Lock(),
                    threading.Event(),
                    os.getpid(),
                )
                token = _CURRENT_INSPECTION.set(scope)
                try:
                    yield stage
                finally:
                    scope.closed.set()
                    original_error = sys.exception()
                    try:
                        require_current()
                    except Exception as error:
                        if original_error is None:
                            raise
                        original_error.add_note(
                            "Inspection project custody changed: " + str(error)
                        )
                    finally:
                        _CURRENT_INSPECTION.reset(token)
        finally:
            if runtime_state is not None and stage is not None and stage.retired:
                with runtime_state.inspection_lock:
                    runtime_state.inspection_children.discard(child)
        require_current()


def _require_inspection_scope(scope):
    from .evidence_staging import EvidenceStage, require_staging_output

    if scope.receiver != os.getpid() or scope.closed.is_set():
        raise ProjectRuntimeError(
            "inspection scope ended or belongs to another process"
        )
    # The allocator captured this original guard; it is never read from a claim.
    scope.require_current()
    require_staging_output(scope.stage, EvidenceStage.path.__get__(scope.stage))


@contextmanager
def project_inspection_execution(owner):
    """Borrow only the original allocating scope's held project mutex.

    A real creator descriptor remains registered for the complete native call,
    so closing the staging scope cannot silently dispose an active execution.
    """
    from .evidence_files import _access
    from .evidence_staging import EvidenceStage

    scope = _CURRENT_INSPECTION.get()
    if scope is None or scope.stage is not owner:
        raise ProjectRuntimeError(
            "original current inspection execution owner required"
        )
    _require_inspection_scope(scope)
    if not scope.execution_lock.acquire(blocking=False):
        raise ProjectRuntimeError("inspection execution is already active")
    try:
        EvidenceStage.verify(owner)
        root = EvidenceStage.path.__get__(owner)
        relative = ".ex-" + secrets.token_hex(4)
        parts = EvidenceStage.prepare(owner, relative)
        try:
            with _access(root) as access:
                descriptor = access.open(
                    parts,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                )
                with EvidenceStage.created(owner, relative, descriptor, access):
                    _require_inspection_scope(scope)
                    execution_token = _CURRENT_EXECUTION.set(
                        (scope, os.getpid(), threading.get_ident())
                    )
                    try:
                        yield
                    finally:
                        _CURRENT_EXECUTION.reset(execution_token)
        finally:
            original_error = sys.exception()
            try:
                _require_inspection_scope(scope)
                EvidenceStage.verify(owner)
            except Exception as error:
                if original_error is None:
                    raise
                original_error.add_note(
                    "Inspection execution closure refused; retained: " + str(error)
                )
    finally:
        scope.execution_lock.release()


def inspection_native_binding(owner):
    scope = _CURRENT_INSPECTION.get()
    execution = _CURRENT_EXECUTION.get()
    if (
        scope is None
        or scope.stage is not owner
        or execution is None
        or execution != (scope, os.getpid(), threading.get_ident())
    ):
        raise ProjectRuntimeError("original allocating inspection execution required")

    def require_current():
        if (
            _CURRENT_EXECUTION.get() is not execution
            or _CURRENT_INSPECTION.get() is not scope
            or (os.getpid(), threading.get_ident()) != execution[1:]
        ):
            raise ProjectRuntimeError("original native inspection execution closed")
        _require_inspection_scope(scope)

    require_current()
    return scope.native_parent, require_current


def require_scoped_runtime_candidate(path):
    owner = current_project_runtime()
    if owner is not None:
        require_runtime_candidate(owner, _state(owner).project, path)


@contextmanager
def project_runtime_scope(owner, project):
    if owner is None:
        token = _CURRENT.set(None)
        try:
            yield
        finally:
            _CURRENT.reset(token)
        return
    require_project_runtime(owner, project)
    # Only separately nested runtime/candidate slots may enter CLI path admission.
    ContainedProjectRuntime.candidate_receipt.__get__(owner)
    token = _CURRENT.set(owner)
    try:
        yield
    finally:
        original_error = sys.exception()
        try:
            require_project_runtime(owner, project)
        except Exception as error:
            if original_error is None:
                raise
            original_error.add_note("Runtime custody changed: " + str(error))
        finally:
            _CURRENT.reset(token)
