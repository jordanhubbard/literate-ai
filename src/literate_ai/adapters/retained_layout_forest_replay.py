"""Bounded native receipt-prefix descriptions, never recovery effect rights.

This interpreter retains the last recorded namespace and an optional unfinished
intent. It does not resolve an unfinished intent by assuming its effect happened.
Fresh canonical controls and complete current native reclassification are separate
requirements. Parking ancestry is supplied as fresh observation data, not inferred
from an old program that did not record the parking parent's ancestry.
"""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.contracts.identity import canonical_json_bytes

from .catalog_copy_plan import _Observation
from .retained_layout_forest_native import (
    _advance_move,
    _native_event_schedule,
    _native_steps,
    _NativeForestProgram,
    _rows,
    _wire,
    plan_native_forest,
)
from .retained_layout_forest_span import _shape, _SpanRoot
from .retained_layout_recovery_controls import _node


def _fail(message):
    raise ValueError("layout.forest-replay: " + message)


@dataclass(frozen=True, slots=True)
class _RecordedFrontier:
    span: object
    pending: tuple | None
    refresh_directories: tuple
    consumed: int
    complete: bool
    recovery: object = None


def _recorded_node(value):
    # Control decoding already validates the complete plain POSIX integer shape.
    # Source aliases additionally retain their raw text, without dereferencing it.
    if type(value) is not dict:
        _fail("recorded native node required")
    link = value.get("link_target")
    node = _node(dict(value, link_target=None))
    if stat.S_ISLNK(node.mode):
        if type(link) is not str or len(link.encode()) > 4096:
            _fail("bounded raw symbolic text required")
    elif link is not None:
        _fail("non-symbolic native node cannot carry symbolic text")
    return replace(node, link_target=link)


def _parent_name(name):
    parent = Path(name).parent.as_posix()
    return "" if parent == "." else parent


def _source_node(span, action):
    root = span.roots[action.source_area]
    node = dict(root.native)[action.source]
    if stat.S_ISLNK(node.mode):
        node = replace(node, link_target=dict(root.links)[action.source])
    return node


def _with_node(span, area, name, node):
    roots = list(span.roots)
    native = dict(roots[area].native)
    native[name] = node
    roots[area] = replace(roots[area], native=_rows(native))
    return replace(span, roots=tuple(roots))


def _directory_receipt(span, dirty, area, name, document):
    node = _recorded_node(document)
    old = dict(span.roots[area].native).get(name)
    if old is None or old.directory_identity != node.directory_identity:
        _fail("recorded parent identity differs from its predecessor")
    if (area, name) not in dirty and old != node:
        _fail("recorded parent changed without an intervening creation")
    dirty.discard((area, name))
    return _with_node(span, area, name, node)


def _parking_lineage(program, parent, node):
    paths = tuple(str(p) for p in (*reversed(program.private_root.parents),))
    if type(parent) is not tuple or len(parent) != len(paths):
        _fail("fresh parking-parent ancestry data required")
    for row, path in zip(parent, paths, strict=True):
        if (
            type(row) is not tuple
            or len(row) != 6
            or row[0] != path
            or any(type(v) is not int for v in row[1:])
            or not stat.S_ISDIR(row[3])
        ):
            _fail("plain direct parking-parent ancestry required")
    original = {row[0]: row for row in program.span.roots[0].lineage}
    if any(row[0] in original and original[row[0]] != row for row in parent):
        _fail("parking ancestry disagrees with original shared ancestors")
    if parent[-1][1] != node.device:
        _fail("parking creation changed filesystem")
    return (
        *parent,
        (
            str(program.private_root),
            node.device,
            node.inode,
            node.mode,
            node.uid,
            node.gid,
        ),
    )


