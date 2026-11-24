"""Actual owned temp Git journal compatibility; planner fixture is modeled.

UNRUN. No native Windows or Component-retirement qualification claim.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_continuation as writer
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from tests.critical import test_project_layout_continuation as fixtures


@unittest.skipUnless(os.name == "posix", "owned POSIX fixture; Windows unqualified")
class CatalogJournalVersionControls(unittest.TestCase):
    def setUp(self):
        # Reuse fixture helpers without importing/discovering its TestCase class.
        self.fixture = fixtures.CatalogContinuationWriterTests(methodName="runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def rewrite(self, journal, transform):
        path = journal / "intent.json"
        document = json.loads(path.read_bytes())
        document.pop("identity")
        transform(document)
        document["identity"] = canonical_identity(document).uri
        path.write_bytes(canonical_json_bytes(document) + b"\n")

    def test_actual_five_directory_v1_recovers_without_extension_probe(self):
        fixture = self.fixture
        original = (fixture.root / fixture.source).stat()
        journal = Path(fixture.apply()["journal"])
        # Exact prior wire shape: same original fields, only five directories.
        (journal / "retired-source").rmdir()

        def old_format(document):
            document["schema"] = writer._JOURNAL_V1
            document["journal_directories"].pop("retired-source")

        self.rewrite(journal, old_format)
        original_names = writer._names

        def no_extension_probe(path):
            self.assertNotEqual(Path(path).name, "retired-source")
            return original_names(path)

        with patch.object(writer, "_names", no_extension_probe):
            fixture.recover()
            fixture.recover()
        restored = (fixture.root / fixture.source).stat()
        self.assertEqual(
            (restored.st_dev, restored.st_ino, restored.st_mode),
            (original.st_dev, original.st_ino, original.st_mode),
        )
        fixture.assert_custody()
        self.assertFalse((journal / "retired-source").exists())

    def test_new_journal_is_explicit_v2_and_six_directories(self):
        journal = Path(self.fixture.apply()["journal"])
        document = json.loads((journal / "intent.json").read_bytes())
        self.assertEqual(
            document["schema"],
            "literate-ai/project-layout-catalog-continuation-journal@2",
        )
        self.assertEqual(
            set(document["journal_directories"]),
            {
                "before",
                "after",
                "directories",
                "coordination",
                "history",
                "retired-source",
            },
        )
        self.fixture.recover()
        self.fixture.assert_custody()

    def test_rehashed_v1_with_extension_directory_refuses(self):
        journal = Path(self.fixture.apply()["journal"])
        self.rewrite(journal, lambda value: value.update(schema=writer._JOURNAL_V1))
        with self.assertRaises(ProjectLayoutPlanError):
            self.fixture.recover()
        self.assertFalse((self.fixture.root / self.fixture.source).exists())
        self.assertTrue((self.fixture.root / self.fixture.target).is_file())

    def test_rehashed_v2_missing_declared_extension_refuses(self):
        journal = Path(self.fixture.apply()["journal"])
        self.rewrite(
            journal,
            lambda value: value["journal_directories"].pop("retired-source"),
        )
        with self.assertRaises(ProjectLayoutPlanError):
            self.fixture.recover()
        self.assertTrue((self.fixture.root / self.fixture.target).is_file())

    def test_unknown_rehashed_version_refuses_before_restore_or_payload_move(self):
        journal = Path(self.fixture.apply()["journal"])
        self.rewrite(
            journal,
            lambda value: value.update(
                schema="literate-ai/project-layout-catalog-continuation-journal@99"
            ),
        )
        with patch.object(writer, "_restore_source_namespaces") as restore:
            with self.assertRaises(ProjectLayoutPlanError):
                self.fixture.recover()
        restore.assert_not_called()
        self.assertFalse((self.fixture.root / self.fixture.source).exists())
        self.assertTrue((self.fixture.root / self.fixture.target).is_file())
