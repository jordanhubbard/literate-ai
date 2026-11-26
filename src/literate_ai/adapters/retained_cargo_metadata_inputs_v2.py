"""Join Cargo metadata paths to complete live v2 input and package custody.

This checks membership, not the Cargo resolution graph, manifest harness flags,
ancestor configuration, measured tools or native execution. Those remain separate
requirements of the receiving runner. Metadata never supplies filesystem roots,
source exclusions, scratch ownership or permission to execute a command.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import chain
from pathlib import Path

from literate_ai.adapters.retained_cargo_input_scope_v2 import (
    RetainedCargoInputScopeV2,
)
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    RetainedCargoScratchMaterializationV2,
)
from literate_ai.contracts.native_sdk_trees import NativeSdkTree, _ResolutionBudget
from literate_ai.contracts.paths import canonical_relative_posix_path


def _paths(metadata, maximum_paths, maximum_memory):
    if type(metadata) is not dict or type(metadata.get("packages")) is not list:
        raise ValueError("retained.cargo.v2-metadata-invalid")
    packages = metadata["packages"]
    if not packages or len(packages) > maximum_paths:
        raise ValueError("retained.cargo.v2-metadata-path-limit")
    paths = []
    memory = 0

    def append(value):
        nonlocal memory
        if type(value) is not str or not value or len(value) > 4096 or "\x00" in value:
            raise ValueError("retained.cargo.v2-metadata-path-invalid")
        # UTF-8 uses at most four bytes per admitted codepoint. Check length
        # before encoding, then retain only this bounded (at most 16 KiB) buffer.
        encoded = value.encode("utf-8")
        if len(encoded) > 4096:
            raise ValueError("retained.cargo.v2-metadata-path-invalid")
        memory += 512 + 64 * len(encoded)
        if memory > maximum_memory:
            raise ValueError("retained.cargo.v2-metadata-memory-limit")
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError("retained.cargo.v2-metadata-path-invalid")
        paths.append(path)

    for package in packages:
        if type(package) is not dict or type(package.get("targets")) is not list:
            raise ValueError("retained.cargo.v2-metadata-invalid")
        targets = package["targets"]
        if len(paths) + 1 + len(targets) > maximum_paths:
            raise ValueError("retained.cargo.v2-metadata-path-limit")
        append(package.get("manifest_path"))
        for target in targets:
            if type(target) is not dict:
                raise ValueError("retained.cargo.v2-metadata-invalid")
            append(target.get("src_path"))
    return tuple(paths)


def _scope_matches(materialized, scope, environment):
    reviewed = materialized._files.reviewed
    if (
        scope._scratch is not materialized._scratch
        or scope.policy != reviewed.policy
        or scope.owners.policy != reviewed.policy.input_custody
    ):
        raise ValueError("retained.cargo.v2-metadata-input-owner-mismatch")
    expected = {"workspace": materialized._scratch.context.workspace}
    for name, variable in (
        ("cargo-home", "CARGO_HOME"),
        *(("external:" + name, name) for name in scope.policy.external_input_variables),
    ):
        value = environment.get(variable)
        if type(value) is not str or not value:
            raise ValueError("retained.cargo.v2-metadata-input-owner-mismatch")
        expected[name] = Path(value)
    owners = scope.policy.input_custody.owners
    if tuple(name for name, _ in scope.owners.trees) != tuple(
        x.scope for x in owners
    ) or scope.roots != tuple((name, tree.root) for name, tree in scope.owners.trees):
        raise ValueError("retained.cargo.v2-metadata-input-owner-mismatch")
    for (name, tree), owner in zip(scope.owners.trees, owners, strict=True):
        if (
            tree.root != expected[name]
            or tree.budget != owner.budget
            or tree.exclusions
            != (
                materialized._scratch.workspace_exclusions
                if name == "workspace"
                else ()
            )
        ):
            raise ValueError("retained.cargo.v2-metadata-input-owner-mismatch")


def _projection_memory(materialized, scope):
    # Admit the additional indexes before allocating them. The captured owners'
    # conservative bound already includes their simultaneous closing graph;
    # these working indexes are released before the final full reobservation.
    entries = sum(tree.entry_count for _, tree in scope.owners.trees)
    names = sum(
        len(name.encode("utf-8"))
        for _, tree in scope.owners.trees
        for name in chain(
            tree.directories,
            (name for name, _blob, _mode in tree.files),
            (alias.path for alias in tree.aliases),
        )
    )
    package_files = sum(len(package.files) for package in materialized.packages)
    alias_text = sum(
        len(alias.target.encode("utf-8"))
        for _, tree in scope.owners.trees
        for alias in tree.aliases
    )
    required_memory = (
        16 * 1024**2 * len(scope.owners.trees)
        + 4096 * entries
        + 64 * names
        + 64 * alias_text
        + 4096 * package_files
    )
    if required_memory > scope.owners.maximum_metadata_bytes:
        raise ValueError("retained.cargo.v2-metadata-memory-limit")
    # Reserve both the original projection and the final closing projection.
    return (scope.owners.maximum_metadata_bytes - required_memory) // 2


def _require_membership(paths, materialized, scope):
    roots = {tree.root: tree for _name, tree in scope.owners.trees}
    packages = {package.root: package for package in materialized.packages}
    if (
        len(roots) != len(scope.owners.trees)
        or len(packages) != len(materialized.packages)
        or not roots.keys().isdisjoint(packages)
    ):
        raise ValueError("retained.cargo.v2-metadata-input-owner-mismatch")
    selected = {**roots, **packages}
    groups = {}
    for path in paths:
        # Select the nearest declared owner once. Do not scan every package or
        # rehash every input for each path in a large dependency graph.
        for ancestor in chain((path,), path.parents):
            if ancestor in selected:
                groups.setdefault(ancestor, set()).add(path)
                break
        else:
            raise ValueError("retained.cargo.v2-uncaptured-package-path")
    for package in materialized.packages:
        names = {item.path for item in package.files}
        for path in groups.get(package.root, ()):
            if path.relative_to(package.root).as_posix() not in names:
                raise ValueError("retained.cargo.v2-uncaptured-package-path")
    resolution = _ResolutionBudget(
        remaining=max(
            1048576, scope.policy.input_custody.aggregate.maximum_entries * 128
        )
    )
    for _name, tree in scope.owners.trees:
        grouped = groups.get(tree.root)
        if not grouped:
            continue
        directories = set(tree.directories)
        files = {name for name, _blob, _mode in tree.files}
        aliases = {alias.path: alias for alias in tree.aliases}
        for path in grouped:
            relative = path.relative_to(tree.root).as_posix()
            canonical_relative_posix_path(relative, label="Cargo metadata input")
            try:
                resolved = NativeSdkTree._resolve(
                    relative, directories, files, aliases, resolution
                )
            except ValueError as exc:
                raise ValueError("retained.cargo.v2-uncaptured-package-path") from exc
            if resolved not in files:
                raise ValueError("retained.cargo.v2-uncaptured-package-path")


def verify_retained_cargo_metadata_inputs_v2(
    materialized: RetainedCargoScratchMaterializationV2,
    scope: RetainedCargoInputScopeV2,
    metadata: dict,
    *,
    environment: Mapping[str, str],
) -> None:
    """Check every manifest/target through current owners, including internal aliases.

    Only the exact original live scratch owner can join generated package bytes
    to workspace exclusions. Full source/provider/package/environment guards
    bracket the complete batch, rather than rehashing the entire input closure
    for each metadata path. No path supplied by metadata is opened here.
    """
    if (
        type(materialized) is not RetainedCargoScratchMaterializationV2
        or type(scope) is not RetainedCargoInputScopeV2
        or not isinstance(environment, Mapping)
    ):
        raise TypeError("retained.cargo.v2-live-metadata-inputs-required")
    materialized.require_unchanged()
    scope.require_unchanged(environment=environment)
    _scope_matches(materialized, scope, environment)
    maximum_paths = scope.policy.input_custody.aggregate.maximum_entries * 2
    memory = _projection_memory(materialized, scope)
    paths = _paths(metadata, maximum_paths, memory)
    _require_membership(paths, materialized, scope)
    scope.require_unchanged(environment=environment)
    materialized.require_unchanged()
    if _paths(metadata, maximum_paths, memory) != paths:
        raise ValueError("retained.cargo.v2-metadata-changed")
