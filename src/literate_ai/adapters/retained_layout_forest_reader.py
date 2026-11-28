"""Pure simultaneous reader transfers; data alone grants no reader mutation.

The source movement participant must fund and seal these snapshots before native
work, then install the result only from its actual completed native owner.
"""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass, replace


def _fail(message):
    raise ValueError("layout.forest-reader: " + message)


def _beneath(name, parent):
    return name == parent or name.startswith(parent + "/")


def _signature(node):
    return (
        node.device,
        node.inode,
        node.mode,
        node.size,
        node.modified_ns,
        node.changed_ns,
    )


def _presence(node):
    basic = (node.device, node.inode, node.mode, node.uid, node.gid)
    if stat.S_ISDIR(node.mode):
        return basic
    return (
        *basic,
        node.size,
        node.modified_ns,
        node.changed_ns,
        node.links,
    )


@dataclass(frozen=True, slots=True)
class _Transfer:
    program: object
    cache: tuple
    ancestry: tuple
    lineages: tuple
    presences: tuple
    fixed_absences: tuple

    def payload_path(self, path, *, absent, _projection=None):
        root = self.program.span.roots[0].root
        if not path.is_relative_to(root):
            return path
        name = path.relative_to(root).as_posix()
        projection = (
            dict(self.program.graph.projection) if _projection is None else _projection
        )
        if not absent:
            return root / projection.get(name, name)
        if path in self.fixed_absences:
            return path
        # An absent observation has no inode to transfer. Its logical parent
        # follows source projection, except exact canonical producer endpoints.
        parent = path.parent
        while parent.is_relative_to(root):
            relative = "." if parent == root else parent.relative_to(root).as_posix()
            if relative in projection:
                return root / projection[relative] / path.relative_to(parent)
            if parent == root:
                break
            parent = parent.parent
        return path

    def directory_path(self, path):
        root = self.program.span.roots[0].root
        if not path.is_relative_to(root):
            return path
        name = path.relative_to(root).as_posix()
        for action in self.program.actions:
            if action.kind == "retain" and name == action.source:
                return self.program.private_root / action.destination
        for source, target in self.program.graph.carriers:
            if _beneath(name, source):
                return root / (target + name[len(source) :])
        return path


def _plan_transfer(program, cache, ancestry, lineages, presences, *, fixed_absences=()):
    """Funded original snapshots and pre-effect occupancy checks, with no I/O."""
    transfer = _Transfer(
        program,
        tuple(cache),
        tuple(ancestry),
        tuple(lineages),
        tuple(presences),
        tuple(sorted(fixed_absences)),
    )
    root = program.span.roots[0].root
    retained = set(program.graph.retain_directories)
    occupied = set(program.graph.create_directories)
    for name, _node in program.span.roots[0].native:
        if name in retained:
            continue
        target = name
        for source, destination in program.graph.carriers:
            if _beneath(name, source):
                target = destination + name[len(source) :]
                break
        occupied.add(target)
    seen = {}
    projection = dict(program.graph.projection)
    for path, item in transfer.cache:
        if item.path != path:
            _fail("original observation path differs")
        target = transfer.payload_path(
            path, absent=item.content is None, _projection=projection
        )
        if item.content is None and target.is_relative_to(root):
            name = target.relative_to(root).as_posix()
            if name in occupied:
                _fail("projected source would occupy a retained absence")
        if target in seen and (item.content is not None or seen[target] is not None):
            _fail("projected reader payload observations collide")
        seen[target] = item.content
    for path, value in transfer.presences:
        target = (
            transfer.directory_path(path)
            if value is not None and stat.S_ISDIR(value[2])
            else transfer.payload_path(
                path, absent=value is None, _projection=projection
            )
        )
        if value is None and target.is_relative_to(root):
            if target.relative_to(root).as_posix() in occupied:
                _fail("projected source would occupy a retained presence absence")
    return transfer


def _location(span, path):
    for root in span.roots:
        if path.is_relative_to(root.root):
            name = path.relative_to(root.root).as_posix()
            return root, "" if name == "." else name
    return None, None


