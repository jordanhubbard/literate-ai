"""Genuine factory objects from two actual Roots cannot exchange ownership."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from literate_ai.adapters import component_namespace
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_producer_renewal as support


class FrameworkRenewalRootBinding(unittest.TestCase):
    def test_foreign_root_transition_refuses_before_any_renewal_intent(self):
        first = support.FrameworkProducerRenewalTests("runTest")
        second = support.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(first.doCleanups)
        self.addCleanup(second.doCleanups)
        first_project, _first_plan, foreign_endpoint, _first_original = first.fixture()
        project, public, _endpoint, _original = second.fixture()
        self.assertNotEqual(first_project.root, project.root)
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = second.prepare(project, _endpoint)
            with self.assertRaises(ProjectLayoutPlanError):
                second.renew(project, public, foreign_endpoint, prepared)
        self.assertEqual(
            list((project.root / "litai/.literate").glob("framework-renewal-*")), []
        )
        self.assertEqual(
            list((first_project.root / "litai/.literate").glob("framework-renewal-*")),
            [],
        )

    def test_recorded_namespace_identity_is_pure_after_planned_metadata_changes(self):
        helper = support.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _public, endpoint, _original = helper.fixture()
        # The original source metadata has already moved. This is only the
        # actual original recorded namespace, with no physical/currentness read.
        with (
            patch.object(
                component_namespace.os,
                "lstat",
                side_effect=AssertionError("unexpected source lstat"),
            ),
            patch.object(
                component_namespace.os,
                "open",
                side_effect=AssertionError("unexpected source open"),
            ),
        ):
            root, node = component_namespace.original_component_namespace_identity(
                endpoint.original_lock_store
            )
        self.assertEqual(root, project.root / endpoint.source_root)
        self.assertIsInstance(node, tuple)
