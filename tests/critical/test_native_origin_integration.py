"""Controller-origin lifetime and refusal tests using synthetic typed stages.

No generated native program, installed wheel, external provider or worker runs.
The actual lifecycle controller owns these source-only observations.
"""

from __future__ import annotations

import unittest
from unittest import mock

from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from literate_ai.application import standard_project_lifecycle as lifecycle
from literate_ai.contracts.capabilities import DependencyKind
from literate_ai.contracts.executable_components import (
    CandidateAttemptChainDisposition,
    CandidateFailureClassification,
    CandidateRepairDiagnostic,
)
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailureEvidence,
    StandardNodeFailurePhase,
)
from tests.support import fixtures_test_standard_project_lifecycle as fixtures

_MISMATCH = "component_acceptance.rust_harness_result_mismatch"


def _rejection(plan):
    return StandardNodeFailureEvidence(
        plan.component_revision,
        StandardNodeFailurePhase.ACCEPT,
        _MISMATCH,
        plan.identity,
        "synthetic same-code rejection for controller-origin testing",
    )


class _RepairProbe:
    """Accepts the public code deliberately: controller must enforce origin."""

    def __init__(self, *, diagnostic_class=CandidateFailureClassification.RETRYABLE):
        self.diagnostic_class = diagnostic_class
        self.diagnosed = []
        self.preparations = []

    def diagnose(self, failure, output):
        self.diagnosed.append((failure, output))
        return CandidateRepairDiagnostic(
            failure.component_revision,
            failure.phase,
            failure.code,
            "synthetic repair probe does not establish native qualification",
            self.diagnostic_class,
            failure.identity,
        )

    def prepare_repair(self, original, diagnostic, predecessor_attempt_identities):
        self.preparations.append((original, diagnostic, predecessor_attempt_identities))
        raise AssertionError("untrusted acceptance error reached repair preparation")


