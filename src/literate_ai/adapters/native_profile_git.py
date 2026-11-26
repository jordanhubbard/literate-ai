"""Protect native-profile writes from crossing an independent Git worktree."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from literate_ai._filesystem import UnsafeFilesystemPathError, require_safe_directory


class NativeProfileGitBoundaryError(ValueError):
    """A native-profile path crosses an existing or unobservable Git boundary."""


def require_native_profile_git_boundary(
    root: Path, selected: Iterable[str | Path]
) -> None:
    """Check only selected ancestors below the already established outer root."""
    parents = {
        parent
        for path in selected
        for parent in (root / path).parents
        if parent != root and parent.is_relative_to(root)
    }
    for parent in sorted(parents):
        relative = parent.relative_to(root).as_posix()
        try:
            require_safe_directory(parent, allow_missing=True)
            (parent / ".git").lstat()
        except FileNotFoundError:
            continue
        except (OSError, UnsafeFilesystemPathError) as exc:
            raise NativeProfileGitBoundaryError(
                f"Cannot verify Git ownership at {relative}"
            ) from exc
        # A regular gitfile may name a linked worktree. Even an unsafe marker
        # reserves this boundary. Never open it or resolve its destination.
        raise NativeProfileGitBoundaryError(
            f"Native profile paths cross a nested Git boundary at {relative}"
        )
