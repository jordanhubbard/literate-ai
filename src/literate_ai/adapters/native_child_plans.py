"""Read-only complete qualified-child addition/revision plans (ADRs 0062/0066)."""

from __future__ import annotations

import json
import stat
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from literate_ai.adapters.authority import FileAuthorityProjectionStore
from literate_ai.adapters.component_lock_application import current_component_lock
from literate_ai.adapters.conversion_authority import (
    CONVERSION_AUTHORITY_FILE,
    NATIVE_PROJECTS_FILE,
    FilesystemConversionAuthorityStore,
    _current_receipt_identity,
    _native_project_roots,
    require_current_qualified_conversion_authority,
    require_native_project_path,
)
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.native_child_inputs import (
    ChildCaptureLimits,
    ChildQualificationSelection,
    capture_child_tree,
    child_relative_path,
    directory_node,
    physical_node,
    portable_key,
    read_qualification_selection,
    refuse,
)
from literate_ai.adapters.native_project_updates import _digest, _read
from literate_ai.adapters.project_validation import validated_project_authority_identity
from literate_ai.adapters.retained_harness_receipts import (
    _load_retained_documents,
    retained_harness_project_authority_identity,
    retained_harness_receipt_policy,
)
from literate_ai.adapters.retained_provider_authority import (
    RetainedProviderAuthority,
    read_retained_provider_authority,
)
from literate_ai.application.flavor_selection import (
    apply_flavor_selectors,
    parse_scoped_flavor_selector,
)
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.contracts.flavors import FlavorSelectionCandidate
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
    renew_qualified_conversion_authority,
)
from literate_ai.projects import LoadedProject, ProjectConfigurationStore

PLAN_SCHEMA = "literate-ai/qualified-native-child-plan@1"


def _platform_constraints(authority) -> list[dict[str, object]]:
    root = next(
        node
        for node in authority.lock.nodes
        if node.revision.identity == authority.lock.root_revision
    )
    selected = {value.uri for value in root.revision.selected_flavor_revisions}
    values = [
        {
            "axis": flavor.definition.primary_axis.value,
            "targets": list(flavor.definition.supported_targets),
            "revision": flavor.identity.uri,
        }
        for flavor in authority.selected_flavors
        if flavor.identity.uri in selected
        and flavor.definition.primary_axis.value
        in {"platform.os", "platform.architecture"}
    ]
    if not any(value["axis"] == "platform.os" for value in values):
        refuse(
            "target_unsupported",
            "qualification requires explicit current platform Flavor authority",
        )
    return sorted(values, key=lambda value: (value["axis"], value["revision"]))


def _platform_key(value: list[dict[str, object]]) -> str:
    # Different Components and Flavor revisions have distinct lock target hashes.
    # Compare platform constraints while retaining every exact Flavor reference.
    return canonical_identity(
        sorted(
            ({"axis": item["axis"], "targets": item["targets"]} for item in value),
            key=lambda item: (item["axis"], tuple(item["targets"])),
        )
    ).uri


def _parent_platform_constraints(project: LoadedProject, catalog) -> list[dict]:
    """Retained wrappers have no OS slot; use their declared project target.

    Resolve the actual current Flavor catalog and normal ordered selectors. The
    retained receipt separately binds the executed harness and source authority.
    """
    revisions = {flavor.identity.uri: flavor for flavor in catalog.flavor_revisions}
    candidates = tuple(
        FlavorSelectionCandidate(
            candidate_identity=flavor.identity.uri,
            flavor_id=flavor.definition.coordinate.name,
            axis=flavor.definition.primary_axis.value,
            value=flavor.definition.supported_targets[0],
            conflicts=flavor.definition.conflicts,
            coordinate_uri=flavor.definition.coordinate.uri,
        )
        for flavor in revisions.values()
    )
    coordinate = catalog.root_authoring.coordinate.uri
    selectors = []
    for raw in (
        *project.definition.default_flavor_selectors,
        *project.flavor_selectors_for(catalog.root),
    ):
        scope, effective = parse_scoped_flavor_selector(raw)
        if scope is None or scope == coordinate:
            selectors.append(effective)
    selected = apply_flavor_selectors(candidates, selectors)
    result = [
        {
            "axis": item.axis,
            "targets": list(
                revisions[item.candidate_identity].definition.supported_targets
            ),
            "revision": item.candidate_identity,
        }
        for item in selected
        if item.axis in {"platform.os", "platform.architecture"}
    ]
    if not any(item["axis"] == "platform.os" for item in result):
        refuse(
            "target_unsupported",
            "the retained parent requires explicit platform authority",
        )
    return sorted(result, key=lambda item: (item["axis"], item["revision"]))


