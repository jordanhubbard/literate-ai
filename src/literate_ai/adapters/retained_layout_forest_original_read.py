"""Original-to-runtime forest descriptions; no restored canonical ownership."""

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from .catalog_copy_plan import _Observation
from .repository_refresh_reservations import _custody_wire
from .retained_layout_forest_program_read import _initial_node
from .retained_layout_forest_span import _from_namespace
from .retained_layout_recovery_data import _decode
from .retained_layout_source_state import (
    _namespace_description,
    _read_original_state,
    _SavedOriginalState,
    _validate_description,
)


def _fail(message):
    raise ValueError("layout.forest-original-read: " + message)


def bind_original_native_program(saved, program, payloads, *, allowance):
    """Validate descriptive source custody across recorded control publication.

    This compares data only. Publication records do not enroll their former
    issuer, recover descriptors or grant permission to touch any current endpoint.
    """
    if type(saved) is not _SavedOriginalState or type(allowance) is not _Observation:
        _fail("complete saved original and explicit fresh allowance required")
    document, plan_document = saved.document, saved.plan_document
    plan = plan_document["plan"]
    partition = document["partition"]
    count = len(document["namespace"]["native"]) + len(partition["document"]["roles"])
    count += len(program.span.roots[0].native) + len(saved.events)
    allowance.charge_records(128 + 32 * count, 65536 + 8192 * count)
    phase = canonical_identity(plan_document).uri
    original_events = [
        e["data"] for e in saved.events if e["kind"] == "source-original-state-durable"
    ]
    if (
        len(original_events) != 1
        or original_events[0]["source_phase_identity"] != phase
        or original_events[0]["state_payload_digest"]
        != hashlib.sha256(canonical_json_bytes(document)).hexdigest()
        or document["source_phase_identity"] != phase
        or program.source_phase_identity != phase
        or plan.get("source_forest") is None
    ):
        _fail("native program is not bound to the complete original forest")
    durable = next(
        index
        for index, event in enumerate(saved.events)
        if event["kind"] == "source-original-state-durable"
    )
    if any(
        index < durable
        and event["kind"]
        in {
            "control-publication-intent",
            "control-publication-observed",
            "forest-native-start",
        }
        for index, event in enumerate(saved.events)
    ):
        _fail("canonical publication or native start appears before durable original")
    _validate_description(document, plan, allowance)
    census, raw_native = _namespace_description(document)
    original = _from_namespace(
        census.tree,
        tuple((name, _initial_node(node)) for name, node in raw_native),
        census._lineage,
    )
    current = program.span.roots[0]
    if current.root != original.root or current.lineage != original.lineage:
        _fail("native program changed original project root or ancestry")
    graph = partition["graph"]
    for name in (
        "source",
        "destination",
        "carriers",
        "retain_directories",
        "create_directories",
        "projection",
        "protected_directories",
    ):
        if getattr(program.graph, name) != _decode(graph[name]):
            _fail("native program changes acknowledged original source schedule")
    nodes = dict(original.native)
    blobs = {name: (blob, mode) for name, blob, mode in original.payloads}
    controls = {original.root / name for name in partition["document"]["controls"]}
    intents, completed, dirty, added_dirs, added_files = {}, set(), set(), set(), set()
    saw_native = False
    for event in saved.events:
        kind, data = event["kind"], event["data"]
        if kind == "forest-native-start":
            saw_native = True
            break
        if kind not in {"control-publication-intent", "control-publication-observed"}:
            continue
        operation = data.get("operation_id")
        if type(operation) is not str or not operation or operation in completed:
            _fail("unique original control publication operation required")
        if kind.endswith("-intent"):
            if operation in intents:
                _fail("duplicate original control publication intent")
            intents[operation] = data
            continue
        intent = intents.pop(operation, None)
        if intent is None or data != {
            **intent,
            "published_node": data.get("published_node"),
        }:
            _fail("control publication observation lacks its exact intent")
        completed.add(operation)
        path = Path(data["destination"])
        staged, node = (
            _initial_node(data["source_node"]),
            _initial_node(data["published_node"]),
        )
        if staged.after_rename() != node.after_rename():
            _fail("control publication changed its staged node")
        if not path.is_relative_to(original.root):
            # External controls grant no in-project namespace changes. Their
            # current canonical rights are the fresh role owner's responsibility.
            continue
        if path not in controls and not any(
            path in target.parents for target in controls
        ):
            _fail("control publication is outside original canonical coordinates")
        if path == original.root or Path(data["source"]).is_relative_to(original.root):
            _fail("control publication cannot borrow original project entries")
        name = path.relative_to(original.root).as_posix()
        parent = path.parent.relative_to(original.root).as_posix()
        parent = "" if parent == "." else parent
        before = _initial_node(data["destination_parent"])
        if (
            name in nodes
            or parent not in nodes
            or nodes[parent].directory_identity != before.directory_identity
            or (parent not in dirty and nodes[parent] != before)
            or any(
                (old.device, old.inode) == (node.device, node.inode)
                for old in nodes.values()
            )
            or any(row[1:3] == (node.device, node.inode) for row in original.lineage)
        ):
            _fail("control publication contradicts original absence or native parent")
        if data["directory"] is True:
            if (
                path in controls
                or data["payload_digest"] is not None
                or not stat.S_ISDIR(node.mode)
                or stat.S_IMODE(node.mode) != 0o700
            ):
                _fail("original canonical parent needs exact staged directory custody")
            added_dirs.add(name)
        elif data["directory"] is False:
            digest = data["payload_digest"]
            body = payloads.get(digest)
            if (
                path not in controls
                or type(body) is not bytes
                or hashlib.sha256(body).hexdigest() != digest
                or not 1 <= len(body) <= 256
                or not stat.S_ISREG(node.mode)
                or stat.S_IMODE(node.mode) != 0o600
                or node.links != 1
                or node.size != len(body)
            ):
                _fail("original canonical marker needs exact bounded payload custody")
            blobs[name] = BlobRef(digest, len(body)), False
            added_files.add(name)
        else:
            _fail("explicit original control publication kind required")
        nodes[name] = node
        nodes[parent] = before
        dirty.add(parent)
    if not saw_native or intents:
        _fail(
            "complete original control publication prefix required before native start"
        )
    actual = dict(current.native)
    if actual.keys() != nodes.keys():
        _fail("native program invents or loses original namespace entries")
    for name, node in nodes.items():
        if (
            name in dirty and actual[name].directory_identity != node.directory_identity
        ) or (name not in dirty and actual[name] != node):
            _fail("native program changes original or published native custody")
    if (
        current.links != original.links
        or {name: (blob, mode) for name, blob, mode in current.payloads} != blobs
        or set(program.graph.fixed_directories)
        != set(graph["fixed_directories"]) | added_dirs
    ):
        _fail("native program changes original bytes, aliases or fixed-directory scope")
    return tuple(sorted(added_files | added_dirs))


