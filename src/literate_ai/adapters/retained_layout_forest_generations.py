"""Discover existing supplemental controls using actual current producers.

Returned requests are descriptions. Each group still needs the normal fresh raw
proposal, exact acknowledgement and registered descriptor acquisition factory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_roles import _project_roles
from .retained_layout_forest_observation import _record
from .retained_layout_git_controls import observe_layout_git_controls
from .retained_layout_partition import _physical_wire
from .retained_layout_recovery_controls import (
    _RecoveredControlSet,
    _require_recovered_creation,
)
from .retained_layout_recovery_roles import _RecoveryReservations


def _fail(message):
    raise ValueError("layout.forest-generations: " + message)


@dataclass(frozen=True, slots=True)
class _GenerationRequest:
    group: str
    targets: tuple
    current_git_observed: bool = True


def _catalog(value, recovered):
    if (
        type(recovered) is not tuple
        or not 1 <= len(recovered) <= 32
        or any(
            type(o) is not _RecoveredControlSet or o._pool is not value.pool
            for o in recovered
        )
    ):
        _fail("actual same-observer original raw descriptor sets required")
    for owner in recovered:
        _require_recovered_creation(owner)
    count = sum(len(o._plan.markers) + len(o._plan.lineages) for o in recovered)
    value.ledger.charge_records(256 + 64 * count, 131072 + 8192 * count)
    return _RecoveryReservations(value.pool, recovered)


def discover_supplemental_controls(observer, recovered):
    """Read current canonical targets under genuinely held original mutexes."""
    value = _record(observer, reading=True)
    catalog = _catalog(value, recovered)
    original_catalog = (catalog._recovered, catalog._incoming, catalog._inventory)
    receiver = catalog._receiver
    journal = value.journal
    value.ledger.charge_records(2 * len(journal._known) + 2 * len(journal._events))
    roster, events = tuple(journal._known.items()), tuple(journal._events)

    def close():
        if (
            _record(observer, reading=True) is not value
            or catalog._active is not True
            or catalog._receiver != receiver
            or receiver != os.getpid()
            or catalog._pool is not value.pool
            or catalog._recovered is not original_catalog[0]
            or catalog._incoming is not original_catalog[1]
            or catalog._inventory is not original_catalog[2]
            or tuple(journal._events) != events
            or len(journal._known) != len(roster)
            or any(journal._known.get(n) is not r for n, r in roster)
        ):
            _fail("original discovery inputs or actual descriptor catalog changed")
        for owner in recovered:
            _require_recovered_creation(owner)

    try:
        close()
        seed = _project_roles(value.root)
        close()
        if any(not catalog.owns(t.path) for t in seed.targets() if t.advisory):
            _fail("actual canonical project mutexes must already be held")
        tail = value.frontier.recovery
        generations = () if tail is None else tail.generations
        count = sum(len(o._plan.markers) for o in recovered) + sum(
            len(g.leases) + len(g.publications) + len(g.handoffs) for g in generations
        )
        value.ledger.charge_records(256 + 64 * count, 131072 + 8192 * count)
        known = {}
        private_native = set()
        for owner in recovered:
            for marker in owner._plan.markers:
                target = marker.target
                previous = known.setdefault(str(target.path), target)
                if canonical_json_bytes(
                    _custody_wire(previous)
                ) != canonical_json_bytes(_custody_wire(target)):
                    _fail("actual prior producer target anchors disagree")
                if not target.advisory and marker.named != target.path:
                    private_native.add(str(target.path))
        represented = {o._plan.group for o in recovered}
        project_paths = {str(t.path) for t in seed.targets()}
        bootstrap = any(
            generation.group not in represented
            and any(
                lease["advisory"] is False
                and lease["path"] not in project_paths
                and lease["path"] in known
                for lease in generation.leases
            )
            for generation in generations
        )
        if bootstrap:
            # Existing Git writer markers belong to later real generations.
            # Historical target descriptions let the normal raw factory acquire
            # them; only subsequent canonical role derivation validates Git.
            git = None
            targets = tuple(known.values())
        else:
            git = observe_layout_git_controls(value.root, reservations=catalog)
            close()
            value.ledger.charge_records(
                64 * (len(seed.targets()) + len(git.targets())),
                8192 * (len(seed.targets()) + len(git.targets())),
            )
            targets = tuple(dict.fromkeys(seed.targets() + git.targets()))
        target_seal = canonical_json_bytes(_custody_wire(targets))
        current = {str(t.path): t for t in targets}
        reachable = set(represented)
        requests = []
        for generation in generations:
            if generation.group in represented:
                continue
            if not generation.handoffs or not any(
                h["old_group"] in reachable for h in generation.handoffs
            ):
                _fail("supplemental generation lacks its original descriptor lineage")
            selected = []
            for lease in generation.leases:
                target = current.get(lease["path"])
                if target is None or target.advisory is not lease["advisory"]:
                    _fail(
                        "supplemental generation differs from actual canonical producer"
                    )
                if bootstrap and (
                    target.advisory
                    or lease["path"] not in private_native
                    or not any(
                        handoff["old_group"] in reachable
                        and any(
                            path == lease["path"]
                            and canonical_json_bytes(node)
                            == canonical_json_bytes(lease["node"])
                            for path, node in handoff["incoming_nodes"]
                        )
                        for handoff in generation.handoffs
                    )
                ):
                    _fail("bootstrap lacks its exact prior private descriptor lineage")
                selected.append(target)
            if not selected:
                _fail("complete supplemental native lease set required")
            if (
                bootstrap
                and canonical_identity(
                    _physical_wire(
                        [
                            {
                                "path": str(t.path),
                                "anchor": str(t.anchor),
                                "anchor_node": t.anchor_node,
                                "advisory": t.advisory,
                            }
                            for t in selected
                        ]
                    )
                ).uri
                != generation.target_identity
            ):
                _fail("bootstrap target anchors differ from their recorded producer")
            requests.append(
                _GenerationRequest(
                    generation.group,
                    tuple(selected),
                    current_git_observed=not bootstrap,
                )
            )
            reachable.add(generation.group)
        original_requests = tuple(requests)
        references = tuple(
            (item, tuple((f.name, getattr(item, f.name)) for f in fields(item)))
            for item in original_requests + targets
        )
        request_seal = canonical_json_bytes(_custody_wire((original_requests, targets)))
        seed.require_initial_inputs()
        close()
        if git is not None:
            git.require_unchanged(catalog)
            close()
            git.close_native_inputs(catalog)
            close()
        seed.close_native_inputs()
        close()
        catalog.verify_all()
        close()
        final_targets = (
            tuple(known.values())
            if bootstrap
            else tuple(dict.fromkeys(seed.targets() + git.targets()))
        )
        close()
        if canonical_json_bytes(_custody_wire(final_targets)) != target_seal:
            _fail("actual producer targets changed during generation discovery")
        if (
            len(requests) != len(original_requests)
            or any(a is not b for a, b in zip(requests, original_requests, strict=True))
            or any(
                getattr(item, name) is not previous
                for item, values in references
                for name, previous in values
            )
            or canonical_json_bytes(_custody_wire((tuple(requests), targets)))
            != request_seal
        ):
            _fail("derived generation requests or target references changed")
        return original_requests
    finally:
        catalog._active = False
