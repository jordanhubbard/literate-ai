"""Closed private realization and original complete output completion.

Only an actual reopened authored materialization selects an output child. Saved
paths, observed metadata and caller result objects never supply that selection.
"""

import time
import tomllib
from dataclasses import InitVar, dataclass, field, replace
from pathlib import Path

from literate_ai.adapters.authored_retained_cargo_materialization import (
    AuthoredRetainedCargoMaterialization,
)
from literate_ai.adapters.authored_retained_cargo_reopen_owner import (
    _CurrentAuthoredReopenedNamespace,
)
from literate_ai.adapters.cargo_workspace_patches_v2 import (
    _verify_cargo_workspace_patches_v2,
)
from literate_ai.adapters.retained_cargo_native_output_tree import (
    _capture_original_native_output_tree,
    _NativeOutputCensusLedger,
)
from literate_ai.adapters.retained_cargo_test_execution import (
    _UnsavableNativePreparation,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.repositories import RepositoryBuildEnvironment

_KEY = object()


def _reopened_namespace(materialized):
    if type(materialized) is not AuthoredRetainedCargoMaterialization:
        return None
    owner = materialized.scratch._core
    if type(owner) is not _CurrentAuthoredReopenedNamespace:
        return None
    if (
        owner.before.current is not materialized.current
        or owner.context.reviewed is not materialized.files.reviewed
    ):
        raise ValueError("retained.reopen.original-materialization-mismatch")
    return owner


def _reopened_cargo_output(materialized):
    owner = _reopened_namespace(materialized)
    if owner is None:
        return None
    materialized.scratch.require_unchanged()
    output = owner.cargo_output
    reviewed_parent = (
        owner.context.workspace
        / materialized.files.reviewed.plan.graph.common.output_directory
    )
    if output.parent != reviewed_parent:
        raise ValueError("retained.reopen.reviewed-output-parent-mismatch")
    return output


def _verify_reopened_workspace(metadata, *, materialized, registry_sources):
    output = _reopened_cargo_output(materialized)
    if output is None:
        raise TypeError("retained.reopen.actual-materialization-required")
    reviewed = materialized.files.reviewed
    workspace = materialized.scratch.context.workspace
    _verify_cargo_workspace_patches_v2(
        metadata,
        workspace_root=workspace,
        plan=reviewed.plan,
        workspace_manifest=(workspace / "Cargo.toml").read_bytes(),
        lockfile=(workspace / "Cargo.lock").read_bytes(),
        registry_sources=registry_sources,
        _realized_output=output,
    )
    materialized.scratch._core.require_original_files()


def _reopened_metadata_command(materialized, *, offline):
    output = _reopened_cargo_output(materialized)
    if output is None:
        raise TypeError("retained.reopen.actual-materialization-required")
    command = materialized.files.reviewed.plan.metadata_command(offline=offline)
    return replace(
        command,
        environment=tuple(
            RepositoryBuildEnvironment(item.name, str(output))
            if item.name == "CARGO_TARGET_DIR"
            else item
            for item in command.environment
        ),
    )


def _require_reopened_command_pins(command, tool, *, output, project_root):
    """Refuse incompatible explicit reviewed pins before a process is launched.

    This is an interface check, not a static sandbox for arbitrary host scripts.
    Only the framework-generated metadata command is derived separately.
    """
    cwd = project_root / command.working_directory

    def require_path(value):
        path = Path(value)
        if ".." in path.parts or (path if path.is_absolute() else cwd / path) != output:
            raise ValueError("retained.reopen.reviewed-output-pin-refused")

    for name, value in (
        *tool.environment,
        *((item.name, item.value) for item in command.environment),
    ):
        if name in {
            "CARGO_TARGET_DIR",
            "CARGO_BUILD_TARGET_DIR",
            "CARGO_BUILD_BUILD_DIR",
        }:
            require_path(value)
    argv = (*tool.command, *command.argv[1:])
    for index, value in enumerate(argv):
        if value in {"--target-dir", "--build-dir"}:
            if index + 1 >= len(argv):
                raise ValueError("retained.reopen.reviewed-output-pin-refused")
            require_path(argv[index + 1])
        elif value.startswith(("--target-dir=", "--build-dir=")):
            require_path(value.split("=", 1)[1])
        elif value == "--config" or value.startswith("--config="):
            # Arbitrary extra config can override directory semantics; it must
            # first become captured/current input authority in a future route.
            raise ValueError("retained.reopen.extra-config-refused")


def _require_reopened_configuration(inputs, *, output):
    """Inspect actual Cargo search paths already covered by original owners."""
    materialized = inputs.materialized
    reviewed = materialized.files.reviewed
    workspace = materialized.scratch.context.workspace
    trees = tuple(tree for _, tree in inputs.scope.owners.trees)
    captured = {tree.root / name for tree in trees for name, _, _ in tree.files}
    captured.update(path for path, state in inputs._states if state[2] is not None)
    commands = list(reviewed.plan.common.gates)
    from literate_ai.contracts.retained_cargo_test_protocol import (
        RetainedCargoCustomProtocol,
    )

    commands.extend(
        target.protocol.command
        for target in reviewed.inventory.targets
        if isinstance(target.protocol, RetainedCargoCustomProtocol)
    )
    directories = {workspace}
    directories.update(
        reviewed.project.root / command.working_directory for command in commands
    )
    directories.update(
        workspace / package.root for package in reviewed.plan.graph.common.packages
    )
    paths = set()
    for cwd in directories:
        if not (
            cwd == workspace
            or cwd in workspace.parents
            or any(cwd.is_relative_to(tree.root) for tree in trees)
        ):
            raise ValueError("retained.reopen.uncaptured-command-configuration")
        for parent in (cwd, *cwd.parents):
            paths.update(parent / ".cargo" / name for name in ("config", "config.toml"))
    home = dict(inputs.scope.roots)["cargo-home"]
    paths.update(home / name for name in ("config", "config.toml"))
    for path in sorted(paths):
        if not path.exists() and not path.is_symlink():
            continue
        if path not in captured:
            raise ValueError("retained.reopen.uncaptured-cargo-configuration")
        document = tomllib.loads(path.read_text())
        build = document.get("build", {})
        if not isinstance(build, dict):
            raise ValueError("retained.reopen.cargo-configuration-refused")
        for name in ("target-dir", "build-dir"):
            if name in build:
                value = build[name]
                if not isinstance(value, str) or Path(value) != output:
                    raise ValueError("retained.reopen.configuration-output-pin-refused")


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalReopenedOutputCompletion(_UnsavableNativePreparation):
    namespace: object = field(repr=False)
    scratch: object = field(repr=False)
    trees: tuple = field(repr=False)
    policy: object = field(repr=False)
    environment: object = field(repr=False)
    environment_identity: object = field(repr=False)
    registry_sources: object = field(repr=False)
    registry_identity: object = field(repr=False)
    exclusion_permissions: tuple = field(repr=False)
    read_exclusion_permission: object = field(repr=False)
    deadline: float = field(repr=False)
    _key: InitVar[object]

    def __post_init__(self, _key):
        if _key is not _KEY:
            raise TypeError("retained.reopen.original-output-completion-required")

    def _deadline(self):
        if time.monotonic() >= self.deadline:
            raise ValueError("retained.reopen.original-execution-deadline")

    def require_original_files(self):
        self._deadline()
        self.policy._require_current()
        if (
            self.scratch._output_policy is not self.policy
            or self.scratch._original_output_policy is not self.policy
        ):
            raise ValueError("retained.reopen.original-output-policy-changed")
        if canonical_identity(dict(self.environment)) != self.environment_identity:
            raise ValueError("retained.reopen.original-environment-changed")
        registry = {} if self.registry_sources is None else dict(self.registry_sources)
        if canonical_identity(registry) != self.registry_identity:
            raise ValueError("retained.reopen.original-registry-changed")
        self.namespace.require_original_files()
        ledger = _NativeOutputCensusLedger(
            self.policy.native,
            maximum_files=self.policy.maximum_files,
            maximum_entries=self.policy.maximum_entries,
            maximum_metadata_bytes=self.policy._metadata_limit,
        )
        for tree in self.trees:
            tree.require_unchanged(_ledger=ledger)
        self.namespace.require_original_files()
        self._deadline()

    def refresh_permissions(self):
        self._deadline()
        if self.exclusion_permissions and not callable(self.read_exclusion_permission):
            raise ValueError("retained.reopen.original-permission-reader-required")
        for identity in self.exclusion_permissions:
            if self.read_exclusion_permission(identity) != identity:
                raise ValueError("retained.reopen.original-permission-changed")
        self.require_original_files()


def _capture_reopened_output_completion(
    materialized,
    *,
    environment,
    environment_identity,
    registry_sources,
    registry_identity,
    exclusion_permissions,
    read_exclusion_permission,
    deadline,
):
    owner = _reopened_namespace(materialized)
    if owner is None:
        raise TypeError("retained.reopen.actual-materialization-required")
    materialized.scratch.require_unchanged()
    policy = materialized.scratch._output_policy
    policy._require_current()
    ledger = _NativeOutputCensusLedger(
        policy.native,
        maximum_files=policy.maximum_files,
        maximum_entries=policy.maximum_entries,
        maximum_metadata_bytes=policy._metadata_limit,
    )
    trees = tuple(
        _capture_original_native_output_tree(
            child,
            budget=policy.native,
            maximum_files=policy.maximum_files,
            maximum_entries=policy.maximum_entries,
            maximum_metadata_bytes=policy._metadata_limit,
            _ledger=ledger,
        )
        for _kind, _parent, child, _node in owner._children
    )
    return _OriginalReopenedOutputCompletion(
        owner,
        materialized.scratch,
        trees,
        policy,
        environment,
        environment_identity,
        registry_sources,
        registry_identity,
        exclusion_permissions,
        read_exclusion_permission,
        deadline,
        _KEY,
    )


def _select_reopened_test_executables(
    result, metadata, *, materialized, output_root, registry_sources
):
    from literate_ai.adapters.retained_cargo_test_observation import (
        _select_cargo_test_executable_values,
    )

    output = _reopened_cargo_output(materialized)
    if output is None or output_root.parent != output:
        raise ValueError("retained.reopen.actual-test-child-required")
    _verify_reopened_workspace(
        metadata, materialized=materialized, registry_sources=registry_sources
    )
    return _select_cargo_test_executable_values(
        result,
        metadata,
        workspace_root=materialized.scratch.context.workspace,
        output_root=output_root,
        expected=materialized.files.reviewed.plan.graph.common,
        maximum_bytes=8 * 1024**2,
        maximum_records=10000,
    )
