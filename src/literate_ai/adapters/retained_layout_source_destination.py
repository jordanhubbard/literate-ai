"""Original destination data, never a future-parent or movement capability."""

from __future__ import annotations

import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.paths import canonical_relative_posix_path


@dataclass(frozen=True, slots=True)
class _OriginalDestinationState:
    coordinate: str
    root: Path
    prefixes: tuple
    anchor: Path
    anchor_lineage: tuple
    anchor_node: object
    parent_node: object
    target_node: object


def _allowance(census, coordinate):
    count = len(census.tree.directories) + len(census.tree.files)
    count += len(census.tree.aliases) + len(Path(coordinate).parts) + 1
    size = sum(len(name.encode()) for name in census.tree.directories)
    size += sum(len(name.encode()) for name, _, _ in census.tree.files)
    size += sum(len(alias.path.encode()) for alias in census.tree.aliases)
    size += count * len(str(census.tree.root / coordinate).encode())
    return 64 + 16 * count, 65536 + 2048 * count + 64 * size


def _from_original(census, native, coordinate):
    """Pure reconstruction; callers fund construction before entering."""
    if coordinate != ".":
        canonical_relative_posix_path(coordinate, label="source destination")
    nodes = dict(native)
    root = census.tree.root
    if coordinate == ".":
        return _OriginalDestinationState(
            coordinate,
            root,
            ((".", nodes[""]),),
            root,
            census._lineage,
            nodes[""],
            None,
            nodes[""],
        )
    spellings = {unicodedata.normalize("NFC", name.casefold()): name for name in nodes}
    prefixes = []
    anchor, anchor_node = root, nodes[""]
    lineage = list(census._lineage)
    parts = Path(coordinate).parts
    missing = False
    for index in range(len(parts)):
        name = Path(*parts[: index + 1]).as_posix()
        key = unicodedata.normalize("NFC", name.casefold())
        if key in spellings and spellings[key] != name:
            raise ValueError(
                "layout.destination: destination exists or aliases another entry "
                "(portable destination prefix alias)"
            )
        node = nodes.get(name)
        if node is not None and (missing or not stat.S_ISDIR(node.mode)):
            raise ValueError("layout.destination: occupied or redirected prefix")
        prefixes.append((name, node))
        if node is None:
            missing = True
        elif index < len(parts) - 1:
            anchor, anchor_node = root / name, node
            lineage.append(
                (
                    str(anchor),
                    node.device,
                    node.inode,
                    node.mode,
                    node.uid,
                    node.gid,
                )
            )
    parent_name = Path(coordinate).parent.as_posix()
    parent = nodes.get("" if parent_name == "." else parent_name)
    # Root uses the native roster's empty coordinate, not a guessed parent.
    if len(parts) == 1:
        parent = nodes[""]
    return _OriginalDestinationState(
        coordinate,
        root,
        tuple(prefixes),
        anchor,
        tuple(lineage),
        anchor_node,
        parent,
        nodes.get(coordinate),
    )


def _require_current(state, maximum_entries):
    """Known native facts and first missing prefix; no payload reads."""
    from .exclusive_entry import layout_entry_node
    from .retained_layout_partition import _lineage
    from .retained_layout_transaction import _absence

    if _lineage(state.anchor) != state.anchor_lineage:
        raise ValueError("layout.destination: original anchor ancestry changed")
    for name, expected in state.prefixes:
        path = state.root if name == "." else state.root / name
        if expected is None:
            _absence(path, maximum_entries)
            break
        if layout_entry_node(path) != expected:
            raise ValueError("layout.destination: original prefix native facts changed")
    if layout_entry_node(state.anchor) != state.anchor_node:
        raise ValueError("layout.destination: original anchor membership changed")
