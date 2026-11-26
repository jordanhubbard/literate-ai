"""Filesystem-backed, read-only update planning for initialized projects."""

from __future__ import annotations

import hashlib
import html
import json
import posixpath
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote, urlsplit

from literate_ai._filesystem import path_is_link_or_reparse
from literate_ai.adapters.component_markdown import (
    ComponentMarkdownError,
    parse_component_markdown,
)
from literate_ai.adapters.project_initialization import (
    _STARTER_DOCS,
    _STARTER_TEMPLATE_FILES,
    _TEMPLATE_FILES,
    DEFAULT_AUTHORITY_REVIEW_DOCUMENT,
    INITIALIZATION_BASELINE_FILE,
    INITIALIZATION_ORIGIN_FILE,
    LEGACY_LIFT_SHIFT_ADR,
    ProjectInitializationError,
    _template_text,
    discover_installed_initialization_origin,
    render_starter_document,
)
from literate_ai.adapters.project_layout_planning import _SHARED
from literate_ai.adapters.retained_layout import (
    LEGACY_WRAPPER_COMPONENT,
    RetainedLayoutError,
    read_retained_layout_declaration,
    resolve_structural_layout,
)
from literate_ai.contracts import (
    CatalogImportsFile,
    ContentIdentity,
    HashAlgorithm,
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
    ProjectUpdateClassification,
    ProjectUpdateFile,
    ProjectUpdatePlan,
    canonical_json_bytes,
)
from literate_ai.documentation import (
    _ACTIVE_WORK_PATH,
    DocumentationError,
    _roadmap_area,
    _roadmap_header_fields,
    _roadmap_owner_fragment,
    extract_markdown_links,
    markdown_anchors,
)
from literate_ai.projects import (
    PROJECT_FILENAME,
    LoadedProject,
    ProjectConfigurationStore,
    ProjectError,
    contained_catalog_coordinates,
    discover_project,
)
from literate_ai.repository_urls import repository_origin_continues

_MAXIMUM_UPDATE_INPUT_BYTES = 16 * 1024 * 1024


class ProjectUpdateError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _identity(content: bytes) -> ContentIdentity:
    return ContentIdentity(HashAlgorithm.SHA256, hashlib.sha256(content).hexdigest())


def _project_path(root: Path, relative: str) -> Path:
    path = root
    for part in Path(relative).parts:
        path /= part
        if path_is_link_or_reparse(path):
            raise ProjectUpdateError(
                "project.update_path_unsafe",
                "initialized framework path crosses a link or reparse point: "
                f"{relative}",
            )
    return path


def _read_contract(root: Path, relative: str, contract_type):
    path = _project_path(
        ProjectConfigurationStore.context(root).framework_root, relative
    )
    if not path.is_file():
        raise ProjectUpdateError(
            "project.update_evidence_unavailable",
            f"initialized-project evidence is unavailable: {relative}",
        )
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ProjectUpdateError(
            "project.update_evidence_unavailable",
            f"initialized-project evidence is unreadable: {relative}",
        ) from exc
    if len(content) > _MAXIMUM_UPDATE_INPUT_BYTES:
        raise ProjectUpdateError(
            "project.update_evidence_oversized",
            f"initialized-project evidence exceeds the size limit: {relative}",
        )
    try:
        value = json.loads(content)
        contract = contract_type.from_dict(value)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ProjectUpdateError(
            "project.update_evidence_invalid",
            f"initialized-project evidence is invalid: {relative}",
        ) from exc
    if content != canonical_json_bytes(contract.to_dict()) + b"\n":
        raise ProjectUpdateError(
            "project.update_evidence_noncanonical",
            f"initialized-project evidence is not canonical: {relative}",
        )
    return contract


def _local_bytes(root: Path, relative: str) -> bytes | None:
    path = _project_path(root, relative)
    if not path.exists():
        return None
    if not path.is_file():
        raise ProjectUpdateError(
            "project.update_path_unsafe",
            f"initialized framework path is not a regular file: {relative}",
        )
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise ProjectUpdateError(
            "project.update_file_unreadable",
            f"initialized framework file is unreadable: {relative}",
        ) from exc
    if len(content) > _MAXIMUM_UPDATE_INPUT_BYTES:
        raise ProjectUpdateError(
            "project.update_file_oversized",
            f"initialized framework file exceeds the size limit: {relative}",
        )
    return content


