"""Add a Flavor to an existing project without re-initializing it."""

from __future__ import annotations

import os
import posixpath
import stat
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from typing import Any

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.adapters.component_locks import LOCK_FILENAME
from literate_ai.adapters.flavor_markdown import parse_flavor_markdown
from literate_ai.adapters.project_initialization import (
    _FLAVOR_CANONICAL_BY_DIRECTORY,
    _TEMPLATE_FILES,
    _template_text,
    canonical_flavor_selector,
    flavor_selector_directory,
)
from literate_ai.adapters.repository_refresh import _file
from literate_ai.projects import (
    PROJECT_FILENAME,
    ProjectConfigurationStore,
    ProjectContext,
    ProjectError,
)

FLAVOR_ADD_SCHEMA = "literate-ai/flavor-add@1"
_SKIP_LOCK_PARTS = frozenset(
    {"_build", ".git", ".codegraph", "node_modules", "__pycache__"}
)
_SKILL_FILES_BY_DIRECTORY = {
    "lang-elixir": (
        "skills/specification-to-source/elixir-portable-application/SKILL.md",
    ),
    "deploy-docker": (
        "skills/specification-to-source/docker-container-application/SKILL.md",
    ),
    "lang-typescript": (
        "skills/specification-to-source/typescript-portable-application/SKILL.md",
    ),
    "lang-zig": ("skills/specification-to-source/zig-portable-application/SKILL.md",),
    "package-npm": ("skills/specification-to-source/javascript-ecosystem/SKILL.md",),
}


class FlavorAddError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def add_flavor_to_project(
    root: Path, selector: str, *, set_default: bool = True
) -> dict[str, Any]:
    """Stamp one Flavor onto an existing project and optionally select it as default."""

    try:
        snapshot = ProjectConfigurationStore.discover(root)
    except ProjectError as exc:
        raise FlavorAddError(exc.code, exc.message) from exc
    if snapshot is None:
        raise FlavorAddError(
            "project.not_found", f"no {PROJECT_FILENAME} found from {root}"
        )
    signed = _require_add_selector(selector)
    canonical = canonical_flavor_selector(signed)
    directory = flavor_selector_directory(signed)
    if directory not in _FLAVOR_CANONICAL_BY_DIRECTORY:
        raise FlavorAddError(
            "flavor.add_unknown",
            f"Flavor {selector!r} is not in the shipped init catalog",
        )
    incoming = _template_authoring(directory)
    current = _declared_flavor(snapshot, directory)
    if current is not None:
        if (current[1].namespace, current[1].name) != (
            incoming.namespace,
            incoming.name,
        ):
            raise FlavorAddError(
                "flavor.add_catalog_invalid",
                "current Flavor coordinate differs from the shipped selector",
            )
        incoming = current[1]
    store = ProjectConfigurationStore(snapshot.root)
    selected = list(snapshot.definition.default_flavor_selectors)
    if canonical in selected:
        created = _stamp_flavor_files(
            snapshot, directory, overwrite=False, incoming=incoming, current=current
        )
        if not created:
            return {
                "schema": FLAVOR_ADD_SCHEMA,
                "state": "unchanged",
                "selector": canonical,
                "directory": directory,
                "created": [],
                "locks_invalidated": [],
            }
        locks = _invalidate_component_locks(snapshot.root)
        return {
            "schema": FLAVOR_ADD_SCHEMA,
            "state": "completed",
            "selector": canonical,
            "directory": directory,
            "created": created,
            "locks_invalidated": locks,
        }
    if not set_default:
        # Install files only — no default selection, no conflict check.
        # Used for polyglot projects where per-Component flavor_slots
        # select this Flavor at lock/build time.
        created = _stamp_flavor_files(
            snapshot, directory, overwrite=False, incoming=incoming, current=current
        )
        locks = _invalidate_component_locks(snapshot.root)
        return {
            "schema": FLAVOR_ADD_SCHEMA,
            "state": "completed",
            "selector": canonical,
            "directory": directory,
            "default": False,
            "created": created,
            "locks_invalidated": locks,
        }
    _reject_conflicts(snapshot, incoming, directory)
    created = _stamp_flavor_files(
        snapshot, directory, overwrite=False, incoming=incoming, current=current
    )
    updated = replace(
        snapshot.definition,
        default_flavor_selectors=(
            *snapshot.definition.default_flavor_selectors,
            canonical,
        ),
    )
    try:
        store.update(snapshot, updated)
    except ProjectError as exc:
        raise FlavorAddError(exc.code, exc.message) from exc
    locks = _invalidate_component_locks(snapshot.root)
    return {
        "schema": FLAVOR_ADD_SCHEMA,
        "state": "completed",
        "selector": canonical,
        "directory": directory,
        "created": created,
        "locks_invalidated": locks,
    }


