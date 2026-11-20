"""Original source-v2 native execution input owner and exact facade."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

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
from literate_ai.adapters.retained_cargo_input_scope_v2 import (
    RetainedCargoInputScopeV2,
    capture_retained_cargo_input_scope_v2,
)
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    RetainedCargoMaterializationV2,
)
from literate_ai.projects import (
    PinnedInputClosure,
    read_only_project_configuration_parses,
)

_CREATION_KEY = object()


@dataclass(init=False, frozen=True, slots=True)
class RetainedCargoExecutionInputsV2(_CargoConsumerExecutionInputMethods):
    materialized: RetainedCargoMaterializationV2
    scope: RetainedCargoInputScopeV2
    _states: tuple = field(repr=False)
    _configuration: PinnedInputClosure = field(repr=False)

    def __init__(self, *, key, materialized, scope, states, configuration):
        if key is not _CREATION_KEY:
            raise TypeError("retained.inputs.v2-live-capture-required")
        for name, value in (
            ("materialized", materialized),
            ("scope", scope),
            ("_states", states),
            ("_configuration", configuration),
        ):
            object.__setattr__(self, name, value)

    def current_identity(self, *, environment: Mapping[str, str]):
        with (
            read_only_project_configuration_parses(isolated=True),
            read_only_component_catalog_observations(isolated=True),
            read_only_flavor_graph_observations(),
        ):
            return self._current_identity(environment=environment)


def read_retained_cargo_execution_inputs_v2(
    materialized: RetainedCargoMaterializationV2,
    *,
    environment: Mapping[str, str],
    maximum_metadata_bytes: int = 1024 * 1024 * 1024,
) -> RetainedCargoExecutionInputsV2:
    """Capture the entire provisioned Cargo home, not registry/git shortcuts.

    Dependency provisioning and exact-command cache warming precede this reader.
    No cache mutation is permitted during its lifetime. Workspace outputs are
    excluded only through the materializer's still-live original scratch owner.
    """
    if type(materialized) is not RetainedCargoMaterializationV2:
        raise TypeError("retained.inputs.v2-live-materialization-required")
    materialized.require_unchanged()
    reviewed = materialized.files.reviewed
    workspace = materialized.scratch.context.workspace
    scope = capture_retained_cargo_input_scope_v2(
        workspace,
        policy=reviewed.policy,
        environment=environment,
        maximum_metadata_bytes=maximum_metadata_bytes,
        scratch=materialized.scratch,
    )
    states, configuration = _capture_consumer_ancestor_configuration(
        workspace, scope, reviewed.policy
    )
    result = RetainedCargoExecutionInputsV2(
        key=_CREATION_KEY,
        materialized=materialized,
        scope=scope,
        states=states,
        configuration=configuration,
    )
    result.current_identity(environment=environment)
    return result
