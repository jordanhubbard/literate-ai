"""Actual native guards; review/framework/provider ports remain explicit fixtures."""

import inspect
import unittest
from contextlib import nullcontext
from unittest import mock

import tests.critical.test_authored_qualification_planning as fixture
from literate_ai.adapters import authored_qualification_planning as planning
from literate_ai.adapters import legacy_generation_catalog as flavors
from literate_ai.adapters.authored_qualification_authority import (
    CurrentAuthoredQualificationAuthority,
)
from literate_ai.projects import PinnedInputClosure


class AuthoredPlanProjectionTests(unittest.TestCase):
    setUp = fixture.AuthoredQualificationPlanningTests.setUp
    plan = fixture.AuthoredQualificationPlanningTests.plan
    files = fixture.AuthoredQualificationPlanningTests.files

    def observe(self, current, *, captured):
        counts = dict(authority=0, reads=0, review=0, selector=0)
        actual_authority = CurrentAuthoredQualificationAuthority.require_unchanged
        actual_read = PinnedInputClosure._read
        actual_review, actual_selector = current._reviewer, current._coding_selector

        def authority(owner):
            counts["authority"] += 1
            return actual_authority(owner)

        def read(*args, **kwargs):
            counts["reads"] += 1
            return actual_read(*args, **kwargs)

        def review(*args, **kwargs):
            counts["review"] += 1
            return actual_review(*args, **kwargs)

        def selector(*args, **kwargs):
            counts["selector"] += 1
            return actual_selector(*args, **kwargs)

        def validating_projection(oracles):
            # Same original public accessors, never a substituted result.
            return oracles.authority.origin, oracles.identity

        object.__setattr__(current, "_reviewer", review)
        object.__setattr__(current, "_coding_selector", selector)
        try:
            with (
                mock.patch.object(
                    CurrentAuthoredQualificationAuthority,
                    "require_unchanged",
                    authority,
                ),
                mock.patch.object(PinnedInputClosure, "_read", read),
                nullcontext()
                if captured
                else mock.patch.object(
                    planning, "_plan_oracle_projection", validating_projection
                ),
            ):
                current.require_unchanged()
        finally:
            object.__setattr__(current, "_reviewer", actual_review)
            object.__setattr__(current, "_coding_selector", actual_selector)
        return counts

    def test_complete_guards_reduce_duplicate_observation_and_start_cold_each_time(
        self,
    ):
        current = self.plan()
        before = self.files()
        identity = current.plan.identity
        baseline = self.observe(current, captured=False)
        candidate = self.observe(current, captured=True)
        repeated = self.observe(current, captured=True)
        self.assertEqual(candidate, repeated)
        self.assertEqual(candidate["review"], baseline["review"])
        self.assertEqual(candidate["selector"], baseline["selector"])
        self.assertGreater(candidate["authority"], 0)
        self.assertGreater(candidate["reads"], 0)
        self.assertLess(candidate["authority"], baseline["authority"])
        self.assertLess(candidate["reads"], baseline["reads"])
        self.assertEqual(current.plan.identity, identity)
        self.assertEqual(self.files(), before)

    def test_public_accessors_still_validate_and_private_values_grant_no_currency(self):
        current = self.plan()
        self.assertEqual(current.oracles._captured_identity(), current.oracles.identity)
        path = self.fixture.oracle_root / "harness.py"
        original = path.read_bytes()
        expected = current.oracles._captured_identity()
        changed = original + b"\nReal independent verifier source changed.\n"
        try:
            path.write_bytes(changed)
            self.assertEqual(current.oracles._captured_identity(), expected)
            with self.assertRaises((ValueError, RuntimeError)):
                _ = current.oracles.identity
            for captured in (False, True):
                with self.subTest(captured=captured):
                    with self.assertRaises((ValueError, RuntimeError)):
                        self.observe(current, captured=captured)
                    self.assertEqual(path.read_bytes(), changed)
        finally:
            path.write_bytes(original)
        path = self.fixture.component / "component.md"
        original = path.read_bytes()
        try:
            path.write_bytes(original + b"\nOriginal authoring changed.\n")
            with self.assertRaises((ValueError, RuntimeError)):
                _ = current.oracles.authority.origin
        finally:
            path.write_bytes(original)

    def test_reviewer_cannot_replace_plan_fields_after_earlier_comparisons(self):
        current = self.plan()
        actual_review = current._reviewer
        original = current.plan.output_root
        reached = []

        def review(*args, **kwargs):
            result = actual_review(*args, **kwargs)
            reached.append(True)
            object.__setattr__(current.plan, "output_root", original + "-foreign")
            return result

        object.__setattr__(current, "_reviewer", review)
        try:
            with self.assertRaisesRegex(
                ValueError, "original-plan-observation-changed"
            ):
                current.require_unchanged()
            self.assertTrue(reached)
        finally:
            object.__setattr__(current, "_reviewer", actual_review)
            object.__setattr__(current.plan, "output_root", original)

    def test_last_real_flavor_close_cannot_poison_original_oracle_bindings(self):
        current = self.plan()
        actual = flavors.LegacyFlavorGraphObservation.require_current
        closing_code = flavors.read_only_flavor_graph_observations.__wrapped__.__code__
        original = current.oracles.bindings
        reached = []

        def close_then_change(owner, *args, **kwargs):
            result = actual(owner, *args, **kwargs)
            if not reached and inspect.currentframe().f_back.f_code is closing_code:
                reached.append(True)
                object.__setattr__(
                    current.oracles, "bindings", tuple(reversed(original))
                )
            return result

        try:
            with mock.patch.object(
                flavors.LegacyFlavorGraphObservation,
                "require_current",
                close_then_change,
            ):
                with self.assertRaisesRegex(
                    ValueError, "original-plan-observation-changed"
                ):
                    current.require_unchanged()
            self.assertEqual(reached, [True])
        finally:
            object.__setattr__(current.oracles, "bindings", original)
