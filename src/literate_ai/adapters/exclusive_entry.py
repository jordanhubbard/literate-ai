"""Exclusive native entry movement for a separately authorized transaction.

This cooperative primitive neither grants movement authority nor journals or
rolls back effects. Its caller must hold lifecycle/reservation ownership, full
source byte/topology custody and durable intent before use. On error inspect both
endpoints: an effect followed by a closing conflict is deliberately not undone.
"""

from __future__ import annotations

import errno
import os
import stat
import unicodedata
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai._cache_lock import _default_windows_kernel32
from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.contracts.paths import canonical_relative_posix_path

from .exclusive_directory import _native_rename


@dataclass(frozen=True, slots=True)
class LayoutEntryNode:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int
    changed_ns: int
    links: int
    uid: int
    gid: int
    native_identity: tuple[int, int, int] | None
    link_target: str | None

    @property
    def directory_identity(self) -> tuple:
        if not stat.S_ISDIR(self.mode):
            raise ValueError("layout.move.parent-not-directory")
        return (
            self.device,
            self.inode,
            self.mode,
            self.uid,
            self.gid,
            self.native_identity,
        )

    def after_rename(self) -> LayoutEntryNode:
        # A rename may update ctime; every other observed source fact is retained.
        return replace(self, changed_ns=0)


def _from_stat(node, native_identity=None, link_target=None):
    return LayoutEntryNode(
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
        node.st_nlink,
        node.st_uid,
        node.st_gid,
        native_identity,
        link_target,
    )


def layout_entry_node(path: Path) -> LayoutEntryNode:
    """Observe a direct named node; this is data, not permission to move it."""
    return _entry_node(path, directory_identity_only=False)


def _directory_identity(path: Path) -> tuple:
    """Observe ancestor identity without claiming custody of its children."""
    return _entry_node(path, directory_identity_only=True).directory_identity


def _entry_node(path: Path, *, directory_identity_only: bool) -> LayoutEntryNode:
    path = Path(path)
    require_safe_directory(path.parent)
    node = path.lstat()
    if directory_identity_only and not stat.S_ISDIR(node.st_mode):
        raise ValueError("layout.move.parent-not-directory")
    link = stat.S_ISLNK(node.st_mode)
    if not (stat.S_ISREG(node.st_mode) or stat.S_ISDIR(node.st_mode) or link) or (
        stat_is_link_or_reparse(node) and not link
    ):
        raise ValueError("layout.move.entry-type-unsupported")
    target = None
    if link:
        if node.st_size > 4096:
            raise ValueError("layout.move.link-limit")
        target = os.readlink(path)
        if len(target.encode("utf-8")) > 4096:
            raise ValueError("layout.move.link-limit")
    native = None
    if os.name == "nt":
        kernel = _default_windows_kernel32()
        handle = kernel.open_reparse_aware(str(path))
        try:
            native = kernel.file_identity(handle)
        finally:
            kernel.close(handle)
    before, after = _from_stat(node), _from_stat(path.lstat())
    if directory_identity_only:
        if before.directory_identity != after.directory_identity:
            raise ValueError("layout.move.parent-changed")
    elif before != after:
        raise ValueError("layout.move.entry-changed")
    return _from_stat(node, native, target)


