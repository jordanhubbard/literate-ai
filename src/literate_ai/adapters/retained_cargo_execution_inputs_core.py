"""Private consumer configuration observations and complete current bookends.

Origin-specific facades freshly capture actual scopes from original live
materializations. These shared mechanics cannot mint execution permission.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

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
        """Require every source/manifest to resolve within captured input owners."""
        self.current_identity(environment=environment)
        files = {
            (tree.root / relative).resolve(strict=True)
            for _, tree in self.scope.owners.trees
            for relative, _, _ in tree.files
        }
        for package in self.materialized.packages:
            files.update((package.root / item.path) for item in package.files)
        if not isinstance(metadata, dict) or not isinstance(
            metadata.get("packages"), list
        ):
            raise ValueError("retained.inputs.v2-metadata-invalid")
        for package in metadata["packages"]:
            if not isinstance(package, dict) or not isinstance(
                package.get("targets"), list
            ):
                raise ValueError("retained.inputs.v2-metadata-invalid")
            paths = [package.get("manifest_path")]
            for target in package["targets"]:
                if not isinstance(target, dict):
                    raise ValueError("retained.inputs.v2-metadata-invalid")
                paths.append(target.get("src_path"))
            for value in paths:
                if not isinstance(value, str):
                    raise ValueError("retained.inputs.v2-metadata-invalid")
                path = Path(value)
                if (
                    not path.is_absolute()
                    or ".." in path.parts
                    or path.resolve(strict=True) not in files
                ):
                    raise ValueError("retained.inputs.v2-uncaptured-package-path")
        self.current_identity(environment=environment)


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
