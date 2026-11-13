"""Fresh retained control descriptors, not transaction recovery or saved roles.

The caller must separately derive actual canonical roles and classify all source
and metadata endpoints before any recovery effect. No marker is created, rewritten
or removed here, and a retired private token never owns its former public name.
"""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, fields
from pathlib import Path

from literate_ai._cache_lock import _acquire
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from ._write_reservations import (
    _CREATION_KEY,
    WriteReservationSet,
    WriteReservationTarget,
    _OwnedMarker,
    combine_body_and_release_errors,
)
from .exclusive_entry import LayoutEntryNode, _from_stat, layout_entry_node
from .repository_refresh import _file
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_publication import _ControlPool, _pinned_directory
from .retained_layout_journal import _file as _journal_file
from .retained_layout_partition import _lineage, _physical_wire
from .retained_layout_reservations import _HeldDirectories, _portable_name


def _fail(message):
    raise ValueError("layout.recovery-controls: " + message)


def _node(document):
    names = {field.name for field in fields(LayoutEntryNode)}
    if type(document) is not dict or set(document) != names:
        _fail("invalid recorded native node")
    values = dict(document)
    for name in names - {"native_identity", "link_target"}:
        value = values[name]
        if type(value) is dict and set(value) == {"integer_decimal"}:
            raw = value["integer_decimal"]
            if type(raw) is not str or not 1 <= len(raw) <= 128:
                _fail("invalid recorded native integer")
            value = int(raw)
            if str(value) != raw:
                _fail("noncanonical recorded native integer")
        if type(value) is not int:
            _fail("invalid recorded native integer")
        values[name] = value
    if values["native_identity"] is not None or values["link_target"] is not None:
        _fail("direct POSIX control node required")
    return LayoutEntryNode(**values)


def _optional_node(path):
    try:
        return layout_entry_node(path)
    except FileNotFoundError:
        return None


def _read_marker(path):
    before = layout_entry_node(path)
    if (
        not stat.S_ISREG(before.mode)
        or before.links != 1
        or before.uid != os.geteuid()
        or not 1 <= before.size <= 256
    ):
        _fail("existing bounded owned single-link marker required")
    content = _file(path, maximum_bytes=256).content
    if layout_entry_node(path) != before or len(content) != before.size:
        _fail("marker changed during observation")
    return before, content


def _names(root, limit):
    names = set()
    with os.scandir(root) as entries:
        for entry in entries:
            if len(names) >= limit:
                _fail("retirement namespace exceeds its bound")
            names.add(entry.name)
    return tuple(sorted(names))


@dataclass(frozen=True, slots=True)
class _RecoveryMarker:
    target: WriteReservationTarget
    named: Path
    node: LayoutEntryNode
    content: bytes


@dataclass(frozen=True, slots=True)
class _ControlRecoveryPlan:
    pool_root: Path
    header: bytes
    history: tuple[bytes, ...]
    markers: tuple[_RecoveryMarker, ...]
    lineages: tuple
    retirement_root: Path | None
    retirement_names: tuple[str, ...]
    public_nodes: tuple

    @property
    def identity(self):
        return canonical_identity(_custody_wire(self))


def _records(journal, targets):
    events = journal.events
    complete = [e["data"] for e in events if e["kind"] == "reservation-set-acquired"]
    if len(complete) != 1:
        _fail("one complete original reservation set required; retain incomplete state")
    acquired = complete[0]
    leases = [
        e["data"]
        for e in events
        if e["kind"] == "reservation-lease-intent"
        and e["data"].get("group") == acquired["group"]
    ]
    leases.sort(key=lambda item: item["ordinal"])
    by_path = {str(target.path): target for target in targets}
    if (
        len(by_path) != len(targets)
        or len(leases) != acquired["count"]
        or len(leases) != len(targets)
        or [item["ordinal"] for item in leases] != list(range(len(leases)))
        or {item["path"] for item in leases} != set(by_path)
    ):
        _fail("complete actual target coordinates required")
    ordered = [by_path[item["path"]] for item in leases]
    identity = (
        "sha256:"
        + hashlib.sha256(
            canonical_json_bytes(
                _physical_wire(
                    [
                        {
                            "path": str(t.path),
                            "anchor": str(t.anchor),
                            "anchor_node": t.anchor_node,
                            "advisory": t.advisory,
                        }
                        for t in ordered
                    ]
                )
            )
        ).hexdigest()
    )
    if identity != acquired["target_identity"] or any(
        item["target_identity"] != identity or item["advisory"] is not target.advisory
        for item, target in zip(leases, ordered, strict=True)
    ):
        _fail("recorded acquisition disagrees with actual targets")
    return events, leases, ordered