def move_layout_entry_exclusive(
    source: Path,
    destination: Path,
    *,
    expected_source: LayoutEntryNode,
    expected_source_parent: LayoutEntryNode,
    expected_destination_parent: LayoutEntryNode,
    maximum_directory_entries: int = 16384,
    _before_effect=None,
) -> None:
    """Move one expected node without replacement, copying or implicit cleanup.

    File contents and directory descendants are the surrounding live transaction's
    responsibility. Parent handles remain held through closing checks. Same-user
    actors ignoring cooperative reservations can cause an ambiguous post-effect
    conflict; every endpoint is retained for the journal owner's safe recovery.
    """
    source, destination = Path(source), Path(destination)
    if (
        not source.is_absolute()
        or not destination.is_absolute()
        or ".." in source.parts
        or ".." in destination.parts
        or source == destination
        or source.is_relative_to(destination)
        or destination.is_relative_to(source)
        or type(maximum_directory_entries) is not int
        or not 1 <= maximum_directory_entries <= 4_000_000
        or any(
            type(value) is not LayoutEntryNode
            for value in (
                expected_source,
                expected_source_parent,
                expected_destination_parent,
            )
        )
    ):
        raise ValueError("layout.move.arguments-invalid")
    for path in (source, destination):
        canonical_relative_posix_path(path.name, label="layout move entry")
    if (
        len(
            {
                expected_source.device,
                expected_source_parent.device,
                expected_destination_parent.device,
            }
        )
        != 1
    ):
        raise OSError(errno.EXDEV, "layout move requires one filesystem")

    if os.name == "nt":
        identities = (
            expected_source.native_identity,
            expected_source_parent.native_identity,
            expected_destination_parent.native_identity,
        )
        if any(identity is None for identity in identities):
            raise ValueError("layout.move.native-identity-required")
        if len({identity[0] for identity in identities}) != 1:
            raise OSError(errno.EXDEV, "layout move requires one native volume")

    with ExitStack() as stack:
        pinned = {}
        kernel = _default_windows_kernel32() if os.name == "nt" else None
        flags = (
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        flags |= getattr(os, "O_CLOEXEC", 0)
        for parent in (source.parent, destination.parent):
            descriptor = None
            for path in (*reversed(parent.parents), parent):
                if path in pinned:
                    descriptor = pinned[path][0]
                    continue
                current = _directory_identity(path)
                if kernel is None:
                    opened = (
                        os.open(path.anchor, flags)
                        if descriptor is None
                        else os.open(path.name, flags, dir_fd=descriptor)
                    )
                    stack.callback(os.close, opened)
                    actual = _from_stat(os.fstat(opened)).directory_identity
                else:
                    opened = kernel.open_reparse_aware(str(path), share_delete=False)
                    stack.callback(kernel.close, opened)
                    actual = (*current[:-1], kernel.file_identity(opened))
                if current != actual:
                    raise ValueError("layout.move.parent-changed")
                pinned[path] = opened, actual
                descriptor = opened

        def guard():
            for path, (opened, expected) in pinned.items():
                if _directory_identity(path) != expected:
                    raise ValueError("layout.move.parent-changed")
                if kernel is None:
                    actual = _from_stat(os.fstat(opened)).directory_identity
                else:
                    actual = (*expected[:-1], kernel.file_identity(opened))
                if actual != expected:
                    raise ValueError("layout.move.parent-changed")
            if (
                pinned[source.parent][1] != expected_source_parent.directory_identity
                or pinned[destination.parent][1]
                != expected_destination_parent.directory_identity
            ):
                raise ValueError("layout.move.expected-parent-changed")

        guard()
        if layout_entry_node(source) != expected_source:
            raise ValueError("layout.move.source-changed")
        target_key = unicodedata.normalize("NFC", destination.name.casefold())
        for index, entry in enumerate(destination.parent.iterdir()):
            if index >= maximum_directory_entries:
                raise ValueError("layout.move.directory-limit")
            if unicodedata.normalize("NFC", entry.name.casefold()) == target_key:
                raise FileExistsError(
                    errno.EEXIST, "layout move destination exists or aliases"
                )
        guard()
        if layout_entry_node(source) != expected_source:
            raise ValueError("layout.move.source-changed")
        if kernel is None:
            relative = os.stat(
                source.name, dir_fd=pinned[source.parent][0], follow_symlinks=False
            )
            if _from_stat(relative) != replace(
                expected_source, native_identity=None, link_target=None
            ):
                raise ValueError("layout.move.source-changed")
            if _before_effect is not None:
                _before_effect()
            _native_rename(
                pinned[source.parent][0],
                os.fsencode(source.name),
                os.fsencode(destination.name),
                pinned[destination.parent][0],
            )
        else:
            if _before_effect is not None:
                _before_effect()
            os.rename(source, destination)
        guard()
        if os.path.lexists(source):
            raise ValueError("layout.move.source-repopulated")
        if (
            layout_entry_node(destination).after_rename()
            != expected_source.after_rename()
        ):
            raise ValueError("layout.move.destination-changed-after-effect")
        guard()
