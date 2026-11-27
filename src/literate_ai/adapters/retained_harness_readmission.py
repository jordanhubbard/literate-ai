"""Reviewed replacement of an unqualified retained harness after adoption."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import weakref
from argparse import Namespace
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

from literate_ai._atomic_publication import atomic_publication_scope
from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.component_markdown import parse_component_markdown
from literate_ai.adapters.conversion_authority import (
    CONVERSION_AUTHORITY_FILE,
    FilesystemConversionAuthorityStore,
)
from literate_ai.adapters.flavor_markdown import parse_flavor_markdown
from literate_ai.adapters.harness_inventory import (
    HARNESS_BASELINE_SCHEMA,
    HARNESS_DIAGNOSTIC_CHARS,
    HARNESS_PARITY_SCHEMA,
    HARNESS_WRAPPER_FILENAME,
    classify_ci,
    execute_harness_baseline,
    execute_harness_wrapper_parity,
    inspect_harness,
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
    ProjectInitializationError,
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
from literate_ai.adapters.retained_readmission_publication import (
    ReadmissionPublication,
    ReadmissionPublicationError,
    publish_readmission_evidence,
)
from literate_ai.contracts import (
    ContentIdentity,
    ExecutionWorker,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import (
    DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
    DEFAULT_MAXIMUM_PINNED_INPUT_FILES,
    DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES,
    PinnedInputClosure,
    ProjectConfigurationStore,
    configured_catalog_path,
    load_project,
)

from .retained_scaffold_coordinates import (
    retained_scaffold_path,
    retained_shim_authority,
)

PLAN_SCHEMA = "literate-ai/retained-harness-readmission-plan@1"
HISTORY = ".literate/retained-harness-readmission"
INVENTORY = ".literate/harness-inventory.json"
BASELINE = ".literate/legacy-harness-baseline.json"
PARITY = ".literate/legacy-wrapper-parity.json"
LIFT_SHIFT = ".literate/legacy-lift-shift.json"
_AUTHORITY_OUTPUTS = frozenset(
    {
        INVENTORY,
        BASELINE,
        PARITY,
        HARNESS_WRAPPER_FILENAME,
        "literate.project.json",
        "components/legacy-project-wrapper/component.md",
        "components/legacy-project-wrapper/component.lock.json",
        "components/legacy-project-wrapper/component.resolution-audit.host.json",
    }
)
_PARITY_SOURCE_CAPTURE_ATTEMPTS = 2
_SOURCE_INPUTS_KEY = object()
_PHASE_LIST = (
    r"(?:none|`(?:build|test|package|ci)`(?:, `(?:build|test|package|ci)`){0,3})"
)
_BASELINE_SUMMARY = re.compile(
    r"^This Component exposes the quarantined project's proven pipeline "
    r"through the\r?\n"
    r"top-level `litai\.harness\.mk` boundary\. "
    r"Proven stages \(direct baseline ran\) are\r?\n"
    + _PHASE_LIST
    + r"; recorded but not executed are "
    + _PHASE_LIST
    + r"; missing stages are\r?\n"
    + _PHASE_LIST
    + r" and fail loudly rather than becoming silent no-ops\.(?=\r?$)",
    re.MULTILINE,
)


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


def _baseline_summaries(content: str) -> list[re.Match[str]]:
    """Recognize prose facts without editing a quoted Markdown example."""
    excluded: list[tuple[int, int]] = []
    fence: str | None = None
    start = offset = 0
    for line in content.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if marker:
            token, rest = marker.groups()
            if fence is None:
                fence, start = token, offset
            elif token[0] == fence[0] and len(token) >= len(fence) and not rest.strip():
                excluded.append((start, offset + len(line)))
                fence = None
        offset += len(line)
    if fence is not None:
        excluded.append((start, len(content)))
    return [
        match
        for match in _BASELINE_SUMMARY.finditer(content)
        if not any(start <= match.start() < end for start, end in excluded)
    ]


def _readmitted_shim_authority(
    root: Path,
    inventory: dict[str, Any],
    baseline: dict[str, Any],
    *,
    wrapper_component: str | None = None,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Keep authored authority; update only the recognized generated facts."""
    wrapper_component = wrapper_component or _layout(root).wrapper_component
    generated = retained_shim_authority(
        root, inventory, baseline, wrapper_component=wrapper_component
    )
    component = f"{wrapper_component}/component.md"
    preserved: dict[str, str] = {}
    for relative in generated:
        try:
            preserved[relative] = (
                _safe_path(root, relative).read_bytes().decode("utf-8")
            )
        except UnicodeError:
            _fail(
                "shim_authority_invalid", "Existing shim authority must be valid UTF-8"
            )
    before = dict(preserved)
    old_matches = _baseline_summaries(before[component])
    new_matches = _baseline_summaries(generated[component])
    if len(old_matches) != 1 or len(new_matches) != 1:
        _fail(
            "shim_ownership_ambiguous",
            "Readmission requires one recognized baseline summary; "
            "authored authority was preserved",
        )
    old = old_matches[0]
    old_summary = old.group()
    new_summary = new_matches[0].group()
    if "\r\n" in old_summary:
        new_summary = new_summary.replace("\n", "\r\n")
    preserved[component] = (
        before[component][: old.start()] + new_summary + before[component][old.end() :]
    )
    changes = []
    for relative, content in preserved.items():
        changed = content != before[relative]
        changes.append(
            {
                "path": relative,
                "before_identity": _identity(before[relative].encode("utf-8")),
                "after_identity": _identity(content.encode("utf-8")),
                "change": "baseline-summary" if changed else "preserved",
                # Only fixed framework text and closed phase labels enter the plan.
                "before_summary": old_summary if changed else None,
                "after_summary": new_summary if changed else None,
            }
        )
    return preserved, changes


