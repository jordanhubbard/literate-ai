"""Pinned future forest effect areas and same-original-ledger allowances.

These descriptions are not source or publication authority. Only the actual
source join may consume their prepaid representations, under its original live
phase and separately verified metadata/control receipt machinery.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, fields
from pathlib import Path

from literate_ai.contracts.identity import canonical_json_bytes

from .exclusive_entry import _from_stat, layout_entry_node
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_partition import _lineage


def _fail(message):
    raise ValueError("layout.forest-effects: " + message)


def _metadata_allowance(root, private, prospective, inputs, namespace_count):
    from .retained_layout_transaction import (
        _LIFT,
        HARNESS_WRAPPER_FILENAME,
        RETAINED_LAYOUT_PATH,
    )

    names = (HARNESS_WRAPPER_FILENAME, _LIFT, RETAINED_LAYOUT_PATH)
    original = {item.path: item for item in inputs}
    destinations = []
    for index, name in enumerate(names):
        if original[root / name].content is not None:
            destinations.append(private / f"old-{index}")
        destinations.append(root / name)
    payload = 2 * sum(len(prospective[name]) for name in names)
    payload += sum(len(original[root / name].content or b"") for name in names)
    count = namespace_count * len(destinations)
    records = 64 + 2 * count + 6 * len(names)
    size = payload + 256 * count + 16 * sum(len(str(p).encode()) for p in destinations)
    return records, payload, size, len(destinations)


def _finalization_allowance(sequence_count, namespace_count, cache_count, marker_count):
    count = sequence_count * (namespace_count + cache_count + marker_count)
    return 128 + 12 * count, 1024**2 + 1024 * count


@dataclass(frozen=True, slots=True)
class _Pin:
    root: Path
    descriptor: int
    guard: object
    node: object
    lineage: tuple

    @property
    def data(self):
        return self.root, self.node, self.lineage


@dataclass(frozen=True, slots=True)
class _Effects:
    metadata: _Pin
    retirement: _Pin
    parking: Path
    metadata_allowance: tuple
    finalization_allowance: tuple
    journal_tail: tuple
    metadata_steps: int
    marker_count: int
    json_nodes_per_event: int = 512
    event_preview_identities: tuple = ()

    @property
    def document(self):
        return {
            "schema": "literate-ai/forest-bound-effects@1",
            "metadata": _custody_wire(self.metadata.data),
            "retirement": _custody_wire(self.retirement.data),
            "parking": str(self.parking),
            "metadata_allowance": self.metadata_allowance,
            "finalization_allowance": self.finalization_allowance,
            "journal_tail": self.journal_tail,
            "metadata_steps": self.metadata_steps,
            "marker_count": self.marker_count,
            "json_nodes_per_event": self.json_nodes_per_event,
            "event_preview_identities": self.event_preview_identities,
        }


def _document_nodes(raw):
    from .retained_layout_journal import _document

    value = _document(raw)
    pending, count = [value], 0
    while pending:
        item = pending.pop()
        count += 1 + (len(item) if type(item) is dict else 0)
        if type(item) is dict:
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
    return count


def _decision_document(phase_identity, retirement_root, *, committed):
    """Compact forest profile; the journal chain binds all actual receipts.

    The original plan and complete native/metadata receipts are already durable.
    Do not duplicate an unbounded input roster or invent future native values.
    Fresh recovery must still acquire real roles and reclassify endpoints.
    """
    if type(committed) is not bool:
        _fail("exact forest decision state required")
    raw = canonical_json_bytes(
        {
            "schema": "literate-ai/forest-finalization-decision@1",
            "source_phase_identity": phase_identity,
            "state": "committed-unqualified" if committed else "finalizing",
            "retirement_root": str(retirement_root),
            "qualified": False,
        }
    )
    _document_nodes(raw)
    return raw


def _binding(value):
    return (
        value,
        tuple((f.name, getattr(value, f.name)) for f in fields(value)),
        tuple(
            (pin, tuple((f.name, getattr(pin, f.name)) for f in fields(pin)))
            for pin in (value.metadata, value.retirement)
        ),
        canonical_json_bytes(value.document),
    )


def _matches(value, binding):
    return (
        type(value) is _Effects
        and binding[0] is value
        and all(getattr(value, name) is old for name, old in binding[1])
        and all(
            getattr(pin, name) is old for pin, rows in binding[2] for name, old in rows
        )
        and canonical_json_bytes(value.document) == binding[3]
    )


def _separate(lineage, other):
    if lineage[-1][1:3] in {row[1:3] for row in other} or other[-1][1:3] in {
        row[1:3] for row in lineage
    }:
        _fail("private effect areas physically overlap")


def _pin(record, root):
    from .retained_layout_source_admission import _enter_phase_resource
    from .retained_layout_source_metadata import _separate_predecessor_state

    if type(root) not in (str, type(Path())):
        _fail("both private effect paths must be bound before source movement")
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute private effect roots required")
    descriptor, guard = _enter_phase_resource(record.phase, _pinned_directory(root))
    lineage, node = _lineage(root), _from_stat(os.fstat(descriptor))
    if (
        layout_entry_node(root) != node
        or node.uid != os.geteuid()
        or stat.S_IMODE(node.mode) != 0o700
    ):
        _fail("actual owned mode0700 private effect root required")
    with os.scandir(descriptor) as entries:
        if next(entries, None) is not None:
            _fail("bound private effect root is not empty")
    for other in (record.original.root, record.pool.root, record.journal_root):
        _separate(lineage, _lineage(other))
    _separate_predecessor_state(record, lineage, _before_movement=True)
    guard()
    if _from_stat(os.fstat(descriptor)) != node or _lineage(root) != lineage:
        _fail("bound private effect root changed during admission")
    from .retained_layout_forest_operation import _join_operation_area

    _join_operation_area(record, root, node, lineage)
    return _Pin(root, descriptor, guard, node, lineage)


def _prepare(record, metadata_root, retirement_root, span, graph, parking):
    from .retained_layout_transaction import _LIFT, RETAINED_LAYOUT_PATH

    ledger, reader, phase = record.original.ledger, record.original.reader, record.phase
    # Fixed-size area bindings and their complete serializations are charged
    # before retaining either actual descriptor observation.
    ledger.charge_records(
        128,
        65536
        + 128
        * sum(len(str(p).encode()) for p in (metadata_root, retirement_root, parking)),
    )
    metadata, retirement = _pin(record, metadata_root), _pin(record, retirement_root)
    _separate(metadata.lineage, retirement.lineage)
    parking_parent = _lineage(parking.parent)
    for pin in (metadata, retirement):
        if (
            parking.is_relative_to(pin.root)
            or pin.root.is_relative_to(parking)
            or pin.lineage[-1][1:3] in {row[1:3] for row in parking_parent}
        ):
            _fail("bound effect area overlaps original parking placement")
    markers = record.controls.reservations._markers
    devices = {
        span.roots[0].native[0][1].device,
        metadata.node.device,
        retirement.node.device,
        parking_parent[-1][1],
        os.fstat(record.pool._descriptor).st_dev,
        os.fstat(record.pool._journal._descriptor).st_dev,
    }
    for marker in markers:
        devices.add(os.fstat(marker.descriptor).st_dev)
        parent = record.controls.reservations._held.nodes[marker.target.path.parent][0]
        devices.add(os.fstat(parent).st_dev)
    nodes = dict(span.roots[0].native)
    for name, _body in phase.plan.prospective:
        parent = (phase.plan.root / name).parent
        relative = (
            ""
            if parent == phase.plan.root
            else parent.relative_to(phase.plan.root).as_posix()
        )
        if relative not in nodes:
            _fail("actual metadata parent required before forest movement")
        devices.add(nodes[relative].device)
    if devices != {metadata.node.device}:
        _fail(
            "complete forest publication requires one filesystem before source effects"
        )
    actions = sum(not marker.target.advisory or marker.created for marker in markers)
    native_count = sum(not marker.target.advisory for marker in markers)
    sequence_count = actions + 2
    for index in range(3):
        for prefix in ("new", "old"):
            if (
                reader.file(
                    metadata.root / f"{prefix}-{index}",
                    optional=True,
                    maximum_bytes=ledger.budget.maximum_file_bytes,
                ).content
                is not None
            ):
                _fail("bound metadata endpoint is occupied")
    for index in range(native_count):
        if (
            reader.file(
                retirement.root / f"control-{index}", optional=True, maximum_bytes=256
            ).content
            is not None
        ):
            _fail("bound retirement endpoint is occupied")
    prospective = dict(phase.plan.prospective)
    if any(
        len(body) > ledger.budget.maximum_file_bytes for body in prospective.values()
    ):
        _fail("prospective metadata exceeds original per-file allowance")
    for name in (_LIFT, RETAINED_LAYOUT_PATH):
        reader.json_value(prospective[name], str(phase.plan.root / name))
    maximum_nodes = len(span.roots[0].native) + len(graph.create_directories) + 3
    records, payload, size, steps = _metadata_allowance(
        phase.plan.root, metadata.root, prospective, phase.plan.inputs, maximum_nodes
    )
    finalization = _finalization_allowance(
        sequence_count, maximum_nodes, len(ledger.cache), len(markers)
    )
    ledger.bytes += payload
    ledger.charge_records(records, size)
    ledger.charge_records(*finalization)
    # Both terminal parking snapshots and all pins/coupons survive simultaneously
    # with the original/final views until normal descriptor-stack retirement.
    ledger.charge_records(
        128 + 32 * (len(graph.retain_directories) + 1),
        65536
        + 128
        * sum(len(str(parking / name).encode()) for name in graph.retain_directories),
    )
    tail_events = 1 + 2 * steps + 1 + 2 * actions + 4
    tail_payloads = steps + 2 * len(markers) + 3
    tail_storage = (
        tail_events * 128 * 1024
        + payload
        + 2 * sum(len(m.content) for m in markers)
        + 65536
    )
    from .retained_layout_reservations import _finalization_intent_data

    # Fund the exact known control-roster preview before allocating/decoding it.
    ledger.charge_records(
        256 + 96 * len(markers),
        65536 + 128 * sum(len(str(m.target.path).encode()) for m in markers),
    )
    previews = (
        _decision_document(phase.plan.identity.uri, retirement.root, committed=False),
        _decision_document(phase.plan.identity.uri, retirement.root, committed=True),
        canonical_json_bytes(
            _finalization_intent_data(
                retirement.root,
                retirement.node,
                markers,
                record.controls.reservations._expected,
            )
        ),
    )
    node_limit = max(512, *(_document_nodes(raw) for raw in previews))
    for source, target in graph.carriers:
        node = nodes[source]
        path = phase.plan.root / target
        reader.reserve_lineage(path if stat.S_ISDIR(node.mode) else path.parent)
    for name in graph.create_directories:
        reader.reserve_lineage(phase.plan.root / name)
    reader.reserve_lineage(parking.parent)
    reader.reserve_lineage(parking)
    return _Effects(
        metadata,
        retirement,
        parking,
        (records, payload, size),
        finalization,
        (tail_events, tail_payloads, tail_storage),
        steps,
        len(markers),
        node_limit,
        tuple(hashlib.sha256(raw).hexdigest() for raw in previews),
    )


def _require_empty(pin):
    descriptor, root, guard, node, lineage = (
        pin.descriptor,
        pin.root,
        pin.guard,
        pin.node,
        pin.lineage,
    )
    guard()
    if (
        _from_stat(os.fstat(descriptor)) != node
        or layout_entry_node(root) != node
        or _lineage(root) != lineage
    ):
        _fail("original bound empty effect area changed")
    with os.scandir(descriptor) as entries:
        if next(entries, None) is not None:
            _fail("original bound private effect area became occupied")
    guard()
    if _from_stat(os.fstat(descriptor)) != node or layout_entry_node(root) != node:
        _fail("original bound effect area changed after final guard")


def _preflight_decode_headroom(ledger, program, effects):
    # Actual future journal records are decoded once when written. This is
    # remaining headroom, not a second debit of prepaid retained graph views.
    records = (
        effects.json_nodes_per_event
        * (program.required_events + effects.journal_tail[0] + 2)
        + 256
    )
    if (
        records > ledger.budget.maximum_entries - ledger.records
        or 4096 * records > ledger.metadata - ledger.charged
    ):
        _fail("complete forest operation lacks original decoded-record headroom")
