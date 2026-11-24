"""Actual selected producer capture versus unrelated owned sibling changes."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_resources as production
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_project_layout_framework_resources as support


class FrameworkProducerNamespaceTests(unittest.TestCase):
    def test_unrelated_owned_coordination_sibling_keeps_original_file_custody(self):
        project, observed, origin = support.framework_fixture(self)
        with patch.object(production, "_read_current_origin", return_value=origin):
            owner = production.observe_original_framework_resources(observed)
            before = dict(observed.contents)
            project.write("litai/.literate/owned-coordination.lock", b"owned\n")
            production.require_current_framework_resources(owner)
        self.assertEqual(observed.contents, before)

    def test_selected_file_content_or_same_bytes_replacement_is_not_adopted(self):
        for mutation in ("content", "inode"):
            with self.subTest(mutation=mutation):
                project, observed, origin = support.framework_fixture(self)
                with patch.object(
                    production, "_read_current_origin", return_value=origin
                ):
                    owner = production.observe_original_framework_resources(observed)
                    path = project.root / "litai/.literate/initialization-baseline.json"
                    before = path.read_bytes()
                    if mutation == "content":
                        path.write_bytes(before + b" ")
                    else:
                        path.rename(path.with_suffix(".retained"))
                        path.write_bytes(before)
                    with self.assertRaises(ProjectLayoutPlanError):
                        production.require_current_framework_resources(owner)

    def test_original_metadata_ancestor_replacement_refuses_before_recapture(self):
        project, observed, origin = support.framework_fixture(self)
        with patch.object(production, "_read_current_origin", return_value=origin):
            owner = production.observe_original_framework_resources(observed)
            old = project.root / "litai/.literate"
            old.rename(project.root / "litai/old-metadata")
            old.mkdir()
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_framework_resources(owner)
