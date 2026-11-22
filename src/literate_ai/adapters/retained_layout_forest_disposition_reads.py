"""Receipt-derived control input successors; unrelated reader facts stay fixed.

These helpers grant no writer rights. The actual registered disposition owner
checks dispatch, live descriptors and complete source custody around their use.
"""

from __future__ import annotations

import os
import stat
import unicodedata
from dataclasses import fields, is_dataclass

from literate_ai.contracts.identity import canonical_json_bytes

from .exclusive_entry import layout_entry_node
from .repository_refresh import RefreshFileObservation, _raw_file
from .repository_refresh_reservations import _custody_wire
from .retained_layout_forest_control_read import _close_reader


def _fail(message):
    raise ValueError("layout.forest-disposition-reads: " + message)


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
    return (
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


def read_owned_marker(path, *, maximum_bytes=256):
    """Bounded no-follow native read, without advancing any ordinary observer."""
    if type(maximum_bytes) is not int or not 1 <= maximum_bytes <= 256:
        _fail("finite owned marker read allowance required")
    before = layout_entry_node(path)
    if (
        not stat.S_ISREG(before.mode)
        or before.links != 1
        or before.uid != os.geteuid()
        or not 1 <= before.size <= maximum_bytes
    ):
        _fail("bounded owned single-link marker required")
    raw = _raw_file(path, maximum_bytes=maximum_bytes)
    if (
        raw.signature != _signature(before)
        or layout_entry_node(path) != before
        or len(raw.content) != before.size
    ):
        _fail("actual marker changed during receipt observation")
    return before, raw.content


def require_fixed_control_reads(value, entries, destinations):
    """Refuse unmatched aliases before entering any control mutation schedule."""
    owned = {(e.node.device, e.node.inode): e.named for e in entries}

    def key(path):
        return tuple(
            unicodedata.normalize("NFC", part.casefold()) for part in path.parts
        )

    prospective = {key(path): path for path in destinations}
    for path, item in value.ledger.cache.items():
        if item.signature is not None:
            actual = owned.get(item.signature[:2])
            if actual is not None and path != actual:
                _fail("observed control alias requires an explicit receipt transfer")
        expected = prospective.get(key(path))
        if expected is not None and path != expected:
            _fail("observed retirement alias requires an explicit receipt transfer")
    for path, node in value.reader._presences.items():
        if node is not None:
            actual = owned.get(node[:2])
            if actual is not None and path != actual:
                _fail("control presence alias requires an explicit receipt transfer")
        expected = prospective.get(key(path))
        if expected is not None and path != expected:
            _fail("retirement presence alias requires an explicit receipt transfer")


def seal_successors(bundle):
    """Capture the exact finite derived graph before callback-bearing reads."""
    pending, seen, references = [bundle], set(), []
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        if type(item) is tuple:
            pending.extend(item)
        elif is_dataclass(item):
            values = tuple((f.name, getattr(item, f.name)) for f in fields(item))
            references.append((item, values))
            pending.extend(v for _name, v in values)
    return bundle, tuple(references), canonical_json_bytes(_custody_wire(bundle))


def require_successors(bundle, sealed):
    if (
        len(bundle) != len(sealed[0])
        or any(a is not b for a, b in zip(bundle, sealed[0], strict=True))
        or any(
            getattr(item, name) is not original
            for item, values in sealed[1]
            for name, original in values
        )
    ):
        _fail("derived successor references changed after native verification")
    if canonical_json_bytes(_custody_wire(bundle)) != sealed[2]:
        _fail("derived successor contents changed after native verification")


def project_control_reads(value, entry, node, content, destination):
    """Substitute only an actual owned control's exact before/after facts."""
    ledger, reader = value.ledger, value.reader
    reader._live()
    if reader._io_active:
        _fail("original reader I/O overlaps control receipt transfer")
    cache, presences = dict(ledger.cache), dict(reader._presences)
    old = cache.get(entry.named)
    if old is not None:
        if (
            old.path != entry.named
            or old.signature != _signature(entry.node)
            or old.content != entry.content
        ):
            _fail("original control input differs from held pre-effect custody")
        cache[entry.named] = RefreshFileObservation(
            entry.named,
            _signature(node) if destination is None else None,
            content if destination is None else None,
        )
    if entry.named in presences:
        if presences[entry.named] != _presence(entry.node):
            _fail("original control presence differs from held pre-effect custody")
        presences[entry.named] = _presence(node) if destination is None else None
    if destination is not None:
        if destination in cache:
            old = cache[destination]
            if old.signature is not None or old.content is not None:
                _fail("retirement cannot replace an observed input")
            cache[destination] = RefreshFileObservation(
                destination, _signature(node), content
            )
        if destination in presences:
            if presences[destination] is not None:
                _fail("retirement cannot replace an observed native presence")
            presences[destination] = _presence(node)
    return tuple(cache.items()), tuple(presences.items())


def seal_projection(projection):
    cache, presences = projection
    return (
        canonical_json_bytes(_custody_wire(projection)),
        tuple((p, item, item.path, item.signature, item.content) for p, item in cache),
        tuple(presences),
    )


def require_projection(projection, sealed):
    cache, presences = projection
    if (
        canonical_json_bytes(_custody_wire(projection)) != sealed[0]
        or len(cache) != len(sealed[1])
        or any(
            p is not q
            or item is not old
            or item.path is not path
            or item.signature is not sig
            or item.content is not raw
            for (p, item), (q, old, path, sig, raw) in zip(
                cache, sealed[1], strict=True
            )
        )
        or tuple(presences) != sealed[2]
    ):
        _fail("derived control reader successor changed")


def close_projection(value, projection, sealed):
    value.reader._live()
    if value.reader._io_active:
        _fail("original reader I/O overlaps control receipt transfer")
    require_projection(projection, sealed)
    _close_reader(
        value.reader, dict(projection[0]), value.ledger.ancestry, dict(projection[1])
    )
    require_projection(projection, sealed)
