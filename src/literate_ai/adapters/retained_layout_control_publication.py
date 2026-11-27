"""Journal known private control nodes before exclusive public publication.

This POSIX dependency supplies point-in-time node facts, not project/Git roles,
reservation ownership, source movement or recovery authorization. The actual
transaction must compose those owners. All nodes survive ambiguous failures.
"""

from __future__ import annotations

import os
import stat
import threading
import unicodedata
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from uuid import uuid4
from weakref import WeakKeyDictionary

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.paths import canonical_relative_posix_path

from .exclusive_entry import (
    LayoutEntryNode,
    _from_stat,
    layout_entry_node,
    move_layout_entry_exclusive,
)
from .retained_layout_journal import _directory, _LayoutJournalWriter
from .retained_layout_partition import _physical_wire

_KEY = object()
_DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
_DIRECTORY_FLAGS |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


_LIVE_POOLS = {}
_PUBLICATIONS = {}
_PUBLICATION_SEALS = {}
_CREATED_POOLS = WeakKeyDictionary()


@dataclass(frozen=True, slots=True)
class _Publication:
    """Actual issuer observation; only its live registration authenticates it."""

    pool: object
    path: Path
    staged_node: LayoutEntryNode
    node: LayoutEntryNode
    content: bytes | None
    operation_id: str
    parent_before: LayoutEntryNode
    parent_after: LayoutEntryNode


def _publication_seal(value):
    if type(value) is not _Publication:
        raise ValueError("layout.control.actual-publication-required")
    return (
        tuple(getattr(value, item.name) for item in fields(_Publication)),
        canonical_json_bytes(
            _physical_wire(
                {
                    "path": str(value.path),
                    "content": None if value.content is None else value.content.hex(),
                    "operation_id": value.operation_id,
                    **{
                        name: asdict(getattr(value, name))
                        for name in (
                            "staged_node",
                            "node",
                            "parent_before",
                            "parent_after",
                        )
                    },
                }
            )
        ),
        tuple(
            (
                getattr(value, name),
                tuple(
                    (f.name, getattr(getattr(value, name), f.name))
                    for f in fields(LayoutEntryNode)
                ),
            )
            for name in ("staged_node", "node", "parent_before", "parent_after")
        ),
    )


def _publication_history(pool):
    """Authenticate retained point observations without rereading endpoints.

    Existing published directories may have acquired their own later children.
    The consuming owner must close its complete projected namespace and actual
    acquired descriptors; this history alone grants no role or effect rights.
    """
    original = _LIVE_POOLS.get(pool)
    if type(pool) is not _ControlPool or original is None:
        raise ValueError("layout.control.original-publication-pool-required")
    _close_control_pool_admission(pool, original)
    history = _PUBLICATIONS.get(pool)
    sealed = _PUBLICATION_SEALS.get(pool)
    if (
        type(history) is not tuple
        or sealed is None
        or sealed[0] is not history
        or len(history) != len(sealed[1])
        or len(history) > pool._maximum_entries
        or any(
            not _publication_matches(value, before)
            for value, before in zip(history, sealed[1], strict=True)
        )
    ):
        raise ValueError("layout.control.original-publication-history-changed")
    return history


def _publication_matches(value, before):
    if value is not before[0]:
        return False
    refs = tuple(getattr(value, f.name) for f in fields(_Publication))
    if any(a is not b for a, b in zip(refs, before[1][0], strict=True)):
        return False
    if any(
        getattr(node, name) is not old
        for node, observed in before[1][2]
        for name, old in observed
    ):
        return False
    return _publication_seal(value)[1] == before[1][1]


def _retain_publication(pool, before, value):
    if _publication_history(pool) is not before or value.pool is not pool:
        raise ValueError("layout.control.original-publication-predecessor-changed")
    if len(before) >= pool._maximum_entries:
        raise ValueError("layout.control.publication-history-limit")
    history = (*before, value)
    seals = (*_PUBLICATION_SEALS[pool][1], (value, _publication_seal(value)))
    _PUBLICATIONS[pool], _PUBLICATION_SEALS[pool] = history, (history, seals)