def _parent_wrapper(project: LoadedProject):
    wrapper = project.root / "components/legacy-project-wrapper"
    lock = current_component_lock(wrapper)
    reader = FilesystemLockedGenerationAuthorityReader()
    catalog = reader.load_catalog(wrapper, flavor_roots=(project.root / "flavors",))
    snapshot = reader.resolve(
        catalog,
        target_name=lock.target_name,
        # Conversion explicitly selects its shim over the detected build default.
        flavor_selectors=project.flavor_selectors_for(
            wrapper, ("+flavor://legacy-adoption/build-legacy-shim",)
        ),
    )
    snapshot.require_unchanged()
    return snapshot, catalog


def _metadata(path: Path) -> tuple[bytes, tuple[int, ...]]:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        refuse(
            "metadata_unsafe",
            "parent publication metadata must be direct single-link files",
        )
    content = _read(path)
    if physical_node(path.lstat()) != physical_node(before):
        refuse("parent_changed", "parent metadata changed while capturing")
    return content, physical_node(before)


def _configuration(root: Path) -> tuple[LoadedProject, bytes]:
    directory_node(root)
    snapshot = ProjectConfigurationStore(root).read()
    if snapshot.root != root:
        refuse(
            "project_redirected", "a selected project must be its exact physical root"
        )
    return LoadedProject(snapshot.root, snapshot.definition), snapshot.content


@dataclass(frozen=True)
class CurrentChild:
    root: Path
    summary: dict[str, object]
    _guards: tuple[Callable[[], None], ...] = field(repr=False, compare=False)
    _limits: ChildCaptureLimits = field(repr=False, compare=False)

    def require_unchanged(self) -> None:
        for guard in self._guards:
            guard()
        if capture_child_tree(self.root, self._limits) != self.summary["physical_tree"]:
            refuse(
                "child_changed",
                "a bound child tree changed after qualification observation",
            )
        for guard in self._guards:
            guard()


def read_current_child(
    parent: LoadedProject,
    relative: str,
    selections: tuple[ChildQualificationSelection, ...],
    limits: ChildCaptureLimits,
) -> CurrentChild:
    child_relative_path(relative)
    root = parent.root.joinpath(*PurePosixPath(relative).parts)
    require_native_project_path(parent, root)
    before = capture_child_tree(root, limits)
    project, content = _configuration(root)
    selected = tuple(item for item in selections if item.project == relative)
    if not selected:
        refuse(
            "qualification_selection_missing",
            "every selected child requires current qualification selections",
        )
    coordinates = set(FileAuthorityProjectionStore(root).coordinates())
    if not coordinates:
        refuse(
            "child_unqualified",
            "a child must have current independently qualified Components",
        )
    providers: list[RetainedProviderAuthority] = []
    components = []
    seen = set()
    platforms = {}
    for selector in selected:
        component = root.joinpath(*PurePosixPath(selector.component).parts)
        require_native_project_path(parent, component)
        provider = read_retained_provider_authority(
            root,
            GenerationPreparationRequest(component, selector.target, selector.flavors),
            provider_id=selector.provider,
            profile_path=selector.profile,
            pipeline_model=selector.model,
        )
        projection = provider.promotion.evidence.authority_projection
        result = provider.promotion.evidence.qualification_lifecycle_result
        if projection is None or result is None:
            refuse(
                "child_unqualified",
                "current lifecycle-backed qualification is required",
            )
        coordinate = projection.component_coordinate
        if coordinate in seen:
            refuse(
                "qualification_selection_invalid",
                "one qualified Component cannot be selected twice",
            )
        seen.add(coordinate)
        lock = provider.generation.prepared.locked_authority_snapshot.authority.lock
        if result.runs[0].target_profile_identity != lock.target_profile_identity:
            refuse(
                "child_target_mismatch",
                "qualification must bind the current selected target",
            )
        platform = _platform_constraints(
            provider.generation.prepared.locked_authority_snapshot.authority
        )
        platforms[_platform_key(platform)] = platform
        components.append(
            {
                "coordinate": coordinate,
                "specification": projection.specification_set_identity.uri,
                "source": projection.source_snapshot_identity.uri,
                "projection": projection.identity.uri,
                "qualification": result.identity.uri,
                "target": lock.target_profile_identity.uri,
                "lock": lock.identity.uri,
                "policy": provider.lifecycle.policy.identity.uri,
                "verifier": provider.qualification.case_map.verifier_identity.uri,
                "runs": [run.run_identity.uri for run in result.runs],
                "configuration": provider.project.definition.identity.uri,
            }
        )
        providers.append(provider)
    if seen != coordinates:
        refuse(
            "qualification_incomplete",
            "selections must cover every current child Component projection",
        )
    if len(platforms) != 1:
        refuse(
            "child_target_mismatch",
            "all selected child Components must share current platform constraints",
        )
    revision = validated_project_authority_identity(
        root, synchronize_source_intelligence=False
    )
    if (
        _read(root / "literate.project.json") != content
        or capture_child_tree(root, limits) != before
    ):
        refuse("child_changed", "child inputs changed while reopening qualification")
    summary = {
        "path": relative,
        "project_id": project.definition.project_id,
        "definition": canonical_identity(json.loads(content)).uri,
        "configuration": _digest(content),
        "authority": revision.uri,
        "physical_tree": before,
        "platform": next(iter(platforms.values())),
        "components": sorted(components, key=lambda item: item["coordinate"]),
    }
    guards = tuple(p.require_unchanged for p in providers)
    result = CurrentChild(root, summary, guards, limits)
    result.require_unchanged()
    return result


