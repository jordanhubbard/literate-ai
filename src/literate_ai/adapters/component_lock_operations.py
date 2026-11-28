"""Shared Component lock preparation, currentness checks, and pair publication.

CLI commands and read-only observability use the same input revalidation and
artifact stability checks. Check/diff operations never acquire a writing mutex.
"""

from __future__ import annotations

import weakref
from contextlib import nullcontext
from dataclasses import dataclass, fields
from pathlib import Path, PosixPath, WindowsPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .legacy_generation_catalog import LegacyFlavorGraphObservation

from literate_ai.adapters.component_lock_planning import (
    ComponentCatalogSnapshot,
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.adapters.component_locks import (
    ComponentLockCheck,
    ComponentLockStore,
    ComponentLockStoreError,
)
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditCheck,
    ComponentResolutionAuditStore,
)
from literate_ai.application.component_lock_resolution import (
    ComponentLockResolutionPlan,
    ComponentLockResolutionResult,
    ComponentLockResolver,
)
from literate_ai.contracts import ProjectDefinition, canonical_json_bytes
from literate_ai.contracts.component_locking.locks import (
    ComponentLock,
    ComponentResolutionAudit,
)
from literate_ai.projects import LoadedProject


@dataclass(frozen=True, slots=True, weakref_slot=True)
class PreparedComponentLock:
    component_root: Path
    plan: ComponentLockResolutionPlan
    result: ComponentLockResolutionResult
    catalog_snapshot: ComponentCatalogSnapshot | None = None
    requested_flavor_roots: tuple[Path, ...] | None = None
    lineage_flavors: LegacyFlavorGraphObservation | None = None


def prepare_component_lock(
    component: Path,
    *,
    target: str,
    flavors: tuple[str, ...],
    flavor_roots: tuple[Path, ...],
    planner: FilesystemComponentLockPlanner,
    reuse_lineage_catalog: bool = False,
) -> PreparedComponentLock:
    admission = _begin_prepared_origin(planner, target, flavors, flavor_roots)
    lineage_flavors = None
    if reuse_lineage_catalog:
        from literate_ai.projects import discover_project

        from .legacy_generation_catalog import (
            LegacyFlavorGraphObservation,
            scoped_flavor_graph_observation,
        )

        project = discover_project(component)
        if project is not None:
            roots = project.roots("flavor")
            lineage_flavors = scoped_flavor_graph_observation(roots)
            if lineage_flavors is None:
                lineage_flavors = LegacyFlavorGraphObservation.capture(roots)
    plan, snapshot = planner.plan_with_snapshot(
        component,
        target_name=target,
        flavor_selectors=flavors,
        flavor_roots=flavor_roots,
        **({"lineage_flavors": lineage_flavors} if lineage_flavors is not None else {}),
    )
    result = ComponentLockResolver().resolve(
        plan, expected_input_evidence_identity=plan.identity
    )
    prepared = PreparedComponentLock(
        component.resolve(strict=True),
        plan,
        result,
        snapshot,
        flavor_roots,
        lineage_flavors,
    )
    if admission is not None:
        _register_prepared_origin(prepared, planner, admission)
    return prepared


