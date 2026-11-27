"""Actual resource/file proof inputs; pure projection, no writer or gate claim."""

from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import project_layout_framework_selection as production
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from tests.critical import test_project_layout_framework_source_proofs as support


class ExistingFrameworkSelectionTests(unittest.TestCase):
    def fixture(self, content=b"# Original framework authority\n"):
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, owner = helper.fixture(content=content)
        proof = helper.prove(project, owner)
        return project, owner, proof

    def select(self, project, owner, proof, **overrides):
        arguments = dict(
            resources=owner,
            source_proofs=(proof,),
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
        )
        arguments.update(overrides)
        return production.select_existing_framework_authority(
            project.snapshot, project.context, project.inventory, **arguments
        )

    def catalog_fixture(self, *, extra=False, dot_link=False, contained=False):
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original = helper.fixture()
        files = {
            logical: content
            for logical, content in original.files.items()
            if logical.startswith("flavors/os-base/")
        }
        self.assertIn("flavors/os-base/flavor.md", files)
        if dot_link:
            files["flavors/os-base/flavor.md"] += (
                b"\n[original toolchain](./toolchain.cdx.json)\n"
            )
        rows = list(project.baseline.files)
        bases = UpdateBases(project.root)
        for logical, content in files.items():
            source = "litai/" + logical if contained else logical
            project.write(source, content)
            rows.append(
                ProjectInitializationBaselineFile(
                    source,
                    len(content),
                    ContentIdentity.parse_uri(support.identity(content)),
                )
            )
            bases.advance("framework", source, content)
        if extra:
            project.write("flavors/os-base/custom-application.txt", b"keep local\n")
        project.baseline = replace(
            project.baseline, files=tuple(sorted(rows, key=lambda row: row.path))
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        project.write("litai/.literate/update-bases.json", bases.serialized())
        project.refresh()
        project.inventory["retained_implementation"] = None
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        with patch.object(
            resources, "_read_current_origin", return_value=original.origin
        ):
            owner = resources.observe_original_framework_resources(observed)
        proofs = tuple(
            helper.prove(
                project,
                owner,
                logical=logical,
                source_path="litai/" + logical if contained else logical,
            )
            for logical in sorted(files)
        )
        return project, owner, proofs, files

    def test_actual_initialized_catalog_item_remains_byte_identical(self):
        project, owner, proofs, files = self.catalog_fixture()
        public, private = self.select(project, owner, proofs[0], source_proofs=proofs)
        self.assertEqual(set(public["placements"]), set(files))
        for logical, original in files.items():
            self.assertEqual(private.rewritten_contents["litai/" + logical], original)
            self.assertEqual(
                public["placements"][logical]["from"],
                public["placements"][logical]["to"],
            )
        self.assertNotIn("skills/demo/SKILL.md", public["placements"])

    def test_imported_and_protected_catalog_fallback_preserves_other_placements(self):
        for key, contained in (
            (key, contained)
            for key in ("protected_paths", "imported_paths")
            for contained in (False, True)
        ):
            with self.subTest(key=key, contained=contained):
                project, owner, _proofs, files = self.catalog_fixture(
                    contained=contained
                )
                helper = support.InitializedFrameworkProofTests("runTest")
                proof = helper.prove(project, owner)
                before = dict(project.contents)
                _baseline, baseline_private = self.select(project, owner, proof)
                sources = {"litai/" + path if contained else path for path in files}
                public, private = self.select(
                    project,
                    owner,
                    proof,
                    **{key: frozenset(sources)},
                )
                self.assertIn("SKILL.md", public["owned_placements"])
                self.assertTrue(set(files).isdisjoint(public["owned_placements"]))
                self.assertTrue(sources.isdisjoint(public["placements"]))
                self.assertEqual(
                    private.rewritten_contents["litai/SKILL.md"],
                    baseline_private.rewritten_contents["litai/SKILL.md"],
                )
                self.assertTrue(sources.isdisjoint(private.rewritten_contents))
                for source in sources:
                    self.assertEqual(private.original_contents[source], before[source])
                self.assertEqual(project.contents, before)

    def test_resident_producer_projection_keeps_exact_history_and_source_identities(
        self,
    ):
        project, owner, proof = self.fixture()
        before_bases = project.contents["litai/.literate/update-bases.json"]
        before_baseline = project.contents[
            "litai/.literate/initialization-baseline.json"
        ]
        public, private = self.select(project, owner, proof)
        self.assertEqual(
            private.original_contents["litai/.literate/update-bases.json"], before_bases
        )
        self.assertEqual(
            private.original_contents["litai/.literate/initialization-baseline.json"],
            before_baseline,
        )
        baseline = json.loads(
            private.rewritten_contents["litai/.literate/initialization-baseline.json"]
        )
        row = next(row for row in baseline["files"] if row["path"] == "litai/SKILL.md")
        original = json.loads(before_baseline)
        old_row = next(row for row in original["files"] if row["path"] == "SKILL.md")
        self.assertEqual(
            {key: value for key, value in row.items() if key != "path"},
            {key: value for key, value in old_row.items() if key != "path"},
        )
        bases = json.loads(
            private.rewritten_contents["litai/.literate/update-bases.json"]
        )
        self.assertNotIn("SKILL.md", bases["framework"])
        self.assertEqual(bases["framework"]["litai/SKILL.md"], proof.source_identity)
        self.assertEqual(
            project.bases.scopes["framework"]["SKILL.md"], proof.source_identity
        )
        self.assertEqual(
            public["resident_edits"]["litai/.literate/initialization-baseline.json"][
                "source_proof"
            ],
            None,
        )

    def test_extra_unowned_catalog_child_holds_entire_initialized_item(self):
        project, owner, proofs, _files = self.catalog_fixture(extra=True)
        public, private = self.select(project, owner, proofs[0], source_proofs=proofs)
        self.assertFalse(public["placements"])
        self.assertFalse(public["applicable"])
        self.assertNotIn("flavors/", private.coordinate_map)
        self.assertTrue(
            any(
                row["owner"] == "initializer-catalog"
                for row in public["required_owners"]
            )
        )

    def test_catalog_raw_dot_link_keeps_meaning_without_byte_normalization(self):
        project, owner, proofs, files = self.catalog_fixture(dot_link=True)
        public, private = self.select(project, owner, proofs[0], source_proofs=proofs)
        self.assertEqual(set(public["placements"]), set(files))
        content = private.rewritten_contents["litai/flavors/os-base/flavor.md"]
        self.assertIn(b"](./toolchain.cdx.json)", content)
        self.assertEqual(content, files["flavors/os-base/flavor.md"])

    def test_original_proof_projects_only_its_file_without_io_or_app_changes(self):
        project, owner, proof = self.fixture()
        before = dict(project.contents)
        with (
            patch.object(Path, "open", side_effect=AssertionError("selector I/O")),
            patch.object(Path, "stat", side_effect=AssertionError("selector stat")),
            patch.object(Path, "lstat", side_effect=AssertionError("selector lstat")),
        ):
            public, private = self.select(project, owner, proof)
        self.assertEqual(set(public["owned_placements"]), {"SKILL.md"})
        self.assertEqual(public["placements"], {})
        self.assertEqual(
            private.rewritten_contents["litai/SKILL.md"], proof.source_bytes
        )
        self.assertEqual(project.contents, before)
        self.assertNotIn("application/main.py", private.rewritten_contents)
        self.assertNotIn("CHANGELOG.md", private.rewritten_contents)
        self.assertFalse(public["writes"])
        self.assertFalse(public["full_containment"])
        self.assertNotIn("source_bytes", str(public))

    def test_occupied_destination_cannot_be_adopted_even_with_identical_bytes(self):
        project, owner, proof = self.fixture()
        contents = dict(project.contents)
        contents["litai/SKILL.md"] = proof.source_bytes
        observations = dict(project.observations)
        observations["litai/SKILL.md"] = dict(project.observations["SKILL.md"])
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(
                project, owner, proof, contents=contents, observations=observations
            )

    def test_protected_imported_and_foreign_copied_proofs_refuse(self):
        project, owner, proof = self.fixture()
        for key in ("protected_paths", "imported_paths"):
            with self.subTest(key=key), self.assertRaises(ProjectLayoutPlanError):
                self.select(project, owner, proof, **{key: frozenset({"SKILL.md"})})
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, owner, copy.copy(proof))

    def test_missing_original_reference_is_explicit_not_synthetic_closure(self):
        project, owner, proof = self.fixture(b"See [guide](docs/missing-guide.md).\n")
        public, _private = self.select(project, owner, proof)
        self.assertFalse(public["applicable"])
        self.assertTrue(
            any(row["owner"] == "reference-scope" for row in public["required_owners"])
        )

    def test_opaque_source_blocks_closed_plan_and_is_not_directory_disposal(self):
        project, owner, proof = self.fixture()
        public, private = self.select(
            project,
            owner,
            proof,
            source_held=({"path": "docs/private", "source": True, "reason": "opaque"},),
        )
        self.assertFalse(public["applicable"])
        self.assertNotIn("docs/", private.coordinate_map)
        self.assertTrue(
            any(row["owner"] == "source-scope" for row in public["required_owners"])
        )

    def test_renderer_descriptor_replacement_never_runs_foreign_getter(self):
        project, owner, proof = self.fixture()
        calls = []

        class Foreign:
            def __get__(self, *_args):
                calls.append(True)
                return production._TEMPLATE

        with patch.object(
            production.ProjectScaffoldPlacement, "template_content", Foreign()
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                self.select(project, owner, proof)
        self.assertEqual(calls, [])
