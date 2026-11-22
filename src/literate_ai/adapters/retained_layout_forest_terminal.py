"""Receipt-derived parking facts and pure Git footprint separation.

A frozen description grants no source/phase/FD rights. The actual terminal
participant must independently enroll its snapshot before resource teardown.
Read-only verification opens fresh descriptors for the original known paths;
it never calls an ended native owner or borrows that owner's closed descriptor.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass, fields, replace
from pathlib import Path

from literate_ai.contracts.identity import canonical_json_bytes

from .exclusive_entry import _from_stat, layout_entry_node
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_partition import _lineage


def _fail(message):
    raise ValueError("layout.forest-terminal: " + message)


@dataclass(frozen=True, slots=True)
class _Parking:
    owner: object
    program: object
    program_raw: bytes
    journal: object
    owner_span: object
    private_span: object
    registration: tuple
    descriptor: int
    pid: int
    thread: int
    root: Path
    root_node: object
    known: tuple


def _seal(value):
    return (
        value,
        tuple((f.name, getattr(value, f.name)) for f in fields(value)),
        canonical_json_bytes(
            _custody_wire((value.private_span, value.root_node, value.known))
        ),
    )


def _require(value, seal, *, ended=None):
    """Pure original identity checks; no borrowed descriptors or callbacks."""
    from .retained_layout_forest_native import _LIVE

    if (
        type(value) is not _Parking
        or seal[0] is not value
        or any(getattr(value, name) is not old for name, old in seal[1])
        or canonical_json_bytes(
            _custody_wire((value.private_span, value.root_node, value.known))
        )
        != seal[2]
    ):
        _fail("original parking snapshot changed")
    owner = value.owner
    if (
        owner.program is not value.program
        or owner.journal is not value.journal
        or owner._span is not value.owner_span
        or owner._raw is not value.program_raw
        or owner._descriptor != value.descriptor
        or type(owner._descriptor) is not int
        or (owner._pid, owner._thread) != (value.pid, value.thread)
        or owner._failed is not False
        or owner._attempted is not True
        or canonical_json_bytes(value.program.document) != value.program_raw
    ):
        _fail("original parking owner/program binding changed")
    active = owner._active
    if active is True:
        if ended is True or _LIVE.get(owner) is not value.registration:
            _fail("actual native parking teardown required")
    elif active is False:
        if ended is False or owner in _LIVE:
            _fail("original native parking lifetime is inconsistent")
    else:
        _fail("original parking lifetime changed")


def _freeze(owner):
    from .retained_layout_forest_native import _LIVE, _PROGRESS, _NativeForest

    if type(owner) is not _NativeForest:
        _fail("actual completed live native owner required")
    owner.require_private_current()
    schedule, cursor, pending = _PROGRESS[owner]
    if cursor != len(schedule) or pending is not None or not owner._attempted:
        _fail("actual completed native parking schedule required")
    registration = _LIVE[owner]
    private = owner._span.roots[1]
    expected = {
        "",
        *(a.destination for a in owner.program.actions if a.kind == "retain"),
    }
    if (
        private.payloads
        or private.links
        or {name for name, _ in private.native} != expected
        or any(
            not stat.S_ISDIR(node.mode) or "/" in name for name, node in private.native
        )
    ):
        _fail(
            "only exact retained empty original containers may reach terminal parking"
        )
    nodes = dict(private.native)
    value = _Parking(
        owner,
        owner.program,
        owner._raw,
        owner.journal,
        owner._span,
        replace(owner._span, roots=(private,)),
        registration,
        owner._descriptor,
        owner._pid,
        owner._thread,
        private.root,
        nodes[""],
        tuple((name, (node, None)) for name, node in private.native if name),
    )
    seal = _seal(value)
    owner.require_private_current()
    _require(value, seal, ended=False)
    return value, seal


def _verify(value, seal, *, ended=True):
    """Bounded read-only membership and native facts after payload work."""
    _require(value, seal, ended=ended)
    root = value.private_span.roots[0]
    if _lineage(value.root) != root.lineage:
        _fail("original parking ancestry changed")
    expected = dict(value.known)
    with _pinned_directory(value.root) as (descriptor, guard):
        if _from_stat(os.fstat(descriptor)) != value.root_node:
            _fail("original parking root changed")
        names = set()
        with os.scandir(descriptor) as entries:
            for entry in entries:
                if entry.name not in expected or entry.name in names:
                    _fail("unknown terminal parking entry")
                names.add(entry.name)
        if names != expected.keys():
            _fail("original parking membership changed")
        for name, (node, _content) in value.known:
            fd = os.open(
                name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            try:
                if _from_stat(os.fstat(fd)) != node:
                    _fail("retained original container changed")
                with os.scandir(fd) as children:
                    if next(children, None) is not None:
                        _fail("retained original container is no longer empty")
                if (
                    _from_stat(os.fstat(fd)) != node
                    or layout_entry_node(value.root / name) != node
                ):
                    _fail("retained original container changed after membership scan")
            finally:
                os.close(fd)
        # Membership reads can run callbacks/native activity affecting an
        # earlier container. Close the complete observed roster only after
        # every scan, without interleaving another dependent traversal.
        for name, (node, _content) in value.known:
            if layout_entry_node(value.root / name) != node:
                _fail("retained original container changed during final closure")
        guard()
        if _lineage(value.root) != root.lineage:
            _fail("original parking ancestry changed during final closure")
        if (
            _from_stat(os.fstat(descriptor)) != value.root_node
            or layout_entry_node(value.root) != value.root_node
        ):
            _fail("original parking root changed after native closure")
    _require(value, seal, ended=ended)


def _git_footprints(program, native, protected, admin_lineages):
    """Pure checks of actual resulting footprints, not destination-root exclusion."""
    root = program.span.roots[0].root
    nodes = dict(native)
    names = {target for _source, target in program.graph.carriers} | set(
        program.graph.create_directories
    )
    root_ancestors = {row[1:3] for row in program.span.roots[0].lineage}
    for name in names:
        path = root / name
        if any(
            path.is_relative_to(admin) or admin.is_relative_to(path)
            for admin in protected
        ):
            _fail("source effect footprint overlaps exact Git administration")
        node = nodes.get(name)
        if node is None:
            _fail("actual source effect footprint disappeared")
        ancestors = set(root_ancestors)
        relative = Path()
        for part in Path(name).parent.parts:
            relative /= part
            parent = nodes.get(relative.as_posix())
            if parent is None or not stat.S_ISDIR(parent.mode):
                _fail("actual footprint parent is unavailable")
            ancestors.add((parent.device, parent.inode))
        if stat.S_ISDIR(node.mode):
            ancestors.add((node.device, node.inode))
        for lineage in admin_lineages:
            if lineage[-1][1:3] in ancestors or (
                stat.S_ISDIR(node.mode)
                and (node.device, node.inode) in {row[1:3] for row in lineage}
            ):
                _fail("source effect footprint physically overlaps Git administration")
