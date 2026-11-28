"""Closed root-history/budget controls, not native or live-authority proof.

Symbolic content identities model retained records. Pure joins must reject mixed
histories even when their individual records are structurally valid and rehashed.
"""

from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from literate_ai.contracts._validation import ContractValidationError
from literate_ai.contracts.executable_components.candidate_repair import (
    CandidateAttempt,
    CandidateAttemptChain,
    CandidateAttemptChainDisposition,
    CandidateAttemptDisposition,
    CandidateFailureClassification,
    CandidateRepairDiagnostic,
    CandidateRepairRequest,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NATIVE_ROOT_REPAIR_MESSAGE,
    NATIVE_ROOT_RESULT_MISMATCH,
    NATIVE_ROOT_RUN_MAX_DURATION_SECONDS,
    NativeRootAcceptanceClosure,
    NativeRootAcceptanceRejection,
    NativeRootCandidateAttempt,
    NativeRootContinuationLedger,
    NativeRootContinuationStop,
    NativeRootExecutionResult,
    NativeRootPackageBinding,
    NativeRootQualifiedDependencyBinding,
    NativeRootRepairDiagnostic,
    NativeRootRepairRequest,
    NativeRootRunBinding,
    NativeRootRunDeadline,
    NativeRootRunPolicy,
)
from literate_ai.contracts.standard_lifecycle_membership import StandardNodeFailurePhase
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


def ci(label):
    return canonical_identity({"closed-protocol-fixture": label})


def package(label):
    return NativeRootPackageBinding(
        ci(label + "-graph"),
        ci(label + "-link"),
        ci(label + "-plan"),
        ci(label + "-result"),
        ci(label + "-root-tests"),
        ci(label + "-execution"),
    )


