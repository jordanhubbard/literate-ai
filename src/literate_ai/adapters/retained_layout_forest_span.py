"""Exact runtime source spans, including temporarily dangling parked aliases.

These immutable descriptions grant no source, control or movement authority.
The eventual movement owner must derive every successor from its actual native
receipts and retain original logical alias proofs. This checker never follows
links and does not relax the SDK tree reader's complete-alias contract.
"""

from __future__ import annotations

import os
import stat
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from .exclusive_entry import LayoutEntryNode, _from_stat, layout_entry_node
from .retained_layout_partition import _lineage
from .retained_project_inputs import _directory_access, _inventory, _link_bytes, _stream

_NATIVE_PAYLOAD_CHUNK = 64 * 1024


def _fail(message):
    raise ValueError("layout.forest-span: " + message)


@dataclass(frozen=True, slots=True)
class _SpanRoot:
    root: Path
    lineage: tuple
    native: tuple
    payloads: tuple
    links: tuple = ()


@dataclass(frozen=True, slots=True)
class _ForestSpan:
    roots: tuple
    budget: RetainedCargoInputBudget
    maximum_metadata_bytes: int


def _from_namespace(tree, native, lineage):
    """Pure data construction after the caller reserves the retained view."""
    if tree.exclusions:
        _fail("complete namespace without exclusions required")
    payloads = {name: (blob, executable) for name, blob, executable in tree.files}
    aliases = {alias.path: alias for alias in tree.aliases}
    for alias in tree.aliases:
        if alias.kind != "hardlink":
            continue
        target = alias.target
        seen = {alias.path}
        while target not in payloads:
            if target in seen or target not in aliases:
                _fail("original hardlink payload is unavailable")
            seen.add(target)
            other = aliases[target]
            if other.kind != "hardlink":
                _fail("hardlink cannot borrow a symbolic payload")
            target = other.target
        payloads[alias.path] = payloads[target]
    return _SpanRoot(
        tree.root,
        lineage,
        native,
        tuple((name, *payloads[name]) for name in sorted(payloads)),
        tuple(
            (alias.path, alias.target)
            for alias in tree.aliases
            if alias.kind == "symlink"
        ),
    )


def _original_span(preparation):
    """Read-only data from the actual original forest participant and budget."""
    from .retained_layout_source_namespace import _current_view
    from .retained_layout_source_namespace import _record as namespace_record
    from .retained_layout_source_preparation import _state
    from .retained_layout_source_roles import _require_plan

    original = _state(preparation)
    plan = original.plan
    if plan.source_forest is None:
        _fail("actual original forest preparation required")
    _require_plan(plan)
    from .retained_layout_source_namespace import _PREPARATIONS

    namespace = namespace_record(_PREPARATIONS[preparation], reading=True)
    tree, native = _current_view(preparation)
    count = len(native) + len(tree.aliases)
    size = sum(len(name.encode()) for name, _ in native)
    original.ledger.charge_records(
        128 + 24 * count,
        65536
        + 4096 * count
        + 128 * size
        + 128 * sum(len(str(row[0]).encode()) for row in namespace.census._lineage),
    )
    root = _from_namespace(tree, native, namespace.census._lineage)
    return _ForestSpan((root,), original.ledger.budget, original.ledger.metadata)