def _local_identity(root: Path, relative: str) -> ContentIdentity | None:
    content = _local_bytes(root, relative)
    return None if content is None else _identity(content)


def _catalog_import_paths(root: Path) -> frozenset[str]:
    """Return destinations recorded as catalog-inherited, not template-scaffolded."""

    root = ProjectConfigurationStore.context(root).framework_root
    imports_path = root / CatalogImportsFile.PATH
    if not imports_path.is_file():
        return frozenset()
    try:
        imports = CatalogImportsFile.load(root)
    except (OSError, TypeError, ValueError):
        return frozenset()
    return frozenset(
        file.path for imported in imports.imports for file in imported.files
    )


_PROJECT_GLOBAL_INPUT_KINDS = frozenset(
    {
        "model-selection",
        "routing-policy",
        "specification-to-source-skill",
        "toolchain-constraint",
        "workflow",
    }
)


def _project_owned_generation_input_paths(
    project: LoadedProject, imported_paths: frozenset[str]
) -> frozenset[str]:
    """Keep local Component closure out of framework-template retirement.

    Older initialization baselines cannot distinguish a copied framework catalog
    member from one retained as project authority. Current catalog-import provenance
    identifies inherited Components; every other Component is project-owned, so its
    project-global workflow, routing, and skill references must survive an update.
    """

    root = project.root
    catalog_roots = tuple(
        {
            *project.definition.skill_roots,
            *project.definition.workflow_roots,
            *project.definition.routing_roots,
        }
    )
    protected: set[str] = set()
    for component_root in project.roots("component"):
        for manifest in sorted(component_root.rglob("component.md")):
            relative = manifest.relative_to(root).as_posix()
            if relative in imported_paths:
                continue
            if manifest.is_symlink() or not manifest.is_file():
                raise ProjectUpdateError(
                    "project.update_local_component_invalid",
                    f"project-owned Component is not a regular file: {relative}",
                )
            try:
                content = _local_bytes(root, relative)
                assert content is not None
                authoring = parse_component_markdown(
                    manifest,
                    content.decode("utf-8"),
                    project_root=root,
                )
            except (ComponentMarkdownError, UnicodeError) as exc:
                raise ProjectUpdateError(
                    "project.update_local_component_invalid",
                    f"project-owned Component is invalid: {relative}",
                ) from exc
            selectors = (
                authoring.workflow_definition,
                authoring.routing_policy,
                *(
                    item
                    for item in authoring.authoring_inputs
                    if item.kind in _PROJECT_GLOBAL_INPUT_KINDS
                ),
            )
            for selector in selectors:
                candidate = Path(selector.uri).as_posix()
                if candidate in imported_paths:
                    continue
                if any(
                    candidate == catalog_root
                    or candidate.startswith(f"{catalog_root}/")
                    for catalog_root in catalog_roots
                ):
                    protected.add(candidate)
    return frozenset(protected)


_LEGACY_SHIM_FLAVOR_PATHS = frozenset(
    {
        "flavors/legacy-project-shim/flavor.md",
        "flavors/legacy-project-shim/openspec/spec.md",
    }
)
_LEGACY_SHIM_DEPENDENT_PATHS = (
    "workflows/legacy-adoption/workflow.md",
    "routing/legacy-adoption.json",
    "skills/specification-to-source/legacy-project-shim/SKILL.md",
)
_LEGACY_HARNESS_INVENTORY_PATH = ".literate/harness-inventory.json"