def _safe_path(root: Path, relative: str, *, must_exist: bool = True) -> Path:
    raw = PurePosixPath(relative)
    if (
        raw.is_absolute()
        or raw.as_posix() != relative
        or any(part in {"", ".", ".."} for part in raw.parts)
    ):
        _fail("unsafe_path", f"metadata path is unsafe: {relative}")
    # Only these implicit producer coordinates are rebased. Declared document,
    # shim and source paths retain their application-relative meaning.
    if raw.parts[0] == ".literate" or relative in {
        "literate.project.json",
        HARNESS_WRAPPER_FILENAME,
    }:
        relative = retained_scaffold_path(root, relative).relative_to(root).as_posix()
        raw = PurePosixPath(relative)
    path = root
    for part in raw.parts:
        path = path / part
        if path.is_symlink():
            _fail("unsafe_path", f"metadata path must not traverse a link: {relative}")
    if must_exist and not path.is_file():
        _fail("metadata_missing", f"required metadata is unavailable: {relative}")
    return path


def _require_written_documents(root: Path, expected: dict[str, bytes]) -> None:
    """Refuse late metadata edits without adopting them as readmission output."""
    for relative, content in expected.items():
        try:
            unchanged = _safe_path(root, relative).read_bytes() == content
        except (OSError, RetainedHarnessReadmissionError):
            unchanged = False
        if not unchanged:
            _fail("metadata_changed", "Project metadata changed during readmission")


def _stable_authority_identity(
    root: Path, review: dict[str, Any], *, project_definition: str | None = None
) -> str:
    """Bind all review inputs outside the exact authority this operation replaces."""
    wrapper_component = _layout(root).wrapper_component
    component = _safe_path(root, f"{wrapper_component}/component.md")
    coordinate = parse_component_markdown(
        component, component.read_bytes().decode("utf-8"), project_root=root
    ).coordinate.uri
    inputs = review["inputs"]
    if sum(item["coordinate"] == coordinate for item in inputs["components"]) != 1:
        _fail("authority_review_invalid", "Wrapper authority is ambiguous")
    outputs = {
        _safe_path(root, name).relative_to(root).as_posix()
        for name in (
            INVENTORY,
            BASELINE,
            PARITY,
            HARNESS_WRAPPER_FILENAME,
            "literate.project.json",
            *(
                f"{wrapper_component}/{name}"
                for name in (
                    "component.md",
                    "component.lock.json",
                    "component.resolution-audit.host.json",
                )
            ),
        )
    }
    stable = {
        **inputs,
        "components": [
            item for item in inputs["components"] if item["coordinate"] != coordinate
        ],
        **{
            key: [item for item in inputs[key] if item["path"] not in outputs]
            for key in ("documentation", "documentation_assets")
        },
    }
    if project_definition is not None:
        stable["project_definition"] = project_definition
    return _identity(stable)


def _preserved_authority_inputs(
    root: Path, *, wrapper_component: str, shim_paths
) -> PinnedInputClosure:
    """Fence referenced authored files while the generated summary is replaced."""
    project = load_project(root)
    closure = PinnedInputClosure.for_project(project)
    component = _safe_path(root, f"{wrapper_component}/component.md")
    authored = parse_component_markdown(
        component, component.read_bytes().decode("utf-8"), project_root=root
    )

    def pin(path: Path, expected_identity: ContentIdentity | None = None) -> None:
        # The Component itself is fenced by old_documents and intentionally may
        # acquire new baseline facts. All other referenced bytes must survive.
        if path == component:
            return
        closure.pin(
            path,
            boundary=root,
            label="readmission:" + path.relative_to(root).as_posix(),
            expected_identity=expected_identity,
        )

    for uri in authored.specification_roots:
        pin(component.parent / uri)
    global_kinds = {
        "model-selection",
        "routing-policy",
        "specification-to-source-skill",
        "toolchain-constraint",
        "workflow",
    }
    selectors = (
        authored.workflow_definition,
        authored.routing_policy,
        *authored.authoring_inputs,
        *authored.acceptance_contracts,
        *(item.interface for item in authored.provides if item.interface is not None),
        *(
            item.integration_contract
            for item in authored.source_dependencies
            if item.integration_contract is not None
        ),
    )
    for selector in selectors:
        base = root if selector.kind in global_kinds else component.parent
        pin(
            configured_catalog_path(root, base, selector.uri, kind=selector.kind),
            selector.pin,
        )
    flavors = tuple(name for name in shim_paths if Path(name).name == "flavor.md")
    if len(flavors) != 1:
        _fail("shim_ownership_ambiguous", "retained shim Flavor authority is ambiguous")
    flavor_path = _safe_path(root, flavors[0])
    flavor = parse_flavor_markdown(flavor_path.read_bytes(), source=str(flavor_path))
    for uri in (
        *flavor.specification_roots,
        *(item.uri for item in flavor.authoring_inputs),
        *(item.content.uri for item in flavor.contributions),
    ):
        pin(flavor_path.parent / uri)
    closure.require_unchanged()
    return closure


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
    shim, shim_changes = _readmitted_shim_authority(
        root,
        new_inventory,
        {
            "schema": HARNESS_BASELINE_SCHEMA,
            "state": "passed",
            "phases": expected_phases,
        },
        wrapper_component=layout.wrapper_component,
    )
    preserved_inputs = _preserved_authority_inputs(
        root, wrapper_component=layout.wrapper_component, shim_paths=shim
    )
    review = FilesystemProjectValidationAdapter().documentation_review(
        root, include_inputs=True
    )
    preserved_inputs.require_unchanged()
    document = review.get("document")
    if review.get("state") not in {"current", "stale"} or not isinstance(document, str):
        _fail("authority_review_invalid", "project documentation authority is invalid")
    review_path = _safe_path(root, document)
    new_project_definition = replace(
        project.definition,
        test_receipt_policy=expected_policy,
        default_flavor_selectors=selectors,
    ).identity.uri
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
    for change in shim_changes:
        old_documents[change["path"]] = change["before_identity"]
    component_root = layout.wrapper_root
    for path in (
        component_root / "component.lock.json",
        component_root / "component.resolution-audit.host.json",
    ):
        relative = path.relative_to(root).as_posix()
        old_documents[relative] = _identity(_safe_path(root, relative).read_bytes())
    if command_renewal is not None:
        metadata_paths = tuple(_safe_path(root, relative) for relative in old_documents)
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
        "shim_authority_changes": shim_changes,
        "preserved_authority_inputs": preserved_inputs.to_dict(),
        "old_authority_identity": review["authority_identity"],
        "stable_authority_identity": _stable_authority_identity(
            root, review, project_definition=new_project_definition
        ),
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


