"""Complete read-only namespace facts and proposed exact-file layout partitions.

Labels grant no source exclusion, move, execution, Git/control ownership or
qualification authority. The transaction owner must separately join this census
to current reviewed framework ownership and live protected control nodes.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    require_safe_directory,
    stat_is_link_or_reparse,
)
from literate_ai.adapters.retained_cargo_tree_v2 import (
    RetainedCargoInputTreeV2,
    capture_retained_cargo_tree_v2,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.native_sdk_trees import NativeSdkTree, _ResolutionBudget
from literate_ai.contracts.paths import canonical_relative_posix_paths
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from .retained_layout import RetainedLayoutError


def _physical_wire(value):
    # Local filesystem facts need not fit canonical JSON's signed64 domain.
    # Match repository-refresh custody encoding; never truncate through floats.
    if isinstance(value, int) and not isinstance(value, bool):
        return (
            value if -(2**63) <= value <= 2**63 - 1 else {"integer_decimal": str(value)}
        )
    if isinstance(value, dict):
        return {key: _physical_wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_physical_wire(item) for item in value]
    return value


def _lineage(root: Path) -> tuple:
    from .bounded_role_observation import current_role_observation

    observation = current_role_observation()
    if observation is not None:
        observation.reserve_lineage(root)
    try:
        require_safe_directory(root)
        nodes = []
        for directory in (*reversed(root.parents), root):
            node = directory.lstat()
            if not stat.S_ISDIR(node.st_mode) or stat_is_link_or_reparse(node):
                raise RetainedLayoutError("layout physical ancestry is redirected")
            nodes.append(
                (
                    str(directory),
                    node.st_dev,
                    node.st_ino,
                    node.st_mode,
                    node.st_uid,
                    node.st_gid,
                )
            )
        value = tuple(nodes)
        if observation is not None:
            observation.remember_lineage(root, value)
        return value
    except (OSError, UnsafeFilesystemPathError) as exc:
        raise RetainedLayoutError("layout physical ancestry is unavailable") from exc


@dataclass(frozen=True, slots=True)
class RetainedLayoutPartitionCensus:
    """Physical namespace and proposed labels, with no transition permission."""

    tree: RetainedCargoInputTreeV2
    framework_files: tuple[str, ...]
    other_files: tuple[str, ...]
    shared_directories: tuple[str, ...]
    _lineage: tuple = field(repr=False)

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(
            {
                "schema": "literate-ai/retained-layout-partition-census@1",
                "namespace_identity": self.tree.identity.to_dict(),
                "physical_custody_identity": canonical_identity(
                    _physical_wire(
                        {
                            "ancestry": self._lineage,
                            "namespace_nodes": self.tree._physical,
                        }
                    )
                ).to_dict(),
                "framework_files": list(self.framework_files),
                "other_files": list(self.other_files),
                "shared_directories": list(self.shared_directories),
            }
        )

    def require_unchanged(self) -> None:
        # The same complete capture, not an allowlist of previously seen source.
        # Includes fresh names, bytes, modes, topology and physical identities.
        if _lineage(self.tree.root) != self._lineage:
            raise RetainedLayoutError("layout physical ancestry changed")
        self.tree.require_unchanged()
        if _lineage(self.tree.root) != self._lineage:
            raise RetainedLayoutError("layout physical ancestry changed")


def capture_retained_layout_partition(
    root: Path,
    *,
    framework_files: tuple[str, ...],
    budget: RetainedCargoInputBudget,
    maximum_metadata_bytes: int = 1024 * 1024 * 1024,
) -> RetainedLayoutPartitionCensus:
    """Capture every actual entry, then check proposed exact-file ownership.

    The reused raw reader applies finite byte/entry/metadata budgets, complete
    internal topology and physical closing checks. No exclusions are supplied.
    Exact labels must name observed regular files or aliases; a directory never
    stands for its descendants. Newly present files always enter the other
    partition. Protected Git/control ownership must be bound before any effects.
    """
    if (
        type(budget) is not RetainedCargoInputBudget
        or not isinstance(framework_files, tuple)
        or len(framework_files) > budget.maximum_entries
        or any(not isinstance(name, str) for name in framework_files)
        or framework_files != tuple(sorted(set(framework_files)))
    ):
        raise RetainedLayoutError(
            "layout partition requires a bounded exact file tuple"
        )
    try:
        canonical_relative_posix_paths(framework_files, label="layout framework files")
        original_lineage = _lineage(Path(root).absolute())
        tree = capture_retained_cargo_tree_v2(
            root,
            budget=budget,
            maximum_metadata_bytes=maximum_metadata_bytes,
        )
    except (OSError, ValueError) as exc:
        raise RetainedLayoutError("layout complete namespace capture refused") from exc
    files = {name for name, _, _ in tree.files}
    aliases = {alias.path: alias for alias in tree.aliases}
    leaves = files | aliases.keys()
    framework = frozenset(framework_files)
    if not framework <= leaves:
        raise RetainedLayoutError(
            "layout framework labels require exact observed files"
        )

    # A directory's roles are derived from actual leaves/empty directories; no
    # proposed file label can reserve a directory or hide future children.
    roles: dict[str, set[str]] = {name: set() for name in tree.directories}
    roles["."] = set()

    def role(name: str) -> str:
        return "framework" if name in framework else "other"

    def ancestors(name: str):
        current = name
        while "/" in current:
            current = current.rsplit("/", 1)[0]
            yield current
        yield "."

    for name in leaves:
        for parent in ancestors(name):
            roles[parent].add(role(name))
    # A directory without any observed descendant is still an original entry.
    for name in sorted(tree.directories, key=lambda x: x.count("/"), reverse=True):
        if not roles[name]:
            roles[name].add("other")
        for parent in ancestors(name):
            roles[parent].update(roles[name])

    resolution = _ResolutionBudget(remaining=max(1048576, budget.maximum_entries * 128))
    directories = set(tree.directories)
    for name in sorted(aliases):
        expected_role = role(name)

        def observe(candidate: str, expected_role: str = expected_role) -> None:
            if candidate in aliases and role(candidate) != expected_role:
                raise RetainedLayoutError(
                    "layout alias traverses another proposed ownership partition"
                )

        target = NativeSdkTree._resolve(
            name, directories, files, aliases, resolution, observe=observe
        )
        expected = {expected_role}
        target_roles = roles[target] if target in roles else {role(target)}
        if target_roles != expected:
            raise RetainedLayoutError(
                "layout alias crosses its proposed ownership partition"
            )
    # Namespace parsing/partitioning is read-only; the caller must hold this
    # complete physical capture current before using any of its facts.
    tree.require_unchanged()
    if _lineage(tree.root) != original_lineage:
        raise RetainedLayoutError("layout physical ancestry changed during census")
    return RetainedLayoutPartitionCensus(
        tree,
        framework_files,
        tuple(sorted(leaves - framework)),
        tuple(sorted(name for name, values in roles.items() if len(values) > 1)),
        original_lineage,
    )
