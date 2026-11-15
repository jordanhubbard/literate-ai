"""No-follow POSIX source reads and canonical closed link inventories."""

from __future__ import annotations

import hashlib
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from literate_ai.contracts import SourceEntry, SourceEntryType
from literate_ai.contracts.internal_links import validate_internal_symlink_closure
from literate_ai.contracts.paths import canonical_relative_posix_path


def _stamp(value):
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


@contextmanager
def source_parent(root: Path, relative: str):
    """Hold and revalidate every ancestor, including ancestors of the root."""
    if os.name == "nt":
        raise ValueError("Internal source links require a POSIX worker")
    canonical_relative_posix_path(relative, label="source input")
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("Source input root must be an absolute canonical path")
    path = root / relative
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    handles = []
    try:
        descriptor = os.open(path.anchor, flags)
        handles.append((None, path.anchor, descriptor, _stamp(os.fstat(descriptor))))
        for name in path.parts[1:-1]:
            before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            child = os.open(name, flags, dir_fd=descriptor)
            handles.append((descriptor, name, child, _stamp(before)))
            if _stamp(os.fstat(child)) != _stamp(before):
                raise ValueError("Source ancestor changed during open")
            descriptor = child
        yield descriptor, path.name
        for parent, name, child, expected in handles:
            actual = os.stat(name, dir_fd=parent, follow_symlinks=False)
            # Directory children can be created by unrelated callers. Custody is
            # the current no-follow directory identity, not directory mtime.
            if (actual.st_dev, actual.st_ino, actual.st_mode) != expected[:3]:
                raise ValueError("Source ancestor changed during read")
            opened = os.fstat(child)
            if (opened.st_dev, opened.st_ino, opened.st_mode) != expected[:3]:
                raise ValueError("Source ancestor changed during read")
    finally:
        for _, _, descriptor, _ in reversed(handles):
            os.close(descriptor)


def read_source_entry(
    root: Path, relative: str, *, symlink: bool, output=None, executable=None
):
    """Read link text or regular bytes with stable leaf and ancestor identities."""
    with source_parent(root, relative) as (parent, name):
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if symlink:
            if not stat.S_ISLNK(before.st_mode) or before.st_size > 4096:
                raise ValueError("Source link kind or size changed")
            data = os.readlink(name, dir_fd=parent).encode("utf-8")
            if len(data) > 4096:
                raise ValueError("Source link exceeds target byte bound")
            result = hashlib.sha256(data).hexdigest(), len(data), data
        else:
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("Source entry is not a regular file")
            if executable is not None and bool(before.st_mode & 0o111) != executable:
                raise ValueError("Source executable mode changed")
            descriptor = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            digest, size, prefix = hashlib.sha256(), 0, bytearray()
            with os.fdopen(descriptor, "rb") as stream:
                if _stamp(os.fstat(stream.fileno())) != _stamp(before):
                    raise ValueError("Source file changed during open")
                while chunk := stream.read(1024 * 1024):
                    if output is not None:
                        output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                    if len(prefix) < 1024:
                        prefix.extend(chunk[: 1024 - len(prefix)])
                if _stamp(os.fstat(stream.fileno())) != _stamp(before):
                    raise ValueError("Source file changed during read")
            if size != before.st_size:
                raise ValueError("Source file size changed during read")
            result = digest.hexdigest(), size, bytes(prefix)
        if _stamp(os.stat(name, dir_fd=parent, follow_symlinks=False)) != _stamp(
            before
        ):
            raise ValueError("Source entry changed during read")
        return result


def validate_source_links(entries: tuple[SourceEntry, ...], targets: dict[str, str]):
    """Use the retained-input validator over source entries and implied directories."""
    names = {entry.path for entry in entries}
    if len(names) != len(entries):
        raise ValueError("Duplicate source entries in link namespace")
    directories = {"."}
    for name in names:
        parent = name.rpartition("/")[0]
        while parent:
            if parent in names:
                raise ValueError("Source entry traverses a link or file ancestor")
            directories.add(parent)
            parent = parent.rpartition("/")[0]
    expected = {e.path for e in entries if e.entry_type is SourceEntryType.SYMLINK}
    if expected != set(targets):
        raise ValueError("Source link target inventory differs from captured entries")
    return validate_internal_symlink_closure(targets, names | directories, directories)
