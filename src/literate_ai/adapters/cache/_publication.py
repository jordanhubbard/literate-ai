"""Cooperative transactions for one immutable filesystem cache target.

Every operation must cooperate before owned-link rollback is safe. A format
marker is opened read-only and never created, truncated, written, or replaced.
"""

from __future__ import annotations

import errno
import math
import os
import stat
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai import _cache_lock

# Keep Windows' mandatory byte lock outside every valid format marker read.
# The CRT explicitly supports _locking beyond EOF and on _O_RDONLY descriptors:
# https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/locking
_LOCK_OFFSET = 4096
_LOCAL = threading.local()


class CachePublicationLockError(RuntimeError):
    """The immutable lock coordinate or cooperative operation is unavailable."""


def _descriptor_identity(descriptor: int) -> tuple[int, ...]:
    if _cache_lock._is_windows():
        return _cache_lock._default_windows_kernel32().file_identity(
            _cache_lock._default_get_osfhandle(descriptor)
        )
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


def _try_lock(descriptor: int) -> None:
    if _cache_lock._is_windows():
        import msvcrt

        os.lseek(descriptor, _LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(descriptor: int) -> None:
    if _cache_lock._is_windows():
        import msvcrt

        os.lseek(descriptor, _LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(descriptor, fcntl.LOCK_UN)


class _HeldPath:
    """Hold a native identity without denying Windows deletion of owned links."""

    def __init__(self, path: Path) -> None:
        self._kernel = None
        self._descriptor = None
        if _cache_lock._is_windows():
            self._kernel = _cache_lock._default_windows_kernel32()
            self._handle = self._kernel.open_reparse_aware(str(path))
        else:
            self._descriptor = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
            )

    def matches(self, path: Path) -> bool:
        if self._kernel is not None:
            candidate = self._kernel.open_reparse_aware(str(path))
            try:
                return self._kernel.file_identity(
                    candidate
                ) == self._kernel.file_identity(self._handle)
            finally:
                self._kernel.close(candidate)
        return _cache_lock._identity_matches(
            path, path.lstat(), self._descriptor, os.fstat(self._descriptor)
        )

    def close(self) -> None:
        if self._kernel is not None:
            self._kernel.close(self._handle)
        else:
            os.close(self._descriptor)


def _note(error: BaseException, message: str) -> None:
    try:
        BaseException.add_note(error, message)
    except BaseException:
        pass


def _note_cleanup(error: BaseException, label: str, cleanup: BaseException) -> None:
    try:
        _note(error, f"{label}: {cleanup}")
    except BaseException:
        pass


def _close_handles(handles, original_error: BaseException | None) -> None:
    errors = []
    for held in handles:
        if held is not None:
            try:
                held.close()
            except BaseException as error:
                errors.append(error)
    if original_error is not None:
        for error in errors:
            _note_cleanup(original_error, "unretained custody cleanup failed", error)
    elif errors:
        for error in errors[1:]:
            _note_cleanup(errors[0], "additional unretained cleanup failure", error)
        raise errors[0]


@dataclass
class _Operation:
    destination: Path
    held: _HeldPath
    parent: _HeldPath
    backup: Path | None = None
    backup_parent: _HeldPath | None = None


class CachePublicationTransaction:
    """One held target lock with ordered custody of new links and removals."""

    def __init__(
        self,
        marker: Path,
        descriptor: int,
        require_current: Callable[[], None] | None,
    ) -> None:
        self.marker = marker
        self.descriptor = descriptor
        self._require_current = require_current
        self._owner = os.getpid(), threading.get_ident()
        self._operations: list[_Operation] = []
        self._rollback_failed = False
        self._active = True

    def _require_coordinate(self) -> None:
        if not self._active or self._owner != (os.getpid(), threading.get_ident()):
            raise CachePublicationLockError("cache transaction is closed")
        _cache_lock._require_safe_ancestors(self.marker.parent)
        observed = self.marker.lstat()
        original = os.fstat(self.descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or not 0 < original.st_size <= _LOCK_OFFSET
            or not _cache_lock._identity_matches(
                self.marker, observed, self.descriptor, original
            )
        ):
            raise CachePublicationLockError("cache format lock coordinate changed")

    def require_current(self) -> None:
        self._require_coordinate()
        if self._require_current is not None:
            self._require_current()
        self._require_coordinate()

    @property
    def guarded(self) -> bool:
        return self._require_current is not None

    def link(self, temporary: Path, destination: Path) -> bool:
        """Link a prepared file; False means a borrowed, unowned destination.

        The caller must validate exact existing bytes after False, and flush the
        destination directory then call require_current after True. The retained
        descriptor prevents recycling the created file's identity before cleanup.
        """
        self.require_current()
        _cache_lock._require_safe_ancestors(destination.parent)
        held = _HeldPath(temporary)
        parent = None
        retained = False
        operation_error = None
        try:
            observed = temporary.lstat()
            if not stat.S_ISREG(observed.st_mode) or not held.matches(temporary):
                raise CachePublicationLockError("temporary publication file changed")
            parent = _HeldPath(destination.parent)
            self.require_current()
            _cache_lock._require_safe_ancestors(destination.parent)
            if not held.matches(temporary) or not parent.matches(destination.parent):
                raise CachePublicationLockError("publication paths changed before link")
            try:
                os.link(temporary, destination)
            except FileExistsError:
                return False
            self._operations.append(_Operation(destination, held, parent))
            retained = True
            self.require_current()
            return True
        except BaseException as error:
            operation_error = error
            raise
        finally:
            if not retained:
                _close_handles((held, parent), operation_error)

    def remove(
        self, destination: Path, *, staging: Path, require_original_read=None
    ) -> None:
        """Retire one pointer, retaining exact private undo custody if guarded."""
        self.require_current()
        if require_original_read is not None:
            require_original_read()
        if not self.guarded:
            destination.unlink()
            return
        _cache_lock._require_safe_ancestors(destination.parent)
        _cache_lock._require_safe_ancestors(staging)
        held, parent = _HeldPath(destination), None
        backup_parent = None
        retained = False
        operation_error = None
        try:
            if not stat.S_ISREG(destination.lstat().st_mode):
                raise CachePublicationLockError("retired pointer is not regular")
            parent = _HeldPath(destination.parent)
            directory = Path(tempfile.mkdtemp(prefix=".retire-", dir=staging))
            backup_parent = _HeldPath(directory)
            backup = directory / "membership"
            operation = _Operation(destination, held, parent, backup, backup_parent)
            self._operations.append(operation)
            retained = True
            self.require_current()
            if not parent.matches(destination.parent) or not held.matches(destination):
                raise CachePublicationLockError(
                    "retired pointer changed before custody"
                )
            os.link(destination, backup)
            if not held.matches(backup):
                raise CachePublicationLockError("retired pointer undo custody changed")
            from literate_ai.adapters.cache.filesystem import _fsync_directory

            _fsync_directory(directory)
            _fsync_directory(staging)
            self.require_current()
            if not parent.matches(destination.parent) or not held.matches(destination):
                raise CachePublicationLockError(
                    "retired pointer changed before removal"
                )
            destination.unlink()
            _fsync_directory(destination.parent)
            self.require_current()
        except BaseException as error:
            operation_error = error
            raise
        finally:
            if not retained:
                _close_handles((held, parent, backup_parent), operation_error)

    def _rollback(self, original_error: BaseException) -> None:
        # Never consult an expired run here: coordinate and exact file custody,
        # under the still-held cooperative lock, authorize cleanup instead.
        for operation in reversed(self._operations):
            destination, held, parent = (
                operation.destination,
                operation.held,
                operation.parent,
            )
            try:
                self._require_coordinate()
                _cache_lock._require_safe_ancestors(destination.parent)
                if not parent.matches(destination.parent):
                    raise CachePublicationLockError(
                        "owned cache link parent changed; replacement retained"
                    )
                # Import locally to avoid coupling this primitive to store setup.
                from literate_ai.adapters.cache.filesystem import _fsync_directory

                if operation.backup is not None:
                    # The original may still be present if removal never ran.
                    if destination.exists() or destination.is_symlink():
                        if not held.matches(destination):
                            raise CachePublicationLockError(
                                "retired pointer was replaced; replacement retained"
                            )
                        continue
                    if not operation.backup_parent.matches(operation.backup.parent):
                        raise CachePublicationLockError("undo custody parent changed")
                    if not held.matches(operation.backup):
                        raise CachePublicationLockError("undo custody file changed")
                    try:
                        os.link(operation.backup, destination)
                    except FileExistsError:
                        if not held.matches(destination):
                            raise CachePublicationLockError(
                                "retired pointer restore raced; replacement retained"
                            ) from None
                else:
                    try:
                        observed = destination.lstat()
                    except FileNotFoundError:
                        continue
                    if not stat.S_ISREG(observed.st_mode) or not held.matches(
                        destination
                    ):
                        raise CachePublicationLockError(
                            "owned cache link was replaced; replacement retained"
                        )
                    destination.unlink()
                _fsync_directory(destination.parent)
            except BaseException as cleanup_error:
                self._rollback_failed = True
                _note_cleanup(
                    original_error,
                    "cache publication rollback incomplete",
                    cleanup_error,
                )
                for retained in self._operations:
                    if retained.backup is not None:
                        _note(
                            original_error,
                            f"private cache undo custody retained: {retained.backup}",
                        )
                # A failed restore must retain its preceding tombstone. Stop
                # destructive undo and retain private recovery custody as well.
                break

    def _close(self) -> None:
        self._active = False
        errors = []
        for operation in self._operations:
            if operation.backup is not None and not self._rollback_failed:
                try:
                    if not operation.backup_parent.matches(operation.backup.parent):
                        raise CachePublicationLockError("undo custody parent changed")
                    if operation.backup.exists() or operation.backup.is_symlink():
                        if not operation.held.matches(operation.backup):
                            raise CachePublicationLockError("undo custody file changed")
                        operation.backup.unlink()
                    operation.backup.parent.rmdir()
                except BaseException as error:
                    errors.append(error)
            for held in (operation.held, operation.parent, operation.backup_parent):
                if held is not None:
                    try:
                        held.close()
                    except BaseException as error:
                        errors.append(error)
        if errors:
            for extra in errors[1:]:
                _note_cleanup(errors[0], "additional custody cleanup failure", extra)
            raise errors[0]


@contextmanager
def cache_publication_transaction(
    marker: Path,
    *,
    require_current: Callable[[], None] | None = None,
    remaining: Callable[[], float] | None = None,
    select_constraint: Callable[
        [], tuple[Callable[[], None], Callable[[], float]] | None
    ]
    | None = None,
    timeout_seconds: float = 30.0,
) -> Iterator[CachePublicationTransaction]:
    """Serialize cooperating operations without granting filesystem writes.

    Recursive PUBLIC entry, including another instance on the same inode, is
    refused. Internal compound reads must call explicit unlocked helpers while
    holding one transaction. Only guarded attempts undo their owned links;
    omission preserves the legacy partial-publication behavior on failure.

    The final successful currentness check is the commit point. Failures in
    handle cleanup or unlock after that point report cleanup failure and retain
    committed links; rollback is never attempted after custody closes or the
    target lock releases. Callers must record success only after normal exit.
    """
    if (require_current is None) != (remaining is None):
        raise TypeError("a commit constraint requires both currentness and remaining")
    if require_current is not None and (
        not callable(require_current) or not callable(remaining)
    ):
        raise TypeError("commit constraints must be callable")
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("cache lock timeout must be positive")
    path = Path(marker).absolute()
    _cache_lock._require_safe_ancestors(path.parent)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise CachePublicationLockError("cache format marker must be a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    transaction = CachePublicationTransaction(path, descriptor, require_current)
    active = getattr(_LOCAL, "active", None)
    if active is None:
        active = _LOCAL.active = set()
    key = None
    registered = locked = False
    operation_error: BaseException | None = None
    try:
        key = (os.getpid(), *_descriptor_identity(descriptor))
        if key in active:
            raise CachePublicationLockError("recursive public cache operation refused")
        active.add(key)
        registered = True
        if select_constraint is not None:
            if require_current is not None or remaining is not None:
                raise TypeError("select or supply one original commit constraint")
            selected = select_constraint()
            if selected is not None:
                require_current, remaining = selected
                transaction._require_current = require_current
        deadline = time.monotonic() + timeout_seconds
        while True:
            transaction.require_current()
            now = time.monotonic()
            if remaining is not None:
                deadline = min(deadline, now + remaining())
                transaction.require_current()
            if now >= deadline:
                raise CachePublicationLockError("cache publication lock timed out")
            try:
                _try_lock(descriptor)
                locked = True
                break
            except OSError as error:
                if error.errno not in {errno.EACCES, errno.EAGAIN}:
                    raise CachePublicationLockError(
                        "cache publication lock unavailable"
                    ) from error
            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
        transaction.require_current()
        yield transaction
        transaction.require_current()
    except BaseException as error:
        operation_error = error
        if locked and require_current is not None:
            transaction._rollback(error)
        raise
    finally:
        try:
            try:
                transaction._close()
            except BaseException as cleanup_error:
                if operation_error is None:
                    operation_error = cleanup_error
                    raise
                _note_cleanup(
                    operation_error,
                    "cache ownership descriptor cleanup failed",
                    cleanup_error,
                )
        finally:
            try:
                if locked:
                    _unlock(descriptor)
            except BaseException as cleanup_error:
                if operation_error is None:
                    operation_error = cleanup_error
                    raise
                _note_cleanup(
                    operation_error, "cache lock release failed", cleanup_error
                )
            finally:
                if registered:
                    active.discard(key)
                try:
                    os.close(descriptor)
                except BaseException as cleanup_error:
                    if operation_error is None:
                        raise
                    _note_cleanup(
                        operation_error, "cache lock close failed", cleanup_error
                    )
