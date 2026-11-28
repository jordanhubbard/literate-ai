"""Acknowledged forest data restoration under actual fresh canonical roles.

This owner reverses only witnessed original metadata/native entry effects. It
retains all newly created directories and prospective metadata privately. Saved
plans are descriptions; only this actual fresh planner and its live descriptors
can enroll a one-use effect context. Public admission remains independently gated.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import unicodedata
from contextlib import ExitStack
from dataclasses import dataclass, fields, replace
from pathlib import Path
from weakref import WeakKeyDictionary

from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)

from .catalog_copy_plan import _anchor
from .exclusive_entry import layout_entry_node, move_layout_entry_exclusive
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_forest_current import (
    _fund,
    observe_current_native_forest,
)
from .retained_layout_forest_effects import _decision_document
from .retained_layout_forest_metadata_replay import _apart
from .retained_layout_forest_native import (
    _Action,
    _advance_move,
    _native_event_schedule,
    _native_steps,
)
from .retained_layout_forest_observation import _record
from .retained_layout_forest_span import _require_current, _SpanRoot
from .retained_layout_journal import _LIVE_ROOTS
from .retained_layout_partition import _lineage
from .retained_layout_recovery_roles import _CREATED_ROLES, _RecoveryRoleLease
from .retained_project_inputs import _directory_access

_PREPARED = WeakKeyDictionary()
_PLAN_SEALS = WeakKeyDictionary()
_LIVE = {}
_PROGRESS = {}
_RECEIPTS = {}
_DISPATCH = {}
_READING = {}
_WRITES = {}
_OBSERVED = {}
_SCHEDULE = {}


def _fail(message):
    raise ValueError("layout.forest-recovery: " + message)


@dataclass(frozen=True, slots=True, eq=False, weakref_slot=True)
class _ForestDataRecoveryPlan:
    root: Path
    phase_identity: str
    program_identity: str
    role_identity: str
    private_root: Path
    span: object
    actions: tuple
    history: tuple
    original_position: str
    original_frontier: object
    committed: bool
    issues: tuple
    resume: object = None

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/forest-data-recovery@1",
                "plan": _custody_wire(self),
            }
        )


@dataclass(frozen=True, slots=True)
class _Prepared:
    value: object
    roles: object
    role_binding: object
    document: bytes
    policies: tuple
    roster: tuple
    events: tuple
    reader_seal: bytes


def _same_roles(observer, roles):
    value = _record(observer, reading=True)
    if type(roles) is not _RecoveryRoleLease:
        _fail("actual same-observer canonical role lifetime required")
    roles._require_created()
    if roles._pool is not value.pool or roles._seed.root != value.root:
        _fail("actual same-observer canonical role lifetime required")
    return value, _CREATED_ROLES[roles]


def _parent(name):
    value = Path(name).parent.as_posix()
    return "" if value == "." else value


def _coordinate(span, spelling):
    path = Path(spelling)
    candidates = [
        (i, r)
        for i, r in enumerate(span.roots)
        if path != r.root and path.is_relative_to(r.root)
    ]
    if len(candidates) != 1:
        _fail("original entry escapes its complete native roots")
    area, root = candidates[0]
    return area, path.relative_to(root.root).as_posix()


def _committed(value, current):
    events = value.saved.events
    commits = [
        (i, e["data"])
        for i, e in enumerate(events)
        if e["kind"] == "layout-commit-observed"
    ]
    if not commits:
        return False
    if (
        len(commits) != 1
        or current.metadata is None
        or not current.metadata.complete
        or not current.journal_complete
    ):
        _fail("commit lacks complete original source and metadata receipts")
    index, document = commits[0]
    expected = _decision_document(
        value.program.source_phase_identity,
        current.metadata.retirement_root,
        committed=True,
    )
    before = _decision_document(
        value.program.source_phase_identity,
        current.metadata.retirement_root,
        committed=False,
    )
    starts = [
        i
        for i, e in enumerate(events)
        if e["kind"] == "layout-finalization-intent"
        and canonical_json_bytes(e["data"]) == before
    ]
    metadata_ends = [
        i for i, e in enumerate(events) if e["kind"] == "layout-metadata-observed"
    ]
    if (
        canonical_json_bytes(document) != expected
        or len(starts) != 1
        or len(metadata_ends) != 1
        or not metadata_ends[0] < starts[0] < index
    ):
        _fail("exact original durable forest commit decision required")
    return True


def _inverse_actions(value, current, quarantine):
    """Derive coordinates from the exact already validated original prefix."""
    metadata = []
    for event in value.saved.events:
        kind, data = event["kind"], event["data"]
        if kind in {"metadata-quarantine-observed", "metadata-publication-observed"}:
            metadata.append((kind.removesuffix("-observed"), data))
    if (
        current.metadata is not None
        and current.metadata.pending is not None
        and current.position == "pending-after"
    ):
        pending = current.metadata.pending
        metadata.append((pending.kind.removesuffix("-intent"), pending.data))
    result = []
    for kind, data in reversed(metadata):
        source_area, source = _coordinate(current.span, data["destination"])
        if kind == "metadata-publication":
            target_area, target = quarantine, f"prospective-{len(result):04d}"
        else:
            target_area, target = _coordinate(current.span, data["source"])
        result.append(_Action("metadata", source_area, source, target_area, target))
    steps = _native_steps(value.program)
    performed = [
        steps[index][1]
        for index, kind in _native_event_schedule(value.program)[
            : value.frontier.consumed
        ]
        if kind == "forest-entry-observed"
    ]
    if (
        value.frontier.pending is not None
        and value.frontier.pending[0] == "forest-entry-intent"
        and current.position == "pending-after"
    ):
        index = _native_event_schedule(value.program)[value.frontier.consumed - 1][0]
        performed.append(steps[index][1])
    result.extend(
        _Action("native", a.destination_area, a.destination, a.source_area, a.source)
        for a in reversed(performed)
    )
    return tuple(result)


def _pin_quarantine(value, span, metadata, private):
    if (
        type(private) is not type(Path())
        or not private.is_absolute()
        or ".." in private.parts
    ):
        _fail("direct existing empty private quarantine required")
    if _portable_beneath(private, value.program.private_root) or _portable_beneath(
        value.program.private_root, private
    ):
        _fail("quarantine overlaps original parking domain")
    value.ledger.charge_records(
        128 + 16 * len(private.parts), 65536 + 128 * len(str(private).encode())
    )
    lineage = _lineage(private)
    with _directory_access(private) as access:
        if access is None:
            _fail("actual no-follow quarantine access required")
        before = layout_entry_node(private)
        if before.uid != os.geteuid() or stat.S_IMODE(before.mode) != 0o700:
            _fail("owned mode0700 quarantine required")
        with os.scandir(access._absolute[-1][1]) as entries:
            if next(entries, None) is not None:
                _fail("new quarantine must be empty; preserve existing entries")
        if (
            layout_entry_node(private) != before
            or before.device != span.roots[0].native[0][1].device
        ):
            _fail("quarantine native facts changed or filesystem differs")
        for root in span.roots:
            _apart(private, lineage, root.root, root.lineage)
        if metadata is not None:
            _apart(
                private, lineage, metadata.retirement_root, metadata.retirement_lineage
            )
        for root in (value.pool.root, _LIVE_ROOTS[value.journal]):
            _apart(private, lineage, root, value.reader._lineages[root])
        storage = value.selection.path.parent
        anchor, storage_lineage = value.ledger.ancestry[value.selection.path]
        if (
            private.is_relative_to(storage)
            or storage.is_relative_to(private)
            or lineage[-1][1:3] in {row[1:3] for row in storage_lineage}
            or (
                anchor == storage
                and storage_lineage[-1][1:3] in {row[1:3] for row in lineage}
            )
        ):
            _fail("quarantine overlaps current canonical storage")
        if _lineage(private) != lineage or layout_entry_node(private) != before:
            _fail("quarantine changed during complete separation checks")
    return _SpanRoot(private, lineage, (("", before),), ())


def _journal_capacity(value, actions, span):
    journal = value.journal
    count = 2 + 2 * len(actions)
    maximum = 65536
    for action in actions:
        source = span.roots[action.source_area].root / action.source
        destination = span.roots[action.destination_area].root / action.destination
        # Full before/after child and parent nodes, conservative JSON escaping,
        # and all coordinate spellings fit this preflight bound. Native numbers
        # are bounded by the original strict typed programme decoder.
        bound = 16384 + 32 * (
            len(str(source).encode())
            + len(str(destination).encode())
            + len(action.source.encode())
            + len(action.destination.encode())
        )
        if bound > maximum:
            _fail("complete recovery event exceeds finite record ceiling")
    if (
        len(journal._events) + count > journal._budget.maximum_events
        or maximum > journal._budget.maximum_payload_bytes
        or sum(len(row[1]) for row in journal._known.values())
        + count * (maximum + 1024)
        > journal._budget.maximum_storage_bytes
    ):
        _fail("complete recovery journal exceeds immutable current policy")
    return count, maximum


def _refuse_recovery_prefix(value, binding, *, allow_saved=False):
    if not allow_saved and any(
        e["kind"].startswith("forest-data-recovery-") for e in value.saved.events
    ):
        _fail("previous forest recovery requires exact fresh recovery-prefix replay")
    names = value.journal._events[len(value.events) :]
    size = sum(len(value.journal._known[n][1]) for n in names)
    value.ledger.charge_records(128 * len(names), 4 * size)
    value.journal.require_current()
    records = []
    for name in names:
        event = json.loads(value.journal._known[name][1])
        if event["kind"].startswith("forest-"):
            _fail("post-load forest suffix requires exact fresh recovery-prefix replay")
        records.append((event["kind"], canonical_json_bytes(event["data"])))
    from .retained_layout_disposition_read import has_compact, read_history

    semantic = (
        read_history(value.journal, value.ledger)
        if has_compact(value.journal)
        else None
    )
    if semantic is not None:
        records = [
            (kind, raw)
            for position, kind, raw in semantic.records
            if position >= len(value.events)
        ]
    from .retained_layout_forest_recovery_transcript import decode_recovery_transcript

    decoded = decode_recovery_transcript(
        value.program,
        tuple(records),
        allowance=value.ledger,
        payloads=frozenset(value.journal._payloads),
        compact_bindings=() if semantic is None else semantic.bindings,
    )
    role_plan = binding[0]
    role_index = len(role_plan.history)
    expected = canonical_json_bytes(
        {
            "recovery_role_identity": binding[5],
            "project_root": str(value.root),
            "grants_source_effects": False,
        }
    )
    events = value.journal._events
    # The actual role proposal commits its complete pre-acquisition history.
    # A copied later intent/observation pair cannot impersonate this live lease.
    if (
        decoded.segments
        or decoded.canonical_pending is not None
        or decoded.canonical_role_identity != binding[5]
        or decoded.raw_recovery_identities
        != tuple(sorted(i.uri for i in role_plan.recovery_identities))
        or not records
        or records[-1] != ("recovery-canonical-roles-observed", expected)
        or role_index >= len(events)
        or tuple(value.journal._known[n][1] for n in events[:role_index])
        != role_plan.history
    ):
        _fail("exact actual canonical reacquisition suffix required")
    actual = []
    for index, name in enumerate(events[role_index:], role_index):
        event = json.loads(value.journal._known[name][1])
        if event["kind"] in {
            "recovery-canonical-roles-intent",
            "recovery-canonical-roles-observed",
        }:
            actual.append((index, event["kind"], canonical_json_bytes(event["data"])))
    if actual != [
        (role_index, "recovery-canonical-roles-intent", expected),
        (len(events) - 1, "recovery-canonical-roles-observed", expected),
    ]:
        _fail("new canonical records do not belong to the actual creating role lease")


def _reader_seal(value):
    reader = value.reader
    return canonical_json_bytes(
        _custody_wire(
            (
                tuple(value.ledger.cache.items()),
                tuple(value.ledger.ancestry.items()),
                tuple(reader._presences.items()),
                tuple(reader._lineages.items()),
                tuple(sorted(reader._lineage_allowances)),
            )
        )
    )


def _portable_beneath(path, parent):
    left = tuple(unicodedata.normalize("NFC", part).casefold() for part in path.parts)
    right = tuple(
        unicodedata.normalize("NFC", part).casefold() for part in parent.parts
    )
    return left[: len(right)] == right


def _require_fixed_reader(value, span, actions):
    # This operation retains its actual original named facts. An incompatible
    # extra observation must be rejected while planning, before any durable
    # recovery intent, rather than discarded or discovered after a source move.
    value.ledger.charge_records(
        16
        * (
            len(value.ledger.cache)
            + len(value.reader._lineages)
            + len(value.reader._presences)
        ),
        65536,
    )
    reader = value.reader
    # Cached files and recorded lineages already contain native ancestry. A raw
    # presence may have no such row; close its actual safe nearest anchor while
    # planning, before any intent, to cover alternative filesystem spellings.
    ancestries = [rows for _anchor_path, rows in value.ledger.ancestry.values()]
    ancestries.extend(reader._lineages.values())
    for path in tuple(reader._presences):
        if path not in value.ledger.ancestry and path.parent not in reader._lineages:
            reader.reserve_lineage(path.parent)
            _actual_anchor, rows = _anchor(path)
            ancestries.append(rows)
    preview = span
    for action in actions:
        sr, dr = (
            preview.roots[action.source_area],
            preview.roots[action.destination_area],
        )
        source, destination = sr.root / action.source, dr.root / action.destination
        node = dict(sr.native)[action.source]
        for path in (
            *value.ledger.cache,
            *value.reader._lineages,
            *value.reader._presences,
        ):
            if _portable_beneath(path, source) or _portable_beneath(path, destination):
                _fail(
                    "named reader facts require a receipt-transfer plan before recovery"
                )
        if stat.S_ISDIR(node.mode) and any(
            row[1:3] == (node.device, node.inode) for rows in ancestries for row in rows
        ):
            _fail("reader directory ancestry requires receipt-transfer before recovery")
        if not stat.S_ISDIR(node.mode):
            for item in value.ledger.cache.values():
                if item.signature is not None and item.signature[:2] == (
                    node.device,
                    node.inode,
                ):
                    _fail(
                        "reader alias requires a receipt-transfer plan before recovery"
                    )
            for presence in value.reader._presences.values():
                if presence is not None and presence[:2] == (node.device, node.inode):
                    _fail(
                        "reader alias requires a receipt-transfer plan before recovery"
                    )
        sn, dn = dict(sr.native), dict(dr.native)
        preview = _advance_move(
            preview,
            action,
            node,
            sn[_parent(action.source)],
            dn[_parent(action.destination)],
        )


def plan_forest_data_recovery(observer, roles, private_root):
    """Actual fresh planning; descriptions alone cannot enroll an effect owner."""
    value, binding = _same_roles(observer, roles)
    journal = value.journal
    value.ledger.charge_records(2 * len(journal._known) + 2 * len(journal._events))
    roster, events = tuple(journal._known.items()), tuple(journal._events)

    def close_planning():
        _same_roles(observer, roles)
        if (
            tuple(journal._events) != events
            or len(journal._known) != len(roster)
            or any(journal._known.get(name) is not row for name, row in roster)
        ):
            _fail("original planning journal prefix changed")

    tail = value.frontier.recovery
    resuming = tail is not None and bool(tail.segments)
    _refuse_recovery_prefix(value, binding, allow_saved=resuming)
    close_planning()
    current = observe_current_native_forest(observer, roles)
    close_planning()
    if current.issues or current.span is None:
        _fail("unresolved current endpoints grant no recovery effects")
    private = Path(private_root)
    count = sum(len(r.native) for r in current.span.roots)
    value.ledger.charge_records(256 + 48 * count, 131072 + 16384 * count)
    if resuming:
        from .retained_layout_forest_recovery_resume import remaining_recovery_actions

        first = tail.segments[0].header
        if (
            private != Path(first["private_root"])
            or sum(r.root == private for r in current.span.roots) != 1
        ):
            _fail("retry requires the exact already-bound recovery quarantine")
        span = current.span
        committed = first["committed"]
        actions, resume = remaining_recovery_actions(value, current)
        original_position = first["original_position"]
        original_frontier = first["original_frontier"]
    else:
        from .retained_layout_forest_recovery_witness import original_recovery_witness

        quarantine = _pin_quarantine(value, current.span, current.metadata, private)
        span = replace(current.span, roots=(*current.span.roots, quarantine))
        committed = _committed(value, current)
        actions = (
            () if committed else _inverse_actions(value, current, len(span.roots) - 1)
        )
        resume = None
        original_position = current.position
        original_frontier = original_recovery_witness(value, current)
    _require_fixed_reader(value, span, actions)
    preview = span
    initial_paths = sum(
        len(str(r.root / name).encode()) for r in span.roots for name, _ in r.native
    )
    maximum_paths = initial_paths
    for action in actions:
        source, target = (
            preview.roots[action.source_area],
            preview.roots[action.destination_area],
        )
        sn, tn = dict(source.native), dict(target.native)
        if (
            action.source not in sn
            or action.destination in tn
            or _parent(action.source) not in sn
            or _parent(action.destination) not in tn
        ):
            _fail("inverse programme collides or loses an original parent")
        preview = _advance_move(
            preview,
            action,
            sn[action.source],
            sn[_parent(action.source)],
            tn[_parent(action.destination)],
        )
        maximum_paths = max(
            maximum_paths,
            sum(
                len(str(r.root / name).encode())
                for r in preview.roots
                for name, _ in r.native
            ),
        )
    records, maximum = _journal_capacity(value, actions, span)
    checks = 2 * len(actions) + 4
    # Fund all repeated full reads and simultaneous successor maps before the
    # first durable recovery intent. Moves conserve nodes and blob groups. The
    # extra path allowance covers every longer original or quarantine spelling.
    # One registered non-reentrant workspace bounds simultaneous verifier,
    # old/current successor, seal and receipt maps. Sequential passes reuse this
    # memory; all file/byte passes and retained journal history remain cumulative.
    value.ledger.charge_records(
        48 * count + records * 512 + 32 * checks,
        32768 * count + 128 * maximum_paths + 4 * records * maximum,
    )
    files, size = value.ledger.files, value.ledger.bytes
    policy = _fund(value, span)
    value.ledger.files += (checks - 1) * (value.ledger.files - files)
    value.ledger.bytes += (checks - 1) * (value.ledger.bytes - size)
    policies = (policy,) * checks
    value.ledger.require_capacity()
    journal = value.journal
    plan = _ForestDataRecoveryPlan(
        value.root,
        value.program.source_phase_identity,
        value.program.identity.uri,
        binding[5],
        private,
        span,
        actions,
        tuple(
            (name, hashlib.sha256(journal._known[name][1]).hexdigest())
            for name in journal._events
        ),
        original_position,
        original_frontier,
        committed,
        (),
        resume,
    )
    document = canonical_json_bytes(_custody_wire(plan))
    if len(canonical_json_bytes(_intent_document(plan))) > 65536:
        _fail("complete recovery intent exceeds finite record ceiling")
    _same_roles(observer, roles)
    roles.require_current()
    close_planning()
    _require_fixed_reader(value, span, actions)
    close_planning()
    if _CREATED_ROLES.get(roles) is not binding:
        _fail("original fresh canonical role binding changed while planning")
    _PREPARED[plan] = _Prepared(
        value,
        roles,
        binding,
        document,
        policies,
        roster,
        events,
        _reader_seal(value),
    )
    prepared = _PREPARED[plan]
    _PLAN_SEALS[plan] = (
        tuple(getattr(prepared, f.name) for f in fields(prepared)),
        canonical_json_bytes([p.to_dict() for p in prepared.policies]),
    )
    return plan


def _prepared(observer, roles, plan):
    if type(plan) is not _ForestDataRecoveryPlan:
        _fail("actual creating forest recovery plan required")
    value, binding = _same_roles(observer, roles)
    original = _PREPARED.get(plan)
    sealed = _PLAN_SEALS.get(plan)
    if (
        original is None
        or sealed is None
        or any(
            getattr(original, f.name) is not old
            for f, old in zip(fields(original), sealed[0], strict=True)
        )
        or canonical_json_bytes([p.to_dict() for p in original.policies]) != sealed[1]
        or original.value is not value
        or original.roles is not roles
        or original.role_binding is not binding
        or canonical_json_bytes(_custody_wire(plan)) != original.document
        or _reader_seal(value) != original.reader_seal
    ):
        _fail("actual creating forest recovery plan lifetime required")
    return original


class _Effect:
    __slots__ = ()

    def _state(self):
        original, progress = _LIVE.get(self), _PROGRESS.get(self)
        if original is None or progress is None:
            _fail("actual forest recovery effect context ended")
        observer, roles, plan, prepared = original
        if _prepared(observer, roles, plan) is not prepared:
            _fail("original forest recovery plan changed")
        span, _index, _checks, roster, events, seal = progress
        if (
            canonical_json_bytes(_custody_wire(span)) != seal
            or tuple(prepared.value.journal._events) != events
            or len(prepared.value.journal._known) != len(roster)
            or any(
                prepared.value.journal._known.get(name) is not row
                for name, row in roster
            )
        ):
            _fail("original forest recovery progress or journal changed")
        return original, progress

    def _step(self, kind, action, phase):
        original, progress = self._state()
        step = _DISPATCH.get(self)
        if step is None or step[1] != kind or step[2] is not action or step[3] != phase:
            _fail("exact registered recovery substep required")
        return original, progress, step

    def _verify(self, key):
        if self in _READING:
            _fail("reentrant recovery workspace use refused")
        original, progress = self._state()
        _observer, roles, _plan, prepared = original
        if key is None or self not in _WRITES or _WRITES[self][0] is not key:
            _fail("one actual registered recovery event required")
        span, index, checks, roster, events, seal = progress
        if checks >= len(prepared.policies):
            _fail("prepaid recovery read count exhausted")
        token = object()
        _READING[self] = token
        next_progress = (span, index, checks + 1, roster, events, seal)
        _PROGRESS[self] = next_progress
        try:

            def closing():
                if _READING.get(self) is not token or self._state() != (
                    original,
                    next_progress,
                ):
                    _fail("original effect state changed during native observation")
                if key is not None:
                    self._append(key)
                expected = _PROGRESS[self]
                roles.require_current()
                if self._state() != (original, expected):
                    _fail("original effect state changed during canonical closure")
                prepared.value.selection.require_current()
                if self._state() != (original, expected):
                    _fail("original effect state changed during selection closure")
                prepared.value.reader.require_current()
                if _READING.get(self) is not token or self._state() != (
                    original,
                    expected,
                ):
                    _fail("original effect state changed during dependency closure")

            _require_current(
                replace(span, budget=prepared.policies[checks]), _after_payload=closing
            )
            if _READING.get(self) is not token:
                _fail("original recovery workspace ended during access teardown")
            self._state()
        finally:
            _READING.pop(self, None)

    def _append(self, key):
        original, progress = self._state()
        record = _WRITES.pop(self, None)
        step = _DISPATCH.get(self)
        if (
            record is None
            or record[0] is not key
            or self not in _READING
            or step is not record[1]
        ):
            _fail("one actual registered recovery event required")
        kind, body = record[2:]
        _DISPATCH[self] = (*step[:3], step[3] + 1)
        observer, roles, plan, prepared = original
        span, index, checks, roster, events, seal = progress
        journal = prepared.value.journal
        journal.append(kind, body)
        if _LIVE.get(self) is not original or _PROGRESS.get(self) is not progress:
            _fail("original effect lifetime ended during durable append")
        _prepared(observer, roles, plan)
        if (
            len(journal._events) != len(events) + 1
            or tuple(journal._events[:-1]) != events
            or len(journal._known) != len(roster) + 1
            or any(journal._known.get(name) is not row for name, row in roster)
        ):
            _fail("recovery append changed unrelated journal records")
        event = json.loads(journal._known[journal._events[-1]][1])
        if event["kind"] != kind or canonical_json_bytes(event["data"]) != body:
            _fail("actual recovery append differs from exact intended record")
        _PROGRESS[self] = (
            span,
            index,
            checks,
            tuple(journal._known.items()),
            tuple(journal._events),
            seal,
        )

    def _emit(self, kind):
        if self in _READING or self in _WRITES:
            _fail("reentrant recovery event refused")
        original, progress = self._state()
        plan = original[2]
        step = _DISPATCH.get(self)
        if step is None:
            _fail("actual registered recovery dispatch required")
        if kind == "begin":
            self._step("begin", None, 0)
            event, data = "forest-data-recovery-intent", _intent_document(plan)
        elif kind == "intent":
            self._step("move", step[2], 0)
            event, data = (
                "forest-data-recovery-entry-intent",
                self._entry_document(step[2]),
            )
        elif kind == "observed":
            self._step("move", step[2], 2)
            receipt = _OBSERVED.pop(self, None)
            if receipt is None or receipt[0] is not step[0]:
                _fail("actual registered observed receipt required")
            event, data = "forest-data-recovery-entry-observed", json.loads(receipt[1])
        elif kind == "finish":
            self._step("finish", None, 0)
            if progress[1] != len(plan.actions):
                _fail("actual complete recovery action schedule required")
            event, data = (
                "forest-data-recovery-observed",
                {
                    "source_phase_identity": plan.phase_identity,
                    "recovery_identity": plan.identity.uri,
                    "state": "committed-unqualified-controls-pending"
                    if plan.committed
                    else "original-data-restored-controls-pending",
                    "data_verified": True,
                    "qualified": False,
                    "controls_released": False,
                },
            )
        else:
            _fail("unrecognized recovery event substep")
        body = canonical_json_bytes(data)
        if len(body) > 65536:
            _fail("prepaid recovery event size exceeded")
        key = object()
        _WRITES[self] = (key, step, event, body)
        self._verify(key)

    def _entry_document(self, action):
        original, progress, step = self._step("move", action, 0)
        span, index = progress[:2]
        plan = original[2]
        if index >= len(plan.actions) or plan.actions[index] is not action:
            _fail("exact next acknowledged recovery action required")
        sr, dr = span.roots[action.source_area], span.roots[action.destination_area]
        sn, dn = dict(sr.native), dict(dr.native)
        return {
            "source_phase_identity": plan.phase_identity,
            "recovery_identity": plan.identity.uri,
            "ordinal": index,
            "action": _custody_wire(action),
            "source": str(sr.root / action.source),
            "destination": str(dr.root / action.destination),
            "node": _custody_wire(sn[action.source]),
            "source_parent": _custody_wire(sn[_parent(action.source)]),
            "destination_parent": _custody_wire(dn[_parent(action.destination)]),
        }

    def _before_effect(self, action):
        _original, _progress, step = self._step("move", action, 1)
        if self in _READING:
            _fail("native effect during recovery read refused")
        _DISPATCH[self] = (*step[:3], "native")

    def _move(self, action):
        original, progress, step = self._step("move", action, 0)
        span = progress[0]
        data = self._entry_document(action)
        sr, dr = span.roots[action.source_area], span.roots[action.destination_area]
        source, destination = sr.root / action.source, dr.root / action.destination
        sn, dn = dict(sr.native), dict(dr.native)
        node, sp, dp = (
            sn[action.source],
            sn[_parent(action.source)],
            dn[_parent(action.destination)],
        )
        self._emit("intent")
        with (
            _pinned_directory(source.parent) as (sfd, sguard),
            _pinned_directory(destination.parent) as (dfd, dguard),
        ):
            self._step("move", action, 1)
            move_layout_entry_exclusive(
                source,
                destination,
                expected_source=node,
                expected_source_parent=sp,
                expected_destination_parent=dp,
                maximum_directory_entries=span.budget.maximum_entries,
                _before_effect=lambda: self._before_effect(action),
            )
            self._step("move", action, "native")
            actual = layout_entry_node(destination)
            after_sp, after_dp = (
                layout_entry_node(source.parent),
                layout_entry_node(destination.parent),
            )
            if (
                actual.after_rename() != node.after_rename()
                or after_sp.directory_identity != sp.directory_identity
                or after_dp.directory_identity != dp.directory_identity
            ):
                _fail("actual recovery native receipt changed original custody")
            os.fsync(sfd)
            os.fsync(dfd)
            sguard()
            self._state()
            dguard()
            self._state()
        successor = _advance_move(span, action, actual, after_sp, after_dp)
        token = object()
        observed = {
            **data,
            "observed_node": _custody_wire(actual),
            "source_parent_after": _custody_wire(after_sp),
            "destination_parent_after": _custody_wire(after_dp),
        }
        _RECEIPTS[token] = (
            self,
            span,
            action,
            successor,
            step[0],
            canonical_json_bytes(observed),
        )
        self._accept(token)
        self._emit("observed")

    def _accept(self, token):
        original, progress = self._state()
        receipt = _RECEIPTS.pop(token, None)
        step = _DISPATCH.get(self)
        if (
            receipt is None
            or receipt[0] is not self
            or receipt[1] is not progress[0]
            or original[2].actions[progress[1]] is not receipt[2]
            or step is None
            or step[0] is not receipt[4]
            or step[3] != "native"
        ):
            _fail("actual one-use recovery native receipt required")
        _PROGRESS[self] = (
            receipt[3],
            progress[1] + 1,
            *progress[2:5],
            canonical_json_bytes(_custody_wire(receipt[3])),
        )
        _DISPATCH[self] = (*step[:3], 2)
        _OBSERVED[self] = (step[0], receipt[5])


def _dispatch(effect, kind, action):
    original, progress = effect._state()
    if effect in _DISPATCH or effect in _READING:
        _fail("reentrant recovery action dispatch refused")
    plan = original[2]
    schedule, cursor = _SCHEDULE[effect]
    if (
        cursor >= len(schedule)
        or schedule[cursor][0] != kind
        or schedule[cursor][1] is not action
    ):
        _fail("exact next registered recovery schedule entry required")
    if (
        kind == "begin"
        and (progress[1] != 0 or progress[4] != original[3].events)
        or kind == "move"
        and (
            progress[1] >= len(plan.actions) or plan.actions[progress[1]] is not action
        )
        or kind == "finish"
        and progress[1] != len(plan.actions)
        or kind not in {"begin", "move", "finish"}
    ):
        _fail("exact next acknowledged recovery dispatch required")
    token = object()
    _DISPATCH[effect] = (token, kind, action, 0)
    try:
        if kind == "move":
            effect._move(action)
        else:
            effect._emit(kind)
        expected = (token, kind, action, 3 if kind == "move" else 1)
        if _DISPATCH.get(effect) != expected:
            _fail("recovery dispatch did not close its exact receipt")
        if _SCHEDULE.get(effect) != (schedule, cursor):
            _fail("original recovery schedule changed during dispatch")
        _SCHEDULE[effect] = (schedule, cursor + 1)
    finally:
        _DISPATCH.pop(effect, None)


def _intent_document(plan):
    quarantine = next(r for r in plan.span.roots if r.root == plan.private_root)
    return {
        "schema": "literate-ai/forest-data-recovery-intent@2"
        if plan.resume is None
        else "literate-ai/forest-data-recovery-intent@3",
        **({} if plan.resume is None else {"resume": plan.resume}),
        "source_phase_identity": plan.phase_identity,
        "program_identity": plan.program_identity,
        "recovery_identity": plan.identity.uri,
        "private_root": str(plan.private_root),
        "private_node": _custody_wire(quarantine.native[0][1]),
        "private_lineage": _custody_wire(quarantine.lineage),
        "original_position": plan.original_position,
        "original_frontier": plan.original_frontier,
        "committed": plan.committed,
        "actions": [_custody_wire(a) for a in plan.actions],
        "qualified": False,
    }


def apply_forest_data_recovery(
    observer, roles, plan, *, acknowledged_recovery_identity, allow_host_execution
):
    """Restore witnessed data; retain canonical controls for real disposition."""
    prepared = _prepared(observer, roles, plan)
    if (
        allow_host_execution is not True
        or type(acknowledged_recovery_identity) is not ContentIdentity
        or acknowledged_recovery_identity != plan.identity
    ):
        _fail(
            "exact current forest recovery acknowledgement and host authority required"
        )
    effect = _Effect()
    if any(v[2] is plan for v in _LIVE.values()):
        _fail("forest recovery plan already executing")
    _LIVE[effect] = (observer, roles, plan, prepared)
    _PROGRESS[effect] = (
        plan.span,
        0,
        0,
        prepared.roster,
        prepared.events,
        canonical_json_bytes(_custody_wire(plan.span)),
    )
    _SCHEDULE[effect] = (
        (("begin", None), *(("move", a) for a in plan.actions), ("finish", None)),
        0,
    )
    stack = ExitStack()
    try:
        for root in plan.span.roots:
            effect._state()
            access = stack.enter_context(_directory_access(root.root))
            effect._state()
            if (
                access is None
                or len(access._absolute) != len(root.lineage)
                or any(
                    actual != row[1:]
                    for (_name, _fd, actual), row in zip(
                        access._absolute, root.lineage, strict=True
                    )
                )
            ):
                _fail("retained recovery root differs from its pinned ancestry")
        _dispatch(effect, "begin", None)
        for action in plan.actions:
            _dispatch(effect, "move", action)
        _dispatch(effect, "finish", None)
        final = _PROGRESS[effect][0]
        stack.close()
        effect._state()
        return {
            "state": "committed-unqualified-controls-pending"
            if plan.committed
            else "original-data-restored-controls-pending",
            "qualified": False,
            "data_verified": True,
            "controls_released": False,
            "internal_recovery_complete": False,
            "span": final,
        }
    finally:
        _LIVE.pop(effect, None)
        _DISPATCH.pop(effect, None)
        _SCHEDULE.pop(effect, None)
        _READING.pop(effect, None)
        _WRITES.pop(effect, None)
        _OBSERVED.pop(effect, None)
        _PROGRESS.pop(effect, None)
        _PREPARED.pop(plan, None)
        _PLAN_SEALS.pop(plan, None)
        for key, receipt in tuple(_RECEIPTS.items()):
            if receipt[0] is effect:
                del _RECEIPTS[key]
        stack.__exit__(*sys.exc_info())