def _close_control_pool_admission(pool, original):
    if (
        _LIVE_POOLS.get(pool) is not original
        or original[0] != os.getpid()
        or original[1] != threading.get_ident()
        or original[2] != pool._descriptor
        or original[3] is not pool._guard
        or original[4] is not pool._journal
        or original[5] != pool._maximum_entries
        or original[6] != pool.root
    ):
        raise ValueError("layout.control.original-live-pool-required")


def _require_control_pool_reference(pool):
    """Reject foreign references without inspecting native pool state."""
    if type(pool) is not _ControlPool or pool not in _LIVE_POOLS:
        raise TypeError("layout.control.actual-live-pool-required")
    return _LIVE_POOLS[pool]


def _require_live_control_pool(pool):
    original = _require_control_pool_reference(pool)
    _close_control_pool_admission(pool, original)
    if pool._poisoned:
        raise ValueError("layout.control.publication-interrupted")
    pool._guard()
    _close_control_pool_admission(pool, original)
    return original


class StagedLayoutControl:
    """An opaque entry token, useful only in its creating live pool."""

    def __init__(self, key):
        if key is not _KEY:
            raise TypeError("layout.control.live-stage-required")


@dataclass(frozen=True, slots=True)
class PublishedLayoutControl:
    """Descriptive facts to recheck when opening actual reservation descriptors."""

    path: Path
    node: LayoutEntryNode
    payload_digest: str | None
    operation_id: str


@dataclass(frozen=True, slots=True)
class _Stage:
    name: str
    node: LayoutEntryNode
    content: bytes | None
    operation_id: str


@contextmanager
def _pinned_directory(path):
    require_safe_directory(path)
    with ExitStack() as stack:
        pinned = []
        for ancestor in (*reversed(path.parents), path):
            fd = os.open(ancestor, _DIRECTORY_FLAGS)
            stack.callback(os.close, fd)
            expected = _directory(ancestor.lstat())
            if _directory(os.fstat(fd)) != expected:
                raise ValueError("layout.control.parent-changed")
            pinned.append((ancestor, fd, expected))

        def current():
            for ancestor, fd, expected in pinned:
                if (
                    _directory(ancestor.lstat()) != expected
                    or _directory(os.fstat(fd)) != expected
                ):
                    raise ValueError("layout.control.parent-changed")

        current()
        yield pinned[-1][1], current
        current()


def _inspect(path, content):
    before = layout_entry_node(path)
    if content is None:
        if not stat.S_ISDIR(before.mode) or stat.S_IMODE(before.mode) != 0o700:
            raise ValueError("layout.control.private-empty-directory-required")
        flags = _DIRECTORY_FLAGS
    else:
        if (
            not stat.S_ISREG(before.mode)
            or stat.S_IMODE(before.mode) != 0o600
            or before.links != 1
            or before.size != len(content)
        ):
            raise ValueError("layout.control.private-marker-required")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    if before.uid != os.geteuid():
        raise ValueError("layout.control.private-owner-required")
    fd = os.open(path, flags)
    try:
        if _from_stat(os.fstat(fd)) != before:
            raise ValueError("layout.control.entry-changed")
        if content is None:
            with os.scandir(fd) as entries:
                if next(entries, None) is not None:
                    raise ValueError("layout.control.directory-not-empty")
        else:
            remaining, chunks = len(content) + 1, []
            while remaining:
                part = os.read(fd, remaining)
                if not part:
                    break
                remaining -= len(part)
                chunks.append(part)
            if b"".join(chunks) != content:
                raise ValueError("layout.control.marker-bytes-changed")
        if _from_stat(os.fstat(fd)) != before or layout_entry_node(path) != before:
            raise ValueError("layout.control.entry-changed")
        return before
    finally:
        os.close(fd)


def _require_portable_name(destination, parent_fd):
    key = unicodedata.normalize("NFC", destination.name.casefold())
    aliases = []
    with os.scandir(parent_fd) as entries:
        for index, entry in enumerate(entries):
            if index >= 16384:
                raise ValueError("layout.control.destination-entry-limit")
            if unicodedata.normalize("NFC", entry.name.casefold()) == key:
                aliases.append(entry.name)
    if aliases != [destination.name]:
        raise ValueError("layout.control.published-name-aliased")


