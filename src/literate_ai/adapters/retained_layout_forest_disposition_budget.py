"""Paid bounds for one non-reentrant disposition workspace, not writer rights.

Original source observations and their immutable seals remain charged to the
creating ledger. Cumulative payload reads are charged separately by the caller.
Here we reserve new reference tables, retained records and the simultaneous
wire/normalization buffers that overlap a full native verifier and its callbacks.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass

from .retained_layout_journal import _RECORD_LIMIT
from .retained_layout_recovery_controls import _RecoveredControlSet

# A control receipt changes only regular-file/directory native facts. On the
# supported native stat ABIs, 128 decimal digits exceed even 128-bit fields with
# nanosecond scaling. Existing immutable facts are covered by their exact seals.
# Sixteen 160-byte scalar encodings include local-integer wrappers/native IDs;
# 256 bytes cover the fixed LayoutEntryNode keys and punctuation. No new runtime
# input limit is imposed by this conservative producer-representation bound.
_CHANGED_NODE_WIRE = 256 + 16 * 160


def _area_limit(span, path):
    """A read bound from the complete current span; never occupancy authority."""
    for root in span.roots:
        if path == root.root:
            prefix = ""
        elif path.is_relative_to(root.root):
            name = path.relative_to(root.root).as_posix()
            node = next((node for n, node in root.native if n == name), None)
            if node is None or not stat.S_ISDIR(node.mode):
                break
            prefix = name + "/"
        else:
            continue
        return min(
            1024,
            sum(
                bool(name)
                and name.startswith(prefix)
                and "/" not in name[len(prefix) :]
                for name, _node in root.native
            ),
        )
    raise ValueError("layout.forest-disposition: private area escapes current span")


def fund_planning(value, data, prepared, owners, retirement):
    """Fund new plan objects and encoding before any variable construction.

    Source nodes, cached payloads and old journal bytes stay charged and shared.
    Only the new maps/reference arrays, observations, plan and seals are retained
    here. Runtime verifier maps and callback wire work remain independently funded
    by _prepay, including while these planner locals are still live.
    """
    ledger = value.ledger
    nodes = sum(len(root.native) for root in data.span.roots)
    markers = sum(len(owner._markers) for owner in owners)
    facts = (
        len(ledger.cache)
        + len(ledger.ancestry)
        + len(value.reader._presences)
        + len(value.reader._lineages)
    )
    # Pay for sizing traversal, path conversion and the bounded area-limit map
    # before materializing it. Existing exact seals bound original path text.
    ledger.charge_records(
        128 + 8 * nodes + 32 * markers + 8 * facts,
        len(prepared.document) + len(prepared.reader_seal) + _RECORD_LIMIT,
    )
    journal = value.journal
    event_names = tuple(journal._events)
    event_rows = tuple(journal._known[name] for name in event_names)
    event_bytes = sum(len(row[1]) for row in event_rows)
    # Structural punctuation overcounts tokens inside strings, which is safe.
    # Container opens, member colons and separators bound every decoded JSON
    # container/key/value without allocating a second parser during sizing.
    event_records = sum(
        1 + raw.count(b"{") + raw.count(b"[") + 2 * raw.count(b":") + raw.count(b",")
        for _node, raw in event_rows
    )
    limits = {}
    retirement_bytes = len(str(retirement.root).encode())
    path_bytes = 2 * retirement_bytes * (1 + len(retirement.lineage))
    lineage_slots = 2 * len(retirement.lineage)
    for owner in owners:
        if type(owner) is _RecoveredControlSet:
            roots = tuple(a.root for a in owner._plan.recovery_areas)
            if owner._plan.retirement_root:
                roots += (owner._plan.retirement_root,)
            for path in roots:
                if path not in limits:
                    limits[path] = _area_limit(data.span, path)
                    lineage_slots += len(path.parts)
                    path_bytes += len(str(path).encode()) * (1 + len(path.parts))
        group = (
            owner._plan.group if type(owner) is _RecoveredControlSet else owner._group
        )
        for ordinal, marker in enumerate(owner._markers):
            target = marker.target
            path_bytes += sum(
                len(str(path).encode()) for path in (target.path, target.anchor)
            )
            # Named locations can differ from target paths after retirement.
            named = (
                owner._plan.markers[ordinal].named
                if type(owner) is _RecoveredControlSet
                else owner._locations.get(target.path, target.path)
            )
            path_bytes += len(str(named).encode()) + len(group.encode())
            path_bytes += retirement_bytes + len(f"control-{ordinal}")
    observed = sum(limits.values())
    events = len(value.journal._events)
    # Bytes become fixed digest commitments in _custody_wire; histories retain
    # original bodies by reference. Each new observed area node and control can
    # introduce native scalar encodings. 4096 bounds native component text on
    # supported filesystem ABIs, including UTF-8 expansion; this adds no input
    # acceptance rule. The read limits reject an extra raced entry before capture.
    # A same-count raced replacement can itself be a symbolic link. Reserve
    # entry-name and link-target text separately, before any such observation.
    observations_wire = observed * (_CHANGED_NODE_WIRE + 2 * 6 * 4096)
    controls_wire = markers * (4 * _CHANGED_NODE_WIRE + 1024)
    encoded_plan = (
        2 * len(prepared.document)
        + len(prepared.reader_seal)
        + observations_wire
        + controls_wire
        + 6 * path_bytes
        + 512 * lineage_slots
        + 128 * events
        + 65536
    )
    # One retained plan seal plus at most three simultaneous normalization,
    # encoding and comparison buffers. Records fund _shape maps/sets and their
    # field/reference slots separately from these bytes.
    ledger.charge_records(
        256
        + 32 * nodes
        + 64 * markers
        + 16 * facts
        + 16 * observed
        + 16 * lineage_slots
        + 4 * events
        + 2 * event_records,
        4 * encoded_plan + 2 * event_bytes,
    )
    return limits, (event_names, event_rows)


def require_planning_history(value, history):
    """Refuse new envelopes before another funded JSON traversal can begin."""
    names, rows = history
    journal = value.journal
    if tuple(journal._events) != names or any(
        journal._known.get(name) is not row
        for name, row in zip(names, rows, strict=True)
    ):
        raise ValueError("layout.forest-disposition: funded planning history changed")


@dataclass(frozen=True, slots=True)
class _Workspace:
    records: int
    bytes: int
    encoded_unit: int
    retained_records: int
    mutable_nodes: int


def fund_sizing(ledger, plan, sealed_plan):
    """Pay before building the maximal roster or traversing its variable paths."""
    nodes = sum(len(root.native) for root in plan.span.roots)
    ledger.charge_records(
        128 + 8 * nodes + 64 * len(plan.entries) + 8 * len(plan.span.roots),
        len(sealed_plan) + 8192 * len(plan.entries),
    )


def workspace_bound(plan, maximum, *, sealed_plan, reader_seal, schedule, checks):
    """Size only known descriptions; no payload read or capability is created.

    The plan seal already contains the complete source span and exact control/area
        descriptions. The reader seal contains its cached observations. Successors
        share immutable objects; at most eight native-node occurrences per control
        plus four per root change across the span, descriptor and area views.
    """
    nodes = sum(len(root.native) for root in maximum.roots)
    payloads = sum(len(root.payloads) + len(root.links) for root in maximum.roots)
    lineages = sum(len(root.lineage) for root in maximum.roots)
    entries = len(plan.entries)
    mutable_nodes = 8 * entries + 4 * len(maximum.roots)
    # Only the retirement names are new; original names and links remain in the
    # sealed plan. Six bounds JSON escaping even for unusual private path text.
    path_bytes = 0
    for ordinal, entry in enumerate(plan.entries):
        future = plan.retirement.root / f"control-{ordinal}"
        path_bytes += 6 * (len(str(future).encode()) + len(str(entry.named).encode()))
    encoded_unit = (
        len(sealed_plan)
        + len(reader_seal)
        + mutable_nodes * _CHANGED_NODE_WIRE
        + path_bytes
        + _RECORD_LIMIT
    )
    # Current span/entry/reader/pending seals, proposed bundle/projection seals,
    # and active comparison/encoding overlap at most eight such units. Namespace
    # verifier maps have their own _fund reservation and remain charged while
    # dependency callbacks use this workspace. Nonreentrancy prevents a second
    # verifier/transition workspace from overlapping it. The actual recording
    # preparation borrows this same registered slot for its transient encoding;
    # its new retained decoded records and journal storage are charged separately.
    wire_workspace = 8 * encoded_unit
    # Each future journal envelope has the existing enforced record ceiling.
    # Histories retain these bytes by reference rather than eight copies/event.
    retained_records = schedule * _RECORD_LIMIT + sum(
        len(entry.content) for entry in plan.entries
    )
    records = (
        256 * entries
        + 64 * checks
        + 512 * schedule
        + 32 * nodes
        + 16 * payloads
        + 8 * lineages
    )
    return _Workspace(
        records,
        wire_workspace + retained_records,
        encoded_unit,
        retained_records,
        mutable_nodes,
    )