def operate_component_lock(
    prepared: PreparedComponentLock,
    *,
    target: str,
    flavors: tuple[str, ...],
    flavor_roots: tuple[Path, ...],
    planner: FilesystemComponentLockPlanner,
    check: bool,
    difference: bool,
) -> tuple[dict[str, object], int]:
    # Only the original factory-admitted lane adds these checks. Existing
    # unadmitted/custom preparation retains the original operation behavior.
    original_guard = None
    original = _PREPARED_ADMISSIONS.get(id(prepared))
    if original is not None and original[0]() is prepared:
        original_guard = require_original_prepared_component_lock
        original_guard(prepared)
    component_root = prepared.component_root
    result = prepared.result
    lock_store = ComponentLockStore(component_root)
    audit_store = ComponentResolutionAuditStore(component_root, target)

    def require_inputs_unchanged() -> None:
        if original_guard is not None:
            original_guard(prepared)
        snapshot = (
            prepared.catalog_snapshot
            if (check or difference) and prepared.requested_flavor_roots == flavor_roots
            else None
        )
        if snapshot is None:
            current = prepare_component_lock(
                component_root,
                target=target,
                flavors=flavors,
                flavor_roots=flavor_roots,
                planner=planner,
            )
        else:
            # Reuse parsed immutable catalog values only within this read-only
            # transaction. Reopen all bound bytes and membership before planning;
            # plan_snapshot still observes current graph authority and revalidates
            # selected inputs afterwards. This is private prepared-operation state,
            # not a shared cache of trusted currentness.
            snapshot.require_unchanged()
            plan = planner.plan_snapshot(
                snapshot,
                target_name=target,
                flavor_selectors=flavors,
                **(
                    {"lineage_flavors": prepared.lineage_flavors}
                    if prepared.lineage_flavors is not None
                    else {}
                ),
            )
            current = PreparedComponentLock(
                component_root,
                plan,
                ComponentLockResolver().resolve(
                    plan, expected_input_evidence_identity=plan.identity
                ),
                snapshot,
                flavor_roots,
            )
        if (
            current.plan.identity != prepared.plan.identity
            or current.result.lock.identity != result.lock.identity
            or current.result.catalog_audit.identity != result.catalog_audit.identity
        ):
            raise ComponentLockPlanningError(
                "component_lock.inputs_changed",
                "Component or catalog inputs changed during lock materialization",
            )
        # Foreign repository_source_resolver.lock ran inside the real planner.
        # Check before any next store/check dispatch, not only at outer return.
        if original_guard is not None:
            original_guard(prepared)

    with nullcontext() if check or difference else lock_store.operation():
        require_inputs_unchanged()
        first_checks = component_artifact_checks(lock_store, audit_store, result)
        require_inputs_unchanged()
        second_checks = component_artifact_checks(lock_store, audit_store, result)
        require_component_checks_stable(first_checks, second_checks)
        if check or difference:
            require_inputs_unchanged()
            lock_check, audit_check = second_checks
            current = lock_check.current and audit_check.current
            return {
                **_base_report(prepared, target, lock_check, audit_check),
                "mode": "diff" if difference else "check",
                "current": current,
            }, (0 if current else 1)

        lock_snapshot = lock_store.snapshot()
        audit_snapshot = audit_store.snapshot()
        try:
            audit_updated = audit_store.update(
                result.catalog_audit, revalidate=require_inputs_unchanged
            )
            lock_updated = lock_store.update(
                result.lock, revalidate=require_inputs_unchanged
            )
            require_inputs_unchanged()
            first_final = component_artifact_checks(lock_store, audit_store, result)
            require_inputs_unchanged()
            final_checks = component_artifact_checks(lock_store, audit_store, result)
            require_component_checks_stable(
                first_final, final_checks, require_current=True
            )
            require_inputs_unchanged()
        except Exception:
            rollback_errors: list[Exception] = []
            for restore in (
                lambda: lock_store.restore_if_current(
                    lock_snapshot, expected_current=result.lock
                ),
                lambda: audit_store.restore_if_current(
                    audit_snapshot, expected_current=result.catalog_audit
                ),
            ):
                try:
                    restore()
                except Exception as rollback_error:
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                raise ComponentLockStoreError(
                    "component_lock.rollback_failed",
                    "Component lock/audit publication failed and could not be "
                    "rolled back",
                ) from rollback_errors[0]
            raise
        lock_check, audit_check = final_checks
        return {
            **_base_report(prepared, target, lock_check, audit_check),
            "mode": "update",
            "lock_updated": lock_updated,
            "catalog_audit_updated": audit_updated,
        }, 0