_EXECUTION_PLAN_SCHEMA = "literate-ai/retained-harness-readmission-plan@3"
_EXECUTION_RENEWAL_SCHEMA = "literate-ai/retained-command-renewal@1"
_REFINED_EXECUTION_PLAN_SCHEMA = "literate-ai/retained-harness-readmission-plan@4"
_REFINED_EXECUTION_RENEWAL_SCHEMA = "literate-ai/retained-command-renewal@2"


def _prior_receipt_inputs(selected):
    """Read old receipt bytes as bounded history inputs, never as admission."""
    from literate_ai.adapters.monorepo_adoption import _consume_direct_file

    snapshot = ProjectConfigurationStore(selected).read()
    name = snapshot.definition.test_receipt
    path = _safe_path(snapshot.root, name, must_exist=False) if name else None
    node = None
    digest = hashlib.sha256()
    if path is not None:
        require_safe_directory(path.parent, allow_missing=True)
    parent = (
        next((p for p in path.parents if p.is_dir()), snapshot.root)
        if path
        else snapshot.root
    )
    ancestry = _lineage(parent)
    if path is not None and os.path.lexists(path):
        node = _signature(path)
        _consume_direct_file(
            path,
            digest.update,
            maximum_bytes=DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
        )
    binding = {
        "path": name,
        "state": "present"
        if node is not None
        else "missing"
        if name
        else "unconfigured",
        "identity": "sha256:" + digest.hexdigest() if node is not None else None,
    }

    def close():
        if _lineage(parent) != ancestry:
            _fail("prior_receipt_changed", "prior receipt ancestry changed")
        if path is not None:
            require_safe_directory(path.parent, allow_missing=True)
            _safe_path(snapshot.root, name, must_exist=False)
            current = _signature(path) if os.path.lexists(path) else None
            if current != node:
                _fail("prior_receipt_changed", "prior receipt changed during planning")

    close()
    return snapshot, binding, close


