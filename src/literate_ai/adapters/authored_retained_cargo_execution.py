"""Distinct authored native consumer execution under original receiving custody."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    AuthoredRetainedCargoExecutionInputs,
)
from literate_ai.adapters.authored_retained_cargo_materialization import (
    AuthoredRetainedCargoMaterialization,
)
from literate_ai.adapters.builders import run_bounded_process
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.retained_cargo_execution import (
    RetainedCargoCommandObservation,
)
from literate_ai.adapters.retained_cargo_execution_core import (
    _execute_cargo_consumer,
)


@dataclass(frozen=True, slots=True)
class AuthoredRetainedCargoExecution:
    observations: tuple[RetainedCargoCommandObservation, ...]
    target_outcomes: tuple
    consumer_inputs_identity: object


def execute_authored_retained_cargo_consumer(
    materialized: AuthoredRetainedCargoMaterialization,
    *,
    cargo: LocalComponentToolBinding,
    rustc: LocalComponentToolBinding,
    gate_tools: Mapping[str, LocalComponentToolBinding],
    environment: Mapping[str, str],
    consumer_inputs: AuthoredRetainedCargoExecutionInputs,
    allow_host_execution: bool,
    read_exclusion_permission=None,
    registry_sources: Mapping[str, str] | None = None,
    offline: bool = True,
    timeout_seconds: float = 900,
    max_output_bytes: int = 4 * 1024 * 1024,
    max_total_output_bytes: int = 64 * 1024 * 1024,
) -> AuthoredRetainedCargoExecution:
    """Bracket complete reviewed gates and typed target coverage with real metadata.

    No retirement or source mutation occurs here. Authorization is explicit, all
    commands share one finite deadline/output budget, and a successful process is
    not a durable admission. The caller owns independently measured tools and
    current registry-source/permission authority; candidate documents cannot
    supply those permissions. This is same-user execution, not OS containment.
    """
    if allow_host_execution is not True:
        raise ValueError("retained.execution.authored-authorization-required")
    if (
        type(materialized) is not AuthoredRetainedCargoMaterialization
        or type(consumer_inputs) is not AuthoredRetainedCargoExecutionInputs
        or consumer_inputs.materialized is not materialized
    ):
        raise TypeError("retained.execution.authored-live-inputs-required")
    observations, outcomes, baseline = _execute_cargo_consumer(
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
        _process=run_bounded_process,
    )
    return AuthoredRetainedCargoExecution(observations, outcomes, baseline)
