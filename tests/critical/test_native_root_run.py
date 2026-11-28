"""Original run lifetime constraints; no native execution or permission grant."""

from __future__ import annotations

import copy
import pickle
import unittest
from unittest import mock

from literate_ai.application import native_root_run as run
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootRunDeadline,
    NativeRootRunPolicy,
)


class NativeRootRunTests(unittest.TestCase):
    def setUp(self):
        self.utc = 1_000_000_000_000
        self.monotonic = 1_000_000_000
        self.checks = []
        self.arguments = {
            "project_identity": canonical_identity({"project": "root"}),
            "framework_distribution_identity": canonical_identity({"framework": 1}),
            "lifecycle_policy_identity": canonical_identity({"lifecycle": 1}),
            "require_current": lambda: self.checks.append(True),
            "utc_clock": lambda: self.utc,
            "monotonic_clock": lambda: self.monotonic,
        }

    def open(self, seconds=10, **kwargs):
        return run.open_native_root_run(
            NativeRootRunPolicy(max_duration_seconds=seconds, candidate_limit=3),
            **(self.arguments | kwargs),
        )

    def assert_refused(self, operation, code):
        with self.assertRaises(run.NativeRootRunError) as caught:
            operation()
        self.assertEqual(caught.exception.code, "native_root_run." + code)

    def test_one_original_deadline_survives_multiple_operations_without_reset(self):
        with self.open() as owner:
            deadline = owner.deadline
            self.assertEqual(owner.remaining(), 10)
            self.assertEqual(owner.clamp_timeout(3), 3)
            for step in range(1, 4):
                self.utc += 2_000_000_000
                self.monotonic += 2_000_000_000
                owner.require_current()
                self.assertIs(owner.deadline, deadline)
                self.assertEqual(owner.clamp_timeout(60), 10 - 2 * step)
            self.assertEqual(len(self.checks), 4)
        self.assert_refused(owner.remaining, "closed")

    def test_native_clock_projection_uses_the_same_explicit_finite_policy(self):
        arguments = {
            key: value
            for key, value in self.arguments.items()
            if key not in {"utc_clock", "monotonic_clock"}
        }
        with run.open_native_root_run(
            NativeRootRunPolicy(max_duration_seconds=60, candidate_limit=3),
            **arguments,
        ) as owner:
            owner.deadline.require_policy(owner.policy)
            self.assertEqual(
                owner.deadline.expires_utc_ns - owner.deadline.started_utc_ns,
                60_000_000_000,
            )
            self.assertGreater(owner.remaining(), 0)
            self.assertLessEqual(owner.remaining(), 60)

    def test_explicit_longer_run_keeps_original_expiry_and_operation_caps(self):
        with self.open(seconds=3600) as owner:
            deadline = owner.deadline
            self.assertEqual(owner.remaining(), 3600)
            self.monotonic += 1_800_000_000_000
            self.utc += 1_800_000_000_000
            self.assertEqual(owner.remaining(), 1800)
            self.assertIs(owner.deadline, deadline)
            self.assertEqual(owner.clamp_timeout(600), 600)

    def test_expiry_is_irreversible_even_if_clock_is_restored(self):
        with self.open() as owner:
            self.monotonic += 10_000_000_000
            self.assert_refused(owner.remaining, "expired")
            self.monotonic -= 10_000_000_000
            self.assert_refused(owner.remaining, "closed")

    def test_utc_rollback_cannot_extend_and_forward_expiry_refuses(self):
        with self.open() as owner:
            self.utc -= 100_000_000_000
            self.monotonic += 9_000_000_000
            self.assertEqual(owner.remaining(), 1)
            self.utc = owner.deadline.expires_utc_ns
            self.assert_refused(owner.remaining, "expired")

    def test_monotonic_regression_closes_the_original_lifetime(self):
        with self.open() as owner:
            self.monotonic += 1
            owner.remaining()
            self.monotonic -= 1
            self.assert_refused(owner.remaining, "clock_regressed")
            self.assert_refused(owner.remaining, "closed")

    def test_upstream_cannot_extend_the_admitted_original_expiry(self):
        upstream = [3.0]
        with self.open(original_remaining=lambda: upstream[0]) as owner:
            self.assertEqual(owner.remaining(), 3)
            upstream[0] = 100
            self.monotonic += 2_000_000_000
            self.utc += 2_000_000_000
            self.assertEqual(owner.remaining(), 1)
            upstream[0] = 0
            self.assert_refused(owner.remaining, "timeout_invalid")
            self.assert_refused(owner.remaining, "closed")

    def test_upstream_fractional_bound_is_rounded_down_not_extended(self):
        with self.open(original_remaining=lambda: 0.3) as owner:
            numerator, denominator = (0.3).as_integer_ratio()
            self.assertEqual(
                owner.deadline.expires_utc_ns - owner.deadline.started_utc_ns,
                numerator * 1_000_000_000 // denominator,
            )

    def test_closed_projection_roundtrips_without_restoring_a_live_owner(self):
        with self.open() as owner:
            projection = NativeRootRunDeadline.from_dict(owner.deadline.to_dict())
            self.assertEqual(projection, owner.deadline)
            for operation in (
                lambda: copy.copy(owner),
                lambda: copy.deepcopy(owner),
                lambda: pickle.dumps(owner),
                run.LiveNativeRootRun,
            ):
                with self.assertRaises(TypeError):
                    operation()
        self.assertEqual(projection, owner.deadline)
        self.assert_refused(owner.remaining, "closed")

    def test_wrong_pid_never_acquires_lock_or_calls_any_external_observer(self):
        with self.open() as owner:
            with (
                mock.patch.object(run.os, "getpid", return_value=owner._pid + 1),
                mock.patch.object(owner, "_lock") as lock,
                mock.patch.object(owner, "_upstream") as upstream,
            ):
                lock.__enter__.side_effect = AssertionError("inherited lock touched")
                self.assert_refused(owner.remaining, "owner_invalid")
                self.assert_refused(owner.require_current, "owner_invalid")
                owner.close()
                lock.__enter__.assert_not_called()
                upstream.assert_not_called()
            self.assertEqual(owner.remaining(), 10)

    def test_arbitrary_body_error_and_generator_close_revoke(self):
        with self.assertRaisesRegex(RuntimeError, "stop"):
            with self.open() as failed:
                raise RuntimeError("stop")
        self.assert_refused(failed.remaining, "closed")

        def operation():
            with self.open() as active:
                yield active

        steps = operation()
        active = next(steps)
        steps.close()
        self.assert_refused(active.remaining, "closed")

    def test_authority_callback_failure_or_expiry_revokes(self):
        checks = []

        def changed():
            checks.append(True)
            if len(checks) > 1:
                raise RuntimeError("authority changed")

        with self.open(require_current=changed) as owner:
            with self.assertRaisesRegex(RuntimeError, "authority changed"):
                owner.require_current()
            self.assert_refused(owner.remaining, "closed")

        def slow_check():
            self.monotonic += 11_000_000_000

        with self.assertRaises(run.NativeRootRunError) as caught:
            with self.open(require_current=slow_check):
                self.fail("expired admission yielded a live owner")
        self.assertEqual(caught.exception.code, "native_root_run.expired")

    def test_invalid_caps_and_clock_values_refuse_and_revoke(self):
        for value in (True, 0, -1, float("nan"), float("inf"), "10", 10**1000):
            with self.subTest(value_type=type(value).__name__), self.open() as owner:
                self.assert_refused(
                    lambda value=value: owner.clamp_timeout(value), "timeout_invalid"
                )
                self.assert_refused(owner.remaining, "closed")
        with self.open() as owner:
            self.monotonic = True
            self.assert_refused(owner.remaining, "clock_invalid")
            self.assert_refused(owner.remaining, "closed")

    def test_policy_mutation_refuses_and_independent_runs_have_distinct_nonces(self):
        with self.open() as first, self.open() as second:
            self.assertNotEqual(first.deadline.run_nonce, second.deadline.run_nonce)
            object.__setattr__(first.policy, "max_duration_seconds", 20)
            self.assert_refused(first.remaining, "policy_changed")
            self.assertEqual(second.remaining(), 10)

    def test_mutated_deadline_projection_cannot_rebind_the_original_owner(self):
        with self.open() as owner:
            object.__setattr__(
                owner.deadline, "expires_utc_ns", owner.deadline.expires_utc_ns + 1
            )
            self.assert_refused(owner.remaining, "deadline_changed")
            self.assert_refused(owner.remaining, "closed")

    def test_binding_mutation_revokes_even_if_the_original_data_is_restored(self):
        for index in range(3):
            with self.subTest(binding=index), self.open() as owner:
                binding = owner.bindings[index]
                original = binding.digest
                self.assertNotEqual(original, "f" * 64)
                try:
                    object.__setattr__(binding, "digest", "f" * 64)
                    self.assert_refused(owner.remaining, "binding_changed")
                    object.__setattr__(binding, "digest", original)
                    self.assert_refused(owner.remaining, "closed")
                finally:
                    object.__setattr__(binding, "digest", original)