def _require_add_selector(selector: str) -> str:
    if not isinstance(selector, str) or not selector.strip():
        raise FlavorAddError(
            "flavor.add_selector_invalid", "Flavor selector is required"
        )
    text = selector.strip()
    if text.startswith("-"):
        raise FlavorAddError(
            "flavor.add_subtract_unsupported",
            "litai flavor add cannot subtract a Flavor",
        )
    return text if text.startswith("+") else f"+{text}"


def _template_authoring(directory: str):
    relative = f"flavors/{directory}/flavor.md"
    return parse_flavor_markdown(
        _template_text(relative).encode("utf-8"), source=relative
    )


def _flavor_identities(authoring, directory: str) -> set[str]:
    coordinate = f"flavor://{authoring.namespace}/{authoring.name}"
    return {
        coordinate,
        authoring.name,
        directory,
        f"flavor://literate-ai/{authoring.name}",
        f"flavor://literate-ai/{directory}",
    }


def _reject_conflicts(project, incoming, directory: str) -> None:
    new_ids = _flavor_identities(incoming, directory)
    new_conflicts = set(incoming.conflicts)
    for current in project.definition.default_flavor_selectors:
        signed = current if current.startswith(("+", "-")) else f"+{current}"
        existing_directory = flavor_selector_directory(signed)
        current_authority = _declared_flavor(project, existing_directory)
        existing = (
            current_authority[1]
            if current_authority is not None
            else _template_authoring(existing_directory)
        )
        existing_ids = _flavor_identities(existing, existing_directory)
        existing_conflicts = set(existing.conflicts)
        if existing_ids & new_conflicts or new_ids & existing_conflicts:
            raise FlavorAddError(
                "flavor.add_conflict",
                f"{existing.name} conflicts with {incoming.name}; leave the project "
                "unchanged",
            )


def _declared_flavor(project, directory):
    """Read unique declared current authoring; unsafe metadata never falls back."""
    selected = []
    try:
        for relative in project.definition.flavor_roots:
            path = project.root / relative / directory / "flavor.md"
            require_safe_directory(path.parent, allow_missing=True)
            if not os.path.lexists(path):
                continue
            item = _file(path, maximum_bytes=2 * 1024**2)
            selected.append(
                (path, parse_flavor_markdown(item.content, source=str(path)), item)
            )
    except (OSError, ValueError) as error:
        raise FlavorAddError(
            "flavor.add_catalog_invalid",
            "declared current Flavor is unsafe or unreadable",
        ) from error
    if len(selected) > 1:
        raise FlavorAddError(
            "flavor.add_catalog_ambiguous",
            "multiple declared catalogs contain this Flavor",
        )
    return selected[0] if selected else None


def _skill_destination(project, flavor_directory, uri):
    destination = Path(os.path.abspath(flavor_directory / uri))
    if not destination.is_relative_to(project.root) or not any(
        destination.is_relative_to(project.root / name)
        for name in project.definition.skill_roots
    ):
        raise FlavorAddError(
            "flavor.add_catalog_invalid",
            "associated Skill is outside declared Skill catalogs",
        )
    return destination