def component_artifact_checks(lock_store, audit_store, result):
    return (
        lock_store.check(result.lock, authorings=result.lock.authorings),
        audit_store.check(result.catalog_audit),
    )


def require_component_checks_stable(
    first, second, *, require_current: bool = False
) -> None:
    if tuple(item.to_dict() for item in first) != tuple(
        item.to_dict() for item in second
    ):
        raise ComponentLockStoreError(
            "component_lock.concurrent_change",
            "Component lock or resolution audit changed during final verification",
        )
    if require_current and not all(item.current for item in second):
        raise ComponentLockStoreError(
            "component_lock.publication_inconsistent",
            "Component lock and resolution audit were not published as one exact pair",
        )


def _base_report(prepared, target, lock_check, audit_check) -> dict[str, object]:
    return {
        "schema": "literate-ai/component-lock-command@1",
        "component": str(prepared.component_root),
        "target": target,
        "resolution_plan_identity": prepared.plan.identity.uri,
        "component_lock_identity": prepared.result.lock.identity.uri,
        "catalog_audit_identity": prepared.result.catalog_audit.identity.uri,
        "provider_resolutions": [
            {
                "resolution_id": item.request.resolution_id,
                "selected_provider": item.selected_provider,
                "identity": item.identity.uri,
                "fallback_reason": item.fallback_reason,
                "override_declaration_identity": (
                    None
                    if item.override_declaration_identity is None
                    else item.override_declaration_identity.uri
                ),
                "override_provenance_identity": (
                    None
                    if item.override_provenance_identity is None
                    else item.override_provenance_identity.uri
                ),
            }
            for item in prepared.result.lock.provider_resolutions
        ],
        "lock": lock_check.to_dict(),
        "catalog_audit": audit_check.to_dict(),
    }


# Data provenance only. Normal custom-planner preparation/check/update signatures
# remain unchanged; custom planners produce unadmitted values for this new lane.
_PREPARED_TYPES = (
    PreparedComponentLock,
    FilesystemComponentLockPlanner,
    ComponentCatalogSnapshot,
    ComponentLockResolutionPlan,
    ComponentLockResolutionResult,
    ComponentLockResolver,
    ComponentLock,
    ComponentResolutionAudit,
    ComponentLockStore,
    ComponentResolutionAuditStore,
    ComponentLockCheck,
    ComponentResolutionAuditCheck,
    LoadedProject,
    ProjectDefinition,
)
_PREPARED_DATA_FIELDS = tuple(
    (cls, tuple(field.name for field in fields(cls)))
    for cls in _PREPARED_TYPES
    if cls
    not in (
        FilesystemComponentLockPlanner,
        ComponentLockResolver,
        ComponentLockStore,
        ComponentResolutionAuditStore,
    )
)
_PREPARED_CLASS_ORIGIN = tuple(
    (
        cls,
        tuple(type.__getattribute__(cls, "__dict__").items()),
        type.__getattribute__(cls, "__bases__"),
        type.__getattribute__(cls, "__mro__"),
    )
    for cls in _PREPARED_TYPES
)
_PREPARED_FIELDS = tuple(field.name for field in fields(PreparedComponentLock))
_PREPARED_FACTORY = prepare_component_lock
_PREPARED_ADMISSIONS = {}


def _prepared_classes_current():
    if prepare_component_lock is not _PREPARED_FACTORY or any(
        globals().get(name) is not original
        for name, original in _PREPARED_GLOBAL_ORIGIN
    ):
        raise ComponentLockPlanningError(
            "component_lock.preparation_origin", "original preparation factory changed"
        )
    for cls, members, bases, mro in _PREPARED_CLASS_ORIGIN:
        current = type.__getattribute__(cls, "__dict__")
        if (
            type.__getattribute__(cls, "__bases__") is not bases
            or type.__getattribute__(cls, "__mro__") is not mro
            or set(current) != {name for name, _ in members}
            or any(current[name] is not original for name, original in members)
        ):
            raise ComponentLockPlanningError(
                "component_lock.preparation_origin", "original prepared class changed"
            )


