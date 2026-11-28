"""Project-scoped lifecycle mutation lock.

Two concurrent Standard rebuilds (or a rebuild racing ``--update-receipt``) can
each pass planning and then race the same project's shared checkpoint and
finalized-receipt publication state, so one later fails an internal
predecessor-contract check after already paying for expensive model-backed
generation. This module gives every project-scoped mutating lifecycle
operation one advisory, cross-platform lock so a second concurrent mutation is
rejected -- with a typed diagnostic naming the current holder -- before either
side starts an expensive model stage. Independent read-only commands (for
example ``status`` or a version check) never take this lock and stay
available while a mutation holds it.

The lock reuses the exact portable primitive already relied on for immutable
local-cache publication (:mod:`literate_ai._cache_lock`): an ``O_CREAT``
lock file guarded by ``fcntl.flock``/``msvcrt.locking`` plus the same
symlink/reparse-point and TOCTOU-safe identity checks. That primitive is
failure-safe by construction -- the OS releases the advisory lock the moment
the holder's process exits or crashes, so a crashed holder can never leave a
permanent stale lock, and no separate PID-file staleness recovery is needed.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager, nullcontext, suppress
from dataclasses import dataclass
from pathlib import Path

from literate_ai._cache_lock import (
    CacheLockError,
    _lock_cleanup_allowed,
    exclusive_cache_lock,
)
from literate_ai.projects import ProjectConfigurationStore

# Reject a contended mutation quickly rather than blocking the caller for the
# duration of a peer's rebuild: the point of this lock is to fail *before*
# either side pays for an expensive model stage, not to queue work silently.
_LIFECYCLE_LOCK_TIMEOUT_SECONDS = 0.0


class ProjectLifecycleLockError(RuntimeError):
    """A project-scoped lifecycle mutation lock could not be acquired safely."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class LifecycleLockHolder:
    """Best-effort diagnostics describing who currently holds the lock."""

    operation: str
    pid: int
    hostname: str
    started_at: float

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "pid": self.pid,
            "hostname": self.hostname,
            "started_at": self.started_at,
        }


def _lock_coordinate(root: Path, framework: Path) -> Path:
    identity = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    return framework / ".litai-locks" / identity / "lifecycle.lock"


def project_lifecycle_lock_path(project_root: Path) -> Path:
    """Return the stable lifecycle-lock path for one project checkout."""

    context = ProjectConfigurationStore.context(Path(project_root).resolve(strict=True))
    return _lock_coordinate(context.root, context.framework_root)


def _owner_path(lock_path: Path) -> Path:
    return lock_path.with_name(lock_path.name + ".owner.json")


def _read_holder(lock_path: Path) -> LifecycleLockHolder | None:
    """Best-effort read of the current holder's diagnostics.

    This is advisory: the owner file is written by the holder after it
    acquires the lock and removed before it releases, so a concurrent reader
    can observe it missing, mid-write, or stale by a moment. Any of those
    just means the diagnostic falls back to "another lifecycle operation" --
    never a correctness dependency.
    """

    try:
        raw = _owner_path(lock_path).read_text(encoding="utf-8")
        data = json.loads(raw)
        return LifecycleLockHolder(
            operation=str(data["operation"]),
            pid=int(data["pid"]),
            hostname=str(data["hostname"]),
            started_at=float(data["started_at"]),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _describe_holder(lock_path: Path) -> str:
    holder = _read_holder(lock_path)
    if holder is None:
        return "another lifecycle operation currently holds the project lock"
    age = max(0.0, time.time() - holder.started_at)
    return (
        f"lifecycle {holder.operation!r} (pid {holder.pid} on {holder.hostname}) "
        f"has held the project lock for {age:.1f}s"
    )


@contextmanager
def project_lifecycle_lock(
    project_root: Path,
    *,
    operation: str,
    timeout_seconds: float = _LIFECYCLE_LOCK_TIMEOUT_SECONDS,
    on_locked: Callable[[], None] | None = None,
    require_path: Callable[[Path], None] | None = None,
    layout_locked: bool = False,
) -> Iterator[None]:
    """Hold the one project-scoped mutating-lifecycle lock for ``operation``.

    Raises :class:`ProjectLifecycleLockError` immediately (no busy-waiting
    beyond ``timeout_seconds``) naming the current holder when another
    mutating lifecycle -- ``rebuild``, ``--update-receipt``, or shared
    checkpoint/cache-index publication -- already holds it. Read-only
    commands never call this and stay available while it is held.

    A caller-supplied path guard is checked before lock and owner-file writes
    and before removing the owner file. The OS handle always closes on exit.
    """

    root = Path(project_root).resolve(strict=True)
    context = ProjectConfigurationStore.context(root)
    contained_git = context.framework_root != context.root and os.path.lexists(
        context.root / ".git"
    )
    if contained_git and any(
        name in os.environ
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")
    ):
        raise ProjectLifecycleLockError(
            "lifecycle.layout_unsafe",
            "Contained lifecycle coordination requires the actual Git worktree",
        )
    reservation = (
        ProjectConfigurationStore.layout_lock(context.root)
        if contained_git and not layout_locked
        else nullcontext()
    )
    lock_path = _lock_coordinate(context.root, context.framework_root)
    owner_path = _owner_path(lock_path)
    if require_path is not None:
        require_path(lock_path)

    def _publish_owner(_descriptor: int) -> None:
        if require_path is not None:
            require_path(owner_path)
        owner_path.write_text(
            json.dumps(
                LifecycleLockHolder(
                    operation=operation,
                    pid=os.getpid(),
                    hostname=socket.gethostname() or platform.node(),
                    started_at=time.time(),
                ).to_dict()
            ),
            encoding="utf-8",
        )
        if on_locked is not None:
            on_locked()

    try:
        with ExitStack() as held:
            with reservation:
                # Select and acquire the old namespace while native publication
                # and removal are excluded. Keep only the lifecycle lock during
                # actual work, so competing operations still refuse promptly.
                if contained_git and ProjectConfigurationStore.context(root) != context:
                    raise ProjectLifecycleLockError(
                        "lifecycle.project_changed",
                        "Native project layout changed before lifecycle acquisition",
                    )
                held.enter_context(
                    exclusive_cache_lock(
                        lock_path,
                        timeout_seconds=timeout_seconds,
                        on_locked=_publish_owner,
                    )
                )
            try:
                yield
            finally:
                if _lock_cleanup_allowed(owner_path, require_path):
                    with suppress(OSError):
                        owner_path.unlink()
    except CacheLockError as exc:
        raise ProjectLifecycleLockError(
            "lifecycle.project_locked",
            "another mutating lifecycle operation is already running against "
            f"this project: {_describe_holder(lock_path)}",
        ) from exc


__all__ = [
    "LifecycleLockHolder",
    "ProjectLifecycleLockError",
    "project_lifecycle_lock",
    "project_lifecycle_lock_path",
]
