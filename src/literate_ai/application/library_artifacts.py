"""Pure projection of reviewed library capability authority into import names."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import PurePosixPath

from literate_ai.contracts import ContentIdentity, CppLibraryLayout
from literate_ai.contracts.elixir_libraries import elixir_namespace
from literate_ai.contracts.executable_components.commands import (
    LibraryCapabilityImport,
    LibraryImportSurface,
)
from literate_ai.contracts.library_imports import AuthoredLibraryImport


def javascript_module_paths(
    surface: LibraryImportSurface, module: str
) -> tuple[str, str | None]:
    """Resolve only declared public authority; preserve the established @1 path."""
    if surface.language != "javascript" or module not in {
        item.module for item in surface.capabilities
    }:
        raise ValueError("module is not a public JavaScript library import")
    if surface.declarations:
        declared = next(item for item in surface.declarations if item.module == module)
        return declared.runtime, declared.declaration
    return "source/" + module + ".js", None


def require_declared_commonjs_files(
    surface: LibraryImportSurface, files: Mapping[str, bytes]
) -> None:
    """Require the explicit format boundary before any consumer can load @2."""
    if not surface.declarations:
        return
    for declared in surface.declarations:
        if declared.runtime not in files or declared.declaration not in files:
            raise ValueError(
                "JavaScript provider runtime or declaration is absent from sealed bytes"
            )
    for path, content in files.items():
        if PurePosixPath(path).name != "package.json":
            continue
        if len(content) > 65536:
            raise ValueError("CommonJS package boundary exceeds its metadata bound")
        metadata = json.loads(content)
        if (
            not isinstance(metadata, dict)
            or metadata.get("type", "commonjs") != "commonjs"
        ):
            raise ValueError(
                "declared CommonJS provider has a conflicting package boundary"
            )


def project_library_import_surface(
    component_name: str,
    language: str,
    capabilities: tuple[tuple[str, ContentIdentity], ...],
    *,
    declarations: tuple[AuthoredLibraryImport, ...] = (),
) -> LibraryImportSurface:
    """Project reviewed imports or the established convention shared by adapters."""

    if not isinstance(declarations, tuple) or any(
        not isinstance(item, AuthoredLibraryImport) for item in declarations
    ):
        raise ValueError("native imports require typed declarations")
    selected = tuple(item for item in declarations if item.language == language)
    if selected:
        interfaces = dict(capabilities)
        if (
            len(interfaces) != len(capabilities)
            or tuple(item.capability for item in selected) != tuple(sorted(interfaces))
            or len({item.package for item in selected}) != 1
        ):
            raise ValueError(
                "native import declarations must cover every current interface"
            )
        module_files = {}
        for item in selected:
            if item.node_module is not None:
                previous = module_files.setdefault(item.module, item.node_module)
                if previous != item.node_module:
                    raise ValueError(
                        "conflicting declaration files for one public module"
                    )
        if module_files and any(item.node_module is None for item in selected):
            raise ValueError(
                "declaration-bearing surfaces require complete module authority"
            )
        sdk_exports = {}
        for item in selected:
            for export in item.node_sdk_exports:
                previous = sdk_exports.setdefault(export.module, export)
                if previous != export:
                    raise ValueError("conflicting SDK files for one public module")
        return LibraryImportSurface(
            language,
            selected[0].package,
            tuple(
                LibraryCapabilityImport(
                    item.capability,
                    interfaces[item.capability],
                    item.module,
                    item.symbols,
                )
                for item in selected
            ),
            declarations=tuple(module_files[name] for name in sorted(module_files)),
            node_sdk_exports=tuple(sdk_exports[name] for name in sorted(sdk_exports)),
        )
    package = component_name.replace("-", "_")
    imports = []
    for capability, interface_identity in capabilities:
        prefix = f"{component_name}."
        qualified = capability.startswith(prefix)
        relative = capability.removeprefix(prefix)
        segments = tuple(part.replace("-", "_") for part in relative.split("."))
        symbol = segments[-1]
        if language == "elixir":
            module = (
                elixir_namespace(package)
                + "."
                + "".join(part[:1].upper() + part[1:] for part in symbol.split("_"))
            )
        elif language == "python":
            module = f"{package}.{symbol}"
        elif language == "javascript":
            module = f"{package}/{symbol}"
        elif language == "rust":
            if qualified and len(segments) > 1:
                module = "::".join((package, *segments[:-1]))
                raw_symbol = relative.rsplit(".", 1)[-1]
                if raw_symbol.startswith("type-"):
                    symbol = "".join(
                        part.title()
                        for part in raw_symbol.removeprefix("type-").split("-")
                    )
                elif raw_symbol.startswith("fn-"):
                    symbol = raw_symbol.removeprefix("fn-").replace("-", "_")
            else:
                module = f"{package}::{symbol}"
        else:
            raise ValueError(f"importable libraries do not yet support {language!r}")
        imports.append(
            LibraryCapabilityImport(capability, interface_identity, module, (symbol,))
        )
    return LibraryImportSurface(language, package, tuple(imports))


def project_cpp_library_layout(
    surface: LibraryImportSurface, *, kind: str, platform: str
) -> CppLibraryLayout:
    """Resolve the selected product kind into the target's native file roles."""
    if surface.language != "cpp":
        raise ValueError("native C++ layout requires C++ import authority")
    if platform not in {"linux", "macos", "windows"}:
        raise ValueError("unsupported C++ native product platform")
    if kind not in {"static", "shared"}:
        raise ValueError("C++ product kind must be static or shared")
    headers = tuple(sorted({"include/" + item.module for item in surface.capabilities}))
    package = surface.package
    if platform == "windows":
        link = f"lib/{package}.lib"
        runtime = (f"bin/{package}.dll",) if kind == "shared" else ()
    else:
        suffix = (
            ".a" if kind == "static" else ".dylib" if platform == "macos" else ".so"
        )
        link = f"lib/lib{package}{suffix}"
        runtime = (link,) if kind == "shared" else ()
    return CppLibraryLayout(kind, headers, (link,), runtime)


__all__ = ["project_library_import_surface", "project_cpp_library_layout"]


def javascript_library_source_component(
    provider_revision: ContentIdentity, surface: LibraryImportSurface
) -> dict[str, object]:
    """Exact pre-generation source-BOM declaration; not artifact admission."""
    if (
        not isinstance(provider_revision, ContentIdentity)
        or not isinstance(surface, LibraryImportSurface)
        or surface.language != "javascript"
    ):
        raise ValueError(
            "JavaScript source library declaration requires typed authority"
        )
    return {
        "type": "library",
        ("bom-ref"): (
            f"urn:project:library-import:{provider_revision.digest}:"
            f"{surface.identity.digest}"
        ),
        "name": surface.package,
        "version": provider_revision.uri,
        "purl": (
            f"pkg:generic/project-library/{surface.package}@{provider_revision.digest}"
        ),
        "properties": [
            {"name": "literate-ai:dependency-kind", "value": "package"},
            {"name": "literate-ai:dependency-scope", "value": "runtime"},
            {
                "name": "project:library-provider-revision",
                "value": provider_revision.uri,
            },
            {
                "name": "project:library-import-surface",
                "value": surface.identity.uri,
            },
        ],
    }
