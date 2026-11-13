"""Acquire actual reservation descriptors from journaled, known control nodes.

Target records do not grant project/Git roles or source movement. The enclosing
transaction must prove those separately. Every control remains for explicit
journaled release/recovery; saved records never reopen this live owner.
"""

from __future__ import annotations

import errno
import hashlib
import os
import secrets
import stat
import unicodedata
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from uuid import uuid4

from literate_ai._cache_lock import _acquire
from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import canonical_json_bytes

from ._write_reservations import (
    _CREATION_KEY,
    WriteReservationSet,
    WriteReservationTarget,
    _fail,
    _OwnedMarker,
    combine_body_and_release_errors,
)
from .exclusive_entry import LayoutEntryNode, _from_stat, layout_entry_node
from .repository_orchestration import _read_document
from .retained_layout_control_publication import _ControlPool
from .retained_layout_journal import _directory
from .retained_layout_journal import _file as _journal_file
from .retained_layout_partition import _physical_wire

_PREFIX = b"literate-ai-refresh-reservation\n"
_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
_FLAGS |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


def _portable_name(path, parent_fd, *, present):
    key = unicodedata.normalize("NFC", path.name.casefold())
    found = []
    with os.scandir(parent_fd) as entries:
        for count, entry in enumerate(entries):
            if count >= 16384:
                _fail("limit", "reservation directory exceeds its entry bound")
            if unicodedata.normalize("NFC", entry.name.casefold()) == key:
                found.append(entry.name)
    if found != ([path.name] if present else []):
        _fail("alias", "reservation name is occupied or has a portable alias")


class _HeldDirectories:
    def __init__(self, stack):
        self._stack = stack
        self.nodes = {}

    def current(self):
        for path, (fd, expected) in self.nodes.items():
            if (
                _directory(path.lstat()) != expected
                or _directory(os.fstat(fd)) != expected
            ):
                _fail("changed", "staged reservation ancestry changed")

    def pin(self, path, *, expected=None):
        require_safe_directory(path)
        self.current()
        for ancestor in (*reversed(path.parents), path):
            if ancestor in self.nodes:
                continue
            if len(self.nodes) >= 4096:
                _fail("limit", "staged reservation ancestry exceeds its bound")
            fd = os.open(ancestor, _FLAGS)
            self._stack.callback(os.close, fd)
            node = _directory(os.fstat(fd))
            if _directory(ancestor.lstat()) != node:
                _fail("changed", "staged reservation ancestry changed during open")
            self.nodes[ancestor] = fd, node
        self.current()
        if expected is not None and self.nodes[path][1] != expected:
            _fail("changed", "staged reservation parent was replaced")
        return self.nodes[path][0]


@dataclass(frozen=True, slots=True)
class _MarkerPlan:
    target: WriteReservationTarget
    node: LayoutEntryNode | None
    content: bytes