def _refined_command_execution_plan(
    selected, command_selection, *, prior_test_receipt, **options
):
    from literate_ai.adapters.monorepo_adoption import _consume_direct_file
    from literate_ai.adapters.retained_component_commands import (
        plan_installed_component_command_renewal,
    )
    from literate_ai.adapters.retained_readmission_publication import MAXIMUM_TARGETS

    if options.get("execution_worker") is not None:
        _fail(
            "refined_worker_unavailable", "refined renewal requires its local executor"
        )
    project = load_project(selected)
    limits = project.definition.scale_limits
    bounds = {
        "files": min(
            MAXIMUM_TARGETS,
            limits.pinned_input_files if limits else DEFAULT_MAXIMUM_PINNED_INPUT_FILES,
        ),
        "file_bytes": min(
            DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
            limits.pinned_input_total_bytes
            if limits
            else DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
        ),
        "total_bytes": min(
            DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES,
            limits.pinned_input_total_bytes
            if limits
            else DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES,
        ),
    }
    component_plan = plan_installed_component_command_renewal(
        project.root, command_selection, input_limits=bounds
    )
    old_inventory = _load_json(_safe_path(project.root, INVENTORY))
    retained = tuple(
        dict.fromkeys(
            [stage["id"] for stage in old_inventory["stages"]]
            + list(options.get("retained_stage_ids", ()))
        )
    )
    current = plan_retained_harness_readmission(
        project.root, **{**options, "retained_stage_ids": retained}
    )
    if current["implementation"] != component_plan["source_root"]:
        _fail("command_owner_invalid", "refined source differs from retained authority")
    names = [item["name"] for item in component_plan["old_selection"]["components"]]
    if PurePosixPath(current["wrapper_component"]).name in names:
        _fail("command_owner_invalid", "wrapper and refined Component roles overlap")
    relatives = {
        **current["old_documents"],
        **component_plan["old_documents"],
    }
    if prior_test_receipt["state"] == "present":
        relatives[prior_test_receipt["path"]] = prior_test_receipt["identity"]
    for name in names:
        for filename in ("component.lock.json", "component.resolution-audit.host.json"):
            relatives[f"components/{name}/{filename}"] = None
    nodes = {}
    ancestry = {}
    remaining = bounds["total_bytes"]
    if len(relatives) > bounds["files"]:
        _fail("publication_limit", "refined metadata exceeds the current file bound")
    for relative, expected in relatives.items():
        path = _safe_path(project.root, relative)
        nodes[path] = _signature(path)
        ancestry.setdefault(path.parent, _lineage(path.parent))
        if remaining < 1:
            _fail("publication_limit", "refined metadata exceeds its total byte bound")
        chunks = []
        _consume_direct_file(
            path, chunks.append, maximum_bytes=min(bounds["file_bytes"], remaining)
        )
        content = b"".join(chunks)
        remaining -= len(content)
        identity = _identity(content)
        if expected is not None and expected != identity:
            _fail("plan_stale", "refined metadata changed during planning")
        relatives[relative] = identity
    if any(_signature(path) != node for path, node in nodes.items()) or any(
        _lineage(path) != prior for path, prior in ancestry.items()
    ):
        _fail("plan_stale", "original refined metadata changed during planning")
    current["old_documents"] = relatives
    current["command_renewal"] = {
        "schema": _REFINED_EXECUTION_RENEWAL_SCHEMA,
        "wrapper_component": current["wrapper_component"],
        "selection_plan": {"selection": component_plan["request"]},
        "refined_components": component_plan,
        "compilation_coverage": "unknown",
        "execution_performed": False,
        "apply_supported": True,
    }
    current["qualification"]["refined_components"] = names
    current["changes_required"] = (
        current["changes_required"]
        or component_plan["commands_changed"]
        or component_plan["source_changed"]
    )
    current["schema"] = _REFINED_EXECUTION_PLAN_SCHEMA
    return current


def _current_command_execution_plan(selected, *, command_selection, **options):
    if command_selection is None:
        _fail("command_selection_required", "execution renewal requires a selection")
    snapshot, prior_receipt, close_receipt = _prior_receipt_inputs(selected)
    # The complete existing planning owner retains validation, source custody,
    # phase conservation and fixed bounds. Never reinterpret its saved v2 form.
    from literate_ai.adapters.monorepo_adoption import _selection

    limits = snapshot.definition.scale_limits
    request = _selection(
        command_selection,
        maximum_bytes=min(
            DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
            limits.pinned_input_total_bytes
            if limits
            else DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
        ),
    )
    owners = request["components"]
    wrapper = PurePosixPath(_layout(snapshot.root).wrapper_component).name
    direct_wrapper = (
        isinstance(owners, list)
        and len(owners) == 1
        and isinstance(owners[0], dict)
        and owners[0].get("name") == wrapper
    )
    installed = retained_scaffold_path(
        snapshot.root, ".literate/monorepo-components/installation.json"
    )
    refined = not direct_wrapper and os.path.lexists(installed)
    current = (
        _refined_command_execution_plan(
            selected,
            command_selection,
            prior_test_receipt=prior_receipt,
            **options,
        )
        if refined
        else plan_retained_harness_readmission(
            selected, command_selection=command_selection, **options
        )
    )
    close_receipt()
    if (
        current["old_documents"]["literate.project.json"]
        != snapshot.content_identity.uri
    ):
        _fail("plan_stale", "receipt location changed during renewal planning")
    current.pop("plan_identity")
    current["prior_test_receipt"] = prior_receipt
    if prior_receipt["state"] == "present":
        current["old_documents"] = {
            **current["old_documents"],
            prior_receipt["path"]: prior_receipt["identity"],
        }
    current["schema"] = (
        _REFINED_EXECUTION_PLAN_SCHEMA if refined else _EXECUTION_PLAN_SCHEMA
    )
    current["apply_supported"] = True
    current["command_renewal"] = {
        **current["command_renewal"],
        "schema": (
            _REFINED_EXECUTION_RENEWAL_SCHEMA if refined else _EXECUTION_RENEWAL_SCHEMA
        ),
        "apply_supported": True,
    }
    current["plan_identity"] = _identity(current)
    if len(canonical_json_bytes(current)) + 1 > DEFAULT_MAXIMUM_PINNED_INPUT_BYTES:
        _fail("plan_too_large", "renewal plan exceeds the existing pinned-file limit")
    return current