class _ControlPool:
    def __init__(self, root, descriptor, guard, journal, maximum_entries):
        self.root, self._descriptor, self._guard = root, descriptor, guard
        self._journal = journal
        self._maximum_entries = maximum_entries
        self._created = 0
        self._entries = {}
        self._poisoned = False

    def _names(self):
        names = set()
        with os.scandir(self._descriptor) as entries:
            for entry in entries:
                if len(names) >= self._maximum_entries:
                    raise ValueError("layout.control.stage-limit")
                names.add(entry.name)
        return names

    def require_current(self):
        created = _CREATED_POOLS.get(self)
        if created is not None and (
            self not in _LIVE_POOLS or created != (os.getpid(), threading.get_ident())
        ):
            raise ValueError("layout.control.context-ended")
        _publication_history(self)
        self._guard()
        if self._poisoned:
            raise ValueError("layout.control.publication-interrupted")
        self._require_namespace_current()

    def _require_namespace_current(self):
        _publication_history(self)
        self._guard()
        self._journal.require_current()
        expected = {item.name for item in self._entries.values()}
        if self._names() != expected:
            raise ValueError("layout.control.stage-membership-changed")
        for item in self._entries.values():
            if _inspect(self.root / item.name, item.content) != item.node:
                raise ValueError("layout.control.stage-changed")
        if self._names() != expected:
            raise ValueError("layout.control.stage-membership-changed")
        self._journal.require_current()
        self._require_private_close()
        self._guard()

    def _require_private_close(self):
        # Close after the last blocking journal/endpoint reads. These stages are
        # immutable; any ordinary write, replacement, link or membership change
        # invalidates their complete recorded native facts. Do not traverse more
        # journal payloads after this close and leave private membership unchecked.
        _publication_history(self)
        expected = {item.name for item in self._entries.values()}
        if self._names() != expected:
            raise ValueError("layout.control.stage-membership-changed")
        for item in self._entries.values():
            node = os.stat(item.name, dir_fd=self._descriptor, follow_symlinks=False)
            if _from_stat(node) != item.node:
                raise ValueError("layout.control.stage-changed")
        if self._names() != expected:
            raise ValueError("layout.control.stage-membership-changed")

    def _stage(self, content):
        self.require_current()
        if self._created >= self._maximum_entries:
            raise ValueError("layout.control.stage-limit")
        if content is not None and (type(content) is not bytes or len(content) > 256):
            raise ValueError("layout.control.marker-limit")
        self._poisoned = True
        name, operation = "c-" + uuid4().hex, uuid4().hex
        if content is None:
            os.mkdir(name, 0o700, dir_fd=self._descriptor)
            fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=self._descriptor)
        else:
            fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=self._descriptor,
            )
        try:
            original = _from_stat(os.fstat(fd))
            if content is not None:
                remaining = memoryview(content)
                while remaining:
                    count = os.write(fd, remaining)
                    if count <= 0:
                        raise OSError("layout.control.short-write")
                    remaining = remaining[count:]
            os.fsync(fd)
            node = _inspect(self.root / name, content)
            if (node.device, node.inode, node.mode, node.uid, node.gid) != (
                original.device,
                original.inode,
                original.mode,
                original.uid,
                original.gid,
            ):
                raise ValueError("layout.control.created-node-changed")
        finally:
            os.close(fd)
        os.fsync(self._descriptor)
        token = StagedLayoutControl(_KEY)
        self._entries[token] = _Stage(name, node, content, operation)
        self._created += 1
        self._require_namespace_current()
        self._poisoned = False
        return token

    def stage_marker(self, content):
        if type(content) is not bytes:
            raise ValueError("layout.control.marker-limit")
        return self._stage(content)

    def stage_directory(self):
        return self._stage(None)

    def publish(self, token, destination, *, expected_parent):
        """Publish one known node; never infer control roles or clean conflicts."""
        self.require_current()
        history = _publication_history(self)
        if type(token) is not StagedLayoutControl or token not in self._entries:
            raise ValueError("layout.control.live-stage-required")
        destination = Path(destination)
        if (
            not destination.is_absolute()
            or ".." in destination.parts
            or destination.is_relative_to(self.root)
            or type(expected_parent) is not LayoutEntryNode
        ):
            raise ValueError("layout.control.destination-invalid")
        canonical_relative_posix_path(destination.name, label="control destination")
        item = self._entries[token]
        source = self.root / item.name
        with _pinned_directory(destination.parent) as (parent_fd, parent_current):
            if _directory(os.fstat(parent_fd)) == _directory(
                os.fstat(self._journal._descriptor)
            ):
                raise ValueError("layout.control.journal-destination-forbidden")
            if layout_entry_node(destination.parent).directory_identity != (
                expected_parent.directory_identity
            ):
                raise ValueError("layout.control.expected-parent-changed")
            self._poisoned = True
            payload = (
                None
                if item.content is None
                else self._journal.store_payload(item.content)
            )
            data = {
                "operation_id": item.operation_id,
                "source": str(source),
                "destination": str(destination),
                "source_node": _physical_wire(asdict(item.node)),
                "destination_parent": _physical_wire(asdict(expected_parent)),
                "payload_digest": payload,
                "directory": item.content is None,
            }
            self._journal.append(
                "control-publication-intent", canonical_json_bytes(data)
            )
            self._require_namespace_current()
            parent_current()
            move_layout_entry_exclusive(
                source,
                destination,
                expected_source=item.node,
                expected_source_parent=layout_entry_node(self.root),
                expected_destination_parent=expected_parent,
            )
            os.fsync(parent_fd)
            os.fsync(self._descriptor)
            parent_current()
            node = _inspect(destination, item.content)
            if node.after_rename() != item.node.after_rename():
                raise ValueError("layout.control.published-node-changed")
            _require_portable_name(destination, parent_fd)
            if os.path.lexists(source):
                raise ValueError("layout.control.private-source-repopulated")
            parent_current()
            self._guard()
            self._journal.append(
                "control-publication-observed",
                canonical_json_bytes(
                    {
                        **data,
                        "published_node": _physical_wire(asdict(node)),
                    }
                ),
            )
            del self._entries[token]
            self._require_namespace_current()
            if _inspect(destination, item.content) != node:
                raise ValueError("layout.control.published-node-changed")
            _require_portable_name(destination, parent_fd)
            self._require_private_close()
            parent_current()
            self._guard()
            _retain_publication(
                self,
                history,
                _Publication(
                    self,
                    destination,
                    item.node,
                    node,
                    item.content,
                    item.operation_id,
                    expected_parent,
                    _from_stat(os.fstat(parent_fd)),
                ),
            )
            self._poisoned = False
            return PublishedLayoutControl(destination, node, payload, item.operation_id)