@dataclass(frozen=True)
class CurrentParent:
    project: LoadedProject
    summary: dict[str, object]
    state: ConversionAuthorityState
    registry: dict
    registry_bytes: bytes
    state_bytes: bytes
    receipt_path: Path
    receipt_bytes: bytes
    receipt_node: tuple[int, ...]
    composition_supported: bool

    def require_source_unchanged(self) -> None:
        """Guard unmodified parent inputs even while its two metadata files move."""
        require_parent_sources(self.project.root, self.summary)


def require_parent_sources(root: Path, expected: dict) -> LoadedProject:
    """Reopen unchanged non-membership inputs even during a pending publication."""
    project, content = _configuration(root)
    if (
        directory_node(root) != tuple(expected["root_node"])
        or _digest(content) != expected["configuration"]
        or project.definition.test_receipt is None
    ):
        refuse("parent_changed", "parent root or definition changed")
    receipt_path = root / project.definition.test_receipt
    require_native_project_path(project, receipt_path)
    base = validated_project_authority_identity(
        root, synchronize_source_intelligence=False
    )
    wrapper, _catalog = _parent_wrapper(project)
    if (
        wrapper.authority.lock.identity.uri != expected["wrapper_lock"]
        or base.uri != expected["authority"]
        or retained_harness_project_authority_identity(project, base).uri
        != expected["retained_source_authority"]
        or _digest(_read(receipt_path, maximum_bytes=16 * 1024 * 1024))
        != expected["receipt_bytes"]
        or physical_node(receipt_path.lstat()) != tuple(expected["receipt_node"])
    ):
        refuse("parent_changed", "parent retained source, receipt or authority changed")
    return project


def membership_composition_supported(project: LoadedProject) -> bool:
    documents = _load_retained_documents(project)
    return project.definition.test_receipt_policy == retained_harness_receipt_policy(
        documents["inventory"]["value"]
    )


def read_current_parent(root: Path) -> CurrentParent:
    project, content = _configuration(root)
    state = FilesystemConversionAuthorityStore(root).load_optional()
    if state is None or state.stage is not ConversionAuthorityStage.QUALIFIED:
        refuse("parent_unqualified", "an already qualified adopted parent is required")
    require_current_qualified_conversion_authority(project, state)
    roots = _native_project_roots(project)
    registry_bytes, registry_node = _metadata(root / NATIVE_PROJECTS_FILE)
    registry = json.loads(registry_bytes)
    state_bytes, state_node = _metadata(root / CONVERSION_AUTHORITY_FILE)
    if json.loads(state_bytes) != state.to_dict():
        refuse("parent_changed", "parent qualification changed while observing")
    base = validated_project_authority_identity(
        root, synchronize_source_intelligence=False
    )
    receipt = _current_receipt_identity(project)
    if project.definition.test_receipt is None:
        refuse(
            "parent_receipt_missing", "a current retained-harness receipt is required"
        )
    receipt_path = root / project.definition.test_receipt
    require_native_project_path(project, receipt_path)
    receipt_bytes = _read(receipt_path, maximum_bytes=16 * 1024 * 1024)
    receipt_node = physical_node(receipt_path.lstat())
    wrapper_snapshot, catalog = _parent_wrapper(project)
    wrapper_lock = wrapper_snapshot.authority.lock
    platform_constraints = _parent_platform_constraints(project, catalog)
    wrapper_snapshot.require_unchanged()
    supported = membership_composition_supported(project)
    summary = {
        "project_id": project.definition.project_id,
        "platform": platform_constraints,
        "wrapper_lock": wrapper_lock.identity.uri,
        "root_node": directory_node(root),
        "definition": canonical_identity(json.loads(content)).uri,
        "configuration": _digest(content),
        "authority": base.uri,
        "retained_source_authority": retained_harness_project_authority_identity(
            project, base
        ).uri,
        "receipt": receipt.uri,
        "receipt_bytes": _digest(receipt_bytes),
        "receipt_node": receipt_node,
        "receipt_policy": project.definition.test_receipt_policy.identity.uri,
        "registry": _digest(registry_bytes),
        "registry_node": registry_node,
        "conversion_node": state_node,
        "conversion": state.identity.uri,
        "conversion_bytes": _digest(state_bytes),
        "children": [str(p.relative_to(root).as_posix()) for p in roots],
    }
    result = CurrentParent(
        project,
        summary,
        state,
        registry,
        registry_bytes,
        state_bytes,
        receipt_path,
        receipt_bytes,
        receipt_node,
        supported,
    )
    result.require_source_unchanged()
    return result


