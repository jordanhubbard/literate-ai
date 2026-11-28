"""Original acquired project-layout leases; serialized data is never reentrancy."""

from __future__ import annotations

import hashlib
import os
import stat
import threading
import weakref
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from literate_ai._cache_lock import _identity_matches
from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    require_safe_directory,
    stat_is_link_or_reparse,
)


class ProjectLayoutLeaseError(ValueError):
    pass


_KEY = object()
_CURRENT = ContextVar("original_project_layout_leases", default=())
_LIVE = {}


def native_directory_identity(path):
    """Current physical data, not ownership; caller retains its original scope."""
    try:
        require_safe_directory(path)
    except UnsafeFilesystemPathError as error:
        raise ProjectLayoutLeaseError(
            "original layout directory unavailable or unsafe"
        ) from error
    before = path.lstat()
    if os.name == "nt":
        from literate_ai._cache_lock import _Kernel32Windows

        kernel = _Kernel32Windows()
        handle = kernel.open_reparse_aware(str(path))
        try:
            native = kernel.file_identity(handle)
        finally:
            kernel.close(handle)
    else:
        native = (before.st_dev, before.st_ino)
    closing = path.lstat()
    if (
        stat_is_link_or_reparse(closing)
        or not stat.S_ISDIR(closing.st_mode)
        or (before.st_dev, before.st_ino, before.st_mode)
        != (closing.st_dev, closing.st_ino, closing.st_mode)
    ):
        raise ProjectLayoutLeaseError("original layout directory changed")
    return tuple(native), closing.st_mode


def _git_marker(root):
    marker = root / ".git"
    try:
        before = marker.lstat()
    except FileNotFoundError:
        return None
    if stat_is_link_or_reparse(before):
        raise ProjectLayoutLeaseError("original Git marker redirected")
    if stat.S_ISDIR(before.st_mode):
        return "directory", native_directory_identity(marker)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ProjectLayoutLeaseError("original Git marker unsafe")
    descriptor = os.open(
        marker, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        opened = os.fstat(descriptor)
        if not _identity_matches(marker, before, descriptor, opened):
            raise ProjectLayoutLeaseError("original Git marker changed")
        digest, remaining = hashlib.sha256(), opened.st_size
        while remaining:
            block = os.read(descriptor, min(remaining, 65536))
            if not block:
                raise ProjectLayoutLeaseError("original Git marker changed")
            digest.update(block)
            remaining -= len(block)
        if os.read(descriptor, 1):
            raise ProjectLayoutLeaseError("original Git marker changed")
        after, closing = os.fstat(descriptor), marker.lstat()
        if (
            stat_is_link_or_reparse(closing)
            or (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
            != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            or not _identity_matches(marker, closing, descriptor, after)
        ):
            raise ProjectLayoutLeaseError("original Git marker changed")
        return (
            "file",
            (closing.st_dev, closing.st_ino, closing.st_mode),
            digest.digest(),
        )
    finally:
        os.close(descriptor)


@dataclass
class _State:
    root: Path
    root_identity: object
    parent_identity: object
    lock_path: Path
    descriptor: int
    marker: object
    pid: int
    thread: int
    active: bool = True


class _Lease:
    __slots__ = ("__weakref__",)

    def __new__(cls, key=None):
        if key is not _KEY:
            raise TypeError("original acquired layout lease required")
        return super().__new__(cls)

    def __reduce__(self):
        raise TypeError("layout lease cannot be serialized")


def require_layout_lease(lease, root):
    if type(lease) is not _Lease:
        raise ProjectLayoutLeaseError("original layout lease required")
    pair = _LIVE.get(id(lease))
    state = None if pair is None or pair[0]() is not lease else pair[1]
    if (
        state is None
        or not state.active
        or state.root != Path(root)
        or state.pid != os.getpid()
        or state.thread != threading.get_ident()
    ):
        raise ProjectLayoutLeaseError("original layout lease expired or differs")
    if (
        native_directory_identity(state.root) != state.root_identity
        or native_directory_identity(state.lock_path.parent) != state.parent_identity
    ):
        raise ProjectLayoutLeaseError("original layout namespace changed")
    if _git_marker(state.root) != state.marker:
        raise ProjectLayoutLeaseError("original Git binding changed")
    observed = state.lock_path.lstat()
    opened = os.fstat(state.descriptor)
    if (
        stat_is_link_or_reparse(observed)
        or not stat.S_ISREG(observed.st_mode)
        or observed.st_nlink != 1
        or not _identity_matches(state.lock_path, observed, state.descriptor, opened)
    ):
        raise ProjectLayoutLeaseError("original layout lock descriptor changed")


def current_layout_lease(root):
    """Return only a genuine still-active original FD owner for this same root."""
    for lease in reversed(_CURRENT.get()):
        pair = _LIVE.get(id(lease))
        state = None if pair is None or pair[0]() is not lease else pair[1]
        if state is None:
            raise ProjectLayoutLeaseError("layout lease registry changed")
        if state.root == Path(root):
            require_layout_lease(lease, root)
            return lease
    return None


def _note(primary, error):
    try:
        BaseException.add_note(
            primary, "layout closing refusal: " + type(error).__name__
        )
    except BaseException:
        pass


@contextmanager
def acquired_layout_lease(root, lock_path, descriptor, *, _origin=None):
    """Called ONLY inside original _lock after actual exclusive acquisition.

    A lease registry entry retains the acquired original FD; path or JSON fields
    cannot satisfy current_layout_lease. Expiration precedes actual OS unlocking.
    """
    from literate_ai.projects import (
        _LAYOUT_ACQUIRED_LEASE_KEY,
        ProjectConfigurationStore,
    )

    if _origin is not _LAYOUT_ACQUIRED_LEASE_KEY:
        raise ProjectLayoutLeaseError("original acquired layout origin required")
    root, lock_path = Path(root), Path(lock_path)
    directory = ProjectConfigurationStore.layout_metadata_directory(root)
    expected = (directory or root) / ".literate-layout.write.lock"
    if lock_path != expected:
        raise ProjectLayoutLeaseError("not the actual root layout coordination file")
    lease = _Lease(_KEY)
    state = _State(
        root,
        native_directory_identity(root),
        native_directory_identity(lock_path.parent),
        lock_path,
        descriptor,
        _git_marker(root),
        os.getpid(),
        threading.get_ident(),
    )
    _LIVE[id(lease)] = (weakref.ref(lease), state)
    token = _CURRENT.set((*_CURRENT.get(), lease))
    try:
        require_layout_lease(lease, root)
        try:
            yield lease
        except BaseException as primary:
            try:
                require_layout_lease(lease, root)
            except BaseException as error:
                _note(primary, error)
            raise
        else:
            require_layout_lease(lease, root)
    finally:
        state.active = False
        _CURRENT.reset(token)
        _LIVE.pop(id(lease), None)
