"""Factory-derived compact storage for the existing native disposition machine.

This backend records descriptions only. The enclosing registered forest owner
continues to validate every dispatch, FD, intent, effect receipt and successor.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from weakref import WeakKeyDictionary

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from . import retained_layout_disposition_compact as compact
from . import retained_layout_disposition_history as history
from .exclusive_entry import layout_entry_node
from .repository_refresh_reservations import _custody_wire
from .retained_layout_forest_disposition_budget import _CHANGED_NODE_WIRE
from .retained_layout_journal import _COMPARE_CHUNK_BYTES

_PLANS = WeakKeyDictionary()
_STATES = WeakKeyDictionary()
_SEALS = WeakKeyDictionary()
_ENTERED = WeakKeyDictionary()


def _fail(message):
    raise ValueError("layout.disposition-recording: " + message)


@dataclass(frozen=True, slots=True)
class _Recording:
    manifest: object
    missing: tuple[tuple[str, bytes], ...]
    step_limit: int
    steps: int


def prepare(plan):
    """Derive a recording from the actual registered complete forest factory."""
    from . import retained_layout_forest_disposition as forest

    binding = (
        forest._PLANS.get(plan) if type(plan) is forest._ForestDispositionPlan else None
    )
    if binding is None or plan in _PLANS or plan not in forest._COUPONS:
        _fail("new actual registered forest disposition required")
    # The registered workspace already pays simultaneous normalization/encoding
    # buffers. Borrow it with actual non-reentrancy enforced, without consuming
    # a native payload-read coupon. New retained manifest/step records and their
    # future journal storage remain independently charged below.
    with forest._workspace(plan):
        value, journal = binding[2].value, binding[2].value.journal
        schedule = forest._schedule(plan)
        actions = tuple(
            (kind, entry)
            for kind, entry in schedule
            if entry is not None and kind.endswith("-intent")
        )
        # Existing plan seals pay original immutable nodes/paths. Fund the new
        # manifest dictionaries, encoding buffers and current parent observations
        # before constructing them; no source body is duplicated here.
        value.ledger.charge_records(
            512 + 256 * len(actions),
            65536 + 16 * _CHANGED_NODE_WIRE * len(actions),
        )
        payloads = tuple(
            (digest, journal._known[f"p-{digest}.bin"][1])
            for digest in sorted(journal._payloads)
        )
        known = dict(payloads)
        missing, roster = {}, []
        native = forest._native(plan)
        for kind, entry in actions:
            digest = hashlib.sha256(entry.content).hexdigest()
            if digest not in known:
                missing[digest] = entry.content
                known[digest] = entry.content
            original = hashlib.sha256(entry.original_content).hexdigest()
            if known.get(original) != entry.original_content:
                _fail("original acquired control payload must already be durable")
            normalize = kind == compact._NORMAL
            if normalize and entry.named != entry.target.path:
                _fail("compact normalization requires public named coordinate")
            ordinal = None if normalize else native.index(entry)
            roster.append(
                dict(
                    kind=kind,
                    group=entry.group,
                    path=str(entry.target.path),
                    source=str(entry.named),
                    destination=None
                    if normalize
                    else str(plan.retirement.root / f"control-{ordinal}"),
                    original_node=_custody_wire(entry.original_node),
                    node=_custody_wire(entry.node),
                    before_payload=digest,
                    original_payload=original,
                    source_parent=None
                    if normalize
                    else _custody_wire(layout_entry_node(entry.named.parent)),
                    destination_parent=None
                    if normalize
                    else _custody_wire(layout_entry_node(plan.retirement.root)),
                )
            )
        raw = compact.manifest_bytes(
            forest._boundary(plan, "recovery-control-disposition-intent"),
            canonical_identity(
                _custody_wire((plan.entries, plan.public_nodes, plan.areas, plan.span))
            ).uri,
            binding[2].role_binding[5],
            forest._boundary(plan, "recovery-control-disposition-observed")["state"],
            str(forest.layout_pending_control_path(plan.data.root)),
            roster,
        )
        # Decode/immutable projections and all future encoded subrecords are funded
        # in addition to the existing native verifier workspace and finite coupons.
        tokens = 1 + sum(raw.count(c) for c in (b"{", b"[", b",", b":"))
        value.ledger.charge_records(512 + 16 * tokens, 65536 + 12 * len(raw))
        manifest = compact.decode_manifest(
            raw,
            payloads=tuple(known.items()),
            maximum=journal._budget.maximum_payload_bytes,
            payload_limit=journal._budget.maximum_events,
            storage_limit=journal._budget.maximum_storage_bytes,
        )
        step_limit = 1
        for action in roster:
            data = {
                key: action[key]
                for key in ("group", "path", "original_node", "node", "before_payload")
            }
            data.update(
                operation="a" * 32,
                source_phase_identity=plan.data.phase_identity,
                observed_node=action["node"],
            )
            if action["kind"] == compact._RETIRE:
                data.update(
                    (key, action[key])
                    for key in (
                        "source",
                        "destination",
                        "source_parent",
                        "destination_parent",
                    )
                )
            prototype = compact.step_bytes(
                manifest,
                2 * len(actions) - 1,
                "0" * 64,
                action["kind"].removesuffix("-intent") + "-observed",
                data,
            )
            step_limit = max(step_limit, len(prototype) + 3 * _CHANGED_NODE_WIRE)
        steps = 2 * len(actions)
        value.ledger.charge_records(256 + 256 * steps, 65536 + 4 * steps * step_limit)
        # All old events, payloads, stages and orphans remain counted. One physical
        # stage suffices because each publication completes before the next starts.
        required_payloads = len(missing) + 1 + steps
        event_limit = len(history.batch_boundary(manifest.digest, head="0" * 64)) + 1024
        required_bytes = (
            sum(len(body) for _, body in journal._known.values())
            + sum(map(len, missing.values()))
            + len(raw)
            + steps * step_limit
            + 3 * event_limit
        )
        if (
            len(journal._events) + 3 > journal._budget.maximum_events
            or len(journal._payloads) + required_payloads
            > journal._budget.maximum_events
            or step_limit > journal._budget.maximum_payload_bytes
            or required_bytes > journal._budget.maximum_storage_bytes
            or len(journal._stages) + 1 > journal._budget.maximum_stages
        ):
            _fail("complete compact disposition exceeds immutable journal policy")
        # Two opening full-byte traversals authenticate the existing roster; the
        # writer closes unchanged native signatures after staging and publication.
        # The new staged/published body is actually read twice. Grow the finite
        # roster in actual publication order; existing orphan members still count.
        units = [*(len(body) for body in missing.values()), len(raw), event_limit]
        for index in range(steps):
            if index == 2 * manifest.pending_index:
                units.append(event_limit)
            units.append(step_limit)
        units.append(event_limit)
        count = len(journal._known)
        total = sum(len(body) for _, body in journal._known.values())
        peak = max((len(body) for _, body in journal._known.values()), default=0)
        io_files = io_bytes = 0
        for unit in units:
            if max(peak, unit) > value.ledger.budget.maximum_file_bytes:
                _fail("publication read exceeds fresh per-file policy")
            io_files += 2 * count + 2
            io_bytes += 2 * total + 2 * unit
            count, total, peak = count + 1, total + unit, max(peak, unit)
        value.ledger.files += io_files
        value.ledger.bytes += io_bytes
        # Every old and newly published body is compared as a complete bounded
        # stream. The new immutable source bodies are funded above and retained
        # only after actual native comparison. Fund simultaneous byte chunks and
        # slices rather than allocate another whole stage/published body.
        scratch = 4 * min(_COMPARE_CHUNK_BYTES, peak + 1)
        value.ledger.charge_records(128 + 8 * count, 65536 + scratch)
        recording = _Recording(manifest, tuple(missing.items()), step_limit, steps)
        _PLANS[plan] = recording
        _SEALS[plan] = (
            recording,
            tuple(getattr(recording, f.name) for f in fields(recording)),
            manifest,
            tuple(getattr(manifest, f.name) for f in fields(manifest)),
            canonical_json_bytes(_custody_wire(recording)),
            journal._budget,
            tuple(journal._budget.to_dict().items()),
        )


def initialize(effect):
    recording = _PLANS.get(effect.plan)
    if type(recording) is not _Recording:
        _fail("actual prepaid forest recording required")
    _STATES[effect] = (recording, None, 0)
    close(effect)


def close(effect):
    state = _STATES.get(effect)
    if state is None or _PLANS.get(effect.plan) is not state[0]:
        _fail("actual creating compact recording lifetime required")
    seal = _SEALS.get(effect.plan)
    recording = state[0]
    if (
        seal is None
        or recording is not seal[0]
        or any(
            getattr(recording, f.name) is not old
            for f, old in zip(fields(recording), seal[1], strict=True)
        )
        or recording.manifest is not seal[2]
        or any(
            getattr(seal[2], f.name) is not old
            for f, old in zip(fields(seal[2]), seal[3], strict=True)
        )
        or canonical_json_bytes(_custody_wire(recording)) != seal[4]
        or effect.pool._journal._budget is not seal[5]
        or tuple(seal[5].to_dict().items()) != seal[6]
    ):
        _fail("original recording manifest, fields or policy changed")
    return state


def _publish_payload(journal, raw, close_originals, adopt_owned):
    close_originals()
    before = tuple(journal._known.items())
    events, payloads = tuple(journal._events), frozenset(journal._payloads)
    digest = hashlib.sha256(raw).hexdigest()
    actual = journal.store_payload(raw)
    if (
        actual != digest
        or tuple(journal._events) != events
        or journal._payloads != payloads | {digest}
        or len(journal._known) != len(before) + (digest not in payloads)
        or any(journal._known.get(name) is not row for name, row in before)
        or journal._known.get(f"p-{digest}.bin", (None, None))[1] != raw
    ):
        _fail("foreign change during actual compact payload publication")
    adopt_owned()
    return digest


def record(effect, kind, data):
    """Store one already-authorized logical step; return its physical event kind."""
    from . import retained_layout_forest_disposition as forest

    if (
        type(effect) is not forest.controls._RecoveryDisposition
        or effect in _ENTERED
        or forest._RECORDING.get(effect) != (kind, canonical_json_bytes(data))
    ):
        _fail("actual entered forest recording dispatch required")
    state = forest._state(effect)
    if state is None:
        _fail("actual entered forest disposition required")
    state.close(effect)
    original = close(effect)
    original_flags = effect.active, effect.finished
    forest_progress = forest._STATES[effect]
    token = object()
    _ENTERED[effect] = token

    def close_originals():
        if (
            _ENTERED.get(effect) is not token
            or close(effect) is not original
            or forest._RECORDING.get(effect) != (kind, canonical_json_bytes(data))
            or forest._state(effect) is not state
            or forest._STATES.get(effect) is not forest_progress
            or effect.active is not original_flags[0]
            or effect.finished is not original_flags[1]
        ):
            _fail("original entered recording token or progress changed")
        # Pure owner/registration seals, now against the exact authenticated
        # history of our last publication. No old history check is relaxed.
        effect._flags()
        state.close(effect)

    def adopt_owned():
        nonlocal forest_progress
        if forest._STATES.get(effect) is not forest_progress:
            _fail("original forest progress changed during owned publication")
        forest_progress = (
            *forest_progress[:5],
            forest._history(effect.pool._journal),
            *forest_progress[6:],
        )
        forest._STATES[effect] = forest_progress
        close_originals()

    try:
        recording, head, index = close(effect)
        journal = effect.pool._journal
        manifest = recording.manifest
        event_kind, event_raw = None, None
        if kind == "recovery-control-disposition-intent":
            for _digest, raw in recording.missing:
                _publish_payload(journal, raw, close_originals, adopt_owned)
            digest = _publish_payload(
                journal, manifest.raw, close_originals, adopt_owned
            )
            if digest != manifest.digest or index or head is not None:
                _fail("exact original manifest publication required")
            event_kind, event_raw = compact.BEGIN, history.batch_boundary(digest)
        elif kind in {
            "recovery-control-release-decision",
            "recovery-control-disposition-observed",
        }:
            expected = (
                2 * manifest.pending_index
                if kind.endswith("decision")
                else recording.steps
            )
            if index != expected:
                _fail("batch boundary escapes actual logical step cursor")
            event_kind = (
                compact.DECISION if kind.endswith("decision") else compact.COMPLETE
            )
            event_raw = history.batch_boundary(manifest.digest, head=head)
        else:
            raw = compact.step_bytes(manifest, index, head, kind, data)
            if len(raw) > recording.step_limit or index >= recording.steps:
                _fail("actual step exceeds prepaid encoded bound")
            compact._step(manifest, raw, journal._budget.maximum_payload_bytes)
            head = _publish_payload(journal, raw, close_originals, adopt_owned)
            index += 1
        if event_kind is not None:
            close_originals()
            before = tuple(journal._known.items())
            events = tuple(journal._events)
            journal.append(event_kind, event_raw)
            event = json.loads(journal._known[journal._events[-1]][1])
            if (
                len(journal._known) != len(before) + 1
                or tuple(journal._events[:-1]) != events
                or len(journal._events) != len(events) + 1
                or any(journal._known.get(name) is not row for name, row in before)
                or event["kind"] != event_kind
                or canonical_json_bytes(event["data"]) != event_raw
                or event["sequence"] != len(events)
                or event["previous"]
                != (
                    None
                    if not events
                    else hashlib.sha256(journal._known[events[-1]][1]).hexdigest()
                )
            ):
                _fail("foreign change during actual compact boundary publication")
            adopt_owned()
        close_originals()
        _STATES[effect] = recording, head, index
    finally:
        _ENTERED.pop(effect, None)