def _retained_legacy_shim_authority_paths(
    root: Path, *, preserve_evidence: bool
) -> frozenset[str]:
    """Keep conversion-shim authority while retained legacy state still cites it.

    `litai init --convert` (`legacy_shim_authority()` in ``harness_inventory.py``)
    generates the wrapper Component, its Flavor, and that Flavor's specification
    from harness evidence rather than from a static packaged template, so no
    ``_TEMPLATE_FILES``/``_STARTER_TEMPLATE_FILES`` entry ever reproduces them for a
    later framework-template comparison (#340). `_project_owned_generation_input_paths`
    above already protects the workflow, routing, and skill paths a project-owned
    Component's own selectors point *at*; it cannot see the reverse relationship,
    where those retained files -- along with the retained implementation and
    harness evidence -- still cite the wrapper Component's and Flavor's own
    authority by path. Keep those three files out of mechanical template
    retirement for as long as every dependent that still needs them is present.
    A Phase 2 native rewrite that removes the dependents is the only thing that
    legitimately retires them.
    """

    context = ProjectConfigurationStore.context(root)
    inventory_path = context.framework_path(_LEGACY_HARNESS_INVENTORY_PATH)
    if inventory_path.is_symlink() or not inventory_path.is_file():
        return frozenset()
    lift_shift_path = _project_path(
        root,
        context.framework_path(".literate/legacy-lift-shift.json")
        .relative_to(root)
        .as_posix(),
    )
    wrapper_component = LEGACY_WRAPPER_COMPONENT
    implementation = f"{LEGACY_WRAPPER_COMPONENT}/implementation"
    if lift_shift_path.is_file():
        try:
            content = lift_shift_path.read_bytes()
            if len(content) > _MAXIMUM_UPDATE_INPUT_BYTES:
                raise ValueError("lift-and-shift evidence exceeds update input limit")
            lift_shift = json.loads(content)
            if not isinstance(lift_shift, dict):
                raise ValueError("lift-and-shift evidence must be an object")
            layout = resolve_structural_layout(root, lift_shift)
            wrapper_component = layout.wrapper_component
            implementation = layout.implementation_directory
        except (OSError, UnicodeError, ValueError) as exc:
            raise ProjectUpdateError(
                "project.update_retained_layout_invalid",
                "retained lift-and-shift layout is invalid or redirected",
            ) from exc
    else:
        try:
            if read_retained_layout_declaration(root) is not None:
                raise RetainedLayoutError(
                    "declared layout lacks lift-and-shift evidence"
                )
        except RetainedLayoutError as exc:
            raise ProjectUpdateError(
                "project.update_retained_layout_invalid",
                "retained layout declaration is invalid or lacks "
                "lift-and-shift evidence",
            ) from exc
    for relative in (implementation, *_LEGACY_SHIM_DEPENDENT_PATHS):
        candidate = root.joinpath(*Path(relative).parts)
        if candidate.is_symlink() or not candidate.exists():
            return frozenset()
    authority_paths = {
        f"{wrapper_component}/component.md",
        *_LEGACY_SHIM_FLAVOR_PATHS,
    }
    if preserve_evidence:
        wrapper = root / wrapper_component
        authority_paths.update(
            path.relative_to(root).as_posix()
            for pattern in (
                "component.lock.json",
                "component.resolution-audit.json",
                "component.resolution-audit.*.json",
            )
            for path in wrapper.glob(pattern)
        )
    return frozenset(
        path
        for path in authority_paths
        if (candidate := root.joinpath(*Path(path).parts)).is_file()
        and not candidate.is_symlink()
    )


def _upstream_template(
    baseline_paths: set[str], *, profile: str = "generated"
) -> dict[str, bytes]:
    if profile == "native":
        from .native_project_bootstrap import native_template_files

        return native_template_files()
    converted = LEGACY_LIFT_SHIFT_ADR in baseline_paths
    content = {
        destination: _template_text(resource).encode("utf-8")
        for destination, resource in _TEMPLATE_FILES.items()
    }
    if set(_STARTER_TEMPLATE_FILES) & baseline_paths:
        content.update(
            {
                destination: _template_text(resource).encode("utf-8")
                for destination, resource in _STARTER_TEMPLATE_FILES.items()
            }
        )
    content.update(
        {
            destination: render_starter_document(
                destination, converted=converted
            ).encode("utf-8")
            for destination in _STARTER_DOCS
            if destination != DEFAULT_AUTHORITY_REVIEW_DOCUMENT
        }
    )
    return content


