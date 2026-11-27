"""Private bounded native session for the two exact receiving owner families.

The public facades bind actual process I/O. No public arbitrary currentness or
process callback grants execution; both original input/materializer owners must
match. Native target protocols and SDK/runtime custody remain unchanged.
"""

from __future__ import annotations

import json
import math
import time
from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    AuthoredRetainedCargoExecutionInputs,
)
from literate_ai.adapters.authored_retained_cargo_materialization import (
    AuthoredRetainedCargoMaterialization,
)
from literate_ai.adapters.authored_retained_cargo_reopened_output import (
    _capture_reopened_output_completion,
    _reopened_cargo_output,
    _reopened_metadata_command,
    _require_reopened_command_pins,
    _require_reopened_configuration,
    _verify_reopened_workspace,
)
from literate_ai.adapters.authored_retained_cargo_tool_completion import (
    _capture_authored_consumer_tools,
)
from literate_ai.adapters.builders._executable_digest_data import (
    read_only_executable_digest_data,
)
from literate_ai.adapters.cargo_workspace_patches_v2 import (
    verify_cargo_workspace_patches_v2,
)
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.retained_cargo_current import _unique_object
from literate_ai.adapters.retained_cargo_execution import (
    RetainedCargoCommandObservation,
    RetainedCargoExecutionError,
)
from literate_ai.adapters.retained_cargo_execution_inputs_v2 import (
    RetainedCargoExecutionInputsV2,
)
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    RetainedCargoMaterializationV2,
)
from literate_ai.adapters.retained_cargo_test_execution import (
    _require_native_completion_deadline,
    _UnsavableNativePreparation,
)
from literate_ai.adapters.retained_cargo_test_execution_v2 import (
    _observe_retained_cargo_test_session_v2,
    _ObservedRetainedCargoTests,
    observe_retained_cargo_tests_v2,
)
from literate_ai.application.agent_skill_catalog import (
    read_only_skill_manifest_metadata,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_test_protocol import (
    RetainedCargoCustomProtocol,
    RetainedCargoExcludedProtocol,
)
from literate_ai.projects import read_only_project_manifest_metadata


def _require_distinct_extra_guard(tool, extra_guard):
    """Share an identical current tool callback, never a cached guard result."""
    if not (
        type(tool) is LocalComponentToolBinding and extra_guard is tool._authority_guard
    ):
        extra_guard()


_NATIVE_EXECUTION_KEY = object()


@dataclass(frozen=True, slots=True, eq=False)
class _RetainedCargoNativeCompletion(_UnsavableNativePreparation):
    tests: _ObservedRetainedCargoTests = field(repr=False)
    deadline: float = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _NATIVE_EXECUTION_KEY:
            raise TypeError("retained.execution.original-native-completion-required")

    def require_original_files(self):
        self.tests.require_original_files()

    def refresh_native_dependencies(self):
        """Original execution deadline only; no new execution or admission grant.

        Owning admission must complete all current/provider closers and run its
        remaining original consumer facts after these inspector callbacks.
        """
        _require_native_completion_deadline(self.deadline)
        self.tests.require_original_files()
        self.tests.preparation.refresh_native_dependencies(deadline=self.deadline)
        self.tests.require_original_files()
        _require_native_completion_deadline(self.deadline)


@dataclass(frozen=True, slots=True, eq=False)
class _RetainedCargoExecutedSession(_UnsavableNativePreparation):
    observations: tuple = field(repr=False)
    target_outcomes: tuple = field(repr=False)
    consumer_inputs_identity: object = field(repr=False)
    native_completion: object = field(repr=False)
    tool_completion: object = field(repr=False)
    output_completion: object = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _NATIVE_EXECUTION_KEY:
            raise TypeError("retained.execution.original-native-session-required")


def _execute_cargo_consumer(
    materialized: RetainedCargoMaterializationV2 | AuthoredRetainedCargoMaterialization,
    *,
    cargo: LocalComponentToolBinding,
    rustc: LocalComponentToolBinding,
    gate_tools: Mapping[str, LocalComponentToolBinding],
    environment: Mapping[str, str],
    consumer_inputs: RetainedCargoExecutionInputsV2
    | AuthoredRetainedCargoExecutionInputs,
    allow_host_execution: bool,
    read_exclusion_permission=None,
    registry_sources: Mapping[str, str] | None = None,
    offline: bool = True,
    timeout_seconds: float = 900,
    max_output_bytes: int = 4 * 1024 * 1024,
    max_total_output_bytes: int = 64 * 1024 * 1024,
    _process,
):
    """Bracket complete reviewed gates and typed target coverage with real metadata.

    No retirement or source mutation occurs here. Authorization is explicit, all
    commands share one finite deadline/output budget, and a successful process is
    not a durable admission. The caller owns independently measured tools and
    current registry-source/permission authority; candidate documents cannot
    supply those permissions. This is same-user execution, not OS containment.
    """
    executed = _execute_cargo_consumer_session(
        materialized,
        cargo=cargo,
        rustc=rustc,
        gate_tools=gate_tools,
        environment=environment,
        consumer_inputs=consumer_inputs,
        allow_host_execution=allow_host_execution,
        read_exclusion_permission=read_exclusion_permission,
        registry_sources=registry_sources,
        offline=offline,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        max_total_output_bytes=max_total_output_bytes,
        _process=_process,
        _retain_native=False,
    )
    return (
        executed.observations,
        executed.target_outcomes,
        executed.consumer_inputs_identity,
    )


# Fresh bounded DATA frames belong to each invocation. Discovery, every original
# byte/image read, native probes and all guard bookends remain fresh.
@read_only_executable_digest_data()
@read_only_skill_manifest_metadata()
@read_only_project_manifest_metadata()
def _execute_cargo_consumer_session(
    materialized: RetainedCargoMaterializationV2 | AuthoredRetainedCargoMaterialization,
    *,
    cargo: LocalComponentToolBinding,
    rustc: LocalComponentToolBinding,
    gate_tools: Mapping[str, LocalComponentToolBinding],
    environment: Mapping[str, str],
    consumer_inputs: RetainedCargoExecutionInputsV2
    | AuthoredRetainedCargoExecutionInputs,
    allow_host_execution: bool,
    read_exclusion_permission=None,
    registry_sources: Mapping[str, str] | None = None,
    offline: bool = True,
    timeout_seconds: float = 900,
    max_output_bytes: int = 4 * 1024 * 1024,
    max_total_output_bytes: int = 64 * 1024 * 1024,
    _process,
    _retain_native=True,
):
    """Bracket complete reviewed gates and typed target coverage with real metadata.

    No retirement or source mutation occurs here. Authorization is explicit, all
    commands share one finite deadline/output budget, and a successful process is
    not a durable admission. The caller owns independently measured tools and
    current registry-source/permission authority; candidate documents cannot
    supply those permissions. This is same-user execution, not OS containment.
    """
    if type(_retain_native) is not bool:
        raise TypeError("retained.execution.native-retention-mode-invalid")
    if allow_host_execution is not True:
        raise ValueError("retained.execution.v2-authorization-required")
    if (
        not (
            (
                type(materialized) is RetainedCargoMaterializationV2
                and type(consumer_inputs) is RetainedCargoExecutionInputsV2
            )
            or (
                type(materialized) is AuthoredRetainedCargoMaterialization
                and type(consumer_inputs) is AuthoredRetainedCargoExecutionInputs
            )
        )
        or consumer_inputs.materialized is not materialized
    ):
        raise TypeError("retained.execution.v2-live-inputs-required")
    if (
        type(offline) is not bool
        or type(timeout_seconds) not in (int, float)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
        or any(
            type(x) is not int or x < 2
            for x in (max_output_bytes, max_total_output_bytes)
        )
    ):
        raise ValueError("retained.execution.v2-bounds-invalid")
    materialized.require_unchanged()
    reviewed = materialized.files.reviewed
    plan, policy = reviewed.plan, reviewed.policy
    plan.require_gate_policy(policy)
    root, workspace = reviewed.project.root, materialized.scratch.context.workspace
    output = workspace / plan.graph.common.output_directory
    if not any(
        x.kind == "cargo-output" and workspace / x.path == output
        for x in plan.scratch_roots
    ):
        raise ValueError("retained.execution.v2-owned-output-required")
    if (
        consumer_inputs.scope.policy != policy
        or consumer_inputs.scope._scratch is not materialized.scratch
    ):
        raise ValueError("retained.execution.v2-input-policy-mismatch")
    base_environment = dict(environment)
    baseline = consumer_inputs.current_identity(environment=base_environment)
    registry = {} if registry_sources is None else dict(registry_sources)
    registry_identity = canonical_identity(registry)

    def measured(tool):
        if (
            not isinstance(tool, LocalComponentToolBinding)
            or tool.authority_identity is None
            or not callable(tool._authority_guard)
        ):
            raise ValueError("retained.execution.v2-measured-tool-required")
        tool.require_unchanged()

    measured(cargo)
    measured(rustc)
    if (
        cargo.toolchain_identity != plan.common.cargo_identity
        or rustc.toolchain_identity != plan.common.rustc_identity
        or rustc.arguments
    ):
        raise ValueError("retained.execution.v2-native-tool-mismatch")
    tools = dict(gate_tools)
    needed = {command.argv[0] for command in plan.common.gates}
    needed.update(
        target.protocol.command.argv[0]
        for target in reviewed.inventory.targets
        if isinstance(target.protocol, RetainedCargoCustomProtocol)
        and target.protocol.command.argv[0] != "{target_executable}"
    )
    if set(tools) != needed:
        raise ValueError("retained.execution.v2-gate-tools-incomplete")
    for tool in tools.values():
        measured(tool)
        if tool.toolchain_identity not in policy.toolchains:
            raise ValueError("retained.execution.v2-gate-tool-unreviewed")
    if offline and any(command.network for command in plan.common.gates):
        raise ValueError("retained.execution.v2-network-gate-refused")
    roots = dict(consumer_inputs.scope.roots)

    def reserved(values, cwd):
        if values.get("CARGO_HOME") != str(roots["cargo-home"]):
            raise ValueError("retained.execution.v2-cargo-home-override")
        for name in policy.external_input_variables:
            if values.get(name) != str(roots["external:" + name]):
                raise ValueError("retained.execution.v2-external-input-override")
        selected = values.get("CARGO_TARGET_DIR", str(output))
        path = Path(selected)
        if (path if path.is_absolute() else cwd / path) != output:
            raise ValueError("retained.execution.v2-output-override")
        if values.get("RUSTC", rustc.executable) != rustc.executable:
            raise ValueError("retained.execution.v2-compiler-override")

    reserved(base_environment, workspace)
    reopened_output = _reopened_cargo_output(materialized)
    process_environment = base_environment
    if reopened_output is not None:
        output = reopened_output
        process_environment = {**base_environment, "CARGO_TARGET_DIR": str(output)}
        # Base parent means the reviewed logical output container. Reviewed
        # gate/tool/config pins are concrete and never silently redirected.
        for name in ("CARGO_BUILD_TARGET_DIR", "CARGO_BUILD_BUILD_DIR"):
            if name in base_environment and Path(base_environment[name]) != output:
                raise ValueError("retained.reopen.base-output-pin-refused")
        for command in plan.common.gates:
            _require_reopened_command_pins(
                command, tools[command.argv[0]], output=output, project_root=root
            )
        for target in reviewed.inventory.targets:
            if isinstance(target.protocol, RetainedCargoCustomProtocol):
                command = target.protocol.command
                _require_reopened_command_pins(
                    command,
                    tools.get(command.argv[0], cargo),
                    output=output,
                    project_root=root,
                )
        for tool in (cargo, rustc):
            _require_reopened_command_pins(
                _reopened_metadata_command(materialized, offline=offline),
                tool,
                output=output,
                project_root=root,
            )
        _require_reopened_configuration(consumer_inputs, output=output)
    deadline = time.monotonic() + timeout_seconds
    tool_completion = None
    if _retain_native and type(materialized) is AuthoredRetainedCargoMaterialization:
        tool_completion = _capture_authored_consumer_tools(
            consumer_inputs,
            cargo=cargo,
            rustc=rustc,
            gate_tools=tools,
            environment=base_environment,
            deadline=deadline,
        )
    observations, remaining = [], max_total_output_bytes
    exclusion_permissions = tuple(
        target.protocol.permission_identity
        for target in reviewed.inventory.targets
        if isinstance(target.protocol, RetainedCargoExcludedProtocol)
    )

    def permissions():
        if exclusion_permissions and not callable(read_exclusion_permission):
            raise ValueError("retained.execution.v2-exclusion-authority-required")
        for identity in exclusion_permissions:
            if read_exclusion_permission(identity) != identity:
                raise ValueError("retained.execution.v2-exclusion-authority-changed")

    def guard():
        for tool in (cargo, rustc, *tools.values()):
            tool.require_unchanged()
        # This complete input check already brackets its capture with live
        # materialized source/package/scratch checks. Do not repeat that scan
        # before the independently measured tool observations above.
        if consumer_inputs.current_identity(environment=base_environment) != baseline:
            raise ValueError("retained.execution.v2-consumer-inputs-changed")
        if (
            registry_sources is not None
            and canonical_identity(dict(registry_sources)) != registry_identity
        ):
            raise ValueError("retained.execution.v2-registry-selection-changed")
        permissions()
        if time.monotonic() >= deadline:
            raise ValueError("retained.execution.v2-deadline")

    def run(
        command,
        tool,
        *,
        extra_guard=lambda: None,
        timeout_seconds=None,
        max_output_bytes=None,
    ):
        nonlocal remaining
        guard()
        _require_distinct_extra_guard(tool, extra_guard)
        # A derived native tool's own guard is the exact binary/runtime/source
        # guard. Run it once at this boundary; distinct extra guards still run.
        measured(tool)
        cwd = root / command.working_directory
        require_safe_directory(cwd)
        values = {
            **process_environment,
            **dict(tool.environment),
            **{entry.name: entry.value for entry in command.environment},
        }
        reserved(values, cwd)
        require_safe_directory(output)
        values.update(CARGO_TARGET_DIR=str(output), RUSTC=rustc.executable)
        cap = min(output_limit, remaining // 2)
        if max_output_bytes is not None:
            cap = min(cap, max_output_bytes)
        duration = deadline - time.monotonic()
        if timeout_seconds is not None:
            duration = min(duration, timeout_seconds)
        if cap < 1 or duration <= 0:
            raise ValueError("retained.execution.v2-budget-exhausted")
        argv = (*tool.command, *command.argv[1:])
        try:
            result = _process(
                argv,
                cwd=cwd,
                environment=values,
                timeout_seconds=duration,
                stdout_limit_bytes=cap,
                stderr_limit_bytes=cap,
                error_prefix="retained.execution.v2",
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
            remaining -= len(result.stdout) + len(result.stderr)
            if (
                max_output_bytes is not None
                and len(result.stdout) + len(result.stderr) > max_output_bytes
            ):
                raise ValueError("retained.execution.v2-custom-output-exhausted")
        finally:
            guard()
            _require_distinct_extra_guard(tool, extra_guard)
            tool.require_unchanged()
            require_safe_directory(output)
        if result.returncode != 0:
            raise ValueError("retained.execution.v2-command-failed")
        return result

    output_limit = max_output_bytes

    def metadata():
        command = (
            plan.metadata_command(offline=offline)
            if reopened_output is None
            else _reopened_metadata_command(materialized, offline=offline)
        )
        result = run(command, cargo)
        document = json.loads(result.stdout, object_pairs_hook=_unique_object)
        if reopened_output is None:
            verify_cargo_workspace_patches_v2(
                document,
                workspace_root=workspace,
                plan=plan,
                workspace_manifest=(workspace / "Cargo.toml").read_bytes(),
                lockfile=(workspace / "Cargo.lock").read_bytes(),
                registry_sources=registry,
            )
        else:
            _verify_reopened_workspace(
                document, materialized=materialized, registry_sources=registry
            )
        consumer_inputs.require_metadata_paths(document, environment=base_environment)
        guard()
        return document

    try:
        guard()
        before = metadata()
        for command in plan.common.gates:
            run(command, tools[command.argv[0]])
        if _retain_native:
            native_tests = _observe_retained_cargo_test_session_v2(
                materialized,
                before,
                cargo,
                rustc=rustc,
                environment=base_environment,
                offline=offline,
                run=run,
                observation_identity=lambda: observations[-1].identity,
                source_guard=guard,
                gate_tools=tools,
                read_exclusion_permission=read_exclusion_permission,
                registry_sources=registry,
            )
            outcomes = native_tests.outcomes
        else:
            native_tests = None
            outcomes = observe_retained_cargo_tests_v2(
                materialized,
                before,
                cargo,
                rustc=rustc,
                environment=base_environment,
                offline=offline,
                run=run,
                observation_identity=lambda: observations[-1].identity,
                source_guard=guard,
                gate_tools=tools,
                read_exclusion_permission=read_exclusion_permission,
                registry_sources=registry,
            )
        metadata()
        guard()
        if tool_completion is not None:
            tool_completion.require_original_files()
        output_completion = None
        if reopened_output is not None:
            output_completion = _capture_reopened_output_completion(
                materialized,
                environment=environment,
                environment_identity=canonical_identity(base_environment),
                registry_sources=registry_sources,
                registry_identity=registry_identity,
                exclusion_permissions=exclusion_permissions,
                read_exclusion_permission=read_exclusion_permission,
                deadline=deadline,
            )
            # All callbacks precede rechecks of the SAME complete output capture.
            guard()
            if native_tests is not None:
                native_tests.require_original_files()
            if tool_completion is not None:
                tool_completion.require_original_files()
            output_completion.require_original_files()
    except Exception as error:
        raise RetainedCargoExecutionError(
            "retained.execution.v2-failed", observations
        ) from error
    completion = (
        _RetainedCargoNativeCompletion(native_tests, deadline, _NATIVE_EXECUTION_KEY)
        if _retain_native
        else None
    )
    return _RetainedCargoExecutedSession(
        tuple(observations),
        outcomes,
        baseline,
        completion,
        tool_completion,
        output_completion,
        _NATIVE_EXECUTION_KEY,
    )
