"""Bounded actual CJS/ESM harness runs over separately admitted Node artifacts.

Callers own execution authorization, artifact/interface/target admission and final
lifecycle publication. This owner returns checked observations as data and keeps
the same pinned oracle, tool and complete artifact through both actual children.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    capture_materialized_files,
    require_materialized_files,
    snapshot_directory_file,
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
from literate_ai.adapters.process_liveness import process_liveness
from literate_ai.contracts import (
    ContentIdentity,
    LibraryImportSurface,
    canonical_identity,
)
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.contracts.product_json import product_json_bytes, product_json_identity


def _runtime_namespace(files):
    """Snapshot bounded caller DATA; projection and admission stay with its owner."""
    if type(files) is not tuple or len(files) > 4094:
        raise ValueError("runtime namespace file count exceeds its bound")
    if not files:
        return (), None
    if os.name != "posix":
        raise ValueError("runtime namespace requires POSIX live file custody")
    snapshots = []
    for item in files:
        item = snapshot_directory_file(item)
        if not item.path.startswith("node_modules/"):
            raise ValueError("runtime namespace requires bounded package file DATA")
        snapshots.append(item)
    snapshots = _inventory(tuple(snapshots), maximum=4094)
    canonical_relative_posix_paths(
        ("harness.cjs", "harness.mjs", *(item.path for item in snapshots)),
        label="runtime namespace",
    )
    identity = canonical_identity(
        {
            "schema": "literate-ai/node-library-runtime-namespace@1",
            "custody": "original-posix-stamps@1",
            "files": [
                {
                    "path": item.path,
                    "sha256": hashlib.sha256(item.content).hexdigest(),
                    "size": len(item.content),
                    "mode": item.mode,
                }
                for item in snapshots
            ],
        }
    )
    return snapshots, identity


@dataclass(frozen=True, slots=True)
class NodeLibraryRuntimeChecks:
    """Actual checked results, without a build/admission/publication receipt."""

    oracle: ContentIdentity
    artifact: ContentIdentity
    surface: ContentIdentity
    node: ContentIdentity
    results: tuple[tuple[str, ContentIdentity], ...]
    namespace: ContentIdentity | None = None

    @property
    def identity(self):
        document = {
            "schema": "literate-ai/node-library-runtime-checks@1",
            "oracle": self.oracle.uri,
            "artifact": self.artifact.uri,
            "surface": self.surface.uri,
            "node": self.node.uri,
            "results": [[mode, identity.uri] for mode, identity in self.results],
        }
        if self.namespace is not None:
            document["namespace"] = self.namespace.uri
        return canonical_identity(document)


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
    namespace_files: tuple[DirectoryExportFile, ...] = (),
    _namespace_lifetime: ExitStack | None = None,
) -> NodeLibraryRuntimeChecks:
    """Run each original harness once, with bounded JSON on stdin.

    The input protocol contains schema ``node-library-harness-input@1`` (with the
    ``literate-ai/`` prefix), the private absolute ``artifact_root``, exact
    ``surface`` and runtime ``cases`` (without their expected results). Output is
    the existing library-acceptance-results@1 protocol. No caller configuration,
    package manager, source checkout or registry lookup supplies harness inputs.

    The stage is fresh and retained on failure. Legacy callers retain its
    two-file harness namespace. An explicit package projection adds bounded
    immutable namespace DATA, not discovery or execution permission. Its original
    complete copy is fenced through children, observers and final oracle close.
    The admitted artifact and caller's execution ownership remain independently
    current; unsupported strong namespace custody refuses before creating files.
    """
    namespace_files, namespace_identity = _runtime_namespace(namespace_files)
    if _namespace_lifetime is not None and type(_namespace_lifetime) is not ExitStack:
        raise TypeError("runtime namespace lifetime requires an owned exit stack")
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
    namespace_guard = None

    @contextmanager
    def close_namespace():
        try:
            yield
        finally:
            if namespace_guard is not None:
                # Oracle exit may block or invoke an owner callback. Close the
                # same initial namespace after it without adopting new stamps.
                try:
                    require_current()
                finally:
                    namespace_guard()

    with (
        close_namespace(),
        capture_loaded_node_library_verifier_inputs(oracle) as require_oracle_current,
    ):
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
        file_mode = 0o666 if os.name == "nt" else 0o600
        harnesses = (
            DirectoryExportFile("harness.cjs", inputs.harness_content, file_mode),
            DirectoryExportFile("harness.mjs", inputs.esm_harness_content, file_mode),
        )
        stage_files = (*harnesses, *namespace_files)
        if (
            len(stage_files) > 4096
            or sum(len(item.content) for item in stage_files) > 34 * 1024 * 1024
        ):
            raise ValueError("runtime stage exceeds its aggregate bound")
        workspace.mkdir(mode=0o700)
        # This bounded immutable batch has no owner/provider/observer callbacks.
        # Capture the original stamps before any callback can replace a file.
        for item in stage_files:
            target = workspace / item.path
            target.parent.mkdir(parents=True, exist_ok=True)
            require_safe_directory(target.parent)
            with target.open("xb") as stream:
                stream.write(item.content)
            target.chmod(item.mode)
        if namespace_files:
            namespace_guard = capture_materialized_files(workspace, stage_files)
            if _namespace_lifetime is not None:
                # Add a second close after a combined verifier's outer oracle
                # exit; never defer or replace the standalone close above.
                _namespace_lifetime.enter_context(close_namespace())

        def closing():
            require_current()
            if namespace_guard is not None:
                namespace_guard()
            require_oracle_current()
            node.require_unchanged(child_environment)
            require_materialized_files(artifact_root, files)
            require_materialized_files(workspace, stage_files)
            if (
                surface.identity != surface_identity
                or oracle.identity != oracle_identity
            ):
                raise ValueError("Node runtime verifier authority changed")
            require_current()
            if namespace_guard is not None:
                namespace_guard()

        namespace_scope = (
            process_liveness(namespace_guard)
            if namespace_guard is not None
            else nullcontext()
        )
        with namespace_scope:
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
                        raise ValueError(
                            "independent Node library runtime harness failed"
                        )
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
            namespace_identity,
        )