def _planner_pointer(planner):
    values = object.__getattribute__(planner, "__dict__")
    # Reject shadowed methods even when the original class slot is intact.
    if set(values) != {"repository_source_resolver"}:
        raise ComponentLockPlanningError(
            "component_lock.preparation_origin", "original planner fields changed"
        )
    return values["repository_source_resolver"]


def _begin_prepared_origin(planner, target, flavors, flavor_roots):
    if (
        type(planner) is not FilesystemComponentLockPlanner
        or type(target) is not str
        or type(flavors) is not tuple
        or any(type(value) is not str for value in flavors)
        or type(flavor_roots) is not tuple
        or any(type(value) not in (PosixPath, WindowsPath) for value in flavor_roots)
    ):
        return None
    try:
        _prepared_classes_current()
        pointer = _planner_pointer(planner)
    except ComponentLockPlanningError:
        # Existing instrumented/custom preparation remains usable normally;
        # it simply cannot mint an original admission for the layout lane.
        return None
    return (planner, pointer, target, flavors, flavor_roots)


def _prepared_preimage(prepared):
    return (
        canonical_json_bytes(prepared.plan.to_dict()),
        canonical_json_bytes(prepared.result.lock.to_dict()),
        canonical_json_bytes(prepared.result.catalog_audit.to_dict()),
        canonical_json_bytes(prepared.result.input_evidence_identity.to_dict()),
    )


def _prepared_nested_members(prepared):
    nested = [
        prepared.plan,
        prepared.result,
        prepared.result.lock,
        prepared.result.catalog_audit,
    ]
    if prepared.catalog_snapshot is not None:
        nested.append(prepared.catalog_snapshot)
        if prepared.catalog_snapshot.project is not None:
            nested.extend(
                (
                    prepared.catalog_snapshot.project,
                    prepared.catalog_snapshot.project.definition,
                )
            )
    output = []
    for member in nested:
        selected = next(
            (names for cls, names in _PREPARED_DATA_FIELDS if type(member) is cls), None
        )
        if selected is None:
            raise ComponentLockPlanningError(
                "component_lock.preparation_origin",
                "original typed prepared records required",
            )
        output.append(
            (
                member,
                tuple(
                    (name, object.__getattribute__(member, name)) for name in selected
                ),
            )
        )
    return tuple(output)


def _require_original_members(prepared, previous):
    if any(
        object.__getattribute__(prepared, name) is not original
        for name, original in zip(_PREPARED_FIELDS, previous[1], strict=True)
    ):
        raise ComponentLockPlanningError(
            "component_lock.preparation_origin", "original prepared fields changed"
        )
    for member, values in previous[4]:
        if any(
            object.__getattribute__(member, name) is not original
            for name, original in values
        ):
            raise ComponentLockPlanningError(
                "component_lock.preparation_origin",
                "original nested preparation changed",
            )


def _register_prepared_origin(prepared, planner, admission):
    _prepared_classes_current()
    if planner is not admission[0] or _planner_pointer(planner) is not admission[1]:
        raise ComponentLockPlanningError(
            "component_lock.preparation_origin", "original planner owner changed"
        )
    members = tuple(
        object.__getattribute__(prepared, name) for name in _PREPARED_FIELDS
    )
    nested = _prepared_nested_members(prepared)
    preimage = _prepared_preimage(prepared)
    _prepared_classes_current()
    identity = id(prepared)

    def released(reference):
        previous = _PREPARED_ADMISSIONS.get(identity)
        if previous is not None and previous[0] is reference:
            _PREPARED_ADMISSIONS.pop(identity, None)

    _PREPARED_ADMISSIONS[identity] = (
        weakref.ref(prepared, released),
        members,
        preimage,
        admission,
        nested,
    )
    require_original_prepared_component_lock(prepared)


