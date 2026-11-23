"""Reviewed replacement of an unqualified retained harness after adoption."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from argparse import Namespace
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

from literate_ai.adapters.conversion_authority import (
    CONVERSION_AUTHORITY_FILE,
    FilesystemConversionAuthorityStore,
)
from literate_ai.adapters.harness_inventory import (
    HARNESS_BASELINE_SCHEMA,
    HARNESS_DIAGNOSTIC_CHARS,
    HARNESS_PARITY_SCHEMA,
    HARNESS_WRAPPER_FILENAME,
    classify_ci,
    execute_harness_baseline,
    execute_harness_wrapper_parity,
    inspect_harness,
    legacy_shim_authority,
    render_harness_wrapper,
    validate_harness_command_timeout,
)
from literate_ai.adapters.harness_tree import (
    capture_retained_source_scope,
    copy_retained_source_tree,
    observe_retained_source_bytes,
    observe_retained_tree,
)
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.adapters.project_initialization import (
    KNOWN_FLAVOR_SELECTORS,
    record_project_authority_review,
)
from literate_ai.adapters.project_validation import FilesystemProjectValidationAdapter
from literate_ai.adapters.repository_refresh import _signature
from literate_ai.adapters.retained_harness_receipts import (
    retained_harness_receipt_policy,
    retained_harness_runner_identity,
)
from literate_ai.adapters.retained_harness_remote import (
    RetainedHarnessRemoteError,
    RetainedHarnessSshExecutor,
    retained_harness_runtime_requirements,
)
from literate_ai.adapters.retained_layout import (
    RETAINED_LAYOUT_PATH,
    ResolvedRetainedLayout,
    RetainedLayoutError,
    read_retained_layout_declaration,
    resolve_structural_layout,
)
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.application.project_authority import AUTHORITY_REVIEW_MARKER
from literate_ai.contracts import (
    ContentIdentity,
    ExecutionWorker,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import (
    DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
    ProjectConfigurationStore,
    load_project,
)

PLAN_SCHEMA = "literate-ai/retained-harness-readmission-plan@1"
HISTORY = ".literate/retained-harness-readmission"
INVENTORY = ".literate/harness-inventory.json"
BASELINE = ".literate/legacy-harness-baseline.json"
PARITY = ".literate/legacy-wrapper-parity.json"
LIFT_SHIFT = ".literate/legacy-lift-shift.json"
_PARITY_SOURCE_CAPTURE_ATTEMPTS = 2
_SOURCE_INPUTS_KEY = object()


class RetainedHarnessReadmissionError(RuntimeError):
    """A retained harness cannot be safely replaced."""

    def __init__(self, code: str, message: str) -> None:
        self.code = f"retained_harness.{code}"
        self.message = message
        super().__init__(f"{self.code}: {message}")


def _fail(code: str, message: str) -> None:
    raise RetainedHarnessReadmissionError(code, message)


def _identity(value: object) -> str:
    if isinstance(value, bytes):
        return f"sha256:{__import__('hashlib').sha256(value).hexdigest()}"
    return canonical_identity(value).uri


def _safe_path(root: Path, relative: str, *, must_exist: bool = True) -> Path:
    raw = PurePosixPath(relative)
    if (
        raw.is_absolute()
        or raw.as_posix() != relative
        or any(part in {"", ".", ".."} for part in raw.parts)
    ):
        _fail("unsafe_path", f"metadata path is unsafe: {relative}")
    path = root
    for part in raw.parts:
        path = path / part
        if path.is_symlink():
            _fail("unsafe_path", f"metadata path must not traverse a link: {relative}")
    if must_exist and not path.is_file():
        _fail("metadata_missing", f"required metadata is unavailable: {relative}")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _fail("metadata_invalid", f"{path.name} is not valid JSON")
        raise AssertionError from exc
    if not isinstance(value, dict):
        _fail("metadata_invalid", f"{path.name} must contain one object")
    return value


def _layout(root: Path) -> ResolvedRetainedLayout:
    lift_shift = _load_json(_safe_path(root, LIFT_SHIFT))
    if os.path.lexists(root / "litai/layout.pending"):
        _fail("layout_pending", "pending relocation requires explicit recovery")
    try:
        declaration = read_retained_layout_declaration(root)
        allowed = {"passed", "requalification-required"} if declaration else {"passed"}
        if lift_shift.get("state") not in allowed:
            _fail("lift_shift_unqualified", "retained lift-and-shift has not passed")
        layout = resolve_structural_layout(root, lift_shift)
        if layout.implementation_directory == ".":
            _fail(
                "root_partition_unavailable",
                "root renewal requires the complete partition owner",
            )
        return layout
    except RetainedLayoutError:
        _fail(
            "lift_shift_invalid", "retained implementation path is unsafe or redirected"
        )


def _conversion(root: Path, project_id: str) -> dict[str, Any]:
    state = FilesystemConversionAuthorityStore(root).load_optional()
    if state is None:
        _fail("not_adopted", "project has no conversion authority")
    if state.project_id != project_id:
        _fail("project_mismatch", "conversion authority identifies another project")
    if state.release_authority != "original-source":
        _fail(
            "source_not_authoritative",
            "readmission is available only while original source remains authoritative",
        )
    return state.to_dict()


def _readmitted_selectors(selectors: tuple[str, ...]) -> tuple[str, ...]:
    retained = tuple(
        selector
        for selector in selectors
        if KNOWN_FLAVOR_SELECTORS.get(selector.removeprefix("+")) != "build.system"
        and selector != "+flavor://legacy-adoption/build-legacy-shim"
    )
    return (*retained, "+flavor://legacy-adoption/build-legacy-shim")


def _retain_admitted_stages(
    old_inventory: dict[str, Any],
    new_inventory: dict[str, Any],
    stage_ids: tuple[str, ...],
    *,
    implementation: Path,
) -> dict[str, Any]:
    """Carry exact reviewed stages that fresh inspection cannot rediscover."""

    if any(not isinstance(stage_id, str) or not stage_id for stage_id in stage_ids):
        _fail("stage_selection_invalid", "retained stage IDs must be non-empty strings")
    if len(set(stage_ids)) != len(stage_ids):
        _fail("stage_selection_invalid", "retained stage IDs must be unique")
    if not stage_ids:
        return new_inventory

    raw_old_stages = old_inventory.get("stages")
    if not isinstance(raw_old_stages, list):
        _fail("inventory_invalid", "current harness inventory has no stage list")
    old_stages = {
        stage.get("id"): stage
        for stage in raw_old_stages
        if isinstance(stage, dict) and isinstance(stage.get("id"), str)
    }
    selected: dict[str, dict[str, Any]] = {}
    for stage_id in stage_ids:
        stage = old_stages.get(stage_id)
        if stage is None:
            _fail(
                "stage_not_admitted",
                f"retained stage is not present in the current inventory: {stage_id}",
            )
        if stage_id.split(".", 1)[0] not in {"build", "test", "package", "ci"}:
            _fail(
                "stage_selection_invalid",
                f"retained stage is not an executable harness phase: {stage_id}",
            )
        command = stage.get("command")
        evidence = stage.get("evidence")
        cwd = stage.get("cwd", ".")
        if not all(isinstance(value, str) and value for value in (command, evidence)):
            _fail("inventory_invalid", f"retained stage is incomplete: {stage_id}")
        if not isinstance(cwd, str) or not cwd:
            _fail("inventory_invalid", f"retained stage cwd is invalid: {stage_id}")
        _safe_path(implementation, evidence)
        selected[stage_id] = dict(stage)

    raw_new_stages = new_inventory.get("stages")
    if not isinstance(raw_new_stages, list):
        _fail("inventory_invalid", "re-inspected harness inventory has no stage list")
    merged: list[dict[str, Any]] = []
    present: set[str] = set()
    for raw_stage in raw_new_stages:
        if not isinstance(raw_stage, dict) or not isinstance(raw_stage.get("id"), str):
            _fail("inventory_invalid", "re-inspected harness contains an invalid stage")
        stage_id = raw_stage["id"]
        merged.append(dict(selected.get(stage_id, raw_stage)))
        present.add(stage_id)
    for raw_stage in raw_old_stages:
        if not isinstance(raw_stage, dict):
            continue
        stage_id = raw_stage.get("id")
        if stage_id in selected and stage_id not in present:
            merged.append(dict(selected[stage_id]))
            present.add(stage_id)

    commands = {
        stage["id"]: {
            key: value
            for key, value in stage.items()
            if key in {"command", "cost", "cwd", "evidence", "id"}
        }
        for stage in merged
        if "." not in stage["id"]
    }
    findings = list(new_inventory.get("findings", []))
    findings.extend(
        {
            "detector_id": "operator.retained-stage",
            "path": selected[stage_id]["evidence"],
            "detail": (
                "previously admitted stage retained by explicit review: " + stage_id
            ),
        }
        for stage_id in stage_ids
    )
    result = {
        **new_inventory,
        "stages": merged,
        "commands": commands,
        "findings": findings,
    }
    result["source_scope"] = capture_retained_source_scope(
        implementation,
        required_paths=tuple(stage["evidence"] for stage in merged),
    )
    return result


def _review_command_selection(
    implementation: Path,
    selection_path: Path,
    old_inventory: dict[str, Any],
    inspected_inventory: dict[str, Any],
    *,
    wrapper_component: str,
    retained_stage_ids: tuple[str, ...],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Plan one existing wrapper's commands with initial adoption's validator.

    This is read-only planning. No CLI or execution owner consumes this new
    binding until its execution and publication currentness are implemented.
    """
    from literate_ai.adapters.monorepo_adoption import (
        plan_monorepo_adoption,
        single_root_baseline_inventory,
    )

    refinement = plan_monorepo_adoption(
        implementation, selection_path, inspected_inventory, submodules=[]
    )
    components = refinement["components"]
    if (
        len(components) != 1
        or components[0]["root"] != "."
        or components[0]["name"] != PurePosixPath(wrapper_component).name
        or refinement["selection"]["shared_sources"]
    ):
        _fail(
            "command_owner_invalid",
            "renewal requires the actual single retained wrapper and its whole root",
        )
    _retain_admitted_stages(
        old_inventory,
        inspected_inventory,
        retained_stage_ids,
        implementation=implementation,
    )
    phases = {stage["id"] for stage in components[0]["commands"]}
    if any(stage.split(".", 1)[0] in phases for stage in retained_stage_ids):
        _fail(
            "command_selection_conflict",
            "a selected command phase cannot also retain its old stage",
        )
    old_stages = old_inventory.get("stages")
    if not isinstance(old_stages, list) or not all(
        isinstance(stage, dict) and isinstance(stage.get("id"), str)
        for stage in old_stages
    ):
        _fail("inventory_invalid", "admitted command stages are incomplete")
    stage_ids = tuple(stage["id"] for stage in old_stages)
    # The existing owner checks uniqueness, executable phases and direct evidence.
    _retain_admitted_stages(
        old_inventory, inspected_inventory, stage_ids, implementation=implementation
    )
    source_paths = set(refinement["source_scope"]["paths"])
    if any(stage.get("evidence") not in source_paths for stage in old_stages):
        _fail("command_evidence_invalid", "admitted evidence left current source scope")
    if not isinstance(old_inventory.get("commands"), dict):
        _fail("inventory_invalid", "admitted command definitions are incomplete")
    # Fresh discovery supplies diagnostics and source membership. Only explicit
    # overrides replace admitted phases; newly detected phases gain no command grant.
    inventory = single_root_baseline_inventory(
        {
            **inspected_inventory,
            "stages": [dict(stage) for stage in old_stages],
            "commands": dict(old_inventory["commands"]),
        },
        refinement,
    )
    binding = {
        "schema": "literate-ai/retained-command-renewal-planning@1",
        "wrapper_component": wrapper_component,
        "selection_plan": refinement,
        "old_stages": old_stages,
        "detected_stages": inspected_inventory["stages"],
        "selected_phases": sorted(phases),
        "compilation_coverage": "unknown",
        "execution_performed": False,
        "apply_supported": False,
    }
    return inventory, binding


