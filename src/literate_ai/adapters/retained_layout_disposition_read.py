"""Paid actual-journal snapshots for compact semantic replay, never effects."""

from __future__ import annotations

import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields, replace

from . import retained_layout_disposition_compact as compact
from . import retained_layout_disposition_history as history
from .catalog_copy_plan import _Observation
from .retained_layout_journal import _LIVE_WRITERS, _LayoutJournalWriter

_PLAN = ContextVar("retained_layout_control_plan_history", default=None)
_PLAN_KEY = object()
_PLANS = {}
_PLAN_SEALS = {}


class _ControlPlanRead:
    __slots__ = ()

    def __init__(self, key):
        if key is not _PLAN_KEY:
            raise TypeError("actual compact control plan required")


@dataclass(frozen=True, slots=True)
class _PlanState:
    owner: object
    value: object
    snapshot: tuple | None = None
    result: history._History | None = None


def _active_plan():
    owner = _PLAN.get()
    if owner is None:
        return None
    if type(owner) is not _ControlPlanRead or owner not in _PLANS:
        _fail("original compact control plan lifetime ended")
    state = _PLANS[owner]
    seal = _PLAN_SEALS.get(owner)
    if (
        type(state) is not _PlanState
        or seal is None
        or seal[0] is not state
        or any(
            getattr(state, field.name) is not original
            for field, original in zip(fields(state), seal[1], strict=True)
        )
    ):
        _fail("original compact control plan state changed")
    if state.result is not None and (
        type(state.result) is not history._History
        or seal[2] is None
        or any(
            getattr(state.result, field.name) is not original
            for field, original in zip(fields(state.result), seal[2], strict=True)
        )
    ):
        _fail("original compact control plan history changed")
    return state


def _store_plan(owner, state):
    _PLANS[owner] = state
    _PLAN_SEALS[owner] = (
        state,
        tuple(getattr(state, field.name) for field in fields(state)),
        None
        if state.result is None
        else tuple(getattr(state.result, field.name) for field in fields(state.result)),
    )


@contextmanager
def control_plan_history(pool):
    """Reuse immutable decoding only within one actual read-only control plan.

    Every read still funds and performs both complete native comparisons. The
    scope carries descriptions, never a currentness or descriptor grant, and is
    revoked even when a copied context outlives the creating call.
    """
    if not has_compact(pool._journal):
        yield
        return
    from .retained_layout_forest_observation import _POOLS, _record

    owner = _POOLS.get(pool)
    if owner is None:
        _fail("actual fresh forest observer required for compact controls")
    value = _record(owner, reading=True)
    value.ledger.charge_records(64, 65536)
    scope = _ControlPlanRead(_PLAN_KEY)
    _store_plan(scope, _PlanState(owner, value))
    token = _PLAN.set(scope)
    try:
        yield
        if _record(owner, reading=True) is not value:
            _fail("original compact control plan lifetime ended")
        state = _active_plan()
        if state is not _PLANS.get(scope):
            _fail("original compact control plan lifetime ended")
        _close_plan_snapshot(state)
    finally:
        _PLANS.pop(scope, None)
        _PLAN_SEALS.pop(scope, None)
        _PLAN.reset(token)


def _close_plan_snapshot(scope):
    # The final parent guard can call native observers. Close the original
    # authenticated snapshot after it, without another callback or native read.
    if scope.snapshot is None:
        return
    admission, budget, policy, names, roster, payloads = scope.snapshot
    journal = scope.value.journal
    if (
        _LIVE_WRITERS.get(journal) is not admission
        or journal._budget is not budget
        or tuple(budget.to_dict().items()) != policy
        or tuple(journal._events) != names
        or len(journal._known) != len(roster)
        or any(journal._known.get(name) is not row for name, row in roster)
        or frozenset(journal._payloads) != payloads
    ):
        _fail("original compact control plan snapshot changed")


def _plan_scope(journal, allowance):
    scope = _active_plan()
    if scope is None:
        return None
    from .retained_layout_forest_observation import _record

    owner, value = scope.owner, scope.value
    if (
        value.journal is not journal
        or value.ledger is not allowance
        or _record(owner, reading=True) is not value
    ):
        _fail("original compact control plan lifetime ended")
    return scope


