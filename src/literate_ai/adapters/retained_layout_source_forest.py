"""Logical original source over a complete canonical partition, never a lease.

Shared directories contribute logical source directories while their native
nodes remain fixed. Only the creating preparation can bind this data to a plan.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_sdk_trees import NativeSdkAlias

from .repository_refresh_reservations import _custody_wire

_FOREST_PROFILE = "logical-forest@1"


def _fail(message):
    raise ValueError("layout.source-forest: " + message)


@dataclass(frozen=True, slots=True)
class _LogicalSourceForest:
    root: Path
    source: str
    project_namespace: str
    project_roles: str
    effect_graph: str
    budget: object
    exclusions: tuple
    directories: tuple
    files: tuple
    aliases: tuple
    maximum_metadata_bytes: int
    _physical: tuple
    shared_directories: tuple

    @property
    def document(self):
        return {
            "schema": "literate-ai/original-logical-source-forest@1",
            "forest": _custody_wire(self),
        }

    @property
    def identity(self):
        return canonical_identity(self.document)


def _physical(node):
    base = node.device, node.inode, node.mode
    owners = node.uid, node.gid
    if stat.S_ISDIR(node.mode):
        return (*base, *owners)
    return (
        *base,
        node.size,
        node.modified_ns,
        node.changed_ns,
        node.links,
        *owners,
    )


def _from_original(census, native, namespace, role_identity, roles, directories, graph):
    """Derive data from funded original facts; create no observation/effect owner.

    The caller funds the complete construction before entering this function.
    Source file and alias coordinates are relative to the selected logical root.
    The complete original census/native roster remains with its namespace owner.
    """
    from .retained_layout_effect_graph import _graph_fields

    _graph_fields(graph)
    tree, source = census.tree, graph.source
    leaf_roles, directory_roles = dict(roles), dict(directories)
    projection = dict(graph.projection)
    leaves = {name for name, role in roles if role == "source"}
    logical_directories = projection.keys() & directory_roles.keys()
    if (
        source not in logical_directories
        or projection.keys() - logical_directories != leaves
        or any(
            "source" not in directory_roles[name]
            for name in logical_directories - {source}
        )
    ):
        _fail("complete original source projection required")

    def relative(name):
        if name == source:
            return ""
        if source == ".":
            return name
        if not name.startswith(source + "/"):
            _fail("logical source escapes the selected coordinate")
        return name[len(source) + 1 :]

    files = tuple(
        (relative(name), blob, executable)
        for name, blob, executable in tree.files
        if leaf_roles[name] == "source"
    )
    aliases = tuple(
        NativeSdkAlias(
            relative(alias.path),
            relative(alias.target) if alias.kind == "hardlink" else alias.target,
            alias.kind,
        )
        for alias in tree.aliases
        if leaf_roles[alias.path] == "source"
    )
    if {name for name, _, _ in files} | {alias.path for alias in aliases} != {
        relative(name) for name in leaves
    }:
        _fail("logical source leaves differ from the complete original census")
    originals = dict(native)
    root_node = originals["" if source == "." else source]
    names = sorted(projection.keys() - {source})
    source_native = (
        ("", root_node),
        *((relative(name), originals[name]) for name in names),
    )
    physical = (
        _physical(root_node),
        tuple((name, _physical(node)) for name, node in source_native[1:]),
    )
    forest = _LogicalSourceForest(
        tree.root if source == "." else tree.root / source,
        source,
        namespace,
        role_identity,
        graph.identity.uri,
        tree.budget,
        (),
        tuple(sorted(relative(name) for name in logical_directories - {source})),
        files,
        aliases,
        tree.maximum_metadata_bytes,
        physical,
        tuple(
            sorted(
                relative(name) or "."
                for name in logical_directories
                if directory_roles[name] != ("source",)
            )
        ),
    )
    return forest, source_native
