"""Durable original observations before any canonical publication.

These are bounded descriptions, never reconstructed preparation or effect owners.
Source bytes stay in their original native nodes; every observed metadata body
referenced by this snapshot is separately retained in the actual private journal.
"""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from .repository_refresh_reservations import _custody_wire

_SCHEMA = "literate-ai/layout-original-state@1"
_EVENT = "source-original-state-durable"


def _fail(message):
    raise ValueError("layout.original-state: " + message)


def _children(value):
    if is_dataclass(value):
        return (getattr(value, f.name) for f in fields(value))
    if type(value) is dict:
        return (part for pair in value.items() for part in pair)
    if type(value) is tuple:
        return iter(value)
    return iter(())


def _fund(ledger, value, depth=0):
    # Encoding reuses existing immutable scalar observations. Fund its new
    # wire/normalized containers, digest/decimal/path wrappers and mapping/array
    # slots before allocation. The metadata multiplier covers temporary copies,
    # encoded output and peak buffers. Fresh JSON decoding has its own full
    # per-value/key accounting in the separately funded reader below.
    if depth > 96:
        _fail("original description nesting exceeds its bound")
    count, size = 0, 128
    if is_dataclass(value):
        count, size = 3, size + 96 * len(fields(value))
    elif type(value) is dict:
        count, size = 3, size + 96 * len(value)
    elif type(value) is tuple:
        count, size = 2, size + 64 * len(value)
    elif type(value) is bytes:
        count, size = 5, size + 256
    elif isinstance(value, Path):
        count = 1
    elif type(value) is int and not -(2**63) <= value <= 2**63 - 1:
        count, size = 4, size + 6 * len(str(value))
    if isinstance(value, (str, Path)):
        size += 6 * len(str(value))
    ledger.charge_records(count, size)
    for child in _children(value):
        _fund(ledger, child, depth + 1)


def _bodies(value):
    if type(value) is bytes:
        yield value
    for child in _children(value):
        yield from _bodies(child)


def _role_document(context, facts, namespace):
    from .retained_layout_source_roles import _input_commitments

    return {
        "schema": "literate-ai/original-source-roles@1",
        "namespace": namespace.identity.uri,
        "roles": facts.roles,
        "directories": facts.directories,
        "controls": facts.controls,
        "graph": facts.graph.identity.uri,
        "prospective": canonical_identity(_custody_wire(context.prospective)).uri,
        "origin": facts.origin.to_dict(),
        "provider": None if facts.provider is None else facts.provider.identity.uri,
        "inputs": _custody_wire(_input_commitments(facts.inputs)),
        "framework": facts.framework,
        "children": facts.children,
        "imported": facts.imported,
        "imported_directories": facts.imported_directories,
        "authored": facts.authored,
    }


def _census_parts(census):
    # Complete semantic fields; the physical table is derived losslessly from
    # the separately retained full native roster, not stored a second time.
    return (
        tuple(
            getattr(census.tree, f.name)
            for f in fields(census.tree)
            if f.name != "_physical"
        ),
        census.framework_files,
        census.other_files,
        census.shared_directories,
        census._lineage,
    )


def _census_document(census):
    return {
        **{
            f.name: _custody_wire(getattr(census, f.name))
            for f in fields(census)
            if f.name != "tree"
        },
        "tree": {
            f.name: _custody_wire(getattr(census.tree, f.name))
            for f in fields(census.tree)
            if f.name != "_physical"
        },
    }


