"""Read-only relocation planning from original finite source observations.

A plan is intent plus freshly measured inputs. Application must rebuild this
plan under its own lifecycle lock, match the full identity acknowledgement and
acquire original native reservations; deserializing this body grants nothing.
"""

from __future__ import annotations

import os
import stat
from bisect import bisect_left
from itertools import chain
from pathlib import PurePosixPath

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.retained_layout import _fail
from literate_ai.adapters.retained_layout_partition import (
    _layout_source_identity,
    _require_original,
    capture_retained_layout_source,
    observe_retained_layout_partition,
)
from literate_ai.adapters.retained_project_inputs import _directory_access, _inventory
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_layout import RetainedLayoutDeclaration
from literate_ai.projects import LoadedProject


def _physical(node):
    # Local inode/time identifiers may exceed JSON's exact integer range. They
    # remain lossless decimal strings, never portable ownership capabilities.
    return {
        field: str(getattr(node, field))
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
    }


def _ancestry(root, coordinate):
    result = []
    path = root
    for name in (".", *PurePosixPath(coordinate).parts):
        if name != ".":
            path = path / name
        try:
            require_safe_directory(path, allow_missing=True)
            node = path.lstat()
        except FileNotFoundError:
            break
        if not stat.S_ISDIR(node.st_mode):
            _fail(
                "destination_unsafe",
                "layout destination ancestry is not a direct directory",
            )
        result.append(
            {
                "path": path.relative_to(root).as_posix(),
                "node": {
                    field: str(getattr(node, field))
                    for field in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid")
                },
            }
        )
    return result


