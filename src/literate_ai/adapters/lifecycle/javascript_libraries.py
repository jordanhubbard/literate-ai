"""Artifact-local native imports for exact generic JavaScript library bindings."""

from __future__ import annotations

import json
import os
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import path_is_link_or_reparse, require_safe_directory
from literate_ai.adapters.action_build_limits import (
    MAX_BUILD_ARCHIVE_BYTES,
    MAX_BUILD_ARCHIVE_FILES,
)
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    read_directory_export,
)
from literate_ai.contracts import (
    ArtifactExport,
    BlobRef,
    ComponentCommandContract,
    ContentIdentity,
    canonical_identity,
)
from literate_ai.contracts.executable_components.commands import (
    LibraryConsumerBinding,
    LibraryImportSurface,
)
from literate_ai.contracts.paths import canonical_relative_posix_path

SCHEMA = "literate-ai/javascript-library-imports@1"
_PACKAGE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")


@dataclass(frozen=True, slots=True)
class JavaScriptLibraryPackage:
    name: str
    provider: ArtifactExport
    surface: LibraryImportSurface
    bindings: tuple[LibraryConsumerBinding, ...]
    files: tuple[DirectoryExportFile, ...]
    exports: tuple[tuple[str, str], ...]

    @property
    def surface_identity(self) -> ContentIdentity:
        return self.surface.identity


@dataclass(frozen=True, slots=True)
class JavaScriptLibraryImports:
    consumer: ContentIdentity
    packages: tuple[JavaScriptLibraryPackage, ...]
    builtin_modules: tuple[str, ...]

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(
            {
                "schema": SCHEMA,
                "consumer": self.consumer.to_dict(),
                "builtin_modules": list(self.builtin_modules),
                "packages": [
                    {
                        "name": p.name,
                        "artifact": p.provider.identity.to_dict(),
                        "surface": p.surface_identity.to_dict(),
                        "bindings": [b.to_dict() for b in p.bindings],
                        "exports": dict(p.exports),
                    }
                    for p in self.packages
                ],
            }
        )


