"""Actual original local owners, inert plans only; no publication/native claim.

Current distribution origin remains the maintained explicit fixture seam. Real
resource/file/absence/bootstrap owners and original public read are exercised.
"""

from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_finite_creations as finite
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_selection as selection
from literate_ai.adapters.project_layout_framework_plan import (
    decode_framework_authority_plan,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.contracts import canonical_identity
from tests.critical import test_project_layout_finite_creations as support


class FrameworkCreationCompositionTests(unittest.TestCase):
    def fixture(self, *, bootstrap=False):
        helper = support.FiniteFrameworkCreationTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, resources, proof = helper.fixture(bootstrap=bootstrap)
        return project, resources, proof

    def observation(self, project):
        return ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )

    def observe(self, project, resources, **kwargs):
        result = ingress.observe_existing_framework_authority(
            self.observation(project),
            resources=resources,
            **kwargs,
        )
        self.addCleanup(ingress.close_observed_framework_selection, result[1])
        return result

    def select(self, project, resources, proof=None, **kwargs):
        return selection.select_existing_framework_authority(
            project.snapshot,
            project.context,
            project.inventory,
            resources=resources,
            source_proofs=() if proof is None else (proof,),
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
            **kwargs,
        )

    def rehash(self, plan):
        plan["plan_identity"] = canonical_identity(
            {key: value for key, value in plan.items() if key != "plan_identity"}
        ).uri
        return plan

    def test_default_observation_acquires_original_ignore_without_writing(self):
        project, resources, _ = self.fixture()
        public, private = self.observe(project, resources)
        (owner,) = private.creation_owners
        self.assertIs(owner.resources, resources)
        finite.require_current_finite_framework_creation(owner)
        self.assertIsNone(public["owned_creations"]["litai/.gitignore"]["from"])
        self.assertEqual(private.rewritten_contents["litai/.gitignore"], owner.content)
        self.assertFalse((project.root / "litai/.gitignore").exists())
        self.assertNotIn("creation_owners", public)
        ingress.require_current_observed_framework_selection(private)

    def test_default_public_read_reaches_actual_bootstrap_helper_acquisition(self):
        project, _resources, _ = self.fixture(bootstrap=True)
        public, private = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, private)
        helper = next(
            owner
            for owner in private.creation_owners
            if owner.bootstrap_proof is not None
        )
        bootstrap = next(
            proof
            for proof in private.source_proofs
            if proof.logical == "scripts/bootstrap_litai.py"
        )
        self.assertIs(helper.bootstrap_proof, bootstrap)
        self.assertIs(helper.resources, private.resources)
        self.assertEqual(dict(helper.coordinates), dict(private.coordinate_map))
        self.assertEqual(
            public["owned_placements"][bootstrap.source_path]["projection"],
            "reviewed-bootstrap",
        )
        self.assertIn(helper.destination, public["owned_creations"])
        self.assertFalse((project.root / helper.destination).exists())
        ingress.require_current_observed_framework_selection(private)

    def test_new_helper_is_current_base_not_fabricated_old_initialization_output(self):
        project, resources, _ = self.fixture(bootstrap=True)
        original = json.loads(
            project.contents["litai/.literate/initialization-baseline.json"]
        )
        public, private = self.observe(project, resources)
        after = json.loads(
            private.rewritten_contents["litai/.literate/initialization-baseline.json"]
        )
        self.assertEqual(len(original["files"]), len(after["files"]))
        self.assertNotIn(
            "litai/scripts/_bootstrap_processes.py",
            {row["path"] for row in after["files"]},
        )
        bases = json.loads(
            private.rewritten_contents["litai/.literate/update-bases.json"]
        )
        row = public["owned_creations"]["litai/scripts/_bootstrap_processes.py"]
        self.assertEqual(
            bases["framework"]["litai/scripts/_bootstrap_processes.py"], row["to"]
        )
        self.assertEqual(bases["sources"], project.bases.sources)

    def test_existing_custom_contained_ignore_is_observed_and_never_overwritten(self):
        project, resources, _ = self.fixture()
        project.write("litai/.gitignore", b"# custom resident ignore\n")
        # Actual fresh target capture classifies this resident file.
        public, private = self.observe(project, resources)
        self.assertNotIn("litai/.gitignore", public["owned_creations"])
        self.assertEqual(
            private.original_contents["litai/.gitignore"], b"# custom resident ignore\n"
        )
        self.assertNotIn("litai/.gitignore", private.rewritten_contents)
        self.assertTrue(
            any(
                row["owner"] == "existing-contained-ignore"
                for row in public["required_owners"]
            )
        )
        self.assertFalse(public["applicable"])

    def test_existing_custom_helper_blocks_bootstrap_pair_without_ghost_coordinates(
        self,
    ):
        project, resources, _ = self.fixture(bootstrap=True)
        project.write(
            "litai/scripts/_bootstrap_processes.py", b"# original custom code\n"
        )
        public, private = self.observe(project, resources)
        self.assertNotIn(
            "litai/scripts/_bootstrap_processes.py", public["owned_creations"]
        )
        self.assertNotIn("scripts/bootstrap_litai.py", public["owned_placements"])
        self.assertNotEqual(
            private.coordinate_map.get("scripts/bootstrap_litai.py"),
            "litai/scripts/bootstrap_litai.py",
        )
        self.assertNotEqual(
            private.coordinate_map.get("scripts/_bootstrap_processes.py"),
            "litai/scripts/_bootstrap_processes.py",
        )
        self.assertFalse(public["applicable"])

    def test_occupied_alias_target_refuses_without_overwrite(self):
        project, resources, _ = self.fixture()
        project.write("litai/.GITIGNORE", b"# resident alias\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.observe(project, resources)
        self.assertEqual(
            (project.root / "litai/.GITIGNORE").read_bytes(), b"# resident alias\n"
        )

    def test_foreign_resources_and_copied_creation_owners_refuse(self):
        project, resources, _ = self.fixture()
        owner = finite.observe_original_finite_framework_creation(
            resources, ".gitignore"
        )
        self.addCleanup(finite.close_original_finite_framework_creation, owner)
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, resources, creation_owners=(copy.copy(owner),))
        other, other_resources, _ = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(other, other_resources, creation_owners=(owner,))

    def test_original_absence_change_refuses_after_observation(self):
        project, resources, _ = self.fixture()
        _public, private = self.observe(project, resources)
        project.write("litai/.gitignore", b"# new foreign resident\n")
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_current_observed_framework_selection(private)

    def test_exact_creation_tuple_is_sealed_and_close_retires_acquired_owners(self):
        project, resources, _ = self.fixture()
        _public, private = self.observe(project, resources)
        owners = private.creation_owners
        object.__setattr__(private, "creation_owners", ())
        try:
            with self.assertRaises(ProjectLayoutPlanError):
                ingress.require_original_observed_framework_selection(private)
        finally:
            object.__setattr__(private, "creation_owners", owners)
        ingress.close_observed_framework_selection(private)
        for owner in owners:
            with self.assertRaises(ProjectLayoutPlanError):
                finite.require_original_finite_framework_creation(owner)

    def test_empty_tuple_preserves_pure_selection_public_bytes_and_constructor_default(
        self,
    ):
        project, resources, _ = self.fixture()
        default, first = self.select(project, resources)
        explicit, second = self.select(project, resources, creation_owners=())
        self.assertEqual(default, explicit)
        self.assertEqual(first.creation_owners, ())
        self.assertEqual(second.creation_owners, ())
        self.assertEqual(default["owned_creations"], {})

    def test_codec_rehash_cannot_admit_unknown_or_mixed_creation_variants(self):
        project, resources, _ = self.fixture()
        public, _private = self.observe(project, resources)
        mutations = (
            ("from", "sha256:" + "a" * 64),
            ("logical", "custom.py"),
            ("owner", "initialized-file"),
            ("projection", "original-bytes"),
            ("source_proof", None),
            ("mode", 0o755),
            ("resource_identity", "sha256:" + "b" * 64),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                changed = copy.deepcopy(public)
                changed["owned_creations"]["litai/.gitignore"][field] = value
                with self.assertRaises((ProjectLayoutPlanError, ValueError)):
                    decode_framework_authority_plan(self.rehash(changed))

    def test_codec_helper_creation_requires_actual_reviewed_bootstrap_move(self):
        project, resources, _ = self.fixture(bootstrap=True)
        public, _private = self.observe(project, resources)
        changed = copy.deepcopy(public)
        changed["owned_placements"].pop("scripts/bootstrap_litai.py")
        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_plan(self.rehash(changed))

    def test_decoded_plan_never_reopens_original_selection_or_absence(self):
        project, resources, _ = self.fixture()
        public, _private = self.observe(project, resources)
        decoded = decode_framework_authority_plan(public)
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_original_observed_framework_selection(decoded)
        with self.assertRaises(ProjectLayoutPlanError):
            finite.require_original_finite_framework_creation(
                decoded["owned_creations"]["litai/.gitignore"]
            )

    def test_changed_factory_registration_refuses_before_foreign_dispatch(self):
        project, resources, _ = self.fixture()
        captured = []
        original = finite._register

        def record(owner):
            original(owner)
            captured.append(owner)

        # Original capture seam only records the genuine issued object.
        with patch.object(finite, "_register", side_effect=record):
            # Factory implementation does not accept replacement registration.
            with self.assertRaises(ProjectLayoutPlanError):
                self.observe(project, resources)
        self.assertEqual(captured, [])

    def test_helper_owner_with_incomplete_coordinate_map_refuses_without_rebaseline(
        self,
    ):
        project, resources, proof = self.fixture(bootstrap=True)
        owner = finite.observe_original_finite_framework_creation(
            resources,
            "scripts/_bootstrap_processes.py",
            bootstrap_proof=proof,
            coordinate_map={
                "scripts/bootstrap_litai.py": "litai/scripts/bootstrap_litai.py",
                "scripts/_bootstrap_processes.py": (
                    "litai/scripts/_bootstrap_processes.py"
                ),
            },
        )
        self.addCleanup(finite.close_original_finite_framework_creation, owner)
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, resources, proof, creation_owners=(owner,))
        finite.require_current_finite_framework_creation(owner)

    def test_actual_bootstrap_source_drift_after_observation_refuses(self):
        project, resources, _ = self.fixture(bootstrap=True)
        _public, private = self.observe(project, resources)
        project.write("scripts/bootstrap_litai.py", b"# changed real bootstrap\n")
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_current_observed_framework_selection(private)
