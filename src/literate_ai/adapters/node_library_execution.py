"""Bounded actual CJS/ESM harness runs over separately admitted Node artifacts.

Callers own execution authorization, artifact/interface/target admission and final
lifecycle publication. This owner returns checked observations as data and keeps
the same pinned oracle, tool and complete artifact through both actual children.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    require_materialized_files,
)
from literate_ai.adapters.library_harness_results import (
    validate_library_harness_results,
)
from literate_ai.adapters.node_library_acceptance import (
    NodeLibraryAcceptance,
    capture_loaded_node_library_verifier_inputs,
)
from literate_ai.adapters.node_sdk_tools import (
    NodeSDKToolProcess,
    node_sdk_tool_environment,
    notify_node_sdk_process,
    require_node_sdk_process_observer,
)
from literate_ai.adapters.node_sdk_typescript import _inventory
from literate_ai.contracts import (
    ContentIdentity,
    LibraryImportSurface,
    canonical_identity,
)
from literate_ai.contracts.product_json import product_json_bytes, product_json_identity


@dataclass(frozen=True, slots=True)
class NodeLibraryRuntimeChecks:
    """Actual checked results, without a build/admission/publication receipt."""

    oracle: ContentIdentity
    artifact: ContentIdentity
    surface: ContentIdentity
    node: ContentIdentity
    results: tuple[tuple[str, ContentIdentity], ...]

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/node-library-runtime-checks@1",
                "oracle": self.oracle.uri,
                "artifact": self.artifact.uri,
                "surface": self.surface.uri,
                "node": self.node.uri,
                "results": [[mode, identity.uri] for mode, identity in self.results],
            }
        )


def check_node_library_runtime(
    oracle: NodeLibraryAcceptance,
    *,
    node: NodeToolchain,
    artifact: ContentIdentity,
    surface: LibraryImportSurface,
    files: tuple[DirectoryExportFile, ...],
    artifact_root: Path,
    workspace: Path,
    environment: Mapping[str, str],
    require_current: Callable[[], None],
    observe_process: Callable[[NodeSDKToolProcess], None] | None = None,
) -> NodeLibraryRuntimeChecks:
    """Run each original harness once, with bounded JSON on stdin.

    The input protocol contains schema ``node-library-harness-input@1`` (with the
    ``literate-ai/`` prefix), the private absolute ``artifact_root``, exact
    ``surface`` and runtime ``cases`` (without their expected results). Output is
    the existing library-acceptance-results@1 protocol. No caller configuration,
    package manager, source checkout or registry lookup supplies harness inputs.

    The stage is fresh and retained on failure. Its complete two-file namespace
    and the complete admitted artifact are rechecked at process boundaries.
    The separate execution owner's live guard remains active during each child.
    """
    if (
        type(oracle) is not NodeLibraryAcceptance
        or not isinstance(node, NodeToolchain)
        or not isinstance(artifact, ContentIdentity)
        or not isinstance(surface, LibraryImportSurface)
        or surface.language not in {"javascript", "typescript"}
        or oracle.language != surface.language
        or oracle.import_surface_identity != surface.identity
        or {case.capability for case in oracle.cases}
        != {capability.capability for capability in surface.capabilities}
        or not callable(require_current)
    ):
        raise ValueError("Node runtime checks require exact selected verifier data")
    require_node_sdk_process_observer(observe_process)
    files = _inventory(files, maximum=4096)
    selected_identity = ContentIdentity.parse_uri(node.identity)
    surface_identity = surface.identity
    oracle_identity = oracle.identity
    surface_content = product_json_bytes(surface.to_dict())
    if canonical_identity(json.loads(surface_content)) != surface_identity:
        raise ValueError("Node runtime surface snapshot differs from its identity")
    require_current()
    require_safe_directory(artifact_root)
    require_safe_directory(workspace.parent)
    if workspace.parent.resolve(strict=True).is_relative_to(
        artifact_root.resolve(strict=True)
    ):
        raise ValueError("Node verifier stage must be outside the immutable artifact")
    child_environment = node_sdk_tool_environment(environment)
    with capture_loaded_node_library_verifier_inputs(oracle) as require_oracle_current:
        inputs = require_oracle_current.inputs
        if inputs.identity != oracle_identity:
            raise ValueError("Node runtime oracle snapshot differs from its identity")
        request = product_json_bytes(
            {
                "schema": "literate-ai/node-library-harness-input@1",
                "artifact_root": str(artifact_root.resolve(strict=True)),
                "surface": json.loads(surface_content),
                "cases": json.loads(inputs.cases_content),
            }
        )
        if len(request) > 4 * 1024 * 1024:
            raise ValueError("Node runtime verifier input exceeds its byte bound")
        node.require_unchanged(child_environment)
        require_materialized_files(artifact_root, files)
        require_current()
        workspace.mkdir(mode=0o700)
        file_mode = 0o666 if os.name == "nt" else 0o600
        harnesses = (
            DirectoryExportFile("harness.cjs", inputs.harness_content, file_mode),
            DirectoryExportFile("harness.mjs", inputs.esm_harness_content, file_mode),
        )
        for item in harnesses:
            with (workspace / item.path).open("xb") as stream:
                stream.write(item.content)
            (workspace / item.path).chmod(item.mode)

        def closing():
            require_current()
            require_oracle_current()
            node.require_unchanged(child_environment)
            require_materialized_files(artifact_root, files)
            require_materialized_files(workspace, harnesses)
            if (
                surface.identity != surface_identity
                or oracle.identity != oracle_identity
            ):
                raise ValueError("Node runtime verifier authority changed")
            require_current()

        checks = []
        for mode, harness in zip(("commonjs", "module"), harnesses, strict=True):
            closing()
            command = (*node.command, "--no-addons", str(workspace / harness.path))
            try:
                result = run_bounded_process(
                    command,
                    cwd=workspace,
                    environment=child_environment,
                    timeout_seconds=60,
                    stdout_limit_bytes=2 * 1024 * 1024,
                    stderr_limit_bytes=1024 * 1024,
                    error_prefix="Node library independent runtime verifier",
                    input_bytes=request,
                    input_limit_bytes=4 * 1024 * 1024,
                    interrupt_guard=require_current,
                    terminate_descendants=True,
                    trace=False,
                )
                closing()
                if observe_process is not None:
                    try:
                        notify_node_sdk_process(
                            observe_process,
                            command=command,
                            result=result,
                            input_bytes=request,
                        )
                    finally:
                        closing()
                if result.returncode:
                    raise ValueError("independent Node library runtime harness failed")
                observed = validate_library_harness_results(
                    inputs, result.stdout, oracle_identity=oracle_identity
                )
                checks.append((mode, product_json_identity(observed)))
            finally:
                closing()
        closing()
        return NodeLibraryRuntimeChecks(
            oracle_identity,
            artifact,
            surface_identity,
            selected_identity,
            tuple(checks),
        )
