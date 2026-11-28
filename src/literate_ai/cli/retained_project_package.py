"""Compose the existing ZIP provider with live complete retained admission."""

from pathlib import Path

from literate_ai.adapters.component_lock_application import (
    current_project_component_locks,
)
from literate_ai.adapters.retained_project_package import RetainedProjectZipPackage
from literate_ai.contracts import ContentIdentity, StandardProjectLifecycleDriver
from literate_ai.contracts.flavors import FlavorAxis
from literate_ai.projects import discover_project

from .errors import CliFailure
from .execution_workers import add_execution_worker_arguments
from .retained_project import retained_project_from_args


def _selected_zip_provider(project, identity):
    lock_identity = ContentIdentity.parse_uri(identity)
    locks = current_project_component_locks(project)
    lock = next((item for item in locks if item.identity == lock_identity), None)
    if lock is None:
        raise ValueError("retained.package.selected-provider-lock-required")
    node = next(
        item for item in lock.nodes if item.revision.identity == lock.root_revision
    )
    providers = [
        value
        for slot in node.target_flavor_selection.slots
        if slot.slot.axis is FlavorAxis.PACKAGING
        for value in slot.selected
        if value.value == "zip"
    ]
    if len(providers) != 1:
        raise ValueError("retained.package.locked-zip-provider-required")
    return lock.identity, providers[0].flavor_revision


def retained_project_package_from_args(args):
    from .rebuild import _resolve_standard_binding

    try:
        project = discover_project(Path(args.project))
        if project is None:
            raise ValueError("retained.package.project-required")
        driver = project.definition.lifecycle_driver
        if not isinstance(driver, StandardProjectLifecycleDriver):
            raise ValueError("retained.package.standard-lifecycle-required")
        binding = _resolve_standard_binding(driver)
        lock, revision = _selected_zip_provider(project, args.provider_lock)
        packages = []

        def consume(admission, workspace):
            if args.retained_project_plan:
                raise ValueError("retained.package.read-only-intent")
            # Re-read selected authority before consuming the actual live admission.
            if _selected_zip_provider(project, args.provider_lock) != (lock, revision):
                raise ValueError("retained.package.provider-changed")
            owner = RetainedProjectZipPackage(
                admission, provider_lock_identity=lock, provider_revision=revision
            )
            result = owner.construct(workspace.objects)
            owner.verify(result)
            packages.append({"plan": owner.plan.to_dict(), "result": result.to_dict()})

        result = retained_project_from_args(
            project, binding, args, consume_admission=consume
        )
        if args.retained_project_plan:
            if _selected_zip_provider(project, args.provider_lock) != (lock, revision):
                raise ValueError("retained.package.provider-changed")
            return {
                **result,
                "package_qualified": False,
                "package_intent": {
                    "provider": "zip",
                    "provider_lock": lock.uri,
                    "provider_revision": revision.uri,
                    "scope": (
                        "complete admitted retained payload; "
                        "exact archive requires execution"
                    ),
                },
            }
        if len(packages) != 1 or result.get("admitted") is not True:
            raise ValueError("retained.package.live-consumer-required")
        return {**result, "package_qualified": True, "retained_package": packages[0]}
    except CliFailure:
        raise
    except (ValueError, TypeError, OSError) as exc:
        raise CliFailure("retained.package.execution_failed", str(exc)) from exc


def add_retained_project_package_parser(commands):
    parser = commands.add_parser(
        "retained-project",
        help="run the complete retained lifecycle and verify its selected ZIP",
    )
    parser.add_argument("--project", default=".")
    parser.add_argument("--target", default="host")
    parser.add_argument("--retained-project", required=True)
    parser.add_argument("--retained-project-profile", required=True)
    parser.add_argument(
        "--provider-lock", required=True, help="current ZIP Component lock identity"
    )
    parser.add_argument("--retained-project-plan", action="store_true")
    parser.add_argument("--authorize-retained-project")
    parser.add_argument("--allow-host-execution", action="store_true")
    parser.add_argument("--build-dir")
    parser.add_argument("--obj-dir")
    add_execution_worker_arguments(parser)
    parser.set_defaults(specification=".", force_regeneration=False)