class NativeOriginIntegrationControls(unittest.TestCase):
    """Actual controller flow; all source/stage observations are synthetic."""

    def setUp(self):
        self.lock = fixtures._diamond_lock(dependency_kind=DependencyKind.GENERATION)
        self.execution, self.requests = fixtures._prepared_execution(self.lock)
        self.nodes = fixtures._prepared_nodes(self.execution, self.requests)
        self.names = fixtures._names(self.lock)
        self.money_uri = next(
            uri for uri, name in self.names.items() if name == "money"
        )

    def _configured(self, repair):
        ports = fixtures.ContractEvidenceLifecyclePorts(self.execution, self.names)
        service = fixtures._service(ports, candidate_repair_port=repair)
        return ports, service

    def _execute(self, service):
        return service.execute(
            self.execution,
            component_lock=self.lock,
            invalidation=fixtures._decision(
                self.execution, self.names, "money", tuple(self.names.values())
            ),
            prepared_nodes=self.nodes,
            max_parallelism=1,
        )

    def test_closing_actual_outer_generator_revokes_escaped_sink(self):
        repair = _RepairProbe()
        ports, service = self._configured(repair)
        original_once = service._run_complete_node_once_steps
        captured = []
        inner_finalized = []

        def observe_once(*args, **kwargs):
            # Wrap rather than replace the actual once-steps generator. The first
            # yielded production lifecycle step suspends its real continuation.
            captured.append(kwargs["_native_rejection_sink"])
            try:
                return (yield from original_once(*args, **kwargs))
            finally:
                inner_finalized.append(True)

        prepared = self.nodes[self.money_uri]
        steps = service._run_complete_node_steps(
            self.execution,
            prepared.plan,
            prepared,
            None,
            None,
            None,
            (),
            (),
            True,
        )
        with mock.patch.object(service, "_run_complete_node_once_steps", observe_once):
            try:
                first_step = next(steps)
                self.assertIsInstance(first_step, lifecycle._LifecycleStep)
                self.assertEqual(len(captured), 1)
            finally:
                steps.close()
        self.assertEqual(inner_finalized, [True])
        with self.assertRaises(lifecycle.StandardProjectLifecycleError) as refused:
            captured[0](object(), object())
        self.assertEqual(
            refused.exception.code,
            "standard_lifecycle.candidate_rejection_origin_invalid",
        )
        self.assertEqual(repair.diagnosed, [])
        self.assertEqual(repair.preparations, [])
        self.assertEqual(ports.issued_receipts, [])

    def _untrusted_rejection_stays_terminal(self, *, origin, private_marker):
        repair = _RepairProbe()
        ports, service = self._configured(repair)
        verifier_calls = []
        forged = []

        def refuse(plan):
            if private_marker:
                failure = _rejection(plan)
                forged.append(failure)
                raise lifecycle._GeneratedCandidateRejected(failure)
            raise ComponentAcceptanceError(
                _MISMATCH, "synthetic generic acceptance error"
            )

        if origin == "acceptor":
            original_accept = ports.accept

            def accept(plan, test, execution):
                if plan.component_revision.uri == self.money_uri:
                    ports._record("accept", "money")
                    refuse(plan)
                return original_accept(plan, test, execution)

            ports.accept = accept
        else:

            class Verifier:
                def verify(_self, plan, output, accepted):
                    verifier_calls.append(plan.component_revision.uri)
                    if plan.component_revision.uri == self.money_uri:
                        refuse(plan)
                    return None

            service.generated_candidate_verifier = Verifier()

        result = self._execute(service)
        money = next(
            node
            for node in result.node_results
            if node.component_revision.uri == self.money_uri
        )
        chain = next(
            item
            for item in result.candidate_attempt_chains
            if item.component_revision.uri == self.money_uri
        )
        self.assertFalse(result.successful)
        self.assertIs(money.failure_evidence.phase, StandardNodeFailurePhase.ACCEPT)
        self.assertEqual(money.failure_evidence.code, _MISMATCH)
        if private_marker:
            self.assertIs(money.failure_evidence, forged[0])
        if origin == "verifier":
            self.assertEqual(verifier_calls.count(self.money_uri), 1)
        self.assertIs(chain.disposition, CandidateAttemptChainDisposition.TERMINAL)
        self.assertEqual(len(chain.attempts), 1)
        self.assertEqual(ports.events.count(("generate", "money")), 1)
        self.assertEqual(repair.diagnosed, [])
        self.assertEqual(repair.preparations, [])
        self.assertNotIn(("publish", "money"), ports.events)
        self.assertEqual(ports.issued_receipts, [])

    def test_generic_acceptor_mismatch_stays_terminal(self):
        self._untrusted_rejection_stays_terminal(
            origin="acceptor", private_marker=False
        )

    def test_private_marker_from_acceptor_stays_terminal(self):
        self._untrusted_rejection_stays_terminal(origin="acceptor", private_marker=True)

    def test_generic_verifier_mismatch_stays_terminal(self):
        self._untrusted_rejection_stays_terminal(
            origin="verifier", private_marker=False
        )

    def test_private_marker_from_verifier_stays_terminal(self):
        self._untrusted_rejection_stays_terminal(origin="verifier", private_marker=True)

    def test_actual_verifier_return_reaches_diagnosis_through_all_controller_layers(
        self,
    ):
        # Positive wiring control: a returned object passes the real inner and
        # outer layers. A terminal probe avoids any source replacement and does
        # not imply that this synthetic verifier is native repair authority.
        repair = _RepairProbe(diagnostic_class=CandidateFailureClassification.TERMINAL)
        ports, service = self._configured(repair)
        returned = []

        class Verifier:
            def verify(_self, plan, output, accepted):
                if plan.component_revision.uri == self.money_uri:
                    failure = _rejection(plan)
                    returned.append((failure, output))
                    return failure
                return None

        service.generated_candidate_verifier = Verifier()
        result = self._execute(service)
        self.assertFalse(result.successful)
        self.assertEqual(len(returned), 1)
        self.assertEqual(len(repair.diagnosed), 1)
        self.assertIs(repair.diagnosed[0][0], returned[0][0])
        self.assertIs(repair.diagnosed[0][1], returned[0][1])
        self.assertEqual(repair.preparations, [])
        self.assertEqual(ports.events.count(("generate", "money")), 1)
        self.assertEqual(ports.issued_receipts, [])


if __name__ == "__main__":
    unittest.main()