def reopen_retained_command_renewal_execution_plan(
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
    """Reopen the complete executable request; acknowledgement remains separate.

    A self-hash or an older planning record supplies no execution authority.
    Fresh planning independently supplies every nested field and current input.
    This operation itself performs no target invocation or publication.
    """
    try:
        if (
            type(content) is not bytes
            or len(content) > DEFAULT_MAXIMUM_PINNED_INPUT_BYTES
            or command_selection is None
        ):
            raise ValueError("invalid executable renewal bytes")
        data = json.loads(content)
        encoded = canonical_json_bytes(data)
        if not isinstance(data, dict) or content not in (encoded, encoded + b"\n"):
            raise ValueError("noncanonical executable renewal")
        renewal = data.get("command_renewal")
        if (
            data.get("apply_supported") is not True
            or not isinstance(renewal, dict)
            or (data.get("schema"), renewal.get("schema"))
            not in {
                (_EXECUTION_PLAN_SCHEMA, _EXECUTION_RENEWAL_SCHEMA),
                (_REFINED_EXECUTION_PLAN_SCHEMA, _REFINED_EXECUTION_RENEWAL_SCHEMA),
            }
            or renewal.get("apply_supported") is not True
            or renewal.get("execution_performed") is not False
            or renewal.get("compilation_coverage") != "unknown"
        ):
            raise ValueError("unsupported executable renewal form")
        identity = _identity(
            {key: value for key, value in data.items() if key != "plan_identity"}
        )
        if data.get("plan_identity") != identity:
            raise ValueError("executable renewal body identity mismatch")
        ContentIdentity.parse_uri(reviewed_plan_identity)
    except (ValueError, TypeError, RecursionError, OverflowError):
        _fail("plan_invalid", "saved executable renewal is invalid or unsupported")
    if identity != reviewed_plan_identity:
        _fail("plan_stale", "saved executable renewal differs from reviewed identity")
    current = _current_command_execution_plan(
        selected,
        command_selection=command_selection,
        execution_worker=execution_worker,
        worker_catalog_identity=worker_catalog_identity,
        timeout_seconds=timeout_seconds,
        retained_stage_ids=retained_stage_ids,
    )
    if canonical_json_bytes(current) != encoded:
        _fail("plan_stale", "saved executable renewal differs from current inputs")
    return current


def plan_retained_command_renewal_execution(
    selected: Path,
    *,
    command_selection: Path,
    execution_worker: ExecutionWorker | None = None,
    worker_catalog_identity: ContentIdentity | None = None,
    timeout_seconds: int = 1800,
    retained_stage_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Expose a fresh executable request only with complete read-back support."""
    return _current_command_execution_plan(
        selected,
        command_selection=command_selection,
        execution_worker=execution_worker,
        worker_catalog_identity=worker_catalog_identity,
        timeout_seconds=timeout_seconds,
        retained_stage_ids=retained_stage_ids,
    )


def _require_layout_current(root: Path, plan: dict[str, Any]) -> None:
    # Capture known native inputs before parsing any layout/history payloads.
    # The final pass below reads no payloads and never accepts resampled facts.
    metadata_root = retained_scaffold_path(root, ".literate")
    ancestry = _lineage(metadata_root)
    nodes = []
    for relative in (CONVERSION_AUTHORITY_FILE, LIFT_SHIFT, RETAINED_LAYOUT_PATH):
        path = retained_scaffold_path(root, relative)
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
    if _lineage(metadata_root) != ancestry:
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
    if _lineage(metadata_root) != ancestry:
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

    def __init__(
        self, key, root, scope, *, _bounded_source=None, _original_inventory=None
    ):
        from literate_ai.adapters.harness_tree import _validated_scope

        if key is not _SOURCE_INPUTS_KEY:
            raise TypeError("original readmission source owner required")
        if _bounded_source is not None:
            _bounded_readmission_class_current()
            from .project_layout_retained_source_observation import (
                bounded_retained_source_data_for,
            )

            original_scope, paths, raw = bounded_retained_source_data_for(
                _bounded_source, root, _original_inventory
            )
            if scope is not original_scope:
                _fail("source_changed", "same original retained scope required")
            _bounded_readmission_class_current()
            values = (
                root,
                scope,
                paths,
                raw,
                None,
                None,
                _bounded_source,
                _original_inventory,
            )
            _bind_bounded_readmission(self, values)
            return
        self.root = root
        self.scope = json.loads(canonical_json_bytes(scope))
        self.paths, _excluded = _validated_scope(self.scope)
        self.closed = False
        self.nodes, self.ancestry = _source_native_inputs(root, self.paths)
        self.raw = observe_retained_source_bytes(root, self.scope)
        if self.raw["missing_count"]:
            _fail("source_changed", "original retained source is missing")

    def require_current(self):
        bounded = _bounded_readmission(self)
        if bounded is not None:
            from .project_layout_retained_source_observation import (
                require_bounded_retained_source_for,
            )

            try:
                require_bounded_retained_source_for(bounded[6], bounded[0], bounded[7])
            except (OSError, ValueError, RetainedLayoutError) as exc:
                try:
                    _fail("source_changed", "original bounded retained source changed")
                except RetainedHarnessReadmissionError as error:
                    raise error from exc
            _bounded_readmission(self)
            return
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
        bounded = _bounded_readmission(self)
        if bounded is not None:
            if root is not bounded[0] or inventory is not bounded[7]:
                _fail("source_changed", "same original source/inventory required")
            _current_readmission(self)
            return
        if root != self.root or inventory["source_scope"] != self.scope:
            _fail("source_changed", "source observation belongs to another operation")
        _current_readmission(self)

    def require_copy(self, root):
        _current_readmission(self)
        try:
            nodes, ancestry = _source_native_inputs(root, self.paths)
            _require_initial_copy_namespace(root, self.paths)
            raw = observe_retained_source_bytes(root, self.scope)
            _require_initial_copy_namespace(root, self.paths)
            _current_readmission(self)
            current = (
                raw == self.raw
                and all(_signature(path) == fact for path, fact in nodes)
                and all(_lineage(path) == fact for path, fact in ancestry)
            )
        except (OSError, ValueError, RetainedLayoutError):
            current = False
        if not current:
            _fail("source_changed", "disposable source differs from original inputs")


def _bounded_readmission_admissions(cls):
    """Original opt-in pairing; absent legacy instances acquire no new owner."""
    namespace = tuple(vars(cls).items())
    bases, mro = cls.__bases__, cls.__mro__
    dictionary = vars(cls)["__dict__"]
    original_current = vars(cls)["require_current"]
    names = (
        "root",
        "scope",
        "paths",
        "raw",
        "nodes",
        "ancestry",
        "_bounded_source",
        "_bounded_inventory",
    )
    records = {}

    def class_current():
        if globals().get("_ReadmissionSourceInputs") is not cls:
            _fail("source_changed", "original readmission source class replaced")
        current = dict(vars(cls))
        if (
            "__slotnames__" not in dict(namespace)
            and type(current.get("__slotnames__")) is list
            and not current["__slotnames__"]
        ):
            current.pop("__slotnames__")
        if (
            cls.__bases__ is not bases
            or cls.__mro__ is not mro
            or set(current) != {name for name, _value in namespace}
            or any(current[name] is not value for name, value in namespace)
        ):
            _fail("source_changed", "original bounded readmission descriptor changed")

    def data(owner):
        if type(owner) is not cls:
            _fail("source_changed", "original readmission source receiver required")
        actual = dictionary.__get__(owner, cls)
        if type(actual) is not dict or any(type(name) is not str for name in actual):
            _fail("source_changed", "original source instance data changed")
        return actual

    def require(owner):
        record = records.get(id(owner))
        if record is None or record[0]() is not owner:
            if data(owner).get("_bounded_source") is not None:
                _fail("source_changed", "unadmitted bounded source receiver")
            return None
        class_current()
        actual = data(owner)
        if record[2] or actual.get("closed") is True:
            record[2] = True
            _fail("source_inputs_expired", "original source observation is closed")
        if actual.get("closed") is not False or any(
            actual.get(name) is not value
            for name, value in zip(names, record[1], strict=True)
        ):
            _fail("source_changed", "original bounded source pairing changed")
        return record[1]

    def bind(owner, values):
        class_current()
        if id(owner) in records:
            _fail("source_changed", "bounded source receiver cannot renew")
        actual = data(owner)
        actual.update(dict(zip(names, values, strict=True)))
        actual["closed"] = False
        key = id(owner)

        def release(dead):
            old = records.get(key)
            if old is not None and old[0] is dead:
                records.pop(key, None)

        records[key] = [weakref.ref(owner, release), values, False]
        require(owner)

    def current(owner):
        if require(owner) is None:
            return owner.require_current()
        return original_current(owner)

    def end(owner):
        record = records.get(id(owner))
        if record is not None and record[0]() is owner:
            record[2] = True
            try:
                actual = dictionary.__get__(owner, cls)
            except TypeError:
                return
            if type(actual) is dict:
                actual["closed"] = True

    return bind, require, current, end, class_current


(
    _bind_bounded_readmission,
    _bounded_readmission,
    _current_readmission,
    _end_bounded_readmission,
    _bounded_readmission_class_current,
) = _bounded_readmission_admissions(_ReadmissionSourceInputs)


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
def _readmission_source_inputs(
    implementation, inventory, *, expected_tree=None, _bounded_source=None
):
    try:
        if _bounded_source is None:
            inputs = _ReadmissionSourceInputs(
                _SOURCE_INPUTS_KEY, implementation, inventory["source_scope"]
            )
        else:
            _bounded_readmission_class_current()
            inputs = _ReadmissionSourceInputs(
                _SOURCE_INPUTS_KEY,
                implementation,
                inventory["source_scope"],
                _bounded_source=_bounded_source,
                _original_inventory=inventory,
            )
    except (OSError, ValueError, RetainedLayoutError):
        _fail("source_changed", "original retained source is unavailable or redirected")
    try:
        if _bounded_source is not None:
            if expected_tree is not None:
                from .project_layout_retained_source_observation import (
                    bounded_retained_source_tree_for,
                )

                if (
                    bounded_retained_source_tree_for(
                        _bounded_source, implementation, inventory
                    )
                    != expected_tree
                ):
                    _fail(
                        "source_changed",
                        "original source differs from the reviewed plan",
                    )
        elif (
            expected_tree is not None
            and observe_retained_tree(implementation, inputs.scope)["source_tree"]
            != expected_tree
        ):
            _fail("source_changed", "original source differs from the reviewed plan")
        _current_readmission(inputs)
        yield inputs
    finally:
        if _bounded_source is None:
            try:
                inputs.require_current()
            finally:
                inputs.closed = True
        else:
            primary = sys.exception()
            try:
                _current_readmission(inputs)
            except BaseException:
                if primary is None:
                    raise
                try:
                    primary.add_note(
                        "original bounded source closing guard also refused"
                    )
                except BaseException:
                    pass
            finally:
                _end_bounded_readmission(inputs)


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
    maximum_total_bytes: int,
) -> tuple[Path, bool]:
    history_root = _safe_path(
        root,
        f"{HISTORY}/{plan_identity.digest}.evidence",
        must_exist=False,
    )
    try:
        created = publish_readmission_evidence(
            history_root, before, maximum_total_bytes=maximum_total_bytes
        )
    except ReadmissionPublicationError as exc:
        if exc.code == "retained_harness.publication_history_collision":
            _fail("history_collision", "prior-evidence history has different bytes")
        raise
    return history_root, created


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
    command_selection: Path | None = None,
) -> dict[str, Any]:
    """Qualify and atomically publish one freshly re-inspected harness."""

    if acknowledge is not True:
        _fail("acknowledgement_required", "readmission requires acknowledgement")
    project = load_project(selected)
    with project_lifecycle_lock(project.root, operation="retained-harness.readmit"):
        options = {
            "execution_worker": execution_worker,
            "worker_catalog_identity": worker_catalog_identity,
            "timeout_seconds": timeout_seconds,
            "retained_stage_ids": retained_stage_ids,
        }
        plan = (
            plan_retained_harness_readmission(project.root, **options)
            if command_selection is None
            else plan_retained_command_renewal_execution(
                project.root, command_selection=command_selection, **options
            )
        )

        def require_renewal_current():
            if command_selection is not None:
                current = plan_retained_command_renewal_execution(
                    project.root, command_selection=command_selection, **options
                )
                if current["plan_identity"] != expected_plan_identity:
                    _fail("plan_stale", "renewal inputs changed during execution")

        if plan["plan_identity"] != expected_plan_identity:
            _fail("plan_stale", "source or metadata changed after review")
        if not plan["changes_required"]:
            return {**plan, "applied": False}
        root = project.root
        selection_node = selection_ancestry = None
        if command_selection is not None:
            command_selection = command_selection.absolute()
            selection_node = _signature(command_selection)
            selection_ancestry = _lineage(command_selection.parent)

        def require_selection_current():
            if command_selection is None:
                return
            from literate_ai.adapters.monorepo_adoption import _selection

            if (
                _selection(command_selection)
                != plan["command_renewal"]["selection_plan"]["selection"]
                or _signature(command_selection) != selection_node
                or _lineage(command_selection.parent) != selection_ancestry
            ):
                _fail("command_selection_stale", "reviewed command selection changed")

        require_selection_current()
        implementation = root / plan["implementation"]
        inventory = plan["new_inventory"]
        wrapper = render_harness_wrapper(
            inventory, legacy_directory=plan["implementation"]
        ).encode("utf-8")
        executor = remote_executor or RetainedHarnessSshExecutor()
        plan_identity = ContentIdentity.parse_uri(plan["plan_identity"])
        preserved_inputs = _preserved_authority_inputs(
            root,
            wrapper_component=plan["wrapper_component"],
            shim_paths=plan["new_shim_identities"],
        )
        if preserved_inputs.to_dict() != plan["preserved_authority_inputs"]:
            _fail("plan_stale", "referenced authority changed before qualification")
        with ExitStack() as source_stack:
            source_inputs = source_stack.enter_context(
                _readmission_source_inputs(
                    implementation, inventory, expected_tree=plan["source_tree"]
                )
            )
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
            source_inputs.require_current()
            require_renewal_current()
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
            source_inputs.require_current()
            require_renewal_current()
            _require_layout_current(root, plan)
            if "layout_readmission" in plan:
                if baseline.get("state") != "passed" or parity.get("state") != "passed":
                    _fail("layout_unqualified", "fresh baseline and parity must pass")
                baseline["layout_readmission"] = plan["layout_readmission"]
                parity["layout_readmission"] = plan["layout_readmission"]
            preserved_inputs.require_unchanged()
            review = FilesystemProjectValidationAdapter().documentation_review(root)
            if review["authority_identity"] != plan["old_authority_identity"]:
                _fail("plan_stale", "project authority changed during qualification")
            shim, _ = _readmitted_shim_authority(
                root, inventory, baseline, wrapper_component=plan["wrapper_component"]
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
            refined = plan.get("command_renewal", {}).get("refined_components")
            if refined is not None:
                for relative in refined["old_documents"]:
                    paths[relative] = _safe_path(root, relative)
                for item in refined["old_selection"]["components"]:
                    for filename in (
                        "component.lock.json",
                        "component.resolution-audit.host.json",
                    ):
                        relative = f"components/{item['name']}/{filename}"
                        paths[relative] = _safe_path(root, relative)
            before = {name: path.read_bytes() for name, path in paths.items()}
            if any(
                _identity(content) != plan["old_documents"][name]
                for name, content in before.items()
            ):
                _fail("plan_stale", "project metadata changed before publication")
            for relative in (
                CONVERSION_AUTHORITY_FILE,
                LIFT_SHIFT,
                RETAINED_LAYOUT_PATH,
            ):
                if relative in plan["old_documents"]:
                    before[relative] = _safe_path(root, relative).read_bytes()
                    if _identity(before[relative]) != plan["old_documents"][relative]:
                        _fail(
                            "layout_changed",
                            "layout changed before history publication",
                        )
            prior_receipt = plan.get("prior_test_receipt")
            if prior_receipt is not None and prior_receipt["state"] == "present":
                name = prior_receipt["path"]
                path = _safe_path(root, name)
                from literate_ai.adapters.monorepo_adoption import _consume_direct_file

                content = []
                _consume_direct_file(
                    path,
                    content.append,
                    maximum_bytes=DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
                )
                before[name] = b"".join(content)
                if _identity(before[name]) != prior_receipt["identity"]:
                    _fail(
                        "prior_receipt_changed", "prior receipt changed before history"
                    )
            limits = project.definition.scale_limits
            maximum_files = (
                limits.pinned_input_files
                if limits
                else DEFAULT_MAXIMUM_PINNED_INPUT_FILES
            )
            if len(before) > maximum_files:
                _fail(
                    "publication_limit", "readmission metadata exceeds project limits"
                )
            history = _safe_path(
                root,
                f"{HISTORY}/{plan_identity.digest}.json",
                must_exist=False,
            )
            history.parent.mkdir(parents=True, exist_ok=True)
            history_bytes = canonical_json_bytes(plan) + b"\n"
            if history.exists():
                if history.read_bytes() != history_bytes:
                    _fail(
                        "history_collision", "readmission history has different bytes"
                    )
            else:
                with history.open("xb") as stream:
                    stream.write(history_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
            evidence_history, _created_evidence_history = _history_evidence(
                root,
                plan_identity=plan_identity,
                before=before,
                maximum_total_bytes=(
                    limits.pinned_input_total_bytes
                    if limits
                    else DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES
                ),
            )
            publication = ReadmissionPublication.create(
                root,
                before={
                    _safe_path(root, name).relative_to(root).as_posix(): content
                    for name, content in before.items()
                },
                writable=tuple(
                    path.relative_to(root).as_posix() for path in paths.values()
                ),
                plan_identity=plan["plan_identity"],
                maximum_total_bytes=(
                    limits.pinned_input_total_bytes
                    if limits
                    else DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES
                ),
                maximum_steps=maximum_files,
            )
            try:
                with atomic_publication_scope(publication):
                    component_result = None
                    if refined is not None:
                        from .retained_component_command_execution import (
                            _execute_component_command_renewal,
                        )

                        def require_refined_source_current():
                            source_inputs.require_current()
                            require_selection_current()
                            _require_layout_current(root, plan)

                        component_result = _execute_component_command_renewal(
                            root,
                            command_selection,
                            planning_record=refined,
                            publication=publication,
                            acknowledge=True,
                            require_source_current=require_refined_source_current,
                            worker_id=plan["qualification"]["worker_id"],
                            timeout_seconds=timeout_seconds,
                        )
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
                        FilesystemConversionAuthorityStore._atomic_write(
                            paths[name], content
                        )
                    store = ProjectConfigurationStore(root)
                    snapshot = store.read()
                    store.update(
                        snapshot,
                        replace(
                            snapshot.definition,
                            test_receipt_policy=retained_harness_receipt_policy(
                                inventory
                            ),
                            default_flavor_selectors=tuple(
                                plan["new_default_flavor_selectors"]
                            ),
                        ),
                    )
                    from literate_ai.adapters.component_lock_commands import (
                        _component_locks_from_args,
                    )

                    lock_components = [wrapper_component]
                    if refined is not None:
                        lock_components.extend(
                            f"components/{item['name']}"
                            for item in refined["old_selection"]["components"]
                        )
                    for component in lock_components:
                        lock_result, lock_status = _component_locks_from_args(
                            Namespace(
                                component=str(root / component),
                                target="host",
                                flavor_root=[],
                                flavor=[],
                                check=False,
                                diff=False,
                                large_review=None,
                            )
                        )
                        if lock_status != 0:
                            _fail(
                                "lock_reconciliation_failed",
                                f"component lock reconciliation failed: {lock_result}",
                            )
                    preserved_inputs.require_unchanged()
                    review = FilesystemProjectValidationAdapter().documentation_review(
                        root, include_inputs=True
                    )
                    if (
                        _stable_authority_identity(root, review)
                        != plan["stable_authority_identity"]
                    ):
                        _fail(
                            "metadata_changed",
                            "Project authority changed during readmission",
                        )
                    try:
                        record_project_authority_review(
                            root,
                            expected_authority_identity=review["authority_identity"],
                            expected_document_content=before[plan["authority_review"]],
                        )
                    except ProjectInitializationError as exc:
                        if exc.code != "project.documentation_authority_review_changed":
                            raise
                        _fail(
                            "metadata_changed",
                            "Project metadata changed during readmission",
                        )
                    preserved_inputs.require_unchanged()
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
                                "conversion authority or lift-and-shift "
                                "evidence changed",
                            )
                    _require_layout_current(root, plan)
                    source_inputs.require_current()
                    require_selection_current()
                    if command_selection is not None:
                        _snapshot, prior, close_receipt = _prior_receipt_inputs(root)
                        close_receipt()
                        if prior != plan["prior_test_receipt"]:
                            _fail(
                                "prior_receipt_changed",
                                "prior receipt changed during publication",
                            )
                    preserved_inputs.require_unchanged()
                    final_review = (
                        FilesystemProjectValidationAdapter().documentation_review(
                            root, include_inputs=True
                        )
                    )
                    if (
                        final_review["state"] != "current"
                        or _stable_authority_identity(root, final_review)
                        != plan["stable_authority_identity"]
                    ):
                        _fail(
                            "metadata_changed",
                            "Project authority changed during readmission",
                        )
                    preserved_inputs.require_unchanged()
                    publication.require_current_targets()
                    # Close the original observation while rollback is still
                    # pending; its finally refusal must precede commit.
                    source_stack.close()
                    publication.commit()
            except BaseException:
                if not publication.closed:
                    publication.rollback()
                # Failed evidence stays readable in history. Never recursively
                # delete a directory that another writer may have extended.
                raise
            result = {
                **plan,
                "applied": True,
                "history": history.relative_to(root).as_posix(),
                "prior_evidence_history": evidence_history.relative_to(root).as_posix(),
                "baseline_identity": _identity(baseline),
                "parity_identity": _identity(parity),
            }
            if component_result is not None:
                result["component_renewal"] = component_result
            return result
