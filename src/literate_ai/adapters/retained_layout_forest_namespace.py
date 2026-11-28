"""Complete metadata namespace derived from verified native forest receipts.

This is data construction, never a new inventory baseline or project permission.
The caller holds the actual completed native owner and funds the retained view
through its original observation ledger before construction.
"""

from __future__ import annotations

import stat
from collections import defaultdict
from dataclasses import replace

from literate_ai.contracts.native_sdk_trees import (
    NativeSdkAlias,
    NativeSdkTree,
    _ResolutionBudget,
)

from .retained_cargo_tree_v2 import RetainedCargoInputTreeV2


def _physical(node):
    if stat.S_ISDIR(node.mode):
        return node.device, node.inode, node.mode, node.uid, node.gid
    return (
        node.device,
        node.inode,
        node.mode,
        node.size,
        node.modified_ns,
        node.changed_ns,
        node.links,
        node.uid,
        node.gid,
    )


def _from_completed_span(span):
    """Pure projection of the actual owner's already-verified final span."""
    root, private = span.roots
    if (
        private.payloads
        or private.links
        or any(not stat.S_ISDIR(node.mode) for _name, node in private.native)
    ):
        raise ValueError("layout.forest-namespace: source payload remains parked")
    nodes, links = dict(root.native), dict(root.links)
    payloads = {name: (blob, executable) for name, blob, executable in root.payloads}
    directories, groups, aliases = [], defaultdict(list), []
    for name, node in root.native:
        if not name:
            continue
        if stat.S_ISDIR(node.mode):
            directories.append(name)
        elif stat.S_ISREG(node.mode):
            groups[node.device, node.inode].append(name)
        elif stat.S_ISLNK(node.mode):
            aliases.append(NativeSdkAlias(name, links[name]))
        else:
            raise ValueError("layout.forest-namespace: unsupported final entry")
    files = []
    for names in groups.values():
        representative = min(names)
        commitment = payloads[representative]
        if any(
            nodes[name].links != len(names) or payloads[name] != commitment
            for name in names
        ):
            raise ValueError("layout.forest-namespace: incomplete final hardlink group")
        files.append((representative, *commitment))
        aliases.extend(
            NativeSdkAlias(name, representative, "hardlink")
            for name in names
            if name != representative
        )
    directory_set, file_set = set(directories), {name for name, *_ in files}
    alias_map = {alias.path: alias for alias in aliases}
    resolution = _ResolutionBudget(
        remaining=max(1048576, span.budget.maximum_entries * 128)
    )
    for alias in aliases:
        NativeSdkTree._resolve(
            alias.path, directory_set, file_set, alias_map, resolution
        )
    tree = RetainedCargoInputTreeV2(
        root.root,
        span.budget,
        (),
        tuple(sorted(directories)),
        tuple(sorted(files)),
        tuple(sorted(aliases, key=lambda alias: alias.path)),
        span.maximum_metadata_bytes,
        (
            _physical(nodes[""]),
            tuple((name, _physical(node)) for name, node in root.native if name),
        ),
    )
    # The transaction namespace uses the same stat-only native shape as
    # _native_tree(), including for symlinks. Keep receipt-only native IDs/link
    # text in the actual owner's full span; its closing checks authenticate that
    # span before and after this projection. Logical link text remains in aliases.
    native = tuple(
        (
            name,
            node
            if node.native_identity is None and node.link_target is None
            else replace(node, native_identity=None, link_target=None),
        )
        for name, node in root.native
    )
    return tree, native
