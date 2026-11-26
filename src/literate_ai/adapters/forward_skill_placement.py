"""Resolve explicit catalog placement through established import ownership."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import PurePosixPath

from literate_ai.adapters.catalog_import import read_contained_catalog_imports
from literate_ai.adapters.project_initialization import INITIALIZATION_BASELINE_FILE
from literate_ai.adapters.project_layout_planning import _SHARED, _fail
from literate_ai.adapters.project_updates import _read_contract
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    ProjectInitializationBaseline,
    canonical_json_bytes,
)
from literate_ai.projects import (
    CATALOG_PLACEMENT_ROOTS,
    CONTAINED_SKILL_ROOT,
    FORWARD_SKILL_ROOT,
    catalog_placement_root,
)


def _relocate_paths(values, coordinates):
    result = {}
    for path, value in values.items():
        target = coordinates.get(path, path)
        if target in result:
            _fail("skill_placement_conflict", f"duplicate Skill update base: {target}")
        result[target] = value
    return result


def plan_forward_skill_placement(
    snapshot,
    lineage,
    members,
    *,
    read_file,
    include_related=False,
):
    """Return exact physical moves and rewritten producer-record bytes."""
    if "skills" not in snapshot.definition.skill_roots:
        _fail(
            "skill_placement_unavailable",
            "legacy project declares no root Skill catalog",
        )
    imports = read_contained_catalog_imports(snapshot)
    if imports is None:
        _fail("skill_placement_unavailable", "imported Skill provenance is missing")
    owners = Counter(row.path for item in imports.imports for row in item.files)
    inherited = {
        (
            node.project_id,
            node.project_identity.uri,
            f"git:{node.repository_url}@{node.resolved_revision}",
        )
        for node in lineage.nodes
    }
    coordinates = {}
    blockers = []
    integrations = {
        name: read_file(name)
        for name, member in members.items()
        if include_related
        and (
            name in _SHARED
            or name.startswith(".github/workflows/")
            or member.get("role") == "application"
        )
    }
    for item in imports.imports:
        forward = item.kind == "skill" and item.name.startswith(
            "specification-to-source/"
        )
        if not forward and (
            not include_related or item.kind not in CATALOG_PLACEMENT_ROOTS
        ):
            continue
        catalog_root = catalog_placement_root(item.kind, item.files[0].path)
        if catalog_root not in getattr(snapshot.definition, f"{item.kind}_roots"):
            continue
        if (
            item.source.project_id,
            item.source.project_identity,
            item.source.ref,
        ) not in inherited:
            continue
        coordinate = f"{catalog_root}/{item.name}"
        prefix = coordinate + "/"
        sentinel = {
            "skill": "SKILL.md",
            "flavor": "flavor.md",
            "component": "component.md",
        }.get(item.kind)
        expected = prefix + sentinel if sentinel else coordinate
        if not any(row.path == expected for row in item.files):
            _fail(
                "skill_placement_conflict",
                f"missing owned {item.kind} manifest: {item.name}",
            )
        for row in item.files:
            found = members.get(row.path, {})
            if (
                not (
                    row.path.startswith(prefix) if sentinel else row.path == coordinate
                )
                or owners[row.path] != 1
                or found.get("role") == "application"
            ):
                _fail("skill_placement_conflict", f"mixed Skill ownership: {row.path}")
            if found.get("identity") != row.identity:
                _fail(
                    "skill_source_changed",
                    f"checked {item.kind} import differs: {row.path}",
                )
        integration_refs = [
            {
                "path": name,
                "owner": item.name,
                "reason": f"host reference to {row.path}",
            }
            for name, content in integrations.items()
            for row in item.files
            if row.path.encode() in content
        ]
        if integration_refs:
            blockers.extend(integration_refs)
            continue
        if include_related and item.kind == "skill":
            authored = read_file(f"{prefix}{sentinel}")
            commands = [
                row.path
                for row in item.files
                if PurePosixPath(row.path).suffix.casefold()
                in {".py", ".sh", ".ps1", ".bat"}
                and row.path.encode() in authored
            ]
            if commands:
                blockers.extend(
                    {
                        "path": path,
                        "owner": item.name,
                        "reason": "literal application-root command",
                    }
                    for path in commands
                )
                continue
        coordinates.update({row.path: f"litai/{row.path}" for row in item.files})
    if not coordinates:
        _fail("skill_placement_unavailable", f"no inherited {FORWARD_SKILL_ROOT} files")
    if CONTAINED_SKILL_ROOT in snapshot.definition.skill_roots:
        _fail(
            "skill_placement_conflict", "the contained Skill root is already declared"
        )

    def relocate(record):
        return replace(
            record,
            files=tuple(
                replace(row, path=coordinates.get(row.path, row.path))
                for row in record.files
            ),
        )

    projected = replace(
        imports,
        imports=tuple(relocate(item) for item in imports.imports),
        decisions=tuple(relocate(item) for item in imports.decisions),
    )
    baseline = _read_contract(
        snapshot.root, INITIALIZATION_BASELINE_FILE, ProjectInitializationBaseline
    )
    relocated_baseline = replace(
        baseline,
        files=tuple(
            sorted(
                (
                    replace(row, path=coordinates.get(row.path, row.path))
                    for row in baseline.files
                ),
                key=lambda row: row.path,
            )
        ),
    )
    bases = UpdateBases(snapshot.root)
    for name, paths in bases.scopes.items():
        bases.scopes[name] = _relocate_paths(paths, coordinates)
    bases.sources = _relocate_paths(bases.sources, coordinates)
    return (
        coordinates,
        {
            CatalogImportsFile.PATH: canonical_json_bytes(projected.to_dict()) + b"\n",
            INITIALIZATION_BASELINE_FILE: canonical_json_bytes(
                relocated_baseline.to_dict()
            )
            + b"\n",
            ".literate/update-bases.json": bases.serialized(),
        },
        blockers,
    )
