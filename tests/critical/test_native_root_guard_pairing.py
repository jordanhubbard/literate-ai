"""Fresh original guard custody with real run/sequence and typed model records.

The counted scope models backend observation only. No compiler, installed
framework, generated process, or independent native qualification runs here.
"""

import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.application.native_root_candidate_sequence import (
    open_native_root_candidate_sequence,
)
from literate_ai.application.native_root_continuation import NativeRootController
from literate_ai.application.native_root_run import NativeRootRunError
from tests.critical import test_native_root_candidate_sequence as sequence_fixture


class _CountedScope:
    """A genuine bound method, modeling the backend's fresh custody scan."""

    def __init__(self, owner, binding):
        self._original_run = owner
        self._run_binding = binding
        self.metadata_observer = None
        self.prepared_root = object()
        self.calls = 0
        self.action = None
        self.closed = False

    @property
    def original_run(self):
        if self.metadata_observer is not None:
            self.metadata_observer("original_run")
        return self._original_run

    @property
    def run_binding(self):
        if self.metadata_observer is not None:
            self.metadata_observer("run_binding")
        return self._run_binding

    def require_current(self):
        self.calls += 1
        if self.action is not None:
            self.action()

    def close(self):
        self.closed = True

    def other_guard(self):
        self.calls += 1


