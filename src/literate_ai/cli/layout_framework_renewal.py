"""Explicit normal producer selection inside an acknowledged native migration."""

from __future__ import annotations

from pathlib import Path

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_lock_planning import (
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.adapters.project_layout_framework_producer_result import (
    SCHEMA,
    decode_framework_producer_result,
)
from literate_ai.adapters.project_layout_framework_renewal import (
    renew_placed_framework_component,
)
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import ProjectConfigurationStore


def renew_framework_from_args(args):
    """No decoded source actor; issue actual preparation under this Root lease."""
    if not args.acknowledge or not args.place_framework_authority:
        raise ProjectLayoutPlanError(
            "acknowledgement_required", "acknowledge original framework placement"
        )
    try:
        coordinate = canonical_relative_posix_path(
            args.component, label="Component"
        ).as_posix()
        requested_roots = tuple(
            canonical_relative_posix_path(path, label="Flavor root").as_posix()
            for path in args.flavor_root
        )
    except (TypeError, ValueError) as exc:
        raise ProjectLayoutPlanError("framework_producer_selection", str(exc)) from exc
    snapshot = ProjectConfigurationStore.discover(Path(args.project))
    if (
        snapshot is None
        or ProjectConfigurationStore.context(snapshot.root).framework_root
        != snapshot.root / "litai"
    ):
        raise ProjectLayoutPlanError(
            "framework_migration_profile", "contained framework project required"
        )
    root = snapshot.root
    with ProjectConfigurationStore.layout_lock(root):
        lease = current_layout_lease(root)
        journal, intent = framework._decode(root, args.plan_identity)
        framework._current(root, journal, intent, lease, None)
        matches = [
            row for row in intent["components"] if row["destination_root"] == coordinate
        ]
        if len(matches) != 1 or args.target not in matches[0]["target_names"]:
            raise ProjectLayoutPlanError(
                "framework_producer_selection",
                "select an original placed Component and producer target",
            )
        component = matches[0]
        actual = ProjectConfigurationStore(root).read()
        roots = tuple(
            root / canonical_relative_posix_path(path, label="Flavor root")
            for path in (requested_roots or actual.definition.flavor_roots)
        )
        try:
            prepared = operations.prepare_component_lock(
                root / coordinate,
                target=args.target,
                flavors=tuple(args.flavor),
                flavor_roots=roots,
                planner=FilesystemComponentLockPlanner(),
            )
            result = renew_placed_framework_component(
                root, args.plan_identity, prepared=prepared, layout_lease=lease
            )
        except ComponentLockPlanningError as exc:
            raise ProjectLayoutPlanError(exc.code, str(exc)) from exc
        return decode_framework_producer_result(
            {
                "schema": SCHEMA,
                "operation": "renew",
                "project": str(root),
                "plan_identity": args.plan_identity,
                "source_component": component["source_root"],
                "destination_component": coordinate,
                "target": args.target,
                **result,
            }
        )