def _shape(span):
    """Bound the complete retained input before inventories and stream buffers."""
    if (
        type(span) is not _ForestSpan
        or type(span.budget) is not RetainedCargoInputBudget
        or type(span.roots) is not tuple
        or not span.roots
        or type(span.maximum_metadata_bytes) is not int
        or span.maximum_metadata_bytes < 65536
    ):
        _fail("finite typed runtime span required")
    if any(
        type(getattr(span.budget, name)) is not int
        for name in (
            "maximum_files",
            "maximum_entries",
            "maximum_file_bytes",
            "maximum_total_bytes",
        )
    ):
        _fail("plain finite policy values required")
    count = size = 0
    roots = set()
    identities = []
    for root in span.roots:
        if (
            type(root) is not _SpanRoot
            or type(root.root) is not type(Path())
            or not root.root.is_absolute()
            or ".." in root.root.parts
            or type(root.native) is not tuple
            or not root.native
            or type(root.payloads) is not tuple
            or type(root.links) is not tuple
            or type(root.lineage) is not tuple
            or len(root.lineage) != len(root.root.parts)
        ):
            _fail("plain complete root description required")
        if any(
            type(row) is not tuple
            or len(row) != 2
            or type(row[0]) is not str
            or type(row[1]) is not LayoutEntryNode
            for row in root.native
        ) or any(
            type(row) is not tuple
            or len(row) != 6
            or type(row[0]) is not str
            or any(type(value) is not int for value in row[1:])
            for row in root.lineage
        ):
            _fail("plain native and ancestry rows required")
        if any(
            type(row) is not tuple
            or len(row) != 3
            or type(row[0]) is not str
            or type(row[1]) is not BlobRef
            or type(row[2]) is not bool
            for row in root.payloads
        ) or any(
            type(row) is not tuple
            or len(row) != 2
            or type(row[0]) is not str
            or type(row[1]) is not str
            for row in root.links
        ):
            _fail("plain payload and symbolic rows required")
        if any(
            root.root.is_relative_to(other) or other.is_relative_to(root.root)
            for other in roots
        ):
            _fail("runtime roots must be disjoint")
        roots.add(root.root)
        count += len(root.native)
        if (
            count > span.budget.maximum_entries
            or len(root.payloads) > len(root.native)
            or len(root.links) > len(root.native)
        ):
            _fail("runtime span exceeds original entry policy")
        size += 65536 + 4096 * len(root.native)
        # Four bytes per character bounds UTF-8 without first allocating an
        # untrusted encoded path. These are retained-view metadata ceilings.
        size += 512 * sum(len(name) for name, _ in root.native)
        size += 512 * sum(len(str(row[0])) for row in root.lineage)
        if count > span.budget.maximum_entries or size > span.maximum_metadata_bytes:
            _fail("runtime span exceeds original metadata or entry policy")
        names = tuple(name for name, _ in root.native)
        if names[0] != "" or len(set(names)) != len(names):
            _fail("exact complete native root roster required")
        for name in names[1:]:
            canonical_relative_posix_path(name, label="runtime entry")
        nodes = dict(root.native)
        if any(type(node) is not LayoutEntryNode for node in nodes.values()):
            _fail("plain original native observations required")
        if not stat.S_ISDIR(nodes[""].mode):
            _fail("runtime root is not a directory")
        root_node = nodes[""]
        if root.lineage[-1] != (
            str(root.root),
            root_node.device,
            root_node.inode,
            root_node.mode,
            root_node.uid,
            root_node.gid,
        ):
            _fail("runtime root and ancestry describe different native nodes")
        identity = root_node.device, root_node.inode
        ancestors = {row[1:3] for row in root.lineage}
        if any(
            identity in before or previous in ancestors
            for previous, before in identities
        ):
            _fail("runtime roots physically overlap")
        identities.append((identity, ancestors))
        payloads = {}
        for name, blob, executable in root.payloads:
            if (
                name not in nodes
                or not stat.S_ISREG(nodes[name].mode)
                or type(blob) is not BlobRef
                or type(executable) is not bool
                or name in payloads
                or blob.size != nodes[name].size
            ):
                _fail("exact regular payload description required")
            payloads[name] = (blob, executable)
        if set(payloads) != {
            name for name, node in nodes.items() if stat.S_ISREG(node.mode)
        }:
            _fail("every regular entry needs its original payload commitment")
        links = dict(root.links)
        if len(links) != len(root.links) or set(links) != {
            name for name, node in nodes.items() if stat.S_ISLNK(node.mode)
        }:
            _fail("every symbolic entry needs its original text commitment")
        for target in links.values():
            if (
                type(target) is not str
                or len(target) > 4096
                or len(target.encode()) > min(4096, span.budget.maximum_file_bytes)
            ):
                _fail("bounded original symbolic text required")
        for node in nodes.values():
            if not (
                stat.S_ISDIR(node.mode)
                or stat.S_ISREG(node.mode)
                or stat.S_ISLNK(node.mode)
            ):
                _fail("unsupported runtime entry type")


