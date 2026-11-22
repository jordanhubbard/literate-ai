"""Live forest-data handoff to the actual canonical descriptor disposition owner.

Plans remain descriptions. Only this factory registers the same observer, real
canonical lease and freshly verified complete forest for the shared native writer.
Original source admission and the legacy data-recovery guard remain independent.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from pathlib import Path
from weakref import WeakKeyDictionary, ref

from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)

from . import retained_layout_forest_recovery as recovery
from . import retained_layout_recovery_disposition as controls
from .exclusive_entry import _from_stat, layout_entry_node
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_roles import layout_pending_control_path
from .retained_layout_forest_disposition_reads import (
    close_projection,
    project_control_reads,
    read_owned_marker,
    require_fixed_control_reads,
    require_projection,
    require_successors,
    seal_projection,
    seal_successors,
)
from .retained_layout_forest_native import _Action, _advance_move, _rows
from .retained_layout_forest_observation import _record
from .retained_layout_forest_span import _require_current, _shape
from .retained_layout_recovery_controls import (
    _close_dependencies,
    _close_dependency_facts,
    _recovery_area,
)
from .retained_layout_recovery_roles import _CREATED_ROLES

_PLANS = WeakKeyDictionary()
_STATES = WeakKeyDictionary()
_DISPATCH = WeakKeyDictionary()
_COUPONS = WeakKeyDictionary()
_MARKER_READS = WeakKeyDictionary()
_READING = WeakKeyDictionary()
_INFLIGHT = WeakKeyDictionary()
_RECORDING = WeakKeyDictionary()


def _fail(message):
    raise ValueError("layout.forest-disposition: " + message)


def _wire(value):
    return canonical_json_bytes(_custody_wire(value))


@dataclass(frozen=True, slots=True, eq=False, weakref_slot=True)
class _ForestDispositionPlan:
    data: object
    entries: tuple
    bindings: tuple
    areas: tuple
    retirement: object
    public_nodes: tuple
    span: object
    history: tuple

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/forest-control-disposition@2",
                "recording": "hash-linked-control-payloads@1",
                "plan": _custody_wire(self),
            }
        )


def _history(journal):
    return tuple(journal._known.items()), tuple(journal._events)


def _close_history(journal, history):
    roster, events = history
    if (
        len(journal._known) != len(roster)
        or tuple(journal._events) != events
        or any(journal._known.get(name) is not row for name, row in roster)
    ):
        _fail("original disposition journal history changed")


def _coordinate(span, path):
    found = [
        (i, root)
        for i, root in enumerate(span.roots)
        if path != root.root and path.is_relative_to(root.root)
    ]
    if len(found) > 1:
        _fail("control overlaps multiple complete forest roots")
    return (
        None
        if not found
        else (found[0][0], path.relative_to(found[0][1].root).as_posix())
    )


def plan_forest_control_disposition(observer, roles, private_root, retirement_root):
    """Capture one read-only proposal under the original live journal snapshot."""
    from .retained_layout_disposition_read import control_plan_history

    value = _record(observer, reading=True)
    with control_plan_history(value.pool):
        return _plan_forest_control_disposition(
            observer, roles, private_root, retirement_root
        )


def _plan_forest_control_disposition(observer, roles, private_root, retirement_root):
    """Capture a real zero-action verified recovery under the creating roles."""
    value, _binding = recovery._same_roles(observer, roles)
    # Enroll the new immutable ancestry before the original data planner seals
    # its reader. No prior reader facts are discarded or retrospectively resealed.
    requested = Path(retirement_root)
    value.ledger.charge_records(
        128 + 16 * len(requested.parts), 65536 + 128 * len(str(requested).encode())
    )
    initial_retirement = _recovery_area(requested, maximum_entries=0)
    if initial_retirement.entries:
        _fail("new direct empty private retirement root required")
    data = recovery.plan_forest_data_recovery(observer, roles, private_root)
    prepared = recovery._prepared(observer, roles, data)
    value = prepared.value
    tail = value.frontier.recovery
    if (
        data.actions
        or data.issues
        or tail is None
        or not tail.segments
        or not tail.segments[-1].complete
    ):
        _fail("complete actually recorded forest data restoration required")
    owners = controls._owners(roles)
    from .retained_layout_forest_disposition_budget import (
        fund_planning,
        require_planning_history,
    )

    area_limits, planning_history = fund_planning(
        value, data, prepared, owners, initial_retirement
    )
    if any(o._disposition is not None for o in owners):
        _fail("original descriptor owners already handed off")
    require_planning_history(value, planning_history)
    entries, bindings = controls._entries(
        value.pool, owners, _event_snapshot=planning_history
    )
    extra = recovery._pin_quarantine(value, data.span, None, Path(retirement_root))
    retirement = _recovery_area(extra.root, maximum_entries=0)
    if retirement.entries:
        _fail("new direct empty private retirement root required")
    if retirement != initial_retirement:
        _fail("original enrolled retirement inputs changed")
    root_node = extra.native[0][1]
    require_planning_history(value, planning_history)
    from .retained_layout_disposition_read import control_events, has_compact

    declarations = (
        control_events(
            value.pool, kinds=frozenset({"recovery-control-disposition-intent"})
        )
        if has_compact(value.journal)
        else tuple(json.loads(row[1]) for row in planning_history[1])
    )
    if any(
        e["kind"] == "recovery-control-disposition-intent"
        and e["data"].get("retirement_root") == str(retirement.root)
        for e in declarations
    ):
        _fail("previously journaled retirement root cannot be reused")
    if {root_node.device, *(e.node.device for e in entries)} != {
        os.fstat(value.pool._descriptor).st_dev
    }:
        _fail("complete disposition requires one filesystem")
    pending = layout_pending_control_path(data.root)
    if sum(not e.target.advisory and e.named == pending for e in entries) != 1:
        _fail("one actual current public pending barrier required")
    areas, public = {}, {}
    for owner in owners:
        if type(owner) is controls._RecoveredControlSet:
            for root in (
                *(a.root for a in owner._plan.recovery_areas),
                *(
                    (owner._plan.retirement_root,)
                    if owner._plan.retirement_root
                    else ()
                ),
            ):
                area = _recovery_area(root, maximum_entries=area_limits[root])
                if root in areas and areas[root] != area:
                    _fail("complete original retirement namespace changed")
                areas[root] = area
            public.update(owner._plan.public_nodes)
    # Another genuinely held generation supersedes a prior public observation.
    # Every such replacement is already proved by current forest projection.
    for entry in entries:
        if entry.named == entry.target.path:
            expected = public.pop(entry.named, entry.node)
            if expected is not None and expected != entry.node:
                _fail("public generation differs from its actual held owner")
    advisory, native = controls._actions(entries)
    require_fixed_control_reads(
        value,
        (*advisory, *native),
        tuple(
            retirement.root / f"control-{i}"
            for i, _entry in enumerate(
                sorted(
                    native,
                    key=lambda e: (
                        e.target.path == layout_pending_control_path(data.root)
                    ),
                )
            )
        ),
    )
    journal = value.journal
    span = replace(
        data.span,
        roots=data.span.roots + (extra,),
    )
    _shape(span)
    plan = _ForestDispositionPlan(
        data,
        entries,
        bindings,
        tuple(areas.values()),
        retirement,
        tuple(public.items()),
        span,
        tuple(journal._known[n][1] for n in journal._events),
    )
    sealed = (tuple(getattr(plan, f.name) for f in fields(plan)), _wire(plan))
    _PLANS[plan] = (observer, roles, prepared, sealed, _history(journal))
    _prepay(value, plan, owners)
    from .retained_layout_disposition_recording import prepare

    prepare(plan)
    _require_plan(observer, roles, plan)
    return plan


def _prepay(value, plan, owners):
    from .retained_layout_forest_disposition_budget import (
        fund_sizing,
        workspace_bound,
    )

    binding = _PLANS[plan]
    fund_sizing(value.ledger, plan, binding[3][1])
    # All successors conserve source payload groups; only exact external native
    # descriptors can add payloads to the complete private span. Budget that
    # largest roster before any repeated verifier or durable intent.
    extra = [
        (i, e)
        for i, e in enumerate(_native(plan))
        if _coordinate(plan.span, e.named) is None
    ]
    root = plan.span.roots[-1]
    maximum = replace(
        plan.span,
        roots=(
            *plan.span.roots[:-1],
            replace(
                root,
                native=root.native + tuple((f"control-{i}", e.node) for i, e in extra),
                payloads=tuple(
                    (
                        f"control-{i}",
                        BlobRef(hashlib.sha256(e.content).hexdigest(), len(e.content)),
                        bool(e.node.mode & 0o111),
                    )
                    for i, e in extra
                ),
            ),
        ),
    )
    schedule = _schedule(plan)
    # Each actual action observes its one owned marker in the native method and
    # again when adopting that observation. Those reads never traverse the
    # forest or cached input closure. Give them a disjoint marker-only allowance.
    actions = sum(
        entry is not None and kind.endswith("-intent") for kind, entry in schedule
    )
    marker_reads = 2 * actions
    # normalize/retire each call _writer five times (including the two in
    # _intent) and _advance verifies the full native successor once. Intent and
    # observation are rows of that same action, not separate full traversals.
    # Retain the original fixed planning/refusal and descriptor-exit allowances.
    checks = 32 + 6 * actions + 8 * len(owners)
    marker_limit = min(256, value.ledger.budget.maximum_file_bytes)
    workspace = workspace_bound(
        plan,
        maximum,
        sealed_plan=binding[3][1],
        reader_seal=binding[2].reader_seal,
        schedule=len(_schedule(plan)),
        checks=checks,
    )
    value.ledger.charge_records(workspace.records, workspace.bytes)
    before_files, before_bytes = value.ledger.files, value.ledger.bytes
    policy = recovery._fund(value, maximum)
    value.ledger.files += (checks - 1) * (
        value.ledger.files - before_files
    ) + 2 * checks * len(plan.entries)
    value.ledger.bytes += (checks - 1) * (
        value.ledger.bytes - before_bytes
    ) + 2 * checks * sum(len(e.content) for e in plan.entries)
    cached = tuple(value.ledger.cache.values())
    value.ledger.charge_records(
        128 * len(cached),
        8192 * len(cached)
        + 4 * max((1, *(len(item.content or b"") for item in cached))),
    )
    value.ledger.files += checks * len(cached)
    value.ledger.bytes += checks * sum(len(item.content or b"") for item in cached)
    value.ledger.files += marker_reads
    value.ledger.bytes += marker_reads * marker_limit
    value.ledger.charge_records(16, 4096 + 4 * marker_limit)
    value.ledger.require_capacity()
    _COUPONS[plan] = (policy, checks)
    _MARKER_READS[plan] = (marker_reads, marker_limit)


@contextmanager
def _workspace(plan):
    """Borrow the prepaid non-reentrant scratch area, never native read rights."""
    if plan in _READING:
        _fail("reentrant disposition verification refused")
    if plan not in _COUPONS:
        _fail("original finite disposition read allowance exhausted")
    token = object()
    _READING[plan] = token
    try:
        yield
        if _READING.get(plan) is not token:
            _fail("original disposition verifier workspace ended")
    finally:
        _READING.pop(plan, None)


@contextmanager
def _reading(plan):
    with _workspace(plan):
        value = _COUPONS.get(plan)
        if value is None or value[1] <= 0:
            _fail("original finite disposition read allowance exhausted")
        _COUPONS[plan] = (value[0], value[1] - 1)
        yield value[0]


@contextmanager
def _marker_reading(plan):
    """One prepaid marker read, with no full-forest verification policy."""
    with _workspace(plan):
        remaining = _MARKER_READS.get(plan)
        if remaining is None or remaining[0] <= 0:
            _fail("original finite marker read allowance exhausted")
        _MARKER_READS[plan] = (remaining[0] - 1, remaining[1])
        yield remaining[1]


def _require_plan(observer, roles, plan):
    binding = _PLANS.get(plan) if type(plan) is _ForestDispositionPlan else None
    if binding is None or binding[0] is not observer or binding[1] is not roles:
        _fail("actual creating forest disposition plan required")
    with _reading(plan) as policy:
        return _require_plan_read(observer, roles, plan, policy)


def _require_plan_read(observer, roles, plan, policy):
    binding = _PLANS.get(plan) if type(plan) is _ForestDispositionPlan else None
    if binding is None or binding[0] is not observer or binding[1] is not roles:
        _fail("actual creating forest disposition plan required")
    if (
        any(
            getattr(plan, f.name) is not old
            for f, old in zip(fields(plan), binding[3][0], strict=True)
        )
        or _wire(plan) != binding[3][1]
    ):
        _fail("original forest disposition proposal changed")
    prepared = recovery._prepared(observer, roles, plan.data)
    if prepared is not binding[2]:
        _fail("actual verified forest data receipt changed")
    _close_history(prepared.value.journal, binding[4])
    roles.require_current()
    if (
        controls._entries(prepared.value.pool, controls._owners(roles))
        != (plan.entries, plan.bindings)
        or _recovery_area(plan.retirement.root, maximum_entries=0) != plan.retirement
    ):
        _fail("original descriptor or retirement inputs changed")
    _require_current(
        replace(plan.span, budget=policy), _after_payload=roles.require_current
    )
    _close_history(prepared.value.journal, binding[4])
    if _wire(plan) != binding[3][1]:
        _fail("original forest disposition proposal changed during closure")
    if (
        recovery._prepared(observer, roles, plan.data) is not prepared
        or _PLANS.get(plan) is not binding
    ):
        _fail("original prepared data or role lifetime changed during closure")
    return binding


def _state(effect):
    saved = _STATES.get(effect)
    if saved is None:
        return None
    state = saved[0]()
    if state is None or effect._forest_state is not state:
        _fail("actual transferred forest receipt lifetime changed")
    return state


class _ForestState:
    def __init__(self, observer, roles, binding):
        self.observer, self.roles = observer, roles
        self.value, self.role_binding = binding[2].value, binding[2].role_binding
        self.pid, self.thread = os.getpid(), threading.get_ident()

    def close(self, effect, *, selected=None):
        saved = _STATES.get(effect)
        if (
            saved is None
            or saved[0]() is not self
            or _record(self.observer, reading=True) is not self.value
        ):
            _fail("actual transferred observer lifetime ended")
        if (
            (self.pid, self.thread) != (os.getpid(), threading.get_ident())
            or effect.roles is not self.roles
            or effect.pool is not self.value.pool
        ):
            _fail("actual transferred producer or receiver changed")
        plan, seal, span, span_seal, history, cursor, pending = saved[1:8]
        pins = saved[8]
        if (
            (
                id(self.observer),
                id(self.roles),
                id(self.value),
                id(self.role_binding),
                self.pid,
                self.thread,
            )
            != pins[0]
            or tuple(id(o) for o in effect.owners) != pins[1]
            or effect.entries is not pins[2]
            or effect.areas is not pins[3]
            or _wire((effect.entries, effect.areas)) != pins[4]
            or effect.receiver != self.pid
            or any(
                getattr(plan, f.name) is not old
                for f, old in zip(fields(plan), pins[5], strict=True)
            )
            or any(
                getattr(plan.data, f.name) is not old
                for f, old in zip(fields(plan.data), pins[6], strict=True)
            )
            or recovery._reader_seal(self.value) != pins[7]
        ):
            _fail("original transferred producer or native inventory changed")
        if effect.plan is not plan or _wire(plan) != seal or _wire(span) != span_seal:
            _fail("transferred forest proposal or successor changed")
        _close_history(self.value.journal, history)
        from .retained_layout_disposition_recording import close

        close(effect)
        if self.roles._active:
            if _CREATED_ROLES.get(self.roles) is not self.role_binding:
                _fail("original canonical creating binding changed")
        elif not effect.finished or selected is None:
            _fail("canonical role lifetime ended before completion")
        if getattr(self.roles, "_disposition", None) is not None and (
            self.roles._disposition is not effect
            or self.roles._finalizing is not True
            or self.roles.reservations._active is not False
            or any(o._disposition is not effect for o in effect.owners)
        ):
            _fail("original canonical-to-disposition handoff changed")
        if effect.active:
            effect._writer_binding()
        return span, cursor, pending

    def verify(self, effect, selected=None):
        saved = _STATES.get(effect)
        if saved is None:
            _fail("actual transferred forest receipt required")
        with _reading(saved[1]) as policy:
            return self._verify(effect, selected, policy)

    def _verify(self, effect, selected, policy):
        span, _cursor, _pending = self.close(effect, selected=selected)
        if selected is not None and (
            selected not in effect.owners or selected._disposition is not effect
        ):
            _fail("actual handed-off descriptor owner required")
        effect._resources(selected)
        effect.pool.require_current()
        private = effect._private_close()

        def close_native():
            effect._resources(selected)
            self.value.selection.require_current()
            self.value.reader.require_current()
            producers = _close_dependencies(effect.pool)
            if selected is None:
                if not effect.native_released:
                    effect.roles.git.close_native_inputs(effect)
                effect.roles._seed.close_native_inputs()
            effect._markers(selected, native_only=True)
            effect._close_private_native(private)
            _close_dependency_facts(effect.pool, producers)
            effect._flags(selected)
            self.close(effect, selected=selected)

        effect._markers(selected)
        _require_current(replace(span, budget=policy), _after_payload=close_native)
        self.close(effect, selected=selected)

    def read_marker(self, effect, path):
        _span, _cursor, pending = self.close(effect)
        step = _DISPATCH.get(effect)
        if (
            step is None
            or pending is None
            or pending[0] is not step[1]
            or pending[2] is not None
        ):
            _fail("actual pending owned marker observation required")
        kind, entry = step
        self.admit(effect, kind, entry, before=True)
        expected = (
            entry.named
            if entry.target.advisory
            else Path(json.loads(pending[1])["destination"])
        )
        if path != expected:
            _fail("marker observation escapes original native intent")
        with _marker_reading(effect.plan) as maximum_bytes:
            owner = effect.owners[entry.owner]
            effect._resources(owner)
            node, content = read_owned_marker(path, maximum_bytes=maximum_bytes)
            marker = owner._markers[entry.ordinal]
            if _from_stat(os.fstat(marker.descriptor)) != node:
                _fail("observed marker differs from original held descriptor")
            effect._flags(owner)
            self.close(effect)
            return node, content

    def advance(self, effect, entry, node, content, destination):
        observed = self.read_marker(effect, destination or entry.named)
        with _reading(effect.plan) as policy:
            return self._advance(
                effect, entry, node, content, destination, observed, policy
            )

    def _advance(self, effect, entry, node, content, destination, observed, policy):
        span, cursor, pending = self.close(effect)
        if (
            pending is None
            or pending[0] is not entry
            or pending[2] is not None
            or _DISPATCH.get(effect)
            != ("normalize" if destination is None else "retire", entry)
        ):
            _fail("actual pending native disposition receipt required")
        if observed != (node, content):
            _fail("actual observed native descriptor receipt changed")
        if destination is None:
            if not entry.target.advisory or content != b"\0":
                _fail("exact advisory normalization receipt required")
            where = _coordinate(span, entry.named)
            if where is not None:
                area, name = where
                root = span.roots[area]
                nodes, payloads = (
                    dict(root.native),
                    {n: (b, x) for n, b, x in root.payloads},
                )
                if nodes[name] != entry.node:
                    _fail("normalization differs from original forest node")
                nodes[name] = node
                payloads[name] = (
                    BlobRef(hashlib.sha256(content).hexdigest(), len(content)),
                    bool(node.mode & 0o111),
                )
                roots = list(span.roots)
                roots[area] = replace(
                    root,
                    native=_rows(nodes),
                    payloads=tuple((n, *v) for n, v in sorted(payloads.items())),
                )
                span = replace(span, roots=tuple(roots))
        else:
            if (
                entry.target.advisory
                or destination.parent != effect.plan.retirement.root
            ):
                _fail("exact owned native retirement receipt required")
            source, target = (
                _coordinate(span, entry.named),
                _coordinate(span, destination),
            )
            if target is None:
                _fail("complete new retirement root required")
            sp, tp = (
                layout_entry_node(entry.named.parent),
                layout_entry_node(destination.parent),
            )
            if source is not None:
                area, name = source
                if dict(span.roots[area].native)[name] != entry.node:
                    _fail("retirement differs from original forest node")
                span = _advance_move(
                    span,
                    _Action("move", area, name, target[0], target[1]),
                    node,
                    sp,
                    tp,
                )
            else:
                area, name = target
                root = span.roots[area]
                nodes = dict(root.native)
                if name in nodes:
                    _fail("retirement receipt collides with known node")
                nodes[name], nodes[""] = node, tp
                payloads = root.payloads + (
                    (
                        name,
                        BlobRef(hashlib.sha256(content).hexdigest(), len(content)),
                        bool(node.mode & 0o111),
                    ),
                )
                roots = list(span.roots)
                roots[area] = replace(
                    root, native=_rows(nodes), payloads=tuple(sorted(payloads))
                )
                span = replace(span, roots=tuple(roots))
        updated = replace(
            entry, node=node, content=content, named=destination or entry.named
        )
        entries = tuple(updated if e is entry else e for e in effect.entries)
        areas = effect.areas
        if destination is not None:
            values = []
            for area in areas:
                if area.root == destination.parent:
                    known = dict(area.entries)
                    if destination.name in known:
                        _fail("native receipt collides with original retirement")
                    known[destination.name] = node
                    area = replace(area, entries=tuple(sorted(known.items())))
                values.append(area)
            areas = tuple(values)
        projection = project_control_reads(
            self.value, entry, node, content, destination
        )
        projection_seal = seal_projection(projection)
        successors = seal_successors((span, entries, areas))

        def close_native():
            self.value.selection.require_current()
            effect._resources()
            producers = _close_dependencies(effect.pool)
            for known in entries:
                marker = effect.owners[known.owner]._markers[known.ordinal]
                if (
                    _from_stat(os.fstat(marker.descriptor)) != known.node
                    or layout_entry_node(known.named) != known.node
                    or os.pread(marker.descriptor, len(known.content) + 1, 0)
                    != known.content
                    or _from_stat(os.fstat(marker.descriptor)) != known.node
                ):
                    _fail(
                        "actual control receipt changed after successor payload reads"
                    )
            close_projection(self.value, projection, projection_seal)
            _close_dependency_facts(effect.pool, producers)
            effect._flags()
            self.close(effect)

        _require_current(replace(span, budget=policy), _after_payload=close_native)
        self.close(effect)
        require_projection(projection, projection_seal)
        require_successors((span, entries, areas), successors)
        self.value.ledger.cache.update(projection[0])
        self.value.reader._presences.update(projection[1])
        effect._entries_current, effect._areas_current = entries, areas
        saved = _STATES[effect]
        pins = (
            *saved[8][:2],
            entries,
            areas,
            _wire((entries, areas)),
            *saved[8][5:7],
            recovery._reader_seal(self.value),
        )
        _STATES[effect] = (
            saved[0],
            saved[1],
            saved[2],
            span,
            _wire(span),
            saved[5],
            cursor,
            (entry, pending[1], node),
            pins,
        )

    def admit(self, effect, kind, entry, *, before=False, enter=False):
        if _DISPATCH.get(effect) != (kind, entry) or effect.plan in _READING:
            _fail("actual non-reentrant native disposition dispatch required")
        if enter:
            if effect in _INFLIGHT:
                _fail("reentrant native disposition method refused")
            _INFLIGHT[effect] = (kind, entry, object())
        elif effect not in _INFLIGHT or _INFLIGHT[effect][:2] != (kind, entry):
            _fail("actual entered native disposition method required")
        _span, cursor, pending = self.close(effect)
        effect._writer_binding()
        schedule = _schedule(effect.plan)
        prefix = (
            "recovery-control-normalization"
            if kind == "normalize"
            else "recovery-control-retirement"
        )
        expected = prefix + ("-observed" if before else "-intent")
        if (
            cursor >= len(schedule)
            or schedule[cursor][0] != expected
            or schedule[cursor][1] is not entry
        ):
            _fail("native disposition phase escapes original schedule")
        if (not before and pending is not None) or (
            before
            and (pending is None or pending[0] is not entry or pending[2] is not None)
        ):
            _fail("actual native intent phase required")

    def payload(self, effect, content):
        step = _DISPATCH.get(effect)
        if step is None or content is not step[1].content:
            _fail("actual current descriptor payload receipt required")
        self.admit(effect, *step)
        journal = self.value.journal
        previous = _STATES[effect]
        digest = hashlib.sha256(content).hexdigest()
        name = "p-" + digest + ".bin"
        existed = name in journal._known
        actual = journal.store_payload(content)
        history = _history(journal)
        roster, events = previous[5]
        if (
            actual != digest
            or history[1] != events
            or len(history[0]) != len(roster) + (not existed)
            or any(journal._known.get(n) is not row for n, row in roster)
            or journal._known.get(name, (None, None))[1] != content
        ):
            _fail("foreign journal change during actual payload receipt")
        _STATES[effect] = (*previous[:5], history, *previous[6:])
        self.close(effect)
        return digest

    def event(self, effect, kind, data):
        if effect.plan in _READING or effect in _RECORDING:
            _fail("reentrant disposition event refused")
        _span, cursor, pending = self.close(effect)
        schedule = _schedule(effect.plan)
        if cursor >= len(schedule) or schedule[cursor][0] != kind:
            _fail("event escapes exact original disposition schedule")
        entry = schedule[cursor][1]
        if kind.endswith("-intent") and entry is not None:
            self.admit(
                effect,
                "normalize"
                if kind == "recovery-control-normalization-intent"
                else "retire",
                entry,
            )
            operation = data.get("operation")
            if (
                type(operation) is not str
                or len(operation) != 32
                or any(c not in "0123456789abcdef" for c in operation)
            ):
                _fail("exact current operation identity required")
            expected = {
                "operation": operation,
                "group": entry.group,
                "path": str(entry.target.path),
                "source_phase_identity": effect.plan.data.phase_identity,
                "original_node": _custody_wire(entry.original_node),
                "node": _custody_wire(entry.node),
                "before_payload": hashlib.sha256(entry.content).hexdigest(),
            }
            if kind == "recovery-control-retirement-intent":
                ordinal = _native(effect.plan).index(entry)
                expected.update(
                    source=str(entry.named),
                    destination=str(effect.plan.retirement.root / f"control-{ordinal}"),
                    source_parent=_custody_wire(layout_entry_node(entry.named.parent)),
                    destination_parent=_custody_wire(
                        layout_entry_node(effect.plan.retirement.root)
                    ),
                )
            if _wire(data) != _wire(expected):
                _fail("native intent differs from exact held descriptor")
            pending = (entry, _wire(data), None)
        elif entry is not None:
            step = _DISPATCH.get(effect)
            if step is None or step[1] is not entry:
                _fail("actual observed native dispatch required")
            if pending is None or pending[0] is not entry or pending[2] is None:
                _fail("actual observed disposition receipt required")
            expected = {
                **json.loads(pending[1]),
                "observed_node": _custody_wire(pending[2]),
            }
            if _wire(data) != _wire(expected):
                _fail("observation differs from actual native receipt")
            pending = None
        else:
            if effect in _DISPATCH:
                _fail("boundary event during native dispatch refused")
            if _wire(data) != _wire(_boundary(effect.plan, kind)):
                _fail("disposition boundary differs from exact forest plan")
        journal = self.value.journal
        previous = _STATES[effect]
        from .retained_layout_disposition_recording import record

        _RECORDING[effect] = kind, canonical_json_bytes(data)
        try:
            record(effect, kind, data)
        finally:
            _RECORDING.pop(effect, None)
        history = _history(journal)
        _STATES[effect] = (*previous[:5], history, cursor + 1, pending, previous[8])
        self.close(effect)


def _native(plan):
    return tuple(
        sorted(
            controls._actions(plan.entries)[1],
            key=lambda e: e.target.path == layout_pending_control_path(plan.data.root),
        )
    )


def _dispatch(effect, kind, entry, ordinal=None):
    if effect in _DISPATCH:
        _fail("native disposition dispatch already active")
    state = _state(effect)
    if state is None:
        _fail("actual transferred forest receipt required")
    _span, cursor, pending = state.close(effect)
    schedule = _schedule(effect.plan)
    expected = (
        "recovery-control-normalization-intent"
        if kind == "normalize"
        else "recovery-control-retirement-intent"
    )
    if (
        pending is not None
        or cursor >= len(schedule)
        or schedule[cursor] != (expected, entry)
    ):
        _fail("native dispatch escapes exact original disposition schedule")
    _DISPATCH[effect] = (kind, entry)
    try:
        if kind == "normalize":
            effect.normalize(entry)
        elif kind == "retire" and ordinal == _native(effect.plan).index(entry):
            effect.retire(entry, ordinal)
        else:
            _fail("exact native disposition operation required")
        _span, next_cursor, next_pending = state.close(effect)
        if next_cursor != cursor + 2 or next_pending is not None:
            _fail("native method did not close its exact observed receipt")
    finally:
        _INFLIGHT.pop(effect, None)
        _DISPATCH.pop(effect, None)


def _schedule(plan):
    steps = [("recovery-control-disposition-intent", None)]
    for entry in controls._actions(plan.entries)[0]:
        steps.extend(
            (
                ("recovery-control-normalization-intent", entry),
                ("recovery-control-normalization-observed", entry),
            )
        )
    for entry in _native(plan):
        if entry.target.path == layout_pending_control_path(plan.data.root):
            steps.append(("recovery-control-release-decision", None))
        steps.extend(
            (
                ("recovery-control-retirement-intent", entry),
                ("recovery-control-retirement-observed", entry),
            )
        )
    return (*steps, ("recovery-control-disposition-observed", None))


def _boundary(plan, kind):
    state = (
        "committed-unqualified"
        if plan.data.committed
        else "original-data-restored-unqualified"
    )
    data = {
        "source_phase_identity": plan.data.phase_identity,
        "disposition_identity": plan.identity.uri,
        "qualified": False,
    }
    if kind == "recovery-control-disposition-intent":
        data.update(
            retirement_root=str(plan.retirement.root),
            retirement_node=_custody_wire(plan.span.roots[-1].native[0][1]),
            data_identity=plan.data.identity.uri,
        )
    else:
        data["state"] = state
        if kind == "recovery-control-release-decision":
            data["pending_control"] = str(layout_pending_control_path(plan.data.root))
    return data


def _initialize(effect, key, pool, roles, plan, owners):
    binding = _PLANS.get(plan) if type(plan) is _ForestDispositionPlan else None
    if (
        key is not controls._KEY
        or binding is None
        or binding[1] is not roles
        or binding[2].value.pool is not pool
        or any(a is not b for a, b in zip(owners, controls._owners(roles), strict=True))
    ):
        _fail("actual forest data-to-descriptor handoff factory required")
    _require_plan(binding[0], roles, plan)
    effect._pool, effect._roles, effect._plan, effect._owners = (
        pool,
        roles,
        plan,
        owners,
    )
    effect._entries_current, effect._areas_current = (
        plan.entries,
        plan.areas + (plan.retirement,),
    )
    effect._receiver, effect._active = os.getpid(), False
    effect.finished, effect.decision_attempted, effect.decision = False, False, None
    state = _ForestState(binding[0], roles, binding)
    effect._forest_state = state
    _STATES[effect] = (
        ref(state),
        plan,
        _wire(plan),
        plan.span,
        _wire(plan.span),
        binding[4],
        0,
        None,
        (
            (
                id(state.observer),
                id(state.roles),
                id(state.value),
                id(state.role_binding),
                state.pid,
                state.thread,
            ),
            tuple(id(o) for o in owners),
            effect.entries,
            effect.areas,
            _wire((effect.entries, effect.areas)),
            tuple(getattr(plan, f.name) for f in fields(plan)),
            tuple(getattr(plan.data, f.name) for f in fields(plan.data)),
            recovery._reader_seal(state.value),
        ),
    )
    from .retained_layout_disposition_recording import initialize

    initialize(effect)


def apply_forest_control_disposition(
    observer, roles, plan, *, acknowledged_recovery_identity, allow_host_execution
):
    """Transfer verified forest custody; use real normalization/retirement effects."""
    binding = _require_plan(observer, roles, plan)
    if (
        allow_host_execution is not True
        or type(acknowledged_recovery_identity) is not ContentIdentity
        or acknowledged_recovery_identity != plan.identity
    ):
        _fail("exact current disposition acknowledgement and host authority required")
    pool = binding[2].value.pool
    owners = controls._owners(roles)
    for owner in owners:
        owner._held.pin(plan.retirement.root)
    effect = controls._RecoveryDisposition(controls._KEY, pool, roles, plan, owners)
    effect.verify()
    effect._event(
        "recovery-control-disposition-intent",
        _boundary(plan, "recovery-control-disposition-intent"),
    )
    effect.verify()
    roles._finalizing, roles.reservations._active, roles._disposition = (
        True,
        False,
        effect,
    )
    for owner in owners:
        owner._disposition = effect
    effect._active = True
    _PLANS.pop(plan, None)
    recovery._PREPARED.pop(plan.data, None)
    recovery._PLAN_SEALS.pop(plan.data, None)
    try:
        for entry in controls._actions(plan.entries)[0]:
            _dispatch(effect, "normalize", entry)
        for ordinal, entry in enumerate(_native(plan)):
            if entry.target.path == layout_pending_control_path(plan.data.root):
                effect._writer()
                effect.decision_attempted = True
                effect._event(
                    "recovery-control-release-decision",
                    _boundary(plan, "recovery-control-release-decision"),
                )
                effect.decision = (
                    "committed-unqualified"
                    if plan.data.committed
                    else "original-data-restored-unqualified"
                )
                effect._writer()
            _dispatch(effect, "retire", entry, ordinal)
        effect._writer()
        if controls._actions(effect.entries) != ((), ()) or os.path.lexists(
            layout_pending_control_path(plan.data.root)
        ):
            _fail("actual disposition incomplete; retain all state")
        effect._event(
            "recovery-control-disposition-observed",
            _boundary(plan, "recovery-control-disposition-observed"),
        )
        effect._writer()
        effect.finished = True
        return {
            "state": effect.decision,
            "qualified": False,
            "controls_released": True,
            "internal_recovery_complete": True,
            "feature_complete": False,
            "span": _STATES[effect][3],
        }
    except BaseException as error:
        effect.raise_outcome(error)
        raise
    finally:
        effect._active = False