@contextmanager
def staged_layout_controls(root, journal, *, maximum_entries=64):
    """Use a fresh existing private staging directory; retain all nodes on exit.

    The owning transaction selects framework state, holds its actual journal
    context and supplies real project/Git/control authority separately. Published
    facts are point-in-time observations; reopening real reservation descriptors
    and explicit fresh recovery remain the caller's responsibility.
    """
    root = Path(root)
    if (
        os.name != "posix"
        or not root.is_absolute()
        or ".." in root.parts
        or type(journal) is not _LayoutJournalWriter
        or type(maximum_entries) is not int
        or not 1 <= maximum_entries <= 1024
    ):
        raise ValueError("layout.control.native-context-required")
    with _pinned_directory(root) as (descriptor, parent_current):
        node = os.fstat(descriptor)
        if node.st_uid != os.geteuid() or stat.S_IMODE(node.st_mode) != 0o700:
            raise ValueError("layout.control.private-stage-root-required")
        active, receiver = True, os.getpid()

        def guard():
            if not active or receiver != os.getpid():
                raise ValueError("layout.control.context-ended")
            parent_current()

        try:
            pool = _ControlPool(root, descriptor, guard, journal, maximum_entries)
            _LIVE_POOLS[pool] = (
                os.getpid(),
                threading.get_ident(),
                descriptor,
                guard,
                journal,
                maximum_entries,
                root,
            )
            _PUBLICATIONS[pool] = ()
            _PUBLICATION_SEALS[pool] = (_PUBLICATIONS[pool], ())
            _CREATED_POOLS[pool] = os.getpid(), threading.get_ident()
            pool.require_current()
            os.fsync(descriptor)
            with _pinned_directory(root.parent) as (parent_fd, current):
                os.fsync(parent_fd)
                current()
            yield pool
            pool.require_current()
        finally:
            if "pool" in locals():
                _LIVE_POOLS.pop(pool, None)
                _PUBLICATIONS.pop(pool, None)
                _PUBLICATION_SEALS.pop(pool, None)
            active = False
