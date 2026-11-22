"""Actual bounded marker bytes; no forest observation or execution grant."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import retained_layout_forest_disposition_reads as reads


@unittest.skipUnless(os.name == "posix", "POSIX owned-marker metadata")
class OwnedMarkerReadTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve(strict=True)
        self.path = self.root / "marker"
        self.path.write_bytes(b"abc")

    def test_exact_native_body_and_caller_bound_refuse_growth_before_read(self):
        node, content = reads.read_owned_marker(self.path, maximum_bytes=3)
        self.assertEqual(content, b"abc")
        self.assertEqual(node.inode, self.path.stat().st_ino)
        self.path.write_bytes(b"abcd")
        with patch.object(
            reads, "_raw_file", side_effect=AssertionError("over-budget native read")
        ):
            with self.assertRaisesRegex(ValueError, "bounded owned"):
                reads.read_owned_marker(self.path, maximum_bytes=3)
        self.assertEqual(self.path.read_bytes(), b"abcd")

    def test_invalid_allowance_refuses_before_any_native_observation(self):
        with patch.object(
            reads,
            "layout_entry_node",
            side_effect=AssertionError("invalid allowance IO"),
        ):
            for limit in (0, -1, 257, True, None):
                with (
                    self.subTest(limit=limit),
                    self.assertRaisesRegex(ValueError, "finite owned marker"),
                ):
                    reads.read_owned_marker(self.path, maximum_bytes=limit)

    def test_linked_marker_refuses_without_reading_or_changing_foreign_bytes(self):
        alias = self.root / "alias"
        os.link(self.path, alias)
        with patch.object(
            reads, "_raw_file", side_effect=AssertionError("linked marker native read")
        ):
            with self.assertRaisesRegex(ValueError, "bounded owned"):
                reads.read_owned_marker(alias, maximum_bytes=3)
        self.assertEqual(alias.read_bytes(), b"abc")
        self.assertEqual(self.path.read_bytes(), b"abc")
