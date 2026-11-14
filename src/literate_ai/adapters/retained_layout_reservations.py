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
from pathlib import Path
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
from .exclusive_entry import (
    LayoutEntryNode,
    _from_stat,
    layout_entry_node,
    move_layout_entry_exclusive,
)
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
                from .bounded_role_observation import current_role_observation

                observation = current_role_observation()
                content = (
                    _read_document(target.path, maximum_bytes=256)
                    if observation is None
                    else observation.file(target.path, maximum_bytes=256).content
                )
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
        self._locations = {}
        self._normal = set()
        self._finishing = False
        self._finalized = False
        self._retirement_root = None
        self._disposition = None
        self._group = None
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
        path = self._locations.get(marker.target.path, marker.target.path)
        expected = self._expected[marker.target.path]
        if (
            _from_stat(os.fstat(marker.descriptor)) != expected
            or layout_entry_node(path) != expected
        ):
            _fail("changed", "staged reservation native identity changed")
        if os.pread(marker.descriptor, len(marker.content) + 1, 0) != marker.content:
            _fail("changed", "staged reservation bytes changed")
        _portable_name(
            path,
            self._held.nodes[path.parent][0],
            present=True,
        )
        if (
            _from_stat(os.fstat(marker.descriptor)) != expected
            or layout_entry_node(path) != expected
        ):
            _fail("changed", "staged reservation changed during closing observation")
        self._live()

    def verify_all(self):
        if self._disposition is not None:
            from .retained_layout_recovery_disposition import _RecoveryDisposition

            if type(self._disposition) is not _RecoveryDisposition:
                _fail("inactive", "actual disposition owner required")
            return self._disposition.verify_descriptor_owner(self)
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
            path = self._locations.get(marker.target.path, marker.target.path)
            _portable_name(
                path,
                self._held.nodes[path.parent][0],
                present=True,
            )
        self._close_currentness()

    def _close_marker_inputs(self):
        """Only held/named marker facts; no payload or namespace traversal."""
        self._live()
        if not self._complete:
            _fail("inactive", "staged reservations are not complete")
        # Earlier markers may have changed during later bounded payload/name
        # reads. Close every held/named native identity after those observations.
        for marker in self._markers:
            expected = self._expected[marker.target.path]
            path = self._locations.get(marker.target.path, marker.target.path)
            parent_fd = self._held.nodes[path.parent][0]
            named = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                _from_stat(named) != expected
                or _from_stat(os.fstat(marker.descriptor)) != expected
            ):
                _fail("changed", "staged reservation set changed during final closure")

    def _close_currentness(self):
        """Close already-read native/dependency facts without payload traversal."""
        self._close_marker_inputs()
        self._close_dependencies()
        if self._retirement_root is not None:
            expected_names = {path.name for path in self._locations.values()}
            with os.scandir(self._held.nodes[self._retirement_root][0]) as entries:
                names = set()
                for entry in entries:
                    if len(names) >= 1024:
                        _fail("limit", "retired control namespace exceeds its bound")
                    names.add(entry.name)
            if names != expected_names:
                _fail("changed", "retired control namespace changed")
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

    def _native_dependency_closer(self):
        """Bind original private facts for a later stat-only closing pass.

        The enclosing reader must check dependency membership after its last
        namespace traversal. This closer then checks known files and directory
        stamps without starting another payload or membership read.
        """
        self._live()
        pool, journal = self._pool, self._pool._journal
        directories = tuple(
            (descriptor, _from_stat(os.fstat(descriptor)))
            for descriptor in (pool._descriptor, journal._descriptor)
        )
        records = tuple((name, value[0]) for name, value in journal._known.items())
        stages = tuple(pool._entries.values())

        def close():
            self._live()
            if pool._poisoned or journal._poisoned:
                _fail("changed", "private dependency writer was interrupted")
            self._close_marker_inputs()
            for name, expected in records:
                current = os.stat(
                    name, dir_fd=journal._descriptor, follow_symlinks=False
                )
                if _journal_file(current) != expected:
                    _fail("changed", "original journal native facts changed")
            for stage in stages:
                current = os.stat(
                    stage.name, dir_fd=pool._descriptor, follow_symlinks=False
                )
                if _from_stat(current) != stage.node:
                    _fail("changed", "original private stage changed")
            for descriptor, expected in directories:
                if _from_stat(os.fstat(descriptor)) != expected:
                    _fail("changed", "private dependency namespace changed")
            self._live()

        return close

    def owns(self, path):
        self._unhanded()
        self.verify_all()
        return path not in self._locations and any(
            marker.target.path == path for marker in self._markers
        )

    def begin_finalization(self, retirement_root):
        """One-way live control handoff, never a source/commit authorization."""
        self._unhanded()
        self.verify_all()
        if self._finishing:
            _fail("inactive", "control finalization already started")
        retirement_root = Path(retirement_root)
        self._held.pin(retirement_root)
        node = retirement_root.lstat()
        with os.scandir(self._held.nodes[retirement_root][0]) as entries:
            occupied = next(entries, None) is not None
        if (
            node.st_uid != os.geteuid()
            or stat.S_IMODE(node.st_mode) != 0o700
            or occupied
        ):
            _fail("changed", "control retirement requires empty owned private state")
        devices = {
            os.fstat(self._pool._descriptor).st_dev,
            os.fstat(self._pool._journal._descriptor).st_dev,
            os.fstat(self._held.nodes[retirement_root][0]).st_dev,
        }
        for marker in self._markers:
            devices.add(self._expected[marker.target.path].device)
            devices.add(os.fstat(marker.descriptor).st_dev)
            devices.add(os.fstat(self._held.nodes[marker.target.path.parent][0]).st_dev)
        if devices != {node.st_dev}:
            _fail(
                "changed",
                "control retirement requires one filesystem before normalization",
            )
        self._pool._journal.append(
            "control-finalization-intent",
            canonical_json_bytes(
                {
                    "root": str(retirement_root),
                    "node": _physical_wire(asdict(layout_entry_node(retirement_root))),
                    "controls": [
                        {
                            "path": str(m.target.path),
                            "node": _physical_wire(
                                asdict(self._expected[m.target.path])
                            ),
                            "advisory": m.target.advisory,
                            "created": m.created,
                        }
                        for m in self._markers
                    ],
                }
            ),
        )
        self.verify_all()
        self._retirement_root = retirement_root
        self._finishing = True

    def normalize_advisory(self, path):
        self._unhanded()
        self.verify_all()
        if not self._finishing or self._finalized:
            _fail("inactive", "live finalization required")
        marker = next(m for m in self._markers if m.target.path == path)
        if not marker.target.advisory or not marker.created or path in self._normal:
            _fail("changed", "only a newly created live advisory can be normalized")
        before = self._expected[path]
        journal = self._pool._journal
        data = {
            "path": str(path),
            "node": _physical_wire(asdict(before)),
            "before": journal.store_payload(marker.content),
            "after": journal.store_payload(b"\0"),
        }
        journal.append("advisory-normalization-intent", canonical_json_bytes(data))
        self.verify_all()
        if os.pwrite(marker.descriptor, b"\0", 0) != 1:
            _fail("changed", "advisory normalization made no progress")
        os.ftruncate(marker.descriptor, 1)
        os.fsync(marker.descriptor)
        after = _from_stat(os.fstat(marker.descriptor))
        if (
            (after.device, after.inode, after.mode, after.links, after.uid, after.gid)
            != (
                before.device,
                before.inode,
                before.mode,
                before.links,
                before.uid,
                before.gid,
            )
            or after.size != 1
            or os.pread(marker.descriptor, 2, 0) != b"\0"
            or layout_entry_node(path) != after
            or _from_stat(os.fstat(marker.descriptor)) != after
        ):
            _fail("changed", "normalized advisory native ownership changed")
        marker.content = b"\0"
        self._expected[path] = after
        self._normal.add(path)
        journal.append(
            "advisory-normalization-observed",
            canonical_json_bytes({**data, "node": _physical_wire(asdict(after))}),
        )
        self.verify_all()

    def retire_native(self, path):
        """Quarantine one exact native marker; never delete or replace it."""
        self._unhanded()
        self.verify_all()
        if not self._finishing or self._finalized or path in self._locations:
            _fail("inactive", "live unspent native control required")
        marker = next(m for m in self._markers if m.target.path == path)
        if marker.target.advisory:
            _fail("changed", "advisory mutex inodes must remain in place")
        destination = self._retirement_root / f"control-{len(self._locations)}"
        before = self._expected[path]
        source_parent = layout_entry_node(path.parent)
        destination_parent = layout_entry_node(destination.parent)
        data = {
            "source": str(path),
            "destination": str(destination),
            "node": _physical_wire(asdict(before)),
            "source_parent": _physical_wire(asdict(source_parent)),
            "destination_parent": _physical_wire(asdict(destination_parent)),
            "payload": self._pool._journal.store_payload(marker.content),
        }
        self._pool._journal.append(
            "native-control-retirement-intent", canonical_json_bytes(data)
        )
        self.verify_all()
        move_layout_entry_exclusive(
            path,
            destination,
            expected_source=before,
            expected_source_parent=source_parent,
            expected_destination_parent=destination_parent,
        )
        for parent in (path.parent, destination.parent):
            os.fsync(self._held.nodes[parent][0])
        after = _from_stat(os.fstat(marker.descriptor))
        if (
            after.after_rename() != before.after_rename()
            or layout_entry_node(destination) != after
            or os.pread(marker.descriptor, len(marker.content) + 1, 0) != marker.content
            or _from_stat(os.fstat(marker.descriptor)) != after
        ):
            _fail("changed", "retired native control ownership changed")
        self._locations[path] = destination
        self._expected[path] = after
        self._pool._journal.append(
            "native-control-retirement-observed",
            canonical_json_bytes({**data, "node": _physical_wire(asdict(after))}),
        )
        self.verify_all()
        return destination, after, marker.content

    def verify_finalized(self):
        self.verify_all()
        if not self._finishing or any(
            (
                m.target.advisory
                and m.created
                and (m.target.path not in self._normal or m.content != b"\0")
            )
            or (not m.target.advisory and m.target.path not in self._locations)
            for m in self._markers
        ):
            _fail("inactive", "actual controls are not fully finalized")

    def finish_finalization(self):
        self.verify_finalized()
        self._finalized = True

    def owns_directory(self, path):
        self._unhanded()
        self._live()
        result = super().owns_directory(path)
        self._live()
        return result

    def _unhanded(self):
        if self._disposition is not None:
            _fail("inactive", "ordinary staged writer handed off")


