"""Actual fresh native closure after a strictly decoded recovery suffix.

Original receipts and a bound pending witness determine the source roster;
recovery entries can only move those known nodes. All current canonical rights
come from independently reacquired descriptors, never from these descriptions.
"""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack
from dataclasses import replace

from literate_ai.contracts.identity import canonical_json_bytes

from .repository_refresh_reservations import _custody_wire
from .retained_layout_forest_control_inventory import (
    close_control_inventory,
    control_inventory,
    require_control_inputs,
)
from .retained_layout_forest_metadata_replay import _apart, _pin
from .retained_layout_forest_native import _advance_move
from .retained_layout_forest_observation import _record
from .retained_layout_forest_program_read import _initial_node
from .retained_layout_forest_recovery_witness import apply_original_recovery_witness
from .retained_layout_forest_span import _require_current, _SpanRoot
from .retained_layout_journal import _LIVE_ROOTS


def _fail(message):
    raise ValueError("layout.forest-recovery-current: " + message)


def _parent(name):
    return name.rpartition("/")[0]


def observe_recovered_forest(observer, roles):
    from .retained_layout_forest_control_projection import project_current_controls
    from .retained_layout_forest_current import (
        _CurrentNativeForest,
        _EndpointReads,
        _fund,
        _join_future_roots,
        _with_node,
    )
    from .retained_layout_forest_current import (
        _parent as actual_parent,
    )
    from .retained_layout_forest_metadata_replay import load_forest_metadata_frontier
    from .retained_layout_forest_recovery import (
        _committed,
        _inverse_actions,
        _portable_beneath,
    )

    value = _record(observer, reading=True)
    binding = control_inventory(value, roles)
    tail = value.frontier.recovery
    if not tail.segments or tail.canonical_pending in {"raw", "roles"}:
        _fail("complete canonical acquisition and recorded recovery attempts required")
    segment = tail.segments[0]
    header = segment.header
    metadata = load_forest_metadata_frontier(observer)
    baseline = value.frontier.span if metadata is None else metadata.span
    baseline = apply_original_recovery_witness(
        value, metadata, baseline, header["original_frontier"]
    )
    future = () if metadata is None else metadata.future_roots
    private, node, lineage = _pin(
        [header["private_root"], header["private_node"], header["private_lineage"]]
    )
    if node.uid != os.geteuid():
        _fail("recorded recovery quarantine must remain owned by this user")
    if _portable_beneath(private, value.program.private_root) or _portable_beneath(
        value.program.private_root, private
    ):
        _fail("recovery quarantine overlaps original parking domain")
    for root in _join_future_roots(baseline, future).roots:
        if _portable_beneath(private, root.root) or _portable_beneath(
            root.root, private
        ):
            _fail("recovery quarantine overlaps an original portable coordinate")
        _apart(private, lineage, root.root, root.lineage)
    for root in (value.pool.root, _LIVE_ROOTS[value.journal]):
        if _portable_beneath(private, root) or _portable_beneath(root, private):
            _fail("recovery quarantine overlaps an actual producer coordinate")
        _apart(private, lineage, root, value.reader._lineages[root])
    storage = value.selection.path.parent
    anchor, storage_lineage = value.ledger.ancestry[value.selection.path]
    if (
        private.is_relative_to(storage)
        or storage.is_relative_to(private)
        or lineage[-1][1:3] in {r[1:3] for r in storage_lineage}
        or (anchor == storage and storage_lineage[-1][1:3] in {r[1:3] for r in lineage})
    ):
        _fail("recovery quarantine overlaps actual selected canonical storage")
    quarantine = _SpanRoot(private, lineage, (("", node),), ())
    initial = replace(
        _join_future_roots(baseline, future),
        roots=(*_join_future_roots(baseline, future).roots, quarantine),
    )
    policy = _fund(value, initial)
    journal, ledger = value.journal, value.ledger
    ledger.charge_records(2 * len(journal._known) + 2 * len(journal._events))
    roster, events = tuple(journal._known.items()), tuple(journal._events)

    def close_originals():
        close_control_inventory(value, roles, binding)
        if (
            _record(observer, reading=True) is not value
            or tuple(journal._events) != events
            or len(journal._known) != len(roster)
            or any(journal._known.get(n) is not r for n, r in roster)
        ):
            _fail("original fresh recovery reader, roles or journal changed")

    require_control_inputs(value, roles, binding, initial=True)
    close_originals()
    stack = ExitStack()
    try:
        access = _EndpointReads(stack, value, metadata)
        access.add(private, lineage)
        span, control_dirty = project_current_controls(
            value, roles, baseline, metadata, access
        )
        # New disposition areas follow the original quarantine. Original inverse
        # action indices must not shift when later private control roots appear.
        original_roots = {r.root for r in baseline.roots} | {r.root for r in future}
        extra = tuple(r for r in span.roots if r.root not in original_roots)
        retained = replace(
            span, roots=tuple(r for r in span.roots if r.root in original_roots)
        )
        retained = _join_future_roots(retained, future)
        for root in extra:
            _apart(private, lineage, root.root, root.lineage)
        span = replace(retained, roots=(*retained.roots, quarantine, *extra))
        quarantine_area = len(retained.roots)
        original = _CurrentNativeForest(
            span,
            header["original_position"],
            None,
            value.frontier.complete,
            (),
            (),
            metadata,
        )
        committed = _committed(value, original)
        actions = (
            () if committed else _inverse_actions(value, original, quarantine_area)
        )
        if (
            committed != header["committed"]
            or [_custody_wire(a) for a in actions] != header["actions"]
        ):
            _fail("recovery action programme differs from exact original inverse")
        dirty = set(
            value.frontier.refresh_directories
            if metadata is None
            else metadata.refresh_directories
        ) | set(control_dirty)
        endpoints, issues = [], ()
        position, pending_kind = "recovery-recorded", None

        def observe(path):
            actual = access.read(path)
            endpoints.append((path, actual))
            return actual

        if len(value.frontier.span.roots) == 1:
            if observe(value.program.private_root) is not None:
                _fail("unrecorded original parking creation remains unresolved")
        from .retained_layout_forest_recovery_witness import _pending

        original_kind, original_action = _pending(value, metadata)
        if original_kind == "forest-directory-intent":
            if observe(value.program.private_root / original_action[0]) is not None:
                _fail("unrecorded original staged creation remains unresolved")
        if metadata is not None:
            for path in metadata.unrecorded_stages:
                if observe(path) is not None:
                    _fail("unrecorded original metadata stage remains unresolved")

        def intent(data):
            nonlocal span
            index = data["ordinal"]
            action = actions[index]
            sr, dr = span.roots[action.source_area], span.roots[action.destination_area]
            before = dict(sr.native).get(action.source)
            if (
                before is None
                or action.destination in dict(dr.native)
                or data["source"] != str(sr.root / action.source)
                or data["destination"] != str(dr.root / action.destination)
                or _initial_node(data["node"]) != before
            ):
                _fail("recovery intent changes original known child or endpoint")
            for area, name, key in (
                (action.source_area, action.source, "source_parent"),
                (action.destination_area, action.destination, "destination_parent"),
            ):
                coordinate = (area, _parent(name))
                old = dict(span.roots[area].native).get(coordinate[1])
                parent = _initial_node(data[key])
                if (
                    old is None
                    or old.directory_identity != parent.directory_identity
                    or (coordinate not in dirty and old != parent)
                ):
                    _fail("recovery intent changes an unowned native parent")
                span = _with_node(span, area, coordinate[1], parent)
                dirty.discard(coordinate)
            return action, before

        from .retained_layout_forest_recovery_resume import apply_resume_witness
        from .retained_layout_forest_recovery_transcript import _same

        full_actions, cursor, previous = actions, 0, None
        for segment in tail.segments:
            if previous is not None:
                span, skipped = apply_resume_witness(
                    span, previous, segment.header["resume"]
                )
                cursor += skipped
                if (
                    _initial_node(segment.header["private_node"])
                    != dict(span.roots[quarantine_area].native)[""]
                ):
                    _fail("resume changes the known quarantine native root")
            actions = full_actions[cursor:]
            if not _same(
                [_custody_wire(a) for a in actions], segment.header["actions"]
            ):
                _fail("resume differs from exact remaining original inverse actions")
            for data in segment.entries:
                action, _before = intent(data)
                parents = tuple(
                    _initial_node(data[k])
                    for k in ("source_parent_after", "destination_parent_after")
                )
                span = _advance_move(
                    span, action, _initial_node(data["observed_node"]), *parents
                )
                cursor += 1
            if segment.pending is not None and segment is not tail.segments[-1]:
                intent(segment.pending)
            previous = segment
        if segment.pending is not None:
            data = segment.pending
            action, before = intent(data)
            sr, dr = span.roots[action.source_area], span.roots[action.destination_area]
            source, destination = sr.root / action.source, dr.root / action.destination
            sn, dn = observe(source), observe(destination)
            pending_kind = "forest-data-recovery-entry-intent"
            if (
                sn == replace(before, native_identity=None, link_target=None)
                and dn is None
            ):
                position = "recovery-pending-before"
            elif sn is None and dn is not None:
                carried = replace(
                    dn,
                    native_identity=before.native_identity,
                    link_target=before.link_target,
                )
                if carried.after_rename() != before.after_rename():
                    issues = (
                        "pending recovery target differs from original native custody",
                    )
                else:
                    parents = tuple(
                        actual_parent(span, area, name, observe)
                        for area, name in (
                            (action.source_area, action.source),
                            (action.destination_area, action.destination),
                        )
                    )
                    span = _advance_move(span, action, carried, *parents)
                    position = "recovery-pending-after"
            else:
                issues = ("pending recovery endpoints are ambiguous",)
        # Recognized parent stamps may refresh, while complete membership and
        # independent known-payload hashing still close every represented root.
        for area, name in sorted(dirty):
            root = span.roots[area]
            old = dict(root.native)[name]
            actual = observe(root.root / name)
            if actual is None or actual.directory_identity != old.directory_identity:
                _fail("recorded dirty recovery parent lost its native identity")
            span = _with_node(span, area, name, actual)
        policy = _fund(value, span)
        sealed = canonical_json_bytes(_custody_wire((span, metadata)))

        def close_projected():
            close_originals()
            if canonical_json_bytes(_custody_wire((span, metadata))) != sealed:
                _fail("derived recovery view changed during closing")

        def close_dependencies():
            require_control_inputs(value, roles, binding)
            close_projected()
            value.selection.require_current()
            close_projected()
            value.reader.require_current()
            close_projected()

        if issues:
            close_dependencies()
        else:
            _require_current(
                replace(span, budget=policy), _after_payload=close_dependencies
            )
        for path, expected in endpoints:
            if access.read(path) != expected:
                _fail("current recovery endpoint changed during closing")
        stack.close()
        close_projected()
        return _CurrentNativeForest(
            None if issues else span,
            "unresolved" if issues else position,
            pending_kind,
            segment.complete,
            tuple(sorted(dirty)),
            issues,
            metadata,
        )
    finally:
        stack.__exit__(*sys.exc_info())