def _persist_original_state(admission):
    from .bounded_role_observation import _activate_role_observation
    from .retained_layout_control_publication import _publication_history
    from .retained_layout_source_admission import _record as admission_record
    from .retained_layout_source_namespace import _record as namespace_record
    from .retained_layout_source_roles import (
        _ADMISSION_BINDINGS,
        _ADMITTED,
        _BOUND,
        _FACTS,
        _require_registration,
    )
    from .retained_layout_transaction import _require_prepared

    if admission_record(admission.preparation) is not admission:
        _fail("actual original admission required")
    original, pool = admission.original, admission.pool
    owner = _BOUND.get(admission.preparation)

    def require_original():
        if (
            owner in _ADMITTED
            or owner in _ADMISSION_BINDINGS
            or admission.provider is not None
            or admission.phase is not None
            or admission.controls is not None
        ):
            _fail("original unbound preparation role observations required")
        return _require_registration(admission.preparation, original)

    # Registration funds the actual private writer. Original role observations
    # stay with their creating preparation until the durable snapshot closes;
    # a source phase and its provider-role permissions do not yet exist.
    context = require_original()
    journal, plan, ledger = pool._journal, original.plan, original.ledger
    with _activate_role_observation(original.reader, _borrow=True):
        namespace = namespace_record(context.namespace, reading=True)
        facts = _FACTS[owner]
        if _publication_history(pool) or namespace.controlled is not None:
            _fail("unpublished original namespace required")
        if any(event["kind"] == _EVENT for event in journal.events):
            _fail("original state may be persisted only once")
        # All traversal roots are actual sealed participant fields, never a
        # caller-provided census or replacement namespace.
        descriptions = (
            plan,
            _census_parts(namespace.census),
            namespace.native,
            facts.inputs,
            facts.roles,
            facts.directories,
            facts.graph,
            facts.framework,
            facts.children,
            facts.imported,
            facts.imported_directories,
            facts.authored,
        )
        _fund(ledger, descriptions)
        ledger.charge_records(256, 65536)
        role_document = _role_document(context, facts, namespace)
        if canonical_identity(role_document) != facts.identity:
            _fail("original role description differs from acknowledged facts")
        document = {
            "schema": _SCHEMA,
            "source_phase_identity": plan.identity.uri,
            "namespace": {
                "identity": namespace.identity.uri,
                "document": {
                    "schema": "literate-ai/original-project-namespace@1",
                    "namespace": namespace.census.identity.uri,
                    "native": canonical_identity(_custody_wire(namespace.native)).uri,
                },
                "census": _census_document(namespace.census),
                "native": _custody_wire(namespace.native),
            },
            "partition": {
                "identity": facts.identity.uri,
                "document": role_document,
                "graph": facts.graph.document,
                "inputs": _custody_wire(facts.inputs),
            },
        }
        # Pack byte witnesses so a large original metadata roster does not
        # consume one journal payload slot per input file. The immutable journal
        # payload/count/storage policy remains unchanged.
        bodies = {
            hashlib.sha256(body).hexdigest(): body for body in _bodies(descriptions)
        }
        body_size = sum(map(len, bodies.values()))
        if body_size > journal._budget.maximum_storage_bytes:
            _fail("original byte witnesses exceed original journal storage")
        ledger.charge_records(16 + 4 * len(bodies), body_size + 128 * len(bodies))
        index, offset = {}, 0
        for digest, body in sorted(bodies.items()):
            index[digest] = [offset, len(body)]
            offset += len(body)
        packed = b"".join(bodies[digest] for digest in sorted(bodies))
        ceiling = journal._budget.maximum_payload_bytes
        chunks = tuple(
            packed[start : start + ceiling] for start in range(0, len(packed), ceiling)
        )
        document["byte_witnesses"] = {
            "chunks": [hashlib.sha256(chunk).hexdigest() for chunk in chunks],
            "size": body_size,
            "index": index,
        }
        raw = canonical_json_bytes(document)
        plan_raw = canonical_json_bytes(plan.document)
        payloads = {hashlib.sha256(chunk).hexdigest(): chunk for chunk in chunks}
        payloads[hashlib.sha256(raw).hexdigest()] = raw
        payloads[hashlib.sha256(plan_raw).hexdigest()] = plan_raw
        # Refuse the complete private write set before the first payload write.
        # The journal's own immutable policy and the original admission reserve
        # still cover every write, including its native temporary stages.
        fresh = {d: b for d, b in payloads.items() if d not in journal._payloads}
        if (
            any(
                len(body) > journal._budget.maximum_payload_bytes
                for body in payloads.values()
            )
            or len(journal._payloads) + len(fresh) > journal._budget.maximum_events
            or len(journal._events) >= journal._budget.maximum_events
            or len(journal._stages) >= journal._budget.maximum_stages
            or sum(len(body) for body in fresh.values())
            + sum(len(value[1]) for value in journal._known.values())
            + 4096
            > journal._budget.maximum_storage_bytes
        ):
            _fail(
                "complete original state exceeds the original journal policy "
                f"(largest payload {max(map(len, payloads.values()))}, "
                f"payload count {len(journal._payloads) + len(fresh)}, "
                f"new bytes {sum(map(len, fresh.values()))})"
            )
        # Opening preparation validation and the original sealed observations
        # authenticate these private descriptions. The full closing validation
        # below follows every blocking write and precedes admission/effects.
        for body in payloads.values():
            journal.store_payload(body)
        journal.append(
            _EVENT,
            canonical_json_bytes(
                {
                    "source_phase_identity": plan.identity.uri,
                    "state_payload_digest": hashlib.sha256(raw).hexdigest(),
                    "grants_move_authority": False,
                }
            ),
        )
        # Blocking durable writes may race external changes. Close the same
        # original participants again before canonical acquisition can begin.
        _require_prepared(plan)
        owner.require_current()
        if (
            admission_record(admission.preparation) is not admission
            or require_original() is not context
            or namespace_record(context.namespace, references=True) is not namespace
            or _publication_history(pool)
        ):
            _fail("original participants changed during persistence")


