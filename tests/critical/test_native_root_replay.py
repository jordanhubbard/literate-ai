"""Closed binding controls with modeled lifecycle records, not native acceptance.

No installed/native qualification, historical source reopening or mismatch
decision is established by this fixture or by the helper under test.
"""

import unittest
from dataclasses import fields, replace

from literate_ai.adapters.native_root_replay import (
    NativeRootReplayAuthority,
    NativeRootReplayError,
    NativeRootReplayLimits,
    NativeRootReplaySubject,
    verify_closed_native_root_bindings,
)
from literate_ai.contracts.executable_components.candidate_repair import (
    CandidateAttemptChain,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceClosure,
    NativeRootContinuationLedger,
    NativeRootExecutionResult,
    NativeRootPackageBinding,
    NativeRootRepairRequest,
)
from tests.critical import test_native_root_continuation_contracts as contracts
from tests.support import fixtures_test_standard_project_lifecycle as fixture


class NativeRootReplayTests(unittest.TestCase):
    def setUp(self):
        self.records = {}
        self.contract = contracts.NativeRootContinuationContractTests()
        self.contract.setUp()
        model = fixture.StandardProjectLifecycleTests()
        model.setUp()
        ports = fixture.LifecyclePorts(model.execution, model.names)
        self.lifecycle = fixture._service(ports).execute(
            model.execution,
            component_lock=model.lock,
            invalidation=fixture._decision(
                model.execution, model.names, "money", tuple(model.names.values())
            ),
            prepared_nodes=model.nodes,
            max_parallelism=1,
        )
        self.assertTrue(self.lifecycle.successful)
        self.root = self.lifecycle.root_integration
        self.node = next(
            node
            for node in self.lifecycle.node_results
            if node.component_revision == model.lock.root_revision
        )
        self.package = NativeRootPackageBinding(
            self.root.artifact_graph.identity,
            self.root.link_plan.identity,
            self.root.package_plan.identity,
            self.root.package_result.identity,
            self.root.root_generated_integration_test_identity,
            self.root.packaged_execution_identity,
        )
        self.dependency = replace(
            self.contract.dependency,
            target_profile_identity=self.root.package_plan.target_identity,
        )
        self.run = replace(
            self.contract.run,
            root_revision=model.lock.root_revision,
            component_lock_identity=model.lock.identity,
            execution_plan_identity=self.lifecycle.execution_plan_identity,
            target_profile_identity=self.root.package_plan.target_identity,
            qualified_dependency_binding_identities=(self.dependency.identity,),
        )
        self.authority = NativeRootReplayAuthority(
            **{
                field.name: getattr(self.run, field.name)
                for field in fields(NativeRootReplayAuthority)
            }
        )
        self.accepted = replace(
            self.contract.root0,
            run_binding_identity=self.run.identity,
            source_output_identity=self.node.source_output.identity,
            node_lifecycle_result_identity=self.node.identity,
            legacy_node_chain_identity=None,
            legacy_node_attempt_index=None,
            outcome="root-accepted",
            failure_evidence_identity=None,
            diagnostic_identity=None,
            retryability="none",
            actual_packaged_acceptance_identity=contracts.ci(
                "actual-final-native-acceptance"
            ),
            final_packaged_binding=self.package,
        )
        for record in (
            self.contract.policy,
            self.contract.deadline,
            self.dependency,
            self.run,
        ):
            self.put(record)
        self.put(self.node.source_output)
        self.put_json(self.node.identity_document())
        self.install((self.accepted,))

    def put_json(self, value):
        identity = canonical_identity(value)
        self.records[identity] = canonical_json_bytes(value)
        return identity

    def put(self, record):
        return self.put_json(record.to_dict())

    def install(self, attempts):
        history = tuple(
            sorted(
                {
                    attempt.legacy_node_chain_identity
                    for attempt in attempts
                    if attempt.legacy_node_chain_identity is not None
                },
                key=lambda identity: identity.uri,
            )
        )
        self.ledger = NativeRootContinuationLedger(
            self.run.identity, attempts, history, "accepted", None
        )
        final = attempts[-1]
        self.closure = NativeRootAcceptanceClosure(
            self.run.identity,
            self.ledger.identity,
            final.actual_packaged_acceptance_identity,
            final.source_output_identity,
            final.final_packaged_binding.package_plan_identity,
            final.final_packaged_binding.package_result_identity,
        )
        root = replace(self.root, independent_acceptance_identity=self.closure.identity)
        self.put(root)
        lifecycle = self.lifecycle.identity_document()
        lifecycle["root_integration_evidence_identity"] = root.identity.uri
        lifecycle_identity = self.put_json(lifecycle)
        self.subject = NativeRootReplaySubject(
            lifecycle_identity,
            root,
            self.node.identity,
            self.node.source_output.identity,
        )
        self.audit = NativeRootExecutionResult(
            self.run.identity,
            self.ledger.identity,
            lifecycle_identity,
            self.closure.identity,
            "accepted",
        )
        for record in (*attempts, self.ledger, self.closure, self.audit):
            self.put(record)

    def verify(self, **changes):
        kwargs = dict(
            read_record=self.records.__getitem__,
            selected_policy=self.contract.policy,
            authority=self.authority,
            subject=self.subject,
            qualified_dependencies=(self.dependency,),
        )
        kwargs.update(changes)
        return verify_closed_native_root_bindings(**kwargs)

    def test_required_closure_and_computed_audit_join_without_changing_lifecycle_wire(
        self,
    ):
        self.assertNotIn("native_root_execution", self.lifecycle.identity_document())
        self.assertEqual(self.verify(), self.audit)
        self.assertFalse(hasattr(self.audit, "require_current"))

    def test_missing_closure_or_derived_audit_has_no_optional_fallback(self):
        for identity in (self.closure.identity, self.audit.identity):
            with self.subTest(identity=identity):
                payload = self.records.pop(identity)
                with self.assertRaises(KeyError):
                    self.verify()
                self.records[identity] = payload

    def test_each_trusted_authority_join_refuses_substitution(self):
        for field in fields(self.authority):
            with (
                self.subTest(field=field.name),
                self.assertRaises(NativeRootReplayError),
            ):
                self.verify(
                    authority=replace(
                        self.authority,
                        **{field.name: contracts.ci("foreign-" + field.name)},
                    )
                )

    def test_archive_dependencies_cannot_establish_qualification_or_hide_missing_rows(
        self,
    ):
        for trusted in (
            (),
            (
                replace(
                    self.dependency,
                    acceptance_identity=contracts.ci("foreign-acceptance"),
                ),
            ),
        ):
            with (
                self.subTest(trusted=trusted),
                self.assertRaises(NativeRootReplayError),
            ):
                self.verify(qualified_dependencies=trusted)
        self.records.pop(self.dependency.identity)
        with self.assertRaises(KeyError):
            self.verify()

    def test_each_of_six_rehashed_final_package_coordinates_must_match_original_root(
        self,
    ):
        for field in fields(self.package):
            with self.subTest(field=field.name):
                changed = replace(
                    self.package, **{field.name: contracts.ci("foreign-" + field.name)}
                )
                self.install((replace(self.accepted, final_packaged_binding=changed),))
                with self.assertRaises(NativeRootReplayError):
                    self.verify()

    def test_native_repair_request_reopens_exact_diagnostic_rejection_and_allocation(
        self,
    ):
        rejection = replace(
            self.contract.rejection,
            run_binding_identity=self.run.identity,
            component_revision=self.run.root_revision,
            candidate_ordinal=0,
            bounded_generation_request_identity=self.accepted.bounded_generation_request_identity,
            workspace_allocation_identity=self.accepted.workspace_allocation_identity,
            source_output_identity=contracts.ci("old-source"),
            node_lifecycle_result_identity=contracts.ci("old-node"),
            verifier_profile_identity=self.run.verifier_profile_identity,
            oracle_identity=self.run.oracle_identity,
            target_profile_identity=self.run.target_profile_identity,
            acceptance_scope="node-native-precheck",
            packaged_binding=None,
        )
        diagnostic = replace(
            self.contract.native_diagnostic,
            component_revision=self.run.root_revision,
            acceptance_rejection_identity=rejection.identity,
        )
        first = replace(
            self.accepted,
            source_output_identity=rejection.source_output_identity,
            node_lifecycle_result_identity=rejection.node_lifecycle_result_identity,
            outcome="native-precheck-rejected",
            failure_evidence_identity=rejection.identity,
            diagnostic_identity=diagnostic.identity,
            retryability="retryable",
            actual_packaged_acceptance_identity=None,
            final_packaged_binding=None,
        )
        request = NativeRootRepairRequest(
            self.run.identity,
            1,
            self.run.original_recipe_identity,
            (first.identity,),
            diagnostic.identity,
            rejection.identity,
            contracts.ci("new-request"),
            contracts.ci("new-workspace"),
            "native-acceptance",
            rejection.identity,
        )
        final = replace(
            self.accepted,
            ordinal=1,
            predecessor_root_attempt_identities=(first.identity,),
            incoming_request_kind="native-root-repair",
            incoming_request_identity=request.identity,
            bounded_generation_request_identity=request.bounded_generation_request_identity,
            workspace_allocation_identity=request.workspace_allocation_identity,
        )
        for record in (rejection, diagnostic, request):
            self.put(record)
        self.install((first, final))
        self.assertEqual(self.verify(), self.audit)
        for identity in (request.identity, diagnostic.identity, rejection.identity):
            payload = self.records.pop(identity)
            with self.subTest(missing=identity), self.assertRaises(KeyError):
                self.verify()
            self.records[identity] = payload
        changed = replace(
            request, workspace_allocation_identity=contracts.ci("substituted-workspace")
        )
        self.put(changed)
        self.install(
            (first, replace(final, incoming_request_identity=changed.identity))
        )
        with self.assertRaises(NativeRootReplayError):
            self.verify()

    def test_canonical_record_digest_and_bounded_reads_are_required(self):
        original = self.records[self.closure.identity]
        self.records[self.closure.identity] = original + b"\n"
        with self.assertRaises(NativeRootReplayError):
            self.verify()
        self.records[self.closure.identity] = canonical_json_bytes(self.audit.to_dict())
        with self.assertRaises(NativeRootReplayError):
            self.verify()
        self.records[self.closure.identity] = original
        with self.assertRaises(NativeRootReplayError):
            self.verify(limits=NativeRootReplayLimits(maximum_records=1))
        with self.assertRaises(NativeRootReplayError):
            self.verify(limits=NativeRootReplayLimits(maximum_record_bytes=1))

    def test_original_legacy_history_and_embedded_request_must_reopen_exactly(self):
        diagnostic = replace(
            self.contract.build_diagnostic, component_revision=self.run.root_revision
        )
        first_legacy = replace(
            self.contract.legacy0,
            component_revision=self.run.root_revision,
            diagnostic=diagnostic,
        )
        request = replace(
            self.contract.legacy_request1,
            component_revision=self.run.root_revision,
            predecessor_attempt_identities=(first_legacy.identity,),
            diagnostic_identity=diagnostic.identity,
        )
        final_legacy = replace(
            self.contract.legacy1,
            component_revision=self.run.root_revision,
            generation_response_identity=self.node.source_output.identity,
            lifecycle_result_identity=self.node.identity,
            predecessor_attempt_identities=(first_legacy.identity,),
            repair_request=request,
        )
        chain = CandidateAttemptChain(
            self.run.root_revision,
            (first_legacy, final_legacy),
            self.contract.legacy_chain.disposition,
        )
        first = replace(
            self.contract.root0,
            run_binding_identity=self.run.identity,
            legacy_node_chain_identity=chain.identity,
            diagnostic_identity=diagnostic.identity,
        )
        final = replace(
            self.accepted,
            ordinal=1,
            predecessor_root_attempt_identities=(first.identity,),
            incoming_request_kind="legacy-node-repair",
            incoming_request_identity=request.identity,
            bounded_generation_request_identity=final_legacy.generation_request_identity,
            workspace_allocation_identity=final_legacy.workspace_allocation_identity,
            legacy_node_chain_identity=chain.identity,
            legacy_node_attempt_index=1,
        )
        self.put(chain)
        self.put(request)
        self.install((first, final))
        self.assertEqual(self.verify(), self.audit)
        self.records.pop(chain.identity)
        with self.assertRaises(KeyError):
            self.verify()

    def test_untrusted_policy_or_original_subject_coordinates_cannot_select_fallback(
        self,
    ):
        with self.assertRaises(TypeError):
            self.verify(selected_policy=None)
        for name in ("final_node_identity", "final_source_output_identity"):
            with self.subTest(name=name), self.assertRaises(NativeRootReplayError):
                self.verify(
                    subject=replace(
                        self.subject, **{name: contracts.ci("foreign-subject")}
                    )
                )
