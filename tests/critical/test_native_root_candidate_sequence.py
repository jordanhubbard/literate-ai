"""Original live budget constraints with symbolic candidate evidence.

These tests grant no native custody and do not execute generated code. Actual
repair eligibility and full lifecycle acceptance remain the runtime's duty.
"""

import copy
import pickle
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest import mock

from literate_ai.application.native_root_candidate_sequence import (
    LiveNativeRootCandidateSequence,
    open_native_root_candidate_sequence,
)
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    open_native_root_run,
)
from literate_ai.contracts.native_root_continuation import NativeRootContinuationStop
from tests.critical import test_native_root_continuation_contracts as fixtures

ci = fixtures.ci


class NativeRootCandidateSequenceTests(unittest.TestCase):
    def setUp(self):
        self.records = fixtures.NativeRootContinuationContractTests()
        self.records.setUp()
        self.monotonic = 1_000_000_000

    def original_run(self):
        record = self.records.run
        return open_native_root_run(
            self.records.policy,
            project_identity=record.project_definition_identity,
            framework_distribution_identity=record.framework_distribution_identity,
            lifecycle_policy_identity=record.lifecycle_policy_identity,
            require_current=lambda: None,
            utc_clock=lambda: 1_000_000_000_000,
            monotonic_clock=lambda: self.monotonic,
        )

    def sequence(self, owner, *, require_current=lambda: None, **changes):
        binding = replace(
            self.records.run,
            run_nonce=owner.deadline.run_nonce,
            original_deadline_identity=owner.deadline.identity,
            **changes,
        )
        return open_native_root_candidate_sequence(
            owner,
            binding,
            project_authority_identity=binding.project_authority_identity,
            require_current=require_current,
            qualified_dependencies=(self.records.dependency,),
        )

    def attempt(self, sequence, ordinal, **changes):
        # Reuse closed B/T -> package -> B/T records, preserving their distinct
        # causes while joining them to this actual original owner's one counter.
        original = (self.records.root0, self.records.root1, self.records.root2)[ordinal]
        return replace(
            original,
            run_binding_identity=sequence._binding.identity,
            predecessor_root_attempt_identities=tuple(
                a.identity for a in sequence.attempts
            ),
            legacy_node_chain_identity=None,
            legacy_node_attempt_index=None,
            incoming_request_kind="initial" if ordinal == 0 else "native-root-repair",
            incoming_request_identity=None
            if ordinal == 0
            else ci(f"root-request{ordinal}"),
            **changes,
        )

    def record(self, sequence, attempt):
        self.assertEqual(
            sequence.register_allocated_candidate(
                attempt.bounded_generation_request_identity,
                attempt.workspace_allocation_identity,
                incoming_request_kind=attempt.incoming_request_kind,
                incoming_request_identity=attempt.incoming_request_identity,
            ),
            attempt.ordinal,
        )
        sequence.record_attempt(attempt)

    def test_build_package_and_build_failures_exhaust_one_counter_without_fourth(self):
        with self.original_run() as owner, self.sequence(owner) as sequence:
            for index in range(3):
                self.record(sequence, self.attempt(sequence, index))
                self.assertEqual(sequence.consumed_candidates, index + 1)
            self.assertEqual(sequence.ledger().disposition, "exhausted")
            self.assertEqual(
                [a.outcome for a in sequence.ledger().attempts],
                ["node-rejected", "package-rejected", "node-rejected"],
            )
            with self.assertRaises(NativeRootRunError):
                sequence.require_allocation_available()

    def test_closing_or_failing_one_sequence_cannot_buy_a_new_counter(self):
        with self.original_run() as owner:
            with self.sequence(owner) as sequence:
                self.record(sequence, self.attempt(sequence, 0))
            with self.assertRaises(NativeRootRunError):
                with self.sequence(owner):
                    self.fail("renewed original root counter")
            owner.require_current()

    def test_allocated_candidate_is_counted_before_source_or_node_completion(self):
        with self.original_run() as owner, self.sequence(owner) as sequence:
            attempt = self.attempt(sequence, 0)
            sequence.register_allocated_candidate(
                attempt.bounded_generation_request_identity,
                attempt.workspace_allocation_identity,
                incoming_request_kind="initial",
                incoming_request_identity=None,
            )
            self.assertEqual(sequence.consumed_candidates, 1)
            with self.assertRaises(NativeRootRunError):
                sequence.ledger()
            with self.assertRaises(NativeRootRunError):
                sequence.require_allocation_available()
            terminal = replace(
                attempt,
                source_output_identity=None,
                node_lifecycle_result_identity=None,
                outcome="terminal-before-node",
                retryability="terminal",
            )
            sequence.record_attempt(terminal)
            self.assertEqual(sequence.ledger().disposition, "terminal")

    def test_failed_repair_preparation_records_stop_without_fictitious_candidate(self):
        with self.original_run() as owner, self.sequence(owner) as sequence:
            self.record(sequence, self.attempt(sequence, 0))
            stop = NativeRootContinuationStop(
                sequence._binding.identity,
                1,
                sequence.attempts[-1].identity,
                ci("allocation-failed"),
                "prepare-repair",
                "source.workspace-unavailable",
            )
            sequence.record_preparation_stop(stop)
            self.assertEqual(sequence.consumed_candidates, 1)
            self.assertEqual(sequence.ledger().terminal_stop_identity, stop.identity)
            self.assertEqual(sequence.ledger().disposition, "terminal")
            with self.assertRaises(NativeRootRunError):
                sequence.require_allocation_available()

    def test_expiry_closes_pending_counter_without_restoration_by_clock_reset(self):
        with self.original_run() as owner, self.sequence(owner) as sequence:
            self.record(sequence, self.attempt(sequence, 0))
            self.monotonic += 120_000_000_000
            with self.assertRaises(NativeRootRunError):
                sequence.require_allocation_available()
            self.monotonic = 1_000_000_000
            with self.assertRaises(NativeRootRunError):
                sequence.ledger()

    def test_copy_pickle_closed_projection_and_foreign_pid_cannot_restore_sequence(
        self,
    ):
        with self.original_run() as owner, self.sequence(owner) as sequence:
            for operation in (
                lambda: copy.copy(sequence),
                lambda: pickle.dumps(sequence),
                LiveNativeRootCandidateSequence,
            ):
                with self.assertRaises(TypeError):
                    operation()
            with mock.patch("os.getpid", return_value=sequence._pid + 1):
                with self.assertRaises(NativeRootRunError):
                    sequence.ledger()
            sequence.require_current()
        with self.assertRaises(NativeRootRunError):
            sequence.ledger()

    def test_concurrent_initial_allocations_cannot_overwrite_pending_candidate(self):
        synchronize = threading.Event()
        barrier = threading.Barrier(2)

        def current():
            if synchronize.is_set():
                barrier.wait(timeout=5)

        with (
            self.original_run() as owner,
            self.sequence(owner, require_current=current) as sequence,
        ):
            attempt = self.attempt(sequence, 0)
            synchronize.set()

            def allocate():
                try:
                    return sequence.register_allocated_candidate(
                        attempt.bounded_generation_request_identity,
                        attempt.workspace_allocation_identity,
                        incoming_request_kind="initial",
                        incoming_request_identity=None,
                    )
                except NativeRootRunError:
                    return "refused"

            with ThreadPoolExecutor(max_workers=2) as pool:
                left = pool.submit(allocate)
                right = pool.submit(allocate)
                outcomes = (left.result(timeout=10), right.result(timeout=10))
            synchronize.clear()
            self.assertCountEqual(outcomes, (0, "refused"))
            self.assertEqual(sequence.consumed_candidates, 1)

    def test_substituted_framework_policy_never_claims_original_root_counter(self):
        with self.original_run() as owner:
            with self.assertRaises(NativeRootRunError):
                with self.sequence(
                    owner, framework_distribution_identity=ci("foreign-framework")
                ):
                    self.fail("foreign binding admitted")
            with self.sequence(owner) as sequence:
                self.assertEqual(sequence.consumed_candidates, 0)
