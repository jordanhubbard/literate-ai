"""Actual canonical projection objects and native Python tool observations.

The maintained fixture injects review/framework/provider admission and macOS
selection. No generated application, model, SDK or consumer admission is proved.
"""

import copy
import pickle
import time
import unittest
from unittest.mock import patch

from literate_ai.adapters import authored_qualification_projection as projection
from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthoritySnapshot,
)
from literate_ai.adapters.standard_project import ProjectedStandardToolchainClosure
from literate_ai.projects import PinnedInputClosureError
from tests.critical import test_authored_qualification_projection as fixtures


class AuthoredProjectionCompletionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.AuthoredQualificationProjectionTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.current = self.fixture.current
        self.enterContext(
            patch(
                "literate_ai.adapters.standard_project._host_platform_target",
                return_value="macos",
            )
        )

    def capture(self):
        return projection._open_current_authored_qualification_projection_session(
            self.current
        )

    def test_original_objects_refresh_after_close_but_public_projection_stays_expired(
        self,
    ):
        deadline = time.monotonic() + 900
        with self.capture() as session:
            session.projection.require_unchanged()
            session.completion.require_original_files()
        with self.assertRaisesRegex(ValueError, "projection_owner_expired"):
            session.projection.require_unchanged()
        session.completion.refresh_current(deadline=deadline)
        trap = AssertionError("raw projection invoked current owner or tool callbacks")
        with (
            patch.object(
                projection.CurrentAuthoredQualificationProjection,
                "require_unchanged",
                side_effect=trap,
            ),
            patch.object(
                CurrentAuthoredQualificationPlan, "require_unchanged", side_effect=trap
            ),
            patch.object(
                LockedGenerationAuthoritySnapshot, "require_unchanged", side_effect=trap
            ),
            patch.object(
                type(session.completion._projector), "guard", side_effect=trap
            ),
            patch.object(
                ProjectedStandardToolchainClosure, "require_unchanged", side_effect=trap
            ),
            patch("subprocess.run", side_effect=trap),
            patch("subprocess.Popen", side_effect=trap),
        ):
            session.completion.require_original_files()
        for value in (session, session.completion):
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(
                    type=type(value).__name__, operation=operation.__name__
                ):
                    with self.assertRaises(TypeError):
                        operation(value)

    def test_after_last_actual_current_refresh_source_mutation_refuses_and_is_preserved(
        self,
    ):
        deadline = time.monotonic() + 900
        with self.capture() as session:
            pass
        path = self.fixture.fixture.fixture.component / "specs/spec.md"
        changed = path.read_bytes() + b"\nPreserve final current callback change.\n"
        actual = CurrentAuthoredQualificationPlan.require_unchanged
        calls = []

        def late(owner):
            result = actual(owner)
            if owner is self.current:
                calls.append(owner)
                if len(calls) == 2:
                    path.write_bytes(changed)
            return result

        with patch.object(
            CurrentAuthoredQualificationPlan, "require_unchanged", new=late
        ):
            with self.assertRaises(PinnedInputClosureError):
                session.completion.refresh_current(deadline=deadline)
        self.assertEqual(len(calls), 2)
        self.assertEqual(path.read_bytes(), changed)

    def test_changed_actual_contract_tuple_cannot_choose_a_replacement_baseline(self):
        with self.capture() as session:
            pass
        closure = session.completion._closure
        changed = tuple(reversed(closure.contracts))
        self.assertGreater(len(changed), 1)
        object.__setattr__(closure, "contracts", changed)
        with patch.object(
            projection,
            "project_locked_standard_toolchain_closure",
            side_effect=AssertionError("fresh projection"),
        ):
            with self.assertRaisesRegex(
                ValueError, "original-projection-owner-changed"
            ):
                session.completion.require_original_files()
        self.assertIs(closure.contracts, changed)

    def test_expired_original_deadline_refuses_before_any_refresh_callback(self):
        deadline = time.monotonic() + 900
        with self.capture() as session:
            pass
        with (
            patch("time.monotonic", return_value=deadline + 1),
            patch.object(
                CurrentAuthoredQualificationPlan,
                "require_unchanged",
                side_effect=AssertionError("expired callback"),
            ),
        ):
            with self.assertRaisesRegex(ValueError, "completion-deadline"):
                session.completion.refresh_current(deadline=deadline)

    def test_actual_last_current_refresh_overrun_is_not_accepted(self):
        deadline = time.monotonic() + 900
        with self.capture() as session:
            pass
        actual = CurrentAuthoredQualificationPlan.require_unchanged
        clock = time.monotonic
        state = {"calls": 0, "late": False}

        def late(owner):
            result = actual(owner)
            if owner is self.current:
                state["calls"] += 1
                if state["calls"] == 2:
                    state["late"] = True
            return result

        with (
            patch(
                "time.monotonic",
                side_effect=lambda: deadline + 1 if state["late"] else clock(),
            ),
            patch.object(
                CurrentAuthoredQualificationPlan, "require_unchanged", new=late
            ),
        ):
            with self.assertRaisesRegex(ValueError, "completion-deadline"):
                session.completion.refresh_current(deadline=deadline)
        self.assertEqual(state["calls"], 2)

    def test_replaced_original_dependency_guard_is_not_invoked(self):
        with self.capture() as session:
            pass

        class Replacement:
            calls = 0

            def __eq__(self, other):
                return True

            def __call__(self):
                self.calls += 1

        changed = Replacement()
        closure = session.completion._closure
        object.__setattr__(closure, "dependency_guard", changed)
        with self.assertRaisesRegex(ValueError, "original-projection-owner-changed"):
            session.completion.refresh_current(deadline=time.monotonic() + 900)
        self.assertEqual(changed.calls, 0)
        self.assertIs(closure.dependency_guard, changed)

    def test_last_actual_current_callback_cannot_disable_original_closure_plan_guard(
        self,
    ):
        deadline = time.monotonic() + 900
        with self.capture() as session:
            pass
        closure = session.completion._closure
        self.assertIsNotNone(closure.execution_plan)
        actual = CurrentAuthoredQualificationPlan.require_unchanged
        calls = []

        def late(owner):
            result = actual(owner)
            if owner is self.current:
                calls.append(owner)
                if len(calls) == 2:
                    object.__setattr__(closure, "execution_plan", None)
            return result

        with patch.object(
            CurrentAuthoredQualificationPlan, "require_unchanged", new=late
        ):
            with self.assertRaisesRegex(
                ValueError, "original-projection-owner-changed"
            ):
                session.completion.refresh_current(deadline=deadline)
        self.assertEqual(len(calls), 2)
        self.assertIsNone(closure.execution_plan)
