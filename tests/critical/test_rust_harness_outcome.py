"""Live executor lifetime controls with synthetic native-command observations.

The actual executor, input owners and filesystem pins run. Native commands are
controlled protocol fixtures: these tests claim no native/installed qualification.
"""

from __future__ import annotations

import copy
import json
import os
import pickle
import unittest
from contextlib import contextmanager
from dataclasses import fields
from unittest import mock

from literate_ai.adapters import rust_library_harness_execution as executor
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    open_native_root_run,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootRunBinding,
    NativeRootRunPolicy,
)
from tests.critical import test_rust_harness_guard_budget as fixtures


@unittest.skipUnless(os.name == "posix", "owned POSIX protocol fixtures")
class RustHarnessOutcomeTests(unittest.TestCase):
    setUp = fixtures.RustHarnessGuardBudgetTests.setUp
    observe = fixtures.RustHarnessGuardBudgetTests.observe
    metadata = fixtures.RustHarnessGuardBudgetTests.metadata
    library_current = fixtures.RustHarnessGuardBudgetTests.library_current

    def native_protocol(self, argv, **kwargs):
        completed = fixtures.RustHarnessGuardBudgetTests.native_protocol(
            self, argv, **kwargs
        )
        if argv[0] != self.cargo.command[0]:
            document = json.loads(completed.stdout)
            mode = getattr(self, "mode", "values")
            if mode == "values":
                document["cases"][0]["result"] = {"synthetic": "wrong value"}
            elif mode == "ids":
                document["cases"][0]["case_id"] = "foreign-case"
            elif mode == "capability":
                document["cases"][0]["capability"] = "foreign-capability"
            completed.stdout = json.dumps(document).encode()
        return completed

    def binding(self, run):
        # Closed synthetic context IDs do not grant real candidate/package rights.
        arguments = {
            field.name: canonical_identity({"synthetic": field.name})
            for field in fields(NativeRootRunBinding)
        }
        arguments.update(
            run_nonce=run.deadline.run_nonce,
            project_definition_identity=run.bindings[0],
            framework_distribution_identity=run.bindings[1],
            lifecycle_policy_identity=run.bindings[2],
            original_deadline_identity=run.deadline.identity,
            oracle_identity=self.fixture.oracle.identity,
            verifier_profile_identity=canonical_identity(
                self.fixture.oracle.rust_harness.to_dict()
            ),
            qualified_dependency_binding_identities=(),
            candidate_limit=3,
        )
        if getattr(self, "forged_profile", False):
            arguments["verifier_profile_identity"] = canonical_identity({"forged": 1})
        return NativeRootRunBinding(**arguments)

    def operate(self, action):
        captured = []

        @contextmanager
        def observe(oracle, **kwargs):
            with open_native_root_run(
                NativeRootRunPolicy(180, 3),
                project_identity=canonical_identity({"definition": 1}),
                framework_distribution_identity=canonical_identity({"framework": 1}),
                lifecycle_policy_identity=canonical_identity({"lifecycle": 1}),
                require_current=lambda: None,
                utc_clock=lambda: 1_000_000_000_000 + int(self.clock * 1_000_000_000),
                monotonic_clock=lambda: int(self.clock * 1_000_000_000),
            ) as run:
                binding, owner = self.binding(run), object()
                context = executor._observe_rust_library_harness_outcome(
                    oracle,
                    **kwargs,
                    original_run=run,
                    run_binding=binding,
                    continuation_owner=owner,
                    approved_project_authority_identity=binding.project_authority_identity,
                )
                with context as outcome:
                    captured.append((outcome, run, owner))
                    action(outcome, run, owner)
                    if getattr(self, "close_generator", False):
                        before = len(self.probes)
                        context.gen.close()
                        self.assertGreater(len(self.probes), before)
                        self.assert_code(
                            lambda: outcome.require_current(run, owner),
                            "outcome_closed",
                        )
                    yield outcome.result, outcome.observation

        with mock.patch.object(executor, "execute_rust_library_harness", observe):
            fixtures.RustHarnessGuardBudgetTests.operate(self)
        return captured[0]

    def assert_code(self, operation, suffix):
        with self.assertRaises(ComponentAcceptanceError) as caught:
            operation()
        self.assertEqual(
            caught.exception.code, "component_acceptance.rust_harness_" + suffix
        )

    def test_values_rejection_is_actual_original_result_once_then_expires(self):
        def consume(outcome, run, owner):
            self.assertTrue(outcome.values_differ)
            self.assertEqual(outcome.result.returncode, 0)
            self.assertIn("native_verifier_identity", outcome.observation)
            self.assertIs(outcome.consume_rejection(run, owner), outcome)
            self.assert_code(
                lambda: outcome.consume_rejection(run, owner), "outcome_consumed"
            )

        outcome, run, owner = self.operate(consume)
        self.assert_code(lambda: outcome.require_current(run, owner), "outcome_closed")

    def test_protocol_inventory_and_capability_refuse_before_any_live_yield(self):
        for mode in ("ids", "capability"):
            with self.subTest(mode=mode):
                # Each fixture has exclusive stage ownership, just as each run does.
                if self.stage.exists():
                    self.stage.rename(self.root / ("prior-stage-" + mode))
                self.stage.mkdir()
                self.commands.clear()
                self.mode = mode
                self.assert_code(
                    lambda: self.operate(
                        lambda *_: self.fail("invalid protocol yielded")
                    ),
                    "result_mismatch",
                )

    def test_matching_result_has_no_rejection_authority(self):
        self.mode = "matching"
        self.operate(
            lambda outcome, run, owner: self.assert_code(
                lambda: outcome.consume_rejection(run, owner), "outcome_consumed"
            )
        )

    def test_substituted_profile_refuses_before_native_execution(self):
        self.forged_profile = True
        self.assert_code(
            lambda: self.operate(lambda *_: self.fail("forged profile yielded")),
            "outcome_binding",
        )
        self.assertEqual(self.commands, [])

    def test_mutating_matching_decision_cannot_mint_rejection(self):
        self.mode = "matching"

        def mutate(outcome, run, owner):
            self.assertFalse(outcome.values_differ)
            outcome._values_differ = True
            self.assert_code(
                lambda: outcome.consume_rejection(run, owner), "outcome_changed"
            )
            self.assert_code(
                lambda: outcome.require_current(run, owner), "outcome_closed"
            )

        self.operate(mutate)

    def test_copied_serialized_and_wrong_owner_never_borrow_original(self):
        def inspect(outcome, run, owner):
            for operation in (
                lambda: copy.copy(outcome),
                lambda: copy.deepcopy(outcome),
                lambda: pickle.dumps(outcome),
                executor._LiveRustHarnessOutcome,
            ):
                with self.assertRaises(TypeError):
                    operation()
            self.assert_code(
                lambda: outcome.require_current(run, object()), "outcome_owner"
            )
            with mock.patch.object(
                executor.os, "getpid", return_value=outcome._pid + 1
            ):
                with mock.patch.object(outcome, "_lock") as lock:
                    lock.__enter__.side_effect = AssertionError("inherited lock used")
                    self.assert_code(
                        lambda: outcome.require_current(run, owner), "outcome_owner"
                    )
                    outcome.close()
                    lock.__enter__.assert_not_called()
            outcome.require_current(run, owner)

        self.operate(inspect)

    def test_observation_substitution_refuses_and_revokes(self):
        def mutate(outcome, run, owner):
            outcome.observation["native_verifier_identity"] = canonical_identity(
                {"forged": 1}
            ).uri
            self.assert_code(
                lambda: outcome.consume_rejection(run, owner), "outcome_changed"
            )
            self.assert_code(
                lambda: outcome.require_current(run, owner), "outcome_closed"
            )

        self.operate(mutate)

    def test_native_executable_mutation_refuses_before_consume_and_on_exit(self):
        def mutate(outcome, run, owner):
            executable = self.stage / "target/debug/litai-library-acceptance"
            executable.write_bytes(b"substituted native verifier")
            with self.assertRaises(ValueError):
                outcome.consume_rejection(run, owner)

        with self.assertRaises(ValueError):
            self.operate(mutate)

    def test_consumer_exception_revokes_the_original_outcome(self):
        escaped = []

        def refuse(outcome, run, owner):
            escaped.append((outcome, run, owner))
            raise RuntimeError("consumer failed")

        with self.assertRaisesRegex(RuntimeError, "consumer failed"):
            self.operate(refuse)
        outcome, run, owner = escaped[0]
        self.assert_code(lambda: outcome.require_current(run, owner), "outcome_closed")

    def test_generator_close_runs_native_guards_and_revokes(self):
        self.close_generator = True
        outcome, run, owner = self.operate(lambda *_: None)
        self.assert_code(lambda: outcome.require_current(run, owner), "outcome_closed")

    def test_raw_result_substitution_refuses_before_rejection_consume(self):
        def mutate(outcome, run, owner):
            outcome.result.stdout = b"substituted returned observation"
            self.assert_code(
                lambda: outcome.consume_rejection(run, owner), "outcome_changed"
            )

        self.operate(mutate)

    def test_expired_original_run_cannot_consume_or_extend_native_operation(self):
        escaped = []

        def expire(outcome, run, owner):
            escaped.append((outcome, run, owner))
            self.clock = 180
            with self.assertRaises(NativeRootRunError):
                outcome.consume_rejection(run, owner)
            self.assert_code(
                lambda: outcome.require_current(run, owner), "outcome_closed"
            )

        with self.assertRaises(NativeRootRunError):
            self.operate(expire)
        self.assertEqual(len(escaped), 1)

    def test_strict_public_wrapper_still_raises_original_mismatch_before_yield(self):
        self.assert_code(
            lambda: fixtures.RustHarnessGuardBudgetTests.operate(self),
            "result_mismatch",
        )


if __name__ == "__main__":
    unittest.main()