def _require_current(span, *, _after_payload=None):
    """Verify raw names/bytes/link text, then close every known native fact.

    A valid span proves only these observations, never permission to advance a
    transaction. Original referent/ownership proofs belong to the movement owner.
    """
    _shape(span)
    count, payload_bytes, files = 0, 0, 0
    groups = {}
    with ExitStack() as stack:
        opened = []
        for root in span.roots:
            if _lineage(root.root) != root.lineage:
                _fail("runtime root ancestry changed")
            access = stack.enter_context(_directory_access(root.root))
            nodes = dict(root.native)
            observed = set()

            def observe(name, metadata, *, nodes=nodes, observed=observed):
                nonlocal count
                count += 1
                if count > span.budget.maximum_entries:
                    _fail("runtime membership exceeds original entry policy")
                expected = nodes.get(name)
                if expected is None or _from_stat(metadata) != replace(
                    expected, native_identity=None, link_target=None
                ):
                    _fail("runtime native namespace changed")
                observed.add(name)

            tops = []
            with os.scandir(root.root) as entries:
                for entry in entries:
                    if (
                        len(tops) >= span.budget.maximum_entries
                        or entry.name not in nodes
                    ):
                        _fail("runtime root has an unexpected entry")
                    tops.append(entry.name)
            _inventory(
                root.root,
                tuple(sorted(tops)),
                span.budget.maximum_entries,
                allow_internal_symlinks=True,
                access=access,
                observe=observe,
            )
            if observed != set(nodes) - {""}:
                _fail("runtime native entries are missing")
            opened.append((root, nodes, access))
        for root, nodes, access in opened:
            for name, blob, executable in root.payloads:
                node = nodes[name]
                group = node.device, node.inode
                expected = blob, executable
                if group in groups:
                    if groups[group] != expected:
                        _fail("hardlink group has inconsistent payload commitments")
                    continue
                files += 1
                payload_bytes += blob.size
                if (
                    files > span.budget.maximum_files
                    or blob.size > span.budget.maximum_file_bytes
                    or payload_bytes > span.budget.maximum_total_bytes
                ):
                    _fail("runtime payload exceeds original policy")
                size, mode, digest = _stream(
                    root.root,
                    name,
                    blob.size,
                    access=access,
                    windows_executable=executable,
                    _chunk_size=_NATIVE_PAYLOAD_CHUNK,
                )
                if (size, bool(mode & 0o111), digest) != (
                    blob.size,
                    executable,
                    blob.digest,
                ):
                    _fail("runtime source payload changed")
                groups[group] = expected
            for name, target in root.links:
                expected = target.encode()
                if len(expected) > min(
                    span.budget.maximum_file_bytes,
                    span.budget.maximum_total_bytes - payload_bytes,
                ):
                    _fail("runtime symbolic text exceeds original policy")
                data = _link_bytes(root.root, name, len(expected), access)
                payload_bytes += len(expected)
                if data != expected:
                    _fail("runtime symbolic text changed or exceeds policy")
        # A composing current owner may close its actual canonical dependencies
        # after all payload reads while these no-follow access handles remain live.
        if _after_payload is not None:
            _after_payload()
        # No payload read follows this complete known-native close. Directory
        # stamps detect late insertion/removal, including inside shared parents.
        for root, _nodes, access in opened:
            ordered = sorted(
                root.native,
                key=lambda item: (
                    stat.S_ISDIR(item[1].mode),
                    -len(Path(item[0]).parts),
                ),
            )
            for name, expected in ordered:
                path = root.root / name
                actual = _from_stat(
                    access.metadata(path)
                    if access is not None and name
                    else path.lstat()
                )
                if expected.native_identity is not None and not stat.S_ISLNK(
                    expected.mode
                ):
                    actual = replace(
                        actual, native_identity=layout_entry_node(path).native_identity
                    )
                if actual != replace(expected, link_target=None):
                    _fail("runtime native facts changed after payload reads")
            if access is not None:
                access.require_current()
            if _lineage(root.root) != root.lineage or _from_stat(
                root.root.lstat()
            ) != replace(root.native[0][1], native_identity=None, link_target=None):
                _fail("runtime root changed during final closure")
