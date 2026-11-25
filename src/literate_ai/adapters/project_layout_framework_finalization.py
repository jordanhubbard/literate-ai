"""Actual destination producers and original source Component closure.

This finalizes bounded framework Components, not complete project containment.
Original journals/history are immutable. A restart recreates actual normal
preparations from current project data and the exact selected renewal facts.
"""

from __future__ import annotations

import os
from pathlib import Path

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters import project_layout_framework_source_closure as closing
from literate_ai.adapters import project_layout_framework_source_controls as controls
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.project_layout_lease import (
    current_layout_lease,
    require_layout_lease,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore


def _bind_original_finalizer():
    namespace = globals()
    aliases = tuple(
        (name, namespace[name])
        for name in (
            "operations",
            "native",
            "renewal",
            "closing",
            "controls",
            "framework",
            "filesystem",
            "FilesystemComponentLockPlanner",
            "FilesystemLockedGenerationAuthorityReader",
            "current_layout_lease",
            "require_layout_lease",
            "ProjectConfigurationStore",
            "Path",
        )
    )
    delegates = tuple(
        (module, name, vars(module)[name])
        for module, names in (
            (
                operations,
                (
                    "prepare_component_lock",
                    "require_original_prepared_component_lock",
                    "operate_component_lock",
                ),
            ),
            (
                framework,
                ("_current", "_decode", "_state", "_guard_intent", "_move_directory"),
            ),
            (
                closing,
                (
                    "close_component_source",
                    "records",
                    "_held",
                    "_residual",
                    "_paths",
                    "_expected",
                ),
            ),
            (
                controls,
                (
                    "close_source_controls",
                    "restore_source_controls",
                    "is_recorded",
                    "records",
                    "locations",
                    "_expected",
                    "_path",
                    "_stage",
                    "_held",
                    "_move",
                    "_fail",
                    "native",
                    "filesystem",
                    "physical",
                    "os",
                    "json",
                    "tempfile",
                    "Path",
                    "directory_node",
                    "require_layout_lease",
                    "canonical_identity",
                    "canonical_json_bytes",
                    "move_file_between_owned_parents_exclusive",
                    "publish_directory_between_owned_parents_exclusive",
                    "_acquire",
                    "_release",
                    "_SCHEMA",
                    "_CLOSED",
                ),
            ),
            (
                renewal,
                ("_decode", "_guard_journal", "_state", "_path", "_expected_pairs"),
            ),
            (filesystem, ("_file", "_identity")),
        )
        for name in names
    )
    read = ProjectConfigurationStore.read
    catalog_read = FilesystemLockedGenerationAuthorityReader.load_catalog
    error_type = ProjectLayoutPlanError

    def bindings():
        if (
            namespace.get("finalize_framework_components")
            is not finalize_framework_components
            or any(namespace.get(name) is not original for name, original in aliases)
            or any(
                vars(module).get(name) is not original
                for module, name, original in delegates
            )
            or ProjectConfigurationStore.read is not read
            or FilesystemLockedGenerationAuthorityReader.load_catalog
            is not catalog_read
        ):
            raise error_type(
                "framework_finalization_conflict",
                "original framework finalization delegate changed",
            )

    def _fail(message):
        raise ProjectLayoutPlanError("framework_finalization_conflict", message)

    def _views(root, journal, intent, lease, namespace):
        bindings()
        framework._current(root, journal, intent, lease, namespace)
        bindings()
        if "retired-source" not in intent["journal_directories"]:
            _fail("original v1 framework journal supports rollback, not source closure")
        if not os.path.lexists(journal / "placed") or os.path.lexists(
            journal / "rolled-back"
        ):
            _fail("source closure requires completed original framework placement")
        renewals, outputs = {}, {}
        for component, target in renewal._expected_pairs(intent):
            path = renewal._path(
                root, intent["plan"]["plan_identity"], component["source_root"], target
            )
            if not os.path.lexists(path):
                continue
            pair_journal, record = renewal._decode(
                root, intent["plan"]["plan_identity"], component, target, intent
            )
            renewal._guard_journal(
                root, pair_journal, record, journal, intent, lease, namespace
            )
            if not os.path.lexists(pair_journal / "renewed") or os.path.lexists(
                pair_journal / "rolled-back"
            ):
                _fail("normal renewal must finish or recover before source closure")
            for coordinate, row in record["entries"].items():
                state = renewal._state(root, pair_journal, coordinate, row)
                if state != ("original" if row["from"] == row["to"] else "published"):
                    _fail("normal producer is not at its exact original terminal state")
                outputs[coordinate] = row
            renewals[(component["source_root"], target)] = record
        for source, row in intent["entries"].items():
            if row["destination"] in outputs:
                if not native._matches(
                    native._view(journal / "before" / row["slot"]), row, original=True
                ):
                    _fail("original source producer history changed")
                if native._view(journal / "after" / row["slot"]) is not None:
                    _fail("original placed producer replacement is ambiguous")
            elif framework._state(root, journal, source, row) != "published":
                _fail("original nonproducer framework output is not published")
        return renewals

    def _normal_current(root, journal, intent, lease, namespace):
        renewals = _views(root, journal, intent, lease, namespace)
        bindings()
        snapshot = ProjectConfigurationStore(root).read()
        bindings()
        reports = []
        for component in intent["components"]:
            manifest = root / component["destination_root"] / "component.md"
            if (
                filesystem._identity(filesystem._file(manifest)[1])
                != component["manifest_identity"]
            ):
                _fail("actual destination Component differs from original authoring")
            catalog = FilesystemLockedGenerationAuthorityReader().load_catalog(
                root / component["destination_root"]
            )
            bindings()
            _views(root, journal, intent, lease, namespace)
            if (
                catalog.project is None
                or catalog.project.root != root
                or catalog.project.definition != snapshot.definition
            ):
                _fail("actual destination catalog belongs to another project")
            catalog.require_unchanged()
            for target in component["target_names"]:
                record = renewals.get((component["source_root"], target))
                selection = record["selection"] if record else None
                flavors = tuple(selection["flavors"]) if selection else ()
                roots = (
                    tuple(root / path for path in selection["flavor_roots"])
                    if selection
                    else tuple(root / path for path in snapshot.definition.flavor_roots)
                )
                planner = FilesystemComponentLockPlanner()
                prepared = operations.prepare_component_lock(
                    root / component["destination_root"],
                    target=target,
                    flavors=flavors,
                    flavor_roots=roots,
                    planner=planner,
                )
                bindings()
                operations.require_original_prepared_component_lock(prepared)
                _views(root, journal, intent, lease, namespace)
                if selection and (
                    prepared.plan.identity.uri != selection["prepared_plan_identity"]
                    or prepared.result.lock.identity.uri
                    != selection["component_lock_identity"]
                    or prepared.result.catalog_audit.identity.uri
                    != selection["catalog_audit_identity"]
                ):
                    _fail(
                        "fresh normal producer differs from original selected renewal"
                    )
                report, status = operations.operate_component_lock(
                    prepared,
                    target=target,
                    flavors=flavors,
                    flavor_roots=roots,
                    planner=planner,
                    check=True,
                    difference=False,
                )
                _views(root, journal, intent, lease, namespace)
                operations.require_original_prepared_component_lock(prepared)
                if (
                    type(status) is not int
                    or status != 0
                    or report.get("current") is not True
                ):
                    _fail("original destination requires ordinary producer renewal")
                reports.append(report)
        bindings()
        current = ProjectConfigurationStore(root).read()
        bindings()
        if (
            current.content != snapshot.content
            or current.directory_binding != snapshot.directory_binding
            or current.manifest_path != snapshot.manifest_path
        ):
            _fail("actual destination project changed during source finalization")
        return reports

    def finalize_framework_components(root, expected):
        """Recreate actual current owners; never deserialize a transition or lease."""
        bindings()
        root = Path(root).absolute()
        lease = current_layout_lease(root)
        require_layout_lease(lease, root)
        journal, intent = framework._decode(root, expected)
        with native._operation(root) as namespace, native._reserve(root, namespace):
            _normal_current(root, journal, intent, lease, namespace)
            # No generic Component operation/write fences remain. The closing actor
            # takes separate original data-control handles and never unlinks them.
            for component in intent["components"]:
                _normal_current(root, journal, intent, lease, namespace)
                if controls.is_recorded(intent, component):
                    controls.close_source_controls(
                        root, journal, intent, component, lease, namespace
                    )
                else:
                    closing.close_component_source(
                        root, journal, intent, component, lease, namespace
                    )
                _views(root, journal, intent, lease, namespace)
            reports = _normal_current(root, journal, intent, lease, namespace)
            closed = closing.records(root, journal, intent)
            control_records = controls.records(root, journal, intent)
            closed_names = {record["source_root"] for record, _, _ in closed}
            control_names = {record["source_root"] for record, _, _ in control_records}
            if (
                closed_names & control_names
                or closed_names | control_names
                != {row["source_root"] for row in intent["components"]}
                or any(not archived for _, _, archived in closed)
                or any(
                    not archived
                    for _, _, rows in control_records
                    for _, _, archived in rows
                )
            ):
                _fail("original Component source namespace remains live")
            return {
                "components_finalized": True,
                "closed_components": sorted(closed_names | control_names),
                "normal_producers": reports,
                "full_containment": False,
                "qualification": False,
            }

    return finalize_framework_components


finalize_framework_components = _bind_original_finalizer()