def _preflight(pool, targets, held):
    if type(targets) is not tuple or not 1 <= len(targets) <= 1024:
        raise ValueError("layout.reservations.bounded-targets-required")
    unique, aliases = {}, set()
    for target in targets:
        if type(target) is not WriteReservationTarget:
            raise TypeError("layout.reservations.typed-target-required")
        if target.path.is_relative_to(pool.root):
            _fail("alias", "reservation cannot occupy its private stage namespace")
        spelling = str(target.path)
        if spelling in unique:
            if unique[spelling] != target:
                _fail("alias", "one reservation has conflicting target records")
            continue
        alias = unicodedata.normalize("NFC", spelling.casefold())
        if alias in aliases:
            _fail("alias", "staged reservation targets alias")
        aliases.add(alias)
        unique[spelling] = target
    paths = {target.path for target in unique.values()}
    if any(path in other.parents for path in paths for other in paths):
        _fail("alias", "a reservation file overlaps another reservation parent")
    protected = {
        _directory(os.fstat(pool._descriptor)),
        _directory(os.fstat(pool._journal._descriptor)),
    }
    device = os.fstat(pool._descriptor).st_dev
    directories, plans = {}, []
    for target in unique.values():
        WriteReservationSet._guard(target)
        held.pin(target.anchor)
        current = target.anchor
        for part in ("", *target.path.relative_to(target.anchor).parts[:-1]):
            current = current / part
            if current in directories:
                continue
            if os.path.lexists(current):
                held.pin(current)
                node = held.nodes[current][1]
                if node in protected:
                    _fail(
                        "alias", "reservation cannot occupy private staging or journal"
                    )
                if node[0] != device:
                    raise OSError(errno.EXDEV, "staged controls require one filesystem")
                directories[current] = node
            else:
                directories[current] = None
        if directories[target.path.parent] is None:
            node, content = None, None
        else:
            parent_fd = held.nodes[target.path.parent][0]
            exists = os.path.lexists(target.path)
            _portable_name(target.path, parent_fd, present=exists)
            if exists:
                if not target.advisory:
                    _fail("busy", "retained or active reservation requires its owner")
                node = layout_entry_node(target.path)
                if not stat.S_ISREG(node.mode) or node.links != 1:
                    _fail("changed", "existing advisory control is not a direct file")
                content = _read_document(target.path, maximum_bytes=256)
                if not content or content.startswith(_PREFIX):
                    _fail(
                        "busy", "empty or retained advisory control requires recovery"
                    )
                if layout_entry_node(target.path) != node:
                    _fail("changed", "existing advisory control changed during read")
            else:
                node, content = None, None
        if node is None:
            content = _PREFIX + secrets.token_hex(32).encode("ascii") + b"\n"
        elif node.device != device:
            raise OSError(errno.EXDEV, "staged controls require one filesystem")
        plans.append(_MarkerPlan(target, node, content))
        held.current()
    for path, node in directories.items():
        if node is None and os.path.lexists(path):
            _fail("changed", "planned absent control parent changed during preflight")
    for plan in plans:
        if plan.node is None and os.path.lexists(plan.target.path):
            _fail("changed", "planned absent control marker changed during preflight")
    new_nodes = sum(value is None for value in directories.values())
    new_nodes += sum(plan.node is None for plan in plans)
    journal = pool._journal
    events = 2 * new_nodes + 2 * len(plans) + 1
    payloads = {hashlib.sha256(plan.content).hexdigest() for plan in plans}
    storage = sum(len(value[1]) for value in journal._known.values())
    if (
        new_nodes > pool._maximum_entries - pool._created
        or events > journal._budget.maximum_events - len(journal._events)
        or len(payloads - journal._payloads) + len(journal._payloads)
        > journal._budget.maximum_events
        or storage + events * 128 * 1024 + sum(len(p.content) for p in plans)
        > journal._budget.maximum_storage_bytes
    ):
        _fail("limit", "staged acquisition exceeds its complete finite reservation")
    pool.require_current()
    held.current()
    return sorted(
        plans,
        key=lambda plan: (
            not plan.target.advisory,
            plan.node is None,
            str(plan.target.path),
        ),
    ), directories


class _StagedReservationSet(WriteReservationSet):
    def __init__(self, pool, held):
        super().__init__(_CREATION_KEY)
        self._pool, self._held, self._receiver = pool, held, os.getpid()
        self._expected = {}
        # This internal acquisition factory retains even a partial preparation.
        self._retain_for_recovery = True

    def _live(self):
        if not self._active or self._receiver != os.getpid():
            _fail("inactive", "staged reservation context ended")
        self._pool._guard()
        self._pool._journal._guard()
        self._held.current()

    def _verify_marker(self, marker):
        self._live()
        expected = self._expected[marker.target.path]
        if (
            _from_stat(os.fstat(marker.descriptor)) != expected
            or layout_entry_node(marker.target.path) != expected
        ):
            _fail("changed", "staged reservation native identity changed")
        if os.pread(marker.descriptor, len(marker.content) + 1, 0) != marker.content:
            _fail("changed", "staged reservation bytes changed")
        _portable_name(
            marker.target.path,
            self._held.nodes[marker.target.path.parent][0],
            present=True,
        )
        if (
            _from_stat(os.fstat(marker.descriptor)) != expected
            or layout_entry_node(marker.target.path) != expected
        ):
            _fail("changed", "staged reservation changed during closing observation")
        self._live()

    def verify_all(self):
        self._live()
        if not self._complete:
            _fail("inactive", "staged reservations are not complete")
        self._pool.require_current()
        for marker in self._markers:
            if marker.target.advisory and not marker.advisory_locked:
                _fail("inactive", "staged advisory mutex was not acquired")
            self._verify_marker(marker)
        for path, node, target in self._directories:
            self._guard(target)
            if _directory(path.lstat())[:3] != node:
                _fail("changed", "staged control directory changed")
        # Marker observations can be the last blocking reads before acquisition
        # yields. Re-close the real journal/private dependencies afterwards.
        self._pool.require_current()
        for marker in self._markers:
            _portable_name(
                marker.target.path,
                self._held.nodes[marker.target.path.parent][0],
                present=True,
            )
        # Earlier markers may have changed during later bounded payload/name
        # reads. Close every held/named native identity after those observations.
        for marker in self._markers:
            expected = self._expected[marker.target.path]
            parent_fd = self._held.nodes[marker.target.path.parent][0]
            named = os.stat(
                marker.target.path.name, dir_fd=parent_fd, follow_symlinks=False
            )
            if (
                _from_stat(named) != expected
                or _from_stat(os.fstat(marker.descriptor)) != expected
            ):
                _fail("changed", "staged reservation set changed during final closure")
        self._close_dependencies()
        self._live()

    def _close_dependencies(self):
        journal = self._pool._journal
        journal._guard()
        expected = set(journal._known)
        if journal._names() != expected:
            _fail("changed", "staged reservation journal namespace changed")
        for name, (signature, _) in journal._known.items():
            named = os.stat(name, dir_fd=journal._descriptor, follow_symlinks=False)
            if _journal_file(named) != signature:
                _fail("changed", "staged reservation journal native facts changed")
        if journal._names() != expected:
            _fail("changed", "staged reservation journal namespace changed")
        self._pool._require_private_close()
        journal._guard()

    def owns(self, path):
        self.verify_all()
        return any(marker.target.path == path for marker in self._markers)

    def owns_directory(self, path):
        self._live()
        result = super().owns_directory(path)
        self._live()
        return result


