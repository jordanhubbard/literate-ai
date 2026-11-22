"""Bounded semantic descriptions of compact records; never a journal writer.

Physical events retain their actual hashes and sequence numbers. This module
returns separate immutable semantic rows and never fabricates physical events.
The next actual acquisition must anchor an unfinished batch before it can be
interpreted as an earlier prefix on subsequent reads.
"""

from __future__ import annotations

from dataclasses import dataclass

from literate_ai.contracts.identity import canonical_json_bytes

from . import retained_layout_disposition_compact as compact
from .retained_layout_forest_recovery_transcript import _fields, _identity

BATCH_SCHEMA = "literate-ai/control-disposition-batch@1"
ACQUISITION_SCHEMA = "literate-ai/control-recovery-acquisition@2"
RAW_INTENT = "control-recovery-acquisition-intent"
RAW_OBSERVED = "control-recovery-acquisition-observed"


def _fail(message):
    raise ValueError("layout.disposition-history: " + message)


@dataclass(frozen=True, slots=True)
class _History:
    # Physical position, semantic kind, immutable canonical semantic body.
    records: tuple[tuple[int, str, bytes], ...]
    # Disposition identity, canonical acquisition epoch, namespace commitment.
    bindings: tuple[tuple[str, str, str], ...]
    # At most one unfinished batch: full manifest digest and exact prefix head.
    open_batch: tuple[str, str | None] | None


def batch_boundary(manifest_digest, *, head=compact._ABSENT):
    compact._digest(manifest_digest)
    data = dict(schema=BATCH_SCHEMA, manifest_digest=manifest_digest)
    if head is not compact._ABSENT:
        compact._head(head)
        data["head"] = head
    return canonical_json_bytes(data)


def acquisition_bytes(recovery_identity, open_batch):
    _identity(recovery_identity)
    if open_batch is None:
        return canonical_json_bytes(dict(recovery_identity=recovery_identity))
    if type(open_batch) is not tuple or len(open_batch) != 2:
        _fail("exact immutable unfinished batch anchor required")
    digest, head = open_batch
    compact._digest(digest)
    compact._head(head)
    return canonical_json_bytes(
        dict(
            schema=ACQUISITION_SCHEMA,
            recovery_identity=recovery_identity,
            disposition_head=dict(manifest_digest=digest, head=head),
        )
    )


def _boundary(data, *, headed):
    _fields(data, "schema manifest_digest head" if headed else "schema manifest_digest")
    if data["schema"] != BATCH_SCHEMA:
        _fail("exact versioned batch boundary required")
    compact._digest(data["manifest_digest"])
    if headed:
        compact._head(data["head"])
    return data["manifest_digest"]


def _raw_identity(data):
    if set(data) == {"recovery_identity"}:
        _identity(data["recovery_identity"])
        return data["recovery_identity"], None
    _fields(data, "schema recovery_identity disposition_head")
    if data["schema"] != ACQUISITION_SCHEMA:
        _fail("supported anchored acquisition schema required")
    _identity(data["recovery_identity"])
    anchor = data["disposition_head"]
    _fields(anchor, "manifest_digest head")
    compact._digest(anchor["manifest_digest"])
    compact._head(anchor["head"])
    return data["recovery_identity"], (anchor["manifest_digest"], anchor["head"])


