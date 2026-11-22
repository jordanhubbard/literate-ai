"""Bounded checkpoint observations preserve update parsing and publication guards."""

from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import update_merge
from literate_ai.adapters.project_updates import ProjectUpdateError
from literate_ai.adapters.update_merge import CHECKPOINT, SCHEMA, UpdateBases, digest
from literate_ai.contracts import ContentIdentity


class UpdateBaseObservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / CHECKPOINT
        self.path.parent.mkdir()
        self.content = b"original upstream bytes\n"
        self.key = digest(self.content)
        self.value = {
            "schema": SCHEMA,
            "blobs": {self.key: base64.b64encode(self.content).decode("ascii")},
            "framework": {"scripts/managed.py": self.key},
            "catalog": {},
            "sources": {},
        }
        self.raw = json.dumps(self.value, indent=2).encode() + b"\n"
        self.path.write_bytes(self.raw)

    def test_snapshot_parser_matches_store_without_checkpoint_reread(self):
        ordinary = UpdateBases(self.root)
        with mock.patch.object(
            Path, "read_bytes", side_effect=AssertionError("reopened checkpoint")
        ):
            observed = UpdateBases.from_observed(self.root, self.raw, maximum_entries=2)
        self.assertEqual(observed.original, ordinary.original)
        self.assertEqual(observed.blobs, ordinary.blobs)
        self.assertEqual(observed.scopes, ordinary.scopes)
        self.assertEqual(observed.sources, ordinary.sources)
        self.assertEqual(observed.entry_count, 2)

    def test_later_checkpoint_bytes_are_not_adopted_or_overwritten(self):
        foreign = b"foreign checkpoint bytes\n"
        self.path.write_bytes(foreign)
        observed = UpdateBases.from_observed(self.root, self.raw)
        self.assertEqual(
            observed.get(ContentIdentity.parse_uri(self.key)), self.content
        )
        observed.advance("framework", "scripts/managed.py", b"new upstream\n")
        with self.assertRaisesRegex(ProjectUpdateError, "update baseline changed"):
            observed.write()
        self.assertEqual(self.path.read_bytes(), foreign)

    def test_entry_limit_precedes_blob_decoding(self):
        with mock.patch.object(update_merge.base64, "b64decode") as decode:
            with self.assertRaisesRegex(ProjectUpdateError, "entries exceed"):
                UpdateBases.from_observed(self.root, self.raw, maximum_entries=1)
        decode.assert_not_called()

    def test_legacy_identity_only_and_catalog_sources_remain_readable(self):
        value = dict(self.value, blobs={})
        value["catalog"] = {"components/imported/component.md": self.key}
        ref = "git:https://example.invalid/source.git@" + "a" * 40
        value["sources"] = {"components/imported/component.md": ref}
        observed = UpdateBases.from_observed(
            self.root, json.dumps(value).encode(), maximum_entries=3
        )
        self.assertIsNone(observed.get(ContentIdentity.parse_uri(self.key)))
        self.assertEqual(observed.scopes["framework"], value["framework"])
        self.assertEqual(observed.scopes["catalog"], value["catalog"])
        self.assertEqual(observed.sources, value["sources"])
        self.assertEqual(observed.entry_count, 3)

    def test_invalid_snapshot_types_and_entry_bounds_refuse(self):
        for raw in ("not bytes", b"[]", b"{}"):
            with self.subTest(raw=raw):
                with self.assertRaises(ProjectUpdateError):
                    UpdateBases.from_observed(self.root, raw)
        for bound in (-1, True, "2"):
            with self.subTest(bound=bound):
                with self.assertRaises(ProjectUpdateError):
                    UpdateBases.from_observed(
                        self.root, self.raw, maximum_entries=bound
                    )

    def test_missing_observation_keeps_publication_absence_guard(self):
        observed = UpdateBases.from_observed(self.root, None, maximum_entries=0)
        self.assertEqual(observed.entry_count, 0)
        self.assertEqual(observed.blobs, {})
        with self.assertRaisesRegex(ProjectUpdateError, "update baseline changed"):
            observed.write()
        self.assertEqual(self.path.read_bytes(), self.raw)
