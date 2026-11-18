"""One object-custody composition owner for generated and retained Node SDKs.

Callers retain lifecycle admission, compiler execution and current live owners.
This module never discovers a provider, fetches a dependency, or grants execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.lifecycle.javascript_libraries import (
    JavaScriptLibraryImports,
    prepare_javascript_library_imports,
)
from literate_ai.adapters.node_sdk_tools import SDK_TOOL_ENVIRONMENT_POLICY
from literate_ai.application.library_artifacts import require_declared_commonjs_files
from literate_ai.contracts import (
    ArtifactExport,
    BlobRef,
    ComponentCommandContract,
    ContentIdentity,
    LibraryImportSurface,
    SemanticVersion,
    canonical_identity,
)
from literate_ai.contracts.executable_components.commands import LibraryConsumerBinding
from literate_ai.contracts.node_sdk import (
    MAX_NODE_SDK_PROVIDERS,
    CommonJSModuleDeclaration,
    is_node_sdk_package_name,
    node_sdk_package_boundary_files,
)
from literate_ai.contracts.paths import (
    canonical_relative_posix_path,
    canonical_relative_posix_paths,
)

MAX_SDK_FILES = 4096
MAX_SDK_BYTES = 32 * 1024 * 1024
SCHEMA = "literate-ai/node-sdk-composition-plan@1"


def _data_mode() -> int:
    return 0o666 if os.name == "nt" else 0o644


@dataclass(frozen=True, slots=True)
class NodeSDKEntrypoint:
    public: str
    module: str

    def __post_init__(self):
        if self.public != ".":
            if not self.public.startswith("./"):
                raise ValueError("SDK export must be a root or explicit subpath")
            canonical_relative_posix_path(self.public[2:], label="SDK public subpath")
        canonical_relative_posix_path(self.module, label="SDK output module")
        if any(
            part.casefold() in {"node_modules", "_providers"}
            for path in (self.public, self.module)
            for part in path.split("/")
        ):
            raise ValueError("SDK entrypoint uses a reserved dependency namespace")
        if any(token in self.public + self.module for token in ("*", "%", "#", "?")):
            raise ValueError("SDK export patterns and URL escapes are forbidden")


def _file_record(file: DirectoryExportFile) -> dict[str, object]:
    return {
        "path": file.path,
        "sha256": hashlib.sha256(file.content).hexdigest(),
        "bytes": len(file.content),
        "mode": file.mode,
    }


def _files(files: tuple[DirectoryExportFile, ...]) -> tuple[DirectoryExportFile, ...]:
    if not isinstance(files, tuple) or not 1 <= len(files) <= MAX_SDK_FILES:
        raise ValueError("SDK requires a bounded immutable file inventory")
    if any(
        not isinstance(file, DirectoryExportFile)
        or not isinstance(file.path, str)
        or len(file.path) > 512
        or not isinstance(file.content, bytes)
        or file.mode not in ((0o666, 0o777) if os.name == "nt" else (0o644, 0o755))
        for file in files
    ):
        raise ValueError("SDK inventory requires regular portable files")
    paths = canonical_relative_posix_paths(
        tuple(file.path for file in files), label="SDK file"
    )
    if any(part.casefold() == "node_modules" for path in paths for part in path.parts):
        raise ValueError("SDK inventory contains a reserved dependency namespace")
    prefixes = {}
    for path in paths:
        for depth in range(1, len(path.parts) + 1):
            prefix = "/".join(path.parts[:depth])
            alias = unicodedata.normalize("NFC", prefix.casefold())
            if prefixes.setdefault(alias, prefix) != prefix:
                raise ValueError("SDK directory paths alias on a supported filesystem")
    if sum(len(file.content) for file in files) > MAX_SDK_BYTES:
        raise ValueError("SDK inventory exceeds its byte budget")
    return tuple(sorted(files, key=lambda file: file.path))


@dataclass(frozen=True, slots=True)
class NodeSDKCompositionPlan:
    consumer: ContentIdentity
    consumer_contract: ContentIdentity
    source: ContentIdentity
    target: ContentIdentity
    compiler: ContentIdentity
    node: ContentIdentity
    packer: ContentIdentity
    bindings: tuple[LibraryConsumerBinding, ...]
    files: tuple[DirectoryExportFile, ...]
    providers: JavaScriptLibraryImports

    def __post_init__(self):
        if any(
            not isinstance(value, ContentIdentity)
            for value in (
                self.consumer,
                self.consumer_contract,
                self.source,
                self.target,
                self.compiler,
                self.node,
                self.packer,
            )
        ):
            raise TypeError("SDK plan identities must be typed")
        if (
            not isinstance(self.providers, JavaScriptLibraryImports)
            or self.providers.consumer != self.consumer
        ):
            raise ValueError("SDK plan carries a different consumer")
        if _files(self.files) != self.files:
            raise ValueError("SDK plan files must be canonical")
        if not isinstance(self.bindings, tuple) or any(
            not isinstance(binding, LibraryConsumerBinding)
            or binding.consumer_component_revision != self.consumer
            or binding.target_identity != self.target
            for binding in self.bindings
        ):
            raise ValueError("SDK plan bindings differ from its consumer/target")

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "consumer": self.consumer.to_dict(),
            "consumer_contract": self.consumer_contract.to_dict(),
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "compiler": self.compiler.to_dict(),
            "node": self.node.to_dict(),
            "packer": self.packer.to_dict(),
            "bindings": [binding.to_dict() for binding in self.bindings],
            "providers": self.providers.identity.to_dict(),
            "files": [_file_record(file) for file in self.files],
            "packer_arguments": ["pack", "--ignore-scripts", "--offline", "--json"],
            "packer_policy": "owned-config-cache-output@1",
            "provider_import_policy": "artifact-preserving-cjs-forwarders@1",
            "tool_environment_policy": SDK_TOOL_ENVIRONMENT_POLICY,
            "mode_policy": "npm-executable-0755-other-0644",
        }


def prepare_node_sdk_providers(
    consumer: ComponentCommandContract,
    *,
    providers: tuple[ArtifactExport, ...],
    generation_bindings: tuple[LibraryConsumerBinding, ...],
    build_bindings: tuple[LibraryConsumerBinding, ...],
    contracts: Mapping[str, ComponentCommandContract],
    read_blob: Callable[[BlobRef], bytes],
    builtin_modules: frozenset[str],
) -> JavaScriptLibraryImports:
    """Reopen exact provider bytes through the existing shared import owner."""
    if not isinstance(providers, tuple) or any(
        not isinstance(provider, ArtifactExport) for provider in providers
    ):
        raise TypeError("SDK providers must be typed artifact exports")
    if not all(
        isinstance(items, tuple)
        and all(isinstance(item, LibraryConsumerBinding) for item in items)
        for items in (generation_bindings, build_bindings)
    ):
        raise TypeError("SDK requires typed generation and build bindings")
    generation = tuple(sorted(generation_bindings, key=lambda item: item.identity.uri))
    bindings = tuple(sorted(build_bindings, key=lambda item: item.identity.uri))
    if generation != bindings or not bindings:
        raise ValueError("SDK generation/build provider bindings differ or are empty")
    if (
        len(providers) > MAX_NODE_SDK_PROVIDERS
        or sum(provider.blob.size for provider in providers) > MAX_SDK_BYTES
    ):
        raise ValueError("SDK providers exceed the closed profile budget")
    imports = prepare_javascript_library_imports(
        consumer,
        providers,
        bindings,
        contracts,
        read_blob,
        builtin_modules=builtin_modules,
    )
    if any(
        not package.surface.declarations
        or package.provider.dependency_artifact_identities
        for package in imports.packages
    ):
        raise ValueError(
            "SDK v1 requires direct declaration-bearing dependency-free providers"
        )
    return imports


def node_sdk_provider_module_paths(
    provider: ArtifactExport, module: CommonJSModuleDeclaration
) -> tuple[str, str]:
    """Derive consumer-owned entry paths; this grants no provider admission.

    A .cjs/.d.cts pair lets ordinary downstream TypeScript resolve the exact
    authority-declared .d.ts even when it is not adjacent to the original runtime.
    The original complete provider artifact remains byte-for-byte unchanged.
    """
    if not isinstance(provider, ArtifactExport) or not isinstance(
        module, CommonJSModuleDeclaration
    ):
        raise TypeError("SDK provider paths require typed artifact/module metadata")
    stem = (
        "_providers/"
        + provider.component_revision.digest
        + "/imports/"
        + hashlib.sha256(module.module.encode("utf-8")).hexdigest()
    )
    return stem + ".cjs", stem + ".d.cts"


def node_sdk_provider_package_files(
    provider: ArtifactExport,
    surface: LibraryImportSurface,
    provider_files: tuple[DirectoryExportFile, ...],
) -> tuple[DirectoryExportFile, ...]:
    """One byte-preserving package projection for already admitted inputs.

    SDK consumers and independent declaration verifiers share this owner. The
    caller retains artifact readback, current interface/target and execution
    authority; projecting data never admits a consumer or creates acceptance.
    """
    if (
        not isinstance(provider, ArtifactExport)
        or not isinstance(surface, LibraryImportSurface)
        or not surface.declarations
        or provider.role != "library"
        or provider.dependency_artifact_identities
    ):
        raise ValueError(
            "SDK v1 requires a direct declaration-bearing CommonJS library"
        )
    provider_files = _files(provider_files)
    require_declared_commonjs_files(
        surface, {file.path: file.content for file in provider_files}
    )
    files: dict[str, DirectoryExportFile] = {}
    prefix = "_providers/" + provider.component_revision.digest
    files[prefix + "/package.json"] = DirectoryExportFile(
        prefix + "/package.json",
        b'{"type":"commonjs","private":true}\n',
        _data_mode(),
    )
    for file in provider_files:
        if any(part.casefold() == "node_modules" for part in file.path.split("/")):
            raise ValueError("SDK provider contains a nested dependency namespace")
        if file.path.rsplit("/", 1)[-1] == "package.json":
            metadata = json.loads(file.content)
            if not isinstance(metadata, dict) or any(
                metadata.get(key)
                for key in (
                    "dependencies",
                    "optionalDependencies",
                    "peerDependencies",
                    "bundledDependencies",
                    "bundleDependencies",
                )
            ):
                raise ValueError("SDK provider format or dependency authority differs")
        path = prefix + "/artifact/" + file.path
        if path in files:
            raise ValueError("SDK provider namespace collision")
        files[path] = DirectoryExportFile(path, file.content, file.mode)
    names = {file.path for file in provider_files}
    folded_names = {name.casefold() for name in names}
    for module in surface.declarations:
        if module.runtime not in names or module.declaration not in names:
            raise ValueError("SDK provider entry files are absent from its artifact")
        # A .js type reference resolves .ts/.tsx before .d.ts in native
        # TypeScript. Deny those shadows rather than compile another file.
        stem = module.declaration[:-5]
        if any(
            (stem + suffix).casefold() in folded_names for suffix in (".ts", ".tsx")
        ):
            raise ValueError(
                "SDK provider declared types are shadowed by TypeScript source"
            )
        runtime, declaration = node_sdk_provider_module_paths(provider, module)
        # The runtime forwards the identical CommonJS value; declarations
        # re-export its exact declared type namespace. No provider is edited.
        runtime_source = (
            '"use strict";\nmodule.exports=require('
            + json.dumps("../artifact/" + module.runtime)
            + ");\n"
        )
        type_source = (
            "import provider = require("
            + json.dumps("../artifact/" + module.declaration[:-5] + ".js")
            + ");\nexport = provider;\n"
        )
        for path, content in (
            (runtime, runtime_source),
            (declaration, type_source),
        ):
            if path in files:
                raise ValueError("SDK provider forwarding namespace collision")
            files[path] = DirectoryExportFile(
                path, content.encode("utf-8"), _data_mode()
            )
    return _files(tuple(files.values()))


def node_sdk_provider_files(
    imports: JavaScriptLibraryImports,
) -> tuple[DirectoryExportFile, ...]:
    """Use the identical private provider layout for compilation and packing."""
    if not isinstance(imports, JavaScriptLibraryImports):
        raise ValueError("SDK providers require typed resolved imports")
    files = {}
    for package in imports.packages:
        for file in node_sdk_provider_package_files(
            package.provider, package.surface, package.files
        ):
            if file.path in files:
                raise ValueError("SDK provider namespace collision")
            files[file.path] = file
    return _files(tuple(files.values()))


def require_node_sdk_output_authority(
    consumer: ComponentCommandContract,
    name: str,
    entrypoints: tuple[NodeSDKEntrypoint, ...],
) -> None:
    """Bind generated exports; retained callers retain their separate admission."""
    if not isinstance(consumer, ComponentCommandContract):
        raise TypeError("SDK composition requires its exact consumer contract")
    surface = consumer.library_import_surface
    if surface is None:
        return
    if not surface.node_sdk_exports:
        raise ValueError(
            "generated SDK libraries require the explicit dual export surface"
        )
    expected = tuple(
        NodeSDKEntrypoint(
            "."
            if item.module == surface.package
            else "./" + item.module[len(surface.package) + 1 :],
            item.stem,
        )
        for item in surface.node_sdk_exports
    )
    if name != surface.package or entrypoints != expected:
        raise ValueError(
            "SDK package or exports differ from its current library authority"
        )


def prepare_node_sdk_composition(
    consumer: ComponentCommandContract,
    *,
    source: ContentIdentity,
    compiler: ContentIdentity,
    node: ContentIdentity,
    packer: ContentIdentity,
    name: str,
    version: str,
    entrypoints: tuple[NodeSDKEntrypoint, ...],
    compiled: tuple[DirectoryExportFile, ...],
    licenses: tuple[DirectoryExportFile, ...],
    providers: tuple[ArtifactExport, ...],
    generation_bindings: tuple[LibraryConsumerBinding, ...],
    build_bindings: tuple[LibraryConsumerBinding, ...],
    contracts: Mapping[str, ComponentCommandContract],
    read_blob: Callable[[BlobRef], bytes],
    builtin_modules: frozenset[str],
) -> NodeSDKCompositionPlan:
    """Bind current compiler output and exact direct providers without a resolver.

    Compiler inputs/results and independent provider acceptance must be admitted
    by the calling generated/retained lifecycle before invoking this owner.
    """
    require_node_sdk_output_authority(consumer, name, entrypoints)
    if any(
        not isinstance(value, ContentIdentity)
        for value in (source, compiler, node, packer)
    ):
        raise TypeError("Node SDK composition requires exact source/tool identities")
    if (
        not is_node_sdk_package_name(name)
        or not isinstance(version, str)
        or len(version) > 128
    ):
        raise ValueError("SDK name/version must be bounded native package metadata")
    if str(SemanticVersion.parse(version)) != version:
        raise ValueError("SDK version must use canonical SemVer")
    if (
        not isinstance(entrypoints, tuple)
        or not 1 <= len(entrypoints) <= 128
        or any(not isinstance(item, NodeSDKEntrypoint) for item in entrypoints)
    ):
        raise ValueError("SDK requires explicit bounded public entrypoints")
    public = tuple(item.public for item in entrypoints)
    if (
        public != tuple(sorted(set(public)))
        or "." not in public
        or len({value.casefold() for value in public}) != len(public)
    ):
        raise ValueError("SDK public exports require a canonical root and subpaths")
    imports = prepare_node_sdk_providers(
        consumer,
        providers=providers,
        generation_bindings=generation_bindings,
        build_bindings=build_bindings,
        contracts=contracts,
        read_blob=read_blob,
        builtin_modules=builtin_modules,
    )
    bindings = tuple(sorted(build_bindings, key=lambda item: item.identity.uri))
    if (
        name.casefold() in {package.name.casefold() for package in imports.packages}
        or name in builtin_modules
    ):
        raise ValueError("SDK name collides with a provider or Node builtin")
    outputs = _files(compiled)
    legal = _files(licenses)
    if any(
        not (
            file.path.startswith(("cjs/", "esm/"))
            and file.path.endswith((".js", ".d.ts"))
        )
        for file in outputs
    ):
        raise ValueError(
            "SDK compiler outputs must be JavaScript or declarations in format roots"
        )
    if any(
        "/" in file.path or not file.path.startswith(("LICENSE", "NOTICE"))
        for file in legal
    ):
        raise ValueError("SDK licenses must be explicit root license/notice files")
    files = {file.path: file for file in (*outputs, *legal)}
    if len(files) != len(outputs) + len(legal):
        raise ValueError("SDK compiler/license namespace collision")
    modules = {
        (
            file.path.split("/", 1)[1][:-5]
            if file.path.endswith(".d.ts")
            else file.path.split("/", 1)[1][:-3]
        )
        for file in outputs
    }
    if any(
        directory + "/" + module + suffix not in files
        for module in modules
        for directory in ("cjs", "esm")
        for suffix in (".js", ".d.ts")
    ):
        raise ValueError("SDK compilation must close both runtime/declaration formats")
    exports = {}
    for entry in entrypoints:
        conditions = {}
        for condition, directory in (("require", "cjs"), ("import", "esm")):
            runtime, declaration = (
                directory + "/" + entry.module + ".js",
                directory + "/" + entry.module + ".d.ts",
            )
            if runtime not in files or declaration not in files:
                raise ValueError("SDK public runtime/declarations are missing")
            conditions[condition] = {
                "types": "./" + declaration,
                "default": "./" + runtime,
            }
        exports[entry.public] = conditions
    for path, content in node_sdk_package_boundary_files():
        files[path] = DirectoryExportFile(path, content, _data_mode())
    for file in node_sdk_provider_files(imports):
        if file.path in files:
            raise ValueError("SDK provider namespace collision")
        files[file.path] = file
    package = {
        "name": name,
        "version": version,
        "private": False,
        "type": "commonjs",
        "exports": exports,
        "files": ["cjs", "esm", "_providers", *(file.path for file in legal)],
    }
    files["package.json"] = DirectoryExportFile(
        "package.json",
        (json.dumps(package, separators=(",", ":")) + "\n").encode(),
        _data_mode(),
    )
    return NodeSDKCompositionPlan(
        consumer.component_revision,
        consumer.identity,
        source,
        consumer.artifact_export.target_identity,
        compiler,
        node,
        packer,
        bindings,
        _files(tuple(files.values())),
        imports,
    )


def materialize_node_sdk(
    plan: NodeSDKCompositionPlan,
    destination: Path,
    *,
    require_current: Callable[[], None],
) -> None:
    """Create one fresh object projection; failed/uncertain projections are retained."""
    if not isinstance(plan, NodeSDKCompositionPlan):
        raise TypeError("SDK materialization requires its prepared composition plan")
    require_current()
    require_safe_directory(destination.parent)
    destination.mkdir()
    for file in plan.files:
        require_current()
        path = destination.joinpath(
            *canonical_relative_posix_path(file.path, label="SDK file").parts
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        require_safe_directory(path.parent)
        with path.open("xb") as stream:
            stream.write(file.content)
        path.chmod(file.mode)
    require_node_sdk_projection(plan, destination, require_current=require_current)


def require_node_sdk_projection(
    plan: NodeSDKCompositionPlan, root: Path, *, require_current: Callable[[], None]
) -> None:
    """Readback and cache reuse admit only the complete exact planned inventory."""
    from literate_ai.adapters.directory_artifacts import require_materialized_files

    require_current()
    require_materialized_files(root, plan.files)
    require_current()
