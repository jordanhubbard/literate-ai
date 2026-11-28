"""Migration leaf I/O; original owners remain live and the caller owns its journal.

Windows file fsync is retained. Windows directory checks below certify current
namespace identity, NOT POSIX permission bits or power-loss-durable renames.
This helper does not enable migration on an unsupported platform.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse


def _windows():
    return os.name == "nt"


def _read(path, *, maximum_bytes, fail, stamp):
    require_safe_directory(path.parent)
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or stat_is_link_or_reparse(before)
        or before.st_nlink != 1
        or before.st_size > maximum_bytes
    ):
        fail("path_unsafe", f"migration requires bounded direct file {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if stamp(os.fstat(stream.fileno())) != stamp(before):
            fail(
                "plan_stale", f"migration file changed before observation: {path.name}"
            )
        content = stream.read(maximum_bytes + 1)
    if stamp(path.lstat()) != stamp(before) or len(content) != before.st_size:
        fail("plan_stale", f"migration file changed during observation: {path.name}")
    return (
        [before.st_dev, before.st_ino, before.st_mode],
        content,
        stat.S_IMODE(before.st_mode),
    )


def read_migration_file(path: Path, *, maximum_bytes, fail, stamp):
    """Return the existing wire identity; add native Windows custody, not a new ID."""
    path = Path(path)
    if not _windows():
        return _read(path, maximum_bytes=maximum_bytes, fail=fail, stamp=stamp)
    from literate_ai._cache_lock import _Kernel32Windows
    from literate_ai.adapters.qualification_workspace_namespace import (
        hold_qualification_workspace_namespace,
    )

    # Ancestors are held before the first leaf metadata/read access. Keeping the
    # original leaf handle with no-write/no-delete sharing also excludes a
    # same-size, restored-timestamp writer, not merely name substitution.
    with hold_qualification_workspace_namespace(path.parent, read_only=True) as current:
        kernel = _Kernel32Windows()
        handle = kernel.open_reparse_aware(
            str(path), share_delete=False, share_write=False
        )
        try:
            original = kernel.file_identity(handle)
            current()
            result = _read(path, maximum_bytes=maximum_bytes, fail=fail, stamp=stamp)
            probe = kernel.open_reparse_aware(
                str(path), share_delete=False, share_write=False
            )
            try:
                if (
                    kernel.file_identity(probe) != original
                    or kernel.file_identity(handle) != original
                ):
                    fail("plan_stale", f"migration native file changed: {path.name}")
            finally:
                kernel.close(probe)
            current()
            return result
        finally:
            kernel.close(handle)


def write_migration_file(path: Path, content: bytes, mode: int = 0o600) -> None:
    """Create only a fresh owned journal leaf; keep failed originals for recovery."""
    path = Path(path)
    if not _windows():
        # Preserve the original POSIX order, flags and error behavior.
        with path.open("xb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return
    import msvcrt

    from literate_ai._cache_lock import _Kernel32Windows
    from literate_ai.adapters.qualification_workspace_namespace import (
        hold_qualification_workspace_namespace,
    )

    # Writable parent namespace custody permits child creation, but denies
    # ancestor deletion/rename. The new leaf stays open throughout publication.
    with hold_qualification_workspace_namespace(path.parent) as current:
        current()
        with path.open("xb") as stream:
            kernel = _Kernel32Windows()
            original = kernel.file_identity(msvcrt.get_osfhandle(stream.fileno()))
            handle = kernel.open_reparse_aware(str(path), share_delete=False)
            try:
                if kernel.file_identity(handle) != original:
                    raise ValueError("migration journal native file changed")
                current()
                # Windows chmod represents read-only, not POSIX ACL/mode bits.
                os.chmod(path, mode)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
                node = path.lstat()
                if (
                    stat_is_link_or_reparse(node)
                    or not stat.S_ISREG(node.st_mode)
                    or node.st_nlink != 1
                    or node.st_size != len(content)
                    or bool(node.st_mode & stat.S_IWRITE) != bool(mode & stat.S_IWRITE)
                    or kernel.file_identity(handle) != original
                    or kernel.file_identity(msvcrt.get_osfhandle(stream.fileno()))
                    != original
                ):
                    raise ValueError("migration journal native file changed")
                current()
            finally:
                kernel.close(handle)


def flush_migration_directory(directory: Path) -> None:
    """POSIX fsync; Windows original namespace check, with no durability claim."""
    if not _windows():
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return
    from literate_ai.adapters.qualification_workspace_namespace import (
        hold_qualification_workspace_namespace,
    )

    # As in ProjectConfigurationStore publication, Windows cannot fsync an
    # ordinary directory descriptor. Journal contents were fsynced separately.
    # Whole-operation admission must decide the supported crash-consistency
    # contract; this leaf helper cannot certify it by swallowing an OS error.
    with hold_qualification_workspace_namespace(directory, read_only=True) as current:
        current()