def _one(events, kind, key, value):
    found = [
        event["data"]
        for event in events
        if event["kind"] == kind and event["data"].get(key) == value
    ]
    if len(found) > 1:
        _fail("ambiguous repeated control history")
    return found[0] if found else None


def plan_layout_control_recovery(pool, targets):
    """Observe existing endpoints; no OS mutex, marker mutation or role grant."""
    if (
        os.name != "posix"
        or type(pool) is not _ControlPool
        or type(targets) is not tuple
        or not 1 <= len(targets) <= 1024
        or any(type(target) is not WriteReservationTarget for target in targets)
    ):
        raise TypeError("layout.recovery-controls.live-bounded-inputs-required")
    pool.require_current()
    aliases = {unicodedata.normalize("NFC", str(t.path).casefold()) for t in targets}
    if len(aliases) != len(targets) or any(
        target.path in other.path.parents for target in targets for other in targets
    ):
        _fail("target coordinates alias or overlap")
    journal = pool._journal
    events, leases, ordered = _records(journal, targets)
    finalization = [
        event["data"]
        for event in events
        if event["kind"] == "control-finalization-intent"
    ]
    if len(finalization) > 1:
        _fail("ambiguous finalization history")
    retirement_root = None
    if finalization:
        data = finalization[0]
        retirement_root = Path(data["root"])
        if not retirement_root.is_absolute() or ".." in retirement_root.parts:
            _fail("invalid retirement coordinate")
        declared = data["controls"]
        if len(declared) != len(leases) or {item["path"] for item in declared} != {
            item["path"] for item in leases
        }:
            _fail("finalization does not cover complete original set")
        by_path = {item["path"]: item for item in declared}
        for lease in leases:
            item = by_path[lease["path"]]
            if (
                _node(item["node"]) != _node(lease["node"])
                or item["advisory"] is not lease["advisory"]
                or type(item["created"]) is not bool
            ):
                _fail("finalization control facts disagree with original acquisition")
        node = layout_entry_node(retirement_root)
        if (
            node.directory_identity != _node(data["node"]).directory_identity
            or node.uid != os.geteuid()
            or stat.S_IMODE(node.mode) != 0o700
        ):
            _fail("retirement directory changed")
    protected = {
        (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
        for fd in (pool._descriptor, journal._descriptor)
    }
    markers, public_nodes, lineages = [], [], {}
    if retirement_root is not None:
        ancestry = _lineage(retirement_root)
        if any(record[1:3] in protected for record in ancestry):
            _fail("retirement state overlaps current private producer")
        lineages[retirement_root] = ancestry
    for lease, target in zip(leases, ordered, strict=True):
        WriteReservationSet._guard(target)
        original = _node(lease["node"])
        content = journal.read_payload(lease["payload_digest"])
        if not 1 <= len(content) <= 256:
            _fail("invalid original marker payload")
        current, named = _optional_node(target.path), target.path
        normal = _one(events, "advisory-normalization-intent", "path", str(target.path))
        normal_observed = _one(
            events, "advisory-normalization-observed", "path", str(target.path)
        )
        retire = _one(
            events, "native-control-retirement-intent", "source", str(target.path)
        )
        retired = _one(
            events, "native-control-retirement-observed", "source", str(target.path)
        )
        if retire:
            destination = Path(retire["destination"])
            if (
                target.advisory
                or retirement_root is None
                or destination.parent != retirement_root
                or destination.name not in {f"control-{i}" for i in range(len(targets))}
                or _node(retire["node"]) != original
                or journal.read_payload(retire["payload"]) != content
                or layout_entry_node(target.path.parent).directory_identity
                != _node(retire["source_parent"]).directory_identity
                or layout_entry_node(retirement_root).directory_identity
                != _node(retire["destination_parent"]).directory_identity
            ):
                _fail("invalid native retirement intent")
            private = _optional_node(destination)
            if private is not None:
                if private.after_rename() != original.after_rename():
                    _fail("retired marker was replaced")
                if current is not None and (current.device, current.inode) == (
                    original.device,
                    original.inode,
                ):
                    _fail("both marker endpoints contain original node")
                public_nodes.append((target.path, current))
                named, current = destination, private
            elif retired:
                _fail("recorded retired marker is missing")
        elif retired:
            _fail("retirement observation lacks intent")
        if current is None:
            _fail("original marker is missing; retain unresolved endpoints")
        actual, observed = _read_marker(named)
        if actual != current:
            _fail("marker changed during endpoint classification")
        if normal:
            entries = (
                {item["path"]: item for item in finalization[0]["controls"]}
                if finalization
                else {}
            )
            declared = entries.get(str(target.path), {})
            if (
                not target.advisory
                or declared.get("created") is not True
                or _node(normal["node"]) != original
                or journal.read_payload(normal["before"]) != content
                or journal.read_payload(normal["after"]) != b"\0"
            ):
                _fail("invalid advisory normalization intent")
            immutable = ("device", "inode", "mode", "links", "uid", "gid")
            if any(getattr(actual, key) != getattr(original, key) for key in immutable):
                _fail("normalized marker was replaced")
            if observed not in (content, b"\0" + content[1:], b"\0"):
                _fail("unknown normalization bytes")
            if normal_observed and (
                actual != _node(normal_observed["node"]) or observed != b"\0"
            ):
                _fail("observed normalized marker changed")
        elif observed != content or (
            actual != original
            if named == target.path
            else actual.after_rename() != original.after_rename()
        ):
            _fail("retained marker changed")
        if retired and actual != _node(retired["node"]):
            _fail("observed retired marker changed")
        if normal_observed and not normal:
            _fail("normalization observation lacks intent")
        for parent in (target.anchor, target.path.parent, named.parent):
            ancestry = _lineage(parent)
            if any(record[1:3] in protected for record in ancestry):
                _fail("control overlaps current private producer")
            lineages[parent] = ancestry
            if (
                len({record[0] for value in lineages.values() for record in value})
                > 4096
            ):
                _fail("recovery ancestry exceeds its bound")
        with _pinned_directory(named.parent) as (fd, guard):
            _portable_name(named, fd, present=True)
            guard()
        markers.append(_RecoveryMarker(target, named, actual, observed))
    if retirement_root is not None and (
        layout_entry_node(retirement_root).directory_identity
        != _node(finalization[0]["node"]).directory_identity
    ):
        _fail("retirement directory changed during observation")
    names = _names(retirement_root, len(targets)) if retirement_root else ()
    if set(names) != {m.named.name for m in markers if m.named != m.target.path}:
        _fail("retirement namespace contains foreign or missing entries")
    if len({(m.node.device, m.node.inode) for m in markers}) != len(markers):
        _fail("control native identities alias")
    if any(m.node.device != os.fstat(pool._descriptor).st_dev for m in markers):
        _fail("recovery controls require one filesystem")
    plan = _ControlRecoveryPlan(
        pool.root,
        journal._known["header.json"][1],
        tuple(journal._known[name][1] for name in journal._events),
        tuple(markers),
        tuple(lineages.items()),
        retirement_root,
        names,
        tuple(public_nodes),
    )
    _require_inputs(pool, plan)
    return plan


def _require_inputs(pool, plan):
    pool.require_current()
    if (
        pool.root != plan.pool_root
        or pool._journal._known["header.json"][1] != plan.header
    ):
        _fail("recovery producer or journal binding changed")
    for index, raw in enumerate(plan.history):
        if pool._journal._known.get(f"e-{index:04d}.json", (None, None))[1] != raw:
            _fail("original recovery history changed")
    for path, ancestry in plan.lineages:
        if _lineage(path) != ancestry:
            _fail("recovery ancestry changed")
    for marker in plan.markers:
        if _read_marker(marker.named) != (marker.node, marker.content):
            _fail("prepared recovery marker changed")
    _close_inputs(plan)
    # Marker/portable-name observations can be the last blocking reads. Close
    # immutable producer facts afterwards, before granting any descriptor lease.
    _close_dependencies(pool)
    _close_retirement(plan)


def _close_dependencies(pool):
    journal = pool._journal
    journal._guard()
    expected = set(journal._known)
    if journal._names() != expected:
        _fail("journal namespace changed during recovery observation")
    for name, (signature, _) in journal._known.items():
        named = os.stat(name, dir_fd=journal._descriptor, follow_symlinks=False)
        if _journal_file(named) != signature:
            _fail("journal native facts changed during recovery observation")
    if journal._names() != expected:
        _fail("journal namespace changed during closing observations")
    pool._require_private_close()
    journal._guard()


def _close_inputs(plan):
    for marker in plan.markers:
        with _pinned_directory(marker.named.parent) as (fd, guard):
            _portable_name(marker.named, fd, present=True)
            guard()
        if layout_entry_node(marker.named) != marker.node:
            _fail("recovery marker native facts changed")
    for path, expected in plan.public_nodes:
        with _pinned_directory(path.parent) as (fd, guard):
            _portable_name(path, fd, present=expected is not None)
            guard()
        if _optional_node(path) != expected:
            _fail("released public coordinate changed")
    if (
        plan.retirement_root
        and _names(plan.retirement_root, len(plan.markers)) != plan.retirement_names
    ):
        _fail("retirement namespace changed")
    for path, ancestry in plan.lineages:
        if _lineage(path) != ancestry:
            _fail("recovery ancestry changed during closing observations")


def _close_retirement(plan):
    # Preserve the exact retired namespace and physical ancestry after producer
    # closure; do not traverse payloads or reinitialize any control afterwards.
    if plan.retirement_root and (
        _names(plan.retirement_root, len(plan.markers)) != plan.retirement_names
    ):
        _fail("retirement namespace changed after dependency closure")
    for path, ancestry in plan.lineages:
        if _lineage(path) != ancestry:
            _fail("recovery ancestry changed after dependency closure")


class _RecoveredControlSet(WriteReservationSet):
    def __init__(self, pool, plan, held):
        super().__init__(_CREATION_KEY)
        self._pool, self._plan, self._held = pool, plan, held
        self._receiver = os.getpid()
        self._retain_for_recovery = True

    def _live(self):
        if not self._active or self._receiver != os.getpid():
            _fail("recovered descriptor context ended")
        self._pool._guard()
        self._held.current()

    def verify_all(self):
        self._live()
        if not self._complete:
            _fail("recovered descriptor acquisition incomplete")
        _require_inputs(self._pool, self._plan)
        for marker, expected in zip(self._markers, self._plan.markers, strict=True):
            if (
                _from_stat(os.fstat(marker.descriptor)) != expected.node
                or os.pread(marker.descriptor, len(expected.content) + 1, 0)
                != expected.content
                or _from_stat(os.fstat(marker.descriptor)) != expected.node
                or (marker.target.advisory and not marker.advisory_locked)
            ):
                _fail("actual recovered descriptor changed")
        self._pool.require_current()
        _close_inputs(self._plan)
        _close_dependencies(self._pool)
        _close_retirement(self._plan)
        self._live()

    def owns(self, path):
        self.verify_all()
        return any(marker.named == path for marker in self._plan.markers)


@contextmanager
def acquire_layout_recovery_controls(
    pool, plan, *, acknowledged_recovery_identity, allow_host_execution
):
    """Hold new exact FDs/OS locks; never infer canonical roles or recover data."""
    if type(plan) is not _ControlRecoveryPlan or allow_host_execution is not True:
        _fail("explicit current recovery execution authority required")
    current = plan_layout_control_recovery(pool, tuple(m.target for m in plan.markers))
    if current != plan or acknowledged_recovery_identity != current.identity:
        _fail("exact fresh recovery proposal acknowledgement required")
    journal = pool._journal
    if (
        len(journal._events) + 2 > journal._budget.maximum_events
        or sum(len(raw) for _, raw in journal._known.values()) + 256 * 1024
        > journal._budget.maximum_storage_bytes
    ):
        _fail("recovery acquisition exceeds remaining journal budget")
    error, trace = None, None
    with ExitStack() as stack:
        held = _HeldDirectories(stack)
        owned = _RecoveredControlSet(pool, plan, held)
        try:
            for path, _ in plan.lineages:
                held.pin(path)
            _require_inputs(pool, plan)
            data = canonical_json_bytes({"recovery_identity": plan.identity.uri})
            journal.append("control-recovery-acquisition-intent", data)
            _require_inputs(pool, plan)
            for item in plan.markers:
                fd = os.open(
                    item.named.name,
                    os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=held.nodes[item.named.parent][0],
                )
                try:
                    marker = _OwnedMarker(
                        item.target,
                        fd,
                        (item.node.device, item.node.inode, item.node.mode),
                        item.content,
                        created=False,
                    )
                    owned._markers.append(marker)
                except BaseException as setup_error:
                    try:
                        os.close(fd)
                    except BaseException as close_error:
                        raise combine_body_and_release_errors(
                            "recovered descriptor setup",
                            setup_error,
                            setup_error.__traceback__,
                            close_error,
                        ) from None
                    raise
                if (
                    _from_stat(os.fstat(fd)) != item.node
                    or os.pread(fd, len(item.content) + 1, 0) != item.content
                    or layout_entry_node(item.named) != item.node
                ):
                    _fail("opened recovered marker differs from proposal")
                if item.target.advisory:
                    _acquire(fd, item.named, timeout_seconds=0.0)
                    marker.advisory_locked = True
            owned._complete = True
            owned.verify_all()
            journal.append("control-recovery-acquisition-observed", data)
            owned.verify_all()
            yield owned
            owned.verify_all()
        except BaseException as exc:
            error, trace = exc, exc.__traceback__
            raise
        finally:
            try:
                owned._release()
            except BaseException as release_error:
                if error is not None:
                    raise combine_body_and_release_errors(
                        "recovered control", error, trace, release_error
                    ) from None
                raise