class NativeRootGuardPairingTests(unittest.TestCase):
    setUp = sequence_fixture.NativeRootCandidateSequenceTests.setUp
    original_run = sequence_fixture.NativeRootCandidateSequenceTests.original_run

    def scope(self, owner):
        return _CountedScope(
            owner,
            replace(
                self.records.run,
                run_nonce=owner.deadline.run_nonce,
                original_deadline_identity=owner.deadline.identity,
            ),
        )

    def sequence(self, scope, *, callback=None):
        return open_native_root_candidate_sequence(
            scope.original_run,
            scope.run_binding,
            project_authority_identity=scope.run_binding.project_authority_identity,
            require_current=scope.require_current if callback is None else callback,
            qualified_dependencies=(self.records.dependency,),
        )

    @contextmanager
    def paired(self):
        with self.original_run() as owner:
            scope = self.scope(owner)
            with self.sequence(scope) as sequence:
                controller = NativeRootController(scope, mock.Mock(), sequence)
                scope.calls = 0
                yield scope, sequence, controller

    def assert_closed(self, sequence):
        with self.assertRaises(NativeRootRunError) as raised:
            sequence.require_current()
        self.assertEqual(
            raised.exception.code, "native_root_run.candidate_sequence_closed"
        )

    def test_each_boundary_calls_original_bound_guard_once_and_later_calls_are_fresh(
        self,
    ):
        with self.paired() as (scope, _sequence, controller):
            controller.require_current()
            self.assertEqual(scope.calls, 1)
            controller.require_current()
            self.assertEqual(scope.calls, 2)
            failure = ValueError("fresh third scan detects changed custody")
            scope.action = mock.Mock(side_effect=failure)
            with self.assertRaises(ValueError) as raised:
                controller.require_current()
            self.assertIs(raised.exception, failure)
            self.assertEqual(scope.calls, 3)

    def test_closed_original_run_retires_original_scope_without_an_extra_scan(self):
        with self.paired() as (scope, sequence, controller):
            scope.original_run.close()
            with self.assertRaises(NativeRootRunError) as caught:
                controller.require_current()
            self.assertEqual(caught.exception.code, "native_root_run.closed")
            self.assertTrue(scope.closed)
            self.assertEqual(scope.calls, 0)
            self.assert_closed(sequence)

    def test_scope_metadata_getters_run_outside_sequence_lock(self):
        with self.paired() as (scope, sequence, controller):
            observed = []

            def check_lock(name):
                acquired = sequence._lock.acquire(blocking=False)
                if acquired:
                    sequence._lock.release()
                self.assertTrue(acquired, "scope metadata read under sequence lock")
                observed.append(name)

            scope.metadata_observer = check_lock
            controller.require_current()
            self.assertEqual(scope.calls, 1)
            self.assertEqual(
                observed,
                ["original_run", "run_binding", "original_run", "run_binding"],
            )

    def test_callback_cannot_redirect_closing_check_to_a_foreign_live_run(self):
        with self.paired() as (scope, sequence, controller):
            with self.original_run() as foreign:
                scope.action = lambda: setattr(sequence, "_run", foreign)
                with (
                    mock.patch.object(
                        foreign, "_check_current", wraps=foreign._check_current
                    ) as foreign_guard,
                    self.assertRaises(NativeRootRunError) as raised,
                ):
                    controller.require_current()
                self.assertEqual(
                    raised.exception.code, "native_root_run.candidate_sequence_changed"
                )
                foreign_guard.assert_not_called()
                self.assertEqual(scope.calls, 1)
                self.assert_closed(sequence)
                foreign.require_current()

    def test_original_callback_runs_outside_sequence_lock(self):
        with self.paired() as (scope, sequence, controller):

            def check_lock():
                acquired = sequence._lock.acquire(blocking=False)
                self.assertTrue(acquired, "original callback ran under sequence lock")
                if acquired:
                    sequence._lock.release()

            scope.action = check_lock
            controller.require_current()
            self.assertEqual(scope.calls, 1)

    def test_noop_foreign_bound_or_recreated_callback_refused_before_any_guard(self):
        for substitution in ("noop", "foreign", "recreated"):
            with (
                self.subTest(substitution=substitution),
                self.paired() as (scope, sequence, controller),
                self.paired() as (foreign, _foreign_sequence, _foreign_controller),
            ):
                replacement = {
                    "noop": mock.Mock(),
                    "foreign": foreign.require_current,
                    "recreated": scope.require_current,
                }[substitution]
                sequence._current = replacement
                with self.assertRaises(NativeRootRunError):
                    controller.require_current()
                self.assertEqual(scope.calls, 0)
                self.assertEqual(foreign.calls, 0)
                if substitution == "noop":
                    replacement.assert_not_called()
                self.assert_closed(sequence)

    def test_callback_changed_during_callback_refuses_closes_and_never_runs_replacement(
        self,
    ):
        with self.paired() as (scope, sequence, controller):
            original = sequence._current
            replacement = mock.Mock()
            scope.action = lambda: setattr(sequence, "_current", replacement)
            with self.assertRaises(NativeRootRunError) as raised:
                controller.require_current()
            self.assertEqual(
                raised.exception.code, "native_root_run.candidate_sequence_changed"
            )
            self.assertEqual(scope.calls, 1)
            replacement.assert_not_called()
            sequence._current = original
            self.assert_closed(sequence)
            with self.assertRaises(NativeRootRunError):
                with self.sequence(scope):
                    self.fail("closed sequence renewed its original root allowance")

    def test_initial_noop_or_wrong_bound_function_cannot_pair_with_scope(self):
        for kind in ("noop", "wrong-function"):
            with self.subTest(kind=kind), self.original_run() as owner:
                scope = self.scope(owner)
                callback = mock.Mock() if kind == "noop" else scope.other_guard
                with self.sequence(scope, callback=callback) as sequence:
                    scope.calls = 0
                    if kind == "noop":
                        callback.reset_mock()
                    with self.assertRaises(NativeRootRunError):
                        NativeRootController(scope, mock.Mock(), sequence)
                    self.assertEqual(scope.calls, 0)
                    if kind == "noop":
                        callback.assert_not_called()
                    self.assert_closed(sequence)

    def test_cross_scope_constructor_is_refused_before_foreign_guard(self):
        with (
            self.paired() as (scope, sequence, _controller),
            self.paired() as (foreign, foreign_sequence, _foreign_controller),
        ):
            with self.assertRaises(NativeRootRunError):
                NativeRootController(foreign, mock.Mock(), sequence)
            self.assertEqual(scope.calls, 0)
            self.assertEqual(foreign.calls, 0)
            self.assert_closed(sequence)
            foreign_sequence.require_current()
            self.assertEqual(foreign.calls, 1)

    def test_later_scope_or_sequence_substitution_closes_only_original_counter(self):
        for attribute in ("scope", "sequence"):
            with (
                self.subTest(attribute=attribute),
                self.paired() as (scope, sequence, controller),
                self.paired() as (foreign, foreign_sequence, _foreign_controller),
            ):
                setattr(
                    controller,
                    attribute,
                    foreign if attribute == "scope" else foreign_sequence,
                )
                with self.assertRaises(NativeRootRunError):
                    controller.require_current()
                self.assertEqual(scope.calls, 0)
                self.assertEqual(foreign.calls, 0)
                self.assert_closed(sequence)
                foreign_sequence.require_current()
                self.assertEqual(foreign.calls, 1)

    def test_sequence_original_run_and_exact_binding_cannot_be_substituted(self):
        for attribute in ("_run", "_binding"):
            with (
                self.subTest(attribute=attribute),
                self.paired() as (scope, sequence, controller),
                self.original_run() as foreign_owner,
            ):
                replacement = (
                    foreign_owner if attribute == "_run" else replace(scope.run_binding)
                )
                setattr(sequence, attribute, replacement)
                with self.assertRaises(NativeRootRunError):
                    controller.require_current()
                self.assertEqual(scope.calls, 0)
                self.assert_closed(sequence)

    def test_original_guard_error_identity_preserves_consumed_allocation_and_no_renewal(
        self,
    ):
        with self.paired() as (scope, sequence, controller):
            sequence.register_allocated_candidate(
                scope.run_binding.original_bounded_request_identity,
                sequence_fixture.ci("actual-model-workspace"),
                incoming_request_kind="initial",
                incoming_request_identity=None,
            )
            original_pending = sequence._pending
            failure = OSError("original custody read failure")
            scope.action = mock.Mock(side_effect=failure)
            with self.assertRaises(OSError) as raised:
                controller.require_current()
            self.assertIs(raised.exception, failure)
            self.assertEqual(sequence._pending, original_pending)
            self.assertEqual(sequence._attempts, ())
            self.assert_closed(sequence)
            scope.action = None
            with self.assertRaises(NativeRootRunError):
                with self.sequence(scope):
                    self.fail("failure renewed the consumed candidate counter")

    def test_original_deadline_expires_without_callback_or_counter_renewal(self):
        with self.paired() as (scope, sequence, controller):
            deadline = scope.original_run.deadline
            sequence.register_allocated_candidate(
                scope.run_binding.original_bounded_request_identity,
                sequence_fixture.ci("deadline-model-workspace"),
                incoming_request_kind="initial",
                incoming_request_identity=None,
            )
            pending = sequence._pending
            scope.calls = 0
            self.monotonic += 120_000_000_000
            with self.assertRaises(NativeRootRunError) as raised:
                controller.require_current()
            self.assertEqual(raised.exception.code, "native_root_run.expired")
            self.assertEqual(scope.calls, 0)
            self.assertIs(scope.original_run.deadline, deadline)
            self.assertEqual(sequence._pending, pending)
            self.monotonic = 1_000_000_000
            self.assert_closed(sequence)
            with self.assertRaises(NativeRootRunError):
                with self.sequence(scope):
                    self.fail("clock reset renewed original expired root")