def _read_original_state(
    journal, phase_identity=None, *, budget, maximum_metadata_bytes
):
    """Validate durable descriptions; grant no read, publication or recovery lease."""
    from .catalog_copy_plan import _Observation
    from .retained_layout_journal import _require_live_layout_journal

    _require_live_layout_journal(journal)
    allowance = _Observation(budget, maximum_metadata_bytes, ())

    known = journal._known

    def close_journal():
        # require_current rereads the COMPLETE namespace. Fund that operation,
        # including its largest transient read, before calling the native reader.
        count, total, peak = 0, 0, 0
        for _node, body in known.values():
            size = len(body)
            if size > budget.maximum_file_bytes:
                _fail("journal record exceeds fresh per-file read policy")
            count, total, peak = count + 1, total + size, max(peak, size)
        allowance.files += count
        allowance.bytes += total
        allowance.charge_records(2 * count, total + peak + 1)
        roster = tuple(known.items())
        journal.require_current(_expected=roster)
        if journal._known is not known:
            _fail("original journal roster changed during read")
        _require_live_layout_journal(journal)
        if (
            journal._known is not known
            or len(known) != len(roster)
            or any(known.get(name) is not expected for name, expected in roster)
        ):
            _fail("funded journal roster changed after native closure")

    close_journal()

    def decode(raw):
        # Conservative lexical bound before JSON decoding. Punctuation within
        # strings may overcount; it cannot undercount a JSON value/key roster.
        count = 1 + sum(raw.count(c) for c in (b",", b":", b"[", b"{"))
        allowance.charge_records(count, 4 * len(raw))
        value = json.loads(raw)
        if canonical_json_bytes(value) != raw:
            _fail("noncanonical original payload")
        return value

    def payload(digest):
        if digest not in journal._payloads:
            _fail("payload-not-recorded")
        raw = known[f"p-{digest}.bin"][1]
        if hashlib.sha256(raw).hexdigest() != digest:
            _fail("original payload digest changed")
        return raw

    def load(digest):
        raw = payload(digest)
        return raw, decode(raw)

    binding = decode(known["header.json"][1])["binding"]
    if phase_identity is None:
        phase_identity = binding.get("source_phase_identity")
    if binding != {
        "schema": "literate-ai/layout-transaction-binding@1",
        "source_phase_identity": phase_identity,
        "original_state_required": True,
    }:
        _fail("requested phase differs from actual journal binding")
    events = tuple(decode(known[name][1]) for name in journal._events)
    matches = [event["data"] for event in events if event["kind"] == _EVENT]
    if len(matches) != 1 or matches[0].get("source_phase_identity") != phase_identity:
        _fail("one bound durable original state required")
    event = matches[0]
    raw, document = load(event["state_payload_digest"])
    plan_raw, plan_document = load(phase_identity.removeprefix("sha256:"))
    if (
        canonical_json_bytes(document) != raw
        or hashlib.sha256(raw).hexdigest() != event["state_payload_digest"]
        or document.get("schema") != _SCHEMA
        or document.get("source_phase_identity") != phase_identity
        or canonical_json_bytes(plan_document) != plan_raw
        or canonical_identity(plan_document).uri != phase_identity
    ):
        _fail("noncanonical or unbound original state")
    plan = plan_document["plan"]
    namespace, partition = document["namespace"], document["partition"]
    if (
        set(document)
        != {
            "schema",
            "source_phase_identity",
            "namespace",
            "partition",
            "byte_witnesses",
        }
        or set(namespace) != {"identity", "document", "census", "native"}
        or set(partition) != {"identity", "document", "graph", "inputs"}
        or set(document["byte_witnesses"]) != {"chunks", "size", "index"}
    ):
        _fail("unexpected original-state description fields")
    if (
        canonical_identity(namespace["document"]).uri != plan["project_namespace"]
        or namespace["identity"] != plan["project_namespace"]
        or canonical_identity(partition["document"]).uri != plan["project_roles"]
        or partition["identity"] != plan["project_roles"]
        or partition["document"]["namespace"] != namespace["identity"]
        or canonical_identity(partition["graph"]).uri != partition["document"]["graph"]
    ):
        _fail("original namespace or partition commitment changed")
    _validate_description(document, plan)

    witnesses = document["byte_witnesses"]
    roster = witnesses["chunks"]
    size = witnesses["size"]
    ceiling = journal._budget.maximum_payload_bytes
    # Ordered references may repeat: identical chunks occupy one immutable
    # physical payload, but every occurrence contributes to the expanded body.
    # Match the writer's fixed-width packing and original logical storage bound
    # before allocating the expanded bytes; event slots bound physical records.
    if (
        type(size) is not int
        or not 0 <= size <= journal._budget.maximum_storage_bytes
        or type(roster) is not list
        or len(roster) != (size + ceiling - 1) // ceiling
    ):
        _fail("original byte chunk roster exceeds its finite packing policy")
    total = sum(
        len(known[f"p-{digest}.bin"][1])
        for digest in roster
        if digest in journal._payloads
    )
    if total > journal._budget.maximum_storage_bytes:
        _fail("original byte chunk storage exceeds journal policy")
    allowance.charge_records(4 * len(witnesses["index"]) + len(roster), 2 * total)
    chunks = tuple(payload(digest) for digest in roster)
    if total != size or any(
        len(chunk) != min(ceiling, size - i * ceiling) for i, chunk in enumerate(chunks)
    ):
        _fail("original byte witness size changed")
    packed = b"".join(chunks)
    cursor = 0
    for digest, (offset, size) in sorted(witnesses["index"].items()):
        if offset != cursor or type(size) is not int or not 0 <= size <= total - cursor:
            _fail("original byte witness partition changed")
        if (
            hashlib.sha256(memoryview(packed)[offset : offset + size]).hexdigest()
            != digest
        ):
            _fail("original raw metadata body changed")
        cursor += size
    if cursor != total:
        _fail("original byte witness partition is incomplete")

    def require_bodies(value):
        if type(value) is dict:
            if set(value) == {"content_identity"}:
                identity = value["content_identity"]
                if (
                    not identity.startswith("sha256:")
                    or identity[7:] not in witnesses["index"]
                ):
                    _fail("original raw metadata body unavailable")
            else:
                for child in value.values():
                    require_bodies(child)
        elif type(value) is list:
            for child in value:
                require_bodies(child)

    require_bodies(plan)
    require_bodies(partition["inputs"])
    result = _SavedOriginalState(document, packed, plan_document, events)
    close_journal()
    return result


