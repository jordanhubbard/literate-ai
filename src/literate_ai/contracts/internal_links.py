"""Closed POSIX link namespace validation shared by retained and source custody."""

from __future__ import annotations

import posixpath
from collections.abc import Mapping, Set


def validate_internal_symlink_closure(
    targets: Mapping[str, str], nodes: Set[str], directories: Set[str]
) -> None:
    """Validate raw target text without consulting or following the filesystem.

    Callers own complete, normalized, non-overlapping node inventories. Directory
    aliases are finite input nodes; only nonterminating link chains are cycles.
    """
    for target in targets.values():
        if (
            not isinstance(target, str)
            or not target
            or target.startswith("/")
            or any(c in target for c in ("\\", ":", "\x00"))
            or any(ord(c) < 32 for c in target)
            or len(target.encode("utf-8")) > 4096
        ):
            raise ValueError("Retained symlink requires bounded relative target text")
    links = {
        name: posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
        for name, target in targets.items()
    }
    if any(target not in nodes for target in links.values()):
        raise ValueError(
            "Retained symlink target is outside the declared input closure"
        )
    for name, target in targets.items():
        cursor = name.split("/")[:-1]
        parts = target.split("/")
        for index, part in enumerate(parts):
            if part in ("", "."):
                continue
            if part == "..":
                if not cursor:
                    raise ValueError(
                        "Retained symlink traverses outside the input tree"
                    )
                cursor.pop()
            else:
                cursor.append(part)
                if index < len(parts) - 1 and "/".join(cursor) not in directories:
                    raise ValueError(
                        "Retained symlink traverses a link or non-directory"
                    )
    resolved: set[str] = set()
    for start in links:
        current = start
        chain: set[str] = set()
        while current in links and current not in resolved:
            if current in chain:
                raise ValueError("Retained symlink target cycle")
            chain.add(current)
            current = links[current]
        resolved.update(chain)
