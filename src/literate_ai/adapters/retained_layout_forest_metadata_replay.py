"""Metadata receipt-prefix descriptions; saved bytes never restore effect rights.

Only exact original/prospective targets and native entry receipts may project the
recorded source namespace. Potential staged names without an inode witness stay
explicitly unrecorded, even when their bytes might match a prospective payload.
"""

from __future__ import annotations

import hashlib
import stat
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)

from .catalog_copy_plan import _Observation
from .retained_layout_forest_native import _Action, _advance_move, _rows
from .retained_layout_forest_program_read import _initial_node
from .retained_layout_forest_span import _SpanRoot
from .retained_layout_journal import _LIVE_ROOTS
from .retained_layout_recovery_data import _decode
from .retained_layout_source_state import _SavedOriginalState
from .retained_layout_transaction import (
    _LIFT,
    HARNESS_WRAPPER_FILENAME,
    RETAINED_LAYOUT_PATH,
)

_TARGETS = (HARNESS_WRAPPER_FILENAME, _LIFT, RETAINED_LAYOUT_PATH)
_KINDS = frozenset(
    {
        "metadata-quarantine-intent",
        "metadata-quarantine-observed",
        "metadata-publication-intent",
        "metadata-publication-observed",
        "layout-metadata-observed",
    }
)
_EFFECT_FIELDS = frozenset(
    {
        "schema",
        "metadata",
        "retirement",
        "parking",
        "metadata_allowance",
        "finalization_allowance",
        "journal_tail",
        "metadata_steps",
        "marker_count",
        "json_nodes_per_event",
        "event_preview_identities",
    }
)


def _fail(message):
    raise ValueError("layout.forest-metadata-replay: " + message)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class _MetadataPending:
    kind: str
    action: object
    data: dict


@dataclass(frozen=True, slots=True)
class _MetadataFrontier:
    span: object
    pending: object
    refresh_directories: tuple
    unrecorded_stages: tuple
    complete: bool
    metadata_root: Path
    metadata_lineage: tuple
    retirement_root: Path
    retirement_node: object
    retirement_lineage: tuple
    started: bool = True
    future_roots: tuple = ()


def _pin(value):
    if type(value) is not list or len(value) != 3 or type(value[0]) is not str:
        _fail("exact recorded future private pin required")
    root, node, lineage = Path(value[0]), _initial_node(value[1]), _decode(value[2])
    if (
        not root.is_absolute()
        or ".." in root.parts
        or not stat.S_ISDIR(node.mode)
        or stat.S_IMODE(node.mode) != 0o700
        or type(lineage) is not tuple
        or len(lineage) != len(root.parts)
        or any(
            type(row) is not tuple
            or len(row) != 6
            or type(row[0]) is not str
            or any(type(v) is not int for v in row[1:])
            for row in lineage
        )
        or tuple(row[0] for row in lineage)
        != tuple(str(p) for p in (*reversed(root.parents), root))
        or lineage[-1] != (str(root), *node.directory_identity[:-1])
    ):
        _fail("direct mode0700 future private root and exact ancestry required")
    return root, node, lineage


def _apart(root, lineage, other, other_lineage):
    if (
        root.is_relative_to(other)
        or other.is_relative_to(root)
        or lineage[-1][1:3] in {row[1:3] for row in other_lineage}
        or other_lineage[-1][1:3] in {row[1:3] for row in lineage}
    ):
        _fail("future private metadata/retirement overlaps an actual participant")


def _parent_name(name):
    parent = Path(name).parent.as_posix()
    return "" if parent == "." else parent


def _with_node(span, area, name, node):
    roots = list(span.roots)
    nodes = dict(roots[area].native)
    nodes[name] = node
    roots[area] = replace(roots[area], native=_rows(nodes))
    return replace(span, roots=tuple(roots))