def prepare_javascript_library_imports(
    consumer: ComponentCommandContract,
    providers: tuple[ArtifactExport, ...],
    bindings: tuple[LibraryConsumerBinding, ...],
    contracts: Mapping[str, ComponentCommandContract],
    read_blob: Callable[[BlobRef], bytes],
    *,
    builtin_modules: frozenset[str],
) -> JavaScriptLibraryImports:
    """Validate closed direct bindings and reopen bounded sealed provider bytes.

    The caller retains current lifecycle admission. This adapter never admits a
    provider, selects a package from an ambient checkout or authorizes execution.
    """
    if (
        not isinstance(consumer, ComponentCommandContract)
        or not isinstance(providers, tuple)
        or any(not isinstance(p, ArtifactExport) for p in providers)
        or not isinstance(bindings, tuple)
        or any(not isinstance(b, LibraryConsumerBinding) for b in bindings)
    ):
        raise ValueError("JavaScript imports require typed current build inputs")
    if (
        not isinstance(builtin_modules, frozenset)
        or not builtin_modules
        or len(builtin_modules) > 1024
        or any(
            not isinstance(n, str) or not _PACKAGE.fullmatch(n) for n in builtin_modules
        )
    ):
        raise ValueError("JavaScript imports require the current pinned Node namespace")
    exports = {p.identity.uri: p for p in providers}
    if len(exports) != len(providers):
        raise ValueError("duplicate JavaScript provider artifact")
    grouped: dict[str, list[LibraryConsumerBinding]] = {}
    for b in bindings:
        if b.consumer_component_revision != consumer.component_revision:
            raise ValueError("foreign JavaScript consumer binding")
        grouped.setdefault(b.artifact_identity.uri, []).append(b)
    packages, names = [], set()
    total_bytes, total_entries = 0, 0
    for artifact_id, selected in sorted(grouped.items()):
        provider = exports.get(artifact_id)
        contract = contracts.get(selected[0].provider_component_revision.uri)
        if provider is None or not isinstance(contract, ComponentCommandContract):
            raise ValueError("JavaScript provider or contract unavailable")
        surface = contract.library_import_surface
        if (
            not contract.is_library
            or surface is None
            or surface.language != "javascript"
            or provider.role != "library"
            or provider.component_revision != contract.component_revision
            or provider.target_identity != consumer.artifact_export.target_identity
            or provider.target_identity != contract.artifact_export.target_identity
        ):
            raise ValueError("JavaScript provider contract differs")
        name = surface.package
        canonical_relative_posix_path(name, label="JavaScript package")
        if (
            not _PACKAGE.fullmatch(name)
            or name in builtin_modules
            or name.casefold() in names
        ):
            raise ValueError("unsafe or ambiguous JavaScript package name")
        names.add(name.casefold())
        mapping, capabilities = {}, set()
        for b in selected:
            if (
                b.provider_component_revision != provider.component_revision
                or b.import_surface_identity != surface.identity
                or b.target_identity != provider.target_identity
                or b.dependency_artifact_identities
                != provider.dependency_artifact_identities
                or b.capability in capabilities
            ):
                raise ValueError("JavaScript binding differs from sealed provider")
            capability = surface.capability(b.capability)
            if b.interface_identity != capability.interface_identity:
                raise ValueError("JavaScript public interface differs")
            capabilities.add(b.capability)
            module = capability.module
            canonical_relative_posix_path(module, label="JavaScript module")
            if module != name and not module.startswith(name + "/"):
                raise ValueError("JavaScript module leaves its declared package")
            # Export keys cannot contain Node patterns, URL escapes or fragments.
            if any(c in module for c in "*%#?") or "node_modules" in {
                p.casefold() for p in Path(module).parts
            }:
                raise ValueError("JavaScript module is not an exact native import")
            subpath = "." if module == name else "./" + module[len(name) + 1 :]
            mapping[subpath] = "./.litai-provider/source/" + module + ".js"
        if provider.blob.size > MAX_BUILD_ARCHIVE_BYTES - total_bytes:
            raise ValueError("JavaScript provider imports exceed byte bound")
        content = read_blob(provider.blob)
        files = read_directory_export(
            content,
            provider.blob,
            max_bytes=MAX_BUILD_ARCHIVE_BYTES - total_bytes,
            max_entries=MAX_BUILD_ARCHIVE_FILES - total_entries,
        )
        total_bytes += len(content)
        total_entries += len(files)
        paths = {f.path for f in files}
        if any(
            target.removeprefix("./.litai-provider/") not in paths
            for target in mapping.values()
        ):
            raise ValueError("JavaScript provider module is absent from sealed bytes")
        packages.append(
            JavaScriptLibraryPackage(
                name,
                provider,
                surface,
                tuple(sorted(selected, key=lambda b: b.identity.uri)),
                files,
                tuple(sorted(mapping.items())),
            )
        )
    expected = {
        p.identity.uri
        for p in providers
        if contracts.get(p.component_revision.uri) is not None
        and contracts[p.component_revision.uri].is_library
    }
    if set(grouped) != expected:
        raise ValueError("JavaScript direct library binding coverage differs")
    return JavaScriptLibraryImports(
        consumer.component_revision,
        tuple(sorted(packages, key=lambda p: p.name)),
        tuple(sorted(builtin_modules)),
    )


