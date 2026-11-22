"""Read-only terminal forest observation under real recovered control descriptors.

No canonical writer lease is constructed and no public marker is recreated.
Saved disposition records describe the closure; actual raw factories provide
every current descriptor, mutex and private-node proof used here.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, fields, replace

from literate_ai.contracts.identity import canonical_json_bytes

from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_roles import _project_roles
from .retained_layout_forest_control_inventory import _ControlInventory
from .retained_layout_forest_disposition_reads import (
    require_successors,
    seal_successors,
)
from .retained_layout_forest_generations import _catalog
from .retained_layout_forest_observation import _record
from .retained_layout_git_controls import observe_layout_git_controls
from .retained_layout_recovery_controls import (
    _close_dependencies,
    _close_dependency_facts,
    _close_retirement_facts,
    _optional_node,
    _require_recovered_creation,
)
from .retained_layout_recovery_disposition import _actions, _entries

_KEY = object()
_TERMINALS = {}
_SEALS = {}
_READING = {}
_CHECKS = {}


def _fail(message):
    raise ValueError("layout.forest-terminal: " + message)


def _wire(value):
    return canonical_json_bytes(_custody_wire(value))


class _TerminalControls:
    __slots__ = ()

    def __init__(self, key):
        if key is not _KEY:
            _fail("actual terminal read factory required")


@dataclass(frozen=True, slots=True)
class _TerminalState:
    value: object
    catalog: object
    seed: object
    git: object
    facts: object
    targets: tuple
    plans: tuple
    required: tuple
    roster: tuple
    events: tuple
    pid: int
    thread: int


def _terminal_inventory(value, owner):
    state = _TERMINALS.get(owner) if type(owner) is _TerminalControls else None
    if state is None or state.value is not value:
        _fail("actual creating terminal control read lifetime required")
    _close_terminal_inventory(value, owner, state.facts)
    return state.facts


def _close_terminal_inventory(value, owner, facts):
    state = _TERMINALS.get(owner) if type(owner) is _TerminalControls else None
    sealed = _SEALS.get(owner)
    if (
        state is None
        or sealed is None
        or state.value is not value
        or state.facts is not facts
    ):
        _fail("actual creating terminal control read lifetime ended")
    if any(
        getattr(state, f.name) is not old
        for f, old in zip(fields(state), sealed[0], strict=True)
    ):
        _fail("original terminal creating state changed")
    if any(
        getattr(facts, f.name) is not old
        for f, old in zip(fields(facts), sealed[3], strict=True)
    ) or any(
        a is not b
        for a, b in zip(
            (
                state.catalog._recovered,
                state.catalog._inventory,
                state.catalog._required,
            ),
            sealed[4],
            strict=True,
        )
    ):
        _fail("original terminal fact or catalog references changed")
    require_successors(
        (
            state.seed,
            state.git,
            state.targets,
            state.catalog._inventory,
            state.catalog._required,
            state.plans,
        ),
        sealed[2],
    )
    if (
        any(
            getattr(state, f.name) is not old
            for f, old in zip(fields(state), sealed[0], strict=True)
        )
        or (state.pid, state.thread) != (os.getpid(), threading.get_ident())
        or _record(value.owner, reading=True) is not value
        or state.catalog._active is not True
        or state.catalog._receiver != os.getpid()
        or facts.issuer is not owner
        or facts.key is not state.catalog
        or facts.seed is not state.seed
        or facts.git is not state.git
        or facts.recovered is not state.catalog._recovered
        or facts.incoming is not None
        or state.catalog._incoming is not None
        or facts.inventory is not state.catalog._inventory
        or facts.missing != ()
        or state.catalog._required is not state.required
        or state.catalog._pool is not value.pool
        or tuple(value.journal._events) != state.events
        or len(value.journal._known) != len(state.roster)
        or any(value.journal._known.get(n) is not row for n, row in state.roster)
        or _wire((state.seed, state.git, state.targets, facts.inventory)) != sealed[1]
    ):
        _fail("original terminal descriptor/producer binding changed")
    for raw, plan in zip(facts.recovered, state.plans, strict=True):
        _require_recovered_creation(raw)
        if raw._plan is not plan:
            _fail("original raw proposal reference changed")


def _require_terminal_inputs(value, owner, facts):
    _close_terminal_inventory(value, owner, facts)
    if owner in _READING:
        _fail("reentrant terminal native verification refused")
    count = _CHECKS.get(owner, 0)
    if count <= 0:
        _fail("original finite terminal verification allowance exhausted")
    _CHECKS[owner] = count - 1
    token = object()
    _READING[owner] = token
    state = _TERMINALS[owner]

    def guarded(call):
        _close_terminal_inventory(value, owner, facts)
        result = call()
        _close_terminal_inventory(value, owner, facts)
        return result

    try:
        guarded(state.catalog.verify_all)
        guarded(state.seed.require_initial_inputs)
        guarded(lambda: state.git.require_unchanged(state.catalog))
        guarded(value.selection.require_current)
        guarded(value.reader.require_current)
        retired = guarded(state.catalog._close_currentness)
        producers = guarded(lambda: _close_dependencies(value.pool))
        guarded(lambda: state.git.close_native_inputs(state.catalog.native_inputs))
        guarded(state.seed.close_native_inputs)
        guarded(state.catalog._close_marker_inputs)
        guarded(lambda: _close_retirement_facts(retired))
        guarded(lambda: _close_dependency_facts(value.pool, producers))
        if _READING.get(owner) is not token:
            _fail("original terminal verifier workspace ended")
    finally:
        _READING.pop(owner, None)


def _require_raw_tail(value, recovered):
    journal = value.journal
    by_identity = {r._plan.identity.uri: r for r in recovered}
    names = journal._events[len(value.events) :]
    value.ledger.charge_records(
        128 * len(names), 4 * sum(len(journal._known[n][1]) for n in names)
    )
    if len(by_identity) != len(recovered) or len(names) != 2 * len(recovered):
        _fail("exact creating raw acquisition tail required")
    import json

    used = set()
    for i in range(0, len(names), 2):
        pair = [json.loads(journal._known[n][1]) for n in names[i : i + 2]]
        body = pair[0]["data"]
        identity = body.get("recovery_identity") if type(body) is dict else None
        raw = by_identity.get(identity)
        if (
            raw is None
            or identity in used
            or pair[0]["kind"] != "control-recovery-acquisition-intent"
            or pair[1]["kind"] != "control-recovery-acquisition-observed"
            or canonical_json_bytes(body)
            != canonical_json_bytes({"recovery_identity": identity})
            or canonical_json_bytes(pair[1]["data"]) != canonical_json_bytes(body)
        ):
            _fail("tail differs from actual creating raw acquisition")
        prefix = tuple(
            journal._known[n][1] for n in journal._events[: len(value.events) + i]
        )
        if raw._plan.history != prefix:
            _fail("actual raw proposal history differs from terminal tail")
        used.add(identity)


@contextmanager
def _terminal_controls(value, recovered):
    tail = value.frontier.recovery
    if (
        tail is None
        or not tail.dispositions
        or not tail.dispositions[-1].complete
        or tail.canonical_pending is not None
    ):
        _fail("strict recorded complete disposition required")
    # Fund initial native descriptor checks before the catalog borrows any FD.
    if type(recovered) is not tuple or not 1 <= len(recovered) <= 32:
        _fail("actual raw descriptor tuple required")
    for raw in recovered:
        _require_recovered_creation(raw)
    markers = sum(len(raw._plan.markers) for raw in recovered)
    passes = 16 + 8 * markers
    value.ledger.files += passes * markers
    value.ledger.bytes += passes * sum(
        len(r.content) for raw in recovered for r in raw._plan.markers
    )
    value.ledger.charge_records(512 + 128 * markers, 262144 + 16384 * markers)
    _require_raw_tail(value, recovered)
    catalog = _catalog(value, recovered)
    roster, events = tuple(value.journal._known.items()), tuple(value.journal._events)
    original = (
        catalog._pool,
        catalog._recovered,
        catalog._inventory,
        catalog._receiver,
    )
    required = catalog._required

    def close_initial():
        if (
            _record(value.owner, reading=True) is not value
            or catalog._active is not True
            or catalog._incoming is not None
            or catalog._pool is not original[0]
            or catalog._recovered is not original[1]
            or catalog._inventory is not original[2]
            or catalog._required is not required
            or catalog._receiver != original[3]
            or original[3] != os.getpid()
            or tuple(value.journal._events) != events
            or len(value.journal._known) != len(roster)
            or any(value.journal._known.get(n) is not row for n, row in roster)
        ):
            _fail("original terminal catalog changed during producer discovery")
        for raw in recovered:
            _require_recovered_creation(raw)

    owner = _TerminalControls(_KEY)
    try:
        seed = _project_roles(value.root)
        close_initial()
        advisory = tuple(t for t in seed.targets() if t.advisory)
        close_initial()
        catalog._required = advisory
        required = advisory
        catalog._require_coverage(advisory, complete=True)
        git = observe_layout_git_controls(value.root, reservations=catalog)
        close_initial()
        targets = tuple(dict.fromkeys(seed.targets() + git.targets()))
        close_initial()
        catalog._required = tuple(t for t in targets if t.advisory)
        required = catalog._required
        catalog._require_coverage(catalog._required, complete=True)
        current = {t.path: t for t in targets}
        for row in catalog._inventory:
            named, _marker, _fd, _node, target, _body = row
            if (
                current.get(target.path) != target
                or (target.advisory and named != target.path)
                or (not target.advisory and named == target.path)
            ):
                _fail("terminal descriptors do not match exact canonical targets")
        for target in targets:
            if not any(row[4] == target for row in catalog._inventory):
                _fail("complete actual canonical target custody required")
            if not target.advisory and _optional_node(target.path) is not None:
                _fail("terminal public native barrier is occupied")
        producers = seal_successors((seed, git, targets, required))
        entries, _bindings = _entries(value.pool, recovered)
        if _actions(entries) != ((), ()):
            _fail("actual controls have not completed disposition")
        close_initial()
        require_successors((seed, git, targets, required), producers)
        # The actual producers have now captured their bounded metadata inputs.
        # Prepay every subsequent native closure of those cached facts.
        cached = tuple(value.ledger.cache.values())
        checks = 8
        value.ledger.files += checks * (len(cached) + passes * markers)
        value.ledger.bytes += checks * (
            sum(len(i.content or b"") for i in cached)
            + passes
            * sum(len(r.content) for raw in recovered for r in raw._plan.markers)
        )
        value.ledger.charge_records(
            128 * (len(cached) + markers),
            8192 * (len(cached) + markers)
            + 4 * max((1, *(len(i.content or b"") for i in cached))),
        )
        value.ledger.require_capacity()
        facts = _ControlInventory(
            owner, catalog, seed, git, recovered, None, catalog._inventory, ()
        )
        state = _TerminalState(
            value,
            catalog,
            seed,
            git,
            facts,
            targets,
            tuple(raw._plan for raw in recovered),
            required,
            roster,
            events,
            os.getpid(),
            threading.get_ident(),
        )
        _TERMINALS[owner] = state
        _SEALS[owner] = (
            tuple(getattr(state, f.name) for f in fields(state)),
            _wire((seed, git, targets, facts.inventory)),
            seal_successors(
                (
                    seed,
                    git,
                    targets,
                    catalog._inventory,
                    catalog._required,
                    state.plans,
                )
            ),
            tuple(getattr(facts, f.name) for f in fields(facts)),
            (catalog._recovered, catalog._inventory, catalog._required),
        )
        _CHECKS[owner] = checks
        _require_terminal_inputs(value, owner, facts)
        yield owner
        _require_terminal_inputs(value, owner, facts)
    finally:
        _TERMINALS.pop(owner, None)
        _SEALS.pop(owner, None)
        _CHECKS.pop(owner, None)
        _READING.pop(owner, None)
        catalog._active = False


def observe_terminal_native_forest(observer, recovered):
    """Verify final data and controls without creating ordinary writer rights."""
    from .retained_layout_forest_recovery_current import observe_recovered_forest

    value = _record(observer)
    with observer._reads():
        with _terminal_controls(value, recovered) as controls:
            result = observe_recovered_forest(observer, controls)
            if result.issues or not result.journal_complete:
                _fail("complete final source and control closure required")
            result = replace(result, position="disposition-recorded")
            sealed = seal_successors((result,))
        require_successors((result,), sealed)
    if _record(observer) is not value:
        _fail("original terminal observer lifetime ended")
    for raw in recovered:
        _require_recovered_creation(raw)
    require_successors((result,), sealed)
    return result
