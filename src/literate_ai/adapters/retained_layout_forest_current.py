"""Bounded current native-prefix observations under actual fresh canonical roles.

A result describes current source/parking endpoints, never effect authority.
Unknown unobserved creations remain unresolved. Metadata/control publication
projection is descriptive; the acknowledged recovery executor is a separate join.
"""

from __future__ import annotations

import os
import sys
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from .exclusive_entry import _from_stat
from .repository_refresh_reservations import _custody_wire
from .retained_layout_forest_native import (
    _advance_move,
    _native_event_schedule,
    _native_steps,
    _rows,
)
from .retained_layout_forest_observation import _record
from .retained_layout_forest_span import _NATIVE_PAYLOAD_CHUNK, _require_current
from .retained_layout_recovery_roles import _CREATED_ROLES, _RecoveryRoleLease
from .retained_project_inputs import _directory_access


def _fail(message):
    raise ValueError("layout.forest-current: " + message)


@dataclass(frozen=True, slots=True)
class _CurrentNativeForest:
    span: object
    position: str
    pending_kind: str | None
    journal_complete: bool
    refreshed_directories: tuple
    issues: tuple = ()
    metadata: object = None


class _EndpointReads:
    """Retain original-root no-follow handles even for preliminary probes."""

    def __init__(self, stack, value, metadata=None):
        project = value.program.span.roots[0]
        parent = value.program.private_root.parent
        self.stack = stack
        self.accesses = []
        participants = [
            (project.root, project.lineage),
            (parent, value.reader._lineages[parent]),
        ]
        if metadata is not None:
            participants.append((metadata.metadata_root, metadata.metadata_lineage))
            participants.extend(
                (root.root, root.lineage)
                for root in metadata.future_roots
                if root.root != metadata.metadata_root
            )
        for root, lineage in participants:
            self.add(root, lineage)

    def add(self, root, lineage):
        access = self.stack.enter_context(_directory_access(root))
        if access is None:
            _fail("retained no-follow endpoint access is unavailable")
        if len(access._absolute) != len(lineage) or any(
            actual != row[1:]
            for (_name, _fd, actual), row in zip(access._absolute, lineage, strict=True)
        ):
            _fail("endpoint root differs from original observed ancestry")
        self.accesses.append(access)
        self.accesses.sort(key=lambda item: len(item.root.parts), reverse=True)

    def read(self, path):
        access = next(
            (a for a in self.accesses if path == a.root or path.is_relative_to(a.root)),
            None,
        )
        if access is None:
            _fail("native endpoint escaped its actual original roots")
        try:
            if path == access.root:
                access._root_current()
                node = os.fstat(access._absolute[-1][1])
                access._root_current()
            else:
                node = access.metadata(path)
            return _from_stat(node)
        except FileNotFoundError:
            return None


def _with_node(span, area, name, node):
    roots = list(span.roots)
    native = dict(roots[area].native)
    native[name] = node
    roots[area] = replace(roots[area], native=_rows(native))
    return replace(span, roots=tuple(roots))


def _parent(span, area, name, observe):
    parent = Path(name).parent.as_posix()
    parent = "" if parent == "." else parent
    root = span.roots[area]
    before = dict(root.native)[parent]
    actual = observe(root.root / parent)
    if actual is None or actual.directory_identity != before.directory_identity:
        _fail("actual pending parent differs from its recorded native identity")
    return actual


