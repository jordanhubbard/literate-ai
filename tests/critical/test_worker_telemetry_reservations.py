"""Actual controller capacity/dispatch provenance; no worker telemetry route claim."""

import dataclasses
import pickle
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest import mock

from literate_ai.adapters.action_slots import CommandActionSlots
from literate_ai.application import worker_telemetry_reservations as observation
from literate_ai.application.action_dag_scheduler import LifecycleActionTermination
from literate_ai.contracts.identity import canonical_identity
from tests.e2e import test_action_dispatch_wire as fixtures


class WorkerTelemetryReservationTests(unittest.TestCase):
    def setUp(self):
        self.request, self.deadline, self.records = fixtures.request_fixture()
        self.slots = CommandActionSlots(
            (self.request.worker,), self.deadline, observe_reservations=True
        )

    def test_actual_reserved_run_publishes_read_only_current_provenance(self):
        views = []

        def execute(worker, slot):
            self.assertEqual(worker, self.request.worker)
            self.assertEqual(slot, self.request.slot)
            view = observation.bind_current_action_reservation(self.request)
            self.assertEqual(
                view.require_current().binding_identity,
                observation.current_action_reservation_observation()
                .require_current()
                .binding_identity,
            )
            snapshot = view.require_current(self.request)
            self.assertEqual(snapshot.action_identity, self.request.action.identity)
            self.assertEqual(snapshot.worker_identity, worker.worker_identity)
            self.assertEqual(snapshot.deadline_identity, self.deadline.identity)
            for name in ("run", "release", "cancel", "dispatch", "condition"):
                self.assertFalse(hasattr(view, name))
            views.append(view)
            return "actual operation result"

        self.assertEqual(
            self.slots.try_reserve(execute).run(), "actual operation result"
        )
        with self.assertRaises(observation.ReservationObservationError):
            views[0].require_current()
        self.assertEqual(self.slots._reservation_observations, {})
        self.assertEqual(self.slots._occupied, set())

    def test_acquire_context_joins_the_original_slot_and_retires_its_view(self):
        with self.slots.acquire() as (worker, slot):
            self.assertEqual((worker, slot), (self.request.worker, 0))
            view = observation.bind_current_action_reservation(self.request)
            view.require_current(self.request)
            self.assertIsNone(self.slots.try_reserve(lambda *_: None))
        with self.assertRaises(observation.ReservationObservationError):
            view.require_current()
        self.assertEqual(self.slots._held, set())

    def test_real_command_dispatch_binds_before_input_transfer_without_a_job_lock(self):
        fixture = fixtures.CommandActionDispatchTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        dispatcher, request = fixture.dispatcher()
        slots = CommandActionSlots(
            (request.worker,), dispatcher.deadline, observe_reservations=True
        )
        ready, proceed = threading.Event(), threading.Event()
        original = dispatcher.input_records
        views = []

        def records(value):
            view = observation.current_action_reservation_observation()
            view.require_current(value)
            views.append(view)
            ready.set()
            if not proceed.wait(timeout=10):
                raise TimeoutError("bounded controller fixture wait")
            return original(value)

        dispatcher.input_records = records
        reserved = slots.try_reserve(lambda *_: dispatcher.dispatch(request))
        with ThreadPoolExecutor(max_workers=2) as pool:
            action = pool.submit(reserved.run)
            try:
                self.assertTrue(ready.wait(timeout=10))
                with slots.condition:
                    # Another thread can read even while the control lock is held.
                    read = pool.submit(views[0].require_current, request)
                    snapshot = read.result(timeout=2)
                    self.assertEqual(snapshot.request_identity, request.identity)
            finally:
                proceed.set()
            outcome = action.result(timeout=20)
        self.assertIn(outcome.result_identity, fixture.results)
        self.assertEqual(len(fixture.admissions), 2)
        with self.assertRaises(observation.ReservationObservationError):
            views[0].require_current()

    def test_records_or_unissued_objects_cannot_reconstruct_the_actual_owner(self):
        def execute(*_):
            view = observation.bind_current_action_reservation(self.request)
            snapshot = view.require_current()
            self.assertIsNone(
                observation.create_original_reservation_observer(
                    self.request.worker, self.request.slot, self.deadline
                )
            )
            with self.assertRaises(observation.ReservationObservationError):
                observation.ActionReservationObservation(
                    dataclasses.asdict(snapshot), snapshot, _issuer=object()
                )
            with self.assertRaises(observation.ReservationObservationError):
                object.__new__(
                    observation.ActionReservationObservation
                ).require_current()
            with self.assertRaises(TypeError):
                pickle.dumps(view)
            with self.assertRaises(AttributeError):
                view._binding = snapshot

        self.slots.try_reserve(execute).run()

    def test_exchange_retirement_preserves_capacity_and_cannot_revive_its_old_view(
        self,
    ):
        fixture = fixtures.CommandActionDispatchTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        dispatcher, request = fixture.dispatcher()
        slots = CommandActionSlots(
            (request.worker,), dispatcher.deadline, observe_reservations=True
        )
        original = dispatcher.input_records
        views = []

        def records(value):
            views.append(observation.current_action_reservation_observation())
            return original(value)

        dispatcher.input_records = records
        with slots.acquire():
            result = dispatcher.dispatch(request)
            self.assertIn(result.result_identity, fixture.results)
            self.assertIsNone(observation.current_action_reservation_observation())
            with self.assertRaises(observation.ReservationObservationError):
                views[0].require_current()
            self.assertIsNone(slots.try_reserve(lambda *_: None))
            successor = observation.bind_current_action_reservation(request)
            observation.finish_action_reservation_observation(views[0])
            successor.require_current(request)
        self.assertEqual(slots._held, set())

    def test_same_worker_slot_and_deadline_have_fresh_original_reservation_identities(
        self,
    ):
        snapshots = []

        def execute(*_):
            snapshots.append(
                observation.bind_current_action_reservation(
                    self.request
                ).require_current()
            )

        self.slots.try_reserve(execute).run()
        self.slots.try_reserve(execute).run()
        rebuilt = CommandActionSlots(
            (self.request.worker,), self.deadline, observe_reservations=True
        )
        rebuilt.try_reserve(execute).run()
        self.assertEqual(len({s.reservation_identity for s in snapshots}), 3)
        self.assertEqual(len({s.binding_identity for s in snapshots}), 3)

    def test_new_request_binding_cannot_retarget_a_retained_old_view(self):
        def execute(*_):
            old = observation.bind_current_action_reservation(self.request)
            next_request = replace(
                self.request,
                action=replace(self.request.action, action_id="other-action"),
            )
            new = observation.bind_current_action_reservation(next_request)
            new.require_current(next_request)
            with self.assertRaises(observation.ReservationObservationError):
                old.require_current()
            with self.assertRaisesRegex(
                observation.ReservationObservationError, "request_mismatch"
            ):
                new.require_current(self.request)

        self.slots.try_reserve(execute).run()

    def test_foreign_binding_refuses_observation_and_preserves_the_actual_operation(
        self,
    ):
        def execute(*_):
            foreign = replace(
                self.request, deadline_identity=canonical_identity("foreign")
            )
            self.assertIsNone(observation.bind_current_action_reservation(foreign))
            self.assertIsNone(observation.bind_current_action_reservation(self.request))
            return "preserved"

        self.assertEqual(self.slots.try_reserve(execute).run(), "preserved")
        self.assertEqual(self.slots._occupied, set())
        self.assertEqual(self.slots.unresolved_ownership, ())

    def test_unknown_ownership_resolution_does_not_reactivate_the_old_observer(self):
        def execute(*_):
            view = observation.bind_current_action_reservation(self.request)
            self.slots.quarantine(self.request)
            with self.assertRaises(observation.ReservationObservationError):
                view.require_current()
            self.slots.resolve_ownership(
                LifecycleActionTermination(
                    self.request.identity,
                    self.request.worker.worker_identity,
                    canonical_identity("trusted terminal fixture"),
                    "owned-terminal",
                    1,
                ),
                require_held=True,
            )
            with self.assertRaises(observation.ReservationObservationError):
                view.require_current()

        self.slots.try_reserve(execute).run()
        self.assertEqual(self.slots.unresolved_ownership, ())
        self.assertEqual(self.slots._occupied, set())

    def test_observation_clock_refusal_cannot_change_or_revive_the_job_deadline(self):
        deadline_before = self.deadline.to_dict()

        def execute(*_):
            view = observation.bind_current_action_reservation(self.request)
            value = view.require_current()
            with mock.patch.object(
                observation.time,
                "time_ns",
                return_value=value.expires_at_ms * 1_000_000,
            ):
                with self.assertRaises(observation.ReservationObservationError):
                    view.require_current()
            with self.assertRaises(observation.ReservationObservationError):
                view.require_current()
            self.assertGreater(self.deadline.remaining(), 0)
            return "unchanged"

        self.assertEqual(self.slots.try_reserve(execute).run(), "unchanged")
        self.assertEqual(self.deadline.to_dict(), deadline_before)

    def test_busy_observation_bookkeeping_refuses_without_mutating_capacity(self):
        def execute(*_):
            view = observation.bind_current_action_reservation(self.request)
            view._holder._clock_lock.acquire()
            try:
                with self.assertRaisesRegex(
                    observation.ReservationObservationError, "busy"
                ):
                    view.require_current()
            finally:
                view._holder._clock_lock.release()
            view.require_current()
            self.assertIsNone(self.slots.try_reserve(lambda *_: None))

        self.slots.try_reserve(execute).run()

    def test_observation_setup_failure_does_not_change_existing_capacity_behavior(self):
        with mock.patch(
            "literate_ai.adapters.action_slots.create_original_reservation_observer",
            return_value=None,
        ):

            def execute(*_):
                self.assertIsNone(
                    observation.bind_current_action_reservation(self.request)
                )
                self.assertIsNone(observation.current_action_reservation_observation())
                return "normal result"

            self.assertEqual(self.slots.try_reserve(execute).run(), "normal result")
        self.assertEqual(self.slots._held, set())

    def test_legacy_capacity_requires_startup_opt_in_to_publish_an_observation(self):
        slots = CommandActionSlots((self.request.worker,), self.deadline)

        def execute(*_):
            self.assertIsNone(observation.bind_current_action_reservation(self.request))
            self.assertIsNone(observation.current_action_reservation_observation())
            return "legacy"

        self.assertEqual(slots.try_reserve(execute).run(), "legacy")
        self.assertEqual(slots._reservation_observations, {})

        def outer(*_):
            view = observation.bind_current_action_reservation(self.request)
            self.assertEqual(slots.try_reserve(execute).run(), "legacy")
            view.require_current(self.request)
            restored = observation.current_action_reservation_observation()
            self.assertEqual(
                restored.require_current().reservation_identity,
                view.require_current().reservation_identity,
            )

        self.slots.try_reserve(outer).run()
        for invalid in (1, "true", None):
            with self.subTest(invalid=invalid), self.assertRaises(TypeError):
                CommandActionSlots(
                    (self.request.worker,), self.deadline, observe_reservations=invalid
                )
