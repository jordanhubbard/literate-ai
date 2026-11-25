"""A finite caller-owned port for canonical metadata's physical publication.

The original producers retain planning, locks and input validation. A scoped
writer owns staging, durable intent, replacement and recovery; this dispatcher
supplies no project acknowledgement, qualification or filesystem permission.
Outside a scope the existing atomic writers keep their ordinary implementation.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ScopedAtomicWriter(Protocol):
    def publish(
        self,
        path: Path,
        content: bytes,
        *,
        require_current: Callable[[], None] | None,
        preserve_mode: bool,
    ) -> None: ...


class AtomicPublicationScopeError(RuntimeError):
    """An expired, copied or nested publication scope cannot become a fallback."""


@dataclass(frozen=True, slots=True)
class _Scope:
    writer: ScopedAtomicWriter
    pid: int
    publisher: Callable
    reader: Callable | None
    active: bool = True


_ACTIVE: ContextVar[_Scope | None] = ContextVar(
    "atomic_publication_writer", default=None
)


@contextmanager
def atomic_publication_scope(writer: ScopedAtomicWriter) -> Iterator[None]:
    if _ACTIVE.get() is not None:
        raise AtomicPublicationScopeError(
            "an atomic publication scope is already bound"
        )
    publisher = getattr(writer, "publish", None)
    if not callable(publisher):
        raise TypeError("an actual scoped atomic writer is required")
    reader = getattr(writer, "permits_project_read", None)
    scope = _Scope(writer, os.getpid(), publisher, reader if callable(reader) else None)
    token = _ACTIVE.set(scope)
    try:
        yield
    finally:
        object.__setattr__(scope, "active", False)
        _ACTIVE.reset(token)


def publish_atomic_file_if_scoped(
    path: Path,
    content: bytes,
    *,
    require_current: Callable[[], None] | None = None,
    preserve_mode: bool = False,
) -> bool:
    """Delegate one physical write, or select the unchanged ordinary implementation.

    Once a scope is present, expiration and refusal always raise. They never
    turn a failed journal operation into an unobserved ordinary replacement.
    """
    scope = _ACTIVE.get()
    if scope is None:
        return False
    if not scope.active or scope.pid != os.getpid():
        raise AtomicPublicationScopeError("the original atomic writer scope is closed")
    if (
        not isinstance(path, Path)
        or type(content) is not bytes
        or type(preserve_mode) is not bool
        or (require_current is not None and not callable(require_current))
    ):
        raise TypeError("scoped atomic publication inputs are invalid")
    scope.publisher(
        path,
        content,
        require_current=require_current,
        preserve_mode=preserve_mode,
    )
    return True


def scoped_writer_permits_project_read(root: Path) -> bool:
    """Only the still-live writer may revalidate its own pending project."""
    scope = _ACTIVE.get()
    if scope is None:
        return False
    if not scope.active or scope.pid != os.getpid():
        raise AtomicPublicationScopeError("the original atomic writer scope is closed")
    permit = scope.reader
    return callable(permit) and permit(root) is True


def _scoped_atomic_writer() -> ScopedAtomicWriter | None:
    """Observe the original finite writer for one closed batch of replacements."""
    scope = _ACTIVE.get()
    if scope is None:
        return None
    if not scope.active or scope.pid != os.getpid():
        raise AtomicPublicationScopeError("the original atomic writer scope is closed")
    return scope.writer