def _bound_effects(saved, program, native, effects, allowance):
    """Validate original bound data even when no metadata effect has begun."""
    if (
        type(effects) is not dict
        or set(effects) != _EFFECT_FIELDS
        or (
            effects["schema"] != "literate-ai/forest-bound-effects@1"
            or effects["parking"] != str(program.private_root)
            or _decode(effects["journal_tail"]) != program.journal_tail
        )
    ):
        _fail("exact original future-effects description required")
    count = sum(len(root.native) for root in native.span.roots)
    allowance.charge_records(256 + 48 * count, 131072 + 16384 * count)
    metadata, initial, lineage = _pin(effects["metadata"])
    retirement, retired_node, retirement_lineage = _pin(effects["retirement"])
    _apart(metadata, lineage, retirement, retirement_lineage)
    for root in native.span.roots:
        _apart(metadata, lineage, root.root, root.lineage)
        _apart(retirement, retirement_lineage, root.root, root.lineage)
        if any(
            node.device != root.native[0][1].device for node in (initial, retired_node)
        ):
            _fail("metadata and original source require one filesystem")
    all_original_ids = {
        (n.device, n.inode) for r in program.span.roots for _, n in r.native
    }
    if any(
        (node.device, node.inode) in all_original_ids
        for node in (initial, retired_node)
    ):
        _fail("future private root aliases an original native entry")
    phase = program.source_phase_identity
    plan = saved.plan_document["plan"]
    root = native.span.roots[0].root
    if (
        canonical_identity(saved.plan_document).uri != phase
        or saved.document["source_phase_identity"] != phase
        or plan["root"] != str(root)
        or program.span.roots[0].root != root
    ):
        _fail("metadata descriptions belong to another original source")
    parking = tuple(
        unicodedata.normalize("NFC", part).casefold()
        for part in program.private_root.parts
    )
    for future in (metadata, retirement):
        parts = tuple(
            unicodedata.normalize("NFC", part).casefold() for part in future.parts
        )
        if parts[: len(parking)] == parking or parking[: len(parts)] == parts:
            _fail("future private root overlaps original parking coordinate")
    return metadata, initial, lineage, retirement, retired_node, retirement_lineage


