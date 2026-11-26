"""Current reparent eligibility preserves modeled initialization history.

The initializer and source API are real. Added historical rows are fixture data;
actual installed migration/refusal evidence is retained by the explicit journey.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.project_reparenting import (
    FilesystemRepositoryReparentAdapter,
    RepositoryReparentError,
)
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaseline,
    ProjectInitializationBaselineFile,
    RepositoryLineage,
    RepositoryParentSelection,
    canonical_json_bytes,
)
from tests.support.fixtures_test_repository_initialization_e2e import initialize_root
from tests.support.fixtures_test_repository_orchestration import snapshot


class ReparentHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "project"
        initialize_root(self.root)
        self.baseline_path = self.root / "litai/.literate/initialization-baseline.json"
        self.baseline = ProjectInitializationBaseline.from_dict(
            json.loads(self.baseline_path.read_bytes())
        )
        self.calls = []

        def resolve(selection):
            self.calls.append(selection)
            return RepositoryLineage(selection, (), ())

        self.adapter = FilesystemRepositoryReparentAdapter(resolver=resolve)

    def write_baseline(self, baseline):
        self.baseline_path.write_bytes(canonical_json_bytes(baseline.to_dict()) + b"\n")

    def plan(self, selected=None):
        return self.adapter.plan(
            selected or self.root, RepositoryParentSelection.root()
        )

    def test_historical_metadata_and_shared_rows_do_not_block_current_root(self):
        origin = self.root / "litai/.literate/initialization-origin.json"
        content = origin.read_bytes()
        historical = ProjectInitializationBaselineFile(
            ".literate/initialization-origin.json",
            len(content),
            ContentIdentity.parse_uri("sha256:" + hashlib.sha256(content).hexdigest()),
        )
        self.write_baseline(
            replace(
                self.baseline,
                files=tuple(
                    sorted(
                        (*self.baseline.files, historical), key=lambda item: item.path
                    )
                ),
            )
        )
        before = snapshot(self.root)
        root = self.plan()
        descendant = self.plan(self.root / "litai/components")
        self.assertFalse(root.changed)
        self.assertEqual(root.identity, descendant.identity)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / historical.path).exists())
        self.assertEqual(len(self.calls), 2)

    def test_mismatched_origin_refuses_before_prospective_resolution(self):
        self.write_baseline(
            replace(
                self.baseline,
                origin_identity=ContentIdentity.parse_uri("sha256:" + "0" * 64),
            )
        )
        before = snapshot(self.root)
        with self.assertRaises(RepositoryReparentError) as raised:
            self.plan()
        self.assertEqual(raised.exception.code, "project.update_origin_mismatch")
        self.assertEqual(self.calls, [])
        self.assertEqual(snapshot(self.root), before)

    def test_native_profile_still_refuses_before_prospective_resolution(self):
        self.write_baseline(replace(self.baseline, profile="native"))
        before = snapshot(self.root)
        with self.assertRaises(RepositoryReparentError) as raised:
            self.plan()
        self.assertEqual(
            raised.exception.code, "repository_reparent.native_profile_unsupported"
        )
        self.assertEqual(self.calls, [])
        self.assertEqual(snapshot(self.root), before)

    def test_unplaced_agent_still_refuses_before_prospective_resolution(self):
        path = self.root / "litai/literate.project.json"
        document = json.loads(path.read_bytes())
        document["agent_skill"] = "custom.md"
        path.write_bytes(canonical_json_bytes(document) + b"\n")
        (self.root / "custom.md").write_text("Application-owned instructions.\n")
        before = snapshot(self.root)
        with self.assertRaises(RepositoryReparentError) as raised:
            self.plan()
        self.assertEqual(
            raised.exception.code, "repository_reparent.native_profile_unsupported"
        )
        self.assertEqual(self.calls, [])
        self.assertEqual(snapshot(self.root), before)
