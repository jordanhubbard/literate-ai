"""Fresh retained control descriptors, not transaction recovery or saved roles.

The caller must separately derive actual canonical roles and classify all source
and metadata endpoints before any recovery effect. No marker is created, rewritten
or removed here, and a retired private token never owns its former public name.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
import unicodedata
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, fields, replace
from itertools import islice
from pathlib import Path

from literate_ai._cache_lock import _acquire
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from ._write_reservations import (
    _CREATION_KEY,
    WriteReservationSet,
    WriteReservationTarget,
    _OwnedMarker,
    combine_body_and_release_errors,
)
from .exclusive_entry import LayoutEntryNode, _from_stat, layout_entry_node
from .repository_refresh import _file
from .repository_refresh_reservations import _custody_wire
from .retained_layout_control_publication import _ControlPool, _pinned_directory
from .retained_layout_journal import _file as _journal_file
from .retained_layout_partition import _lineage, _physical_wire
from .retained_layout_reservations import (
    _disposition_exit_boundary,
    _HeldDirectories,
    _portable_name,
    _raise_disposition_outcome,
    _StagedReservationSet,
)

_CREATED_RECOVERIES = {}


def _fail(message):
    raise ValueError("layout.recovery-controls: " + message)


def _require_legacy_recovery_profile(pool):
    """Reject a cached unsupported format; grant no authority or native access.

    Existing callers retain their original complete owner/liveness validation.
    In particular, an expired descriptor owner must refuse before any borrowed
    native FD access, including a new pool or journal liveness probe here.
    """
    from .retained_layout_journal import _RECORD_LIMIT, _LayoutJournalWriter

    if type(pool) is not _ControlPool:
        return
    try:
        journal = object.__getattribute__(pool, "_journal")
        if type(journal) is not _LayoutJournalWriter:
            return
        known = object.__getattribute__(journal, "_known")
    except AttributeError:
        return
    if type(known) is not dict:
        return
    header = None
    try:
        # Even an exact dict may contain colliding foreign keys. Inspect only
        # plain string keys, without hashing/comparing supplied key objects.
        # A real journal has at most 256 event and 256 payload records; the
        # fixed bound also covers its header and private stages.
        for name, value in islice(known.items(), 1024):
            if type(name) is str and name == "header.json":
                header = value
                break
    except RuntimeError:
        return
    if (
        type(header) is not tuple
        or len(header) != 2
        or type(header[1]) is not bytes
        or len(header[1]) > _RECORD_LIMIT
    ):
        return
    try:
        document = json.loads(header[1])
    except (ValueError, RecursionError):
        return
    if type(document) is not dict:
        return
    binding = document.get("binding")
    if type(binding) is dict and "source_profile" in binding:
        from .retained_layout_forest_observation import _require_profile

        _require_profile(pool, binding)


def _node(document):
    names = {field.name for field in fields(LayoutEntryNode)}
    if type(document) is not dict or set(document) != names:
        _fail("invalid recorded native node")
    values = dict(document)
    for name in names - {"native_identity", "link_target"}:
        value = values[name]
        if type(value) is dict and set(value) == {"integer_decimal"}:
            raw = value["integer_decimal"]
            if type(raw) is not str or not 1 <= len(raw) <= 128:
                _fail("invalid recorded native integer")
            value = int(raw)
            if str(value) != raw:
                _fail("noncanonical recorded native integer")
        if type(value) is not int:
            _fail("invalid recorded native integer")
        values[name] = value
    if values["native_identity"] is not None or values["link_target"] is not None:
        _fail("direct POSIX control node required")
    return LayoutEntryNode(**values)


def _optional_node(path):
    try:
        return layout_entry_node(path)
    except FileNotFoundError:
        return None


def _read_marker(path):
    before = layout_entry_node(path)
    if (
        not stat.S_ISREG(before.mode)
        or before.links != 1
        or before.uid != os.geteuid()
        or not 1 <= before.size <= 256
    ):
        _fail("existing bounded owned single-link marker required")
    content = _file(path, maximum_bytes=256).content
    if layout_entry_node(path) != before or len(content) != before.size:
        _fail("marker changed during observation")
    return before, content


def _names(root, limit):
    names = set()
    with os.scandir(root) as entries:
        for entry in entries:
            if len(names) >= limit:
                _fail("retirement namespace exceeds its bound")
            names.add(entry.name)
    return tuple(sorted(names))


@dataclass(frozen=True, slots=True)
class _RecoveryMarker:
    target: WriteReservationTarget
    named: Path
    node: LayoutEntryNode
    content: bytes


@dataclass(frozen=True, slots=True)
class _RecoveryArea:
    root: Path
    lineage: tuple
    entries: tuple


def _recovery_area(root, *, maximum_entries=1024):
    if type(maximum_entries) is not int or not 0 <= maximum_entries <= 1024:
        _fail("bounded recovery area observation required")
    lineage = _lineage(root)
    node = layout_entry_node(root)
    if node.uid != os.geteuid() or stat.S_IMODE(node.mode) != 0o700:
        _fail("owned private recovery retirement directory required")
    entries = tuple(
        (name, layout_entry_node(root / name)) for name in _names(root, maximum_entries)
    )
    if _lineage(root) != lineage:
        _fail("recovery retirement ancestry changed")
    return _RecoveryArea(root, lineage, entries)


def _recovery_observation(events, intent):
    matches = [
        e["data"]
        for e in events
        if e["kind"] == intent["kind"].removesuffix("-intent") + "-observed"
        and e["sequence"] > intent["sequence"]
        and e["data"].get("operation") == intent["data"]["operation"]
    ]
    if len(matches) > 1:
        _fail("ambiguous recovery control observation")
    if matches:
        if {k: v for k, v in matches[0].items() if k != "observed_node"} != intent[
            "data"
        ]:
            _fail("recovery control observation contradicts intent")
        return _node(matches[0]["observed_node"])
    return None


def _disposition_areas(pool):
    """Validate whole shared retirement namespaces, without granting their rights."""
    from .retained_layout_disposition_read import control_events

    journal = pool._journal
    events = control_events(
        pool,
        kinds=frozenset(
            {
                "recovery-control-disposition-intent",
                "reservation-lease-intent",
                "recovery-control-retirement-intent",
                "recovery-control-retirement-observed",
            }
        ),
    )
    declarations = [
        e["data"] for e in events if e["kind"] == "recovery-control-disposition-intent"
    ]
    leases = {
        (e["data"]["group"], e["data"]["path"]): e["data"]
        for e in events
        if e["kind"] == "reservation-lease-intent"
    }
    result = []
    for declaration in declarations:
        root = Path(declaration["retirement_root"])
        if not root.is_absolute() or ".." in root.parts:
            _fail("invalid recovery retirement coordinate")
        area = _recovery_area(root)
        if (
            layout_entry_node(root).directory_identity
            != _node(declaration["retirement_node"]).directory_identity
        ):
            _fail("recovery retirement root replaced")
        expected = {}
        for event in events:
            if event["kind"] != "recovery-control-retirement-intent":
                continue
            data = event["data"]
            if Path(data["destination"]).parent != root:
                continue
            lease = leases.get((data["group"], data["path"]))
            if (
                lease is None
                or lease["advisory"] is not False
                or _node(lease["node"]) != _node(data["original_node"])
                or data["source"] != data["path"]
                or journal.read_payload(lease["payload_digest"])
                != journal.read_payload(data["before_payload"])
            ):
                _fail("recovery retirement lacks original native acquisition")
            before = _node(data["node"])
            if before != _node(lease["node"]):
                _fail("recovery retirement substitutes original native node")
            destination = Path(data["destination"])
            if (
                layout_entry_node(root).directory_identity
                != _node(data["destination_parent"]).directory_identity
                or layout_entry_node(Path(data["source"]).parent).directory_identity
                != _node(data["source_parent"]).directory_identity
            ):
                _fail("recovery control retirement parents changed")
            actual = _optional_node(destination)
            observed = _recovery_observation(events, event)
            if actual is None:
                if observed is not None:
                    _fail("observed recovery retirement missing")
                continue
            if (
                actual.after_rename() != before.after_rename()
                or (observed is not None and actual != observed)
                or _read_marker(destination)
                != (actual, journal.read_payload(data["before_payload"]))
            ):
                _fail("recovery retirement node changed")
            if destination.name in expected:
                _fail("ambiguous repeated recovery retirement destination")
            expected[destination.name] = actual
        if dict(area.entries) != expected:
            _fail("recovery retirement contains foreign or missing nodes")
        if any(existing.root == area.root for existing in result):
            _fail("recovery retirement root reused")
        result.append(area)
    return tuple(result)


def _recovery_endpoint(journal, events, group, target, original, content, areas):
    selected = [
        e
        for e in events
        if e["kind"]
        in {
            "recovery-control-normalization-intent",
            "recovery-control-retirement-intent",
        }
        and e["data"].get("group") == group
        and e["data"].get("path") == str(target.path)
        and _node(e["data"]["original_node"]) == original
    ]
    if not selected:
        return None
    if not target.advisory and len(selected) != 1:
        # A retry before the native effect can record another intent. Only one
        # actual private destination may contain the original inode.
        actuals = [
            e
            for e in selected
            if _optional_node(Path(e["data"]["destination"])) is not None
        ]
        if len(actuals) > 1:
            _fail("multiple actual recovery retirement endpoints")
        if actuals:
            selected = actuals
    for event in selected:
        data = event["data"]
        before, payload = (
            _node(data["node"]),
            journal.read_payload(data["before_payload"]),
        )
        if target.advisory:
            immutable = ("device", "inode", "mode", "links", "uid", "gid")
            if (
                event["kind"] != "recovery-control-normalization-intent"
                or not content.startswith(b"literate-ai-refresh-reservation\n")
                or payload not in (content, b"\0" + content[1:])
                or before.size != len(payload)
                or any(getattr(before, k) != getattr(original, k) for k in immutable)
            ):
                _fail("invalid recovery advisory normalization provenance")
        elif (
            event["kind"] != "recovery-control-retirement-intent"
            or before != original
            or payload != content
        ):
            _fail("invalid recovery native retirement provenance")
    event = selected[-1]
    data = event["data"]
    observed = _recovery_observation(events, event)
    if target.advisory:
        actual, value = _read_marker(target.path)
        before = _node(data["node"])
        payload = journal.read_payload(data["before_payload"])
        immutable = ("device", "inode", "mode", "links", "uid", "gid")
        if (
            any(getattr(actual, k) != getattr(original, k) for k in immutable)
            or value not in (payload, b"\0" + payload[1:], b"\0")
            or (observed is not None and (actual != observed or value != b"\0"))
            or (actual == before and value != payload)
        ):
            _fail("recovery advisory bytes/native facts changed")
        return _RecoveryMarker(target, target.path, actual, value), None
    destination = Path(data["destination"])
    if destination.parent not in {area.root for area in areas}:
        _fail("undeclared recovery retirement root")
    actual = _optional_node(destination)
    if actual is None:
        if observed is not None:
            _fail("observed recovery native retirement missing")
        actual, value = _read_marker(target.path)
        if actual != original or value != content:
            _fail("unmoved recovery native marker changed")
        return _RecoveryMarker(target, target.path, actual, value), None
    if _optional_node(target.path) == original:
        _fail("original native control occupies both endpoints")
    return _RecoveryMarker(target, destination, actual, content), (
        target.path,
        _optional_node(target.path),
    )


@dataclass(frozen=True, slots=True)
class _ControlRecoveryPlan:
    pool_root: Path
    header: bytes
    history: tuple[bytes, ...]
    markers: tuple[_RecoveryMarker, ...]
    lineages: tuple
    retirement_root: Path | None
    retirement_names: tuple[str, ...]
    public_nodes: tuple
    group: str
    recovery_areas: tuple = ()
    compact_anchor: tuple | None = None
    compact_steps: tuple = ()

    @property
    def identity(self):
        return canonical_identity(_custody_wire(self))


def _records(pool, targets, reservation_group):
    from .retained_layout_disposition_read import control_events

    events = control_events(
        pool,
        kinds=frozenset(
            {
                "reservation-set-acquired",
                "reservation-lease-intent",
                "control-finalization-intent",
                "advisory-normalization-intent",
                "advisory-normalization-observed",
                "native-control-retirement-intent",
                "native-control-retirement-observed",
                "recovery-control-normalization-intent",
                "recovery-control-normalization-observed",
                "recovery-control-retirement-intent",
                "recovery-control-retirement-observed",
            }
        ),
    )
    by_path = {str(target.path): target for target in targets}
    if len(by_path) != len(targets):
        _fail("complete actual target coordinates required")
    candidates = []
    for event in events:
        if event["kind"] != "reservation-set-acquired":
            continue
        acquired = event["data"]
        if reservation_group is not None and acquired["group"] != reservation_group:
            continue
        leases = [
            entry["data"]
            for entry in events
            if entry["kind"] == "reservation-lease-intent"
            and entry["data"].get("group") == acquired["group"]
        ]
        leases.sort(key=lambda item: item["ordinal"])
        if (
            len(leases) == acquired["count"] == len(targets)
            and [item["ordinal"] for item in leases] == list(range(len(leases)))
            and {item["path"] for item in leases} == set(by_path)
        ):
            candidates.append((event["sequence"], acquired, leases))
    if len(candidates) != 1:
        _fail(
            "complete actual target coordinates and one unambiguous completed "
            "generation required; retain incomplete state"
        )
    sequence, acquired, leases = candidates[0]
    ordered = [by_path[item["path"]] for item in leases]
    identity = (
        "sha256:"
        + hashlib.sha256(
            canonical_json_bytes(
                _physical_wire(
                    [
                        {
                            "path": str(t.path),
                            "anchor": str(t.anchor),
                            "anchor_node": t.anchor_node,
                            "advisory": t.advisory,
                        }
                        for t in ordered
                    ]
                )
            )
        ).hexdigest()
    )
    if identity != acquired["target_identity"] or any(
        item["target_identity"] != identity or item["advisory"] is not target.advisory
        for item, target in zip(leases, ordered, strict=True)
    ):
        _fail("recorded acquisition disagrees with actual targets")
    # Events from earlier generations cannot describe this acquisition's effects.
    actions = tuple(event for event in events if event["sequence"] > sequence)
    return actions, leases, ordered, acquired["group"]


def _one(events, kind, key, value, original, *, observed=False):
    found = [
        event["data"]
        for event in events
        if event["kind"] == kind
        and event["data"].get(key) == value
        and (
            (_node(event["data"]["node"]).device, _node(event["data"]["node"]).inode)
            == (original.device, original.inode)
            if observed
            else _node(event["data"]["node"]) == original
        )
    ]
    if len(found) > 1:
        _fail("ambiguous repeated control history")
    return found[0] if found else None


def plan_layout_control_recovery(pool, targets, *, reservation_group=None):
    """Observe existing endpoints; no OS mutex, marker mutation or role grant."""
    if (
        os.name != "posix"
        or type(pool) is not _ControlPool
        or type(targets) is not tuple
        or not 1 <= len(targets) <= 1024
        or any(type(target) is not WriteReservationTarget for target in targets)
    ):
        raise TypeError("layout.recovery-controls.live-bounded-inputs-required")
    _require_legacy_recovery_profile(pool)
    from .retained_layout_disposition_read import control_plan_history

    with control_plan_history(pool):
        return _plan_layout_control_recovery(
            pool, targets, reservation_group=reservation_group
        )


def _plan_layout_control_recovery(pool, targets, *, reservation_group=None):
    pool.require_current()
    aliases = {unicodedata.normalize("NFC", str(t.path).casefold()) for t in targets}
    if len(aliases) != len(targets) or any(
        target.path in other.path.parents for target in targets for other in targets
    ):
        _fail("target coordinates alias or overlap")
    journal = pool._journal
    events, leases, ordered, group = _records(pool, targets, reservation_group)
    finalization = [
        event["data"]
        for event in events
        if event["kind"] == "control-finalization-intent"
        and {item["path"] for item in event["data"]["controls"]}
        == {item["path"] for item in leases}
        and all(
            any(
                item["path"] == lease["path"]
                and _node(item["node"]) == _node(lease["node"])
                for item in event["data"]["controls"]
            )
            for lease in leases
        )
    ]
    if len(finalization) > 1:
        _fail("ambiguous finalization history")
    retirement_root = None
    if finalization:
        data = finalization[0]
        retirement_root = Path(data["root"])
        if not retirement_root.is_absolute() or ".." in retirement_root.parts:
            _fail("invalid retirement coordinate")
        declared = data["controls"]
        if len(declared) != len(leases) or {item["path"] for item in declared} != {
            item["path"] for item in leases
        }:
            _fail("finalization does not cover complete original set")
        by_path = {item["path"]: item for item in declared}
        for lease in leases:
            item = by_path[lease["path"]]
            if (
                _node(item["node"]) != _node(lease["node"])
                or item["advisory"] is not lease["advisory"]
                or type(item["created"]) is not bool
            ):
                _fail("finalization control facts disagree with original acquisition")
        node = layout_entry_node(retirement_root)
        if (
            node.directory_identity != _node(data["node"]).directory_identity
            or node.uid != os.geteuid()
            or stat.S_IMODE(node.mode) != 0o700
        ):
            _fail("retirement directory changed")
    protected = {
        (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
        for fd in (pool._descriptor, journal._descriptor)
    }
    markers, public_nodes, lineages = [], [], {}
    recovery_areas = _disposition_areas(pool)
    for area in recovery_areas:
        if any(record[1:3] in protected for record in area.lineage):
            _fail("recovery retirement overlaps current producer")
        lineages[area.root] = area.lineage
    if retirement_root is not None:
        ancestry = _lineage(retirement_root)
        if any(record[1:3] in protected for record in ancestry):
            _fail("retirement state overlaps current private producer")
        lineages[retirement_root] = ancestry
    for lease, target in zip(leases, ordered, strict=True):
        WriteReservationSet._guard(target)
        original = _node(lease["node"])
        content = journal.read_payload(lease["payload_digest"])
        if not 1 <= len(content) <= 256:
            _fail("invalid original marker payload")
        recovered = _recovery_endpoint(
            journal, events, group, target, original, content, recovery_areas
        )
        if recovered is not None:
            marker, public = recovered
            markers.append(marker)
            if public is not None:
                public_nodes.append(public)
            for parent in (target.anchor, target.path.parent, marker.named.parent):
                ancestry = _lineage(parent)
                if any(record[1:3] in protected for record in ancestry):
                    _fail("recovered control overlaps current private producer")
                lineages[parent] = ancestry
            with _pinned_directory(marker.named.parent) as (fd, guard):
                _portable_name(marker.named, fd, present=True)
                guard()
            continue
        current, named = _optional_node(target.path), target.path
        normal = _one(
            events, "advisory-normalization-intent", "path", str(target.path), original
        )
        normal_observed = _one(
            events,
            "advisory-normalization-observed",
            "path",
            str(target.path),
            original,
            observed=True,
        )
        retire = _one(
            events,
            "native-control-retirement-intent",
            "source",
            str(target.path),
            original,
        )
        retired = _one(
            events,
            "native-control-retirement-observed",
            "source",
            str(target.path),
            original,
            observed=True,
        )
        if retire:
            destination = Path(retire["destination"])
            if (
                target.advisory
                or retirement_root is None
                or destination.parent != retirement_root
                or destination.name not in {f"control-{i}" for i in range(len(targets))}
                or _node(retire["node"]) != original
                or journal.read_payload(retire["payload"]) != content
                or layout_entry_node(target.path.parent).directory_identity
                != _node(retire["source_parent"]).directory_identity
                or layout_entry_node(retirement_root).directory_identity
                != _node(retire["destination_parent"]).directory_identity
            ):
                _fail("invalid native retirement intent")
            private = _optional_node(destination)
            if private is not None:
                if private.after_rename() != original.after_rename():
                    _fail("retired marker was replaced")
                if current is not None and (current.device, current.inode) == (
                    original.device,
                    original.inode,
                ):
                    _fail("both marker endpoints contain original node")
                public_nodes.append((target.path, current))
                named, current = destination, private
            elif retired:
                _fail("recorded retired marker is missing")
        elif retired:
            _fail("retirement observation lacks intent")
        if current is None:
            _fail("original marker is missing; retain unresolved endpoints")
        actual, observed = _read_marker(named)
        if actual != current:
            _fail("marker changed during endpoint classification")
        if normal:
            entries = (
                {item["path"]: item for item in finalization[0]["controls"]}
                if finalization
                else {}
            )
            declared = entries.get(str(target.path), {})
            if (
                not target.advisory
                or declared.get("created") is not True
                or _node(normal["node"]) != original
                or journal.read_payload(normal["before"]) != content
                or journal.read_payload(normal["after"]) != b"\0"
            ):
                _fail("invalid advisory normalization intent")
            immutable = ("device", "inode", "mode", "links", "uid", "gid")
            if any(getattr(actual, key) != getattr(original, key) for key in immutable):
                _fail("normalized marker was replaced")
            if observed not in (content, b"\0" + content[1:], b"\0"):
                _fail("unknown normalization bytes")
            if normal_observed and (
                actual != _node(normal_observed["node"]) or observed != b"\0"
            ):
                _fail("observed normalized marker changed")
        elif observed != content or (
            actual != original
            if named == target.path
            else actual.after_rename() != original.after_rename()
        ):
            _fail("retained marker changed")
        if retired and actual != _node(retired["node"]):
            _fail("observed retired marker changed")
        if normal_observed and not normal:
            _fail("normalization observation lacks intent")
        for parent in (target.anchor, target.path.parent, named.parent):
            ancestry = _lineage(parent)
            if any(record[1:3] in protected for record in ancestry):
                _fail("control overlaps current private producer")
            lineages[parent] = ancestry
            if (
                len({record[0] for value in lineages.values() for record in value})
                > 4096
            ):
                _fail("recovery ancestry exceeds its bound")
        with _pinned_directory(named.parent) as (fd, guard):
            _portable_name(named, fd, present=True)
            guard()
        markers.append(_RecoveryMarker(target, named, actual, observed))
    if retirement_root is not None and (
        layout_entry_node(retirement_root).directory_identity
        != _node(finalization[0]["node"]).directory_identity
    ):
        _fail("retirement directory changed during observation")
    names = _names(retirement_root, len(targets)) if retirement_root else ()
    if set(names) != {
        m.named.name for m in markers if m.named.parent == retirement_root
    }:
        _fail("retirement namespace contains foreign or missing entries")
    if len({(m.node.device, m.node.inode) for m in markers}) != len(markers):
        _fail("control native identities alias")
    if any(m.node.device != os.fstat(pool._descriptor).st_dev for m in markers):
        _fail("recovery controls require one filesystem")
    from .retained_layout_disposition_read import control_history, has_compact

    compact_anchor = control_history(pool).open_batch if has_compact(journal) else None
    compact_steps = _compact_steps(journal, compact_anchor)
    plan = _ControlRecoveryPlan(
        pool.root,
        journal._known["header.json"][1],
        tuple(journal._known[name][1] for name in journal._events),
        tuple(markers),
        tuple(lineages.items()),
        retirement_root,
        names,
        tuple(public_nodes),
        group,
        recovery_areas,
        compact_anchor,
        compact_steps,
    )
    _require_inputs(pool, plan)
    return plan


def _require_inputs(pool, plan):
    _require_legacy_recovery_profile(pool)
    pool.require_current()
    if (
        pool.root != plan.pool_root
        or pool._journal._known["header.json"][1] != plan.header
    ):
        _fail("recovery producer or journal binding changed")
    for index, raw in enumerate(plan.history):
        if pool._journal._known.get(f"e-{index:04d}.json", (None, None))[1] != raw:
            _fail("original recovery history changed")
    for path, ancestry in plan.lineages:
        if _lineage(path) != ancestry:
            _fail("recovery ancestry changed")
    for marker in plan.markers:
        if _read_marker(marker.named) != (marker.node, marker.content):
            _fail("prepared recovery marker changed")
    retirements = _close_retirement(plan)
    _close_inputs(plan)
    # Complete private-area observations precede final marker and producer
    # native facts. No payload is traversed after this closing pass.
    producers = _close_dependencies(pool)
    _close_marker_facts(plan)
    _close_retirement_facts(retirements)
    _close_dependency_facts(pool, producers)
    _close_compact_prefix(pool._journal, plan)


def _compact_steps(journal, anchor):
    if anchor is None:
        return ()
    from .retained_layout_disposition_compact import STEP_MAGIC

    prefix = STEP_MAGIC + anchor[0].encode("ascii") + b"\n"
    return tuple(
        sorted(
            digest
            for digest in journal._payloads
            if journal._known[f"p-{digest}.bin"][1].startswith(prefix)
        )
    )


def _close_compact_prefix(journal, plan):
    if _compact_steps(journal, plan.compact_anchor) != plan.compact_steps:
        _fail("prepared abandoned compact prefix changed")


def _close_dependencies(pool):
    journal = pool._journal
    journal._guard()
    roots = tuple(
        _from_stat(os.fstat(fd)) for fd in (journal._descriptor, pool._descriptor)
    )
    expected = set(journal._known)
    if journal._names() != expected:
        _fail("journal namespace changed during recovery observation")
    for name, (signature, _) in journal._known.items():
        named = os.stat(name, dir_fd=journal._descriptor, follow_symlinks=False)
        if _journal_file(named) != signature:
            _fail("journal native facts changed during recovery observation")
    if journal._names() != expected:
        _fail("journal namespace changed during closing observations")
    pool._require_private_close()
    journal._guard()
    _close_dependency_facts(pool, roots)
    return roots


def _close_dependency_facts(pool, roots):
    """Only captured producer root/file facts; no payload or namespace reads."""
    journal = pool._journal
    pool._guard()
    if type(roots) is not tuple or len(roots) != 2:
        _fail("actual producer native roots required")
    for fd, expected in zip(
        (journal._descriptor, pool._descriptor), roots, strict=True
    ):
        if _from_stat(os.fstat(fd)) != expected:
            _fail("producer namespace changed after closing observations")
    for name, (signature, _) in journal._known.items():
        if (
            _journal_file(
                os.stat(name, dir_fd=journal._descriptor, follow_symlinks=False)
            )
            != signature
        ):
            _fail("journal native facts changed after namespace observations")
    for item in pool._entries.values():
        if (
            _from_stat(
                os.stat(item.name, dir_fd=pool._descriptor, follow_symlinks=False)
            )
            != item.node
        ):
            _fail("private producer node changed after namespace observations")
    journal._guard()


def _close_inputs(plan):
    for marker in plan.markers:
        with _pinned_directory(marker.named.parent) as (fd, guard):
            _portable_name(marker.named, fd, present=True)
            guard()
        if layout_entry_node(marker.named) != marker.node:
            _fail("recovery marker native facts changed")
    for path, expected in plan.public_nodes:
        with _pinned_directory(path.parent) as (fd, guard):
            _portable_name(path, fd, present=expected is not None)
            guard()
        if _optional_node(path) != expected:
            _fail("released public coordinate changed")
    if (
        plan.retirement_root
        and _names(plan.retirement_root, len(plan.markers)) != plan.retirement_names
    ):
        _fail("retirement namespace changed")
    for path, ancestry in plan.lineages:
        if _lineage(path) != ancestry:
            _fail("recovery ancestry changed during closing observations")


def _close_retirement(plan):
    # Observe complete retirement namespaces before final marker/dependency
    # native closure; never traverse payloads or initialize controls here.
    roots = []
    for area in plan.recovery_areas:
        before = layout_entry_node(area.root)
        if _recovery_area(area.root) != area or layout_entry_node(area.root) != before:
            _fail("recovery retirement namespace changed during closing observations")
        roots.append((area, before))
    if plan.retirement_root and (
        _names(plan.retirement_root, len(plan.markers)) != plan.retirement_names
    ):
        _fail("retirement namespace changed after dependency closure")
    if plan.retirement_root is not None:
        root = plan.retirement_root
        before = layout_entry_node(root)
        expected = _RecoveryArea(
            root,
            dict(plan.lineages)[root],
            tuple(
                sorted(
                    (m.named.name, m.node)
                    for m in plan.markers
                    if m.named.parent == root
                )
            ),
        )
        if _recovery_area(root) != expected or layout_entry_node(root) != before:
            _fail("original retirement graph changed during closing observations")
        roots.append((expected, before))
    for path, ancestry in plan.lineages:
        if _lineage(path) != ancestry:
            _fail("recovery ancestry changed after dependency closure")
    return tuple(roots)


def _close_retirement_facts(roots):
    """Close known private nodes and directory stamps without enumerating names."""
    for area, before in roots:
        if (
            layout_entry_node(area.root) != before
            or _lineage(area.root) != area.lineage
        ):
            _fail("retirement namespace or ancestry changed after observations")
        for name, node in area.entries:
            if layout_entry_node(area.root / name) != node:
                _fail("retired native node changed after observations")


def _close_marker_facts(plan):
    for marker in plan.markers:
        if layout_entry_node(marker.named) != marker.node:
            _fail("named marker changed after namespace observations")
    for path, node in plan.public_nodes:
        if _optional_node(path) != node:
            _fail("public coordinate changed after namespace observations")
    for path, lineage in plan.lineages:
        if _lineage(path) != lineage:
            _fail("marker ancestry changed after namespace observations")


def _recovered_binding(owner, plan):
    return (
        owner._pool,
        plan,
        owner._held,
        os.getpid(),
        threading.get_ident(),
        plan.identity.uri,
        tuple(
            (m, m.target, m.descriptor, m.node, m.content, m.created, m.advisory_locked)
            for m in owner._markers
        ),
    )


def _require_recovered_creation(owner):
    original = _CREATED_RECOVERIES.get(owner)
    if (
        original is None
        or owner._active is not True
        or owner._receiver != os.getpid()
        or original[0] is not owner._pool
        or original[1] is not owner._plan
        or original[2] is not owner._held
        or original[3:5] != (os.getpid(), threading.get_ident())
        or owner._plan.identity.uri != original[5]
        or len(owner._markers) != len(original[6])
        or any(
            marker is not row[0]
            or marker.target is not row[1]
            or (
                marker.descriptor,
                marker.node,
                marker.content,
                marker.created,
                marker.advisory_locked,
            )
            != row[2:]
            for marker, row in zip(owner._markers, original[6], strict=True)
        )
    ):
        _fail("actual creating recovered descriptor lifetime required")
    _require_legacy_recovery_profile(owner._pool)
    return original


class _RecoveredControlSet(WriteReservationSet):
    def __init__(self, pool, plan, held):
        super().__init__(_CREATION_KEY)
        self._pool, self._plan, self._held = pool, plan, held
        self._receiver = os.getpid()
        self._retain_for_recovery = True
        self._disposition = None

    def _live(self):
        if not self._active or self._receiver != os.getpid():
            _fail("recovered descriptor context ended")
        _require_recovered_creation(self)
        self._pool._guard()
        _require_recovered_creation(self)
        self._held.current()
        _require_recovered_creation(self)

    def verify_all(self):
        if self._disposition is not None:
            from .retained_layout_recovery_disposition import _RecoveryDisposition

            if type(self._disposition) is not _RecoveryDisposition:
                _fail("actual disposition owner required")
            return self._disposition.verify_descriptor_owner(self)
        self._verify_view(self._plan)

    def _verify_view(self, plan):
        self._live()
        if not self._complete:
            _fail("recovered descriptor acquisition incomplete")
        _require_inputs(self._pool, plan)
        for marker, expected in zip(self._markers, plan.markers, strict=True):
            if (
                _from_stat(os.fstat(marker.descriptor)) != expected.node
                or os.pread(marker.descriptor, len(expected.content) + 1, 0)
                != expected.content
                or _from_stat(os.fstat(marker.descriptor)) != expected.node
                or (marker.target.advisory and not marker.advisory_locked)
            ):
                _fail("actual recovered descriptor changed")
        self._pool.require_current()
        retirements = _close_retirement(plan)
        _close_inputs(plan)
        producers = _close_dependencies(self._pool)
        self._live()
        for marker, expected in zip(self._markers, plan.markers, strict=True):
            if _from_stat(os.fstat(marker.descriptor)) != expected.node:
                _fail("held marker changed during retirement-area observations")
        _close_marker_facts(plan)
        _close_retirement_facts(retirements)
        _close_dependency_facts(self._pool, producers)
        self._live()
        _close_compact_prefix(self._pool._journal, plan)

    def relinquish_public_observations(self, incoming):
        """A real staged owner takes exact released names; old private rights stay.

        This never grants ownership at those public names to this raw owner.
        The separately composed canonical owner must verify incoming FDs itself.
        """
        if self._disposition is not None:
            _fail("ordinary recovery writer handed off")
        self._live()
        if (
            type(incoming) is not _StagedReservationSet
            or incoming._pool is not self._pool
        ):
            _fail("actual same-producer staged descriptor owner required")
        incoming.verify_all()
        previous = dict(self._plan.public_nodes)
        selected = [m for m in incoming._markers if m.target.path in previous]
        if not selected:
            return ()
        if any(
            previous[m.target.path] is not None or not m.created or m.target.advisory
            for m in selected
        ):
            _fail(
                "only actually staged formerly absent native coordinates may hand off"
            )
        paths = {m.target.path for m in selected}
        view = replace(
            self._plan,
            public_nodes=tuple(
                (path, node)
                for path, node in self._plan.public_nodes
                if path not in paths
            ),
        )
        self._verify_view(view)
        incoming.verify_all()
        self._pool._journal.append(
            "control-recovery-public-handoff",
            canonical_json_bytes(
                {
                    "old_recovery_identity": self._plan.identity.uri,
                    "old_group": self._plan.group,
                    "incoming_nodes": _custody_wire(
                        tuple(
                            (m.target.path, incoming._expected[m.target.path])
                            for m in selected
                        )
                    ),
                    "grants_canonical_roles": False,
                }
            ),
        )
        self._verify_view(view)
        incoming.verify_all()
        incoming._close_currentness()
        _close_dependencies(self._pool)
        _close_retirement(view)
        original = _require_recovered_creation(self)
        successor = _recovered_binding(self, view)
        if _require_recovered_creation(self) is not original:
            _fail("original recovered descriptor changed during handoff")
        self._plan = view
        _CREATED_RECOVERIES[self] = successor
        _require_recovered_creation(self)
        return tuple(sorted(paths, key=str))

    def owns(self, path):
        if self._disposition is not None:
            _fail("ordinary recovery writer handed off")
        self.verify_all()
        return any(marker.named == path for marker in self._plan.markers)


@contextmanager
def acquire_layout_recovery_controls(
    pool, plan, *, acknowledged_recovery_identity, allow_host_execution
):
    """Hold new exact FDs/OS locks; never infer canonical roles or recover data."""
    if type(plan) is not _ControlRecoveryPlan or allow_host_execution is not True:
        _fail("explicit current recovery execution authority required")
    current = plan_layout_control_recovery(
        pool, tuple(m.target for m in plan.markers), reservation_group=plan.group
    )
    if current != plan or acknowledged_recovery_identity != current.identity:
        _fail("exact fresh recovery proposal acknowledgement required")
    journal = pool._journal
    if (
        len(journal._events) + 2 > journal._budget.maximum_events
        or sum(len(raw) for _, raw in journal._known.values()) + 256 * 1024
        > journal._budget.maximum_storage_bytes
    ):
        _fail("recovery acquisition exceeds remaining journal budget")
    error, trace = None, None
    stack = ExitStack()
    held = _HeldDirectories(stack)
    owned = _RecoveredControlSet(pool, plan, held)
    with _disposition_exit_boundary(owned), stack:
        try:
            for path, _ in plan.lineages:
                held.pin(path)
            _require_inputs(pool, plan)
            from .retained_layout_disposition_history import acquisition_bytes

            data = acquisition_bytes(plan.identity.uri, plan.compact_anchor)
            journal.append("control-recovery-acquisition-intent", data)
            _require_inputs(pool, plan)
            for item in plan.markers:
                fd = os.open(
                    item.named.name,
                    os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                    dir_fd=held.nodes[item.named.parent][0],
                )
                try:
                    marker = _OwnedMarker(
                        item.target,
                        fd,
                        (item.node.device, item.node.inode, item.node.mode),
                        item.content,
                        created=False,
                    )
                    owned._markers.append(marker)
                except BaseException as setup_error:
                    try:
                        os.close(fd)
                    except BaseException as close_error:
                        raise combine_body_and_release_errors(
                            "recovered descriptor setup",
                            setup_error,
                            setup_error.__traceback__,
                            close_error,
                        ) from None
                    raise
                if (
                    _from_stat(os.fstat(fd)) != item.node
                    or os.pread(fd, len(item.content) + 1, 0) != item.content
                    or layout_entry_node(item.named) != item.node
                ):
                    _fail("opened recovered marker differs from proposal")
                if item.target.advisory:
                    _acquire(fd, item.named, timeout_seconds=0.0)
                    marker.advisory_locked = True
            owned._complete = True
            _CREATED_RECOVERIES[owned] = _recovered_binding(owned, plan)
            owned.verify_all()
            journal.append("control-recovery-acquisition-observed", data)
            owned.verify_all()
            yield owned
            owned.verify_all()
        except BaseException as exc:
            error, trace = exc, exc.__traceback__
            _raise_disposition_outcome(owned, exc)
            raise
        finally:
            _CREATED_RECOVERIES.pop(owned, None)
            try:
                owned._release()
            except BaseException as release_error:
                if error is not None:
                    combined = combine_body_and_release_errors(
                        "recovered control", error, trace, release_error
                    )
                    _raise_disposition_outcome(owned, combined)
                    raise combined from None
                _raise_disposition_outcome(owned, release_error)
                raise