@contextmanager
def acquire_staged_layout_reservations(pool, targets):
    """Publish and acquire actual controls; retain them for explicit finalization.

    The caller owns the actual journal/pool contexts and separately binds target
    roles and original source. This is not a saved-record decoder or public apply.
    No generic create-first reservation path is used, including partial failures.
    """
    if os.name != "posix" or type(pool) is not _ControlPool:
        raise TypeError("layout.reservations.live-posix-pool-required")
    pool.require_current()
    body_error, body_traceback = None, None
    with ExitStack() as stack:
        held = _HeldDirectories(stack)
        owned = _StagedReservationSet(pool, held)
        try:
            plans, directories = _preflight(pool, targets, held)
            group = uuid4().hex
            target_identity = (
                "sha256:"
                + hashlib.sha256(
                    canonical_json_bytes(
                        _physical_wire(
                            [
                                {
                                    "path": str(p.target.path),
                                    "anchor": str(p.target.anchor),
                                    "anchor_node": p.target.anchor_node,
                                    "advisory": p.target.advisory,
                                }
                                for p in plans
                            ]
                        )
                    )
                ).hexdigest()
            )
            for ordinal, plan in enumerate(plans):
                target = plan.target
                owned._live()
                parent = target.anchor
                for part in target.path.relative_to(target.anchor).parts[:-1]:
                    parent = parent / part
                    if parent in held.nodes:
                        continue
                    if directories[parent] is not None or os.path.lexists(parent):
                        _fail("changed", "planned absent control parent changed")
                    token = pool.stage_directory()
                    observed = pool.publish(
                        token, parent, expected_parent=layout_entry_node(parent.parent)
                    )
                    owned._directories.append(
                        (
                            parent,
                            (
                                observed.node.device,
                                observed.node.inode,
                                observed.node.mode,
                            ),
                            target,
                        )
                    )
                    held.pin(parent, expected=observed.node.directory_identity[:-1])
                expected = plan.node
                if expected is None:
                    token = pool.stage_marker(plan.content)
                    expected = pool.publish(
                        token,
                        target.path,
                        expected_parent=layout_entry_node(target.path.parent),
                    ).node
                payload = pool._journal.store_payload(plan.content)
                data = {
                    "group": group,
                    "ordinal": ordinal,
                    "target_identity": target_identity,
                    "path": str(target.path),
                    "node": _physical_wire(asdict(expected)),
                    "payload_digest": payload,
                    "advisory": target.advisory,
                }
                pool._journal.append(
                    "reservation-lease-intent", canonical_json_bytes(data)
                )
                owned._live()
                fd = os.open(
                    target.path.name,
                    os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=held.nodes[target.path.parent][0],
                )
                try:
                    marker = _OwnedMarker(
                        target,
                        fd,
                        (expected.device, expected.inode, expected.mode),
                        plan.content,
                        created=plan.node is None,
                    )
                    owned._expected[target.path] = expected
                    owned._markers.append(marker)
                except BaseException as setup_error:
                    try:
                        os.close(fd)
                    except BaseException as close_error:
                        raise combine_body_and_release_errors(
                            "staged descriptor setup",
                            setup_error,
                            setup_error.__traceback__,
                            close_error,
                        ) from None
                    raise
                owned._verify_marker(marker)
                if target.advisory:
                    _acquire(fd, target.path, timeout_seconds=0.0)
                    marker.advisory_locked = True
                    owned._verify_marker(marker)
                pool._journal.append(
                    "reservation-lease-observed", canonical_json_bytes(data)
                )
                owned._verify_marker(marker)
            owned._complete = True
            owned.verify_all()
            pool._journal.append(
                "reservation-set-acquired",
                canonical_json_bytes(
                    {
                        "group": group,
                        "target_identity": target_identity,
                        "count": len(plans),
                    }
                ),
            )
            owned.verify_all()
            yield owned
            owned.verify_all()
        except BaseException as exc:
            body_error, body_traceback = exc, exc.__traceback__
            raise
        finally:
            try:
                owned._release()
            except BaseException as release_error:
                if body_error is not None:
                    raise combine_body_and_release_errors(
                        "staged reservation", body_error, body_traceback, release_error
                    ) from None
                raise