def _classification(
    baseline: ContentIdentity | None,
    local: ContentIdentity | None,
    upstream: ContentIdentity | None,
) -> ProjectUpdateClassification:
    if upstream is None:
        return ProjectUpdateClassification.PRESERVED_DYNAMIC
    if baseline is None:
        return (
            ProjectUpdateClassification.ALREADY_CURRENT
            if local == upstream
            else ProjectUpdateClassification.UPSTREAM_ADDED
            if local is None
            else ProjectUpdateClassification.CONFLICT
        )
    if local == baseline:
        return (
            ProjectUpdateClassification.UNCHANGED
            if upstream == baseline
            else ProjectUpdateClassification.UPSTREAM_ONLY
        )
    if local == upstream:
        return ProjectUpdateClassification.ALREADY_CURRENT
    if upstream == baseline:
        return ProjectUpdateClassification.LOCAL_ONLY
    return ProjectUpdateClassification.CONFLICT


def _framework_classification(
    path: str,
    baseline: ContentIdentity | None,
    local: ContentIdentity | None,
    upstream: ContentIdentity | None,
    *,
    catalog_roots: tuple[str, ...],
) -> ProjectUpdateClassification:
    """Retire untouched framework catalog authority without guessing dynamic files.

    The initialization baseline records identities but not whether a file was copied
    from a static template or rendered from project-specific input.  A path beneath a
    declared catalog root supplies the missing fact: it is authority that the framework
    can retire when the current template no longer contains it.  Files outside those
    taxonomic roots retain the conservative identity-only behavior.
    """

    in_catalog = any(
        path == root or path.startswith(f"{root}/") for root in catalog_roots
    )
    if baseline is not None and upstream is None and in_catalog:
        if local is None:
            return ProjectUpdateClassification.ALREADY_CURRENT
        if local == baseline:
            return ProjectUpdateClassification.UPSTREAM_ONLY
        return ProjectUpdateClassification.LOCAL_ONLY
    return _classification(baseline, local, upstream)


def _protect_dangling_roadmap_queue_owners(
    root: Path,
    files: tuple[ProjectUpdateFile, ...],
    upstream_content: dict[str, bytes],
) -> tuple[ProjectUpdateFile, ...]:
    """Refuse a blind queue replacement that would strand a preserved roadmap owner.

    ``docs/roadmap/active-work.md`` is the sole resumable queue; detailed roadmap
    documents record an ``Owning queue item`` link into one of its headings. A
    mechanical upstream-only replacement of the queue file is only safe when no
    preserved dynamic roadmap document still depends on a heading the upstream
    queue does not carry. When one does, classify the queue as a conflict instead
    of applying it, so the operator resolves the collision explicitly.
    """

    active_work_index = next(
        (index for index, item in enumerate(files) if item.path == _ACTIVE_WORK_PATH),
        None,
    )
    if active_work_index is None:
        return files
    active_work_item = files[active_work_index]
    if active_work_item.classification not in (
        ProjectUpdateClassification.UPSTREAM_ONLY,
        ProjectUpdateClassification.MERGEABLE,
    ):
        return files
    upstream_active_work = (
        active_work_item.merged_text.encode("utf-8")
        if active_work_item.merged_text is not None
        else upstream_content.get(_ACTIVE_WORK_PATH)
    )
    if upstream_active_work is None:
        return files
    try:
        upstream_anchors = markdown_anchors(upstream_active_work.decode("utf-8"))
    except UnicodeError:
        return files

    for item in files:
        if item.path == _ACTIVE_WORK_PATH:
            continue
        if item.classification is not ProjectUpdateClassification.PRESERVED_DYNAMIC:
            continue
        if _roadmap_area(item.path) is None:
            continue
        content = _local_bytes(root, item.path)
        if content is None:
            continue
        try:
            text = content.decode("utf-8")
            fields = _roadmap_header_fields(item.path, text)
            _roadmap_owner_fragment(
                path=item.path,
                value=fields["Owning queue item"],
                active_work_anchors=upstream_anchors,
            )
        except (UnicodeError, DocumentationError):
            # Either the owner link is already invalid (a pre-existing defect the
            # documentation validator will surface) or it dangles specifically
            # against the upstream replacement -- both mean a mechanical
            # upstream-only apply of the queue is unsafe here.
            replaced = replace(
                active_work_item,
                classification=ProjectUpdateClassification.CONFLICT,
                merged_text=None,
            )
            return (
                files[:active_work_index] + (replaced,) + files[active_work_index + 1 :]
            )
    return files


