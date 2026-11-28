"""Typed native program decoding from bounded bytes, never an execution owner."""

from __future__ import annotations

import stat
from dataclasses import fields, replace
from pathlib import Path

from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from .catalog_copy_plan import _Observation
from .retained_layout_effect_graph import _SourceEffectGraph
from .retained_layout_forest_native import (
    _Action,
    _NativeForestProgram,
    plan_native_forest,
)
from .retained_layout_forest_span import _ForestSpan, _shape, _SpanRoot
from .retained_layout_recovery_controls import _node
from .retained_layout_recovery_data import _decode


def _fail(message):
    raise ValueError("layout.forest-program-read: " + message)


def _exact(value, kind):
    if type(value) is not dict or set(value) != {f.name for f in fields(kind)}:
        _fail("exact typed program fields required")
    return value


def _initial_node(value):
    if type(value) is not dict:
        _fail("plain original native node required")
    target = value.get("link_target")
    node = _node(dict(value, link_target=None))
    if target is not None and (
        not stat.S_ISLNK(node.mode)
        or type(target) is not str
        or len(target.encode()) > 4096
    ):
        _fail("bounded original symbolic text required")
    return replace(node, link_target=target)


def _path(value):
    if type(value) is not str:
        _fail("plain program path required")
    return Path(value)


def decode_native_forest_start(raw, *, allowance):
    """Decode the exact forest-native-start payload with a fresh finite policy.

    Only the normal independently acknowledged execution factory may consume a
    program for effects. This decoder creates immutable descriptive data only.
    """
    if (
        type(allowance) is not _Observation
        or type(raw) is not bytes
        or len(raw) > 16 * 1024**2
    ):
        _fail("bounded native start bytes and explicit fresh allowance required")
    # Punctuation inside strings can overcount this lexical bound, never hide
    # JSON values/keys. Reserve both the decoded and typed representations first.
    count = 1 + sum(raw.count(c) for c in (b",", b":", b"[", b"{"))
    allowance.charge_records(128 + 2 * count, 65536 + 8 * len(raw))
    document = allowance.json_value(raw, "native-forest-program-start")
    if (
        type(document) is not dict
        or set(document) != {"program"}
        or canonical_json_bytes(document) != raw
    ):
        _fail("canonical native start document required")
    original = document["program"]
    if (
        type(original) is not dict
        or set(original) != {"schema", "program"}
        or original["schema"] != "literate-ai/native-forest-program@1"
    ):
        _fail("supported native forest program schema required")
    data = _exact(_decode(original["program"]), _NativeForestProgram)
    span = _exact(data["span"], _ForestSpan)
    if type(span["roots"]) is not tuple or len(span["roots"]) != 1:
        _fail("one complete original program namespace required")
    root = _exact(span["roots"][0], _SpanRoot)
    namespace = _SpanRoot(
        _path(root["root"]),
        root["lineage"],
        tuple((name, _initial_node(node)) for name, node in root["native"]),
        tuple(
            (name, BlobRef.from_dict(blob), executable)
            for name, blob, executable in root["payloads"]
        ),
        root["links"],
    )
    observed = _ForestSpan(
        (namespace,),
        RetainedCargoInputBudget.from_dict(span["budget"]),
        span["maximum_metadata_bytes"],
    )
    _shape(observed)
    graph = _SourceEffectGraph(**_exact(data["graph"], _SourceEffectGraph))
    recorded = _NativeForestProgram(
        observed,
        graph,
        _path(data["private_root"]),
        data["source_phase_identity"],
        tuple(
            (slot, name, _initial_node(node))
            for slot, name, node in data["directories"]
        ),
        tuple(_Action(**_exact(action, _Action)) for action in data["actions"]),
        data["required_events"],
        data["maximum_event_bytes"],
        data["usage"],
        data["journal_tail"],
    )
    rebuilt = plan_native_forest(
        observed,
        graph,
        recorded.private_root,
        source_phase_identity=recorded.source_phase_identity,
        journal_tail=recorded.journal_tail,
    )
    expected = canonical_json_bytes(original)
    if (
        canonical_json_bytes(recorded.document) != expected
        or canonical_json_bytes(rebuilt.document) != expected
    ):
        _fail("recorded native program is not its exact deterministic reconstruction")
    return recorded
