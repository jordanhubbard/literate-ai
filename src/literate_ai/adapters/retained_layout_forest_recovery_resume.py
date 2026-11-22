"""Typed predecessor progress for actual fresh recovery retry plans.

A witness bridges an unobserved inverse effect using original native identity;
it never admits a new source payload or a new quarantine membership baseline.
"""

from __future__ import annotations

from .repository_refresh_reservations import _custody_wire
from .retained_layout_forest_native import _Action, _advance_move
from .retained_layout_forest_program_read import _initial_node


def _fail(message):
    raise ValueError("layout.forest-recovery-resume: " + message)


def _parent(name):
    return name.rpartition("/")[0]


def validate_resume_description(resume, previous):
    if type(resume) is not dict or set(resume) != {
        "schema",
        "predecessor",
        "consumed",
        "position",
        "node",
        "parents",
    }:
        _fail("exact typed predecessor progress required")
    if (
        resume["schema"] != "literate-ai/forest-recovery-resume@1"
        or resume["predecessor"] != previous.header["recovery_identity"]
        or type(resume["consumed"]) is not int
        or resume["consumed"] != len(previous.entries)
        or type(resume["parents"]) is not list
    ):
        _fail("resume must bind the exact preceding recovery prefix")
    pending = previous.pending
    if pending is None:
        if (
            resume["position"] != "recovery-recorded"
            or resume["node"] is not None
            or resume["parents"]
        ):
            _fail("recorded predecessor cannot acquire an unobserved move")
        return
    if (
        resume["position"] not in {"recovery-pending-before", "recovery-pending-after"}
        or len(resume["parents"]) != 2
    ):
        _fail("exact known pending predecessor classification required")
    node = _initial_node(resume["node"])
    before = _initial_node(pending["node"])
    if node.after_rename() != before.after_rename():
        _fail("resume substitutes the original pending native child")
    if resume["position"] == "recovery-pending-before" and node != before:
        _fail("pending-before changes original native child facts")
    for row, key in zip(
        resume["parents"], ("source_parent", "destination_parent"), strict=True
    ):
        if (
            _initial_node(row).directory_identity
            != _initial_node(pending[key]).directory_identity
        ):
            _fail("resume substitutes an original pending native parent")


def original_resume_witness(value, current):
    previous = value.frontier.recovery.segments[-1]
    node, parents = None, ()
    if previous.pending is not None:
        action = _Action(**previous.pending["action"])
        area, name = (
            (action.destination_area, action.destination)
            if current.position == "recovery-pending-after"
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
    witness = {
        "schema": "literate-ai/forest-recovery-resume@1",
        "predecessor": previous.header["recovery_identity"],
        "consumed": len(previous.entries),
        "position": current.position,
        "node": None if node is None else _custody_wire(node),
        "parents": [_custody_wire(p) for p in parents],
    }
    validate_resume_description(witness, previous)
    return witness


def apply_resume_witness(span, previous, witness):
    validate_resume_description(witness, previous)
    if previous.pending is None:
        return span, 0
    action = _Action(**previous.pending["action"])
    source = span.roots[action.source_area]
    before = dict(source.native).get(action.source)
    if before is None or _initial_node(previous.pending["node"]) != before:
        _fail("predecessor pending child differs from the original derived roster")
    node = _initial_node(witness["node"])
    parents = tuple(_initial_node(p) for p in witness["parents"])
    for (area, name), parent in zip(
        (
            (action.source_area, action.source),
            (action.destination_area, action.destination),
        ),
        parents,
        strict=True,
    ):
        known = dict(span.roots[area].native)[_parent(name)]
        if known.directory_identity != parent.directory_identity:
            _fail("predecessor pending parent differs from original derived roster")
        if witness["position"] == "recovery-pending-before" and parent != known:
            _fail("pending-before cannot refresh an unmodified native parent")
    if witness["position"] == "recovery-pending-before":
        return span, 0
    return _advance_move(span, action, node, *parents), 1


def remaining_recovery_actions(value, current):
    previous = value.frontier.recovery.segments[-1]
    witness = original_resume_witness(value, current)
    consumed = len(previous.entries)
    if previous.pending is not None and current.position == "recovery-pending-after":
        consumed += 1
    return tuple(_Action(**a) for a in previous.header["actions"][consumed:]), witness