def _raise_disposition_outcome(owner, error):
    disposition = getattr(owner, "_disposition", None)
    if disposition is not None:
        from .retained_layout_recovery_disposition import _RecoveryDisposition

        if type(disposition) is _RecoveryDisposition and any(
            item is owner for item in disposition.owners
        ):
            disposition.raise_outcome(error)


@contextmanager
def _disposition_exit_boundary(owner):
    """Keep decision information through the original complete resource stack."""
    try:
        yield
    except BaseException as error:
        _raise_disposition_outcome(owner, error)
        raise


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
    stack = ExitStack()
    held = _HeldDirectories(stack)
    owned = _StagedReservationSet(pool, held)
    with _disposition_exit_boundary(owned), stack:
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
            owned._group = group
            yield owned
            owned.verify_all()
        except BaseException as exc:
            body_error, body_traceback = exc, exc.__traceback__
            _raise_disposition_outcome(owned, exc)
            raise
        finally:
            try:
                owned._release()
            except BaseException as release_error:
                if body_error is not None:
                    combined = combine_body_and_release_errors(
                        "staged reservation", body_error, body_traceback, release_error
                    )
                    _raise_disposition_outcome(owned, combined)
                    raise combined from None
                _raise_disposition_outcome(owned, release_error)
                raise