def _fail(message):
    raise ValueError("layout.disposition-read: " + message)


def has_compact(journal):
    """Conservative sizing-only detection in an actual finite cached roster."""
    if type(journal) is not _LayoutJournalWriter or journal not in _LIVE_WRITERS:
        _fail("actual live journal required")
    if type(journal._events) is not list or len(journal._events) > 256:
        _fail("finite physical event roster required")
    for name in journal._events:
        if type(name) is not str:
            _fail("plain physical event name required")
        row = journal._known.get(name)
        if type(row) is not tuple or len(row) != 2 or type(row[1]) is not bytes:
            _fail("plain actual event bytes required")
        if (
            b"recovery-control-batch-" in row[1]
            or history.ACQUISITION_SCHEMA.encode() in row[1]
        ):
            return True
    return False


def _tokens(raw):
    # Colons/separators inside text overcount, rather than hide decoded values.
    return 1 + sum(raw.count(c) for c in (b"{", b"[", b",", b":"))


def read_history(journal, allowance):
    """Authenticate native inputs, then decode without intervening callbacks.

    No mutable JSON crosses a native callback. Exact native row identities and
    admission close in the producer before the callback-free semantic projection.
    All decoded projections, output bytes and simultaneous scratch are prepaid.
    """
    if type(allowance) is not _Observation:
        _fail("actual finite observation allowance required")
    scope = _plan_scope(journal, allowance)
    has_compact(journal)
    if type(journal._payloads) is not set or len(journal._payloads) > 256:
        _fail("finite physical payload roster required")
    if type(journal._known) is not dict or len(journal._known) > 1024:
        _fail("finite actual journal member roster required")
    allowance.charge_records(
        128
        + 8 * len(journal._events)
        + 8 * len(journal._payloads)
        + 8 * len(journal._known),
        65536,
    )
    admission = _LIVE_WRITERS[journal]
    roster = tuple(journal._known.items())
    budget = journal._budget
    policy = tuple(budget.to_dict().items())
    names = tuple(journal._events)
    rows = tuple(journal._known[name] for name in names)
    payload_names = frozenset(journal._payloads)
    if scope is not None and scope.snapshot is not None:
        old_admission, old_budget, old_policy, old_names, old_roster, old_payloads = (
            scope.snapshot
        )
        if (
            admission is not old_admission
            or budget is not old_budget
            or policy != old_policy
            or names != old_names
            or payload_names != old_payloads
            or len(roster) != len(old_roster)
            or any(journal._known.get(name) is not row for name, row in old_roster)
        ):
            _fail("original compact control plan snapshot changed")
    total, peak = 0, 0
    for name, row in roster:
        if (
            type(name) is not str
            or type(row) is not tuple
            or len(row) != 2
            or type(row[1]) is not bytes
        ):
            _fail("plain complete native journal roster required")
        size = len(row[1])
        if size > allowance.budget.maximum_file_bytes:
            _fail("journal member exceeds fresh per-file read policy")
        total, peak = total + size, max(peak, size)
    # The producer performs two complete native comparisons, each against this
    # immutable expected roster and its original exact read lengths.
    allowance.files += 2 * len(roster)
    allowance.bytes += 2 * total
    # The funded producer streams comparisons rather than joining whole native
    # members into duplicate buffers. Both complete passes still read every byte.
    allowance.charge_records(128 + 4 * len(roster), 65536 + 2 * min(65536, peak + 1))
    event_size = sum(len(row[1]) for row in rows)
    if scope is None or scope.result is None:
        # Only a fresh semantic expansion parses the event envelopes. Native
        # snapshot authentication compares their original immutable bytes; its
        # complete two-pass costs were funded independently above.
        event_tokens = sum(_tokens(row[1]) for row in rows)
        allowance.charge_records(128 + 8 * event_tokens, 65536 + 8 * event_size)
    events, payloads = journal._raw_documents_from_snapshot(
        (names, rows), _expected=roster
    )
    if scope is not None and _active_plan() is not scope:
        _fail("original compact control plan lifetime ended")
    if scope is not None and scope.result is not None:
        result = scope.result
    else:
        result = _expand(journal, allowance, events, payloads, event_size)
    # This trailing close is pure: no foreign/native callback can enlarge the
    # decoded roster after funding or invalidate the original snapshot unnoticed.
    if (
        _LIVE_WRITERS.get(journal) is not admission
        or journal._budget is not budget
        or tuple(budget.to_dict().items()) != policy
        or tuple(journal._events) != names
        or len(journal._known) != len(roster)
        or any(journal._known.get(name) is not row for name, row in roster)
        or frozenset(journal._payloads) != payload_names
        or payload_names != frozenset(digest for digest, _ in payloads)
    ):
        _fail("funded physical event snapshot changed")
    if scope is not None:
        if _active_plan() is not scope:
            _fail("original compact control plan lifetime ended")
        _store_plan(
            _PLAN.get(),
            replace(
                scope,
                snapshot=(admission, budget, policy, names, roster, payload_names),
                result=result,
            ),
        )
    return result


