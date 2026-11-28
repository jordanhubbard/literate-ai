"""Exact Python import declarations on selected managed Component revisions."""

from __future__ import annotations

import keyword
import re
from collections.abc import Mapping

from literate_ai.contracts.executable_components.commands import LibraryImportSurface
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.sbom import (
    CycloneDxManagedGraph,
    ManagedComponentKind,
    component_bom_ref,
)

PYTHON_IMPORT_PROPERTY = "literate-ai:python-top-level-import"
ManagedPythonImports = tuple[tuple[ContentIdentity, str], ...]


def recipe_document_python_imports(document, graph) -> ManagedPythonImports:
    """Read selected mappings from an independently hash-bound recipe preimage."""

    dependencies = document.get("library_dependencies", [])
    if not isinstance(dependencies, list):
        raise ValueError("recipe library dependencies must be canonical records")
    declarations = set()
    for dependency in dependencies:
        if not isinstance(dependency, dict) or set(dependency) != {
            "provider_component_revision",
            "capability",
            "interface_identity",
            "import_surface",
        }:
            raise ValueError("invalid recipe library dependency record")
        provider = ContentIdentity.from_dict(dependency["provider_component_revision"])
        interface = ContentIdentity.from_dict(dependency["interface_identity"])
        surface = LibraryImportSurface.from_dict(dependency["import_surface"])
        capability = surface.capability(dependency["capability"])
        if capability.interface_identity != interface:
            raise ValueError("recipe dependency interface differs from its surface")
        if surface.language == "python":
            declarations.add((provider, capability.module.split(".")[0]))
    result = tuple(sorted(declarations, key=lambda item: (item[0].uri, item[1])))
    managed_python_import_map(graph, result)
    return result


def managed_python_import_map(
    graph: CycloneDxManagedGraph, declarations: ManagedPythonImports
) -> dict[str, tuple[str, ...]]:
    """Join canonical declarations to exact direct managed Component nodes."""

    if not isinstance(declarations, tuple):
        raise ValueError("managed Python imports must be immutable declarations")
    components = {item.bom_ref: item for item in graph.components}
    direct = {
        edge.target_ref for edge in graph.edges if edge.source_ref == graph.root_ref
    }
    result: dict[str, list[str]] = {}
    order = []
    for declaration in declarations:
        if not isinstance(declaration, tuple) or len(declaration) != 2:
            raise ValueError("invalid managed Python import declaration")
        revision, alias = declaration
        if (
            not isinstance(revision, ContentIdentity)
            or not isinstance(alias, str)
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias) is None
            or keyword.iskeyword(alias)
        ):
            raise ValueError("invalid managed Python provider or top-level import")
        ref = component_bom_ref(revision)
        provider = components.get(ref)
        if (
            provider is None
            or provider.identity != revision
            or provider.kind is not ManagedComponentKind.COMPONENT
            or ref not in direct
        ):
            raise ValueError("managed Python provider is not an exact direct Component")
        order.append((revision.uri, alias))
        result.setdefault(ref, []).append(alias)
    if order != sorted(set(order)):
        raise ValueError("managed Python import declarations must be canonical")
    return {ref: tuple(aliases) for ref, aliases in result.items()}


def source_managed_python_imports(
    document: Mapping[str, object], graph: CycloneDxManagedGraph
) -> ManagedPythonImports:
    """Read declarations from a validated predecessor, retaining provider identity."""

    components = {item.bom_ref: item for item in graph.components}
    declarations = []
    inventory = [document["metadata"]["component"], *document["components"]]
    for item in inventory:
        provider = components.get(item["bom-ref"])
        if provider is None:
            continue
        for prop in item.get("properties", ()):
            if prop["name"] == PYTHON_IMPORT_PROPERTY:
                declarations.append((provider.identity, prop["value"]))
    result = tuple(sorted(declarations, key=lambda item: (item[0].uri, item[1])))
    managed_python_import_map(graph, result)
    return result


def require_managed_python_imports(
    document: Mapping[str, object],
    graph: CycloneDxManagedGraph,
    declarations: ManagedPythonImports,
) -> None:
    """Reject missing, additional or moved managed aliases against exact inputs."""

    managed_python_import_map(graph, declarations)
    if source_managed_python_imports(document, graph) != declarations:
        raise ValueError(
            "CycloneDX managed Python imports differ from selected authority"
        )
