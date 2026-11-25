"""Original store namespaces: pre-create mutation guards, separate physical fences.

No normal store is retargeted after metadata movement. Missing/changed original
roots, context or optional authoring refuse before cache-lock parent creation.
"""

from __future__ import annotations

import hashlib
import os
import stat
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai._cache_lock import _identity_matches
from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    require_safe_directory,
    stat_is_link_or_reparse,
)
from literate_ai.adapters.project_layout_lease import (
    ProjectLayoutLeaseError,
)
from literate_ai.adapters.project_layout_lease import (
    native_directory_identity as _native_directory_identity,
)


class ComponentNamespaceError(ValueError):
    pass


_BOUND = {}


def _directory_identity(path):
    try:
        return _native_directory_identity(path)
    except (UnsafeFilesystemPathError, ProjectLayoutLeaseError, OSError) as error:
        raise ComponentNamespaceError(
            "original Component directory unavailable"
        ) from error


def _file_witness(path):
    """Read one metadata leaf under its original physical/byte witness.

    Original publication may pin this read-only input with hardlinks. Reading
    it grants no relocation or disposal; those owners retain their independent
    alias closure checks. Every read still closes exact native/stat/byte state.
    """
    try:
        require_safe_directory(path.parent)
    except UnsafeFilesystemPathError as error:
        raise ComponentNamespaceError(
            "original Component metadata ancestry unsafe"
        ) from error
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if stat_is_link_or_reparse(before) or not stat.S_ISREG(before.st_mode):
        raise ComponentNamespaceError(
            f"original Component metadata is not direct: {path.name}; "
            f"links={before.st_nlink}"
        )
    flags = (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not _identity_matches(path, before, descriptor, opened):
            raise ComponentNamespaceError("Component metadata changed before open")
        if os.name == "nt":
            import msvcrt

            from literate_ai._cache_lock import _Kernel32Windows

            native = tuple(
                _Kernel32Windows().file_identity(msvcrt.get_osfhandle(descriptor))
            )
        else:
            native = (opened.st_dev, opened.st_ino)
        digest, remaining = hashlib.sha256(), opened.st_size
        while remaining:
            block = os.read(descriptor, min(remaining, 65536))
            if not block:
                raise ComponentNamespaceError("Component metadata changed during read")
            digest.update(block)
            remaining -= len(block)
        if os.read(descriptor, 1):
            raise ComponentNamespaceError("Component metadata grew during read")
        after, closing = os.fstat(descriptor), path.lstat()

        def signature(node):
            return (
                node.st_dev,
                node.st_ino,
                node.st_mode,
                node.st_size,
                node.st_mtime_ns,
                node.st_ctime_ns,
                node.st_nlink,
            )

        if (
            stat_is_link_or_reparse(closing)
            or signature(opened) != signature(after)
            or signature(before) != signature(closing)
            or not _identity_matches(path, closing, descriptor, after)
        ):
            raise ComponentNamespaceError("Component metadata changed while closing")
        return native, closing.st_mode, digest.digest()
    finally:
        os.close(descriptor)


def _project(root):
    from literate_ai.projects import ProjectConfigurationStore

    try:
        snapshot = ProjectConfigurationStore.discover(root)
    except (OSError, ValueError) as error:
        raise ComponentNamespaceError(
            "original project context is unavailable"
        ) from error
    if snapshot is None:
        return None
    return (
        snapshot.root,
        snapshot.manifest_path,
        _directory_identity(snapshot.root),
        _directory_identity(snapshot.manifest_path.parent),
        _file_witness(snapshot.manifest_path),
        snapshot.content,
    )


@dataclass(frozen=True)
class _State:
    store_type: type
    pointers: tuple
    root: Path
    root_identity: object
    ancestry: tuple
    project: object
    authoring: object


def _origin(store):
    from literate_ai.adapters.component_locks import (
        _COMPONENT_NAMESPACE_ORIGIN as lock_origin,
    )
    from literate_ai.adapters.component_resolution_audits import (
        _COMPONENT_NAMESPACE_ORIGIN as audit_origin,
    )

    for cls, bases, mro, members in (lock_origin, audit_origin):
        if type(store) is cls:
            # Raw type access precedes every instance descriptor or field read.
            # Class dictionary seals alone do not constrain inherited descriptors.
            if (
                type.__getattribute__(cls, "__bases__") is not bases
                or type.__getattribute__(cls, "__mro__") is not mro
            ):
                raise ComponentNamespaceError("original store class ancestry changed")
            namespace = type.__getattribute__(cls, "__dict__")
            if any(namespace.get(name) is not original for name, original in members):
                raise ComponentNamespaceError("original store field descriptor changed")
            descriptor = dict(members)["__dict__"]
            return cls, descriptor.__get__(store, cls)
    raise ComponentNamespaceError("actual original Component store required")


def _pointers(store):
    _, values = _origin(store)
    names = ("root", "storage_root", "path", "write_lock_path")
    if "operation_lock_path" in values:
        names += ("operation_lock_path",)
    if "target_name" in values:
        names += ("target_name",)
    return tuple((name, values[name]) for name in names)


def bind_component_namespace(store):
    """Constructor-only observation; registration is not restored from a dict."""
    identity = id(store)
    if identity in _BOUND:
        raise ComponentNamespaceError("original store namespace already bound")
    cls, values = _origin(store)
    pointers = _pointers(store)
    root = values["root"]
    before = _directory_identity(root)
    ancestry = tuple((parent, _directory_identity(parent)) for parent in root.parents)
    authoring = _file_witness(root / "component.md")
    project = _project(root)
    if (
        _directory_identity(root) != before
        or _file_witness(root / "component.md") != authoring
        or any(
            now is not original
            for (_, now), (_, original) in zip(_pointers(store), pointers, strict=True)
        )
    ):
        raise ComponentNamespaceError("Component namespace changed during binding")
    state = _State(cls, pointers, root, before, ancestry, project, authoring)

    def expired(reference):
        if _BOUND.get(identity, (None,))[0] is reference:
            _BOUND.pop(identity, None)

    _BOUND[identity] = (weakref.ref(store, expired), state)
    require_component_physical_current(store)


def _state(store):
    pair = _BOUND.get(id(store))
    if pair is None or pair[0]() is not store or type(store) is not pair[1].store_type:
        raise ComponentNamespaceError("actual original Component store required")
    state = pair[1]
    current = _pointers(store)
    if len(current) != len(state.pointers) or any(
        name != original_name or value is not original
        for (name, value), (original_name, original) in zip(
            current, state.pointers, strict=True
        )
    ):
        raise ComponentNamespaceError("original Component store pointers changed")
    return state


def require_component_physical_current(store):
    """Data fences may span planned metadata changes, never a root replacement."""
    state = _state(store)
    try:
        identity = _directory_identity(state.root)
    except (OSError, ValueError) as error:
        raise ComponentNamespaceError(
            "original Component directory unavailable"
        ) from error
    if identity != state.root_identity:
        raise ComponentNamespaceError("original Component directory replaced")
    for parent, original in state.ancestry:
        if _directory_identity(parent) != original:
            raise ComponentNamespaceError("original Component ancestry changed")


def require_component_mutation_current(store):
    state = _state(store)
    require_component_physical_current(store)
    if (
        _file_witness(state.root / "component.md") != state.authoring
        or _project(state.root) != state.project
    ):
        raise ComponentNamespaceError(
            "original Component authoring/context retired or changed"
        )
    require_component_physical_current(store)


@contextmanager
def component_mutation_gate(store):
    """Keep the genuine existing project-layout gate before ANY creating open."""
    state = _state(store)
    require_component_mutation_current(store)
    if state.project is None:
        # Standalone data stores have no derived-project layout transaction.
        yield
        require_component_mutation_current(store)
        return
    from literate_ai.projects import ProjectConfigurationStore

    with ProjectConfigurationStore.layout_lock(state.project[0]):
        require_component_mutation_current(store)
        yield
        require_component_mutation_current(store)


def original_component_namespace_identity(store):
    """Return recorded original namespace data without I/O or currentness grants.

    A consumer must join this data to its independently admitted project before
    opening the physical owner. Planned metadata changes do not rebind a store.
    """
    state = _state(store)
    return state.root, state.root_identity


def original_component_physical_binding(store):
    """Live original physical witness for a distinct data-closing owner only."""
    require_component_physical_current(store)
    state = _state(store)
    return state.root, state.root_identity