@dataclass(frozen=True, slots=True)
class _SavedOriginalState:
    """Decoded data with no participant identity or permission to act."""

    document: dict
    packed: bytes
    plan_document: dict
    events: tuple

    def body(self, digest):
        offset, size = self.document["byte_witnesses"]["index"][digest]
        body = self.packed[offset : offset + size]
        if hashlib.sha256(body).hexdigest() != digest:
            _fail("original raw metadata body changed")
        return body


def _validate_description(document, plan):
    from literate_ai.contracts.blobs import BlobRef
    from literate_ai.contracts.native_sdk_trees import NativeSdkAlias
    from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

    from .retained_cargo_tree_v2 import RetainedCargoInputTreeV2
    from .retained_layout_effect_graph import _source_effect_graph
    from .retained_layout_partition import RetainedLayoutPartitionCensus
    from .retained_layout_recovery_data import _decode

    namespace, partition = document["namespace"], document["partition"]
    value = _decode(namespace["census"])
    data = value["tree"]
    native = _decode(namespace["native"])

    def physical(node):
        base = (node["device"], node["inode"], node["mode"])
        owners = (node["uid"], node["gid"])
        if stat.S_ISDIR(node["mode"]):
            return (*base, *owners)
        return (
            *base,
            node["size"],
            node["modified_ns"],
            node["changed_ns"],
            node["links"],
            *owners,
        )

    physical_nodes = tuple((name, physical(node)) for name, node in native)
    if not physical_nodes or physical_nodes[0][0] != "" or "_physical" in data:
        _fail(
            "complete original native roster required without duplicate physical table"
        )
    tree = RetainedCargoInputTreeV2(
        Path(data["root"]),
        RetainedCargoInputBudget.from_dict(data["budget"]),
        data["exclusions"],
        data["directories"],
        tuple(
            (name, BlobRef(**blob), executable)
            for name, blob, executable in data["files"]
        ),
        tuple(NativeSdkAlias(**alias) for alias in data["aliases"]),
        data["maximum_metadata_bytes"],
        (physical_nodes[0][1], physical_nodes[1:]),
    )
    census = RetainedLayoutPartitionCensus(
        tree,
        value["framework_files"],
        value["other_files"],
        value["shared_directories"],
        value["_lineage"],
    )
    role_document = partition["document"]
    graph = partition["graph"]
    if (
        tree.root != Path(plan["root"])
        or namespace["document"]["namespace"] != census.identity.uri
        or canonical_identity(namespace["native"]).uri
        != namespace["document"]["native"]
        or tree.exclusions
        or canonical_json_bytes(
            _source_effect_graph(
                tree,
                _decode(role_document["roles"]),
                _decode(role_document["directories"]),
                graph["source"],
                graph["destination"],
                protected_directories=tuple(graph["protected_directories"]),
            ).document
        )
        != canonical_json_bytes(graph)
        or role_document["prospective"] != canonical_identity(plan["prospective"]).uri
    ):
        _fail(
            "complete original namespace or effect graph differs from acknowledgement"
        )
    from .repository_refresh import RefreshFileObservation
    from .retained_layout_source_roles import _input_commitments

    inputs = tuple(
        RefreshFileObservation(Path(item["path"]), _decode(item["signature"]), None)
        for item in partition["inputs"]
    )
    # Contents are digest references on disk. Match the exact original path,
    # native signature and content digest roster without substituting live reads.
    commitments = _custody_wire(_input_commitments(inputs))
    for commitment, item in zip(commitments, partition["inputs"], strict=True):
        commitment[2] = (
            None
            if item["content"] is None
            else item["content"]["content_identity"].removeprefix("sha256:")
        )
    if commitments != role_document["inputs"]:
        _fail("original role input commitments changed")
