"""Private consumer configuration observations and complete current bookends.

Origin-specific facades freshly capture actual scopes from original live
materializations. These shared mechanics cannot mint execution permission.
"""

from __future__ import annotations

from collections.abc import Mapping

from literate_ai.adapters.retained_cargo_execution_inputs import _state
from literate_ai.contracts.identity import canonical_identity
from literate_ai.projects import PinnedInputClosure


class _CargoConsumerExecutionInputMethods:
    __slots__ = ()
    _IDENTITY_SCHEMA = "literate-ai/retained-cargo-execution-inputs@2"

    def _current_identity(self, *, environment: Mapping[str, str]):
        self.materialized.require_unchanged()
        self.scope.require_unchanged(environment=environment)
        for path, before in self._states:
            if _state(path) != before:
                raise ValueError("retained.inputs.v2-ancestor-configuration-changed")
        self._configuration.require_unchanged()
        # Project captured fields inside the live bookends. The closing
        # materialization still reopens provider inputs and ends with a
        # full scratch and wrapper check after that callback.
        identity = canonical_identity(
            {
                "schema": self._IDENTITY_SCHEMA,
                "binding": self.materialized.files.reviewed.binding.identity.uri,
                "scope": self.scope._captured_identity().uri,
                "configuration": self._configuration.identity,
                "present": [str(path) for path, state in self._states if state[2]],
                "absent": [
                    str(path) for path, state in self._states if state[2] is None
                ],
            }
        )
        self.scope.require_unchanged(environment=environment)
        self.materialized.require_unchanged()
        return identity

    def require_metadata_paths(self, metadata, *, environment):
        """Join bounded logical paths through the exact original captured owners."""
        from .retained_cargo_metadata_inputs_v2 import (
            _paths,
            _projection_memory,
            _require_membership,
            _scope_matches,
        )

        # Keep both original complete observations, including independently
        # pinned ancestor configuration and native materialization/scratch state.
        self.current_identity(environment=environment)
        _scope_matches(self.materialized, self.scope, environment)
        maximum_paths = self.scope.policy.input_custody.aggregate.maximum_entries * 2
        memory = _projection_memory(self.materialized, self.scope)
        paths = _paths(metadata, maximum_paths, memory)
        _require_membership(paths, self.materialized, self.scope)
        self.current_identity(environment=environment)
        # Exact built-in containers/strings are reprojected without callbacks.
        if _paths(metadata, maximum_paths, memory) != paths:
            raise ValueError("retained.inputs.v2-metadata-changed")


def _capture_consumer_ancestor_configuration(workspace, scope, policy):
    budget = policy.input_custody.aggregate
    counts = scope.owners.counts
    remaining = budget.maximum_total_bytes - counts["bytes"]
    entries = budget.maximum_entries - counts["entries"]
    files = budget.maximum_files - counts["files"]
    if min(remaining, entries, files) < 1:
        raise ValueError("retained.inputs.v2-configuration-budget-exhausted")
    closure = PinnedInputClosure(
        maximum_files=min(files, entries),
        maximum_file_bytes=min(budget.maximum_file_bytes, remaining),
        maximum_total_bytes=remaining,
    )
    states = []
    for index, parent in enumerate(workspace.parents):
        directory = parent / ".cargo"
        states.append((directory, _state(directory)))
        for name in ("config", "config.toml"):
            path = directory / name
            before = _state(path)
            states.append((path, before))
            if before[2] is not None:
                closure.pin(path, boundary=directory, label=f"ancestor-{index}/{name}")
        if len(states) > entries:
            raise ValueError("retained.inputs.v2-configuration-entry-limit")
    return tuple(states), closure
