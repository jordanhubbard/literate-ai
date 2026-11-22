"""Actual recovery control effects, with original descriptor lifetimes retained.

This internal owner completes a nonroot recovery transition, not public layout
acceptance. Its results and read-only release checks never restore writer rights.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from uuid import uuid4

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from .exclusive_entry import _from_stat, layout_entry_node, move_layout_entry_exclusive
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_roles import layout_pending_control_path
from .retained_layout_partition import _lineage
from .retained_layout_recovery_controls import (
    _CREATED_RECOVERIES,
    _close_dependencies,
    _close_dependency_facts,
    _node,
    _optional_node,
    _read_marker,
    _RecoveredControlSet,
    _recovery_area,
)
from .retained_layout_recovery_data import (
    _close_data,
    _close_data_native,
    _DataRecoveryPlan,
    _observe_data,
    _verify,
    plan_layout_data_recovery,
)
from .retained_layout_recovery_roles import _RecoveryRoleLease
from .retained_layout_reservations import _PREFIX, _StagedReservationSet

_KEY = object()


def _fail(message):
    raise ValueError("layout.recovery-disposition: " + message)


@dataclass(frozen=True, slots=True)
class _Entry:
    owner: int
    ordinal: int
    target: object
    named: Path
    node: object
    content: bytes
    group: str
    original_node: object
    original_content: bytes


@dataclass(frozen=True, slots=True)
class _DispositionPlan:
    data: _DataRecoveryPlan
    entries: tuple
    bindings: tuple
    areas: tuple
    retirement: object
    public_nodes: tuple
    history: tuple

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/layout-recovery-disposition@1",
                "plan": _custody_wire(self),
            }
        )


def _owners(roles):
    catalog = roles.reservations
    return catalog._recovered + (
        () if catalog._incoming is None else (catalog._incoming,)
    )


def _entry_owner_pin(pool, owner):
    if type(owner) not in (_RecoveredControlSet, _StagedReservationSet):
        _fail("actual original descriptor owner required")
    raw = type(owner) is _RecoveredControlSet
    registration = _CREATED_RECOVERIES.get(owner) if raw else None
    if (raw and registration is None) or owner._pool is not pool:
        _fail("actual original descriptor owner required")
    names = (
        "_pool",
        "_held",
        "_receiver",
        "_markers",
        "_active",
        "_complete",
        "_disposition",
        *(("_plan",) if raw else ("_group", "_expected", "_locations")),
    )
    attributes = tuple((name, getattr(owner, name)) for name in names)
    markers = tuple(owner._markers)
    maps = []
    if not raw:
        for name in ("_expected", "_locations"):
            value = getattr(owner, name)
            if type(value) is not dict:
                _fail("actual original descriptor mapping required")
            maps.append((value, tuple(value.items())))
    pending = [markers, owner._plan if raw else owner._group]
    pending.extend(items for _mapping, items in maps)
    seen, facts, paths = set(), [], []
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if type(value) is tuple:
            pending.extend(value)
        elif type(value) is type(Path()):
            paths.append((value, type(value), str(value)))
        elif is_dataclass(value):
            members = tuple(
                (field.name, getattr(value, field.name)) for field in fields(value)
            )
            facts.append((value, type(value), members))
            pending.extend(item for _name, item in members)
    return (
        owner,
        registration,
        attributes,
        markers,
        tuple(maps),
        tuple(facts),
        tuple(paths),
    )


def _close_entry_owners(pins):
    for owner, registration, attributes, markers, maps, facts, paths in pins:
        expected_type = (
            _RecoveredControlSet if registration is not None else _StagedReservationSet
        )
        if type(owner) is not expected_type:
            _fail("original descriptor descriptions changed")
        if (
            any(getattr(owner, name) is not value for name, value in attributes)
            or owner._active is not True
            or owner._receiver != os.getpid()
            or owner._complete is not True
            or (
                registration is not None
                and _CREATED_RECOVERIES.get(owner) is not registration
            )
            or len(owner._markers) != len(markers)
            or any(a is not b for a, b in zip(owner._markers, markers, strict=True))
            or any(
                type(value) is not kind
                or any(getattr(value, name) is not old for name, old in members)
                for value, kind, members in facts
            )
            or any(
                len(mapping) != len(items)
                or any(
                    k is not old_k or v is not old_v
                    for (k, v), (old_k, old_v) in zip(
                        mapping.items(), items, strict=True
                    )
                )
                for mapping, items in maps
            )
            or any(
                type(path) is not kind or str(path) != text
                for path, kind, text in paths
            )
        ):
            _fail("original descriptor descriptions changed")


def _entries(pool, owners, *, _event_snapshot=None):
    pins = []
    for owner in owners:
        owner.verify_all()
        pins.append(_entry_owner_pin(pool, owner))
    journal = pool._journal
    if _event_snapshot is None:
        names = tuple(journal._events)
        _event_snapshot = names, tuple(journal._known[name] for name in names)
    events, payloads = journal._raw_documents_from_snapshot(_event_snapshot)
    _close_entry_owners(pins)
    return _entries_from_documents(owners, events, dict(payloads))


def _entries_from_documents(owners, events, payloads):
    """Callback-free projection of actual producer-authenticated immutable bytes."""
    decoded = tuple(json.loads(raw) for raw in events)
    records = [e["data"] for e in decoded if e["kind"] == "reservation-lease-intent"]
    entries, bindings = [], []
    for index, owner in enumerate(owners):
        raw = type(owner) is _RecoveredControlSet
        group = owner._plan.group if raw else owner._group
        if type(group) is not str:
            _fail("actual completed descriptor generation required")
        for ordinal, marker in enumerate(owner._markers):
            if raw:
                record = owner._plan.markers[ordinal]
                named, node, content = record.named, record.node, record.content
            else:
                named = owner._locations.get(marker.target.path, marker.target.path)
                node, content = owner._expected[marker.target.path], marker.content
            leases = [
                r
                for r in records
                if r["group"] == group and r["path"] == str(marker.target.path)
            ]
            if len(leases) != 1 or leases[0]["advisory"] is not marker.target.advisory:
                _fail("original descriptor generation provenance required")
            lease = leases[0]
            original = _node(lease["node"])
            if lease["payload_digest"] not in payloads:
                raise ValueError("layout.journal.payload-not-recorded")
            original_content = payloads[lease["payload_digest"]]
            entries.append(
                _Entry(
                    index,
                    ordinal,
                    marker.target,
                    named,
                    node,
                    content,
                    group,
                    original,
                    original_content,
                )
            )
            bindings.append((id(owner), id(marker), marker.descriptor))
    return tuple(entries), tuple(bindings)


def _actions(entries):
    advisory = tuple(
        e
        for e in entries
        if e.target.advisory
        and e.original_content.startswith(_PREFIX)
        and e.content != b"\0"
    )
    native = tuple(
        e for e in entries if not e.target.advisory and e.named == e.target.path
    )
    return advisory, native


def plan_recovery_control_disposition(pool, roles, data, retirement_root):
    """Read-only fresh verified data plus actual live descriptor disposition."""
    if (
        type(roles) is not _RecoveryRoleLease
        or roles._pool is not pool
        or type(data) is not _DataRecoveryPlan
    ):
        _fail("actual same-producer canonical and data owners required")
    roles.require_current()
    fresh = plan_layout_data_recovery(pool, roles, data.private_root)
    if fresh != data or data.issues or data.actions:
        _fail("fresh fully verified restored or committed data required")
    owners = _owners(roles)
    if any(getattr(owner, "_disposition", None) is not None for owner in owners):
        _fail("descriptor owner already handed off")
    entries, bindings = _entries(pool, owners)
    retirement = _recovery_area(Path(retirement_root))
    if (
        not retirement.root.is_absolute()
        or ".." in retirement.root.parts
        or retirement.entries
    ):
        _fail("new direct empty private retirement root required")
    if any(
        e["kind"] == "recovery-control-disposition-intent"
        and e["data"].get("retirement_root") == str(retirement.root)
        for e in pool._journal.events
    ):
        _fail("previously journaled retirement root cannot be reused")
    forbidden = {
        (node.device, node.inode)
        for _, node in data.source_native
        if stat.S_ISDIR(node.mode)
    }
    forbidden.update(
        (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
        for fd in (pool._descriptor, pool._journal._descriptor)
    )
    for path in roles.protected_admin_entries:
        if path.is_dir():
            node = layout_entry_node(path)
            forbidden.add((node.device, node.inode))
    areas, public = {}, {}
    for owner in owners:
        if type(owner) is _RecoveredControlSet:
            roots = tuple(area.root for area in owner._plan.recovery_areas)
            if owner._plan.retirement_root is not None:
                roots += (owner._plan.retirement_root,)
            for root in roots:
                area = _recovery_area(root)
                if root in areas and areas[root] != area:
                    _fail("retirement namespace changed during capture")
                areas[root] = area
            public.update(owner._plan.public_nodes)
    for root in (*areas, *(area.root for area in data.areas)):
        forbidden.add((layout_entry_node(root).device, layout_entry_node(root).inode))
        if (
            layout_entry_node(retirement.root).device,
            layout_entry_node(retirement.root).inode,
        ) in {x[1:3] for x in _lineage(root)}:
            _fail("new retirement state contains another data or control producer")
    if forbidden.intersection(record[1:3] for record in retirement.lineage):
        _fail("retirement overlaps actual source or another producer")
    devices = {e.node.device for e in entries}
    devices.update(layout_entry_node(e.named.parent).device for e in entries)
    devices.add(layout_entry_node(retirement.root).device)
    if devices != {os.fstat(pool._descriptor).st_dev}:
        _fail("complete control disposition requires one filesystem")
    pending = layout_pending_control_path(data.root)
    if sum(not e.target.advisory and e.named == pending for e in entries) != 1:
        _fail("one actual current public pending barrier required")
    advisory, native = _actions(entries)
    records = 2 * (len(advisory) + len(native)) + 3
    journal = pool._journal
    if (
        len(journal._events) + records > journal._budget.maximum_events
        or sum(len(raw) for _, raw in journal._known.values()) + records * 128 * 1024
        > journal._budget.maximum_storage_bytes
        or len(journal._payloads) + 2 * len(advisory) + len(native)
        > journal._budget.maximum_events
    ):
        _fail("complete recovery disposition exceeds remaining journal budget")
    plan = _DispositionPlan(
        data,
        entries,
        bindings,
        tuple(areas.values()),
        retirement,
        tuple(public.items()),
        tuple(journal._known[n][1] for n in journal._events),
    )
    _verify(pool, roles, data)
    for owner in owners:
        owner.verify_all()
    if (
        _entries(pool, owners) != (entries, bindings)
        or _recovery_area(retirement.root) != retirement
    ):
        _fail("current disposition inputs changed")
    _verify(pool, roles, data)
    return plan


class RecoveryDispositionOutcomeError(RuntimeError):
    qualified = False

    def __init__(self, decision):
        self.decision = decision
        super().__init__(
            "layout.recovery-disposition: "
            + (decision or "release-decision-unknown")
            + "; retain all state for explicit recovery"
        )


class _RecoveryDisposition:
    def __init__(self, key, pool, roles, plan, owners):
        if type(plan) is not _DispositionPlan:
            from .retained_layout_forest_disposition import _initialize

            _initialize(self, key, pool, roles, plan, owners)
            return
        if (
            key is not _KEY
            or type(roles) is not _RecoveryRoleLease
            or roles._pool is not pool
            or type(plan) is not _DispositionPlan
            or type(owners) is not tuple
            or len(owners) != len(_owners(roles))
            or any(
                left is not right
                for left, right in zip(owners, _owners(roles), strict=True)
            )
        ):
            _fail("actual disposition factory required")
        if (
            plan_recovery_control_disposition(
                pool, roles, plan.data, plan.retirement.root
            )
            != plan
        ):
            _fail("actual complete current disposition inputs required")
        self._pool, self._roles, self._plan, self._owners = pool, roles, plan, owners
        self._entries_current = plan.entries
        self._areas_current = plan.areas + (plan.retirement,)
        self._receiver, self._active = os.getpid(), False
        self.finished = False
        self.decision_attempted, self.decision = False, None

    pool = property(lambda self: self._pool)
    roles = property(lambda self: self._roles)
    plan = property(lambda self: self._plan)
    owners = property(lambda self: self._owners)
    entries = property(lambda self: self._entries_current)
    areas = property(lambda self: self._areas_current)
    receiver = property(lambda self: self._receiver)
    active = property(lambda self: self._active)

    @property
    def native_released(self):
        return any(
            not old.target.advisory
            and old.named == old.target.path
            and current.named != old.named
            for old, current in zip(self.plan.entries, self.entries, strict=True)
        )

    def _resources(self, selected=None):
        if self.receiver != os.getpid():
            _fail("disposition receiver changed")
        self.pool._guard()
        for index, owner in enumerate(self.owners):
            if selected is not None and owner is not selected:
                continue
            owner._live()
            for entry, binding in zip(self.entries, self.plan.bindings, strict=True):
                if entry.owner != index:
                    continue
                marker = owner._markers[entry.ordinal]
                if (id(owner), id(marker), marker.descriptor) != binding:
                    _fail("original actual descriptor binding changed")
                if marker.target != entry.target or (
                    entry.target.advisory and not marker.advisory_locked
                ):
                    _fail("actual canonical descriptor role or mutex changed")

    def _flags(self, selected=None):
        # Last checks after native closure: no borrowed FD or payload access.
        if self.receiver != os.getpid():
            _fail("disposition receiver changed")
        for index, owner in enumerate(self.owners):
            if selected is not None and owner is not selected:
                continue
            if not owner._active or owner._receiver != os.getpid():
                _fail("original descriptor context ended")
            for entry, binding in zip(self.entries, self.plan.bindings, strict=True):
                if entry.owner == index:
                    marker = owner._markers[entry.ordinal]
                    if (id(owner), id(marker), marker.descriptor) != binding:
                        _fail("actual descriptor binding ended")

    def _markers(self, selected=None, *, native_only=False):
        for entry in self.entries:
            owner = self.owners[entry.owner]
            if selected is not None and owner is not selected:
                continue
            marker = owner._markers[entry.ordinal]
            node = _from_stat(os.fstat(marker.descriptor))
            if node != entry.node or layout_entry_node(entry.named) != entry.node:
                _fail("held or named control native facts changed")
            if (
                not native_only
                and os.pread(marker.descriptor, len(entry.content) + 1, 0)
                != entry.content
            ):
                _fail("held control bytes changed")
            if _from_stat(os.fstat(marker.descriptor)) != entry.node:
                _fail("control changed during observation")

    def _private_close(self):
        roots = []
        for area in self.areas:
            before = layout_entry_node(area.root)
            if (
                _recovery_area(area.root) != area
                or layout_entry_node(area.root) != before
            ):
                _fail("complete retirement namespace or ancestry changed")
            roots.append((area, before))
        for path, node in self.plan.public_nodes:
            if _optional_node(path) != node:
                _fail("released foreign public observation changed")
        return tuple(roots)

    def _close_private_native(self, roots):
        for area, node in roots:
            if layout_entry_node(area.root) != node:
                _fail("retirement namespace changed after data observations")
            for name, expected in area.entries:
                if layout_entry_node(area.root / name) != expected:
                    _fail("retired control changed after data observations")
        for path, node in self.plan.public_nodes:
            if _optional_node(path) != node:
                _fail("public observation changed after data observations")

    def verify(self):
        from .retained_layout_forest_disposition import _state

        forest = _state(self)
        if forest is not None:
            return forest.verify(self)
        self._resources()
        self.pool.require_current()
        _observe_data(self.plan.data)
        self._markers()
        self._private_close()
        private = self._private_close()
        self._resources()
        data_private = _close_data(self.plan.data)
        producers = _close_dependencies(self.pool)
        if not self.native_released:
            self.roles.git.close_native_inputs(self)
        self.roles._seed.close_native_inputs()
        _close_data_native(self.plan.data, data_private)
        self._markers(native_only=True)
        self._close_private_native(private)
        _close_dependency_facts(self.pool, producers)
        self.pool._guard()
        self._flags()

    def verify_descriptor_owner(self, owner):
        from .retained_layout_forest_disposition import _state

        forest = _state(self)
        if forest is not None:
            return forest.verify(self, owner)
        if owner not in self.owners or owner._disposition is not self:
            _fail("actual handed-off descriptor owner required")
        self._resources(owner)
        self.pool.require_current()
        self._markers(owner)
        private = self._private_close()
        self._resources(owner)
        producers = _close_dependencies(self.pool)
        self._markers(owner, native_only=True)
        self._close_private_native(private)
        _close_dependency_facts(self.pool, producers)
        self._flags(owner)

    def owns(self, path):
        # Native Git closure may ask about its exact held worktree mutex. This
        # observation supplies no ordinary canonical role or new writer grant.
        self._resources()
        self._markers(native_only=True)
        self._flags()
        return any(e.named == path == e.target.path for e in self.entries)

    def verify_role_exit(self, roles):
        if roles is not self.roles or roles._disposition is not self:
            _fail("actual canonical handoff required")
        self.verify()
        if (
            not self.finished
            or _actions(self.entries) != ((), ())
            or os.path.lexists(layout_pending_control_path(self.plan.data.root))
        ):
            _fail("recovery disposition incomplete; retain all state")

    def _writer(self):
        self._writer_binding()
        self.verify()
        self._writer_binding()

    def _writer_binding(self):
        if not self.active or self.receiver != os.getpid():
            _fail("disposition writer context ended")
        if (
            not self.roles._active
            or not self.roles._finalizing
            or self.roles._disposition is not self
            or self.roles.reservations._active
            or any(owner._disposition is not self for owner in self.owners)
        ):
            _fail("actual canonical/descriptor handoff ended")

    def raise_outcome(self, error):
        """Annotate a past durable decision; never revive ownership after close."""
        if not self.decision_attempted or isinstance(
            error, RecoveryDispositionOutcomeError
        ):
            return
        outcome = RecoveryDispositionOutcomeError(self.decision)
        if isinstance(error, Exception):
            raise outcome from error
        if str(outcome) not in getattr(error, "__notes__", ()):
            error.add_note(str(outcome))

    def _adopt(self, entry, node, content, destination=None):
        from .retained_layout_forest_disposition import _state

        forest = _state(self)
        if forest is not None:
            return forest.advance(self, entry, node, content, destination)
        updated = replace(
            entry, node=node, content=content, named=destination or entry.named
        )
        self._entries_current = tuple(
            updated if e is entry else e for e in self.entries
        )
        if destination is not None:
            areas = []
            for area in self.areas:
                if area.root == destination.parent:
                    entries = dict(area.entries)
                    if destination.name in entries:
                        _fail("retirement destination already tracked")
                    entries[destination.name] = node
                    area = replace(area, entries=tuple(sorted(entries.items())))
                areas.append(area)
            self._areas_current = tuple(areas)

    def _event(self, kind, data):
        from .retained_layout_forest_disposition import _state

        forest = _state(self)
        if forest is not None:
            return forest.event(self, kind, data)
        self.pool._journal.append(kind, canonical_json_bytes(data))

    def _payload(self, content):
        from .retained_layout_forest_disposition import _state

        forest = _state(self)
        if forest is not None:
            return forest.payload(self, content)
        return self.pool._journal.store_payload(content)

    def _observed_marker(self, path):
        from .retained_layout_forest_disposition import _state

        forest = _state(self)
        if forest is not None:
            return forest.read_marker(self, path)
        return _read_marker(path)

    def _native_admission(self, kind, entry, *, before=False, enter=False):
        from .retained_layout_forest_disposition import _state

        forest = _state(self)
        if forest is not None:
            forest.admit(self, kind, entry, before=before, enter=enter)

    def _intent(self, entry, kind, **extra):
        self._writer()
        data = {
            "operation": uuid4().hex,
            "group": entry.group,
            "path": str(entry.target.path),
            "source_phase_identity": self.plan.data.phase_identity,
            "original_node": _custody_wire(entry.original_node),
            "node": _custody_wire(entry.node),
            "before_payload": self._payload(entry.content),
            **extra,
        }
        self._event(kind + "-intent", data)
        self._writer()
        return data

    def normalize(self, entry):
        self._native_admission("normalize", entry, enter=True)
        self._writer()
        if entry not in self.entries or entry not in _actions(self.entries)[0]:
            _fail("exact still-owned advisory token required")
        data = self._intent(entry, "recovery-control-normalization")
        marker = self.owners[entry.owner]._markers[entry.ordinal]
        self._native_admission("normalize", entry, before=True)
        if os.pwrite(marker.descriptor, b"\0", 0) != 1:
            _fail("advisory normalization made no progress")
        self._native_admission("normalize", entry, before=True)
        os.ftruncate(marker.descriptor, 1)
        self._native_admission("normalize", entry, before=True)
        os.fsync(marker.descriptor)
        actual = _from_stat(os.fstat(marker.descriptor))
        immutable = ("device", "inode", "mode", "links", "uid", "gid")
        if (
            any(getattr(actual, k) != getattr(entry.node, k) for k in immutable)
            or self._observed_marker(entry.named) != (actual, b"\0")
            or _from_stat(os.fstat(marker.descriptor)) != actual
        ):
            _fail("normalized advisory ownership changed")
        self._adopt(entry, actual, b"\0")
        self._writer()
        self._event(
            "recovery-control-normalization-observed",
            {**data, "observed_node": _custody_wire(actual)},
        )
        self._writer()

    def retire(self, entry, ordinal):
        self._native_admission("retire", entry, enter=True)
        self._writer()
        if entry not in self.entries or entry not in _actions(self.entries)[1]:
            _fail("exact still-owned public native marker required")
        root = self.plan.retirement.root
        destination = root / f"control-{ordinal}"
        source_parent, destination_parent = (
            layout_entry_node(entry.named.parent),
            layout_entry_node(root),
        )
        data = self._intent(
            entry,
            "recovery-control-retirement",
            source=str(entry.named),
            destination=str(destination),
            source_parent=_custody_wire(source_parent),
            destination_parent=_custody_wire(destination_parent),
        )
        move_layout_entry_exclusive(
            entry.named,
            destination,
            expected_source=entry.node,
            expected_source_parent=source_parent,
            expected_destination_parent=destination_parent,
            _before_effect=lambda: self._native_admission("retire", entry, before=True),
        )
        owner = self.owners[entry.owner]
        for parent in (entry.named.parent, root):
            os.fsync(owner._held.nodes[parent][0])
            owner._held.current()
        marker = owner._markers[entry.ordinal]
        actual = _from_stat(os.fstat(marker.descriptor))
        if (
            actual.after_rename() != entry.node.after_rename()
            or self._observed_marker(destination) != (actual, entry.content)
            or _from_stat(os.fstat(marker.descriptor)) != actual
        ):
            _fail("retired native ownership changed")
        self._adopt(entry, actual, entry.content, destination)
        self._writer()
        self._event(
            "recovery-control-retirement-observed",
            {**data, "observed_node": _custody_wire(actual)},
        )
        self._writer()


def apply_recovery_control_disposition(
    pool, roles, plan, *, acknowledged_recovery_identity, allow_host_execution
):
    if type(plan) is not _DispositionPlan or allow_host_execution is not True:
        _fail("explicit current recovery disposition execution authority required")
    fresh = plan_recovery_control_disposition(
        pool, roles, plan.data, plan.retirement.root
    )
    if fresh != plan or acknowledged_recovery_identity != fresh.identity:
        _fail("exact fresh recovery disposition acknowledgement required")
    owners = _owners(roles)
    for owner in owners:
        owner._held.pin(plan.retirement.root)
    effect = _RecoveryDisposition(_KEY, pool, roles, plan, owners)
    effect.verify()
    effect._event(
        "recovery-control-disposition-intent",
        {
            "source_phase_identity": plan.data.phase_identity,
            "disposition_identity": plan.identity.uri,
            "retirement_root": str(plan.retirement.root),
            "retirement_node": _custody_wire(layout_entry_node(plan.retirement.root)),
            "data_identity": plan.data.identity.uri,
            "qualified": False,
        },
    )
    effect.verify()
    roles._finalizing = True
    roles.reservations._active = False
    roles._disposition = effect
    for owner in owners:
        owner._disposition = effect
    effect._active = True
    try:
        for entry in _actions(effect.entries)[0]:
            effect.normalize(entry)
        native = sorted(
            _actions(effect.entries)[1],
            key=lambda e: e.target.path == layout_pending_control_path(plan.data.root),
        )
        state = (
            "committed-unqualified"
            if plan.data.committed
            else "original-data-restored-unqualified"
        )
        for ordinal, entry in enumerate(native):
            if entry.target.path == layout_pending_control_path(plan.data.root):
                effect._writer()
                effect.decision_attempted = True
                effect._event(
                    "recovery-control-release-decision",
                    {
                        "source_phase_identity": plan.data.phase_identity,
                        "disposition_identity": plan.identity.uri,
                        "state": state,
                        "pending_control": str(entry.target.path),
                        "qualified": False,
                    },
                )
                effect.decision = state
                effect._writer()
            effect.retire(entry, ordinal)
        effect._writer()
        if _actions(effect.entries) != ((), ()):
            _fail("actual recovery controls not fully disposed")
        if os.path.lexists(layout_pending_control_path(plan.data.root)):
            _fail("pending coordinate now occupied; retain foreign state")
        effect._event(
            "recovery-control-disposition-observed",
            {
                "source_phase_identity": plan.data.phase_identity,
                "disposition_identity": plan.identity.uri,
                "state": state,
                "qualified": False,
            },
        )
        effect._writer()
        effect.finished = True
        return {
            "state": state,
            "qualified": False,
            "controls_released": True,
            "internal_recovery_complete": True,
            "feature_complete": False,
        }
    except BaseException as error:
        effect.raise_outcome(error)
        raise
    finally:
        effect._active = False