def materialize_javascript_library_imports(
    imports: JavaScriptLibraryImports, export: Path
) -> None:
    """Write only inside a fresh private consumer artifact; never edit providers."""
    if not isinstance(imports, JavaScriptLibraryImports):
        raise TypeError("JavaScript imports require the prepared typed plan")
    require_safe_directory(export)
    if not imports.packages:
        return
    _require_unshadowed_consumer(export, {p.name for p in imports.packages})
    root = export / "node_modules"
    if root.exists() or path_is_link_or_reparse(root):
        raise ValueError("JavaScript import destination already exists")
    root.mkdir()
    for package in imports.packages:
        canonical_relative_posix_path(package.name, label="JavaScript package")
        if not _PACKAGE.fullmatch(package.name):
            raise ValueError("unsafe JavaScript package destination")
        destination = root / package.name
        destination.mkdir()
        retained = destination / ".litai-provider"
        retained.mkdir()
        for item in package.files:
            path = retained.joinpath(
                *canonical_relative_posix_path(
                    item.path, label="JavaScript provider file"
                ).parts
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            require_safe_directory(path.parent)
            with path.open("xb") as stream:
                stream.write(item.content)
            path.chmod(item.mode)
        # The outer scope is CJS, as required by the existing generic library
        # acceptance driver. Any original provider package scopes stay intact.
        metadata = {
            "private": True,
            "type": "commonjs",
            "exports": dict(package.exports),
        }
        with (destination / "package.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(
                json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n"
            )
        _require_written_provider(retained, package.files)


def _require_written_provider(
    root: Path, files: tuple[DirectoryExportFile, ...]
) -> None:
    # Enumerate only the finite original namespace. Unexpected nodes stop before
    # recursion; file reads allocate at most the pinned original length plus one.
    expected = {item.path: item for item in files}
    directories = set()
    for name in expected:
        directories.update(str(p) for p in Path(name).parents if str(p) != ".")
    seen = set()
    pending = [root]
    while pending:
        directory = pending.pop()
        require_safe_directory(directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                name = path.relative_to(root).as_posix()
                if name in seen or path_is_link_or_reparse(path):
                    raise ValueError(
                        "materialized JavaScript provider has a foreign node"
                    )
                seen.add(name)
                if name in directories:
                    if not entry.is_dir(follow_symlinks=False):
                        raise ValueError("materialized JavaScript directory differs")
                    pending.append(path)
                    continue
                item = expected.get(name)
                if item is None or not entry.is_file(follow_symlinks=False):
                    raise ValueError(
                        "materialized JavaScript provider has a foreign file"
                    )
                fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
                with os.fdopen(fd, "rb") as stream:
                    before = os.fstat(stream.fileno())
                    if (
                        not stat.S_ISREG(before.st_mode)
                        or before.st_size != len(item.content)
                        or stat.S_IMODE(before.st_mode) != item.mode
                        or stream.read(len(item.content) + 1) != item.content
                    ):
                        raise ValueError(
                            "materialized JavaScript provider bytes differ"
                        )
                    after = os.fstat(stream.fileno())
                    if (
                        before.st_dev,
                        before.st_ino,
                        before.st_size,
                        before.st_mtime_ns,
                        before.st_ctime_ns,
                    ) != (
                        after.st_dev,
                        after.st_ino,
                        after.st_size,
                        after.st_mtime_ns,
                        after.st_ctime_ns,
                    ):
                        raise ValueError(
                            "materialized JavaScript provider changed during read"
                        )
    if seen != set(expected) | directories:
        raise ValueError("materialized JavaScript provider namespace differs")


def _require_unshadowed_consumer(root: Path, packages: set[str]) -> None:
    pending, count = [root], 0
    while pending:
        directory = pending.pop()
        require_safe_directory(directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                path = Path(entry.path)
                if count > MAX_BUILD_ARCHIVE_FILES or path_is_link_or_reparse(path):
                    raise ValueError(
                        "JavaScript consumer namespace is unsafe or oversized"
                    )
                if entry.name.casefold() == "node_modules":
                    raise ValueError(
                        "JavaScript consumer can shadow the sealed import map"
                    )
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif (
                    entry.is_file(follow_symlinks=False)
                    and entry.name.casefold() == "package.json"
                ):
                    with path.open("rb") as stream:
                        raw = stream.read(65537)
                    if len(raw) > 65536:
                        raise ValueError(
                            "JavaScript consumer package metadata is oversized"
                        )
                    metadata = json.loads(raw)
                    declared = (
                        metadata.get("name") if isinstance(metadata, dict) else None
                    )
                    if (
                        not isinstance(metadata, dict)
                        or (declared is not None and not isinstance(declared, str))
                        or isinstance(declared, str)
                        and declared.casefold() in {p.casefold() for p in packages}
                    ):
                        raise ValueError(
                            "JavaScript consumer package self-reference can shadow "
                            "a sealed import"
                        )


def require_javascript_library_source_bom(
    imports: JavaScriptLibraryImports, content: bytes
) -> None:
    """Require truthful exact generic provider declarations; no import exemption."""
    from literate_ai.application.library_artifacts import (
        javascript_library_source_component,
    )

    if not isinstance(content, bytes) or len(content) > 1048576:
        raise ValueError("JavaScript source BOM exceeds its bound")
    document = json.loads(content)
    if not isinstance(document, dict) or not isinstance(
        document.get("components"), list
    ):
        raise ValueError("JavaScript source BOM is invalid")
    root = document.get("metadata", {}).get("component", {}).get("bom-ref")
    edges = [
        d
        for d in document.get("dependencies", [])
        if isinstance(d, dict) and d.get("ref") == root
    ]
    if (
        not isinstance(root, str)
        or len(edges) != 1
        or not isinstance(edges[0].get("dependsOn"), list)
    ):
        raise ValueError("JavaScript source BOM lacks its root dependency edges")
    for package in imports.packages:
        # The complete surface is committed by the original typed binding and
        # the exact current provider contract, not recovered from model text.
        expected = javascript_library_source_component(
            package.provider.component_revision, package.surface
        )
        matches = [
            c
            for c in document["components"]
            if isinstance(c, dict)
            and (
                c.get("name") == package.name or c.get("bom-ref") == expected["bom-ref"]
            )
        ]
        if matches != [expected] or expected["bom-ref"] not in edges[0]["dependsOn"]:
            raise ValueError(
                "JavaScript source BOM differs from exact direct library authority"
            )