def compose_child_plan(
    parent: CurrentParent,
    children: tuple[CurrentChild, ...],
    candidate: CurrentChild,
    *,
    old_path: str | None,
    selection: dict,
    limits: ChildCaptureLimits,
) -> dict[str, object]:
    """Compose only already-reopened current facts; never certify metadata flags."""
    existing = {c.summary["path"]: c for c in children}
    if set(existing) != set(parent.summary["children"]) or len(existing) != len(
        children
    ):
        refuse(
            "registry_changed", "every active child must remain in the complete plan"
        )
    entries = {entry["path"]: entry for entry in parent.registry["projects"]}
    for child in children:
        entry = entries[child.summary["path"]]
        if (
            entry["project_id"] != child.summary["project_id"]
            or entry["project_definition_identity"] != child.summary["definition"]
        ):
            refuse(
                "registry_changed",
                "an active child's current definition differs from registration",
            )
    prior_evidence = tuple(
        sorted(
            (
                ContentIdentity.parse_uri(component["projection"])
                for child in children
                for component in child.summary["components"]
            ),
            key=lambda value: value.uri,
        )
    )
    if prior_evidence != parent.state.evidence_identities:
        refuse(
            "parent_changed",
            "current parent qualification does not bind all current children",
        )
    if len(children) + 1 > limits.maximum_children:
        refuse(
            "child_limit", "the complete child membership exceeds its reviewed budget"
        )
    if old_path is not None and old_path not in existing:
        refuse("old_child_missing", "revision requires one exact active physical child")
    proposal = candidate.summary
    if proposal["path"] in existing or portable_key(str(proposal["path"])) in {
        portable_key(str(k)) for k in existing
    }:
        refuse(
            "child_collision",
            "the candidate must use a distinct unregistered physical path",
        )
    active = [c for path, c in existing.items() if path != old_path]
    if old_path is not None:
        old = existing[old_path].summary
        if old["project_id"] != proposal["project_id"]:
            refuse(
                "revision_identity_mismatch",
                "a revision must preserve the logical child project identifier",
            )
        prior = {c["coordinate"]: c["specification"] for c in old["components"]}
        later = {c["coordinate"]: c["specification"] for c in proposal["components"]}
        if set(prior) != set(later) or prior == later:
            refuse(
                "revision_intent_invalid",
                "a revision must preserve coordinates and independently accept "
                "changed intent",
            )
        old_runs = {run for component in old["components"] for run in component["runs"]}
        if old_runs.intersection(
            run for component in proposal["components"] for run in component["runs"]
        ):
            refuse(
                "revision_runs_reused",
                "a new revision cannot reuse its old child's qualification runs",
            )
        if _platform_key(old["platform"]) != _platform_key(proposal["platform"]):
            refuse(
                "child_target_mismatch",
                "a revision must retain its active child's current target",
            )
    ids = {c.summary["project_id"] for c in active}
    coordinates = {
        item["coordinate"] for c in active for item in c.summary["components"]
    }
    if (
        proposal["project_id"] == parent.project.definition.project_id
        or proposal["project_id"] in ids
    ):
        refuse("child_collision", "active child project identifiers must remain unique")
    if coordinates.intersection(item["coordinate"] for item in proposal["components"]):
        refuse("child_collision", "active Component coordinates must remain unique")
    if any(
        _platform_key(c.summary["platform"])
        != _platform_key(parent.summary["platform"])
        for c in (*active, candidate)
    ):
        refuse(
            "child_target_mismatch",
            "new membership must match the retained parent platform constraints",
        )
    physical = [
        tuple(c.summary["physical_tree"]["root_node"][:2])
        for c in (*children, candidate)
    ]
    if (
        len(set(physical)) != len(physical)
        or tuple(parent.summary["root_node"][:2]) in physical
    ):
        refuse(
            "child_alias",
            "physical child roots must be independent from the parent and each other",
        )
    own = tuple(FileAuthorityProjectionStore(parent.project.root).coordinates())
    if own:
        refuse(
            "parent_policy_unsupported",
            "parent-local promoted Components require independently bound "
            "membership policy",
        )
    complete = (*active, candidate)
    evidence = tuple(
        ContentIdentity.parse_uri(component["projection"])
        for c in complete
        for component in c.summary["components"]
    )
    registry = {
        "schema": parent.registry["schema"],
        "projects": sorted(
            [
                {
                    "path": c.summary["path"],
                    "project_id": c.summary["project_id"],
                    "project_definition_identity": c.summary["definition"],
                }
                for c in complete
            ],
            key=lambda item: item["path"],
        ),
    }
    renewed = renew_qualified_conversion_authority(
        parent.state, evidence_identities=evidence
    )
    supported = parent.composition_supported
    result = {
        "schema": PLAN_SCHEMA,
        "operation": "revise" if old_path else "add",
        "candidate": proposal["path"],
        "old_child": old_path,
        "selections": selection,
        "limits": limits.to_dict(),
        "parent": parent.summary,
        "children": [c.summary for c in children],
        "candidate_qualification": proposal,
        "proposed_registry": registry,
        "renewed_conversion_authority": renewed.to_dict() if supported else None,
        "renewal": {
            "supported": supported,
            "rule": "unchanged-retained-harness-and-current-qualified-membership@1"
            if supported
            else None,
            "retained_receipt_unchanged": True,
            "required_work": []
            if supported
            else ["renew-parent-under-configured-execution-policy"],
            "consumer_acceptance_required": True,
        },
    }
    result["identity"] = canonical_identity(result).uri
    return json.loads(canonical_json_bytes(result))


