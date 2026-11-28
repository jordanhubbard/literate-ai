"""One actual incoming acquisition may advance its creating forest read facts.

Publication descriptions alone cannot enter here. The canonical acquisition
factory registers a one-use invocation after acquiring its real descriptors.
Only absent observations justified by those publications change; other current
inputs retain their original bytes, presence and ancestry.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .exclusive_entry import _from_stat
from .repository_refresh import RefreshFileObservation, _signature
from .retained_layout_control_publication import _publication_history
from .retained_layout_forest_observation import _POOLS, _record
from .retained_layout_journal import _directory


def _fail(message):
    raise ValueError("layout.forest-control-read: " + message)


def _presence(path):
    try:
        node = path.lstat()
    except FileNotFoundError:
        return None
    basic = node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid
    return (
        basic
        if stat.S_ISDIR(node.st_mode)
        else (*basic, node.st_size, node.st_mtime_ns, node.st_ctime_ns, node.st_nlink)
    )


def _close_lineage(rows):
    for spelling, *expected in rows:
        if _directory(Path(spelling).lstat()) != tuple(expected):
            _fail("original or actually created directory ancestry changed")


def _close_reader(reader, cache, ancestry, presences):
    # These are the same known native facts as the ordinary reader's final
    # closure, with only the receipt-justified proposed absences substituted.
    # Avoid its recording helpers until the verified transfer is installed.
    for rows in reader._lineages.values():
        _close_lineage(rows)
    for path, expected in presences.items():
        if _presence(path) != expected:
            _fail("unrelated original native presence changed")
    for path, item in cache.items():
        anchor, rows = ancestry[path]
        parent = path.parent
        while not os.path.lexists(parent):
            parent = parent.parent
        if parent != anchor:
            _fail("absent input ancestry lacks actual created-directory receipts")
        _close_lineage(rows)
        actual = _signature(path) if os.path.lexists(path) else None
        if actual != item.signature:
            _fail("original or acquired input native facts changed")


def advance_incoming_control_reads(lease, key):
    from .retained_layout_recovery_roles import _CREATED_ROLES, _READ_ADVANCES

    expected_key = _READ_ADVANCES.pop(lease, None)
    if expected_key is None or expected_key is not key:
        _fail("one actual canonical acquisition invocation required")
    owner = _POOLS.get(lease._pool)
    if owner is None:
        return  # Preserve the ordinary recovery path and its original reader.
    value = _record(owner, reading=True)
    lease._require_created()
    binding = _CREATED_ROLES[lease]
    incoming = binding[9]
    if incoming is None:
        return
    ledger, reader = value.ledger, value.reader
    count = (
        len(ledger.cache)
        + len(ledger.ancestry)
        + len(reader._presences)
        + len(reader._lineages)
        + len(incoming._markers)
        + len(incoming._directories)
        + len(incoming._held.nodes)
    )
    # Fund simultaneous old/new maps, immutable witnesses and retained marker
    # bytes before constructing them; retain the same cumulative input policy.
    size = sum(len(str(p).encode()) for p in ledger.cache)
    size += sum(len(str(p).encode()) for p in reader._presences)
    size += sum(len(str(p).encode()) for p in incoming._held.nodes)
    size += sum(len(m.content) for m in incoming._markers)
    ledger.charge_records(12 * count, 16 * size)
    ledger.bytes += sum(len(m.content) for m in incoming._markers)
    ledger.files += len(incoming._markers)
    ledger.require_capacity()
    cache_before = tuple(
        (p, item, item.path, item.signature, item.content)
        for p, item in ledger.cache.items()
    )
    ancestry_before = tuple(ledger.ancestry.items())
    presences_before = tuple(reader._presences.items())
    lineages_before = tuple(reader._lineages.items())
    markers = tuple(
        (
            m,
            m.target,
            m.descriptor,
            m.content,
            m.created,
            m.advisory_locked,
            incoming._expected.get(m.target.path),
        )
        for m in incoming._markers
    )
    directories = tuple(incoming._directories)
    held_owner, marker_list = incoming._held, incoming._markers
    expected_map, directory_list = incoming._expected, incoming._directories
    held = tuple(held_owner.nodes.items())
    history = _publication_history(value.pool)
    published = {item.path: item for item in history}
    if len(published) != len(history):
        _fail("incoming publication coordinates are ambiguous")
    if (
        len(markers) != len(binding[0].missing)
        or {m[1] for m in markers} != set(binding[0].missing)
        or incoming._locations
        or incoming._finishing
        or incoming._finalized
        or not incoming._complete
    ):
        _fail("original complete incoming acquisition required")
    created = {}
    for path, basic, target in directories:
        receipt = published.get(path)
        if (
            receipt is None
            or receipt.content is not None
            or receipt.node.directory_identity[:3] != basic
            or target not in binding[0].missing
            or incoming._held.nodes[path][1] != receipt.node.directory_identity[:-1]
        ):
            _fail("actual incoming created-directory publication required")
        created[path] = receipt
    cache, ancestry, presences = (
        dict(ledger.cache),
        dict(ledger.ancestry),
        dict(reader._presences),
    )
    for _marker, target, _descriptor, content, made, locked, node in markers:
        path = target.path
        receipt = published.get(path)
        if (
            not made
            or receipt is None
            or receipt.node != node
            or receipt.content != content
            or (target.advisory and not locked)
        ):
            _fail("actual created incoming marker publication required")
        before = cache.get(path)
        signature = (
            node.device,
            node.inode,
            node.mode,
            node.size,
            node.modified_ns,
            node.changed_ns,
        )
        if before is not None:
            if before.content is not None or before.signature is not None:
                _fail("only originally absent input bytes may advance")
            cache[path] = RefreshFileObservation(path, signature, content)
        if path in presences:
            if presences[path] is not None:
                _fail("only originally absent marker presence may advance")
            presences[path] = (
                node.device,
                node.inode,
                node.mode,
                node.uid,
                node.gid,
                node.size,
                node.modified_ns,
                node.changed_ns,
                node.links,
            )
    for path, receipt in created.items():
        if path in presences:
            if presences[path] is not None:
                _fail("created directory was not originally absent")
            presences[path] = receipt.node.directory_identity[:-1]
    for path, item, *_ in cache_before:
        if item.content is not None:
            continue
        anchor, rows = ancestry[path]
        try:
            parts = path.parent.relative_to(anchor).parts
        except ValueError:
            _fail("original absent input escaped its retained anchor")
        current, additions = anchor, []
        for part in parts:
            candidate = current / part
            receipt = created.get(candidate)
            if receipt is None:
                break
            current = candidate
            additions.append((str(current), *receipt.node.directory_identity[:-1]))
        if additions:
            ancestry[path] = current, (*rows, *additions)

    def close_originals():
        lease._require_created()
        if (
            _CREATED_ROLES.get(lease) is not binding
            or _record(owner, reading=True) is not value
            or _publication_history(value.pool) is not history
            or tuple(ledger.ancestry.items()) != ancestry_before
            or tuple(reader._presences.items()) != presences_before
            or tuple(reader._lineages.items()) != lineages_before
            or len(ledger.cache) != len(cache_before)
            or any(
                ledger.cache.get(p) is not item
                or (item.path, item.signature, item.content) != (old_path, sig, raw)
                for p, item, old_path, sig, raw in cache_before
            )
            or incoming._held is not held_owner
            or incoming._markers is not marker_list
            or incoming._expected is not expected_map
            or incoming._directories is not directory_list
            or not incoming._complete
            or incoming._finishing
            or incoming._finalized
            or tuple(incoming._directories) != directories
            or tuple(incoming._held.nodes.items()) != held
            or tuple(
                (
                    m,
                    m.target,
                    m.descriptor,
                    m.content,
                    m.created,
                    m.advisory_locked,
                    incoming._expected.get(m.target.path),
                )
                for m in incoming._markers
            )
            != markers
            or incoming._locations
        ):
            _fail("original incoming factory or creating read facts changed")

    incoming.verify_all()
    value.selection.require_current()
    close_originals()
    incoming._close_marker_inputs()
    for path, (descriptor, expected) in held:
        if (
            _directory(path.lstat()) != expected
            or _directory(os.fstat(descriptor)) != expected
        ):
            _fail("original held incoming ancestry changed")
    for _marker, _target, descriptor, _content, _made, _locked, node in markers:
        if _from_stat(os.fstat(descriptor)) != node:
            _fail("actual incoming descriptor changed after dependent reads")
    _close_reader(reader, cache, ancestry, presences)
    # Native reads above may invoke dependent guards. Close every original
    # issuer/role/reader/store registration purely after the last one, then
    # install only the verified simultaneous projection without more callbacks.
    close_originals()
    ledger.cache.update(cache)
    ledger.ancestry.update(ancestry)
    reader._presences.update(presences)