def plan_retained_harness_readmission(
    selected: Path,
    *,
    execution_worker: ExecutionWorker | None = None,
    worker_catalog_identity: ContentIdentity | None = None,
    timeout_seconds: int = 1800,
    retained_stage_ids: tuple[str, ...] = (),
    command_selection: Path | None = None,
) -> dict[str, Any]:
    """Re-inspect one wrapped implementation without changing project bytes."""

    timeout_seconds = validate_harness_command_timeout(timeout_seconds)
    if (execution_worker is None) != (worker_catalog_identity is None):
        _fail(
            "worker_binding_invalid",
            "remote worker and catalog identity must be selected together",
        )
    project = load_project(selected)
    root = project.root
    conversion = _conversion(root, project.definition.project_id)
    layout = _layout(root)
    declaration = read_retained_layout_declaration(root)
    implementation_relative = layout.implementation_directory
    implementation = layout.implementation_root
    inventory_path = _safe_path(root, INVENTORY)
    baseline_path = _safe_path(root, BASELINE)
    parity_path = _safe_path(root, PARITY)
    wrapper_path = _safe_path(root, HARNESS_WRAPPER_FILENAME)
    manifest_path = _safe_path(root, "literate.project.json")
    authority_path = _safe_path(root, CONVERSION_AUTHORITY_FILE)
    old_inventory = _load_json(inventory_path)
    new_inventory = inspect_harness(implementation)
    command_renewal = None
    renewal_nodes: tuple = ()
    renewal_ancestry: tuple = ()
    if command_selection is None:
        new_inventory = _retain_admitted_stages(
            old_inventory,
            new_inventory,
            retained_stage_ids,
            implementation=implementation,
        )
    else:
        new_inventory, command_renewal = _review_command_selection(
            implementation,
            command_selection,
            old_inventory,
            new_inventory,
            wrapper_component=layout.wrapper_component,
            retained_stage_ids=retained_stage_ids,
        )
        renewal_paths = (
            *(implementation / path for path in new_inventory["source_scope"]["paths"]),
            command_selection.absolute(),
        )
        renewal_nodes = tuple((path, _signature(path)) for path in renewal_paths)
        renewal_ancestry = tuple(
            (path, _lineage(path))
            for path in dict.fromkeys(path.parent for path in renewal_paths)
        )
    if "workspace_links" in old_inventory:
        new_inventory["workspace_links"] = old_inventory["workspace_links"]
    if execution_worker is not None and new_inventory.get("workspace_links"):
        _fail(
            "remote_workspace_links_unsupported",
            "remote readmission does not yet transport external workspace links",
        )
    source_tree = observe_retained_tree(implementation, new_inventory["source_scope"])[
        "source_tree"
    ]
    wrapper = render_harness_wrapper(
        new_inventory, legacy_directory=implementation_relative
    ).encode("utf-8")
    expected_policy = retained_harness_receipt_policy(new_inventory)
    selectors = _readmitted_selectors(project.definition.default_flavor_selectors)
    expected_phases = [
        {"phase": stage["id"]}
        for stage in new_inventory["stages"]
        if stage["id"].split(".", 1)[0] in {"build", "test", "package", "ci"}
    ]
    shim = legacy_shim_authority(
        new_inventory,
        {
            "schema": HARNESS_BASELINE_SCHEMA,
            "state": "passed",
            "phases": expected_phases,
        },
        wrapper_component=layout.wrapper_component,
    )
    review = FilesystemProjectValidationAdapter().documentation_review(root)
    document = review.get("document")
    if review.get("state") not in {"current", "stale"} or not isinstance(document, str):
        _fail("authority_review_invalid", "project documentation authority is invalid")
    review_path = _safe_path(root, document)
    old_documents = {
        INVENTORY: _identity(inventory_path.read_bytes()),
        BASELINE: _identity(baseline_path.read_bytes()),
        PARITY: _identity(parity_path.read_bytes()),
        HARNESS_WRAPPER_FILENAME: _identity(wrapper_path.read_bytes()),
        "literate.project.json": _identity(manifest_path.read_bytes()),
        CONVERSION_AUTHORITY_FILE: _identity(authority_path.read_bytes()),
        LIFT_SHIFT: _identity(_safe_path(root, LIFT_SHIFT).read_bytes()),
        document: _identity(review_path.read_bytes()),
    }
    if declaration is not None:
        old_documents[RETAINED_LAYOUT_PATH] = _identity(
            _safe_path(root, RETAINED_LAYOUT_PATH).read_bytes()
        )
    for relative in shim:
        old_documents[relative] = _identity(_safe_path(root, relative).read_bytes())
    component_root = layout.wrapper_root
    for path in (
        component_root / "component.lock.json",
        component_root / "component.resolution-audit.host.json",
    ):
        relative = path.relative_to(root).as_posix()
        old_documents[relative] = _identity(_safe_path(root, relative).read_bytes())
    if command_renewal is not None:
        metadata_paths = tuple(root / relative for relative in old_documents)
        renewal_nodes += tuple((path, _signature(path)) for path in metadata_paths)
        renewal_ancestry += tuple(
            (path, _lineage(path))
            for path in dict.fromkeys(path.parent for path in metadata_paths)
        )
    plan: dict[str, Any] = {
        "schema": PLAN_SCHEMA,
        "project_id": project.definition.project_id,
        "wrapper_component": layout.wrapper_component,
        "implementation": implementation_relative,
        "conversion_authority": conversion,
        "old_documents": old_documents,
        "old_inventory_identity": _identity(old_inventory),
        "new_inventory": new_inventory,
        "new_inventory_identity": _identity(new_inventory),
        "retained_stage_ids": list(retained_stage_ids),
        "source_tree": source_tree,
        "new_wrapper_identity": _identity(wrapper),
        "new_shim_identities": {
            relative: _identity(content.encode("utf-8"))
            for relative, content in shim.items()
        },
        "new_policy": expected_policy.to_dict(),
        "new_default_flavor_selectors": list(selectors),
        "qualification": {
            "worker_id": (
                execution_worker.worker_id if execution_worker is not None else "local"
            ),
            "worker_identity": (
                execution_worker.identity.uri if execution_worker is not None else None
            ),
            "worker_catalog_identity": (
                worker_catalog_identity.uri
                if worker_catalog_identity is not None
                else None
            ),
            "timeout_seconds": timeout_seconds,
            "runtime_requirements": list(
                retained_harness_runtime_requirements(
                    new_inventory,
                    source_root=implementation,
                )
            ),
        },
        "commands_changed": old_inventory.get("stages") != new_inventory.get("stages"),
        "changes_required": (
            old_inventory != new_inventory
            or wrapper_path.read_bytes() != wrapper
            or project.definition.test_receipt_policy != expected_policy
            or project.definition.default_flavor_selectors != selectors
            or any(
                _safe_path(root, relative).read_bytes() != content.encode("utf-8")
                for relative, content in shim.items()
            )
            or _load_json(baseline_path).get("state") != "passed"
            or _load_json(parity_path).get("state") != "passed"
        ),
        "authority_review": document,
    }
    if declaration is not None:
        plan["layout_readmission"] = {
            "schema": "literate-ai/retained-layout-readmission@1",
            "layout_identity": declaration.identity,
            "implementation_directory": implementation_relative,
            "wrapper_component": layout.wrapper_component,
            "lift_shift_identity": _identity(_load_json(_safe_path(root, LIFT_SHIFT))),
            "inventory_identity": _identity(new_inventory),
            "source_tree_identity": source_tree["identity"],
            "wrapper_identity": _identity(wrapper),
        }
        plan["changes_required"] = plan["changes_required"] or any(
            _load_json(path).get("layout_readmission") != plan["layout_readmission"]
            for path in (baseline_path, parity_path)
        )
    # Re-open structural inputs after every inventory/document read. This closes
    # stale location, declaration and pending-state changes before exposing a plan.
    _require_layout_current(root, plan)
    if command_renewal is not None:
        current_inventory, current_renewal = _review_command_selection(
            implementation,
            command_selection,
            old_inventory,
            inspect_harness(implementation),
            wrapper_component=layout.wrapper_component,
            retained_stage_ids=retained_stage_ids,
        )
        # Workspace-link transport remains the existing separate owner.
        if "workspace_links" in old_inventory:
            current_inventory["workspace_links"] = old_inventory["workspace_links"]
        if current_renewal != command_renewal or current_inventory != new_inventory:
            _fail("command_selection_stale", "renewal source or selection changed")
        if any(
            _identity(_safe_path(root, relative).read_bytes()) != identity
            for relative, identity in old_documents.items()
        ):
            _fail("plan_stale", "project metadata changed during renewal planning")
        # Payload reads have finished. Close namespace, original known nodes and
        # physical ancestry without accepting replacement facts as a new snapshot.
        try:
            current_scope = capture_retained_source_scope(
                implementation,
                required_paths=tuple(
                    stage["evidence"] for stage in new_inventory["stages"]
                ),
            )
            unchanged = (
                current_scope == new_inventory["source_scope"]
                and all(_signature(path) == node for path, node in renewal_nodes)
                and all(_lineage(path) == node for path, node in renewal_ancestry)
            )
        except (OSError, RetainedLayoutError):
            unchanged = False
        if not unchanged:
            _fail("command_selection_stale", "renewal native inputs changed")
        plan["schema"] = "literate-ai/retained-harness-readmission-plan@2"
        plan["command_renewal"] = command_renewal
        plan["apply_supported"] = False
    plan["plan_identity"] = _identity(plan)
    if (
        command_renewal is not None
        and len(canonical_json_bytes(plan)) + 1 > DEFAULT_MAXIMUM_PINNED_INPUT_BYTES
    ):
        _fail("plan_too_large", "renewal plan exceeds the existing pinned-file limit")
    return plan