def _hold_unplaced_template_additions(project, files, upstream):
    """Existing root authority cannot introduce a new uncontained dependency."""
    pending = {
        item.path
        for item in files
        if item.classification is ProjectUpdateClassification.UPSTREAM_ADDED
        and not item.path.startswith(project.definition.framework_directory + "/")
    }
    result = []
    for item in files:
        reason = None
        if item.path in pending:
            reason = "new framework template needs an owned contained destination"
        elif (
            item.classification
            in {
                ProjectUpdateClassification.UPSTREAM_ONLY,
                ProjectUpdateClassification.MERGEABLE,
            }
            and item.path.casefold().endswith(".md")
            and (content := upstream.get(item.path)) is not None
        ):
            text = (
                item.merged_text
                if item.merged_text is not None
                else content.decode("utf-8")
            )
            for link in extract_markdown_links(text):
                split = urlsplit(html.unescape(link.destination.strip()))
                if split.scheme or split.netloc or not split.path:
                    continue
                target = posixpath.normpath(
                    posixpath.join(posixpath.dirname(item.path), unquote(split.path))
                )
                if target in pending:
                    reason = (
                        f"template references a pending contained destination: {target}"
                    )
                    break
        if reason is not None:
            item = replace(
                item, compatibility=("project.update_layout_pending", reason)
            )
        result.append(item)
    return tuple(result)


