"""Declared metadata coordinates preserve original retained source semantics."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.retained_scaffold_coordinates import (
    retained_scaffold_coordinate,
)
from literate_ai.projects import (
    ProjectConfigurationStore,
    configured_catalog_path,
    contained_catalog_coordinates,
)
from tests.support import fixtures_test_project_configuration


class RetainedScaffoldCoordinateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def _project(self, contained, *, mixed=False):
        definition = fixtures_test_project_configuration._definition()
        if contained:
            definition = replace(
                definition,
                framework_directory="litai",
                component_roots=("components", "litai/components")
                if mixed
                else ("litai/components", "litai/samples"),
                skill_roots=("litai/skills",),
                workflow_roots=("litai/workflows",),
                routing_roots=("litai/routing",),
            )
        ProjectConfigurationStore(self.root).create(definition)

    def test_new_declared_catalog_selects_framework_wrapper_without_rebasing_source(
        self,
    ):
        self._project(True)
        self.assertEqual(
            retained_scaffold_coordinate(
                self.root, "components/legacy-project-wrapper"
            ),
            "litai/components/legacy-project-wrapper",
        )
        self.assertEqual(
            retained_scaffold_coordinate(self.root, "litai.harness.mk"),
            "litai/litai.harness.mk",
        )
        with self.assertRaises(ValueError):
            retained_scaffold_coordinate(
                self.root, "components/legacy-project-wrapper/implementation"
            )
        self.assertEqual(
            retained_scaffold_coordinate(self.root, ".literate/monorepo-components"),
            "litai/.literate/monorepo-components",
        )

    def test_component_named_implementation_is_metadata_not_retained_source(self):
        self._project(True)
        for relative in (
            "components/implementation",
            "components/implementation/component.md",
            "components/implementation/binding.json",
        ):
            self.assertEqual(
                retained_scaffold_coordinate(self.root, relative), "litai/" + relative
            )

    def test_original_transitional_mixed_roots_keep_original_wrapper(self):
        self._project(True, mixed=True)
        self.assertEqual(
            retained_scaffold_coordinate(
                self.root, "components/legacy-project-wrapper"
            ),
            "components/legacy-project-wrapper",
        )
        self.assertEqual(
            retained_scaffold_coordinate(self.root, "litai.harness.mk"),
            "litai.harness.mk",
        )

    def test_legacy_profile_keeps_original_metadata_coordinates(self):
        self._project(False)
        for relative in (
            "components/legacy-project-wrapper",
            "litai.harness.mk",
            ".literate/monorepo-components",
        ):
            self.assertEqual(
                retained_scaffold_coordinate(self.root, relative), relative
            )

    def test_contained_authored_inputs_need_no_fabricated_imports(self):
        self._project(True)
        self.assertEqual(contained_catalog_coordinates(self.root), {})
        self.assertEqual(
            configured_catalog_path(
                self.root, self.root, "skills/agent/owned/SKILL.md", kind="agent-skill"
            ),
            self.root / "litai/skills/agent/owned/SKILL.md",
        )
        self.assertFalse((self.root / ".literate/imports.json").exists())
        self.assertFalse((self.root / "litai/.literate/imports.json").exists())

    def test_old_root_source_shadow_refuses_instead_of_becoming_current_authority(self):
        self._project(True)
        (self.root / "skills/agent/owned").mkdir(parents=True)
        (self.root / "skills/agent/owned/SKILL.md").write_bytes(
            b"original application bytes"
        )
        with self.assertRaisesRegex(ValueError, "shadows"):
            configured_catalog_path(
                self.root, self.root, "skills/agent/owned/SKILL.md", kind="agent-skill"
            )
        self.assertEqual(
            (self.root / "skills/agent/owned/SKILL.md").read_bytes(),
            b"original application bytes",
        )
