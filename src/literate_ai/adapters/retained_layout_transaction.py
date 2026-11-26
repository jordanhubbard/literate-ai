"""Compile finite relocation operations from a fresh original source context.

Programs are descriptions, not execution grants or native owners. The public
service must compile its own program under the lifecycle lock, join its complete
identity acknowledgement and host authority, and retain original reservations.
No saved program is accepted by the journal issuer as recovery ownership.
"""

from __future__ import annotations

import stat
from bisect import bisect_left
from pathlib import PurePosixPath

from literate_ai.adapters.retained_layout import _fail
from literate_ai.adapters.retained_layout_partition import _require_original
from literate_ai.adapters.retained_layout_planning import _plan_from_observation
from literate_ai.adapters.retained_project_inputs import _directory_access
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_layout import RetainedLayoutDeclaration


def _coordinate(base, relative):
    return (PurePosixPath(base) / relative).as_posix()


def _has_descendant(paths, coordinate):
    prefix = coordinate + "/"
    selected = bisect_left(paths, prefix)
    return selected < len(paths) and paths[selected].startswith(prefix)


def _stamp(row):
    return tuple(
        int(row[field])
        for field in (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
    )


def _compile_source_operations(context, plan):
    record = _require_original(context)
    root = record["root"]
    current = RetainedLayoutDeclaration.from_dict(plan["current_declaration"])
    proposed = RetainedLayoutDeclaration.from_dict(plan["declaration"])
    if current != context.layout.declaration:
        _fail("layout_changed", "transaction source differs from its original context")
    metadata_memory = 4096 * (
        len(plan["source_nodes"]) + len(plan["root_existing_partition"] or ())
    ) + sum(128 * len(row["path"].encode()) for row in plan["source_nodes"])
    # The full plan remains live while this additional operation/index graph is
    # constructed. Its own physical-row fee is admitted conservatively again.
    context.require_framework_current(reserved_memory_bytes=3 * metadata_memory)
    nodes = {row["path"]: row["node"] for row in plan["source_nodes"]}
    directories = {}
    moves = []
    old_directories = {}
    for name, node in nodes.items():
        mode = int(node["st_mode"])
        if mode & 0o7000:
            _fail(
                "source_mode_unsupported",
                "special source modes cannot be silently changed",
            )
        source = _coordinate(current.implementation_directory, name)
        destination = _coordinate(proposed.implementation_directory, name)
        if stat.S_ISDIR(mode):
            old_directories[source] = _stamp(node)
            directories[destination] = stat.S_IMODE(mode)
        elif source != destination:
            moves.append(
                {
                    "source": source,
                    "destination": destination,
                    "source_node": [str(value) for value in _stamp(node)],
                }
            )
    if current.implementation_directory != ".":
        old_directories[current.implementation_directory] = _stamp(
            plan["source_container_node"]
        )
    if proposed.implementation_directory != ".":
        # Container mode is source metadata too. Root itself is never renamed
        # or chmodded; a genuinely new subdirectory receives its ordinary mode.
        old_root = root / current.implementation_directory
        mode = stat.S_IMODE(old_root.lstat().st_mode)
        if mode & 0o7000:
            _fail(
                "source_mode_unsupported", "implementation container has a special mode"
            )
        directories[proposed.implementation_directory] = mode
    leaves = tuple(sorted(row["destination"] for row in moves))
    for name in (*tuple(directories), *leaves):
        parent = PurePosixPath(name).parent
        while parent.parts:
            directories.setdefault(parent.as_posix(), 0o755)
            parent = parent.parent
    creations = []
    existing = []
    with _directory_access(root) as access:
        if access is None:
            _fail(
                "native_owner_unavailable",
                "layout compilation requires original handles",
            )
        for name in sorted(
            directories, key=lambda value: (len(PurePosixPath(value).parts), value)
        ):
            try:
                node = access.metadata(root / name)
            except FileNotFoundError:
                creations.append({"path": name, "mode": directories[name]})
                continue
            if not stat.S_ISDIR(node.st_mode) or node.st_dev != record["root_node"][0]:
                _fail(
                    "destination_unsafe",
                    "planned directory is redirected or on another filesystem",
                )
            existing.append(
                {
                    "path": name,
                    "node": [
                        str(getattr(node, field))
                        for field in (
                            "st_dev",
                            "st_ino",
                            "st_mode",
                            "st_uid",
                            "st_gid",
                        )
                    ],
                }
            )
    final_directories = tuple(sorted(directories))
    framework_paths = tuple(sorted(record["files"]))
    removals = []
    for name in sorted(
        old_directories, key=lambda value: (-len(PurePosixPath(value).parts), value)
    ):
        if (
            name in directories
            or _has_descendant(final_directories, name)
            or _has_descendant(framework_paths, name)
        ):
            continue
        removals.append(
            {
                "path": name,
                "source_node": [str(value) for value in old_directories[name]],
            }
        )
    # Aliases retain their exact original raw targets: no symlink shim or target
    # rewrite can substitute for the canonical tree's internal topology checks.
    return {
        "schema": "literate-ai/retained-layout-source-operations@1",
        "create_directories": creations,
        "existing_directories": existing,
        "move_leaves": sorted(moves, key=lambda value: value["source"]),
        "remove_empty_source_directories": removals,
        "repository_root_move": False,
        "rewrite_alias_targets": False,
    }


def _compile_relocation_transaction(context, declaration, *, limits, case_sensitive):
    """Compile source geometry only from this original fresh observation.

    Metadata derivation must be joined into the full transaction before this is
    exposed by a public plan/apply handler. This private intermediate is never a
    stand-alone apply plan, execution acknowledgement or completed relocation.
    """
    plan = _plan_from_observation(
        context, declaration, limits=limits, case_sensitive=case_sensitive
    )
    program = _compile_source_operations(context, plan)
    context.require_framework_current()
    return {
        "source_plan": plan,
        "source_operations": program,
        "intermediate_identity": canonical_identity(
            {"plan": plan, "operations": program}
        ).uri,
    }
