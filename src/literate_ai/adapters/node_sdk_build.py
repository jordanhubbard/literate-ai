"""One compile-to-plan path for already admitted generated and retained SDK inputs."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_composition import (
    MAX_SDK_FILES,
    NodeSDKCompositionPlan,
    NodeSDKEntrypoint,
    node_sdk_provider_files,
    prepare_node_sdk_composition,
    prepare_node_sdk_providers,
    require_node_sdk_output_authority,
)
from literate_ai.adapters.node_sdk_tools import (
    NodeSDKToolProcess,
    require_node_sdk_process_observer,
)
from literate_ai.adapters.node_sdk_typescript import (
    NodeSDKTypeScriptCompiler,
    _inventory,
)
from literate_ai.contracts import (
    ArtifactExport,
    BlobRef,
    ComponentCommandContract,
    ContentIdentity,
    canonical_identity,
)
from literate_ai.contracts.executable_components.commands import LibraryConsumerBinding


@dataclass(frozen=True, slots=True)
class CompiledNodeSDKPlan:
    plan: NodeSDKCompositionPlan
    compiler_inputs: tuple[str, ...]


def compile_node_sdk_plan(
    consumer: ComponentCommandContract,
    *,
    source_authority: ContentIdentity,
    source_files: tuple[DirectoryExportFile, ...],
    compiler: NodeSDKTypeScriptCompiler,
    packer: ContentIdentity,
    name: str,
    version: str,
    entrypoints: tuple[NodeSDKEntrypoint, ...],
    licenses: tuple[DirectoryExportFile, ...],
    providers: tuple[ArtifactExport, ...],
    generation_bindings: tuple[LibraryConsumerBinding, ...],
    build_bindings: tuple[LibraryConsumerBinding, ...],
    contracts: Mapping[str, ComponentCommandContract],
    read_blob: Callable[[BlobRef], bytes],
    builtin_modules: frozenset[str],
    environment: Mapping[str, str],
    require_current: Callable[[], None],
    observe_process: Callable[[NodeSDKToolProcess], None] | None = None,
    command_paths: tuple[str, str, str] | None = None,
) -> CompiledNodeSDKPlan:
    """Compile once and bind the resulting plan to the actual compiler/input bytes.

    Calling adapters retain source and tool execution authority, current provider
    declaration acceptance and lifecycle publication. This internal owner neither
    admits a provider nor qualifies the generated SDK. It does not materialize
    providers into authored source, infer a registry closure, or publish a package.
    """
    require_node_sdk_process_observer(observe_process)
    if (
        not isinstance(source_authority, ContentIdentity)
        or not isinstance(packer, ContentIdentity)
        or not isinstance(compiler, NodeSDKTypeScriptCompiler)
        or not callable(require_current)
    ):
        raise TypeError("SDK compilation requires exact source/tools and current owner")
    source_files = _inventory(source_files, maximum=MAX_SDK_FILES)
    licenses = _inventory(licenses, maximum=MAX_SDK_FILES)
    source_authority = ContentIdentity.parse_uri(source_authority.uri)
    packer = ContentIdentity.parse_uri(packer.uri)
    if (
        not isinstance(source_files, tuple)
        or not 1 <= len(source_files) <= MAX_SDK_FILES
        or any(
            not isinstance(item, DirectoryExportFile)
            or not isinstance(item.path, str)
            or not item.path.startswith("src/")
            or not item.path.endswith(".ts")
            or not isinstance(item.content, bytes)
            for item in source_files
        )
    ):
        raise ValueError("SDK compiler source must be a bounded src/*.ts inventory")
    if (
        not isinstance(entrypoints, tuple)
        or not 1 <= len(entrypoints) <= 128
        or any(not isinstance(item, NodeSDKEntrypoint) for item in entrypoints)
    ):
        raise ValueError("SDK compilation requires explicit public entrypoints")
    entrypoints = tuple(
        NodeSDKEntrypoint(row.public, row.module) for row in entrypoints
    )
    public = tuple(item.public for item in entrypoints)
    if public != tuple(sorted(set(public))) or "." not in public:
        raise ValueError("SDK compilation requires a canonical root and subpaths")
    require_node_sdk_output_authority(consumer, name, entrypoints)
    roots = tuple(sorted({"src/" + item.module + ".ts" for item in entrypoints}))
    require_current()
    imports = prepare_node_sdk_providers(
        consumer,
        providers=providers,
        generation_bindings=generation_bindings,
        build_bindings=build_bindings,
        contracts=contracts,
        read_blob=read_blob,
        builtin_modules=builtin_modules,
    )
    provider_files = node_sdk_provider_files(imports)
    require_current()
    result = compiler.run(
        operation="compile",
        files=(*source_files, *provider_files),
        roots=roots,
        environment=environment,
        require_current=require_current,
        observe_process=observe_process,
        command_paths=command_paths,
    )
    if not result.success:
        raise ValueError(
            "SDK TypeScript compilation failed: " + repr(result.diagnostics)
        )
    source = canonical_identity(
        {
            "schema": "literate-ai/node-sdk-compiler-source@1",
            "authority": source_authority.to_dict(),
            "roots": list(roots),
            "files": [
                {
                    "path": item.path,
                    "size": len(item.content),
                    "sha256": hashlib.sha256(item.content).hexdigest(),
                }
                for item in sorted(source_files, key=lambda item: item.path)
            ],
        }
    )
    require_current()
    # Reopen sealed inputs through the same resolver at this publication cut;
    # the compiler's earlier in-memory snapshot is not continuing authority.
    plan = prepare_node_sdk_composition(
        consumer,
        source=source,
        compiler=compiler.identity,
        node=ContentIdentity.parse_uri(compiler.node.identity),
        packer=packer,
        name=name,
        version=version,
        entrypoints=entrypoints,
        compiled=result.outputs,
        licenses=licenses,
        providers=providers,
        generation_bindings=generation_bindings,
        build_bindings=build_bindings,
        contracts=contracts,
        read_blob=read_blob,
        builtin_modules=builtin_modules,
    )
    if (
        plan.providers.identity != imports.identity
        or node_sdk_provider_files(plan.providers) != provider_files
    ):
        raise ValueError(
            "SDK providers changed between compilation and plan publication"
        )
    require_current()
    return CompiledNodeSDKPlan(plan, result.inputs)
