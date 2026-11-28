"""Compact descriptions reject ambiguous histories; these grant no native rights."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_layout_disposition_compact as codec
from literate_ai.adapters.exclusive_entry import layout_entry_node
from literate_ai.adapters.repository_refresh_reservations import _custody_wire
from literate_ai.contracts.identity import canonical_json_bytes


class CompactDispositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.retirement = self.root / "retirement"
        self.retirement.mkdir(mode=0o700)
        self.barrier = self.root / "pending"
        self.barrier.write_bytes(b"pending")
        self.payloads = []
        self.options = dict(
            maximum=1024**2, payload_limit=256, storage_limit=16 * 1024**2
        )
        identity = "sha256:" + "1" * 64
        self.header = dict(
            source_phase_identity=identity,
            disposition_identity="sha256:" + "2" * 64,
            retirement_root=str(self.retirement),
            retirement_node=_custody_wire(layout_entry_node(self.retirement)),
            data_identity="sha256:" + "3" * 64,
            qualified=False,
        )
        self.actions = [self.action(self.barrier, 0)]

    def keep(self, raw):
        digest = hashlib.sha256(raw).hexdigest()
        if not any(old == digest for old, _raw in self.payloads):
            self.payloads.append((digest, raw))
        return digest

    def action(self, path, ordinal):
        node = _custody_wire(layout_entry_node(path))
        digest = self.keep(path.read_bytes())
        return dict(
            kind=codec._RETIRE,
            group="actual-description-group",
            path=str(path),
            source=str(path),
            destination=str(self.retirement / f"control-{ordinal}"),
            original_node=node,
            node=node,
            before_payload=digest,
            original_payload=digest,
            source_parent=_custody_wire(layout_entry_node(path.parent)),
            destination_parent=self.header["retirement_node"],
        )

    def manifest(self, **overrides):
        document = dict(
            header=self.header,
            namespace="sha256:" + "4" * 64,
            epoch="sha256:" + "5" * 64,
            state="committed-unqualified",
            barrier=str(self.barrier),
            actions=self.actions,
        )
        document.update(overrides)
        raw = codec.manifest_bytes(**document)
        return codec.decode_manifest(raw, payloads=tuple(self.payloads), **self.options)

    def data(self, action, operation="a" * 32):
        result = {
            key: action[key]
            for key in ("group", "path", "original_node", "node", "before_payload")
        }
        result.update(
            operation=operation,
            source_phase_identity=self.header["source_phase_identity"],
        )
        if action["kind"] == codec._RETIRE:
            result.update(
                (key, action[key])
                for key in (
                    "source",
                    "destination",
                    "source_parent",
                    "destination_parent",
                )
            )
        return result

    def step(self, manifest, index, previous, data, kind=None):
        action = json.loads(manifest.actions[index // 2])
        if kind is None:
            kind = action["kind"]
            if index % 2:
                kind = kind.removesuffix("-intent") + "-observed"
        return self.keep(codec.step_bytes(manifest, index, previous, kind, data))

    def expand(self, manifest, **boundaries):
        return codec.expand_batch(
            manifest.raw,
            tuple(self.payloads),
            **self.options,
            expanded_limit=16 * 1024**2,
            **boundaries,
        )

    def pair(self, manifest, index=0, previous=None):
        intent = self.data(json.loads(manifest.actions[index // 2]))
        first = self.step(manifest, index, previous, intent)
        observed = dict(intent, observed_node=intent["node"])
        return self.step(manifest, index + 1, first, observed)

    def test_empty_head_decision_is_distinct_from_absent_decision(self):
        manifest = self.manifest()
        head = self.pair(manifest)
        with self.assertRaisesRegex(ValueError, "precedes durable decision"):
            self.expand(manifest)
        records = self.expand(manifest, decision=None, complete=head)
        self.assertEqual(len(records), 5)
        self.assertEqual(records[1][0], "recovery-control-release-decision")
        self.assertEqual(records[-1][0], "recovery-control-disposition-observed")
        with self.assertRaisesRegex(ValueError, "completion lacks"):
            self.expand(manifest, decision=None, complete=None)

    def test_manifest_namespace_and_epoch_are_bound_by_step_content_address(self):
        manifest = self.manifest()
        head = self.pair(manifest)
        for key in ("namespace", "epoch"):
            with self.subTest(key=key):
                changed = self.manifest(**{key: "sha256:" + "6" * 64})
                self.assertEqual(changed.identity, manifest.identity)
                self.assertNotEqual(changed.digest, manifest.digest)
                with self.assertRaisesRegex(ValueError, "completion lacks"):
                    self.expand(changed, decision=None, complete=head)

    def test_cached_projection_cannot_change_expansion_under_original_digest(self):
        manifest = self.manifest()
        head = self.pair(manifest)
        header = dict(self.header, disposition_identity="sha256:" + "9" * 64)
        changed = replace(manifest, header=canonical_json_bytes(header), actions=())
        self.assertEqual(changed.digest, manifest.digest)
        options = dict(self.options, expanded_limit=16 * 1024**2)
        with self.assertRaisesRegex(ValueError, "versioned disposition manifest"):
            codec.expand_batch(changed, tuple(self.payloads), **options)
        records = self.expand(changed, decision=None, complete=head)
        self.assertEqual(json.loads(records[0][1]), self.header)
        self.assertEqual(len(records), 5)

    def test_roster_rejects_reused_physical_source_and_retirement_overlap(self):
        other = self.root / "other"
        other.write_bytes(b"other")
        first = self.action(other, 0)
        duplicate = copy.deepcopy(first)
        duplicate["group"] = "different-generation"
        with self.assertRaisesRegex(ValueError, "sources must be distinct"):
            self.manifest(actions=[first, duplicate, self.actions[0]])
        for path in (self.retirement, self.retirement / "control-0"):
            action = dict(self.actions[0], path=str(path), source=str(path))
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "outside new retirement"):
                    self.manifest(actions=[action], barrier=str(path))

    def test_normalization_requires_original_reservation_and_public_coordinate(self):
        path = self.root / "advisory"
        path.write_bytes(b"literate-ai-refresh-reservation\noriginal")
        action = self.action(path, 0)
        action.update(
            kind=codec._NORMAL,
            destination=None,
            source_parent=None,
            destination_parent=None,
        )
        manifest = self.manifest(actions=[action, self.actions[0]])
        intent = self.data(action)
        first = self.step(manifest, 0, None, intent)
        changed = dict(intent["node"], size=1, uid=intent["node"]["uid"] + 1)
        self.step(manifest, 1, first, dict(intent, observed_node=changed))
        with self.assertRaisesRegex(ValueError, "immutable control custody"):
            self.expand(manifest)
        with self.assertRaisesRegex(ValueError, "named control coordinate"):
            self.manifest(
                actions=[
                    dict(action, source=str(self.root / "private")),
                    self.actions[0],
                ]
            )
        with self.assertRaisesRegex(ValueError, "original advisory reservation"):
            self.manifest(
                actions=[
                    dict(
                        action,
                        original_payload=self.actions[0]["original_payload"],
                        original_node=self.actions[0]["original_node"],
                        node=self.actions[0]["node"],
                        before_payload=self.actions[0]["before_payload"],
                    ),
                    self.actions[0],
                ]
            )

    def test_retirement_observation_cannot_change_bytes_or_inode(self):
        manifest = self.manifest()
        intent = self.data(self.actions[0])
        first = self.step(manifest, 0, None, intent)
        changed = dict(intent["node"], size=intent["node"]["size"] + 1)
        self.step(manifest, 1, first, dict(intent, observed_node=changed))
        with self.assertRaisesRegex(ValueError, "original native control custody"):
            self.expand(manifest, decision=None)

    def test_forks_gaps_and_wrong_predecessors_refuse(self):
        manifest = self.manifest()
        intent = self.data(self.actions[0])
        base = tuple(self.payloads)
        cases = (
            ((0, None, intent), (0, None, dict(intent, operation="b" * 32))),
            ((1, None, dict(intent, observed_node=intent["node"])),),
            ((0, "0" * 64, intent),),
        )
        for rows in cases:
            with self.subTest(rows=rows):
                self.payloads[:] = base
                for index, previous, data in rows:
                    self.step(manifest, index, previous, data)
                with self.assertRaisesRegex(ValueError, "forked|gap|predecessor"):
                    self.expand(manifest, decision=None)

    def test_interrupted_prefix_cannot_gain_receipts_after_acquisition_freeze(self):
        other = self.root / "other"
        other.write_bytes(b"other")
        first_action = self.action(other, 0)
        last_action = dict(
            self.actions[0], destination=str(self.retirement / "control-1")
        )
        manifest = self.manifest(actions=[first_action, last_action])
        head = self.pair(manifest)
        self.assertEqual(len(self.expand(manifest, closed_head=head)), 3)
        intent = self.data(last_action, operation="b" * 32)
        self.step(manifest, 2, head, intent)
        with self.assertRaisesRegex(ValueError, "freeze exact abandoned prefix"):
            self.expand(manifest, decision=head, closed_head=head)

    def test_payload_and_expansion_limits_refuse_before_subrecord_decoding(self):
        manifest = self.manifest()
        self.pair(manifest)
        for overrides, message in (
            ({"payload_limit": 1}, "finite immutable"),
            ({"storage_limit": 1}, "aggregate byte"),
            ({"expanded_limit": 1}, "prepaid byte bound"),
        ):
            options = dict(self.options, expanded_limit=16 * 1024**2)
            options.update(overrides)
            with self.subTest(overrides=overrides):
                with mock.patch.object(
                    codec,
                    "_step",
                    side_effect=AssertionError(
                        "subrecords decoded before resource preflight"
                    ),
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        codec.expand_batch(
                            manifest.raw, tuple(self.payloads), **options
                        )
        for name in ("decision", "complete", "closed_head"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "plain content digest"):
                    self.expand(manifest, **{name: False})

    def test_manifest_rejects_nonprivate_root_and_untyped_nested_values(self):
        header = copy.deepcopy(self.header)
        header["retirement_node"]["mode"] = 0o40755
        with self.assertRaisesRegex(ValueError, "mode0700"):
            self.manifest(header=header)
        with self.assertRaises(ValueError):
            self.manifest(actions=[[]])
        with self.assertRaises(ValueError):
            self.manifest(state=[])
        with self.assertRaises(ValueError):
            self.manifest(actions=[dict(self.actions[0], kind=[])])