def _fund(value, span=None):
    ledger = value.ledger
    span = value.frontier.span if span is None else span
    count = sum(len(root.native) for root in span.roots)
    # The original saved/program structures are already bounded and sealed by
    # this actual observer. Charge the simultaneous candidate/maps first.
    paths = sum(
        len(str(root.root / name).encode())
        for root in span.roots
        for name, _ in root.native
    )
    ledger.charge_records(128 + 32 * count, 65536 + 8192 * count + 128 * paths)
    groups, sizes = set(), []
    for root in span.roots:
        nodes = dict(root.native)
        for name, blob, _executable in root.payloads:
            identity = nodes[name].device, nodes[name].inode
            if identity not in groups:
                groups.add(identity)
                sizes.append(blob.size)
        sizes.extend(len(text.encode()) for _name, text in root.links)
    maximum, total = max((1, *sizes)), max(1, sum(sizes))
    if (
        maximum > min(span.budget.maximum_file_bytes, ledger.budget.maximum_file_bytes)
        or len(sizes) > span.budget.maximum_files
    ):
        _fail("known native payload exceeds original or fresh file policy")
    ledger.files += len(sizes)
    ledger.bytes += sum(sizes)
    # The verifier hashes complete regular files through the fixed-size native
    # payload stream. Four chunks cover simultaneous old/new data, buffered IO
    # and digest scratch; symbolic text is separately bounded to 4096 bytes.
    # File-count and cumulative payload-byte charges above remain unchanged.
    ledger.charge_records(2 * len(sizes), 4 * min(maximum, _NATIVE_PAYLOAD_CHUNK))
    # Inventory scratch and streaming ceilings follow this exact known roster,
    # not all unused capacity in a larger original policy.
    policy = RetainedCargoInputBudget(max(1, len(sizes)), count, maximum, total)
    if total > span.budget.maximum_total_bytes:
        _fail("known native payload exceeds original aggregate policy")
    return policy


def _join_future_roots(span, future_roots):
    """Keep unused reservations without replacing actual projected contents."""
    represented = {root.root for root in span.roots}
    missing = tuple(root for root in future_roots if root.root not in represented)
    return replace(span, roots=(*span.roots, *missing)) if missing else span


