"""Conventional verifier lookup follows actual initialized metadata placement."""

import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.component_acceptance import oracle_path
from literate_ai.adapters.project_initialization import (
    FilesystemProjectInitializationAdapter,
)
from literate_ai.adapters.project_scaffold_placement import ScaffoldLayout
from literate_ai.contracts import RepositoryParentSelection
from literate_ai.projects import ProjectConfigurationStore, ProjectError


def initialize_root(root, *, _layout=None):
    FilesystemProjectInitializationAdapter().initialize(
        root,
        parent_selection=RepositoryParentSelection.root(),
        source_intelligence_provider="none",
        empty=False,
        project_type="application",
        **({} if _layout is None else {"_layout": _layout}),
    )


class AcceptanceOraclePlacementTests(unittest.TestCase):
    def test_default_contained_lookup_matches_original_produced_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "project"
            initialize_root(root)
            context = ProjectConfigurationStore.context(root)
            expected = context.framework_path(
                "verification/acceptance/hello-component.json"
            )
            self.assertEqual(oracle_path(root, "hello-component"), expected)
            self.assertEqual(oracle_path(root / "litai", "hello-component"), expected)
            self.assertTrue(expected.is_file())
            self.assertFalse((root / "verification").exists())

    def test_legacy_lookup_matches_original_produced_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "project"
            initialize_root(root, _layout=ScaffoldLayout.LEGACY_ROOT_FIXTURE)
            expected = root / "verification/acceptance/hello-component.json"
            self.assertEqual(oracle_path(root, "hello-component"), expected)
            self.assertTrue(expected.is_file())

    def test_unconfigured_verifier_directory_keeps_root_relative_utility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.assertEqual(
                oracle_path(root, "fixture", "run"),
                root / "verification/acceptance/fixture/run.json",
            )
            self.assertEqual(list(root.iterdir()), [])

    def test_conflicting_metadata_refuses_instead_of_using_foreign_root_oracle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "project"
            initialize_root(root)
            context = ProjectConfigurationStore.context(root)
            foreign = root / "verification/acceptance/hello-component.json"
            foreign.parent.mkdir(parents=True)
            foreign.write_bytes(b"foreign verifier content")
            (root / "literate.project.json").write_bytes(
                context.manifest_path.read_bytes()
            )
            with self.assertRaises(ProjectError):
                oracle_path(root, "hello-component")
            self.assertEqual(foreign.read_bytes(), b"foreign verifier content")