def plan_qualified_native_child(
    parent_path: Path,
    candidate_path: str,
    selection: dict,
    *,
    old_path: str | None = None,
) -> dict[str, object]:
    """Reopen exact authority and qualification without registration or execution."""
    child_relative_path(candidate_path)
    if old_path is not None:
        child_relative_path(old_path)
    selectors, limits = read_qualification_selection(selection)
    root = Path(parent_path).absolute()
    parent = read_current_parent(root)
    paths = tuple(parent.summary["children"])
    if len(paths) + 1 > limits.maximum_children:
        refuse("child_limit", "current membership exceeds the reviewed child budget")
    if {selector.project for selector in selectors} != {*paths, candidate_path}:
        refuse(
            "qualification_selection_invalid",
            "selection must cover exactly all active children and the candidate",
        )
    children = tuple(
        read_current_child(parent.project, path, selectors, limits) for path in paths
    )
    candidate = read_current_child(parent.project, candidate_path, selectors, limits)
    result = compose_child_plan(
        parent,
        children,
        candidate,
        old_path=old_path,
        selection=selection,
        limits=limits,
    )
    parent.require_source_unchanged()
    for child in (*children, candidate):
        child.require_unchanged()
    if (
        tuple(
            str(path.relative_to(root).as_posix())
            for path in _native_project_roots(parent.project)
        )
        != paths
    ):
        refuse("parent_changed", "parent registration changed while planning")
    require_current_qualified_conversion_authority(parent.project, parent.state)
    if (
        _read(root / NATIVE_PROJECTS_FILE) != parent.registry_bytes
        or _read(root / CONVERSION_AUTHORITY_FILE) != parent.state_bytes
        or physical_node((root / NATIVE_PROJECTS_FILE).lstat())
        != tuple(parent.summary["registry_node"])
        or physical_node((root / CONVERSION_AUTHORITY_FILE).lstat())
        != tuple(parent.summary["conversion_node"])
    ):
        refuse(
            "parent_changed", "parent registry or qualification changed while planning"
        )
    if len(canonical_json_bytes(result)) > limits.maximum_plan_bytes:
        refuse("plan_limit", "complete plan exceeds its reviewed serialization budget")
    return result
