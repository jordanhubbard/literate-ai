"""Finalize actual catalog controls without manufacturing a source transaction."""

from __future__ import annotations

import os
from dataclasses import dataclass

from literate_ai.contracts.identity import canonical_json_bytes

from . import retained_layout_journal as journals
from .exclusive_entry import _from_stat
from .retained_layout_control_roles import (
    _require_acquired_control_roles,
    _require_control_registration,
    layout_pending_control_path,
)


def _fail(message):
    raise ValueError("catalog.control-finalization: " + message)


@dataclass(frozen=True, slots=True)
class _Marker:
    marker: object
    target: object
    descriptor: int
    created: bool
    node: object
    content: bytes


@dataclass(frozen=True, slots=True)
class _Finalization:
    roles: tuple
    journal_admission: tuple
    markers: tuple
    events: int
    storage: int
    directory: str = "retired-controls"


def prepare_finalization(stages, controls):
    roles = _require_acquired_control_roles(controls, stages.plan.root)
    markers, journal = controls.reservations._markers, controls._pool._journal
    ledger = stages._ledger
    ledger.charge_records(
        8 * len(markers),
        sum(
            16 * len(str(m.target.path).encode()) + 4 * len(m.content) for m in markers
        ),
    )
    originals = tuple(
        _Marker(
            m,
            m.target,
            m.descriptor,
            m.created,
            controls.reservations._expected[m.target.path],
            m.content,
        )
        for m in markers
    )
    pending = layout_pending_control_path(stages.plan.root)
    if sum(m.target.path == pending and not m.target.advisory for m in originals) != 1:
        _fail("exact original pending barrier required")
    # The reservation writer emits one complete original roster on handoff and
    # bounded intent/completion records for each actual marker operation.
    roster = 4096 + sum(2048 + 12 * len(str(m.target.path).encode()) for m in originals)
    per_action = 16384 + 32 * max(
        len(str(m.target.path).encode()) + len(str(stages.root).encode())
        for m in originals
    )
    if max(roster, per_action) + 4096 > journals._RECORD_LIMIT:
        _fail("complete control intent exceeds original record policy")
    actions = sum(not m.target.advisory or m.created for m in originals)
    events = 2 * actions + 4
    storage = 2 * roster + (events + 2 * actions) * per_action
    if (
        len(journal._events) + events > journal._budget.maximum_events
        or sum(len(raw) for _node, raw in journal._known.values()) + storage
        > journal._budget.maximum_storage_bytes
    ):
        _fail("control finalization exceeds original journal allowance")
    return _Finalization(
        roles, journals._LIVE_WRITERS[journal], originals, events, storage
    )


def require_controls(owner, record):
    """Admit normal roles or this actual receiver's one-way finalizing span."""
    controls, ticket, progress = owner._controls, record[10], record[11]
    if _require_control_registration(controls, owner._project.root) is not ticket.roles:
        _fail("creating control acquisition changed")
    if controls._finalizing != progress["started"]:
        _fail("control finalization did not pass through actual catalog owner")
    journals._close_live_journal_admission(
        controls._pool._journal, ticket.journal_admission
    )
    markers = controls.reservations._markers
    if len(markers) != len(ticket.markers):
        _fail("creating marker roster changed")
    for actual, original in zip(markers, ticket.markers, strict=True):
        path = original.target.path
        if (
            actual is not original.marker
            or actual.target is not original.target
            or actual.descriptor != original.descriptor
            or actual.created != original.created
            or actual.content != progress["contents"][path]
            or controls.reservations._expected[path] != progress["nodes"][path]
        ):
            _fail("creating marker facts differ from exact known effects")
    if controls.reservations._locations != progress["locations"]:
        _fail("control retirement differs from exact known locations")


def require_initial_inputs(owner):
    from .catalog_entry_publication import _OWNERS

    record = _OWNERS[owner._stages]
    if not record[11]["started"]:
        owner._controls.require_initial_inputs()
        return
    require_controls(owner, record)
    controls = owner._controls
    controls.reservations.verify_all()
    current = controls._seed.require_initial_inputs()
    controls.git.require_unchanged(controls.reservations)
    controls.reservations.verify_all()
    controls.git.close_native_inputs(controls.reservations)
    current.close_native_inputs()


def _sync_journal(owner):
    from .catalog_entry_publication import _OWNERS, _digest

    journal = owner._controls._pool._journal
    journals._close_live_journal_admission(
        journal, _OWNERS[owner._stages][10].journal_admission
    )
    state = owner._control_views[1]
    for name, (stamp, raw) in journal._known.items():
        path = state.root / name
        if journals._file(path.lstat()) != stamp:
            _fail("actual control journal result changed")
        observed = _from_stat(path.lstat())
        if name in state.nodes and (
            state.nodes[name] != observed or state.files.get(name) != _digest(raw)
        ):
            _fail("old control journal record changed")
        state.nodes[name], state.files[name] = observed, _digest(raw)
    owner._advance_parent(state, "")