def _stamp_flavor_files(
    project, directory: str, *, overwrite: bool, incoming, current
) -> list[str]:
    context = ProjectContext(project.root, project.manifest_path.parent)
    latest = _declared_flavor(project, directory)
    if (current is None) != (latest is None) or (
        current is not None
        and (
            current[0] != latest[0]
            or current[2].signature != latest[2].signature
            or current[2].content != latest[2].content
        )
    ):
        raise FlavorAddError(
            "flavor.add_changed", "current Flavor changed during installation"
        )
    if current is None:
        catalog = context.framework_path("flavors")
        if catalog not in tuple(
            project.root / name for name in project.definition.flavor_roots
        ):
            raise FlavorAddError(
                "flavor.add_catalog_unconfigured",
                "canonical Flavor catalog is not declared",
            )
        flavor_directory, authoring = catalog / directory, incoming
    else:
        path, authoring, _observation = current
        if (authoring.namespace, authoring.name) != (incoming.namespace, incoming.name):
            raise FlavorAddError(
                "flavor.add_catalog_invalid",
                "current Flavor coordinate differs from the shipped selector",
            )
        flavor_directory = path.parent
    resource_root = files("literate_ai.project_template").joinpath("flavors", directory)
    if not resource_root.is_dir():
        raise FlavorAddError(
            "flavor.add_unknown",
            f"Flavor directory {directory!r} is missing from the init template",
        )
    writes = []
    for relative, resource in _walk_template(resource_root, f"flavors/{directory}"):
        suffix = Path(relative).relative_to(Path("flavors") / directory)
        writes.append((flavor_directory / suffix, resource.read_bytes()))
    for relative in _SKILL_FILES_BY_DIRECTORY.get(directory, ()):
        if relative not in _TEMPLATE_FILES:
            continue
        references = [
            item
            for item in authoring.authoring_inputs
            if item.kind == "specification-to-source-skill"
            and posixpath.normpath(posixpath.join("flavors", directory, item.uri))
            == relative
        ]
        if not references and current is not None:
            # A complete current custom reference is already installed. Preserve
            # it without copying packaged bytes into an unrelated Skill path.
            for reference in authoring.authoring_inputs:
                if reference.kind != "specification-to-source-skill":
                    continue
                selected = _skill_destination(project, flavor_directory, reference.uri)
                try:
                    require_safe_directory(selected.parent)
                    node = selected.lstat()
                    if not stat.S_ISREG(node.st_mode) or stat_is_link_or_reparse(node):
                        raise ValueError("not direct current Skill")
                except (OSError, ValueError) as error:
                    raise FlavorAddError(
                        "flavor.add_catalog_invalid",
                        "current custom Skill is unavailable or unsafe",
                    ) from error
            continue
        if len(references) != 1:
            raise FlavorAddError(
                "flavor.add_catalog_invalid",
                "shipped Skill has no unique current relative reference",
            )
        destination = _skill_destination(project, flavor_directory, references[0].uri)
        writes.append(
            (destination, _template_text(_TEMPLATE_FILES[relative]).encode("utf-8"))
        )
    # Refuse all unsafe/ambiguous placement before the first output is created.
    for destination, _ in writes:
        try:
            require_safe_directory(destination.parent, allow_missing=True)
            if os.path.lexists(destination):
                node = destination.lstat()
                if not stat.S_ISREG(node.st_mode) or stat_is_link_or_reparse(node):
                    raise ValueError("not direct regular metadata")
        except (OSError, ValueError) as error:
            raise FlavorAddError(
                "flavor.add_catalog_invalid", "Flavor output placement is unsafe"
            ) from error
    created = []
    for destination, content in writes:
        if destination.exists() and not overwrite:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        require_safe_directory(destination.parent)
        if overwrite:
            destination.write_bytes(content)
        else:
            try:
                with destination.open("xb") as output:
                    output.write(content)
            except FileExistsError as error:
                raise FlavorAddError(
                    "flavor.add_changed", "Flavor output changed during installation"
                ) from error
        created.append(destination.relative_to(project.root).as_posix())
    return created


def _walk_template(resource, prefix: str):
    if resource.is_file():
        yield prefix, resource
        return
    for child in sorted(resource.iterdir(), key=lambda item: item.name):
        child_prefix = f"{prefix}/{child.name}"
        yield from _walk_template(child, child_prefix)


def _invalidate_component_locks(root: Path) -> list[str]:
    invalidated: list[str] = []
    search_roots = [root]
    cell = os.environ.get("LITAI_MATRIX_CELL_ROOT")
    if cell:
        search_roots.append(Path(cell))
    for search in search_roots:
        if not search.is_dir():
            continue
        for lock in search.rglob(LOCK_FILENAME):
            if any(part in _SKIP_LOCK_PARTS for part in lock.parts):
                continue
            if not (lock.parent / "component.md").is_file():
                continue
            lock.unlink()
            try:
                invalidated.append(lock.relative_to(root).as_posix())
            except ValueError:
                invalidated.append(str(lock))
    return invalidated


__all__ = ["FLAVOR_ADD_SCHEMA", "FlavorAddError", "add_flavor_to_project"]
