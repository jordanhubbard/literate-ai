"""Actual local observation/issuer guards; no migration/native qualification."""

from __future__ import annotations

import copy
import gc
import unittest
import weakref
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_ingress as production
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from tests.critical import test_project_layout_framework_source_proofs as support


class FrameworkIngressTests(unittest.TestCase):
    def fixture(self):
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, resources = helper.fixture(content=b"# Original framework authority\n")
        # Current origin lookup is the existing explicitly modeled fixture seam.
        self.enterContext(
            patch.object(
                support.resources, "_read_current_origin", return_value=resources.origin
            )
        )
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        public, selection = production.observe_existing_framework_authority(
            observed, resources=resources
        )
        self.addCleanup(production.close_observed_framework_selection, selection)
        return project, resources, public, selection

    def test_same_original_snapshot_context_resources_and_private_owner_are_retained(
        self,
    ):
        project, resources, public, selection = self.fixture()
        self.assertIs(selection.snapshot, project.snapshot)
        self.assertIs(selection.context, project.context)
        self.assertIs(selection.resources, resources)
        self.assertIs(selection.observation_owner.snapshot, project.snapshot)
        self.assertIs(selection.observation_owner.context, project.context)
        self.assertIs(selection.observation_owner.resources, resources)
        production.require_current_observed_framework_selection(selection)
        self.assertEqual(
            public["owned_placements"]["SKILL.md"]["destination"], "litai/SKILL.md"
        )
        self.assertNotIn("observation_owner", public)

    def test_pure_selection_and_copied_attached_selection_refuse_effect_origin(self):
        _project, _resources, _public, selection = self.fixture()
        copied = copy.copy(selection)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_observed_framework_selection(copied)
        object.__setattr__(copied, "observation_owner", None)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_observed_framework_selection(copied)

    def test_changed_app_source_or_managed_source_is_not_rebaselined(self):
        for path in ("application/main.py", "SKILL.md"):
            with self.subTest(path=path):
                project, _resources, _public, selection = self.fixture()
                project.write(path, project.contents[path] + b"changed\n")
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_current_observed_framework_selection(selection)

    def test_changed_private_action_and_public_plan_refuse_before_source_callback(self):
        _project, _resources, _public, selection = self.fixture()
        selection.owned_placements["SKILL.md"]["to"] = "sha256:" + "f" * 64
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_observed_framework_selection(selection)

    def test_close_is_irreversible_even_if_caller_keeps_all_saved_fields(self):
        _project, _resources, _public, selection = self.fixture()
        production.close_observed_framework_selection(selection)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_observed_framework_selection(selection)

    def test_owned_unopened_coordination_sibling_does_not_rebase_source_files(self):
        project, _resources, _public, selection = self.fixture()
        project.write("litai/.literate/owned-coordination.lock", b"owned\n")
        production.require_current_observed_framework_selection(selection)

    def test_replaced_selection_descriptor_never_dispatches_foreign_getter(self):
        _project, _resources, _public, selection = self.fixture()
        calls = []

        class Foreign:
            def __get__(self, *_args):
                calls.append(True)
                return None

        with patch.object(
            production.FrameworkAuthoritySelection, "observation_owner", Foreign()
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_original_observed_framework_selection(selection)
        self.assertEqual(calls, [])

    def test_no_registry_cycle_keeps_original_observation_after_selection_release(self):
        # No cleanup closure may retain this specific selection in this control.
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, resources = helper.fixture(content=b"# Original framework authority\n")
        with patch.object(
            support.resources, "_read_current_origin", return_value=resources.origin
        ):
            observed = ProjectLayoutObservation(
                project.snapshot,
                project.context,
                project.inventory,
                project.observations,
                project.contents,
                project.bases,
            )
            _public, selection = production.observe_existing_framework_authority(
                observed, resources=resources
            )
        owner = weakref.ref(selection.observation_owner)
        selected = weakref.ref(selection)
        del selection
        gc.collect()
        self.assertIsNone(selected())
        self.assertIsNone(owner())
