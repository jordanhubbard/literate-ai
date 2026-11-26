"""Observe Cargo's hierarchical configuration through complete current owners.

This is input custody, not configuration interpretation or execution authority.
Every present configuration file must belong to an already reviewed complete
workspace, CARGO_HOME or external input tree. Missing ancestor configurations
remain watched so a later appearance cannot silently change a command's inputs.
The runner still owns configuration-selected tools, includes and external inputs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.retained_cargo_execution_inputs import _state
from literate_ai.adapters.retained_cargo_input_scope_v2 import RetainedCargoInputScopeV2
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    RetainedCargoScratchMaterializationV2,
)
from literate_ai.adapters.retained_cargo_metadata_inputs_v2 import (
    _projection_memory,
    _require_membership,
    _scope_matches,
)
from literate_ai.contracts.identity import canonical_identity


def _candidates(materialized, scope):
    project = materialized._files.reviewed.project.root
    plan = materialized.plan.common
    commands = (plan.metadata_command(offline=True), *plan.gates)
    if len(commands) > 256:
        raise ValueError("retained.cargo.v2-config-path-limit")
    directories = tuple(
        sorted({project / command.working_directory for command in commands})
    )
    # Admit the whole path projection before constructing its parent graph.
    entries = sum(len(path.parts) for path in directories) * 2 + 2
    memory = sum(
        1024 + 256 * (len(str(parent)) + 32)
        for path in directories
        for parent in (path, *path.parents)
    )
    if entries > 4096 or memory > _projection_memory(materialized, scope):
        raise ValueError("retained.cargo.v2-config-path-limit")
    paths = set()
    for directory in directories:
        if not directory.is_absolute() or ".." in directory.parts:
            raise ValueError("retained.cargo.v2-config-directory-invalid")
        require_safe_directory(directory)
        for parent in (directory, *directory.parents):
            paths.update(parent / ".cargo" / name for name in ("config", "config.toml"))
    home = dict(scope.roots)["cargo-home"]
    paths.update(home / name for name in ("config", "config.toml"))
    return directories, tuple(sorted(paths))


def _observations(paths, materialized, scope):
    roots = tuple(tree.root for _scope, tree in scope.owners.trees)
    covered, absent = [], []
    for path in paths:
        if any(path.is_relative_to(root) for root in roots):
            # Complete owner namespaces watch absent files. Present files are
            # checked together below, constructing the input indexes only once.
            workspace = materialized._scratch.context.workspace
            if any(
                path.is_relative_to(workspace / root.path)
                for root in materialized.plan.scratch_roots
                if root.kind == "cargo-output"
            ):
                raise ValueError("retained.cargo.v2-config-output-input-refused")
            if path.exists() or path.is_symlink():
                covered.append(path)
        else:
            state = _state(path)
            if state[2] is not None:
                raise ValueError("retained.cargo.v2-config-uncaptured")
            absent.append((path, state))
    _require_membership(covered, materialized, scope)
    return tuple(covered), tuple(absent)


@dataclass(frozen=True, slots=True)
class RetainedCargoConfigurationV2:
    directories: tuple[Path, ...]
    paths: tuple[Path, ...]
    present: tuple[Path, ...]
    _absent: tuple = field(repr=False)
    _materialized: RetainedCargoScratchMaterializationV2 = field(repr=False)
    _scope: RetainedCargoInputScopeV2 = field(repr=False)

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/retained-cargo-configuration@2",
                "inputs": self._scope.identity.uri,
                "directories": [str(path) for path in self.directories],
                "candidates": [str(path) for path in self.paths],
                "present": [str(path) for path in self.present],
                "absent": [
                    {
                        "path": str(path),
                        "ancestor": str(state[0]),
                        "node": list(state[1]),
                    }
                    for path, state in self._absent
                ],
            }
        )

    def require_unchanged(self, *, environment: Mapping[str, str]):
        self._materialized.require_unchanged()
        self._scope.require_unchanged(environment=environment)
        _scope_matches(self._materialized, self._scope, environment)
        if _candidates(self._materialized, self._scope) != (
            self.directories,
            self.paths,
        ):
            raise ValueError("retained.cargo.v2-config-changed")
        if _observations(self.paths, self._materialized, self._scope) != (
            self.present,
            self._absent,
        ):
            raise ValueError("retained.cargo.v2-config-changed")
        self._scope.require_unchanged(environment=environment)
        self._materialized.require_unchanged()
        # These absent ancestor paths lie outside the captured owner trees.
        # Recheck them after the potentially substantial complete closing
        # observations; an earlier absence cannot authorize a new config file.
        if any(_state(path) != state for path, state in self._absent):
            raise ValueError("retained.cargo.v2-config-changed")


def capture_retained_cargo_configuration_v2(materialized, scope, *, environment):
    if (
        type(materialized) is not RetainedCargoScratchMaterializationV2
        or type(scope) is not RetainedCargoInputScopeV2
        or not isinstance(environment, Mapping)
    ):
        raise TypeError("retained.cargo.v2-live-config-inputs-required")
    materialized.require_unchanged()
    scope.require_unchanged(environment=environment)
    _scope_matches(materialized, scope, environment)
    directories, paths = _candidates(materialized, scope)
    present, absent = _observations(paths, materialized, scope)
    result = RetainedCargoConfigurationV2(
        directories, paths, present, absent, materialized, scope
    )
    result.require_unchanged(environment=environment)
    return result