def replay_forest_metadata(saved, program, native, effects, *, allowance):
    """Replay already bound descriptions, without current I/O or any lease grant."""
    if type(saved) is not _SavedOriginalState or type(allowance) is not _Observation:
        _fail("complete original data and explicit fresh allowance required")
    if not native.complete or native.pending is not None or native.refresh_directories:
        _fail("complete recorded native source before metadata required")
    metadata, initial, lineage, retirement, retired_node, retirement_lineage = (
        _bound_effects(saved, program, native, effects, allowance)
    )
    phase = program.source_phase_identity
    plan = saved.plan_document["plan"]
    root = native.span.roots[0].root
    inputs = {item["path"]: item for item in plan["inputs"]}
    prospective = dict(plan["prospective"])
    source_nodes = dict(program.span.roots[0].native)
    current_nodes = dict(native.span.roots[0].native)
    source_blobs = {n: b for n, b, _ in program.span.roots[0].payloads}
    area = len(native.span.roots)
    steps = []
    for index, name in enumerate(_TARGETS):
        before = inputs[str(root / name)]
        old_node = source_nodes.get(name)
        signature = (
            None
            if old_node is None
            else (
                old_node.device,
                old_node.inode,
                old_node.mode,
                old_node.size,
                old_node.modified_ns,
                old_node.changed_ns,
            )
        )
        if (
            _decode(before["signature"]) != signature
            or current_nodes.get(name) != old_node
        ):
            _fail("canonical metadata target is not fixed original native state")
        references = (before["content"], prospective[name])
        raw = []
        for reference in references:
            if reference is None:
                raw.append(None)
                continue
            identity = reference["content_identity"].removeprefix("sha256:")
            size = saved.document["byte_witnesses"]["index"][identity][1]
            if size > min(
                allowance.budget.maximum_file_bytes,
                program.span.budget.maximum_file_bytes,
            ):
                _fail("original metadata body exceeds fresh file limit")
            allowance.bytes += size
            allowance.charge_records(4, 4 * size)
            raw.append(saved.body(identity))
        old, new = raw
        if new is None or (old is None) != (old_node is None):
            _fail("complete original/prospective metadata bytes required")
        if old_node is not None:
            blob = source_blobs.get(name)
            if (
                not stat.S_ISREG(old_node.mode)
                or old_node.links != 1
                or old_node.uid != initial.uid
                or blob is None
                or (blob.digest, blob.size) != (_digest(old), len(old))
            ):
                _fail("old metadata differs from its complete original commitment")
            action = _Action("metadata", 0, name, area, f"old-{index}")
            steps.append(("metadata-quarantine", action, old, old_node, index))
        action = _Action("metadata", area, f"new-{index}", 0, name)
        steps.append(("metadata-publication", action, new, old_node, index))
    if effects["metadata_steps"] != len(steps):
        _fail("future metadata count differs from exact original programme")
    span = replace(
        native.span,
        budget=allowance.budget,
        maximum_metadata_bytes=allowance.metadata,
        roots=(*native.span.roots, _SpanRoot(metadata, lineage, (("", initial),), ())),
    )
    dirty, witnessed = set(), set()
    pending, cursor, complete = None, 0, False
    native_ends = [
        i for i, e in enumerate(saved.events) if e["kind"] == "forest-native-complete"
    ]
    if len(native_ends) != 1:
        _fail("one complete recorded native prefix required")

    def parent(area_index, name, document):
        nonlocal span
        name = _parent_name(name)
        old = dict(span.roots[area_index].native)[name]
        node = _initial_node(document)
        if node.directory_identity != old.directory_identity or (
            (area_index, name) not in dirty and node != old
        ):
            _fail("metadata intent changes unowned native parent facts")
        span = _with_node(span, area_index, name, node)
        dirty.discard((area_index, name))

    for position, event in enumerate(saved.events):
        kind, data = event["kind"], event["data"]
        if kind not in _KINDS:
            continue
        if position <= native_ends[0] or data.get("source_phase_identity") != phase:
            _fail("metadata appears before native completion or in another phase")
        if kind == "layout-metadata-observed":
            if (
                data.get("qualified") is not False
                or complete
                or pending is not None
                or cursor != len(steps)
                or data
                != {
                    "source_phase_identity": phase,
                    "state": "metadata-published-finalization-pending",
                    "qualified": False,
                }
            ):
                _fail("metadata completion lacks its exact complete entry prefix")
            complete = True
            continue
        if complete or cursor >= len(steps):
            _fail("metadata entry exceeds the exact original programme")
        base, action, content, template, index = steps[cursor]
        if kind == base + "-intent":
            if (
                pending is not None
                or set(data)
                != {
                    "source_phase_identity",
                    "source",
                    "destination",
                    "source_node",
                    "source_parent",
                    "destination_parent",
                    "payload_digest",
                }
                or data["payload_digest"] != _digest(content)
            ):
                _fail("exact next original metadata intent required")
            source = span.roots[action.source_area].root / action.source
            destination = span.roots[action.destination_area].root / action.destination
            if (data["source"], data["destination"]) != (str(source), str(destination)):
                _fail("metadata intent escapes original public/private coordinates")
            node = _initial_node(data["source_node"])
            if (
                not stat.S_ISREG(node.mode)
                or node.links != 1
                or node.uid != initial.uid
            ):
                _fail("owned single-link direct metadata entry required")
            if not cursor:
                # Staging precedes this prefix but had no per-stage inode record.
                # No unrecorded name is admitted by this parent stamp alone.
                dirty.add((area, ""))
            if base == "metadata-publication":
                ids = {(n.device, n.inode) for r in span.roots for _, n in r.native}
                if (
                    (node.device, node.inode) in ids
                    or node.device != initial.device
                    or node.size != len(content)
                    or (
                        template is not None
                        and (node.mode, node.gid) != (template.mode, template.gid)
                    )
                    or (template is None and stat.S_IMODE(node.mode) & ~0o600)
                ):
                    _fail("prospective stage changes its template or aliases an entry")
                roots = list(span.roots)
                private = roots[area]
                roots[area] = replace(
                    private,
                    native=_rows({**dict(private.native), action.source: node}),
                    payloads=tuple(
                        sorted(
                            (
                                *private.payloads,
                                (
                                    action.source,
                                    BlobRef(_digest(content), len(content)),
                                    bool(node.mode & 0o111),
                                ),
                            )
                        )
                    ),
                )
                span = replace(span, roots=tuple(roots))
                witnessed.add(index)
            elif node != dict(span.roots[0].native).get(action.source):
                _fail("quarantine intent substitutes the original metadata inode")
            parent(action.source_area, action.source, data["source_parent"])
            parent(
                action.destination_area, action.destination, data["destination_parent"]
            )
            pending = _MetadataPending(kind, action, data)
        elif kind == base + "-observed":
            if pending is None or data != {
                **pending.data,
                "observed_node": data.get("observed_node"),
            }:
                _fail("metadata observation lacks its exact original intent")
            node = _initial_node(data["observed_node"])
            before = dict(span.roots[action.source_area].native)[action.source]
            if node.after_rename() != before.after_rename():
                _fail("metadata observed entry changed original native custody")
            span = _advance_move(
                span,
                action,
                node,
                dict(span.roots[action.source_area].native)[
                    _parent_name(action.source)
                ],
                dict(span.roots[action.destination_area].native)[
                    _parent_name(action.destination)
                ],
            )
            dirty.update(
                (
                    (action.source_area, _parent_name(action.source)),
                    (action.destination_area, _parent_name(action.destination)),
                )
            )
            pending, cursor = None, cursor + 1
        else:
            _fail("metadata entry is duplicated, reordered or outside its programme")
    return _MetadataFrontier(
        span,
        pending,
        tuple(sorted(dirty)),
        tuple(metadata / f"new-{i}" for i in range(3) if i not in witnessed),
        complete,
        metadata,
        lineage,
        retirement,
        retired_node,
        retirement_lineage,
        True,
        (_SpanRoot(retirement, retirement_lineage, (("", retired_node),), ()),),
    )