class NativeRootContinuationContractTests(unittest.TestCase):
    def setUp(self):
        self.policy = NativeRootRunPolicy(120, 3)
        self.deadline = NativeRootRunDeadline(
            "a" * 32, self.policy.identity, 100, 120_000_000_100
        )
        self.dependency = NativeRootQualifiedDependencyBinding(
            ci("dependency"),
            ci("dependency-acceptance"),
            ci("qualified-product"),
            ci("provenance"),
            (ci("dependency-export"),),
            ci("target"),
            (ci("dependency-tools"),),
            (),
        )
        self.expected_project = {
            "project_definition_identity": ci("original-project-definition"),
            "project_authority_identity": ci("approved-effective-project-revision"),
        }
        self.run = NativeRootRunBinding(
            "a" * 32,
            self.expected_project["project_definition_identity"],
            self.expected_project["project_authority_identity"],
            ci("root"),
            ci("lock"),
            ci("execution-plan"),
            ci("recipe"),
            ci("generation-plan"),
            ci("q0"),
            ci("framework"),
            ci("lifecycle-policy"),
            ci("target"),
            ci("verifier-profile"),
            ci("oracle"),
            self.deadline.identity,
            (self.dependency.identity,),
            3,
        )
        self.build_diagnostic = CandidateRepairDiagnostic(
            self.run.root_revision,
            StandardNodeFailurePhase.BUILD,
            "builder.generated-source-rejected",
            "generated build failed",
            CandidateFailureClassification.RETRYABLE,
            ci("failure0"),
        )
        self.legacy0 = CandidateAttempt(
            self.run.root_revision,
            0,
            ci("q0"),
            ci("source0"),
            ci("tree0"),
            ci("bundle0"),
            ci("w0"),
            ci("node0"),
            (),
            CandidateAttemptDisposition.RETRYABLE_REJECTED,
            self.build_diagnostic,
        )
        self.legacy_request1 = CandidateRepairRequest(
            self.run.root_revision,
            1,
            self.run.original_recipe_identity,
            (self.legacy0.identity,),
            self.build_diagnostic.identity,
            ci("q1"),
            ci("w1"),
        )
        self.legacy1 = CandidateAttempt(
            self.run.root_revision,
            1,
            ci("q1"),
            ci("source1"),
            ci("tree1"),
            ci("bundle1"),
            ci("w1"),
            ci("node1"),
            (self.legacy0.identity,),
            CandidateAttemptDisposition.ACCEPTED,
            None,
            self.legacy_request1,
        )
        self.legacy_chain = CandidateAttemptChain(
            self.run.root_revision,
            (self.legacy0, self.legacy1),
            CandidateAttemptChainDisposition.ACCEPTED,
        )
        self.rejection = NativeRootAcceptanceRejection(
            self.run.identity,
            1,
            self.run.root_revision,
            ci("q1"),
            ci("source1"),
            ci("tree1"),
            ci("w1"),
            ci("node1"),
            ci("build-plan1"),
            ci("build1"),
            ci("artifact1"),
            self.run.verifier_profile_identity,
            self.run.oracle_identity,
            ci("native-observation1"),
            ci("native-executable1"),
            (ci("native-tools"),),
            self.run.target_profile_identity,
            self.run.original_deadline_identity,
            "packaged-root",
            package("p1"),
            "result-values-differ",
            NATIVE_ROOT_RESULT_MISMATCH,
        )
        self.native_diagnostic = NativeRootRepairDiagnostic(
            self.run.root_revision,
            self.rejection.identity,
            NATIVE_ROOT_RESULT_MISMATCH,
            "retryable",
            NATIVE_ROOT_REPAIR_MESSAGE,
        )
        self.root0 = NativeRootCandidateAttempt(
            self.run.identity,
            0,
            (),
            "initial",
            None,
            ci("q0"),
            ci("w0"),
            ci("source0"),
            ci("node0"),
            self.legacy_chain.identity,
            0,
            "node-rejected",
            ci("failure0"),
            self.build_diagnostic.identity,
            "retryable",
            None,
            None,
        )
        self.root1 = NativeRootCandidateAttempt(
            self.run.identity,
            1,
            (self.root0.identity,),
            "legacy-node-repair",
            self.legacy_request1.identity,
            ci("q1"),
            ci("w1"),
            ci("source1"),
            ci("node1"),
            self.legacy_chain.identity,
            1,
            "package-rejected",
            self.rejection.identity,
            self.native_diagnostic.identity,
            "retryable",
            None,
            package("p1"),
        )
        self.request2 = NativeRootRepairRequest(
            self.run.identity,
            2,
            self.run.original_recipe_identity,
            (self.root0.identity, self.root1.identity),
            self.native_diagnostic.identity,
            self.rejection.identity,
            ci("q2"),
            ci("w2"),
            "native-acceptance",
            self.rejection.identity,
        )
        self.last_diagnostic = replace(
            self.build_diagnostic, failure_evidence_identity=ci("failure2")
        )
        self.root2 = NativeRootCandidateAttempt(
            self.run.identity,
            2,
            (self.root0.identity, self.root1.identity),
            "native-root-repair",
            self.request2.identity,
            ci("q2"),
            ci("w2"),
            ci("source2"),
            ci("node2"),
            None,
            None,
            "node-rejected",
            ci("failure2"),
            self.last_diagnostic.identity,
            "retryable",
            None,
            None,
        )
        self.prefix = (self.root0, self.root1)
        self.history = (self.legacy_chain.identity,)

    def ledger(self, attempts=None, disposition="pending", stop=None):
        return NativeRootContinuationLedger(
            self.run.identity,
            self.prefix if attempts is None else attempts,
            self.history,
            disposition,
            stop.identity if stop else None,
        )

    def stop(self, attempts=None, **changes):
        prefix = self.prefix if attempts is None else attempts
        return replace(
            NativeRootContinuationStop(
                self.run.identity,
                len(prefix),
                prefix[-1].identity if prefix else None,
                ci("prepare-failure"),
                "prepare-repair",
                "source.workspace-unavailable",
            ),
            **changes,
        )

    def test_policy_deadline_are_explicit_bounded_data_with_exact_policy_join(self):
        self.deadline.require_policy(self.policy)
        with self.assertRaises(ContractValidationError):
            self.deadline.require_policy(NativeRootRunPolicy(119, 3))
        shorter = replace(
            self.deadline, policy_identity=NativeRootRunPolicy(1, 3).identity
        )
        with self.assertRaises(ContractValidationError):
            shorter.require_policy(NativeRootRunPolicy(1, 3))
        for value in (0, 86401, True, 3600.0, "120"):
            with (
                self.subTest(duration=value),
                self.assertRaises(ContractValidationError),
            ):
                NativeRootRunPolicy(value, 3)
        for value in (2, 4, True):
            with self.subTest(limit=value), self.assertRaises(ContractValidationError):
                NativeRootRunPolicy(120, value)
        for changes in (
            {"expires_utc_ns": 100},
            {"expires_utc_ns": 86_400_000_000_101},
            {"started_utc_ns": True},
            {"run_nonce": "A" * 32},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(ContractValidationError),
            ):
                replace(self.deadline, **changes)

    def test_explicit_whole_run_policies_may_exceed_the_shipped_default(self):
        self.assertEqual(NATIVE_ROOT_RUN_MAX_DURATION_SECONDS, 86400)
        for seconds in (3600, 86400):
            with self.subTest(seconds=seconds):
                policy = NativeRootRunPolicy(seconds, 3)
                deadline = NativeRootRunDeadline(
                    "a" * 32, policy.identity, 100, 100 + seconds * 1_000_000_000
                )
                deadline.require_policy(policy)
                self.assertEqual(
                    NativeRootRunPolicy.from_dict(policy.to_dict()), policy
                )
                self.assertEqual(
                    NativeRootRunDeadline.from_dict(deadline.to_dict()), deadline
                )
                with self.assertRaises(ContractValidationError):
                    deadline.require_policy(NativeRootRunPolicy(seconds - 1, 3))
                if seconds < 86400:
                    over_selected = replace(
                        deadline, expires_utc_ns=deadline.expires_utc_ns + 1
                    )
                    with self.assertRaises(ContractValidationError):
                        over_selected.require_policy(policy)
                else:
                    with self.assertRaises(ContractValidationError):
                        replace(deadline, expires_utc_ns=deadline.expires_utc_ns + 1)

    def test_held_dependency_and_deadline_swaps_refuse_data_context_join(self):
        self.run.require_records(
            self.policy, self.deadline, (self.dependency,), **self.expected_project
        )
        for deadline, dependencies in (
            (replace(self.deadline, run_nonce="b" * 32), (self.dependency,)),
            (
                self.deadline,
                (replace(self.dependency, target_profile_identity=ci("other-target")),),
            ),
            (
                self.deadline,
                (replace(self.dependency, component_revision=self.run.root_revision),),
            ),
            (self.deadline, (self.dependency, self.dependency)),
            (self.deadline, ()),
        ):
            with (
                self.subTest(dependencies=dependencies),
                self.assertRaises(ContractValidationError),
            ):
                self.run.require_records(
                    self.policy, deadline, dependencies, **self.expected_project
                )

    def test_self_rehashed_cross_project_binding_refuses_original_authority(self):
        self.run.require_records(
            self.policy, self.deadline, (self.dependency,), **self.expected_project
        )
        for field in self.expected_project:
            changed = replace(self.run, **{field: ci("other-project-" + field)})
            self.assertNotEqual(changed.identity, self.run.identity)
            retained = NativeRootRunBinding.from_dict(changed.to_dict())
            with self.subTest(field=field), self.assertRaises(ContractValidationError):
                retained.require_records(
                    self.policy,
                    self.deadline,
                    (self.dependency,),
                    **self.expected_project,
                )
        with self.assertRaises(TypeError):
            self.run.require_records(self.policy, self.deadline, (self.dependency,))

    def test_prior_build_and_accepted_node_history_survive_global_exhaustion(self):
        original = self.legacy_chain.to_dict()
        self.request2.require_records(
            self.run, self.prefix, self.native_diagnostic, rejection=self.rejection
        )
        exhausted = self.ledger(self.prefix + (self.root2,), "exhausted")
        exhausted.require_records(self.run, historical_chains=(self.legacy_chain,))
        self.assertEqual(exhausted.consumed_candidates, 3)
        self.assertIsNone(exhausted.attempts[-1].legacy_node_chain_identity)
        self.assertEqual(self.legacy_chain.to_dict(), original)
        self.assertIs(
            self.legacy_chain.attempts[-1].disposition,
            CandidateAttemptDisposition.ACCEPTED,
        )
        with self.assertRaises(ContractValidationError):
            replace(
                self.legacy_chain,
                disposition=CandidateAttemptChainDisposition.EXHAUSTED,
            )
        with self.assertRaises(ContractValidationError):
            replace(exhausted, disposition="pending")
        with self.assertRaises(ContractValidationError):
            replace(exhausted, attempts=exhausted.attempts + (self.root2,))

    def test_legacy_history_cannot_hide_duplicate_or_rewrite_node_observations(self):
        ledger = self.ledger()
        ledger.require_records(self.run, historical_chains=(self.legacy_chain,))
        for changes in (
            {"node_lifecycle_result_identity": ci("foreign-node")},
            {"legacy_node_attempt_index": 0},
            {"bounded_generation_request_identity": ci("foreign-request")},
            {"incoming_request_identity": ci("foreign-legacy-request")},
        ):
            root1 = replace(self.root1, **changes)
            altered = self.ledger((self.root0, root1))
            with (
                self.subTest(changes=changes),
                self.assertRaises(ContractValidationError),
            ):
                altered.require_records(
                    self.run, historical_chains=(self.legacy_chain,)
                )
        with self.assertRaises(ContractValidationError):
            ledger.require_records(self.run, historical_chains=())
        with self.assertRaises(ContractValidationError):
            ledger.require_records(
                self.run, historical_chains=(self.legacy_chain, self.legacy_chain)
            )

    def test_self_rehashed_root_requests_cannot_substitute_candidate_or_native_failure(
        self,
    ):
        for changes in (
            {"original_recipe_identity": ci("other-recipe")},
            {
                "acceptance_rejection_identity": ci("other-rejection"),
                "failure_evidence_identity": ci("other-rejection"),
            },
            {"bounded_generation_request_identity": ci("q1")},
            {"workspace_allocation_identity": ci("w0")},
            {"run_binding_identity": ci("other-run")},
        ):
            value = replace(self.request2, **changes)
            parsed = NativeRootRepairRequest.from_dict(value.to_dict())
            with (
                self.subTest(changes=changes),
                self.assertRaises(ContractValidationError),
            ):
                parsed.require_records(
                    self.run,
                    self.prefix,
                    self.native_diagnostic,
                    rejection=self.rejection,
                )
        with self.assertRaises(ContractValidationError):
            self.request2.require_records(
                self.run,
                self.prefix[::-1],
                self.native_diagnostic,
                rejection=self.rejection,
            )
        with self.assertRaises(ContractValidationError):
            self.request2.require_records(
                self.run,
                self.prefix,
                self.native_diagnostic,
                rejection=replace(
                    self.rejection, source_output_identity=ci("other-source")
                ),
            )

    def test_self_rehashed_initial_request_cannot_replace_original(self):
        changed_run = replace(
            self.run, original_bounded_request_identity=ci("other-q0")
        )
        attempts = []
        for old in self.prefix:
            attempts.append(
                replace(
                    old,
                    run_binding_identity=changed_run.identity,
                    predecessor_root_attempt_identities=tuple(
                        a.identity for a in attempts
                    ),
                )
            )
        altered = NativeRootContinuationLedger(
            changed_run.identity,
            tuple(attempts),
            (self.legacy_chain.identity,),
            "pending",
            None,
        )
        with self.assertRaises(ContractValidationError):
            altered.require_records(changed_run, historical_chains=(self.legacy_chain,))
        request = replace(
            self.request2,
            run_binding_identity=changed_run.identity,
            predecessor_root_attempt_identities=tuple(a.identity for a in attempts),
        )
        with self.assertRaises(ContractValidationError):
            request.require_records(
                changed_run,
                tuple(attempts),
                self.native_diagnostic,
                rejection=self.rejection,
            )
        with self.assertRaises(ContractValidationError):
            self.ledger(
                (
                    self.root0,
                    replace(
                        self.root1,
                        workspace_allocation_identity=self.root0.workspace_allocation_identity,
                    ),
                )
            )

    def test_build_failure_after_root_repair_keeps_old_build_diagnostic(
        self,
    ):
        first = replace(
            self.root1,
            ordinal=0,
            predecessor_root_attempt_identities=(),
            incoming_request_kind="initial",
            incoming_request_identity=None,
            bounded_generation_request_identity=self.run.original_bounded_request_identity,
            legacy_node_chain_identity=None,
            legacy_node_attempt_index=None,
        )
        middle = replace(
            self.root2,
            ordinal=1,
            predecessor_root_attempt_identities=(first.identity,),
            incoming_request_identity=ci("incoming-root-request"),
        )
        request = NativeRootRepairRequest(
            self.run.identity,
            2,
            self.run.original_recipe_identity,
            (first.identity, middle.identity),
            self.last_diagnostic.identity,
            None,
            ci("q3"),
            ci("w3"),
            "node-build-test",
            ci("failure2"),
        )
        request.require_records(self.run, (first, middle), self.last_diagnostic)
        with self.assertRaises(ContractValidationError):
            request.require_records(
                self.run,
                (first, middle),
                replace(
                    self.last_diagnostic,
                    phase=StandardNodeFailurePhase.ACCEPT,
                    code=NATIVE_ROOT_RESULT_MISMATCH,
                ),
            )
        with self.assertRaises(ContractValidationError):
            CandidateRepairRequest.from_dict(request.to_dict())
        with self.assertRaises(ContractValidationError):
            NativeRootRepairRequest.from_dict(self.legacy_request1.to_dict())

    def test_post_node_root_terminal_preserves_accepted_history_and_partial_stage(self):
        historical = self.legacy_chain.to_dict()
        root = Path(__file__).resolve().parents[2]
        registry = Registry()
        for relative in (
            "schemas/v1/identity.schema.json",
            "schemas/v2/native-root-continuation.schema.json",
        ):
            document = json.loads((root / relative).read_text())
            registry = registry.with_resource(
                document["$id"], Resource.from_contents(document)
            )
        registry = registry.crawl()
        validator = Draft202012Validator(
            registry.resolver().lookup(NativeRootCandidateAttempt.SCHEMA).contents,
            registry=registry,
        )
        for full_package in (None, package("p1")):
            with self.subTest(full_package=full_package is not None):
                terminal = replace(
                    self.root1,
                    outcome="root-terminal",
                    failure_evidence_identity=ci("actual-root-stage-failure"),
                    diagnostic_identity=None,
                    retryability="terminal",
                    final_packaged_binding=full_package,
                )
                self.assertEqual(
                    NativeRootCandidateAttempt.from_dict(terminal.to_dict()), terminal
                )
                wire = terminal.to_dict()
                validator.validate(wire)
                for changes in (
                    {"retryability": "retryable"},
                    {"source_output_identity": None},
                    {"node_lifecycle_result_identity": None},
                    {"failure_evidence_identity": None},
                    {
                        "actual_packaged_acceptance_identity": ci(
                            "false-acceptance"
                        ).to_dict()
                    },
                    {
                        "final_packaged_binding": {
                            "artifact_graph_identity": ci("partial").to_dict()
                        }
                    },
                ):
                    with self.assertRaises(ValidationError):
                        validator.validate({**wire, **changes})
                ledger = self.ledger((self.root0, terminal), "terminal")
                ledger.require_records(self.run, historical_chains=(self.legacy_chain,))
                self.assertEqual(ledger.consumed_candidates, 2)
                self.assertEqual(self.legacy_chain.to_dict(), historical)
                self.assertEqual(
                    terminal.source_output_identity, self.root1.source_output_identity
                )
                self.assertEqual(
                    terminal.node_lifecycle_result_identity,
                    self.root1.node_lifecycle_result_identity,
                )
                self.assertEqual(terminal.final_packaged_binding, full_package)
                for changes in (
                    {
                        "retryability": "retryable",
                        "diagnostic_identity": self.native_diagnostic.identity,
                    },
                    {"retryability": "none"},
                    {"failure_evidence_identity": None},
                    {"source_output_identity": None},
                    {"node_lifecycle_result_identity": None},
                    {"actual_packaged_acceptance_identity": ci("false-acceptance")},
                ):
                    with self.assertRaises(ContractValidationError):
                        replace(terminal, **changes)
                altered = replace(
                    terminal, node_lifecycle_result_identity=ci("fake-node")
                )
                with self.assertRaises(ContractValidationError):
                    self.ledger((self.root0, altered), "terminal").require_records(
                        self.run, historical_chains=(self.legacy_chain,)
                    )
                with self.assertRaises(ContractValidationError):
                    NativeRootAcceptanceClosure(
                        self.run.identity,
                        ledger.identity,
                        ci("false-acceptance"),
                        terminal.source_output_identity,
                        ci("absent-plan"),
                        ci("absent-result"),
                    ).require_records(self.run, ledger)
                with self.assertRaises(ContractValidationError):
                    replace(ledger, disposition="accepted")

    def test_stop_before_allocation_terminalizes_without_inventing_candidate(self):
        original = tuple(attempt.to_dict() for attempt in self.prefix)
        stop = self.stop()
        ledger = self.ledger(disposition="terminal", stop=stop)
        ledger.require_records(
            self.run, historical_chains=(self.legacy_chain,), terminal_stop=stop
        )
        self.assertEqual(ledger.consumed_candidates, 2)
        self.assertEqual(tuple(a.to_dict() for a in ledger.attempts), original)
        for changes in (
            {"before_candidate_ordinal": 3},
            {"last_attempt_identity": self.root0.identity},
            {"run_binding_identity": ci("foreign-run")},
        ):
            changed = replace(stop, **changes)
            rehashed = replace(ledger, terminal_stop_identity=changed.identity)
            with (
                self.subTest(changes=changes),
                self.assertRaises(ContractValidationError),
            ):
                rehashed.require_records(
                    self.run,
                    historical_chains=(self.legacy_chain,),
                    terminal_stop=changed,
                )
        with self.assertRaises(ContractValidationError):
            ledger.require_records(self.run, historical_chains=(self.legacy_chain,))
        for disposition in ("pending", "accepted", "exhausted"):
            with (
                self.subTest(disposition=disposition),
                self.assertRaises(ContractValidationError),
            ):
                replace(ledger, disposition=disposition)

    def test_stop_before_first_or_after_third_keeps_exact_reserved_count(self):
        empty_stop = self.stop(())
        empty = NativeRootContinuationLedger(
            self.run.identity, (), (), "terminal", empty_stop.identity
        )
        empty.require_records(self.run, terminal_stop=empty_stop)
        self.assertEqual(empty.consumed_candidates, 0)
        with self.assertRaises(ContractValidationError):
            replace(empty_stop, last_attempt_identity=ci("manufactured-candidate"))
        all_attempts = self.prefix + (self.root2,)
        stop = self.stop(all_attempts, stage="custody-close", code="authority.changed")
        terminal = self.ledger(all_attempts, "terminal", stop)
        terminal.require_records(
            self.run, historical_chains=(self.legacy_chain,), terminal_stop=stop
        )
        self.assertEqual(terminal.consumed_candidates, 3)
        with self.assertRaises(ContractValidationError):
            replace(terminal, terminal_stop_identity=None)

    def test_accepted_last_candidate_and_terminal_failure_have_distinct_budget_states(
        self,
    ):
        accepted = replace(
            self.root2,
            outcome="root-accepted",
            failure_evidence_identity=None,
            diagnostic_identity=None,
            retryability="none",
            actual_packaged_acceptance_identity=ci("actual-acceptance2"),
            final_packaged_binding=package("p2"),
        )
        ledger = self.ledger(self.prefix + (accepted,), "accepted")
        closure = NativeRootAcceptanceClosure(
            self.run.identity,
            ledger.identity,
            ci("actual-acceptance2"),
            ci("source2"),
            package("p2").package_plan_identity,
            package("p2").package_result_identity,
        )
        closure.require_records(self.run, ledger)
        result = NativeRootExecutionResult(
            self.run.identity,
            ledger.identity,
            ci("legacy-lifecycle"),
            closure.identity,
            "accepted",
        )
        result.require_records(self.run, ledger, closure=closure)
        with self.assertRaises(ContractValidationError):
            replace(
                closure, package_result_identity=ci("foreign-package")
            ).require_records(self.run, ledger)
        with self.assertRaises(ContractValidationError):
            replace(result, ledger_identity=ci("foreign-ledger")).require_records(
                self.run, ledger, closure=closure
            )
        with self.assertRaises(ContractValidationError):
            replace(result, status="exhausted")
        terminal = replace(
            self.root2, retryability="terminal", diagnostic_identity=None
        )
        self.ledger(self.prefix + (terminal,), "terminal")
        with self.assertRaises(ContractValidationError):
            self.ledger(self.prefix + (terminal,), "exhausted")

    def test_complete_record_family_roundtrips_and_current_catalog_registers_exact_ids(
        self,
    ):
        stop = self.stop()
        ledger = self.ledger(disposition="terminal", stop=stop)
        closure = NativeRootAcceptanceClosure(
            self.run.identity,
            ci("accepted-ledger"),
            ci("actual-native"),
            ci("source2"),
            ci("package-plan"),
            ci("package-result"),
        )
        result = NativeRootExecutionResult(
            self.run.identity, ledger.identity, ci("failed-lifecycle"), None, "terminal"
        )
        records = (
            self.policy,
            self.deadline,
            self.dependency,
            self.run,
            self.rejection,
            self.native_diagnostic,
            self.request2,
            self.root1,
            stop,
            ledger,
            closure,
            result,
        )
        catalog = SchemaCatalog()
        root = Path(__file__).resolve().parents[2]
        index = json.loads((root / "schemas/v2/index.json").read_text())
        entry = next(
            x
            for x in index["schemas"]
            if x["file"] == "native-root-continuation.schema.json"
        )
        self.assertEqual(set(entry["public_ids"]), {v.SCHEMA for v in records})
        documents = (
            json.loads((root / "schemas/v1/identity.schema.json").read_text()),
            json.loads(
                (root / "schemas/v2/native-root-continuation.schema.json").read_text()
            ),
        )
        registry = Registry()
        for document in documents:
            Draft202012Validator.check_schema(document)
            registry = registry.with_resource(
                document["$id"], Resource.from_contents(document)
            )
        registry = registry.crawl()
        container = Draft202012Validator(documents[1], registry=registry)
        for value in records:
            with self.subTest(schema=value.SCHEMA):
                wire = value.to_dict()
                self.assertEqual(type(value).from_dict(wire), value)
                catalog.validate(value.SCHEMA, wire)
                resolved = registry.resolver().lookup(value.SCHEMA).contents
                validator = Draft202012Validator(resolved, registry=registry)
                validator.validate(wire)
                container.validate(wire)
                for key, payload in (
                    ("unknown", True),
                    ("schema", "urn:literate-ai:schema:v2:candidate-attempt-chain"),
                ):
                    altered = {**wire, key: payload}
                    with self.assertRaises(ContractValidationError):
                        type(value).from_dict(altered)
                    with self.assertRaises(AssertionError):
                        catalog.validate(value.SCHEMA, altered)
                    with self.assertRaises(ValidationError):
                        validator.validate(altered)
                    with self.assertRaises(ValidationError):
                        container.validate(altered)

    def test_nested_bool_integer_duplicates_and_reordered_prefix_refuse(self):
        for changes in (
            {"ordinal": True},
            {
                "predecessor_root_attempt_identities": (
                    self.root0.identity,
                    self.root0.identity,
                )
            },
            {"legacy_node_attempt_index": True},
            {"outcome": "root-accepted"},
            {"incoming_request_kind": "initial"},
            {"final_packaged_binding": None},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(ContractValidationError),
            ):
                replace(self.root1, **changes)
        wire = self.ledger().to_dict()
        altered = copy.deepcopy(wire)
        altered["attempts"][1]["ordinal"] = True
        with self.assertRaises(ContractValidationError):
            NativeRootContinuationLedger.from_dict(altered)
        with self.assertRaises(ContractValidationError):
            self.ledger(self.prefix[::-1])
        with self.assertRaises(ContractValidationError):
            replace(
                self.rejection, tool_observation_identities=(ci("tool"), ci("tool"))
            )
        with self.assertRaises(ContractValidationError):
            replace(self.native_diagnostic, sanitized_text="private oracle says 41")
