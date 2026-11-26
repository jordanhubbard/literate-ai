"""Run reviewed Cargo commands within original v2 materialization/input custody.

These are command observations, never test coverage or receiving admission.
The subsequent protocol owner must execute the complete reviewed inventory,
including custom/ignored/excluded targets, before any admission receipt exists.
Explicit offline flags are not OS network containment for arbitrary gate tools.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Mapping
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.builders import run_bounded_process
from literate_ai.adapters.cargo_workspace_patches_v2 import (
    verify_cargo_workspace_patches_v2,
)
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.retained_cargo_configuration_v2 import (
    capture_retained_cargo_configuration_v2,
)
from literate_ai.adapters.retained_cargo_current import _unique_object
from literate_ai.adapters.retained_cargo_execution import (
    RetainedCargoCommandObservation,
    RetainedCargoExecutionError,
)
from literate_ai.adapters.retained_cargo_input_scope_v2 import RetainedCargoInputScopeV2
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    RetainedCargoScratchMaterializationV2,
)
from literate_ai.adapters.retained_cargo_metadata_inputs_v2 import (
    verify_retained_cargo_metadata_inputs_v2,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.projects import PinnedInputClosure


def execute_retained_cargo_commands_v2(
    materialized,
    *,
    cargo,
    rustc,
    gate_tools,
    environment,
    consumer_inputs,
    allow_host_execution,
    offline=True,
    timeout_seconds=10800,
    max_output_bytes=4 * 1024**2,
    max_total_output_bytes=64 * 1024**2,
    maximum_document_bytes=16 * 1024**2,
    registry_sources=None,
):
    """Bracket exact reviewed gates with actual metadata, graph and source checks.

    Existing scratch roots must still belong to the same original materializer.
    No directory is adopted, dependency installed, manifest edited or receipt
    minted. Configuration-selected includes/tools/external inputs still require
    independent receiving review; this API does not interpret their semantics.
    """
    if allow_host_execution is not True:
        raise ValueError("retained.execution.authorization-required")
    if (
        type(materialized) is not RetainedCargoScratchMaterializationV2
        or type(consumer_inputs) is not RetainedCargoInputScopeV2
        or type(offline) is not bool
    ):
        raise TypeError("retained.execution.v2-current-inputs-required")
    if (
        type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 10800
        or any(
            type(n) is not int or not 2 <= n <= 256 * 1024**2
            for n in (max_output_bytes, max_total_output_bytes)
        )
        or type(maximum_document_bytes) is not int
        or not 0 < maximum_document_bytes <= 256 * 1024**2
    ):
        raise ValueError("retained.execution.v2-limits-invalid")
    deadline = time.monotonic() + timeout_seconds
    materialized.require_unchanged()
    plan = materialized.plan
    common = plan.common
    reviewed = materialized._files.reviewed
    if not isinstance(environment, Mapping):
        raise ValueError("retained.execution.environment-invalid")
    consumer_inputs.require_unchanged(environment=environment)
    base = dict(environment)
    configuration = capture_retained_cargo_configuration_v2(
        materialized, consumer_inputs, environment=environment
    )

    def measured(tool):
        if (
            type(tool) is not LocalComponentToolBinding
            or tool.authority_identity is None
            or not callable(tool._authority_guard)
        ):
            raise ValueError("retained.execution.measured-tool-custody-required")
        tool.require_unchanged()

    measured(cargo)
    measured(rustc)
    if (
        cargo.toolchain_identity != common.cargo_identity
        or rustc.toolchain_identity != common.rustc_identity
        or rustc.arguments
    ):
        raise ValueError("retained.execution.native-tool-mismatch")
    if not isinstance(gate_tools, Mapping) or len(gate_tools) > 128:
        raise ValueError("retained.execution.gate-tools-incomplete")
    tools = dict(gate_tools)
    if set(tools) != {command.argv[0] for command in common.gates}:
        raise ValueError("retained.execution.gate-tools-incomplete")
    for tool in tools.values():
        measured(tool)
        if tool.toolchain_identity not in reviewed.policy.toolchains:
            raise ValueError("retained.execution.gate-tool-unreviewed")
    if offline and any(command.network for command in common.gates):
        raise ValueError("retained.execution.network-gate-refused")
    sources = {} if registry_sources is None else registry_sources
    if (
        not isinstance(sources, Mapping)
        or len(sources) > 128
        or any(
            type(k) is not str
            or type(v) is not str
            or not 0 < len(k) <= 4096
            or not 0 < len(v) <= 4096
            for k, v in sources.items()
        )
    ):
        raise ValueError("retained.execution.registry-inputs-invalid")
    source_identity = canonical_identity(dict(sources))
    root = reviewed.project.root
    workspace = root / common.workspace_root
    output = workspace / common.graph.output_directory
    if (
        sum(
            row.kind == "cargo-output" and workspace / row.path == output
            for row in plan.scratch_roots
        )
        != 1
    ):
        raise ValueError("retained.execution.v2-owned-output-required")
    manifest_inputs = PinnedInputClosure(
        maximum_files=2,
        maximum_file_bytes=maximum_document_bytes,
        maximum_total_bytes=2 * maximum_document_bytes,
    )
    references = {item.path: item.after for item in common.manifests}
    documents = {}
    for name in ("Cargo.toml", "Cargo.lock"):
        reference = references.get(name)
        if reference is None or not 0 < reference.size <= maximum_document_bytes:
            raise ValueError("retained.execution.v2-manifest-required")
        content = manifest_inputs.pin(
            workspace / name,
            boundary=workspace,
            label=name,
            expected_identity=reference.identity,
        )
        if len(content) != reference.size:
            raise ValueError("retained.execution.v2-manifest-size-mismatch")
        documents[name] = content
    observations = []
    remaining_output = max_total_output_bytes

    def guard():
        configuration.require_unchanged(environment=environment)
        if dict(environment) != base:
            raise ValueError("retained.execution.input-environment-mismatch")
        if canonical_identity(dict(sources)) != source_identity:
            raise ValueError("retained.execution.registry-inputs-changed")
        manifest_inputs.require_unchanged()
        for tool in (cargo, rustc, *tools.values()):
            tool.require_unchanged()
        require_safe_directory(output)

    def reserved(values, cwd):
        roots = dict(consumer_inputs.roots)
        if values.get("CARGO_HOME") != str(roots["cargo-home"]):
            raise ValueError("retained.execution.cargo-home-override-refused")
        for variable in reviewed.policy.external_input_variables:
            if values.get(variable) != str(roots["external:" + variable]):
                raise ValueError("retained.execution.external-input-override-refused")
        configured = values.get("CARGO_TARGET_DIR")
        if configured is not None:
            selected = Path(configured)
            if not selected.is_absolute():
                selected = cwd / selected
            if selected != output:
                raise ValueError("retained.execution.output-override-refused")
        if values.get("RUSTC", rustc.executable) != rustc.executable:
            raise ValueError("retained.execution.compiler-override-refused")

    reserved(base, workspace)

    def run(command, tool):
        nonlocal remaining_output
        guard()
        cwd = root / command.working_directory
        require_safe_directory(cwd)
        values = {
            **base,
            **dict(tool.environment),
            **{entry.name: entry.value for entry in command.environment},
        }
        reserved(values, cwd)
        values.update(CARGO_TARGET_DIR=str(output), RUSTC=rustc.executable)
        limit = min(max_output_bytes, remaining_output // 2)
        if limit < 1:
            raise ValueError("retained.execution.total-output-exhausted")
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise ValueError("retained.execution.v2-deadline-exceeded")
        argv = (*tool.command, *command.argv[1:])
        try:
            result = run_bounded_process(
                argv,
                cwd=cwd,
                environment=values,
                timeout_seconds=seconds,
                stdout_limit_bytes=limit,
                stderr_limit_bytes=limit,
                error_prefix="retained.execution.v2",
                terminate_descendants=True,
            )
            observations.append(
                RetainedCargoCommandObservation(
                    command,
                    argv,
                    canonical_identity(values),
                    result,
                    tool.authority_identity,
                )
            )
            remaining_output -= len(result.stdout) + len(result.stderr)
        finally:
            guard()
        if result.returncode != 0:
            raise ValueError("retained.execution.command-failed")
        if time.monotonic() >= deadline:
            raise ValueError("retained.execution.v2-deadline-exceeded")
        return result

    def metadata():
        result = run(common.metadata_command(offline=offline), cargo)
        data = json.loads(result.stdout, object_pairs_hook=_unique_object)
        verify_cargo_workspace_patches_v2(
            data,
            workspace_root=workspace,
            plan=plan,
            workspace_manifest=documents["Cargo.toml"],
            lockfile=documents["Cargo.lock"],
            registry_sources=sources,
            maximum_document_bytes=maximum_document_bytes,
        )
        verify_retained_cargo_metadata_inputs_v2(
            materialized, consumer_inputs, data, environment=environment
        )

    try:
        guard()
        metadata()
        for command in common.gates:
            run(command, tools[command.argv[0]])
        metadata()
        guard()
        if time.monotonic() >= deadline:
            raise ValueError("retained.execution.v2-deadline-exceeded")
    except Exception as exc:
        raise RetainedCargoExecutionError(
            "retained.execution.v2-failed", observations
        ) from exc
    return tuple(observations)