def _acquired_partition(document, phase, graph):
    """Validate observation data; never reconstruct its former live participant."""
    required = {
        "schema",
        "identity",
        "source_phase_identity",
        "namespace_identity",
        "roles",
        "directories",
        "source_effect_graph",
    }
    if (
        type(document) is not dict
        or not required <= set(document)
        or set(document) - required - {"framework_update", "catalog_copy"}
        or document["schema"] != "literate-ai/layout-owned-partition-observation@1"
        or document["source_phase_identity"] != phase
        or canonical_json_bytes(document["source_effect_graph"])
        != canonical_json_bytes(graph)
        or type(document["roles"]) is not list
        or type(document["directories"]) is not list
    ):
        _fail("actual acquired partition observation schema/phase/graph required")
    ContentIdentity.parse_uri(document["identity"])
    ContentIdentity.parse_uri(document["namespace_identity"])


def _prefix_document(value, digest, label):
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(c not in "0123456789abcdef" for c in digest)
    ):
        _fail("exact original input payload identity required")
    name = f"p-{digest}.bin"
    row = value.journal._known.get(name)
    if (
        row is None
        or _digest(row[1]) != digest
        or not any(key == name and original is row for key, original in value.prefix)
    ):
        _fail("durable original-prefix input payload required")
    raw = row[1]
    if len(raw) > value.ledger.budget.maximum_file_bytes:
        _fail("input payload exceeds fresh per-file policy")
    value.ledger.charge_records(128, 4 * len(raw))
    document = value.ledger.json_value(raw, label)
    if canonical_json_bytes(document) != raw:
        _fail("canonical original input payload required")
    return document


def _current_bound_domains(value, result):
    """Original future pins remain separate from actual fresh producer domains."""
    storage = value.selection.path.parent
    anchor, storage_lineage = value.ledger.ancestry[value.selection.path]
    for root, lineage in (
        (result.metadata_root, result.metadata_lineage),
        (result.retirement_root, result.retirement_lineage),
    ):
        for producer in (value.pool.root, _LIVE_ROOTS[value.journal]):
            _apart(root, lineage, producer, value.reader._lineages[producer])
        if (
            root.is_relative_to(storage)
            or storage.is_relative_to(root)
            or lineage[-1][1:3] in {row[1:3] for row in storage_lineage}
            or (
                anchor == storage
                and storage_lineage[-1][1:3] in {row[1:3] for row in lineage}
            )
        ):
            _fail("future private root overlaps actual canonical storage")