def expand_history(
    events, payloads, *, maximum, payload_limit, storage_limit, expanded_limit
):
    """Expand authenticated immutable inputs after caller-paid decode funding.

    Canonical envelope validation and native membership remain the actual
    journal producer's responsibility. All physical batch boundaries and raw
    acquisition anchors are checked here before legacy semantic replay.
    """
    available = compact._bounded_payloads(
        payloads, maximum, payload_limit, storage_limit
    )
    if (
        type(events) is not tuple
        or len(events) > 256
        or any(type(raw) is not bytes or len(raw) > 128 * 1024 for raw in events)
    ):
        _fail("finite immutable actual event bytes required")
    if type(expanded_limit) is not int or expanded_limit < 1:
        _fail("explicit prepaid total expansion bound required")
    if sum(map(len, events)) + sum(len(raw) for _, raw in payloads) > storage_limit:
        _fail("event and payload bytes exceed original storage policy")
    result, bindings, seen = [], [], set()
    identities = set()
    active, paired, used = None, None, 0

    def emit(position, kind, raw):
        nonlocal used
        used += len(raw)
        if used > expanded_limit:
            _fail("semantic history exceeds prepaid expansion bound")
        result.append((position, kind, raw))

    def finish(closed_head=compact._OPEN):
        nonlocal active
        position, manifest, decision, complete = active
        rows = compact.expand_batch(
            manifest.raw,
            payloads,
            maximum=maximum,
            payload_limit=payload_limit,
            storage_limit=storage_limit,
            expanded_limit=expanded_limit - used,
            decision=decision,
            complete=complete,
            closed_head=closed_head,
        )
        for kind, raw in rows:
            emit(position, kind, raw)
        bindings.append((manifest.identity, manifest.epoch, manifest.namespace))
        # The compact decoder has already established one exact contiguous chain.
        prefix = compact.STEP_MAGIC + manifest.digest.encode("ascii") + b"\n"
        head, last = None, -1
        for digest, raw in payloads:
            if raw.startswith(prefix):
                step = compact._step(manifest, raw, maximum)
                if step["index"] > last:
                    head, last = digest, step["index"]
        active = None
        return manifest.digest, head

    for position, raw in enumerate(events):
        event = compact._document(raw, 128 * 1024)
        if type(event.get("kind")) is not str or type(event.get("data")) is not dict:
            _fail("plain actual event kind and body required")
        kind, data = event["kind"], event["data"]
        if kind == compact.BEGIN:
            digest = _boundary(data, headed=False)
            if active is not None or digest in seen or digest not in available:
                _fail("one new durable manifest per disposition required")
            manifest = compact.decode_manifest(
                available[digest],
                payloads=payloads,
                maximum=maximum,
                payload_limit=payload_limit,
                storage_limit=storage_limit,
            )
            if manifest.digest != digest:
                _fail("batch boundary differs from manifest content address")
            if manifest.identity in identities:
                _fail("disposition plan identity repeats across manifests")
            seen.add(digest)
            identities.add(manifest.identity)
            active = (position, manifest, compact._ABSENT, compact._ABSENT)
            continue
        if kind in {compact.DECISION, compact.COMPLETE}:
            digest = _boundary(data, headed=True)
            if active is None or digest != active[1].digest:
                _fail("batch boundary lacks its actual manifest intent")
            index, manifest, decision, complete = active
            if kind == compact.DECISION:
                if decision is not compact._ABSENT:
                    _fail("batch release decision repeats")
                active = (index, manifest, data["head"], complete)
            else:
                active = (index, manifest, decision, data["head"])
                finish()
            continue
        if kind in {RAW_INTENT, RAW_OBSERVED}:
            identity, anchor = _raw_identity(data)
            if kind == RAW_INTENT:
                if active is not None:
                    if anchor is None or anchor[0] != active[1].digest:
                        _fail("new acquisition must anchor unfinished batch")
                    if finish(anchor[1]) != anchor:
                        _fail("new acquisition changes unfinished batch head")
                elif anchor is not None:
                    _fail("acquisition anchor has no unfinished batch")
                if paired is not None:
                    _fail("raw acquisition intent lacks previous observation")
                paired = canonical_json_bytes(data)
            else:
                if paired is None or canonical_json_bytes(data) != paired:
                    _fail("exact anchored acquisition observation required")
                paired = None
            emit(position, kind, canonical_json_bytes(dict(recovery_identity=identity)))
            continue
        if active is not None:
            _fail("foreign event interrupts compact disposition")
        emit(position, kind, canonical_json_bytes(data))
    open_batch = finish() if active is not None else None
    return _History(tuple(result), tuple(bindings), open_batch)