def _expand(journal, allowance, events, payloads, event_size):
    # Envelope parsing is paid above. The following pure pass sizes only the
    # manifests and matching step payloads; ordinary packed source payloads are
    # neither parsed nor charged as decoded control records.
    declarations = set()
    for raw in events:
        event = json.loads(raw)
        if event.get("kind") == compact.BEGIN:
            data = event.get("data")
            if type(data) is not dict:
                _fail("plain manifest declaration required")
            declarations.add(compact._digest(data.get("manifest_digest")))
    prefixes = tuple(
        compact.STEP_MAGIC + digest.encode("ascii") + b"\n" for digest in declarations
    )
    relevant = tuple(
        raw
        for digest, raw in payloads
        if digest in declarations or raw.startswith(prefixes)
    )
    size = sum(map(len, relevant))
    tokens = sum(_tokens(raw) for raw in relevant)
    expanded_limit = event_size + 4 * size + 65536
    allowance.charge_records(
        512 + 12 * tokens + 32 * len(payloads), 65536 + 12 * size + 4 * expanded_limit
    )
    return history.expand_history(
        events,
        payloads,
        maximum=journal._budget.maximum_payload_bytes,
        payload_limit=journal._budget.maximum_events,
        storage_limit=journal._budget.maximum_storage_bytes,
        expanded_limit=expanded_limit,
    )


def control_history(pool, *, _events=False, _event_kinds=None):
    """Use only the actual forest observer's ledger for raw control descriptions."""
    _active_plan()  # Refuse a copied ended scope before any native parent guard.
    from .retained_layout_forest_observation import _POOLS, _record

    owner = _POOLS.get(pool)
    if owner is None:
        _fail("actual fresh forest observer required for compact controls")
    value = _record(owner, reading=True)
    result = read_history(value.journal, value.ledger)
    if _record(owner, reading=True) is not value:
        _fail("original compact control read lifetime ended")
    if _events:
        # Every mutable view is fresh and funded before its callback-free parse,
        # including views projected from a reused immutable semantic history.
        value.ledger.charge_records(
            128
            + 8
            * sum(
                _tokens(raw)
                for _, kind, raw in result.records
                if _event_kinds is None or kind in _event_kinds
            ),
            65536
            + 8
            * sum(
                len(raw)
                for _, kind, raw in result.records
                if _event_kinds is None or kind in _event_kinds
            ),
        )
    return result


def control_events(pool, *, kinds=None):
    """Decode fresh requested views after authenticating the complete history.

    Selection saves only JSON construction. All immutable semantic records and
    compact transitions are still validated, and every native byte is compared.
    Sequence numbers retain their positions in the complete semantic history.
    """
    if kinds is not None and (
        type(kinds) is not frozenset or any(type(kind) is not str for kind in kinds)
    ):
        raise TypeError("plain immutable control event selection required")
    if not has_compact(pool._journal):
        return tuple(
            event
            for event in pool._journal.events
            if kinds is None or event["kind"] in kinds
        )
    result = control_history(pool, _events=True, _event_kinds=kinds)
    return tuple(
        dict(sequence=ordinal, kind=kind, data=json.loads(raw))
        for ordinal, (_physical, kind, raw) in enumerate(result.records)
        if kinds is None or kind in kinds
    )
