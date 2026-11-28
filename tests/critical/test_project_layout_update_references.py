"""Update templates reference recorded resources without relocating them.

The actual upstream renderer consumes explicit baseline coordinates. Files here
are reference-target fixtures, not invented migration/qualification evidence.
The installed maintenance journey owns the genuine plan/apply regression.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters import project_updates as updates
from literate_ai.adapters.project_scaffold_placement import project_scaffold_placement
from literate_ai.documentation import extract_markdown_links


class UpdateReferencePlacementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.decision = updates.LEGACY_LIFT_SHIFT_ADR
        self.placement = project_scaffold_placement(
            self.root,
            (
                *updates._TEMPLATE_FILES,
                *updates._STARTER_TEMPLATE_FILES,
                *updates._STARTER_DOCS,
            ),
        )

    def put(self, relative):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"# Original conversion decision\n")
        return path

    def render(self, paths):
        return updates._upstream_template(set(paths), placement=self.placement)

    def assert_reference(self, content, document, target):
        link = next(
            row.destination
            for row in extract_markdown_links(content.decode())
            if self.decision.rsplit("/", 1)[1] in row.destination
        )
        self.assertEqual((self.root / document).parent.joinpath(link).resolve(), target)
        self.assertTrue(target.is_file())

    def test_mixed_project_keeps_reference_to_unwritten_root_decision(self):
        decision = self.put(self.decision)
        before = decision.read_bytes()
        content = self.render({self.decision, "litai/docs/README.md"})
        self.assert_reference(
            content["litai/docs/README.md"], "litai/docs/README.md", decision
        )
        self.assertNotIn(self.decision, content)
        self.assertNotIn("litai/" + self.decision, content)
        self.assertEqual(decision.read_bytes(), before)
        self.assertFalse((self.root / "litai" / self.decision).exists())

    def test_contained_project_references_recorded_contained_decision(self):
        decision = self.put("litai/" + self.decision)
        before = decision.read_bytes()
        content = self.render({"litai/" + self.decision, "litai/docs/README.md"})
        self.assert_reference(
            content["litai/docs/README.md"], "litai/docs/README.md", decision
        )
        self.assertEqual(decision.read_bytes(), before)
        self.assertFalse((self.root / self.decision).exists())

    def test_legacy_project_keeps_original_root_reference_behavior(self):
        decision = self.put(self.decision)
        content = updates._upstream_template({self.decision, "docs/README.md"})
        self.assert_reference(content["docs/README.md"], "docs/README.md", decision)

    def test_ambiguous_recorded_resource_does_not_choose_or_repair_a_target(self):
        original = self.put(self.decision)
        contained = self.put("litai/" + self.decision)
        before = {path: path.read_bytes() for path in (original, contained)}
        with self.assertRaises(updates.ProjectUpdateError) as caught:
            self.render(
                {self.decision, "litai/" + self.decision, "litai/docs/README.md"}
            )
        self.assertEqual(caught.exception.code, "project.update_reference_ambiguous")
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_historical_metadata_rows_do_not_redirect_current_metadata_producers(self):
        paths = {self.decision, "litai/docs/README.md"}
        original = self.render(paths)
        paths.update(
            {
                ".literate/initialization-origin.json",
                "litai/.literate/initialization-origin.json",
                "literate.project.json",
                "litai/literate.project.json",
                "verification/current.json",
                "litai/verification/current.json",
            }
        )
        self.assertEqual(self.render(paths), original)