def load_forest_metadata_frontier(observer):
    """Read only a real observer's sealed journal prefix; return descriptive data."""
    from .retained_layout_forest_observation import _record

    value = _record(observer, reading=True)
    events = value.saved.events
    intents = [
        (i, e["data"])
        for i, e in enumerate(events)
        if e["kind"] == "forest-source-intent"
    ]
    metadata_events = any(e["kind"] in _KINDS for e in events)
    if not intents:
        if metadata_events:
            _fail("metadata records lack the original bound future effect paths")
        return None
    if len(intents) != 1:
        _fail("one exact original forest source intent required")
    index, data = intents[0]
    legacy = {
        "source_phase_identity",
        "native_program_identity",
        "effects_payload_digest",
        "partition_payload_digest",
    }
    current = {
        "schema",
        "source_phase_identity",
        "native_program_identity",
        "original_partition_identity",
        "effects_payload_digest",
        "acquired_partition_payload_digest",
    }
    if (
        type(data) is not dict
        or set(data) not in (legacy, current)
        or (
            data["source_phase_identity"] != value.program.source_phase_identity
            or data["native_program_identity"] != value.program.identity.uri
        )
    ):
        _fail("original future effects belong to another native source programme")
    if set(data) == current:
        if (
            data["schema"] != "literate-ai/forest-source-intent@2"
            or data["original_partition_identity"]
            != value.saved.document["partition"]["identity"]
        ):
            _fail("source intent changed its original partition commitment")
        acquired = data["acquired_partition_payload_digest"]
    else:
        # The original producer stored an acquired observation here, never the
        # earlier original-role identity document. Legacy records stay distinct.
        acquired = data["partition_payload_digest"]
        if acquired is None:
            _fail("legacy source intent requires its acquired observation payload")
    durable = [
        i for i, e in enumerate(events) if e["kind"] == "source-original-state-durable"
    ]
    starts = [i for i, e in enumerate(events) if e["kind"] == "forest-native-start"]
    if len(durable) != 1 or len(starts) != 1 or not durable[0] < index < starts[0]:
        _fail("future effect binding is outside durable-original/native-start order")
    if acquired is not None:
        document = _prefix_document(value, acquired, "forest-acquired-partition")
        _acquired_partition(
            document, value.program.source_phase_identity, value.program.graph.document
        )
    effects = _prefix_document(
        value, data["effects_payload_digest"], "forest-metadata-bound-effects"
    )
    if not value.frontier.complete:
        if metadata_events:
            _fail("metadata records require complete original native movement")
        metadata, initial, lineage, retirement, retired_node, retirement_lineage = (
            _bound_effects(
                value.saved, value.program, value.frontier, effects, value.ledger
            )
        )
        parent = value.reader._lineages[value.program.private_root.parent]
        for node in (initial, retired_node):
            if node.device != parent[-1][1] or (node.device, node.inode) in {
                row[1:3] for row in parent
            }:
                _fail("future private root overlaps actual parking ancestry")
        # Keep original native area indices until pending-before/after
        # classification. The current observer joins these two original empty
        # roots only afterward, before its complete no-follow native closure.
        future_roots = (
            _SpanRoot(metadata, lineage, (("", initial),), ()),
            _SpanRoot(retirement, retirement_lineage, (("", retired_node),), ()),
        )
        result = _MetadataFrontier(
            replace(
                value.frontier.span,
                budget=value.ledger.budget,
                maximum_metadata_bytes=value.ledger.metadata,
            ),
            None,
            value.frontier.refresh_directories,
            (),
            False,
            metadata,
            lineage,
            retirement,
            retired_node,
            retirement_lineage,
            False,
            future_roots,
        )
    else:
        result = replay_forest_metadata(
            value.saved, value.program, value.frontier, effects, allowance=value.ledger
        )
    _current_bound_domains(value, result)
    if _record(observer, reading=True) is not value:
        _fail("actual creating metadata observation ended")
    return result