def observe_current_native_forest(observer, roles):
    """Observe inside the creating reader activation; return no reusable grant."""
    value = _record(observer, reading=True)
    if type(roles) is not _RecoveryRoleLease:
        _fail("actual same-observer canonical recovery role lease required")
    roles._require_created()
    if roles._pool is not value.pool or roles._seed.root != value.root:
        _fail("actual same-observer canonical recovery role lease required")
    binding = _CREATED_ROLES[roles]
    from .retained_layout_forest_metadata_replay import load_forest_metadata_frontier

    if value.frontier.recovery is not None and value.frontier.recovery.segments:
        from .retained_layout_forest_recovery_current import observe_recovered_forest

        return observe_recovered_forest(observer, roles)
    metadata = load_forest_metadata_frontier(observer)
    # Fund the known initial complete view before opening any current source
    # endpoint; projected controls receive their own same-ledger prepayment.
    future_roots = () if metadata is None else metadata.future_roots
    initial = value.frontier.span if metadata is None else metadata.span
    policy = _fund(
        value,
        _join_future_roots(initial, future_roots),
    )
    ledger, journal = value.ledger, value.journal
    ledger.charge_records(2 * len(journal._known) + 2 * len(journal._events))
    roster, events = tuple(journal._known.items()), tuple(journal._events)

    def close_originals():
        roles._require_created()
        if (
            _CREATED_ROLES.get(roles) is not binding
            or _record(observer, reading=True) is not value
            or tuple(journal._events) != events
            or len(journal._known) != len(roster)
            or any(journal._known.get(name) is not row for name, row in roster)
        ):
            _fail("original current-observation role, reader or journal changed")

    roles.require_initial_inputs()
    close_originals()
    stack = ExitStack()
    try:
        access = _EndpointReads(stack, value, metadata)
        frontier, program = value.frontier, value.program
        span = frontier.span if metadata is None else metadata.span
        position, issues = "recorded", ()
        pending = None if frontier.pending is None else frontier.pending[0]
        if metadata is not None and metadata.pending is not None:
            pending = metadata.pending.kind
        endpoints = []

        def observe(path):
            node = access.read(path)
            endpoints.append((path, node))
            return node

        if len(span.roots) == 1:
            parking = observe(program.private_root)
            if parking is not None:
                issues = ("unrecorded parking creation has no durable native witness",)
            elif pending == "forest-parking-intent":
                position = "pending-before"
        if metadata is not None:
            for path in metadata.unrecorded_stages:
                if observe(path) is not None:
                    issues = (
                        "unrecorded metadata stage has no durable native witness",
                    )
        if not issues and pending is not None:
            if metadata is not None and metadata.pending is not None:
                action = metadata.pending.action
            else:
                step = _native_event_schedule(program)[frontier.consumed - 1][0]
                _operation, action = _native_steps(program)[step]
            if pending == "forest-directory-intent":
                slot, _name, _template = action
                staged = observe(program.private_root / slot)
                if staged is None:
                    position = "pending-before"
                else:
                    issues = (
                        "unrecorded staged creation has no durable native witness",
                    )
            elif pending in {
                "forest-entry-intent",
                "metadata-quarantine-intent",
                "metadata-publication-intent",
            }:
                source = span.roots[action.source_area]
                target = span.roots[action.destination_area]
                before = dict(source.native)[action.source]
                actual_source = observe(source.root / action.source)
                actual_target = observe(target.root / action.destination)
                if (
                    actual_source
                    == replace(before, native_identity=None, link_target=None)
                    and actual_target is None
                ):
                    position = "pending-before"
                elif actual_source is None and actual_target is not None:
                    carried = replace(
                        actual_target,
                        native_identity=before.native_identity,
                        link_target=before.link_target,
                    )
                    if carried.after_rename() == before.after_rename():
                        span = _advance_move(
                            span,
                            action,
                            carried,
                            _parent(span, action.source_area, action.source, observe),
                            _parent(
                                span,
                                action.destination_area,
                                action.destination,
                                observe,
                            ),
                        )
                        position = "pending-after"
                    else:
                        issues = (
                            "pending target differs from the original native node",
                        )
                else:
                    issues = ("pending entry endpoints are ambiguous or foreign",)
            elif pending == "forest-mode-intent":
                root = span.roots[0]
                before = dict(root.native)[action.source]
                actual = observe(root.root / action.source)
                mode = next(
                    t.mode
                    for _slot, name, t in program.directories
                    if name == action.source
                )
                if actual == before:
                    position = "pending-before"
                elif (
                    actual is not None
                    and actual.mode == mode
                    and replace(actual, mode=before.mode, changed_ns=before.changed_ns)
                    == before
                ):
                    span = _with_node(span, 0, action.source, actual)
                    position = "pending-after"
                else:
                    issues = ("pending mode differs from the intended directory",)
        refresh = (
            frontier.refresh_directories
            if metadata is None
            else metadata.refresh_directories
        )
        control_refresh = ()
        if not issues:
            from .retained_layout_forest_control_projection import (
                project_current_controls,
            )

            previous = span
            span, control_refresh = project_current_controls(
                value, roles, span, metadata, access
            )
            if span is not previous:
                funded = _join_future_roots(span, future_roots)
                policy = _fund(value, funded)
        span = _join_future_roots(span, future_roots)
        if not issues:
            refresh = tuple(sorted(set(refresh) | set(control_refresh)))
            for area, name in refresh:
                root = span.roots[area]
                before = dict(root.native)[name]
                actual = observe(root.root / name)
                if (
                    actual is None
                    or actual.directory_identity != before.directory_identity
                ):
                    _fail("observed stage parent lost its original native identity")
                span = _with_node(span, area, name, actual)

        projected = canonical_json_bytes(_custody_wire((span, metadata)))

        def close_projected():
            close_originals()
            if canonical_json_bytes(_custody_wire((span, metadata))) != projected:
                _fail("original derived metadata/native projection changed")

        def close_dependencies():
            roles.require_current()
            close_projected()
            value.selection.require_current()
            close_projected()
            value.reader.require_current()
            close_projected()

        if issues:
            close_dependencies()
        else:
            checker = replace(span, budget=policy)
            _require_current(checker, _after_payload=close_dependencies)
        for path, expected in endpoints:
            if access.read(path) != expected:
                _fail("current pending native endpoint changed during closing")
        stack.close()
        close_projected()
        return _CurrentNativeForest(
            None if issues else span,
            "unresolved" if issues else position,
            pending,
            frontier.complete,
            refresh,
            issues,
            metadata,
        )
    finally:
        # A failed/revoked body must close descriptors without resuming access
        # contexts as successful exits and borrowing FDs for currentness checks.
        stack.__exit__(*sys.exc_info())