def _ancestry(span, path, *, directory=False, nodes=None):
    root, _name = _location(span, path)
    if root is None:
        _fail("transferred observation has no verified namespace")
    nodes = dict(root.native) if nodes is None else nodes
    anchor = path if directory else path.parent
    while anchor != root.root:
        name = anchor.relative_to(root.root).as_posix()
        if name in nodes:
            if not stat.S_ISDIR(nodes[name].mode):
                _fail("transferred ancestry is blocked by a file")
            break
        if directory:
            _fail("transferred original directory is unavailable")
        anchor = anchor.parent
    parts = anchor.relative_to(root.root).parts
    result, current = root.lineage, root.root
    for part in parts:
        current /= part
        node = nodes[current.relative_to(root.root).as_posix()]
        if not stat.S_ISDIR(node.mode):
            _fail("transferred ancestry is not a directory")
        result = (
            *result,
            (str(current), node.device, node.inode, node.mode, node.uid, node.gid),
        )
    return anchor, result


def _project_transfer(transfer, span):
    """Receipt-span data for the creating participant to authenticate/install."""
    cache, ancestry, lineages, presences = {}, {}, {}, {}
    old_ancestry = dict(transfer.ancestry)
    projection = dict(transfer.program.graph.projection)
    native_maps = {root.root: dict(root.native) for root in span.roots}
    payload_maps = {
        root.root: {n: (blob, mode) for n, blob, mode in root.payloads}
        for root in span.roots
    }
    for path, item in transfer.cache:
        target = transfer.payload_path(
            path, absent=item.content is None, _projection=projection
        )
        root, name = _location(span, target)
        if root is None:
            cache[target], ancestry[target] = item, old_ancestry[path]
            continue
        node = native_maps[root.root].get(name)
        if item.content is None:
            if node is not None:
                _fail("transferred absent payload is occupied")
            replacement = replace(item, path=target)
        else:
            commitments = payload_maps[root.root]
            commitment = commitments.get(name)
            if (
                node is None
                or not stat.S_ISREG(node.mode)
                or item.signature[:2] != (node.device, node.inode)
                or commitment is None
                or (hashlib.sha256(item.content).hexdigest(), len(item.content))
                != (commitment[0].digest, commitment[0].size)
                or bool(node.mode & 0o111) != commitment[1]
            ):
                _fail("transferred payload lacks exact original native/byte custody")
            replacement = replace(item, path=target, signature=_signature(node))
        if target == path and replacement == item:
            # Fixed canonical selectors retain their actual observation object.
            # All receipt-derived native/byte checks above still apply.
            replacement = item
        if target in cache and cache[target] != replacement:
            _fail("transferred payload observations disagree")
        cache[target], ancestry[target] = (
            replacement,
            _ancestry(span, target, nodes=native_maps[root.root]),
        )
    for path, value in transfer.lineages:
        target = transfer.directory_path(path)
        root, _name = _location(span, target)
        projected = (
            value
            if root is None
            else _ancestry(span, target, directory=True, nodes=native_maps[root.root])[
                1
            ]
        )
        if projected[-1][1:] != value[-1][1:]:
            _fail("original directory identity changed during transfer")
        if target in lineages and lineages[target] != projected:
            _fail("transferred original directory observations collide")
        lineages[target] = projected
    for path, value in transfer.presences:
        target = (
            transfer.directory_path(path)
            if value is not None and stat.S_ISDIR(value[2])
            else transfer.payload_path(
                path, absent=value is None, _projection=projection
            )
        )
        root, name = _location(span, target)
        if root is None:
            projected = value
        else:
            node = native_maps[root.root].get(name)
            if value is None:
                if node is not None:
                    _fail("transferred absent presence is occupied")
                projected = None
            else:
                if node is None or value[:2] != (node.device, node.inode):
                    _fail("transferred presence lost original native custody")
                projected = _presence(node)
        if target in presences and presences[target] != projected:
            _fail("transferred presence observations collide")
        presences[target] = projected
    return (
        tuple(cache.items()),
        tuple(ancestry.items()),
        tuple(lineages.items()),
        tuple(presences.items()),
    )
