"""Authored receiving native execution input owner with fresh actual capture."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from literate_ai.adapters.authored_retained_cargo_input_scope import (
    AuthoredRetainedCargoInputScope,
    capture_authored_retained_cargo_input_scope,
)
from literate_ai.adapters.authored_retained_cargo_materialization import (
    AuthoredRetainedCargoMaterialization,
)
from literate_ai.adapters.legacy_generation_catalog import (
    read_only_flavor_graph_observations,
)
from literate_ai.adapters.locked_generation_authority import (
    read_only_component_catalog_observations,
)
from literate_ai.adapters.retained_cargo_execution_inputs_core import (
    _capture_consumer_ancestor_configuration,
    _CargoConsumerExecutionInputMethods,
)
from literate_ai.projects import (
    PinnedInputClosure,
    read_only_project_configuration_parses,
)

_CREATION_KEY = object()


@dataclass(init=False, frozen=True, slots=True)
class AuthoredRetainedCargoExecutionInputs(_CargoConsumerExecutionInputMethods):
    _IDENTITY_SCHEMA = "literate-ai/authored-retained-cargo-execution-inputs@1"

    materialized: AuthoredRetainedCargoMaterialization
    scope: AuthoredRetainedCargoInputScope
    _states: tuple = field(repr=False)
    _configuration: PinnedInputClosure = field(repr=False)

    def __init__(self, *, key, materialized, scope, states, configuration):
        if key is not _CREATION_KEY:
            raise TypeError("retained.inputs.authored-live-capture-required")
        for name, value in (
            ("materialized", materialized),
            ("scope", scope),
            ("_states", states),
            ("_configuration", configuration),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("retained.inputs.authored-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.inputs.authored-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.inputs.authored-not-serializable")

    def current_identity(self, *, environment: Mapping[str, str]):
        with (
            read_only_project_configuration_parses(isolated=True),
            read_only_component_catalog_observations(isolated=True),
            read_only_flavor_graph_observations(),
        ):
            return self._current_identity(environment=environment)


def read_authored_retained_cargo_execution_inputs(
    materialized: AuthoredRetainedCargoMaterialization,
    *,
    environment: Mapping[str, str],
    maximum_metadata_bytes: int = 1024 * 1024 * 1024,
) -> AuthoredRetainedCargoExecutionInputs:
    """Capture the entire provisioned Cargo home, not registry/git shortcuts.

    Dependency provisioning and exact-command cache warming precede this reader.
    No cache mutation is permitted during its lifetime. Workspace outputs are
    excluded only through the materializer's still-live original scratch owner.
    """
    if type(materialized) is not AuthoredRetainedCargoMaterialization:
        raise TypeError("retained.inputs.authored-live-materialization-required")
    materialized.require_unchanged()
    reviewed = materialized.files.reviewed
    workspace = materialized.scratch.context.workspace
    scope = capture_authored_retained_cargo_input_scope(
        workspace,
        policy=reviewed.policy,
        environment=environment,
        maximum_metadata_bytes=maximum_metadata_bytes,
        scratch=materialized.scratch,
    )
    states, configuration = _capture_consumer_ancestor_configuration(
        workspace, scope, reviewed.policy
    )
    result = AuthoredRetainedCargoExecutionInputs(
        key=_CREATION_KEY,
        materialized=materialized,
        scope=scope,
        states=states,
        configuration=configuration,
    )
    result.current_identity(environment=environment)
    return result
