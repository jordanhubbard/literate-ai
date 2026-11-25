"""Acknowledged public selection delegates to actual normal/native owners."""

from __future__ import annotations

from pathlib import Path

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_catalog_renewal as catalog
from literate_ai.adapters import project_layout_catalog_successor as successor
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters.component_lock_planning import (
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.adapters.project_layout_component_results import (
    CATALOG_SCHEMA,
    FINALIZATION_SCHEMA,
    decode_catalog_producer_result,
    decode_source_finalization_result,
)
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import ProjectConfigurationStore


def _root(args):
    if not args.acknowledge:
        raise ProjectLayoutPlanError(
            "acknowledgement_required", "acknowledge the exact original layout plan"
        )
    snapshot = ProjectConfigurationStore.discover(Path(args.project))
    if (
        snapshot is None
        or ProjectConfigurationStore.context(snapshot.root).framework_root
        != snapshot.root / "litai"
    ):
        raise ProjectLayoutPlanError(
            "component_migration_profile", "contained framework project required"
        )
    return snapshot.root


def renew_catalog_from_args(args):
    root = _root(args)
    try:
        coordinate = canonical_relative_posix_path(
            args.component, label="Component"
        ).as_posix()
        requested_roots = tuple(
            canonical_relative_posix_path(path, label="Flavor root").as_posix()
            for path in args.flavor_root
        )
    except (TypeError, ValueError) as error:
        raise ProjectLayoutPlanError(
            "catalog_producer_selection", str(error)
        ) from error
    with ProjectConfigurationStore.layout_lock(root):
        lease = current_layout_lease(root)
        parent, intent = native._decode_intent(root, args.plan_identity)
        binding = (
            successor.observe_catalog_successor(
                root, parent, intent, lease, None, args.successor_plan_identity
            )
            if args.successor_plan_identity
            else None
        )
        catalog._guard(root, parent, intent, lease, None, successor=binding)
        matches = [
            row for row in intent["components"] if row["destination_root"] == coordinate
        ]
        if len(matches) != 1 or args.target not in matches[0]["target_names"]:
            raise ProjectLayoutPlanError(
                "catalog_producer_selection",
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
            result = catalog.renew_placed_catalog_component(
                root,
                args.plan_identity,
                prepared=prepared,
                layout_lease=lease,
                successor_plan_identity=args.successor_plan_identity,
            )
        except ComponentLockPlanningError as error:
            raise ProjectLayoutPlanError(error.code, str(error)) from error
        return decode_catalog_producer_result(
            {
                "schema": CATALOG_SCHEMA,
                "operation": "renew",
                "project": str(root),
                "plan_identity": args.plan_identity,
                "catalog_intent_identity": canonical_identity(intent).uri,
                "successor_plan_identity": args.successor_plan_identity,
                "source_component": component["source_root"],
                "destination_component": coordinate,
                "target": args.target,
                **result,
            }
        )


def finalize_layout_from_args(args):
    root = _root(args)
    scope = "framework" if args.place_framework_authority else "catalog"
    with ProjectConfigurationStore.layout_lock(root):
        if scope == "framework":
            from literate_ai.adapters.project_layout_framework_finalization import (
                finalize_framework_components,
            )

            result = finalize_framework_components(root, args.plan_identity)
        else:
            from literate_ai.adapters.project_layout_catalog_finalization import (
                finalize_catalog_components,
            )

            result = finalize_catalog_components(
                root,
                args.plan_identity,
                successor_plan_identity=args.successor_plan_identity,
            )
        return decode_source_finalization_result(
            {
                "schema": FINALIZATION_SCHEMA,
                "operation": "finalize",
                "scope": scope,
                "project": str(root),
                "plan_identity": args.plan_identity,
                "successor_plan_identity": args.successor_plan_identity,
                **result,
            }
        )
