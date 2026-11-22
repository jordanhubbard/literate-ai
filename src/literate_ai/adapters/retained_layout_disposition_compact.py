"""Versioned immutable control subrecords, never descriptor or effect authority.

The actual journal producer authenticates input bytes and funds decoding before
calling this pure codec. A completed payload chain is still incomplete without
its separately durable decision and completion events. Legacy record validation
and actual fresh native factories remain necessary after expansion.
"""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass

from literate_ai.contracts.identity import canonical_json_bytes

from .retained_layout_forest_disposition_transcript import _regular
from .retained_layout_forest_recovery_transcript import (
    _directory,
    _fields,
    _identity,
    _path,
    _same,
)

MANIFEST_SCHEMA = "literate-ai/control-disposition-manifest@1"
STEP_SCHEMA = "literate-ai/control-disposition-subrecord@1"
MANIFEST_MAGIC = b"literate-ai-control-disposition-manifest@1\n"
STEP_MAGIC = b"literate-ai-control-disposition-subrecord@1\n"
BEGIN = "recovery-control-batch-intent"
DECISION = "recovery-control-batch-decision"
COMPLETE = "recovery-control-batch-observed"
_NORMAL = "recovery-control-normalization-intent"
_RETIRE = "recovery-control-retirement-intent"
_OPEN = object()
_ABSENT = object()


def _fail(message):
    raise ValueError("layout.disposition-compact: " + message)


