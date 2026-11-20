"""Real custody with simulated native unsigned64/128 identifiers, not native proof."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai._filesystem import is_stat_identity_value, stat_identity_value
from literate_ai.adapters import native_child_publication as publication
from literate_ai.adapters.native_child_inputs import (
    ChildCaptureLimits,
    capture_child_tree,
    physical_node,
)
from literate_ai.contracts._validation import ContractValidationError
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from tests.critical import test_native_child_publication as fixtures


@contextmanager
def wide_stat_identifiers():
    """Preserve distinct measured nodes while projecting IDs beyond signed64."""
    devices, nodes = {}, {}

    class WideStat:
        def __init__(self, actual):
            self.actual = actual
            self.st_dev = devices.setdefault(actual.st_dev, (1 << 63) + len(devices))
            self.st_ino = nodes.setdefault(
                (actual.st_dev, actual.st_ino), (1 << 127) + len(nodes)
            )

        def __getattr__(self, name):
            return getattr(self.actual, name)

    with ExitStack() as stack:
        for name in ("stat", "lstat", "fstat"):
            actual = getattr(os, name)

            def observe(*args, actual=actual, **kwargs):
                return WideStat(actual(*args, **kwargs))

            stack.enter_context(mock.patch.object(os, name, side_effect=observe))
        yield


class NativeChildWideStatTests(unittest.TestCase):
    def test_legacy_wire_is_unchanged_and_wide_encoding_is_canonical(self):
        node = SimpleNamespace(
            st_dev=7,
            st_ino=11,
            st_mode=33188,
            st_nlink=1,
            st_size=4,
            st_mtime_ns=1700000000000000000,
            st_ctime_ns=1700000000000000001,
            st_uid=501,
            st_gid=20,
        )
        self.assertEqual(
            canonical_json_bytes(physical_node(node)),
            b"[7,11,33188,1,4,1700000000000000000,1700000000000000001,501,20]",
        )
        self.assertEqual(
            canonical_json_bytes(publication._key(node)),
            b"[7,11,33188,1,4,1700000000000000000,501,20]",
        )
        for value in (
            -(1 << 127),
            -(1 << 63) - 1,
            -(1 << 63),
            (1 << 63) - 1,
            1 << 63,
            (1 << 64) - 1,
            (1 << 128) - 1,
        ):
            with self.subTest(value=value):
                encoded = stat_identity_value(value)
                self.assertEqual(int(encoded), value)
                self.assertTrue(is_stat_identity_value(encoded))
                canonical_json_bytes(encoded)
        with self.assertRaises(ContractValidationError):
            canonical_json_bytes(1 << 63)

    def test_malformed_or_ambiguous_identity_fields_are_refused(self):
        for value in (
            True,
            False,
            1.5,
            None,
            [],
            {},
            1 << 63,
            "0",
            "1",
            "-0",
            "+9223372036854775808",
            "09223372036854775808",
            " 9223372036854775808",
            "9223372036854775808 ",
            "９２２３３７２０３６８５４７７５８０８",
            "9.223372036854776e18",
            str(1 << 128),
            str(-(1 << 127) - 1),
        ):
            with self.subTest(value=value):
                self.assertFalse(is_stat_identity_value(value))
                self.assertFalse(publication._node_shape([value, 1, 33188], 3))
        for value in (True, 1 << 128, -(1 << 127) - 1):
            with self.assertRaises(ValueError):
                stat_identity_value(value)
        wide = str(1 << 127)
        self.assertTrue(publication._node_shape([wide, wide, 33188], 3))
        self.assertFalse(publication._node_shape([wide, wide, "33188"], 3))
        self.assertFalse(publication._node_shape([wide, wide, True], 3))

    def test_capture_keeps_full_wide_identifiers_and_detects_equal_byte_replacement(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root = base / "child"
            root.mkdir()
            source = root / "source"
            source.write_bytes(b"unchanged source")
            with wide_stat_identifiers():
                before = capture_child_tree(root, ChildCaptureLimits())
                self.assertIsInstance(before["root_node"][0], str)
                self.assertGreaterEqual(int(before["root_node"][0]), 1 << 63)
                self.assertGreaterEqual(int(before["root_node"][1]), 1 << 127)
                self.assertEqual(before, capture_child_tree(root, ChildCaptureLimits()))
                canonical_json_bytes(before)
                source.rename(base / "retained-source")
                source.write_bytes(b"unchanged source")
                self.assertNotEqual(
                    before, capture_child_tree(root, ChildCaptureLimits())
                )

    def test_complete_publication_journal_recovers_wide_node_records(self):
        fixture = fixtures.NativeChildPublicationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        with wide_stat_identifiers():
            identity = publication.prepare_native_child_publication(
                fixture.root,
                plan_identity=fixture.plan,
                previous=fixture.old,
                proposed=fixture.new,
                reviewed_plan=canonical_json_bytes({"metadata-only": True}) + b"\n",
            )
            marker = json.loads((fixture.metadata / publication._ACTIVE).read_bytes())
            attempt = fixture.metadata / publication._HISTORY / marker["attempt"]
            intent = json.loads((attempt / "intent.json").read_bytes())
            for key in ("root_node", "metadata_node", "activation_node"):
                self.assertIsInstance(intent[key][0], str)
                self.assertIsInstance(intent[key][1], str)
            for node in (
                intent["reviewed_plan"]["node"],
                *intent["terminals"].values(),
                *(
                    item[side]["node"]
                    for item in intent["targets"]
                    for side in ("before", "after")
                ),
            ):
                self.assertIsInstance(node[0], str)
                self.assertIsInstance(node[1], str)
                self.assertTrue(all(type(value) is int for value in node[2:]))
            result = publication.recover_native_child_publication(
                fixture.root,
                publication_identity=identity,
                finish=True,
                validate=lambda: fixture.verify(fixture.new),
            )
            self.assertEqual(result["state"], "committed")
            self.assertEqual(
                publication.inspect_native_child_publication(
                    fixture.root,
                    publication_identity=identity,
                    attempt_name=attempt.name,
                )["state"],
                "committed",
            )
            self.assertEqual(canonical_identity(marker).uri, identity)
