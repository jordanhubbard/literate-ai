"""Original ignore producers through fresh planning; no equal-byte adoption."""

from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace

from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_scaffold_placement as scaffold
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from tests.critical import test_project_layout_finite_creations as fixtures
from tests.critical import test_project_layout_framework_transaction as transactions


class OriginalResidentIgnoreTests(unittest.TestCase):
    def fixture(self, *, initial=False, root_ignore=False):
        helper = fixtures.FiniteFrameworkCreationTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _resources, _proof = helper.fixture()
        path = ".gitignore" if root_ignore else "litai/.gitignore"
        content = scaffold._FRAMEWORK_IGNORE
        project.write(path, content)
        if initial:
            project.baseline = replace(
                project.baseline,
                files=tuple(
                    sorted(
                        (
                            *project.baseline.files,
                            ProjectInitializationBaselineFile(
                                path,
                                len(content),
                                ContentIdentity.parse_uri(
                                    "sha256:" + hashlib.sha256(content).hexdigest()
                                ),
                            ),
                        ),
                        key=lambda row: row.path,
                    )
                ),
            )
            project.write(
                "litai/.literate/initialization-baseline.json",
                canonical_json_bytes(project.baseline.to_dict()) + b"\n",
            )
            # The original initializer retains each created byte preimage; this
            # models its actual baseline+blob shape, not a source factory mock.
            project.bases.retain(content)
            project.write(
                "litai/.literate/update-bases.json", project.bases.serialized()
            )
        return project, content

    def read(self, project):
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        return public, selected

    def test_actual_placement_base_is_recognized_by_fresh_original_read(self):
        helper = transactions.FrameworkAuthorityTransactionTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, plan, selected = helper.fixture()
        helper.apply(project, plan, selected)
        content = (project.root / "litai/.gitignore").read_bytes()
        public, fresh = self.read(project)
        self.assertFalse(
            any(
                row["owner"] == "existing-contained-ignore"
                for row in public["required_owners"]
            )
        )
        self.assertNotIn("litai/.gitignore", public["owned_creations"])
        proof = next(
            proof for proof in fresh.source_proofs if proof.logical == ".gitignore"
        )
        self.assertEqual(proof.source_path, "litai/.gitignore")
        self.assertEqual(proof.source_bytes, content)
        ingress.require_current_observed_framework_selection(fresh)
        ingress.close_observed_framework_selection(fresh)
        helper.recover(project, plan)

    def test_original_initialization_baseline_and_retained_bytes_prove_residence(self):
        project, content = self.fixture(initial=True)
        public, selected = self.read(project)
        proof = next(
            proof for proof in selected.source_proofs if proof.logical == ".gitignore"
        )
        self.assertEqual(proof.source_bytes, content)
        self.assertNotIn("litai/.gitignore", selected.rewritten_contents)
        self.assertFalse(
            any(
                row["owner"] == "existing-contained-ignore"
                for row in public["required_owners"]
            )
        )
        ingress.require_current_observed_framework_selection(selected)

    def test_equal_bytes_without_original_producer_remain_an_explicit_blocker(self):
        project, content = self.fixture()
        public, selected = self.read(project)
        self.assertTrue(
            any(
                row["owner"] == "existing-contained-ignore"
                for row in public["required_owners"]
            )
        )
        self.assertFalse(
            any(proof.logical == ".gitignore" for proof in selected.source_proofs)
        )
        self.assertEqual((project.root / "litai/.gitignore").read_bytes(), content)

    def test_custom_edit_of_original_ignore_is_never_overwritten(self):
        project, _content = self.fixture(initial=True)
        project.write("litai/.gitignore", b"# user custom ignore\n")
        public, selected = self.read(project)
        self.assertTrue(
            any(
                row["owner"] == "existing-contained-ignore"
                for row in public["required_owners"]
            )
        )
        self.assertNotIn("litai/.gitignore", selected.rewritten_contents)
        self.assertEqual(
            (project.root / "litai/.gitignore").read_bytes(), b"# user custom ignore\n"
        )

    def test_root_application_ignore_is_not_adopted_even_with_recorded_bytes(self):
        project, content = self.fixture(initial=True, root_ignore=True)
        _public, selected = self.read(project)
        self.assertFalse(
            any(proof.logical == ".gitignore" for proof in selected.source_proofs)
        )
        self.assertEqual((project.root / ".gitignore").read_bytes(), content)

    def test_late_resident_ignore_drift_expires_original_source_observation(self):
        project, _content = self.fixture(initial=True)
        _public, selected = self.read(project)
        project.write("litai/.gitignore", b"late user data\n")
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_current_observed_framework_selection(selected)
        self.assertEqual(
            (project.root / "litai/.gitignore").read_bytes(), b"late user data\n"
        )