def _digest(value):
    if (
        type(value) is not str
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        _fail("plain content digest required")
    return value


def _document(raw, maximum):
    if type(raw) is not bytes or not 0 < len(raw) <= maximum:
        _fail("bounded immutable document required")
    value = json.loads(raw)
    if type(value) is not dict or canonical_json_bytes(value) != raw:
        _fail("plain canonical document required")
    return value


def _bounded_payloads(payloads, maximum, payload_limit, storage_limit):
    if (
        type(maximum) is not int
        or not 1 <= maximum <= 16 * 1024**2
        or type(payload_limit) is not int
        or not 1 <= payload_limit <= 256
        or type(storage_limit) is not int
        or not 1 <= storage_limit <= 64 * 1024**2
        or type(payloads) is not tuple
        or len(payloads) > payload_limit
    ):
        _fail("finite immutable payload snapshot and original limits required")
    total = 0
    for pair in payloads:
        if type(pair) is not tuple or len(pair) != 2:
            _fail("immutable content-addressed payload pair required")
        digest, raw = pair
        _digest(digest)
        if type(raw) is not bytes or len(raw) > maximum:
            _fail("payload exceeds original individual byte policy")
        total += len(raw)
        if total > storage_limit:
            _fail("payloads exceed original aggregate byte policy")
    result = dict(payloads)
    if len(result) != len(payloads):
        _fail("payload snapshot repeats a content address")
    for digest, raw in payloads:
        if hashlib.sha256(raw).hexdigest() != digest:
            _fail("payload content address differs")
    return result


def _head(value):
    if value is not None:
        _digest(value)


@dataclass(frozen=True, slots=True)
class _Manifest:
    raw: bytes
    header: bytes
    namespace: str
    epoch: str
    state: str
    barrier: str
    actions: tuple[bytes, ...]

    @property
    def identity(self):
        return json.loads(self.header)["disposition_identity"]

    @property
    def digest(self):
        return hashlib.sha256(self.raw).hexdigest()

    @property
    def pending_index(self):
        return len(self.actions) - 1


def manifest_bytes(header, namespace, epoch, state, barrier, actions):
    """Encode only explicit data descriptions; no live owner is serialized."""
    return MANIFEST_MAGIC + canonical_json_bytes(
        dict(
            schema=MANIFEST_SCHEMA,
            header=header,
            namespace=namespace,
            epoch=epoch,
            state=state,
            barrier=barrier,
            actions=actions,
        )
    )


def decode_manifest(raw, *, payloads, maximum, payload_limit, storage_limit):
    payloads = _bounded_payloads(payloads, maximum, payload_limit, storage_limit)
    if type(raw) is not bytes or not raw.startswith(MANIFEST_MAGIC):
        _fail("versioned disposition manifest required")
    if len(raw) > maximum:
        _fail("manifest exceeds original payload policy")
    doc = _document(raw[len(MANIFEST_MAGIC) :], maximum)
    _fields(doc, "schema header namespace epoch state barrier actions")
    if doc["schema"] != MANIFEST_SCHEMA:
        _fail("unsupported disposition manifest")
    header = doc["header"]
    _fields(
        header,
        "source_phase_identity disposition_identity retirement_root "
        "retirement_node data_identity qualified",
    )
    for key in ("source_phase_identity", "disposition_identity", "data_identity"):
        _identity(header[key])
    if header["qualified"] is not False:
        _fail("manifest cannot restore qualification")
    retirement, root = (
        _path(header["retirement_root"]),
        _directory(header["retirement_node"]),
    )
    if stat.S_IMODE(root.mode) != 0o700:
        _fail("mode0700 private retirement node required")
    _identity(doc["namespace"])
    _identity(doc["epoch"])
    if type(doc["state"]) is not str or doc["state"] not in {
        "committed-unqualified",
        "original-data-restored-unqualified",
    }:
        _fail("exact unqualified recovery state required")
    barrier = _path(doc["barrier"])
    actions = doc["actions"]
    if type(actions) is not list or not 1 <= len(actions) <= 1024:
        _fail("finite complete control action roster required")
    native, seen, frozen, retired = False, set(), [], 0
    sources = set()
    for position, action in enumerate(actions):
        _fields(
            action,
            "kind group path source destination original_node node "
            "before_payload original_payload source_parent destination_parent",
        )
        kind, group, path = action["kind"], action["group"], _path(action["path"])
        if (
            type(kind) is not str
            or kind not in {_NORMAL, _RETIRE}
            or type(group) is not str
            or not 1 <= len(group) <= 256
        ):
            _fail("bounded original control action required")
        if (group, path) in seen:
            _fail("control repeats within compact roster")
        seen.add((group, path))
        source = _path(action["source"])
        if (
            source in sources
            or source == retirement
            or source.is_relative_to(retirement)
        ):
            _fail("control sources must be distinct and outside new retirement area")
        sources.add(source)
        before, original = _regular(action["node"]), _regular(action["original_node"])
        if before.device != root.device:
            _fail("control escapes original filesystem")
        if any(
            getattr(before, key) != getattr(original, key)
            for key in (
                "device",
                "inode",
                "mode",
                "links",
                "uid",
                "gid",
                "native_identity",
                "link_target",
            )
        ):
            _fail("control differs from original lease inode")
        for key, node in (("before_payload", before), ("original_payload", original)):
            digest = _digest(action[key])
            if digest not in payloads or len(payloads[digest]) != node.size:
                _fail("actual before-control payload required")
            if hashlib.sha256(payloads[digest]).hexdigest() != digest:
                _fail("control payload digest differs")
        if kind == _NORMAL:
            if native or any(
                action[key] is not None
                for key in ("destination", "source_parent", "destination_parent")
            ):
                _fail("normalization follows native retirement or invents parents")
            if _path(action["source"]) != path:
                _fail("normalization must retain its named control coordinate")
            from .retained_layout_reservations import _PREFIX

            if not payloads[action["original_payload"]].startswith(_PREFIX):
                _fail("normalization requires original advisory reservation bytes")
            if payloads[action["before_payload"]] == b"\0":
                _fail("already normalized control cannot be an action")
        else:
            native = True
            if (
                _path(action["source"]) != path
                or _path(action["destination"]) != retirement / f"control-{retired}"
            ):
                _fail("exact ordered retirement coordinate required")
            parents = (
                _directory(action["source_parent"]),
                _directory(action["destination_parent"]),
            )
            if (
                parents[0].device != root.device
                or parents[1].directory_identity != root.directory_identity
            ):
                _fail("initial retirement parent differs")
            retired += 1
            if (path == barrier) is not (position == len(actions) - 1):
                _fail("pending barrier must be the last native action")
        frozen.append(canonical_json_bytes(action))
    if not native or json.loads(frozen[-1])["path"] != str(barrier):
        _fail("complete pending-last control roster required")
    return _Manifest(
        raw,
        canonical_json_bytes(header),
        doc["namespace"],
        doc["epoch"],
        doc["state"],
        str(barrier),
        tuple(frozen),
    )


def step_bytes(manifest, index, previous, kind, data):
    prefix = STEP_MAGIC + manifest.digest.encode("ascii") + b"\n"
    return prefix + canonical_json_bytes(
        dict(
            schema=STEP_SCHEMA,
            batch=manifest.digest,
            index=index,
            previous=previous,
            kind=kind,
            data=data,
        )
    )


def _step(manifest, raw, maximum):
    prefix = STEP_MAGIC + manifest.digest.encode("ascii") + b"\n"
    if type(raw) is not bytes or not raw.startswith(prefix) or len(raw) > maximum:
        _fail("bounded matching batch subrecord required")
    value = _document(raw[len(prefix) :], maximum)
    _fields(value, "schema batch index previous kind data")
    index = value["index"]
    if (
        value["schema"] != STEP_SCHEMA
        or value["batch"] != manifest.digest
        or type(index) is not int
        or not 0 <= index < 2 * len(manifest.actions)
    ):
        _fail("subrecord escapes exact declared roster")
    if value["previous"] is not None:
        _digest(value["previous"])
    action = json.loads(manifest.actions[index // 2])
    kind = (
        action["kind"]
        if index % 2 == 0
        else action["kind"].removesuffix("-intent") + "-observed"
    )
    if value["kind"] != kind:
        _fail("subrecord escapes exact action schedule")
    data = value["data"]
    names = (
        "operation group path source_phase_identity original_node node before_payload"
    )
    if action["kind"] == _RETIRE:
        names += " source destination source_parent destination_parent"
    if index % 2:
        names += " observed_node"
    _fields(data, names)
    operation = data["operation"]
    if (
        type(operation) is not str
        or len(operation) != 32
        or any(c not in "0123456789abcdef" for c in operation)
    ):
        _fail("exact native operation identity required")
    header = json.loads(manifest.header)
    if data["source_phase_identity"] != header["source_phase_identity"] or any(
        not _same(data[key], action[key])
        for key in ("group", "path", "original_node", "node", "before_payload")
    ):
        _fail("subrecord differs from declared held control")
    if action["kind"] == _RETIRE:
        if any(data[key] != action[key] for key in ("source", "destination")) or any(
            _directory(data[key]).directory_identity
            != _directory(action[key]).directory_identity
            for key in ("source_parent", "destination_parent")
        ):
            _fail("subrecord changes initial parent identity or coordinate")
    if index % 2:
        before, after = _regular(data["node"]), _regular(data["observed_node"])
        if action["kind"] == _NORMAL:
            if after.size != 1 or any(
                getattr(before, key) != getattr(after, key)
                for key in (
                    "device",
                    "inode",
                    "mode",
                    "links",
                    "uid",
                    "gid",
                    "native_identity",
                    "link_target",
                )
            ):
                _fail("normalization changed immutable control custody")
        elif before.after_rename() != after.after_rename():
            _fail("retirement changed original native control custody")
    return value


def expand_batch(
    manifest_raw,
    payloads,
    *,
    maximum,
    payload_limit,
    storage_limit,
    expanded_limit,
    decision=_ABSENT,
    complete=_ABSENT,
    closed_head=_OPEN,
):
    """Expand immutable bytes into legacy descriptive records, not writer grants.

    The caller authenticates physical boundary events and passes their heads.
    An abandoned batch must be frozen by the subsequent actual acquisition head.
    Accept the immutable manifest bytes again, never a caller's cached decoded
    projection. The caller prepays manifest decoding as well as step decoding.
    """
    manifest = decode_manifest(
        manifest_raw,
        payloads=payloads,
        maximum=maximum,
        payload_limit=payload_limit,
        storage_limit=storage_limit,
    )
    if type(expanded_limit) is not int or expanded_limit < 1:
        _fail("explicit prepaid expansion byte bound required")
    for supplied in (decision, complete, closed_head):
        if supplied is not _ABSENT and supplied is not _OPEN:
            _head(supplied)
    prefix = STEP_MAGIC + manifest.digest.encode("ascii") + b"\n"
    boundary = {
        "source_phase_identity": json.loads(manifest.header)["source_phase_identity"],
        "disposition_identity": manifest.identity,
        "state": manifest.state,
        "qualified": False,
    }
    release = canonical_json_bytes({**boundary, "pending_control": manifest.barrier})
    completed = canonical_json_bytes(boundary)
    # Each extracted canonical data body is shorter than its original subrecord.
    # Fund the entire possible expansion before constructing decoded step maps.
    expanded_bound = len(manifest.header) + len(release) + len(completed)
    expanded_bound += sum(
        len(raw) for _digest, raw in payloads if raw.startswith(prefix)
    )
    if expanded_bound > expanded_limit:
        _fail("compact expansion exceeds prepaid byte bound")
    indexed = {}
    for digest, raw in payloads:
        if type(raw) is not bytes or not raw.startswith(prefix):
            continue
        _digest(digest)
        if hashlib.sha256(raw).hexdigest() != digest:
            _fail("subrecord content address differs")
        value = _step(manifest, raw, maximum)
        if value["index"] in indexed:
            _fail("forked or repeated compact subrecord")
        indexed[value["index"]] = digest, value
    head, result = None, [("recovery-control-disposition-intent", manifest.header)]
    operations = set()
    decision_index = 2 * manifest.pending_index
    for index in range(len(indexed)):
        if index not in indexed:
            _fail("gap in compact subrecord prefix")
        if index == decision_index:
            if decision is _ABSENT:
                _fail("pending retirement precedes durable decision")
            if decision != head:
                _fail("decision does not bind exact preceding prefix")
            result.append(
                (
                    "recovery-control-release-decision",
                    canonical_json_bytes(
                        {**boundary, "pending_control": manifest.barrier}
                    ),
                )
            )
        digest, value = indexed[index]
        if value["previous"] != head:
            _fail("compact predecessor differs")
        if index % 2 == 0:
            operation = value["data"]["operation"]
            if operation in operations:
                _fail("native operation identity repeats within compact batch")
            operations.add(operation)
        if index % 2:
            previous = indexed[index - 1][1]["data"]
            if not _same({key: value["data"][key] for key in previous}, previous):
                _fail("observation differs from its exact intent")
        head = digest
        result.append((value["kind"], canonical_json_bytes(value["data"])))
    if decision is not _ABSENT and len(indexed) <= decision_index:
        if len(indexed) != decision_index or decision != head:
            _fail("decision precedes its complete prefix")
        result.append(
            (
                "recovery-control-release-decision",
                canonical_json_bytes({**boundary, "pending_control": manifest.barrier}),
            )
        )
    if closed_head is not _OPEN and closed_head != head:
        _fail("acquisition does not freeze exact abandoned prefix")
    if complete is not _ABSENT:
        if (
            len(indexed) != 2 * len(manifest.actions)
            or complete != head
            or decision is _ABSENT
        ):
            _fail("completion lacks exact complete decision and receipts")
        result.append(
            ("recovery-control-disposition-observed", canonical_json_bytes(boundary))
        )
    return tuple(result)
