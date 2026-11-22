"""Typed original interruption evidence carried by real recovery intent.

These descriptions reconstruct a previously checked native frontier. They never
supply a new payload baseline or recreate an original role/effect participant.
"""

from __future__ import annotations

from dataclasses import replace

from .repository_refresh_reservations import _custody_wire
from .retained_layout_forest_native import (
    _advance_move,
    _native_event_schedule,
    _native_steps,
)
from .retained_layout_forest_program_read import _initial_node


def _fail(message):
    raise ValueError("layout.forest-recovery-witness: " + message)


def _pending(value, metadata):
    if metadata is not None and metadata.pending is not None:
        return metadata.pending.kind, metadata.pending.action
    pending = value.frontier.pending
    if pending is None:
        return None, None
    step = _native_event_schedule(value.program)[value.frontier.consumed - 1][0]
    return pending[0], _native_steps(value.program)[step][1]


def _parent(name):
    return name.rpartition("/")[0]


def original_recovery_witness(value, current):
    kind, action = _pending(value, current.metadata)
    node, parents = None, ()
    if kind in {
        "forest-entry-intent",
        "metadata-quarantine-intent",
        "metadata-publication-intent",
    }:
        area, name = (
            (action.destination_area, action.destination)
            if current.position == "pending-after"
            else (action.source_area, action.source)
        )
        node = dict(current.span.roots[area].native)[name]
        parents = tuple(
            dict(current.span.roots[area].native)[_parent(name)]
            for area, name in (
                (action.source_area, action.source),
                (action.destination_area, action.destination),
            )
        )
    elif kind == "forest-mode-intent":
        node = dict(current.span.roots[0].native)[action.source]
    return {
        "schema": "literate-ai/forest-original-interruption@1",
        "native_consumed": value.frontier.consumed,
        "position": current.position,
        "kind": kind,
        "node": None if node is None else _custody_wire(node),
        "parents": [_custody_wire(p) for p in parents],
    }


def apply_original_recovery_witness(value, metadata, span, witness):
    """Validate against original receipts before projecting any recovery moves."""
    kind, action = _pending(value, metadata)
    if (
        type(witness) is not dict
        or set(witness)
        != {"schema", "native_consumed", "position", "kind", "node", "parents"}
        or witness["schema"] != "literate-ai/forest-original-interruption@1"
        or type(witness["native_consumed"]) is not int
        or witness["native_consumed"] != value.frontier.consumed
        or witness["kind"] != kind
        or type(witness["parents"]) is not list
    ):
        _fail("exact original interrupted frontier required")
    position = witness["position"]
    if kind is None:
        if position != "recorded" or witness["node"] is not None or witness["parents"]:
            _fail("recorded original cannot acquire a pending effect")
        return span
    if position not in {"pending-before", "pending-after"}:
        _fail("known original pending classification required")
    if kind in {"forest-parking-intent", "forest-directory-intent"}:
        if (
            position != "pending-before"
            or witness["node"] is not None
            or witness["parents"]
        ):
            _fail("unrecorded creation has no durable native ownership witness")
        return span
    node = _initial_node(witness["node"])
    if kind == "forest-mode-intent":
        before = dict(span.roots[0].native)[action.source]
        mode = next(
            t.mode for _s, name, t in value.program.directories if name == action.source
        )
        expected_mode = before.mode if position == "pending-before" else mode
        if (
            witness["parents"]
            or node.mode != expected_mode
            or replace(node, mode=before.mode, changed_ns=before.changed_ns) != before
            or (position == "pending-before" and node != before)
        ):
            _fail("mode witness changes unrelated original native facts")
        roots = list(span.roots)
        native = dict(roots[0].native)
        native[action.source] = node
        roots[0] = replace(roots[0], native=tuple(sorted(native.items())))
        return replace(span, roots=tuple(roots))
    if kind not in {
        "forest-entry-intent",
        "metadata-quarantine-intent",
        "metadata-publication-intent",
    }:
        _fail("unsupported original pending witness")
    before = dict(span.roots[action.source_area].native)[action.source]
    if node.after_rename() != before.after_rename() or len(witness["parents"]) != 2:
        _fail("pending move changes original native child custody")
    parents = tuple(_initial_node(p) for p in witness["parents"])
    for (area, name), parent in zip(
        (
            (action.source_area, action.source),
            (action.destination_area, action.destination),
        ),
        parents,
        strict=True,
    ):
        if (
            parent.directory_identity
            != dict(span.roots[area].native)[_parent(name)].directory_identity
        ):
            _fail("pending move changes original native parent custody")
    if position == "pending-before":
        if node != before:
            _fail("pending-before changes original native child")
        return span
    return _advance_move(span, action, node, *parents)