def _advance_marker(owner, original, node, content, destination=None):
    from .catalog_entry_publication import _OWNERS, _digest

    record = _OWNERS[owner._stages]
    progress, controls = record[11], owner._controls
    path = original.target.path
    before = progress["nodes"][path]
    actual_path = path if destination is None else destination
    if (
        _from_stat(os.fstat(original.descriptor)) != node
        or _from_stat(actual_path.lstat()) != node
    ):
        _fail("actual marker result changed")
    if (node.device, node.inode, node.mode, node.uid, node.gid, node.links) != (
        before.device,
        before.inode,
        before.mode,
        before.uid,
        before.gid,
        before.links,
    ):
        _fail("marker result lost original native identity")
    if os.pread(original.descriptor, len(content) + 1, 0) != content:
        _fail("actual marker result bytes changed")
    if destination is None:
        if not original.target.advisory or not original.created or content != b"\0":
            _fail("only original newly created advisory may normalize")
    elif (
        controls.reservations._locations.get(path) != destination
        or content != original.content
        or node.after_rename() != before.after_rename()
    ):
        _fail("native retirement differs from original marker")
    if path.is_relative_to(owner._project.root):
        name = path.relative_to(owner._project.root).as_posix()
        if owner._project.nodes.get(name) != before:
            _fail("project marker differs from previous known node")
        if destination is None:
            owner._project.nodes[name], owner._project.files[name] = (
                node,
                _digest(content),
            )
        else:
            del owner._project.nodes[name]
            del owner._project.files[name]
            owner._advance_parent(owner._project, owner._parent(owner._project, name))
    if destination is not None:
        name = destination.relative_to(owner._private.root).as_posix()
        if name in owner._private.nodes:
            _fail("retired control destination was already occupied")
        owner._private.nodes[name], owner._private.files[name] = node, _digest(content)
        owner._advance_parent(owner._private, record[10].directory)
        progress["locations"][path] = destination
    progress["nodes"][path], progress["contents"][path] = node, content


def finalize_controls(owner, acknowledged_plan_identity):
    from .catalog_entry_publication import _BUSY, _FAILED, _WRITERS

    record = owner._live()
    if owner not in _WRITERS:
        _fail("catalog control writer ended")
    if owner in _BUSY:
        _FAILED.add(owner)
        _fail("reentrant catalog control effects refused")
    if acknowledged_plan_identity != owner._stages.plan.identity:
        _fail("exact original catalog plan acknowledgement required")
    if record[9]["phase"] != "published":
        _fail("actual published provenance required before control finalization")
    ticket, progress, controls = record[10], record[11], owner._controls
    if progress["started"]:
        _fail("catalog control finalization is single-use")
    _BUSY.add(owner)
    try:
        owner.require_current()
        owner._journal(
            "catalog-controls-intent",
            {
                "plan": owner._stages.plan.identity.uri,
                "retirement": ticket.directory,
                "qualified": False,
            },
        )
        owner._mkdir(ticket.directory, mode=0o700)
        root = owner._private.root / ticket.directory
        controls.begin_finalization(root)
        progress["started"] = True
        _sync_journal(owner)
        owner.require_current()
        for original in ticket.markers:
            if original.target.advisory and original.created:
                owner.require_current()
                controls.reservations.normalize_advisory(original.target.path)
                _advance_marker(
                    owner,
                    original,
                    controls.reservations._expected[original.target.path],
                    b"\0",
                )
                _sync_journal(owner)
                owner.require_current()
        pending = layout_pending_control_path(owner._project.root)
        native = sorted(
            (m for m in ticket.markers if not m.target.advisory),
            key=lambda m: m.target.path == pending,
        )
        for original in native:
            owner.require_current()
            if original.target.path == pending:
                controls._pool._journal.append(
                    "catalog-commit-observed",
                    canonical_json_bytes(
                        {
                            "plan": owner._stages.plan.identity.uri,
                            "state": "committed-unqualified",
                            "provenance": owner._project.files[record[8].target],
                            "qualified": False,
                        }
                    ),
                )
                _sync_journal(owner)
                progress["decision"] = True
                owner.require_current()
            destination, node, content = controls.reservations.retire_native(
                original.target.path
            )
            _advance_marker(owner, original, node, content, destination)
            _sync_journal(owner)
            owner.require_current()
        controls.reservations.verify_finalized()
        controls._pool._journal.append(
            "catalog-finalization-observed",
            canonical_json_bytes(
                {"plan": owner._stages.plan.identity.uri, "qualified": False}
            ),
        )
        _sync_journal(owner)
        owner.require_current()
        controls.reservations.finish_finalization()
        progress["complete"] = True
        owner._journal(
            "catalog-controls-observed",
            {"plan": owner._stages.plan.identity.uri, "qualified": False},
        )
        owner.require_current()
        return {
            "state": "controls-finalized-imported-handoff-pending",
            "retired": str(root),
            "qualified": False,
            "grants_imported_roles": False,
        }
    except BaseException:
        _FAILED.add(owner)
        raise
    finally:
        _BUSY.discard(owner)