class FilesystemProjectUpdateAdapter:
    """Classify baseline/local/current-template state without mutating the project."""

    def __init__(
        self,
        *,
        origin_provider=discover_installed_initialization_origin,
        protected_paths: frozenset[str] = frozenset(),
        base_reader=None,
        catalog_overrides=None,
        adopt_added=False,
        resolutions=None,
    ):
        self._base_reader = base_reader
        self._origin_provider = origin_provider
        self._protected_paths = frozenset(protected_paths)
        self._catalog_overrides = dict(catalog_overrides or {})
        self._adopt_added = adopt_added
        self._resolutions = dict(resolutions or {})

    def plan(self, selected: Path, *, check_compatibility=True) -> ProjectUpdatePlan:
        try:
            project = discover_project(Path(selected))
        except ProjectError as exc:
            raise ProjectUpdateError(exc.code, exc.message) from exc
        if project is None:
            raise ProjectUpdateError(
                "project.not_found", f"no {PROJECT_FILENAME} found from {selected}"
            )
        root = project.root
        previous = _read_contract(
            root, INITIALIZATION_ORIGIN_FILE, ProjectInitializationOrigin
        )
        baseline = _read_contract(
            root, INITIALIZATION_BASELINE_FILE, ProjectInitializationBaseline
        )
        if baseline.origin_identity != previous.identity:
            raise ProjectUpdateError(
                "project.update_origin_mismatch",
                "initialization baseline does not bind the recorded origin",
            )
        try:
            upstream = self._origin_provider()
        except ProjectInitializationError as exc:
            raise ProjectUpdateError(exc.code, exc.message) from exc
        if not isinstance(upstream, ProjectInitializationOrigin):
            raise ProjectUpdateError(
                "project.update_origin_invalid",
                "installed update origin provider returned an invalid contract",
            )
        if (
            not repository_origin_continues(
                previous.repository_url, upstream.repository_url
            )
            or upstream.distribution_name != previous.distribution_name
        ):
            raise ProjectUpdateError(
                "project.update_origin_changed",
                "installed framework origin differs from the initializing origin",
            )
        from .update_merge import UpdateBases, enrich_merge, recover_bases

        bases = UpdateBases(root)
        baseline_by_path = {item.path: item.identity for item in baseline.files}
        baseline_by_path.update(bases.identities("framework"))
        upstream_content = (
            _upstream_template(set(baseline_by_path), profile="native")
            if baseline.profile == "native"
            else _upstream_template(set(baseline_by_path))
        )
        if baseline.profile == "native":
            imports_path = project.framework_root / CatalogImportsFile.PATH
            if (
                project.definition.framework_directory != "litai"
                or any(not path.startswith("litai/") for path in baseline_by_path)
                or imports_path.exists()
                or imports_path.is_symlink()
                or bases.scopes["catalog"]
                or self._catalog_overrides
            ):
                raise ProjectUpdateError(
                    "project.native_update_catalog_unsupported",
                    "Minimal native updates require contained template ownership "
                    "without catalog imports",
                )
            # Application-root legacy-looking metadata is application content.
            # It grants no exclusions from the contained template policy.
            inherited = self._protected_paths
        else:
            imported = _catalog_import_paths(root)
            logical_skills = contained_catalog_coordinates(root)
            inherited = (
                imported
                | frozenset(logical_skills)
                | frozenset(bases.scopes["catalog"])
                | _project_owned_generation_input_paths(project, imported)
                | _retained_legacy_shim_authority_paths(
                    root, preserve_evidence=project.framework_root != root
                )
                | self._protected_paths
                | frozenset(self._catalog_overrides)
            )
        # Catalog-imported paths are classified against the resolved parent catalog
        # by the lineage adapter. Comparing them here against the installed
        # init-template snapshot reports false conflicts (or would mechanically
        # overwrite current catalog bytes with a stale template).
        if baseline.profile != "native" and project.framework_root != root:
            # A migrated generated/retained project still needs its root
            # integration ownership review. Templates cannot take over those
            # coordinates or advance a retained root agent skill independently
            # of its placement and bootstrap references.
            retained_root = (
                {project.definition.agent_skill}
                if project.agent_skill.parent == root
                else set()
            )
            inherited |= _SHARED | retained_root
        paths = sorted((set(baseline_by_path) | set(upstream_content)) - inherited)
        files = tuple(
            ProjectUpdateFile(
                relative,
                _framework_classification(
                    relative,
                    baseline_by_path.get(relative),
                    local := _local_identity(root, relative),
                    current := (
                        _identity(upstream_content[relative])
                        if relative in upstream_content
                        else None
                    ),
                    catalog_roots=tuple(
                        {
                            *project.definition.component_roots,
                            *project.definition.flavor_roots,
                            *project.definition.skill_roots,
                            *project.definition.workflow_roots,
                            *project.definition.routing_roots,
                            *project.definition.mcp_roots,
                        }
                    ),
                ),
                baseline_by_path.get(relative),
                local,
                current,
            )
            for relative in paths
        )
        recover_bases(root, files, bases, self._base_reader, previous)
        files = tuple(
            enrich_merge(
                item,
                bases.get(item.baseline_identity),
                _local_bytes(root, item.path),
                upstream_content.get(item.path),
            )
            for item in files
        )
        files = _protect_dangling_roadmap_queue_owners(root, files, upstream_content)
        from .project_update_compatibility import classify_skill_compatibility

        if check_compatibility:
            files = classify_skill_compatibility(
                project,
                files,
                upstream_content,
                catalog_overrides=self._catalog_overrides,
                adopt_added=self._adopt_added,
                resolutions=self._resolutions,
            )
        if baseline.profile != "native" and project.framework_root != root:
            files = _hold_unplaced_template_additions(project, files, upstream_content)
        return ProjectUpdatePlan(
            project.definition.identity,
            baseline.identity,
            previous,
            upstream,
            files,
            _identity(bases.original or b""),
        )


__all__ = ["FilesystemProjectUpdateAdapter", "ProjectUpdateError"]