def _validate_prepared_component_origin(prepared):
    """Prove actual original preparation, never decoded data or a restored grant.

    No I/O or input-currentness assertion. The ordinary check operation must
    still freshly reproduce the original plan and selected pair every time.
    """
    _prepared_classes_current()
    previous = _PREPARED_ADMISSIONS.get(id(prepared))
    if (
        type(prepared) is not PreparedComponentLock
        or previous is None
        or previous[0]() is not prepared
    ):
        raise ComponentLockPlanningError(
            "component_lock.preparation_origin",
            "actual original prepared value required",
        )
    _require_original_members(prepared, previous)
    if _prepared_preimage(prepared) != previous[2]:
        raise ComponentLockPlanningError(
            "component_lock.preparation_origin", "original prepared result changed"
        )
    admission = previous[3]
    if _planner_pointer(admission[0]) is not admission[1]:
        raise ComponentLockPlanningError(
            "component_lock.preparation_origin", "original planner pointer changed"
        )
    _prepared_classes_current()
    _require_original_members(prepared, previous)
    return admission[0], admission[2], admission[3], admission[4]


require_original_prepared_component_lock = _validate_prepared_component_origin

_PREPARED_GLOBAL_ORIGIN = tuple(
    (name, globals()[name])
    for name in (
        "PreparedComponentLock",
        "FilesystemComponentLockPlanner",
        "ComponentCatalogSnapshot",
        "ComponentLockResolutionPlan",
        "ComponentLockResolutionResult",
        "ComponentLockResolver",
        "ComponentLock",
        "ComponentResolutionAudit",
        "ComponentLockStore",
        "ComponentResolutionAuditStore",
        "LoadedProject",
        "ProjectDefinition",
        "operate_component_lock",
        "require_original_prepared_component_lock",
        "_validate_prepared_component_origin",
        "_PREPARED_ADMISSIONS",
        "ComponentLockCheck",
        "ComponentResolutionAuditCheck",
        "canonical_json_bytes",
        "component_artifact_checks",
        "require_component_checks_stable",
        "_prepared_classes_current",
        "_begin_prepared_origin",
        "_register_prepared_origin",
        "_planner_pointer",
        "_prepared_preimage",
        "_prepared_nested_members",
        "_require_original_members",
    )
)


def _bind_prepared_validator():
    """Fixed entry/closing raw guard, immune to module checker substitution."""
    validate = require_original_prepared_component_lock
    classes = _PREPARED_CLASS_ORIGIN
    registry = _PREPARED_ADMISSIONS
    error_type = ComponentLockPlanningError
    origin_names = tuple(name for name, _ in _PREPARED_GLOBAL_ORIGIN)

    def raw_current():
        if (
            globals().get("_PREPARED_CLASS_ORIGIN") is not classes
            or globals().get("_PREPARED_ADMISSIONS") is not registry
            or globals().get("_PREPARED_GLOBAL_ORIGIN") is not seals
            or any(globals().get(name) is not original for name, original in seals)
        ):
            raise error_type(
                "component_lock.preparation_origin",
                "original preparation delegate changed",
            )
        for cls, members, bases, mro in classes:
            current = type.__getattribute__(cls, "__dict__")
            if (
                type.__getattribute__(cls, "__bases__") is not bases
                or type.__getattribute__(cls, "__mro__") is not mro
                or set(current) != {name for name, _ in members}
                or any(current[name] is not original for name, original in members)
            ):
                raise error_type(
                    "component_lock.preparation_origin",
                    "original preparation descriptor changed",
                )

    def require(prepared):
        raw_current()
        value = validate(prepared)
        raw_current()
        return value

    seals = tuple(
        (
            name,
            require
            if name == "require_original_prepared_component_lock"
            else globals()[name],
        )
        for name in origin_names
    )
    return require, seals


require_original_prepared_component_lock, _PREPARED_GLOBAL_ORIGIN = (
    _bind_prepared_validator()
)
