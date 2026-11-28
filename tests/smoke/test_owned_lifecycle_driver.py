"""Stage admission in the private synchronous driver, not SDK qualification."""

import unittest
from concurrent.futures import Future
from unittest import mock

from literate_ai.application.standard_project_lifecycle import (
    StandardProjectLifecycleService,
    _LifecycleStep,
)
from literate_ai.contracts import StandardLifecycleStage


class OwnedLifecycleDriverTests(unittest.TestCase):
    def setUp(self):
        self.service = object.__new__(StandardProjectLifecycleService)
        self.events = []
        self.alive = True

    def owner(self):
        if not self.alive:
            raise ValueError("original operation ended")

    def reservation(self, *, run=None, release=None):
        fixture = self

        class Reservation:
            def run(self):
                fixture.events.append("reserved run")
                return run() if run else "stage result"

            def release(self):
                fixture.events.append("release")
                if release:
                    release()

        return Reservation()

    def drive(self, steps):
        self.service._run_complete_node_steps = lambda: steps
        return self.service._run_complete_node(require_current=self.owner)

    def step(self, reserve=None, guard=None):
        return _LifecycleStep(
            StandardLifecycleStage.BUILD,
            lambda: self.events.append("raw operation"),
            guard,
            reserve,
        )

    def test_capacity_retry_uses_reserved_runner_and_releases(self):
        reservation = self.reservation()
        reserve = mock.Mock(side_effect=[None, None, reservation])

        def steps():
            result = yield self.step(reserve, lambda: self.events.append("stage guard"))
            self.events.append("continuation")
            return result

        with mock.patch(
            "literate_ai.application.standard_project_lifecycle.time.sleep"
        ) as sleep:
            self.assertEqual(self.drive(steps()), "stage result")
        self.assertEqual(reserve.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(
            self.events, ["stage guard", "reserved run", "release", "continuation"]
        )

    def test_owner_loss_while_waiting_never_runs_or_repairs(self):
        def reserve():
            self.alive = False
            return None

        def steps():
            try:
                yield self.step(reserve)
            except ValueError:
                self.events.append("repair")
            finally:
                self.events.append("closed")

        with self.assertRaisesRegex(ValueError, "operation ended"):
            self.drive(steps())
        self.assertEqual(self.events, ["closed"])

    def test_revocation_during_reservation_releases_without_run(self):
        def reserve():
            self.alive = False
            return self.reservation()

        def steps():
            yield self.step(reserve)

        with self.assertRaises(ValueError):
            self.drive(steps())
        self.assertEqual(self.events, ["release"])

    def test_revocation_in_stage_guard_releases_without_run(self):
        def stage_guard():
            self.alive = False

        def steps():
            yield self.step(lambda: self.reservation(), stage_guard)

        with self.assertRaises(ValueError):
            self.drive(steps())
        self.assertEqual(self.events, ["release"])

    def test_revocation_in_release_withholds_result_and_repair(self):
        def revoke():
            self.alive = False

        def steps():
            try:
                yield self.step(lambda: self.reservation(release=revoke))
            except ValueError:
                self.events.append("repair")
            self.events.append("continuation")

        with self.assertRaises(ValueError):
            self.drive(steps())
        self.assertEqual(self.events, ["reserved run", "release"])

    def test_ordinary_stage_failure_uses_existing_repair_chain(self):
        def fail():
            raise RuntimeError("ordinary stage failure")

        def steps():
            try:
                yield self.step(lambda: self.reservation(run=fail))
            except RuntimeError:
                self.events.append("repair")
            return "repaired"

        self.assertEqual(self.drive(steps()), "repaired")
        self.assertEqual(self.events, ["reserved run", "release", "repair"])

    def test_owner_loss_during_final_generator_cleanup_withholds_result(self):
        def steps():
            try:
                yield self.step(lambda: self.reservation())
                return "must not escape"
            finally:
                self.alive = False

        with self.assertRaises(ValueError):
            self.drive(steps())

    def test_non_synchronous_or_non_none_owner_cannot_advance_or_reserve(self):
        async def asynchronous():
            self.fail("async owner executed")

        def generator():
            yield None

        class AsyncOwner:
            async def __call__(self):
                self.fail("async callable owner executed")

        def steps():
            self.events.append("advanced")
            yield self.step(lambda: self.events.append("reserved"))

        self.service._run_complete_node_steps = mock.Mock(side_effect=steps)
        for owner in (
            asynchronous,
            generator,
            AsyncOwner(),
            lambda: False,
            lambda: Future(),
            False,
        ):
            with self.subTest(owner=type(owner)), self.assertRaises(TypeError):
                self.service._run_complete_node(require_current=owner)
        self.service._run_complete_node_steps.assert_not_called()
        self.assertEqual(self.events, [])

    def test_hidden_coroutine_owner_is_closed_before_any_stage(self):
        async def asynchronous():
            self.fail("async owner executed")

        result = asynchronous()
        self.service._run_complete_node_steps = mock.Mock()
        with self.assertRaises(TypeError):
            self.service._run_complete_node(require_current=lambda: result)
        self.assertIsNone(result.cr_frame)
        self.service._run_complete_node_steps.assert_not_called()

    def test_caught_owner_failure_cannot_resume_operation(self):
        returned = []

        def owner():
            if returned:
                return False

        def run():
            returned.append(True)
            return "must not escape"

        def steps():
            try:
                yield self.step(lambda: self.reservation(run=run))
            except TypeError:
                self.events.append("repair")

        self.service._run_complete_node_steps = steps
        with self.assertRaises(TypeError):
            self.service._run_complete_node(require_current=owner)
        self.assertEqual(self.events, ["reserved run", "release"])


if __name__ == "__main__":
    unittest.main()
