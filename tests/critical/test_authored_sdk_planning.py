"""Original SDK selection boundaries and unchanged no-SDK planning.

Uses actual authored planning fixtures. No SDK is built and no generated program
runs; real SDK producer/service qualification is separate required evidence.
"""

import unittest

from literate_ai.adapters.authored_qualification_projection import (
    open_current_authored_qualification_projection,
)
from tests.critical import test_authored_qualification_planning as planning_fixtures


class AuthoredSdkPlanningTests(unittest.TestCase):
    def setUp(self):
        fixture = planning_fixtures.AuthoredQualificationPlanningTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture

    def test_explicit_no_sdk_preserves_complete_plan_identity(self):
        implicit = self.fixture.plan()
        explicit = self.fixture.plan(native_sdk_inputs=None)
        self.assertEqual(implicit.plan, explicit.plan)
        self.assertIsNone(implicit._native_sdk_inputs)
        self.assertIsNone(implicit._planned_sdk_inputs)
        implicit.require_unchanged()
        explicit.require_unchanged()

    def test_passive_sdk_descriptor_cannot_plan_as_an_admitted_owner(self):
        for descriptor in ({"identity": "saved-sdk-cache"}, object()):
            with self.subTest(descriptor=descriptor), self.assertRaises(TypeError):
                self.fixture.plan(native_sdk_inputs=descriptor)

    def test_late_sdk_selection_change_cannot_reuse_original_no_sdk_plan(self):
        current = self.fixture.plan()
        object.__setattr__(current, "_native_sdk_inputs", object())
        with self.assertRaisesRegex(ValueError, "original-planned-sdk-owner-changed"):
            current.require_unchanged()

    def test_projection_cannot_introduce_an_sdk_owner_absent_from_current_plan(self):
        current = self.fixture.plan()
        with self.assertRaisesRegex(TypeError, "original-planned-sdk-owner-required"):
            with open_current_authored_qualification_projection(
                current, native_sdk_inputs=object()
            ):
                self.fail("projection accepted a substituted SDK owner")