def _root_placement_boundary(context, *, reserved_memory_bytes):
    """Refuse unselected existing root members rather than silently owning them.

    The actual original implementation is independently captured completely; only
    that exact owned subtree and actual Git administration may prune this root
    namespace check. Framework exclusion is finite regular-file authority.
    """
    record = _require_original(context)
    root = record["root"]
    implementation = context.layout.declaration.implementation_directory
    if implementation == ".":
        return None
    fee = 0

    def admit(name, node=None):
        nonlocal fee
        fee += 4096 + 64 * len(name.encode())
        if record["retained"] + reserved_memory_bytes + fee > record["maximum"]:
            _fail("metadata_limit", "root placement partition exceeds metadata memory")

    known_files = record["files"]
    for name in record["framework_directory_roles"]:
        admit(name)
    allowed_directories = set(record["framework_directory_roles"])
    for name in chain(known_files, (implementation,)):
        parent = PurePosixPath(name).parent
        while parent.parts:
            coordinate = parent.as_posix()
            if coordinate not in allowed_directories:
                admit(coordinate)
                allowed_directories.add(coordinate)
            parent = parent.parent
    transient_directories = set()
    for name in record["transient_roles"]:
        parent = PurePosixPath(name).parent
        while parent.parts:
            coordinate = parent.as_posix()
            if coordinate not in transient_directories:
                admit(coordinate)
                transient_directories.add(coordinate)
            parent = parent.parent
    rows = []

    def observe(name, node):
        admit(name, node)
        if name in record["transient_roles"] or name in transient_directories:
            return
        # The source container's complete node is joined separately; its
        # descendants are already captured and must not be walked a third time.
        if name == implementation or name == ".git":
            return
        rows.append(
            {
                "path": name,
                "node": (
                    {
                        field: str(getattr(node, field))
                        for field in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid")
                    }
                    if stat.S_ISDIR(node.st_mode)
                    else _physical(node)
                ),
            }
        )

    with _directory_access(root) as access:
        if access is None:
            _fail(
                "native_owner_unavailable",
                "root planning needs original directory handles",
            )
        names = []
        with os.scandir(access.directory(())[0]) as entries:
            for entry in entries:
                admit(entry.name)
                names.append(entry.name)
        roots = {implementation}
        if record["git"] is not None:
            roots.add(".git")
        remaining, directories = _inventory(
            root,
            tuple(sorted(names)),
            max(1, record["maximum"] // 4096),
            allow_internal_symlinks=True,
            access=access,
            observe=observe,
            excluded_roots=frozenset(roots),
            excluded_regular_files=frozenset(known_files),
        )
        if remaining or any(name not in allowed_directories for name in directories):
            _fail(
                "root_partition_collision",
                "unselected existing root members would enter retained source",
            )
    context.require_framework_current(reserved_memory_bytes=reserved_memory_bytes + fee)
    return sorted(rows, key=lambda row: row["path"]), fee


def _plan_from_observation(context, declaration, *, limits, case_sensitive):
    record = _require_original(context)
    layout = context.layout
    root = record["root"]
    if declaration == layout.declaration:
        _fail("layout_unchanged", "relocation requires a different retained layout")
    tree = capture_retained_layout_source(
        context, limits=limits, case_sensitive=case_sensitive
    )
    # Moving source above or below itself is handled as a multi-path partition
    # transaction, never by renaming the repository or a shared ancestor.
    destination = (
        root
        if declaration.implementation_directory == "."
        else root.joinpath(*PurePosixPath(declaration.implementation_directory).parts)
    )
    wrapper = root.joinpath(*PurePosixPath(declaration.wrapper_component).parts)
    if sum(wrapper.is_relative_to(path) for path in record["component_roots"]) != 1:
        _fail(
            "wrapper_ambiguous", "selected wrapper must belong to one Component catalog"
        )
    if wrapper == destination:
        _fail("partition_collision", "retained source and wrapper coordinates collide")
    if wrapper != layout.wrapper and os.path.lexists(wrapper):
        _fail("wrapper_occupied", "selected wrapper destination is already occupied")
    # An existing non-root destination is not adopted or merged. Root geometry
    # instead reserves each exact retained member below its shared root.
    if (
        destination != root
        and destination != layout.implementation
        and os.path.lexists(destination)
    ):
        _fail("destination_occupied", "retained implementation destination is occupied")
    plan_memory = sum(
        8192 + 64 * len(name.encode())
        for name in chain(
            tree.directories,
            (item.path for item in tree.files),
            (item.path for item in tree.aliases),
        )
    )
    # Admit the additional physical rows, path ordering and canonical plan
    # representation BEFORE allocating them alongside the live source graph.
    context.require_framework_current(
        reserved_memory_bytes=tree.index.metadata_memory_bound + plan_memory
    )
    paths = tuple(
        sorted(
            chain(
                tree.directories,
                (item.path for item in tree.files),
                (item.path for item in tree.aliases),
            )
        )
    )

    def framework_descendant(directory):
        if not directory.is_relative_to(root):
            return False
        relative = directory.relative_to(root).as_posix()
        if relative == ".":
            return bool(record["existing_framework_paths"])
        prefix = relative + "/"
        known = record["existing_framework_paths"]
        index = bisect_left(known, prefix)
        return index < len(known) and known[index].startswith(prefix)

    # A presently absent canonical metadata role is still reserved. It cannot
    # become a source leaf merely because no file has been published there yet.
    # This is a finite role check, never a name-based source ignore rule.
    framework_roles = tuple(sorted(record["files"]))

    def reserved_target(target, *, directory):
        relative = target.relative_to(root).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            return True
        if relative in record["files"]:
            return True
        if not directory:
            prefix = relative + "/"
            index = bisect_left(framework_roles, prefix)
            return index < len(framework_roles) and framework_roles[index].startswith(
                prefix
            )
        return False

    # A source directory may share an ancestor with actual framework files.
    # This never admits an occupied leaf or an unrelated foreign destination.
    shared_directories = []
    physical = []
    with _directory_access(layout.implementation) as access:
        for name in paths:
            path = layout.implementation / name
            node = access.metadata(path) if access is not None else path.lstat()
            if node.st_dev != record["root_node"][0]:
                _fail("cross_device", "layout relocation requires one filesystem")
            target = destination / name
            if reserved_target(target, directory=stat.S_ISDIR(node.st_mode)):
                _fail(
                    "partition_collision",
                    "a retained destination collides with a canonical framework role",
                )
            if stat.S_ISDIR(node.st_mode):
                require_safe_directory(target, allow_missing=True)
            if target != path and os.path.lexists(target):
                if stat.S_ISDIR(node.st_mode) and framework_descendant(target):
                    require_safe_directory(target)
                    target_node = target.lstat()
                    shared_directories.append(
                        {
                            "path": target.relative_to(root).as_posix(),
                            "node": {
                                field: str(getattr(target_node, field))
                                for field in (
                                    "st_dev",
                                    "st_ino",
                                    "st_mode",
                                    "st_uid",
                                    "st_gid",
                                )
                            },
                        }
                    )
                else:
                    _fail(
                        "destination_occupied",
                        "a retained destination member is occupied",
                    )
            physical.append({"path": name, "node": _physical(node)})
    alias_names = tuple(item.path for item in tree.aliases if item.kind == "symlink")
    directory_names = set(tree.directories)
    for target in tree.resolve_all(alias_names):
        if target == "." or target in directory_names:
            physical_target = destination if target == "." else destination / target
            if framework_descendant(physical_target):
                _fail(
                    "alias_crosses_partition",
                    "relocated directory alias would expose framework authority",
                )
    ancestry = {
        "source": _ancestry(root, layout.declaration.implementation_directory),
        "destination": _ancestry(root, declaration.implementation_directory),
        "wrapper": _ancestry(root, declaration.wrapper_component),
    }
    for chain_rows in ancestry.values():
        if any(
            int(row["node"]["st_dev"]) != record["root_node"][0] for row in chain_rows
        ):
            _fail("cross_device", "layout destination ancestry crosses a filesystem")
    # Root geometry is never renamed. For an actual non-root implementation,
    # also bind the container's complete physical stamp before any whole-root
    # move can be considered by the transaction compiler.
    implementation_node = (
        None
        if layout.implementation == root
        else _physical(layout.implementation.lstat())
    )
    root_observation = (
        _root_placement_boundary(
            context,
            reserved_memory_bytes=tree.index.metadata_memory_bound + plan_memory,
        )
        if declaration.implementation_directory == "."
        else None
    )
    root_boundary, root_boundary_memory = (
        (None, 0) if root_observation is None else root_observation
    )
    source_identity = _layout_source_identity(
        tree.identity,
        tuple(
            (row["path"], stat.S_IMODE(int(row["node"]["st_mode"]))) for row in physical
        ),
    )
    body = {
        "schema": "literate-ai/retained-layout-relocation-plan@1",
        "project_id": record["project_id"],
        "root": str(root),
        "current_layout_identity": layout.identity.uri,
        "current_declaration": layout.declaration.to_dict(),
        "declaration": declaration.to_dict(),
        "source_tree_identity": tree.identity.uri,
        "source_identity": source_identity.uri,
        "source_inventory": {
            "schema": "literate-ai/retained-layout-source-inventory@1",
            "directories": list(tree.directories),
            "files": [item.to_dict() for item in tree.files],
            "aliases": [item.to_dict() for item in tree.aliases],
        },
        "source_nodes": physical,
        "source_container_node": implementation_node,
        "root_existing_partition": root_boundary,
        "ancestry": ancestry,
        "shared_destination_directories": shared_directories,
        "framework_nodes": [
            {
                "path": name,
                "signature": None if value is None else [str(v) for v in value],
            }
            for name, value in sorted(record["files"].items())
            if name not in record["transient_roles"]
        ],
        "transient_framework_roles": sorted(record["transient_roles"]),
        "case_sensitive": case_sensitive,
        "limits": limits.to_dict(),
        "maximum_metadata_bytes": record["maximum"],
        "requalification_required": True,
    }
    # Re-observe the complete source after the additional mode/inode inventory.
    # A byte change cannot pair a former tree identity with a newer physical
    # reservation. Both graph lifetimes are charged during the closing capture.
    closing_tree = capture_retained_layout_source(
        context,
        limits=limits,
        case_sensitive=case_sensitive,
        reserved_memory_bytes=tree.index.metadata_memory_bound
        + plan_memory
        + root_boundary_memory,
    )
    if closing_tree.identity != tree.identity:
        _fail("source_changed", "retained source changed while planning relocation")
    with _directory_access(layout.implementation) as access:
        for row in physical:
            path = layout.implementation / row["path"]
            node = access.metadata(path) if access is not None else path.lstat()
            if _physical(node) != row["node"]:
                _fail(
                    "source_changed",
                    "retained source modes or physical custody changed",
                )
    for row in shared_directories:
        path = root / row["path"]
        require_safe_directory(path)
        node = path.lstat()
        actual = {
            field: str(getattr(node, field))
            for field in ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid")
        }
        if actual != row["node"]:
            _fail(
                "destination_changed",
                "shared destination directory changed while planning",
            )
    if ancestry != {
        "source": _ancestry(root, layout.declaration.implementation_directory),
        "destination": _ancestry(root, declaration.implementation_directory),
        "wrapper": _ancestry(root, declaration.wrapper_component),
    }:
        _fail("ancestry_changed", "layout physical ancestry changed while planning")
    if declaration.implementation_directory == ".":
        closing_boundary = _root_placement_boundary(
            context,
            reserved_memory_bytes=(
                tree.index.metadata_memory_bound
                + closing_tree.index.metadata_memory_bound
                + plan_memory
                + root_boundary_memory
            ),
        )
        if closing_boundary is not None and root_boundary != closing_boundary[0]:
            _fail(
                "root_partition_changed",
                "root ownership partition changed during planning",
            )
        del closing_boundary
    if (
        implementation_node is not None
        and _physical(layout.implementation.lstat()) != implementation_node
    ):
        _fail("source_changed", "implementation container changed while planning")
    context.require_framework_current(
        reserved_memory_bytes=(
            tree.index.metadata_memory_bound
            + closing_tree.index.metadata_memory_bound
            + plan_memory
            + root_boundary_memory
        )
    )
    return body


def plan_retained_layout_relocation(
    project,
    declaration,
    *,
    limits,
    case_sensitive=False,
    maximum_metadata_bytes=1024**3,
):
    """Produce a full fresh plan without source, cache, CAS or journal writes."""
    if (
        not isinstance(project, LoadedProject)
        or type(declaration) is not RetainedLayoutDeclaration
    ):
        raise TypeError("retained.layout.typed-project-and-declaration-required")
    with observe_retained_layout_partition(
        project, maximum_metadata_bytes=maximum_metadata_bytes
    ) as context:
        body = _plan_from_observation(
            context, declaration, limits=limits, case_sensitive=case_sensitive
        )
    return {"plan": body, "plan_identity": canonical_identity(body).uri}