def reopen_retained_command_renewal_plan(
    selected: Path,
    content: bytes,
    *,
    reviewed_plan_identity: str,
    command_selection: Path,
    execution_worker: ExecutionWorker | None = None,
    worker_catalog_identity: ContentIdentity | None = None,
    timeout_seconds: int = 1800,
    retained_stage_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Reopen bounded saved intent against the actual current planning owner.

    Matching a self-hash is insufficient. Regeneration independently supplies
    the complete supported structure and current values, including nested
    inventories and command definitions. This reader supplies no apply grant.
    """
    try:
        if (
            type(content) is not bytes
            or len(content) > DEFAULT_MAXIMUM_PINNED_INPUT_BYTES
            or command_selection is None
        ):
            raise ValueError("invalid bounded renewal bytes")
        data = json.loads(content)
        encoded = canonical_json_bytes(data)
        if content not in (encoded, encoded + b"\n") or not isinstance(data, dict):
            raise ValueError("noncanonical renewal bytes")
        renewal = data.get("command_renewal")
        if (
            data.get("schema") != "literate-ai/retained-harness-readmission-plan@2"
            or data.get("apply_supported") is not False
            or not isinstance(renewal, dict)
            or renewal.get("schema")
            != "literate-ai/retained-command-renewal-planning@1"
            or renewal.get("apply_supported") is not False
            or renewal.get("execution_performed") is not False
            or renewal.get("compilation_coverage") != "unknown"
        ):
            raise ValueError("unsupported renewal form or authority")
        identity = _identity(
            {key: value for key, value in data.items() if key != "plan_identity"}
        )
        if data.get("plan_identity") != identity:
            raise ValueError("renewal body differs from its identity")
        ContentIdentity.parse_uri(reviewed_plan_identity)
    except (ValueError, TypeError, RecursionError, OverflowError):
        _fail("plan_invalid", "saved renewal plan is invalid or unsupported")
    if identity != reviewed_plan_identity:
        _fail("plan_stale", "saved renewal plan differs from the reviewed identity")
    current = plan_retained_harness_readmission(
        selected,
        command_selection=command_selection,
        execution_worker=execution_worker,
        worker_catalog_identity=worker_catalog_identity,
        timeout_seconds=timeout_seconds,
        retained_stage_ids=retained_stage_ids,
    )
    if canonical_json_bytes(current) != encoded:
        _fail(
            "plan_stale", "saved renewal differs from complete current planning inputs"
        )
    return current


def _require_layout_current(root: Path, plan: dict[str, Any]) -> None:
    # Capture known native inputs before parsing any layout/history payloads.
    # The final pass below reads no payloads and never accepts resampled facts.
    ancestry = _lineage(root / ".literate")
    nodes = []
    for relative in (CONVERSION_AUTHORITY_FILE, LIFT_SHIFT, RETAINED_LAYOUT_PATH):
        path = root / relative
        try:
            node = _signature(path)
        except FileNotFoundError:
            node = None
        nodes.append((path, node))
    layout = _layout(root)
    if (
        layout.implementation_directory != plan["implementation"]
        or layout.wrapper_component != plan["wrapper_component"]
    ):
        _fail("layout_changed", "retained layout changed during readmission")
    declaration = read_retained_layout_declaration(root)
    expected = plan.get("layout_readmission")
    if (declaration is None) != (expected is None) or (
        declaration is not None and declaration.identity != expected["layout_identity"]
    ):
        _fail("layout_changed", "retained declaration changed during readmission")
    for relative in (CONVERSION_AUTHORITY_FILE, LIFT_SHIFT, RETAINED_LAYOUT_PATH):
        if relative in plan["old_documents"] and (
            _identity(_safe_path(root, relative).read_bytes())
            != plan["old_documents"][relative]
        ):
            _fail("layout_changed", "retained layout inputs changed during readmission")
    if _lineage(root / ".literate") != ancestry:
        _fail("layout_changed", "retained layout ancestry changed during readmission")
    # Pending absence is observed after all payload reads, then original known
    # file facts close changes made during that observation. No payload follows.
    if os.path.lexists(root / "litai/layout.pending"):
        _fail("layout_pending", "pending relocation requires explicit recovery")
    for path, expected_node in nodes:
        try:
            current_node = _signature(path)
        except FileNotFoundError:
            current_node = None
        if current_node != expected_node:
            _fail(
                "layout_changed",
                "retained layout native inputs changed during readmission",
            )
    if _lineage(root / ".literate") != ancestry:
        _fail("layout_changed", "retained layout ancestry changed during readmission")


def _source_native_inputs(root: Path, paths: tuple[str, ...]):
    nodes = {root}
    for relative in paths:
        path = root / relative
        nodes.add(path)
        nodes.update(parent for parent in path.parents if parent.is_relative_to(root))
    facts = tuple((path, _signature(path)) for path in sorted(nodes))
    parents = {root}
    parents.update((root / relative).parent for relative in paths)
    ancestry = tuple((path, _lineage(path)) for path in sorted(parents))
    return facts, ancestry


class _ReadmissionSourceInputs:
    """Finite original-source observation, distinct from saved plan assertions."""

    def __init__(self, key, root, scope):
        from literate_ai.adapters.harness_tree import _validated_scope

        if key is not _SOURCE_INPUTS_KEY:
            raise TypeError("original readmission source owner required")
        self.root = root
        self.scope = json.loads(canonical_json_bytes(scope))
        self.paths, _excluded = _validated_scope(self.scope)
        self.closed = False
        self.nodes, self.ancestry = _source_native_inputs(root, self.paths)
        self.raw = observe_retained_source_bytes(root, self.scope)
        if self.raw["missing_count"]:
            _fail("source_changed", "original retained source is missing")

    def require_current(self):
        if self.closed:
            _fail("source_inputs_expired", "original source observation is closed")
        try:
            paths = capture_retained_source_scope(self.root, required_paths=self.paths)[
                "paths"
            ]
            current = (
                paths == list(self.paths)
                and all(_signature(path) == fact for path, fact in self.nodes)
                and all(_lineage(path) == fact for path, fact in self.ancestry)
            )
        except (OSError, ValueError, RetainedLayoutError):
            current = False
        if not current:
            _fail("source_changed", "original retained source changed")

    def require_for(self, root, inventory):
        if root != self.root or inventory["source_scope"] != self.scope:
            _fail("source_changed", "source observation belongs to another operation")
        self.require_current()

    def require_copy(self, root):
        self.require_current()
        try:
            nodes, ancestry = _source_native_inputs(root, self.paths)
            _require_initial_copy_namespace(root, self.paths)
            raw = observe_retained_source_bytes(root, self.scope)
            _require_initial_copy_namespace(root, self.paths)
            self.require_current()
            current = (
                raw == self.raw
                and all(_signature(path) == fact for path, fact in nodes)
                and all(_lineage(path) == fact for path, fact in ancestry)
            )
        except (OSError, ValueError, RetainedLayoutError):
            current = False
        if not current:
            _fail("source_changed", "disposable source differs from original inputs")


def _require_initial_copy_namespace(root, paths):
    children: dict[Path, set[str]] = {root: set()}
    for relative in paths:
        path = root / relative
        while path != root:
            children.setdefault(path.parent, set()).add(path.name)
            path = path.parent
    for directory, expected in children.items():
        found = set()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name not in expected:
                    _fail("source_changed", "unexpected initial disposable source name")
                found.add(entry.name)
        if found != expected:
            _fail("source_changed", "initial disposable source name is missing")


@contextmanager
def _readmission_source_inputs(implementation, inventory, *, expected_tree=None):
    try:
        inputs = _ReadmissionSourceInputs(
            _SOURCE_INPUTS_KEY, implementation, inventory["source_scope"]
        )
    except (OSError, ValueError, RetainedLayoutError):
        _fail("source_changed", "original retained source is unavailable or redirected")
    try:
        if (
            expected_tree is not None
            and observe_retained_tree(implementation, inputs.scope)["source_tree"]
            != expected_tree
        ):
            _fail("source_changed", "original source differs from the reviewed plan")
        inputs.require_current()
        yield inputs
    finally:
        try:
            inputs.require_current()
        finally:
            inputs.closed = True


def _baseline_report(
    inventory: dict[str, Any],
    *,
    implementation: Path,
    timeout_seconds: int,
    worker: ExecutionWorker | None,
    worker_catalog_identity: ContentIdentity | None,
    plan_identity: ContentIdentity,
    project_id: str,
    executor: RetainedHarnessSshExecutor,
    source_inputs: _ReadmissionSourceInputs | None = None,
) -> dict[str, Any]:
    if source_inputs is None:
        with _readmission_source_inputs(implementation, inventory) as inputs:
            return _baseline_report(
                inventory,
                implementation=implementation,
                timeout_seconds=timeout_seconds,
                worker=worker,
                worker_catalog_identity=worker_catalog_identity,
                plan_identity=plan_identity,
                project_id=project_id,
                executor=executor,
                source_inputs=inputs,
            )
    if type(source_inputs) is not _ReadmissionSourceInputs:
        _fail("source_changed", "original source observation is required")
    source_inputs.require_for(implementation, inventory)
    if worker is None:
        with tempfile.TemporaryDirectory(prefix="litai-readmit-direct-") as directory:
            execution_root = Path(directory).resolve() / "legacy"
            copy_retained_source_tree(
                implementation, execution_root, inventory["source_scope"]
            )
            source_inputs.require_copy(execution_root)
            result = execute_harness_baseline(
                inventory,
                legacy_root=execution_root,
                timeout_seconds=timeout_seconds,
                run_baseline=True,
            )
            source_inputs.require_current()
            return result
    assert worker_catalog_identity is not None
    observed = observe_retained_tree(implementation, inventory["source_scope"])[
        "source_tree"
    ]
    result = executor.execute(
        worker,
        project_id=project_id,
        project_revision_identity=plan_identity,
        worker_catalog_identity=worker_catalog_identity,
        runner_identity=retained_harness_runner_identity(inventory),
        lifecycle_request_identity=canonical_identity(
            {"operation": "retained-harness.readmit", "phase": "direct"}
        ),
        inventory=inventory,
        inventory_bytes=canonical_json_bytes(inventory),
        source_root=implementation,
        source_identity=ContentIdentity.parse_uri(str(observed["identity"])),
        timeout_seconds=timeout_seconds,
        cwd=implementation,
    )
    source_inputs.require_current()
    phases = [dict(item) for item in result.phases]
    return {
        "schema": HARNESS_BASELINE_SCHEMA,
        "state": "passed",
        "timeout_seconds": timeout_seconds,
        "diagnostic_limit_chars": HARNESS_DIAGNOSTIC_CHARS,
        "source_scope": inventory["source_scope"],
        "legacy_source_tree_before": observed,
        "legacy_source_tree_after": observed,
        "phases": phases,
        "phase_count": len(phases),
        "ci": {
            **classify_ci(inventory["findings"], inventory["commands"]),
            "state": "recorded",
        },
        "execution_worker_identity": worker.identity.uri,
        "platform": result.platform,
    }


def _parity_inventory(inventory: dict[str, Any], source_root: Path) -> dict[str, Any]:
    stages = []
    for stage in inventory["stages"]:
        if stage["id"].split(".", 1)[0] not in {"build", "test", "package", "ci"}:
            continue
        stages.append(
            {
                **stage,
                "command": (
                    f"make -f {HARNESS_WRAPPER_FILENAME} {stage['id']} "
                    "LITAI_LEGACY=legacy"
                ),
                "cwd": ".",
                "evidence": HARNESS_WRAPPER_FILENAME,
            }
        )
    commands = {
        stage["id"]: {
            key: value
            for key, value in stage.items()
            if key in {"command", "cost", "cwd", "evidence", "id"}
        }
        for stage in stages
    }
    rebound = {**inventory, "stages": stages, "commands": commands}
    source_scope = inventory.get("source_scope")
    source_paths = source_scope.get("paths") if isinstance(source_scope, dict) else None
    if not isinstance(source_paths, list) or any(
        not isinstance(path, str) for path in source_paths
    ):
        raise ValueError("retained parity source scope is invalid")
    # The wrapper projection is intentionally outside Git. Its filesystem scan
    # still excludes newly generated output, but must not reinterpret paths the
    # direct Git-visible baseline already admitted (for example include/build/*).
    rebound["source_scope"] = capture_retained_source_scope(
        source_root,
        required_paths=(
            HARNESS_WRAPPER_FILENAME,
            *(f"legacy/{path}" for path in source_paths),
        ),
    )
    return rebound


def _parity_report(
    inventory: dict[str, Any],
    baseline: dict[str, Any],
    wrapper: bytes,
    *,
    implementation: Path,
    timeout_seconds: int,
    worker: ExecutionWorker | None,
    worker_catalog_identity: ContentIdentity | None,
    plan_identity: ContentIdentity,
    project_id: str,
    executor: RetainedHarnessSshExecutor,
    source_inputs: _ReadmissionSourceInputs | None = None,
) -> dict[str, Any]:
    if source_inputs is None:
        with _readmission_source_inputs(implementation, inventory) as inputs:
            return _parity_report(
                inventory,
                baseline,
                wrapper,
                implementation=implementation,
                timeout_seconds=timeout_seconds,
                worker=worker,
                worker_catalog_identity=worker_catalog_identity,
                plan_identity=plan_identity,
                project_id=project_id,
                executor=executor,
                source_inputs=inputs,
            )
    if type(source_inputs) is not _ReadmissionSourceInputs:
        _fail("source_changed", "original source observation is required")
    source_inputs.require_for(implementation, inventory)
    if worker is None:
        with tempfile.TemporaryDirectory(prefix="litai-readmit-wrapper-") as directory:
            project_root = Path(directory).resolve()
            (project_root / HARNESS_WRAPPER_FILENAME).write_bytes(wrapper)
            result = execute_harness_wrapper_parity(
                inventory,
                baseline,
                project_root=project_root,
                legacy_root=implementation,
                timeout_seconds=timeout_seconds,
                initial_source_guard=source_inputs.require_copy,
            )
            source_inputs.require_current()
            return result
    assert worker_catalog_identity is not None
    with tempfile.TemporaryDirectory(prefix="litai-readmit-wrapper-") as directory:
        source_root = Path(directory).resolve()
        legacy = source_root / "legacy"
        copy_retained_source_tree(implementation, legacy, inventory["source_scope"])
        source_inputs.require_copy(legacy)
        (source_root / HARNESS_WRAPPER_FILENAME).write_bytes(wrapper)
        parity_inventory = _parity_inventory(inventory, source_root)
        observed = observe_retained_tree(source_root, parity_inventory["source_scope"])[
            "source_tree"
        ]
        source_capture_attempts = 0
        while True:
            source_capture_attempts += 1
            try:
                source_inputs.require_current()
                result = executor.execute(
                    worker,
                    project_id=project_id,
                    project_revision_identity=plan_identity,
                    worker_catalog_identity=worker_catalog_identity,
                    runner_identity=retained_harness_runner_identity(parity_inventory),
                    lifecycle_request_identity=canonical_identity(
                        {
                            "operation": "retained-harness.readmit",
                            "phase": "wrapper",
                        }
                    ),
                    inventory=parity_inventory,
                    inventory_bytes=canonical_json_bytes(parity_inventory),
                    source_root=source_root,
                    source_identity=ContentIdentity.parse_uri(
                        str(observed["identity"])
                    ),
                    timeout_seconds=timeout_seconds,
                    cwd=implementation,
                )
                source_inputs.require_current()
                break
            except RetainedHarnessRemoteError as exc:
                if (
                    exc.code != "retained_receipt.remote_source_capture_failed"
                    or source_capture_attempts >= _PARITY_SOURCE_CAPTURE_ATTEMPTS
                ):
                    raise
    direct = {
        item["phase"]: item
        for item in baseline["phases"]
        if isinstance(item, dict) and isinstance(item.get("phase"), str)
    }
    phases: list[dict[str, Any]] = []
    for item in result.phases:
        compared = direct.get(item["phase"])
        equal = (
            compared is not None
            and item["exit_code"] == compared.get("exit_code")
            and item["timed_out"] == compared.get("timed_out")
            and item.get("test_collection") == compared.get("test_collection")
        )
        phases.append(
            {
                **item,
                "baseline_source_tree": compared.get("source_tree")
                if compared
                else None,
                "parity": equal,
            }
        )
        if not equal:
            _fail(
                "wrapper_parity_failed",
                "generated wrapper differs from direct execution",
            )
    return {
        "schema": HARNESS_PARITY_SCHEMA,
        "state": "passed",
        "baseline_schema": baseline["schema"],
        "timeout_seconds": timeout_seconds,
        "diagnostic_limit_chars": HARNESS_DIAGNOSTIC_CHARS,
        "phases": phases,
        "phase_count": len(phases),
        "source_capture_attempts": source_capture_attempts,
        "execution_worker_identity": worker.identity.uri,
        "platform": result.platform,
    }


def _history_evidence(
    root: Path,
    *,
    plan_identity: ContentIdentity,
    before: dict[str, bytes],
) -> tuple[Path, bool]:
    history_root = _safe_path(
        root,
        f"{HISTORY}/{plan_identity.digest}.evidence",
        must_exist=False,
    )
    if history_root.exists():
        if not history_root.is_dir() or any(
            _safe_path(history_root, relative).read_bytes() != content
            for relative, content in before.items()
        ):
            _fail("history_collision", "prior-evidence history has different bytes")
        return history_root, False
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{plan_identity.digest}.",
            dir=history_root.parent,
        )
    )
    try:
        for relative, content in before.items():
            destination = staging.joinpath(*PurePosixPath(relative).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        os.replace(staging, history_root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return history_root, True


def apply_retained_harness_readmission(
    selected: Path,
    *,
    expected_plan_identity: str,
    acknowledge: bool,
    timeout_seconds: int,
    execution_worker: ExecutionWorker | None,
    worker_catalog_identity: ContentIdentity | None,
    retained_stage_ids: tuple[str, ...] = (),
    remote_executor: RetainedHarnessSshExecutor | None = None,
) -> dict[str, Any]:
    """Qualify and atomically publish one freshly re-inspected harness."""

    if acknowledge is not True:
        _fail("acknowledgement_required", "readmission requires acknowledgement")
    project = load_project(selected)
    with project_lifecycle_lock(project.root, operation="retained-harness.readmit"):
        plan = plan_retained_harness_readmission(
            project.root,
            execution_worker=execution_worker,
            worker_catalog_identity=worker_catalog_identity,
            timeout_seconds=timeout_seconds,
            retained_stage_ids=retained_stage_ids,
        )
        if plan["plan_identity"] != expected_plan_identity:
            _fail("plan_stale", "source or metadata changed after review")
        if not plan["changes_required"]:
            return {**plan, "applied": False}
        root = project.root
        implementation = root / plan["implementation"]
        inventory = plan["new_inventory"]
        wrapper = render_harness_wrapper(
            inventory, legacy_directory=plan["implementation"]
        ).encode("utf-8")
        executor = remote_executor or RetainedHarnessSshExecutor()
        plan_identity = ContentIdentity.parse_uri(plan["plan_identity"])
        with _readmission_source_inputs(
            implementation, inventory, expected_tree=plan["source_tree"]
        ) as source_inputs:
            baseline = _baseline_report(
                inventory,
                implementation=implementation,
                timeout_seconds=timeout_seconds,
                worker=execution_worker,
                worker_catalog_identity=worker_catalog_identity,
                plan_identity=plan_identity,
                project_id=project.definition.project_id,
                executor=executor,
                source_inputs=source_inputs,
            )
            parity = _parity_report(
                inventory,
                baseline,
                wrapper,
                implementation=implementation,
                timeout_seconds=timeout_seconds,
                worker=execution_worker,
                worker_catalog_identity=worker_catalog_identity,
                plan_identity=plan_identity,
                project_id=project.definition.project_id,
                executor=executor,
                source_inputs=source_inputs,
            )
        _require_layout_current(root, plan)
        if "layout_readmission" in plan:
            if baseline.get("state") != "passed" or parity.get("state") != "passed":
                _fail("layout_unqualified", "fresh baseline and parity must pass")
            baseline["layout_readmission"] = plan["layout_readmission"]
            parity["layout_readmission"] = plan["layout_readmission"]
        shim = legacy_shim_authority(
            inventory, baseline, wrapper_component=plan["wrapper_component"]
        )
        paths = {
            INVENTORY: _safe_path(root, INVENTORY),
            BASELINE: _safe_path(root, BASELINE),
            PARITY: _safe_path(root, PARITY),
            HARNESS_WRAPPER_FILENAME: _safe_path(root, HARNESS_WRAPPER_FILENAME),
            "literate.project.json": _safe_path(root, "literate.project.json"),
            plan["authority_review"]: _safe_path(root, plan["authority_review"]),
        }
        for relative in shim:
            paths[relative] = _safe_path(root, relative)
        wrapper_component = plan["wrapper_component"]
        for relative in (
            f"{wrapper_component}/component.lock.json",
            f"{wrapper_component}/component.resolution-audit.host.json",
        ):
            paths[relative] = _safe_path(root, relative)
        before = {name: path.read_bytes() for name, path in paths.items()}
        if any(
            _identity(content) != plan["old_documents"][name]
            for name, content in before.items()
        ):
            _fail("plan_stale", "project metadata changed before publication")
        for relative in (LIFT_SHIFT, RETAINED_LAYOUT_PATH):
            if relative in plan["old_documents"]:
                before[relative] = _safe_path(root, relative).read_bytes()
                if _identity(before[relative]) != plan["old_documents"][relative]:
                    _fail("layout_changed", "layout changed before history publication")
        history = _safe_path(
            root,
            f"{HISTORY}/{plan_identity.digest}.json",
            must_exist=False,
        )
        history.parent.mkdir(parents=True, exist_ok=True)
        history_bytes = canonical_json_bytes(plan) + b"\n"
        created_history = False
        if history.exists():
            if history.read_bytes() != history_bytes:
                _fail("history_collision", "readmission history has different bytes")
        else:
            with history.open("xb") as stream:
                stream.write(history_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            created_history = True
        evidence_history, created_evidence_history = _history_evidence(
            root,
            plan_identity=plan_identity,
            before=before,
        )
        written: dict[str, bytes] = {}
        try:
            replacements = {
                INVENTORY: canonical_json_bytes(inventory) + b"\n",
                BASELINE: canonical_json_bytes(baseline) + b"\n",
                PARITY: canonical_json_bytes(parity) + b"\n",
                HARNESS_WRAPPER_FILENAME: wrapper,
                **{
                    relative: content.encode("utf-8")
                    for relative, content in shim.items()
                },
            }
            for name, content in replacements.items():
                _require_layout_current(root, plan)
                FilesystemConversionAuthorityStore._atomic_write(paths[name], content)
                written[name] = content
            store = ProjectConfigurationStore(root)
            snapshot = store.read()
            updated = store.update(
                snapshot,
                replace(
                    snapshot.definition,
                    test_receipt_policy=retained_harness_receipt_policy(inventory),
                    default_flavor_selectors=tuple(
                        plan["new_default_flavor_selectors"]
                    ),
                ),
            )
            written["literate.project.json"] = updated.content
            from literate_ai.adapters.component_lock_commands import (
                _component_locks_from_args,
            )

            lock_paths = (
                f"{wrapper_component}/component.lock.json",
                f"{wrapper_component}/component.resolution-audit.host.json",
            )
            try:
                lock_result, lock_status = _component_locks_from_args(
                    Namespace(
                        component=str(root / wrapper_component),
                        target="host",
                        flavor_root=[],
                        flavor=[],
                        check=False,
                        diff=False,
                        large_review=None,
                    )
                )
            finally:
                for relative in lock_paths:
                    current = paths[relative].read_bytes()
                    if current != before[relative]:
                        written[relative] = current
            if lock_status != 0:
                _fail(
                    "lock_reconciliation_failed",
                    f"component lock reconciliation failed: {lock_result}",
                )
            review = FilesystemProjectValidationAdapter().documentation_review(root)
            review_name = plan["authority_review"]
            review_content = AUTHORITY_REVIEW_MARKER.sub(
                review["expected_marker"].encode("utf-8"),
                before[review_name],
                count=1,
            )
            written[review_name] = review_content
            record_project_authority_review(root)
            current_inventory = inspect_harness(implementation)
            current_source_tree = observe_retained_tree(
                implementation, current_inventory["source_scope"]
            )["source_tree"]
            if (
                current_inventory["source_scope"] != inventory["source_scope"]
                or current_source_tree != plan["source_tree"]
            ):
                _fail("source_changed", "source changed during readmission")
            for relative in (CONVERSION_AUTHORITY_FILE, LIFT_SHIFT):
                if (
                    _identity(_safe_path(root, relative).read_bytes())
                    != plan["old_documents"][relative]
                ):
                    _fail(
                        "historical_evidence_changed",
                        "conversion authority or lift-and-shift evidence changed",
                    )
            _require_layout_current(root, plan)
        except BaseException:
            for name, content in reversed(tuple(written.items())):
                if paths[name].read_bytes() == content:
                    FilesystemConversionAuthorityStore._atomic_write(
                        paths[name], before[name]
                    )
            if created_history and history.read_bytes() == history_bytes:
                history.unlink()
            if created_evidence_history:
                shutil.rmtree(evidence_history)
            raise
        return {
            **plan,
            "applied": True,
            "history": history.relative_to(root).as_posix(),
            "prior_evidence_history": evidence_history.relative_to(root).as_posix(),
            "baseline_identity": _identity(baseline),
            "parity_identity": _identity(parity),
        }
