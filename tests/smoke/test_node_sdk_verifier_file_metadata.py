"""Bound metadata DATA before original materialization observation."""

import sys
import unittest
from unittest import mock

from literate_ai.adapters import node_sdk_verifier_file_metadata as metadata
from literate_ai.adapters.directory_artifacts import DirectoryExportFile


class FileMetadataTests(unittest.TestCase):
    def file(self, path="value.js", content=b"value"):
        return DirectoryExportFile(path, content, 0o644)

    def test_detaches_rows_and_measures_depth_root_and_repeated_parent_storage(self):
        original = self.file("shared/value.js")
        root, rows, charge = metadata.measure_node_file_metadata(
            "/tmp/sdk", (original,)
        )
        self.assertEqual(root.as_posix(), "/tmp/sdk")
        self.assertEqual(rows, (original,))
        self.assertIsNot(rows[0], original)
        self.assertGreater(charge, 1024 * 1024)
        self.assertLessEqual(charge, metadata.MAXIMUM_FILE_METADATA_BYTES)
        for other_root, other_files in (
            ("/tmp/longer/sdk", (original,)),
            ("/tmp/sdk", (self.file("shared/nested/value.js"),)),
            ("/tmp/sdk", (original, self.file("shared/peer.js"))),
        ):
            with self.subTest(root=other_root, rows=len(other_files)):
                self.assertGreater(
                    metadata.measure_node_file_metadata(other_root, other_files)[2],
                    charge,
                )

    def test_cheap_bounds_refuse_before_canonical_inventory_parsing(self):
        inventories = (
            ("relative", (self.file(),)),
            ("/" + "a" * 4096, (self.file(),)),
            ("/tmp/sdk", (self.file("a/" * 64 + "v.js"),)),
            ("/tmp/sdk", (self.file("a" * 1025),)),
            ("/tmp/sdk", (self.file(),) * 16385),
        )
        with mock.patch.object(metadata, "canonical_relative_posix_paths") as parse:
            for root, rows in inventories:
                with self.subTest(root_length=len(root), count=len(rows)):
                    with self.assertRaises(ValueError):
                        metadata.measure_node_file_metadata(root, rows)
            parse.assert_not_called()

    def test_deep_repeated_parents_exhaust_metadata_before_parser_or_filesystem(self):
        rows = tuple(self.file("a/" * 60 + f"v{i}.js") for i in range(100))
        with mock.patch.object(metadata, "canonical_relative_posix_paths") as parse:
            with self.assertRaisesRegex(ValueError, "storage exceeds"):
                metadata.measure_node_file_metadata("/tmp/sdk", rows)
            parse.assert_not_called()

    def test_canonical_aliases_and_file_ancestor_collisions_still_refuse(self):
        for paths in (("A.js", "a.js"), ("a", "a/b.js"), ("../v.js",), ("a//b",)):
            with self.subTest(paths=paths):
                with self.assertRaises(ValueError):
                    metadata.measure_node_file_metadata(
                        "/tmp/sdk", tuple(self.file(path) for path in paths)
                    )

    def test_tuple_subclass_is_not_iterated(self):
        calls = []

        class Rows(tuple):
            def __iter__(self):
                calls.append(True)
                raise AssertionError("foreign iteration")

        with self.assertRaises(ValueError):
            metadata.measure_node_file_metadata("/tmp/sdk", Rows((self.file(),)))
        self.assertFalse(calls)

    def test_substituted_file_property_is_refused_without_getter_execution(self):
        row = self.file()
        calls = []

        def getter(_self):
            calls.append(True)
            raise AssertionError("foreign getter")

        with mock.patch.object(DirectoryExportFile, "path", property(getter)):
            with self.assertRaisesRegex(ValueError, "namespace changed"):
                metadata.measure_node_file_metadata("/tmp/sdk", (row,))
        self.assertFalse(calls)

    def test_retained_preflight_failure_releases_source_and_partial_rows(self):
        content = bytes(bytearray(b"source"))
        baseline = sys.getrefcount(content)
        rows = (self.file(content=content), self.file("bad//path"))
        retained = None
        try:
            metadata.measure_node_file_metadata("/tmp/sdk", rows)
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.assertIsNotNone(retained.__traceback__)
        del rows
        self.assertEqual(sys.getrefcount(content), baseline)