def _saved_seal(saved, allowance):
    # Original decoded nodes are already funded by their native reader. Reserve
    # bounded traversal before constructing the small custody wrapper, then fund
    # the actual peak streaming encoder workspace, not another complete JSON DOM
    # and retained body. The exact old canonical byte sequence is still hashed.
    allowance.charge_records(128, 65536)
    refs = _saved_refs(saved)
    wire = _custody_wire(saved)
    limits = _saved_json_limits(wire, maximum_nodes=allowance.metadata // 4096)
    _nodes, longest, slots = limits
    allowance.charge_records(64 + 4 * slots, 4096 + 128 * slots + 64 * longest)
    return refs, _saved_json_digest(wire), limits


def _saved_refs(saved):
    if (
        type(saved) is not _SavedOriginalState
        or type(saved.document) is not dict
        or type(saved.packed) is not bytes
        or type(saved.plan_document) is not dict
        or type(saved.events) is not tuple
        or len(saved.events) > 256
        or any(type(event) is not dict for event in saved.events)
    ):
        _fail("plain saved original data required")
    return saved.document, saved.packed, saved.plan_document, saved.events


def _saved_json_limits(wire, *, maximum_nodes, original=None):
    nodes = longest = 0

    def measure(value, depth=0):
        nonlocal nodes, longest
        if depth > 96:
            _fail("saved original data nesting exceeds its bound")
        nodes += 1
        if nodes > maximum_nodes:
            _fail("saved original data exceeds original streaming allowance")
        if value is None or type(value) is bool:
            return 0
        if type(value) is str:
            longest = max(longest, len(value))
            if original is not None and longest > original[1]:
                _fail("saved original data exceeds original streaming allowance")
            return 0
        if type(value) is int:
            if not -(2**63) <= value < 2**63:
                _fail("saved original data exceeds canonical integer range")
            return 0
        if type(value) is dict:
            if original is not None and len(value) > original[2]:
                _fail("saved original data exceeds original streaming allowance")
            peak = 0
            for key, item in value.items():
                if type(key) is not str:
                    _fail("plain saved original JSON keys required")
                measure(key, depth + 1)
                peak = max(peak, measure(item, depth + 1))
            peak += len(value)
        elif type(value) in (list, tuple):
            peak = 0
            for child in value:
                peak = max(peak, measure(child, depth + 1))
        else:
            _fail("plain saved original canonical JSON required")
        if original is not None and peak > original[2]:
            _fail("saved original data exceeds original streaming allowance")
        return peak

    slots = measure(wire)
    return nodes, longest, slots


def _saved_json_digest(wire):
    # Force the iterator implementation: the one-shot C encoder can retain a
    # complete body. Sorting scratch is bounded by simultaneous ancestor maps;
    # the funded largest-string buffer covers escaping and UTF-8 conversion.
    encoder = json.JSONEncoder(
        ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256()
    for chunk in encoder.iterencode(wire, _one_shot=False):
        digest.update(chunk.encode("utf-8"))
    return digest.digest()


def _close_saved(saved, binding):
    refs, seal, limits = binding
    if any(
        current is not original
        for current, original in zip(_saved_refs(saved), refs, strict=True)
    ):
        _fail("saved original data changed across dependent observations")
    wire = _custody_wire(saved)
    _saved_json_limits(wire, maximum_nodes=limits[0], original=limits)
    if _saved_json_digest(wire) != seal:
        _fail("saved original data changed across dependent observations")


def load_original_native_forest(journal, *, allowance, parking_parent_lineage):
    """Load descriptions without retaining their creating reader's private seal."""
    return _load_original_native_forest(
        journal, allowance=allowance, parking_parent_lineage=parking_parent_lineage
    )[:4]


def _load_original_native_forest(journal, *, allowance, parking_parent_lineage):
    """Load complete original and native data through the same fresh ledger."""
    from .retained_layout_forest_recovery_read import load_native_forest_frontier

    if type(allowance) is not _Observation:
        _fail("explicit fresh original/native allowance required")
    saved = _read_original_state(
        journal,
        budget=allowance.budget,
        maximum_metadata_bytes=allowance.metadata,
        _allowance=allowance,
    )
    binding = _saved_seal(saved, allowance)
    program, frontier = load_native_forest_frontier(
        journal,
        allowance=allowance,
        parking_parent_lineage=parking_parent_lineage,
    )
    _close_saved(saved, binding)
    # Previous funded traversals checked the complete immutable byte roster.
    allowance.charge_records(16 * len(journal._payloads), 65536)
    payloads = {
        digest: journal._known[f"p-{digest}.bin"][1] for digest in journal._payloads
    }
    publications = bind_original_native_program(
        saved, program, payloads, allowance=allowance
    )
    _close_saved(saved, binding)
    return saved, program, frontier, publications, binding
