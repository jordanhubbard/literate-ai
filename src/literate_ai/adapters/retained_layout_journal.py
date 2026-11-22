"""Bounded durable layout records, never project ownership or move authority.

The caller selects a private framework-state directory and separately owns actual
project/Git/control reservations. This POSIX journal dependency does not enable
CLI apply. Windows durability and the surrounding recovery owner remain required.
Interrupted private stages are retained as diagnostics, never interpreted as intent.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from literate_ai._cache_lock import _acquire, _release
from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import canonical_json_bytes

from .exclusive_directory import _native_rename

_SCHEMA = "literate-ai/retained-layout-journal@1"
_DOCUMENT_LIMIT = 64 * 1024
_COMPARE_CHUNK_BYTES = 64 * 1024
_RECORD_LIMIT = 2 * _DOCUMENT_LIMIT
_LABEL = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_STAGE = re.compile(r"s-[0-9a-f]{32}\Z")
_LIVE_WRITERS = {}
_LIVE_ROOTS = {}


def _close_live_journal_admission(writer, original):
    descriptor, guard, budget, pid = original
    if (
        _LIVE_WRITERS.get(writer) is not original
        or writer._descriptor != descriptor
        or writer._guard is not guard
        or writer._budget is not budget
        or pid != os.getpid()
        or writer._poisoned
    ):
        raise ValueError("layout.journal.original-live-writer-required")


def _require_live_layout_journal(writer):
    """Require the actual creating context, never a descriptive writer shape."""
    if type(writer) is not _LayoutJournalWriter or writer not in _LIVE_WRITERS:
        raise TypeError("layout.journal.actual-live-writer-required")
    original = _LIVE_WRITERS[writer]
    _close_live_journal_admission(writer, original)
    guard = original[1]
    guard()
    _close_live_journal_admission(writer, original)
    return writer


@dataclass(frozen=True, slots=True)
class LayoutJournalBudget:
    maximum_events: int = 256
    maximum_payload_bytes: int = 16 * 1024 * 1024
    maximum_storage_bytes: int = 64 * 1024 * 1024
    maximum_stages: int = 32

    def validate(self):
        for value, ceiling in (
            (self.maximum_events, 256),
            (self.maximum_payload_bytes, 16 * 1024 * 1024),
            (self.maximum_storage_bytes, 64 * 1024 * 1024),
            (self.maximum_stages, 32),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError("layout.journal.budget-invalid")

    def to_dict(self):
        return {
            "maximum_events": self.maximum_events,
            "maximum_payload_bytes": self.maximum_payload_bytes,
            "maximum_storage_bytes": self.maximum_storage_bytes,
            "maximum_stages": self.maximum_stages,
        }


def _document(raw):
    if type(raw) is not bytes or len(raw) > _DOCUMENT_LIMIT:
        raise ValueError("layout.journal.document-limit")
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
            raise ValueError("layout.journal.document-not-canonical")
    except (RecursionError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("layout.journal.document-invalid") from exc
    return value


def _directory(node):
    if not stat.S_ISDIR(node.st_mode):
        raise ValueError("layout.journal.directory-required")
    return node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid


def _file(node):
    if (
        not stat.S_ISREG(node.st_mode)
        or node.st_uid != os.geteuid()
        or stat.S_IMODE(node.st_mode) != 0o600
        or node.st_nlink != 1
    ):
        raise ValueError("layout.journal.private-single-file-required")
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
        node.st_nlink,
    )


@contextmanager
def _writer_lock(descriptor, path, *, create, timeout_seconds):
    # Recovery must never create or initialize a foreign/incomplete lock. Opening
    # relative to the held journal also avoids re-following an ancestor pathname.
    receiver_pid = os.getpid()
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    fd = os.open("writer.lock", flags, 0o600, dir_fd=descriptor)
    locked = False
    try:
        original = _file(os.fstat(fd))
        if create:
            if os.write(fd, b"\0") != 1:
                raise OSError("layout.journal.lock-write-incomplete")
            os.fsync(fd)
        node = _file(os.fstat(fd))
        if (
            node[:5] != original[:5]
            or node[5] != 1
            or os.pread(fd, 2, 0) != b"\0"
            or _file(os.stat("writer.lock", dir_fd=descriptor, follow_symlinks=False))
            != node
        ):
            raise ValueError("layout.journal.lock-invalid")
        _acquire(fd, path / "writer.lock", timeout_seconds=timeout_seconds)
        locked = True
        if (
            _file(os.fstat(fd)) != node
            or _file(os.stat("writer.lock", dir_fd=descriptor, follow_symlinks=False))
            != node
        ):
            raise ValueError("layout.journal.lock-changed")
        yield fd, node
    finally:
        try:
            # A fork shares the open-file description: unlocking in an inherited
            # child's cleanup would release the parent's actual writer mutex.
            # The child closes only its descriptor copy; its PID guard already
            # refuses all writer operations. The acquiring process still unlocks.
            if locked and receiver_pid == os.getpid():
                _release(fd)
        finally:
            os.close(fd)


class _LayoutJournalWriter:
    """A process/context-bound writer; serialized records cannot recreate it."""

    def __init__(self, descriptor, guard, budget):
        self._descriptor = descriptor
        self._guard = guard
        self._budget = budget
        self._known = {}
        self._events = []
        self._payloads = set()
        self._stages = set()
        self._poisoned = False

    def _read(self, name, *, maximum_bytes=None):
        fd = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=self._descriptor,
        )
        try:
            before = _file(os.fstat(fd))
            limit = max(_RECORD_LIMIT, self._budget.maximum_payload_bytes)
            if maximum_bytes is not None:
                if type(maximum_bytes) is not int or maximum_bytes < 0:
                    raise ValueError("layout.journal.read-limit-invalid")
                limit = min(limit, maximum_bytes)
            if before[5] > limit:
                raise ValueError("layout.journal.file-limit")
            chunks, size = [], 0
            while True:
                chunk = os.read(fd, min(65536, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise ValueError("layout.journal.file-limit")
            after = _file(os.fstat(fd))
            named = _file(os.stat(name, dir_fd=self._descriptor, follow_symlinks=False))
            if before != after or before != named or size != before[5]:
                raise ValueError("layout.journal.file-changed")
            return before, b"".join(chunks)
        finally:
            os.close(fd)

    def _names(self):
        names = set()
        limit = 2 + 2 * self._budget.maximum_events + self._budget.maximum_stages
        with os.scandir(self._descriptor) as entries:
            for entry in entries:
                if len(names) >= limit:
                    raise ValueError("layout.journal.membership-limit")
                names.add(entry.name)
        return names

    def _compare_member(self, name, expected):
        """Compare every native byte with fixed, prepaid immutable buffers."""
        fd = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=self._descriptor,
        )
        try:
            before = _file(os.fstat(fd))
            content = expected[1]
            if len(content) > max(_RECORD_LIMIT, self._budget.maximum_payload_bytes):
                raise ValueError("layout.journal.file-limit")
            if before[5] > len(content):
                raise ValueError("layout.journal.file-limit")
            if before != expected[0] or before[5] != len(content):
                raise ValueError("layout.journal.record-changed")
            offset = 0
            while True:
                chunk = os.read(
                    fd, min(_COMPARE_CHUNK_BYTES, len(content) + 1 - offset)
                )
                if not chunk:
                    break
                if chunk != content[offset : offset + len(chunk)]:
                    raise ValueError("layout.journal.record-changed")
                offset += len(chunk)
                if offset > len(content):
                    raise ValueError("layout.journal.record-changed")
            after = _file(os.fstat(fd))
            named = _file(os.stat(name, dir_fd=self._descriptor, follow_symlinks=False))
            if before != after or before != named or offset != len(content):
                raise ValueError("layout.journal.record-changed")
        finally:
            os.close(fd)

    def require_current(self, *, _expected=None):
        admission = _LIVE_WRITERS.get(self)
        roster = tuple(self._known.items()) if _expected is None else _expected

        def require_roster():
            if len(self._known) != len(roster) or any(
                self._known.get(name) is not expected for name, expected in roster
            ):
                raise ValueError("layout.journal.funded-roster-changed")

        self._guard()
        require_roster()
        if self._poisoned:
            raise ValueError("layout.journal.writer-interrupted")
        if admission is not None:
            _close_live_journal_admission(self, admission)
        if self._names() != set(self._known):
            raise ValueError("layout.journal.membership-changed")
        for name, expected in roster:
            require_roster()
            self._compare_member(name, expected)
            require_roster()
        if self._names() != set(self._known):
            raise ValueError("layout.journal.membership-changed")
        self._guard()
        require_roster()
        if admission is not None:
            _close_live_journal_admission(self, admission)

    @property
    def events(self):
        self.require_current()
        # Return fresh documents, not mutable aliases into the live writer.
        return tuple(json.loads(self._known[name][1]) for name in self._events)

    def _raw_documents_from_snapshot(self, snapshot, *, _expected=None):
        """Authenticate immutable raw descriptions without returning mutable JSON."""
        _require_live_layout_journal(self)
        admission = _LIVE_WRITERS[self]
        if (
            type(snapshot) is not tuple
            or len(snapshot) != 2
            or any(type(value) is not tuple for value in snapshot)
        ):
            raise ValueError("layout.journal.actual-event-snapshot-required")
        names, rows = snapshot
        if len(names) != len(rows) or any(type(name) is not str for name in names):
            raise ValueError("layout.journal.actual-event-snapshot-required")

        def close():
            if _expected is not None and (
                type(_expected) is not tuple
                or len(self._known) != len(_expected)
                or any(self._known.get(name) is not row for name, row in _expected)
            ):
                raise ValueError("layout.journal.funded-roster-changed")
            if tuple(self._events) != names or any(
                self._known.get(name) is not row
                for name, row in zip(names, rows, strict=True)
            ):
                raise ValueError("layout.journal.funded-event-roster-changed")

        close()
        if _expected is None:
            self.require_current()
        else:
            self.require_current(_expected=_expected)
        _require_live_layout_journal(self)
        close()
        digests = tuple(sorted(self._payloads))
        payload_rows = tuple(self._known[f"p-{digest}.bin"] for digest in digests)
        # Only immutable bytes/strings/tuples cross later consumer callbacks.
        # Decoding belongs to a subsequent callback-free projection.
        result = (
            tuple(row[1] for row in rows),
            tuple(
                (digest, row[1])
                for digest, row in zip(digests, payload_rows, strict=True)
            ),
        )
        if _expected is None:
            self.require_current()
        else:
            self.require_current(_expected=_expected)
        _require_live_layout_journal(self)
        close()
        if (
            _LIVE_WRITERS.get(self) is not admission
            or tuple(sorted(self._payloads)) != digests
            or any(
                self._known.get(f"p-{digest}.bin") is not row
                for digest, row in zip(digests, payload_rows, strict=True)
            )
        ):
            raise ValueError("layout.journal.funded-payload-roster-changed")
        return result

    def read_payload(self, digest):
        self.require_current()
        if digest not in self._payloads:
            raise ValueError("layout.journal.payload-not-recorded")
        return self._known[f"p-{digest}.bin"][1]

    def _publish(self, name, content):
        self.require_current()
        if type(content) is not bytes:
            raise ValueError("layout.journal.payload-limit")
        # These immutable rows were byte-authenticated by this operation. Only
        # our new stage/name may join them; no caller can provide a baseline or
        # reuse this closure for another publication.
        original_rows = tuple(self._known.items())
        descriptor, guard, budget = self._descriptor, self._guard, self._budget
        admission = _LIVE_WRITERS.get(self)

        def directory_signature():
            node = os.fstat(descriptor)
            return (
                _directory(node),
                node.st_size,
                node.st_nlink,
                node.st_mtime_ns,
                node.st_ctime_ns,
            )

        def close_publication(extra_name, extra_row, directory):
            roster = (*original_rows, (extra_name, extra_row))
            names = {member for member, _row in roster}

            def close_references():
                if (
                    self._descriptor != descriptor
                    or self._guard is not guard
                    or self._budget is not budget
                    or _LIVE_WRITERS.get(self) is not admission
                    or self._poisoned
                    or len(self._known) != len(roster)
                    or any(self._known.get(member) is not row for member, row in roster)
                ):
                    raise ValueError("layout.journal.funded-roster-changed")
                if admission is not None:
                    _close_live_journal_admission(self, admission)

            close_references()
            guard()
            close_references()
            if self._names() != names:
                raise ValueError("layout.journal.membership-changed")
            # Finish enumeration before closing the original named ancestry.
            # A held directory descriptor alone does not preserve its path.
            guard()
            close_references()
            for member, row in roster:
                observed = _file(
                    os.stat(member, dir_fd=descriptor, follow_symlinks=False)
                )
                if observed != row[0]:
                    raise ValueError("layout.journal.record-changed")
            # Native change times close additions/removals after enumeration.
            # This baseline comes only from our actual stage create/rename.
            if directory_signature() != directory:
                raise ValueError("layout.journal.directory-changed")
            # No enumeration or guard callback follows these native closures.
            close_references()

        if (
            name in self._known
            or len(self._stages) >= self._budget.maximum_stages
            or sum(len(item[1]) for item in self._known.values()) + len(content)
            > self._budget.maximum_storage_bytes
        ):
            raise ValueError("layout.journal.storage-limit-or-occupied")
        stage = "s-" + uuid4().hex
        self._poisoned = True
        fd = os.open(
            stage,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=self._descriptor,
        )
        try:
            staged_directory = directory_signature()
            original = _file(os.fstat(fd))
            remaining = memoryview(content)
            while remaining:
                count = os.write(fd, remaining)
                if count <= 0:
                    raise OSError("layout.journal.short-write")
                remaining = remaining[count:]
            os.fsync(fd)
            observed = _file(os.fstat(fd)), content
            if observed[0][:5] != original[:5] or observed[0][5] != len(content):
                raise ValueError("layout.journal.stage-changed")
            # The immutable caller body is already funded. Authenticate its
            # complete native counterpart before retaining that same byte value;
            # no second full staged body is allocated or trusted without a read.
            self._compare_member(stage, observed)
            self._known[stage] = observed
        finally:
            os.close(fd)
        # No application effect is authorized until this complete operation returns.
        self._poisoned = False
        close_publication(stage, observed, staged_directory)
        self._poisoned = True
        _native_rename(self._descriptor, stage.encode("ascii"), name.encode("ascii"))
        published_directory = directory_signature()
        os.fsync(self._descriptor)
        published = (
            _file(os.stat(name, dir_fd=self._descriptor, follow_symlinks=False)),
            content,
        )
        if published[0][:5] != observed[0][:5] or published[0][5] != len(content):
            raise ValueError("layout.journal.publication-changed")
        self._compare_member(name, published)
        del self._known[stage]
        self._known[name] = published
        self._poisoned = False
        close_publication(name, published, published_directory)

    def store_payload(self, content):
        self.require_current()
        if (
            type(content) is not bytes
            or len(content) > self._budget.maximum_payload_bytes
        ):
            raise ValueError("layout.journal.payload-limit")
        digest = hashlib.sha256(content).hexdigest()
        if digest not in self._payloads:
            if len(self._payloads) >= self._budget.maximum_events:
                raise ValueError("layout.journal.payload-count-limit")
            self._publish(f"p-{digest}.bin", content)
            self._payloads.add(digest)
        return digest

    def append(self, kind, canonical_data):
        from .retained_layout_source_admission import _fund_journal_document

        _fund_journal_document(self, canonical_data)
        self.require_current()
        if (
            type(kind) is not str
            or not _LABEL.fullmatch(kind)
            or len(self._events) >= self._budget.maximum_events
        ):
            raise ValueError("layout.journal.event-invalid-or-limit")
        previous = None
        if self._events:
            previous = hashlib.sha256(self._known[self._events[-1]][1]).hexdigest()
        raw = canonical_json_bytes(
            {
                "schema": _SCHEMA,
                "sequence": len(self._events),
                "previous": previous,
                "kind": kind,
                "data": _document(canonical_data),
                "grants_move_authority": False,
            }
        )
        name = f"e-{len(self._events):04d}.json"
        self._publish(name, raw)
        self._events.append(name)
        return hashlib.sha256(raw).hexdigest()

    def _load(self, header):
        self._guard()
        total = 0
        for name in sorted(self._names()):
            observed = self._read(name)
            total += len(observed[1])
            if total > self._budget.maximum_storage_bytes:
                raise ValueError("layout.journal.storage-limit")
            self._known[name] = observed
            if name == "writer.lock":
                if observed[1] != b"\0":
                    raise ValueError("layout.journal.lock-invalid")
            elif name == "header.json":
                if observed[1] != header:
                    raise ValueError("layout.journal.binding-mismatch")
            elif _STAGE.fullmatch(name):
                self._stages.add(name)
            elif name.startswith("p-") and name.endswith(".bin"):
                digest = name[2:-4]
                if (
                    not _DIGEST.fullmatch(digest)
                    or hashlib.sha256(observed[1]).hexdigest() != digest
                    or len(observed[1]) > self._budget.maximum_payload_bytes
                ):
                    raise ValueError("layout.journal.payload-invalid")
                self._payloads.add(digest)
            elif name == f"e-{len(self._events):04d}.json":
                raw = observed[1]
                if len(raw) > _RECORD_LIMIT:
                    raise ValueError("layout.journal.event-limit")
                document = json.loads(raw)
                previous = (
                    None
                    if not self._events
                    else hashlib.sha256(self._known[self._events[-1]][1]).hexdigest()
                )
                if (
                    not isinstance(document, dict)
                    or set(document)
                    != {
                        "schema",
                        "sequence",
                        "previous",
                        "kind",
                        "data",
                        "grants_move_authority",
                    }
                    or canonical_json_bytes(document) != raw
                    or document["schema"] != _SCHEMA
                    or type(document["sequence"]) is not int
                    or document["sequence"] != len(self._events)
                    or document["previous"] != previous
                    or document["grants_move_authority"] is not False
                    or type(document["kind"]) is not str
                    or not _LABEL.fullmatch(document["kind"])
                ):
                    raise ValueError("layout.journal.chain-invalid")
                _document(canonical_json_bytes(document["data"]))
                self._events.append(name)
            else:
                raise ValueError("layout.journal.foreign-entry")
        if (
            not {"header.json", "writer.lock"} <= self._known.keys()
            or len(self._events) > self._budget.maximum_events
            or len(self._payloads) > self._budget.maximum_events
            or len(self._stages) > self._budget.maximum_stages
        ):
            raise ValueError("layout.journal.incomplete-or-limit")
        self.require_current()


@contextmanager
def retained_layout_journal(
    path: Path,
    *,
    canonical_binding: bytes,
    budget: LayoutJournalBudget,
    recover: bool = False,
    lock_timeout_seconds: float = 1.0,
):
    """Hold the actual private writer mutex through preparation or recovery.

    Reopening requires explicit recovery and the identical bounded binding/budget.
    Recovery validates the full immutable chain and all payloads; it grants no
    project reservations, effects, deletion rights or acceptance. Every stage is
    retained, including partial writes. Callers must freshly classify real project
    endpoints before recovery effects. Storage may reside inside framework state.
    """
    path = Path(path)
    if (
        os.name != "posix"
        or not path.is_absolute()
        or ".." in path.parts
        or type(budget) is not LayoutJournalBudget
        or type(recover) is not bool
        or type(lock_timeout_seconds) not in (int, float)
        or not 0 < lock_timeout_seconds <= 30
    ):
        raise ValueError("layout.journal.native-context-required")
    budget.validate()
    header = canonical_json_bytes(
        {
            "schema": _SCHEMA,
            "binding": _document(canonical_binding),
            "budget": budget.to_dict(),
            "grants_move_authority": False,
        }
    )
    require_safe_directory(path.parent)
    parent = path.parent.lstat()
    if parent.st_uid != os.geteuid() or stat.S_IMODE(parent.st_mode) != 0o700:
        raise ValueError("layout.journal.private-parent-required")
    receiver_pid, active = os.getpid(), True
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    with ExitStack() as stack:
        pinned = []
        for ancestor in reversed((path.parent, *path.parent.parents)):
            fd = os.open(ancestor, flags)
            stack.callback(os.close, fd)
            identity = _directory(ancestor.lstat())
            if _directory(os.fstat(fd)) != identity:
                raise ValueError("layout.journal.parent-changed")
            pinned.append((ancestor, fd, identity))
        parent_fd = pinned[-1][1]
        if not recover:
            os.mkdir(path.name, 0o700, dir_fd=parent_fd)
        descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        stack.callback(os.close, descriptor)
        identity = _directory(os.fstat(descriptor))
        if identity[3] != os.geteuid() or stat.S_IMODE(identity[2]) != 0o700:
            raise ValueError("layout.journal.private-directory-required")

        def guard():
            if not active or receiver_pid != os.getpid():
                raise ValueError("layout.journal.writer-context-ended")
            for ancestor, fd, expected in pinned:
                if (
                    _directory(ancestor.lstat()) != expected
                    or _directory(os.fstat(fd)) != expected
                ):
                    raise ValueError("layout.journal.parent-changed")
            if (
                _directory(os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False))
                != identity
                or _directory(os.fstat(descriptor)) != identity
            ):
                raise ValueError("layout.journal.directory-changed")

        guard()
        held_lock = []

        original_guard = guard

        def guard():
            original_guard()
            for fd, node in held_lock:
                if (
                    _file(os.fstat(fd)) != node
                    or _file((path / "writer.lock").lstat()) != node
                ):
                    raise ValueError("layout.journal.lock-changed")

        try:
            with _writer_lock(
                descriptor,
                path,
                create=not recover,
                timeout_seconds=lock_timeout_seconds,
            ) as held:
                held_lock.append(held)
                guard()
                writer = _LayoutJournalWriter(descriptor, guard, budget)
                if recover:
                    writer._load(header)
                else:
                    writer._known["writer.lock"] = writer._read("writer.lock")
                    if writer._known["writer.lock"][1] != b"\0":
                        raise ValueError("layout.journal.lock-invalid")
                    writer._publish("header.json", header)
                # Recovered completed records are flushed before allowing effects.
                for name in writer._known:
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                os.fsync(descriptor)
                os.fsync(parent_fd)
                writer.require_current()
                _LIVE_WRITERS[writer] = (descriptor, guard, budget, receiver_pid)
                _LIVE_ROOTS[writer] = path
                try:
                    yield writer
                    writer.require_current()
                finally:
                    _LIVE_WRITERS.pop(writer, None)
                    _LIVE_ROOTS.pop(writer, None)
                    # Revoke before the real writer lock or ancestry FDs close.
                    active = False
        finally:
            active = False