def replay_native_forest(program, records, *, allowance, parking_parent_lineage):
    """Interpret an exact prefix under a separately supplied finite allowance.

    Each record is (kind, canonical envelope bytes, canonical payload bytes).
    The envelope must bind both original identities and the actual payload digest.
    Input data, the result and an empty/complete prefix grant no phase or FD rights.
    """
    if type(program) is not _NativeForestProgram or type(allowance) is not _Observation:
        _fail("typed native program and explicit fresh allowance required")
    if (
        type(records) is not tuple
        or len(records) > 256
        or type(program.required_events) is not int
        or not 4 <= program.required_events <= 256
    ):
        _fail("finite original native event prefix required")
    # Fund program rebuild, schedule, sequential span maps and all encoded/decoded
    # documents before constructing them. The same ledger charges actual JSON nodes.
    from .retained_layout_forest_span import _ForestSpan

    if (
        type(program.span) is not _ForestSpan
        or type(program.span.roots) is not tuple
        or len(program.span.roots) != 1
        or type(program.span.roots[0]) is not _SpanRoot
        or type(program.span.roots[0].native) is not tuple
        or type(program.directories) is not tuple
        or type(program.actions) is not tuple
    ):
        _fail("plain complete original program structures required")
    count = (
        len(program.span.roots[0].native)
        + len(program.directories)
        + len(program.actions)
        + 1
    )
    allowance.charge_records(128 + 32 * count, 65536 + 8192 * count)
    # The complete span shape bounds all subsequent names and raw alias text.
    _shape(program.span)
    paths = sum(
        len(str(program.span.roots[0].root / name).encode())
        for name, _ in program.span.roots[0].native
    )
    paths += sum(
        len(str(program.private_root / action.destination).encode())
        for action in program.actions
    )
    links = sum(len(text.encode()) for _, text in program.span.roots[0].links)
    allowance.charge_records(0, 128 * paths + 32 * links)
    total = 0
    for record in records:
        if (
            type(record) is not tuple
            or len(record) != 3
            or type(record[0]) is not str
            or any(type(raw) is not bytes for raw in record[1:])
            or len(record[1]) > 65536
            or len(record[2]) > 64 * 1024**2
        ):
            _fail("bounded plain native event encodings required")
        total += len(record[1]) + len(record[2])
    allowance.charge_records(128 + 24 * len(records), 65536 + 4 * total)
    rebuilt = plan_native_forest(
        program.span,
        program.graph,
        program.private_root,
        source_phase_identity=program.source_phase_identity,
        journal_tail=program.journal_tail,
    )
    original = canonical_json_bytes(program.document)
    if canonical_json_bytes(rebuilt.document) != original:
        _fail("recorded native program differs from its deterministic schedule")
    schedule, steps = _native_event_schedule(program), _native_steps(program)
    if len(schedule) != program.required_events or len(records) > len(schedule):
        _fail("native prefix exceeds original complete schedule")
    span, dirty, pending = program.span, set(), None
    for index, (kind, envelope_raw, payload_raw) in enumerate(records):
        step, expected_kind = schedule[index]
        if kind != expected_kind:
            _fail("native event is reordered, duplicated or outside its schedule")
        envelope = allowance.json_value(envelope_raw, "forest-replay-envelope")
        if (
            envelope
            != {
                "program_identity": program.identity.uri,
                "source_phase_identity": program.source_phase_identity,
                "payload_digest": hashlib.sha256(payload_raw).hexdigest(),
            }
            or canonical_json_bytes(envelope) != envelope_raw
        ):
            _fail("native event is not bound to this exact original program/payload")
        data = allowance.json_value(payload_raw, "forest-replay-payload")
        if type(data) is not dict or canonical_json_bytes(data) != payload_raw:
            _fail("canonical native payload required")
        _operation, value = steps[step]
        if kind == "forest-native-start":
            expected = {"program": program.document}
        elif kind == "forest-parking-intent":
            expected = {"path": str(program.private_root)}
        elif kind == "forest-parking-observed":
            if set(data) != {"path", "node"}:
                _fail("exact parking observation fields required")
            node = _recorded_node(data["node"])
            if not stat.S_ISDIR(node.mode) or stat.S_IMODE(node.mode) != 0o700:
                _fail("recorded private parking must be mode0700 directory")
            lineage = _parking_lineage(program, parking_parent_lineage, node)
            identity = node.device, node.inode
            if any(
                (old.device, old.inode) == identity
                for root in span.roots
                for _name, old in root.native
            ) or any(row[1:3] == identity for row in parking_parent_lineage):
                _fail("new parking directory aliases an original node or ancestor")
            span = replace(
                span,
                roots=(
                    *span.roots,
                    _SpanRoot(program.private_root, lineage, (("", node),), ()),
                ),
            )
            _shape(span)
            expected = {"path": str(program.private_root), "node": _wire(node)}
        elif kind == "forest-directory-intent":
            slot, _name, template = value
            expected = {"slot": slot, "template": _wire(template)}
        elif kind == "forest-directory-observed":
            slot, _name, template = value
            if set(data) != {"slot", "node"}:
                _fail("exact staged-directory observation fields required")
            node = _recorded_node(data["node"])
            if (
                not stat.S_ISDIR(node.mode)
                or stat.S_IMODE(node.mode) != 0o700
                or (node.device, node.uid, node.gid)
                != (template.device, template.uid, template.gid)
                or any(
                    (old.device, old.inode) == (node.device, node.inode)
                    for root in span.roots
                    for _, old in root.native
                )
            ):
                _fail(
                    "staged directory differs from its original template "
                    "or aliases an original node"
                )
            span = _with_node(span, 1, slot, node)
            # The original observed payload records the stage node, but not its
            # parent's new stamps. A later parent receipt can close these, or
            # fresh current recovery must reclassify that exact directory.
            dirty.add((1, ""))
            expected = {"slot": slot, "node": _wire(node)}
        elif kind == "forest-entry-intent":
            action = value
            if set(data) != {
                "action",
                "source",
                "destination",
                "node",
                "source_parent",
                "destination_parent",
            }:
                _fail("exact entry intent fields required")
            for area, name, key in (
                (action.source_area, _parent_name(action.source), "source_parent"),
                (
                    action.destination_area,
                    _parent_name(action.destination),
                    "destination_parent",
                ),
            ):
                span = _directory_receipt(span, dirty, area, name, data[key])
            expected = {
                "action": _wire(action),
                "source": str(span.roots[action.source_area].root / action.source),
                "destination": str(
                    span.roots[action.destination_area].root / action.destination
                ),
                "node": _wire(_source_node(span, action)),
                "source_parent": data["source_parent"],
                "destination_parent": data["destination_parent"],
            }
        elif kind == "forest-entry-observed":
            action = value
            if set(data) != {"action", "node", "source_parent", "destination_parent"}:
                _fail("exact entry observation fields required")
            node = _recorded_node(data["node"])
            before = _source_node(span, action)
            if node.after_rename() != before.after_rename():
                _fail("moved node differs from original predecessor")
            parents = []
            for area, name, key in (
                (action.source_area, _parent_name(action.source), "source_parent"),
                (
                    action.destination_area,
                    _parent_name(action.destination),
                    "destination_parent",
                ),
            ):
                parent = _recorded_node(data[key])
                if (
                    parent.directory_identity
                    != dict(span.roots[area].native)[name].directory_identity
                ):
                    _fail("observed movement changed parent identity")
                parents.append(parent)
            span = _advance_move(span, action, node, *parents)
            expected = {
                "action": _wire(action),
                "node": _wire(node),
                "source_parent": data["source_parent"],
                "destination_parent": data["destination_parent"],
            }
        elif kind == "forest-mode-intent":
            expected = {
                "path": str(span.roots[0].root / value.source),
                "before": _wire(dict(span.roots[0].native)[value.source]),
                "mode": next(
                    template.mode
                    for _slot, name, template in program.directories
                    if name == value.source
                ),
            }
        elif kind == "forest-mode-observed":
            if set(data) != {"path", "node"}:
                _fail("exact mode observation fields required")
            node = _recorded_node(data["node"])
            before = dict(span.roots[0].native)[value.source]
            mode = next(
                template.mode
                for _slot, name, template in program.directories
                if name == value.source
            )
            if (
                node.mode != mode
                or replace(node, mode=before.mode, changed_ns=before.changed_ns)
                != before
            ):
                _fail("mode receipt changes unrelated original native facts")
            span = _with_node(span, 0, value.source, node)
            expected = {
                "path": str(span.roots[0].root / value.source),
                "node": _wire(node),
            }
        else:
            expected = {"state": "source-moved-metadata-pending"}
        if data != expected:
            _fail("native payload contradicts its exact scheduled predecessor")
        pending = (kind, payload_raw) if kind.endswith("-intent") else None
    if canonical_json_bytes(program.document) != original:
        _fail("original native program changed during replay")
    return _RecordedFrontier(
        span, pending, tuple(sorted(dirty)), len(records), len(records) == len(schedule)
    )
