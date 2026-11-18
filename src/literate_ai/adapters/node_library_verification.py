"""One original-oracle runtime/type owner for admitted Node library projections.

Generated and retained lifecycles retain their distinct real subject admission,
execution grants and final receipt publication. This layer joins actual bounded
checks without manufacturing Component identities or issuing acceptance authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_library_acceptance import (
    NodeLibraryAcceptance,
    capture_loaded_node_library_verifier_inputs,
)
from literate_ai.adapters.node_library_execution import (
    NodeLibraryRuntimeChecks,
    _runtime_namespace,
    check_node_library_runtime,
)
from literate_ai.adapters.node_library_projection import (
    project_commonjs_library_declarations,
    project_node_sdk_declarations,
)
from literate_ai.adapters.node_sdk_declarations import (
    NodeDeclarationChecks,
    check_node_declarations,
)
from literate_ai.adapters.node_sdk_tools import (
    NodeSDKToolProcess,
    require_node_sdk_process_observer,
)
from literate_ai.adapters.node_sdk_typescript import NodeSDKTypeScriptCompiler
from literate_ai.contracts import (
    ArtifactExport,
    ContentIdentity,
    LibraryImportSurface,
    canonical_identity,
)


@dataclass(frozen=True, slots=True)
class NodeLibraryChecks:
    """Joined current observations, not a lifecycle or admission receipt."""

    subject: ContentIdentity
    artifact: ContentIdentity
    surface: ContentIdentity
    oracle: ContentIdentity
    declarations: NodeDeclarationChecks
    runtime: NodeLibraryRuntimeChecks

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/node-library-checks@1",
                "subject": self.subject.uri,
                "artifact": self.artifact.uri,
                "surface": self.surface.uri,
                "oracle": self.oracle.uri,
                "declarations": self.declarations.identity.uri,
                "runtime": self.runtime.identity.uri,
            }
        )


def check_node_library(
    oracle: NodeLibraryAcceptance,
    *,
    subject: ContentIdentity,
    artifact: ContentIdentity,
    surface: LibraryImportSurface,
    files: tuple[DirectoryExportFile, ...],
    artifact_root: Path,
    workspace: Path,
    node: NodeToolchain,
    compiler: NodeSDKTypeScriptCompiler,
    environment: Mapping[str, str],
    require_current: Callable[[], None],
    observe_process: Callable[[NodeSDKToolProcess], None] | None = None,
    provider: ArtifactExport | None = None,
) -> NodeLibraryChecks:
    """Check original independent cases before running both runtime harnesses.

    Generated callers supply their real locked subject; retained callers supply
    their separately admitted product subject. CommonJS provider views additionally
    require the exact real provider export. No package discovery or binding
    resolution occurs here. A caller must keep custody through final publication.
    """
    require_node_sdk_process_observer(observe_process)
    if (
        type(oracle) is not NodeLibraryAcceptance
        or not isinstance(node, NodeToolchain)
        or not isinstance(compiler, NodeSDKTypeScriptCompiler)
        or compiler.node.identity != node.identity
        or not isinstance(surface, LibraryImportSurface)
        or oracle.language != surface.language
        or oracle.import_surface_identity != surface.identity
        or not callable(require_current)
    ):
        raise ValueError("Node library checks require exact joined verifier tools/data")
    sdk_namespace = bool(surface.node_sdk_exports)
    if sdk_namespace:
        if provider is not None:
            raise ValueError("a dual SDK cannot impersonate a CommonJS provider")
        projection = project_node_sdk_declarations(
            subject=subject, artifact=artifact, surface=surface, files=files
        )
    elif (
        isinstance(provider, ArtifactExport)
        and subject == provider.component_revision
        and artifact == provider.identity
    ):
        projection = project_commonjs_library_declarations(provider, surface, files)
    else:
        raise ValueError("CommonJS checks require the exact real provider artifact")
    # Freeze the shared projection before callbacks or compiler children. A
    # host without strong namespace custody refuses this profile immediately.
    runtime_namespace, _namespace_identity = _runtime_namespace(
        projection.files if sdk_namespace else ()
    )
    with (
        ExitStack() as namespace_lifetime,
        capture_loaded_node_library_verifier_inputs(oracle) as scope,
    ):
        inputs = scope.inputs

        def observed(process):
            scope()
            require_current()
            if observe_process is None:
                # No callback/effect/read occurs here. Preserve both original
                # oracle closures without repeating the adjacent full guard.
                scope()
                return None
            try:
                return observe_process(process)
            finally:
                require_current()
                scope()

        require_current()
        declarations = check_node_declarations(
            projection,
            inputs.declaration_cases,
            compiler=compiler,
            environment=environment,
            require_current=require_current,
            observe_process=observed,
        )
        scope()
        require_current()
        runtime = check_node_library_runtime(
            oracle,
            node=node,
            artifact=artifact,
            surface=surface,
            files=files,
            artifact_root=artifact_root,
            workspace=workspace,
            environment=environment,
            require_current=require_current,
            observe_process=observed,
            namespace_files=runtime_namespace,
            _namespace_lifetime=namespace_lifetime,
        )
        scope()
        require_current()
        return NodeLibraryChecks(
            subject,
            artifact,
            projection.surface,
            inputs.identity,
            declarations,
            runtime,
        )
