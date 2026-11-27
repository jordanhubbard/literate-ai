"""Declaration views derived from exact, separately admitted Node library data.

The generated/retained owners supply real subject and artifact identities. These
pure projections issue no provider bindings, acceptance or execution authority.
Original CommonJS bytes use the same forwarding owner as SDK composition.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict

from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_composition import (
    node_sdk_provider_module_paths,
    node_sdk_provider_package_files,
)
from literate_ai.adapters.node_sdk_declarations import NodeDeclarationProjection
from literate_ai.adapters.node_sdk_typescript import _inventory
from literate_ai.contracts import ArtifactExport, ContentIdentity, LibraryImportSurface
from literate_ai.contracts.node_sdk import node_sdk_package_boundary_files


def _data_mode():
    return 0o666 if os.name == "nt" else 0o644


def project_node_sdk_declarations(
    *,
    subject: ContentIdentity,
    artifact: ContentIdentity,
    surface: LibraryImportSurface,
    files: tuple[DirectoryExportFile, ...],
) -> NodeDeclarationProjection:
    """Use the actual dual SDK package, without inventing a retained Component."""
    if not isinstance(surface, LibraryImportSurface) or not surface.node_sdk_exports:
        raise ValueError("SDK declaration projection requires dual output authority")
    files = _inventory(files, maximum=4094)
    content = {file.path: file.content for file in files}
    exports = {}
    by_module = {entry.module: entry for entry in surface.node_sdk_exports}
    for entry in surface.node_sdk_exports:
        key = (
            "."
            if entry.module == surface.package
            else "./" + entry.module[len(surface.package) + 1 :]
        )
        exports[key] = {
            condition: {
                "types": "./" + entry.paths[index + 1],
                "default": "./" + entry.paths[index],
            }
            for condition, index in (("require", 0), ("import", 2))
        }
        if any(path not in content for path in entry.paths):
            raise ValueError("SDK declaration projection lacks public output files")
    metadata = content.get("package.json", b"")
    if not 1 <= len(metadata) <= 65536:
        raise ValueError("SDK declaration package manifest exceeds its byte bound")
    metadata = json.loads(metadata)
    if (
        type(metadata) is not dict
        or metadata.get("name") != surface.package
        or metadata.get("exports") != exports
        or metadata.get("type") != "commonjs"
        or any(
            content.get(path) != data
            for path, data in node_sdk_package_boundary_files()
        )
    ):
        raise ValueError("SDK declaration package differs from exact output authority")
    prefix = "node_modules/" + surface.package + "/"
    capabilities = []
    declarations = defaultdict(set)
    for capability in surface.capabilities:
        entry = by_module[capability.module]
        paths = tuple(prefix + entry.paths[index] for index in (1, 3))
        capabilities.append((capability.capability, *paths))
        for path in paths:
            declarations[path].update(capability.symbols)
    return NodeDeclarationProjection(
        subject,
        artifact,
        surface.identity,
        tuple(
            DirectoryExportFile(prefix + file.path, file.content, file.mode)
            for file in files
        ),
        tuple(sorted(capabilities)),
        tuple(
            (path, tuple(sorted(symbols)))
            for path, symbols in sorted(declarations.items())
        ),
    )


def project_commonjs_library_declarations(
    provider: ArtifactExport,
    surface: LibraryImportSurface,
    files: tuple[DirectoryExportFile, ...],
) -> NodeDeclarationProjection:
    """Reuse byte-preserving provider facades in a verifier-owned package view."""
    projected = node_sdk_provider_package_files(provider, surface, files)
    prefix = "node_modules/" + surface.package + "/"
    by_module = {entry.module: entry for entry in surface.declarations}
    exports = {}
    for entry in surface.declarations:
        runtime, declaration = node_sdk_provider_module_paths(provider, entry)
        key = (
            "."
            if entry.module == surface.package
            else "./" + entry.module[len(surface.package) + 1 :]
        )
        exports[key] = {
            condition: {"types": "./" + declaration, "default": "./" + runtime}
            for condition in ("require", "import")
        }
    manifest = (
        json.dumps(
            {
                "name": surface.package,
                "private": True,
                "type": "commonjs",
                "exports": exports,
            },
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    capabilities = []
    declarations = defaultdict(set)
    for capability in surface.capabilities:
        entry = by_module[capability.module]
        _, declaration = node_sdk_provider_module_paths(provider, entry)
        path = prefix + declaration
        capabilities.append((capability.capability, path, path))
        declarations[path].update(capability.symbols)
    return NodeDeclarationProjection(
        provider.component_revision,
        provider.identity,
        surface.identity,
        (
            DirectoryExportFile(prefix + "package.json", manifest, _data_mode()),
            *(
                DirectoryExportFile(prefix + file.path, file.content, file.mode)
                for file in projected
            ),
        ),
        tuple(sorted(capabilities)),
        tuple(
            (path, tuple(sorted(symbols)))
            for path, symbols in sorted(declarations.items())
        ),
    )
