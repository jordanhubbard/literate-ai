"""New canonical source scaffold publication controls; native proof is separate."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters import project_initialization as initializer
from literate_ai.adapters.project_scaffold_placement import project_scaffold_placement
from literate_ai.adapters.repository_catalogs import InheritedCatalogPlan
from literate_ai.contracts import (
    ProjectInitializationOrigin,
    RepositoryLineage,
    RepositoryParentSelection,
)
from literate_ai.projects import ProjectConfigurationStore


def _adapter():
    return initializer.FilesystemProjectInitializationAdapter(
        standard_binding_provider=lambda: None,
        initialization_origin_provider=lambda: ProjectInitializationOrigin(
            "https://example.test/framework.git", "a" * 40, "literate-ai", "1.4.0"
        ),
        repository_lineage_resolver=lambda selected: RepositoryLineage(
            selected, (), ()
        ),
        repository_catalog_planner=lambda lineage: InheritedCatalogPlan(lineage, ()),
    )


class ProjectScaffoldPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "derived"

    def test_actual_new_root_parent_project_publishes_only_contained_authority(self):
        result = _adapter().initialize(
            self.root,
            empty=True,
            bootstrap_tools=False,
            flavor_selectors=("+python", "+macos"),
            parent_selection=RepositoryParentSelection.root(),
        )
        snapshot = ProjectConfigurationStore(self.root).read()
        self.assertEqual(snapshot.definition.framework_directory, "litai")
        self.assertEqual(
            ProjectConfigurationStore.context(self.root).framework_root,
            self.root / "litai",
        )
        self.assertFalse((self.root / "literate.project.json").exists())
        self.assertFalse((self.root / "components").exists())
        self.assertFalse((self.root / "docs").exists())
        self.assertFalse((self.root / ".literate").exists())
        baseline = json.loads(
            (self.root / "litai/.literate/initialization-baseline.json").read_bytes()
        )
        root_files = {
            "AGENTS.md",
            "CLAUDE.md",
            "agents/openai.yaml",
            ".cursor/rules/literate-ai.mdc",
            "CHANGELOG.md",
        }
        self.assertTrue(
            all(
                row["path"].startswith("litai/") or row["path"] in root_files
                for row in baseline["files"]
            )
        )
        self.assertEqual(
            result["initialization_origin"]["path"],
            "litai/.literate/initialization-origin.json",
        )
        self.assertTrue(
            all(
                path.startswith("litai/") or path in root_files
                for path in result["created"]
            )
        )
        self.assertIn(b"litai/SKILL.md", (self.root / "AGENTS.md").read_bytes())
        self.assertTrue((self.root / "litai/.gitignore").is_file())
        self.assertFalse((self.root / ".gitignore").exists())

    def test_application_readme_preserved_and_starter_is_contained(self):
        self.root.mkdir()
        original = b"# Product-owned readme\n"
        (self.root / "README.md").write_bytes(original)
        _adapter().initialize(
            self.root,
            bootstrap_tools=False,
            flavor_selectors=("+python", "+macos"),
            parent_selection=RepositoryParentSelection.root(),
        )
        self.assertEqual((self.root / "README.md").read_bytes(), original)
        self.assertTrue(
            (self.root / "litai/samples/hello-component/component.lock.json").is_file()
        )
        self.assertTrue(
            (self.root / "litai/verification/acceptance/hello-component.json").is_file()
        )
        self.assertFalse((self.root / "samples").exists())

    def test_dynamic_evidence_projection_is_separate_from_migration_inventory(self):
        placement = project_scaffold_placement(self.root, initializer._TEMPLATE_FILES)
        value = "components/new-original/component.lock.json"
        self.assertEqual(placement.produced_coordinate(value), "litai/" + value)
        with self.assertRaises(ValueError):
            placement.entry(value)
        with self.assertRaises(ValueError):
            placement.produced_coordinate(
                "components/legacy-project-wrapper/implementation/src/main.rs"
            )
        for path in ("src/main.rs", "application-config.json", "../outside"):
            with self.assertRaises(ValueError):
                placement.produced_coordinate(path)

    def test_actual_new_conversion_keeps_native_source_outside_wrapper_metadata(self):
        self.root.mkdir()
        original = b"# Product source\n"
        (self.root / "product.py").write_bytes(original)
        (self.root / "Makefile").write_bytes(
            b"build:\n\t@echo build\ntest:\n\t@echo test\npackage:\n\t@echo package\n"
        )
        result = _adapter().initialize(
            self.root,
            convert=True,
            run_baseline=False,
            bootstrap_tools=False,
            default_branch="main",
            allow_unready=True,
            flavor_selectors=("+python", "+macos", "+make"),
            parent_selection=RepositoryParentSelection.root(),
        )
        self.assertEqual(
            (
                self.root
                / "components/legacy-project-wrapper/implementation/product.py"
            ).read_bytes(),
            original,
        )
        self.assertTrue(
            (
                self.root / "litai/components/legacy-project-wrapper/component.md"
            ).is_file()
        )
        self.assertFalse(
            (self.root / "components/legacy-project-wrapper/component.md").exists()
        )
        self.assertTrue((self.root / "litai/litai.harness.mk").is_file())
        self.assertFalse((self.root / "litai.harness.mk").exists())
        self.assertEqual(
            result["lift_shift"]["implementation_directory"],
            "components/legacy-project-wrapper/implementation",
        )
        self.assertEqual(result["harness_baseline"]["state"], "passed")
        self.assertEqual(result["harness_baseline"]["phase_count"], 3)

    def test_actual_custom_rules_keep_product_history_and_ignore(
        self,
    ):
        self.root.mkdir()
        original = b"# Product rules\nKeep original instructions.\n"
        history = b"# Actual product history\n"
        ignore = b"native-output/\n"
        (self.root / "AGENTS.md").write_bytes(original)
        (self.root / "CHANGELOG.md").write_bytes(history)
        (self.root / ".gitignore").write_bytes(ignore)
        result = _adapter().initialize(
            self.root,
            empty=True,
            bootstrap_tools=False,
            flavor_selectors=("+python", "+macos"),
            parent_selection=RepositoryParentSelection.root(),
        )
        self.assertTrue((self.root / "AGENTS.md").read_bytes().startswith(original))
        self.assertIn(b"litai/SKILL.md", (self.root / "AGENTS.md").read_bytes())
        self.assertEqual((self.root / "CHANGELOG.md").read_bytes(), history)
        self.assertEqual((self.root / ".gitignore").read_bytes(), ignore)
        self.assertNotIn("CHANGELOG.md", result["created"])
