"""Exact typed qualification/CAS projection controls, without native authority.

The shared producer fixture models post-source/native observations explicitly.
Real strict Standard replay, canonical records, qualification receipt membership,
publication/cache decisions and closed ledger/audit checks run. No native process,
actual disk-cache entry or installed/release qualification is asserted here.
"""

import copy
import unittest
from dataclasses import fields, replace

from literate_ai.adapters.native_root_publication_projection import (
    NativeRootPublicationProjectionError,
    recheck_native_root_publication_projection,
    verify_native_root_publication_projection,
)
from literate_ai.adapters.native_root_replay import (
    NativeRootReplayAuthority,
    NativeRootReplayError,
    NativeRootReplaySubject,
    verify_closed_native_root_bindings,
)
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
    reopen_qualification_run,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceClosure,
    NativeRootContinuationLedger,
    NativeRootExecutionResult,
    NativeRootPackageBinding,
)
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardProjectLifecycleMembership,
)
from tests.critical import test_native_root_continuation_contracts as contracts
from tests.support import fixtures_test_qualification_capture as fixture


class NativeRootPublicationProjectionTests(unittest.TestCase):
    def setUp(self):
        producer = fixture.QualificationCaptureTests()
        result, _captures, entries = producer.typed_product_fixture()
        self.records = dict(entries)
        self.reader = self.make_reader()
        # Use the existing complete strict Standard source/build/test/command
        # verifier before selecting the metadata-only projection operation.
        execution = reopen_qualification_run(
            self.reader,
            result.runs[0],
            current_commands=producer.current_commands,
            current_recipes=producer.current_recipes,
        )
        lifecycle = execution.lifecycle
        original_root = lifecycle.root_integration
        self.final = next(
            node
            for node in lifecycle.node_results
            if node.component_revision
            == original_root.package_plan.root_component_revision
        )
        self.before = replace(self.final, source_cache_publication_identity=None)
        self.put_json(self.before.identity_document())
        contract = contracts.NativeRootContinuationContractTests()
        contract.setUp()
        candidate = self.final.source_output.candidate
        self.run = replace(
            contract.run,
            root_revision=self.final.component_revision,
            component_lock_identity=original_root.component_lock_identity,
            execution_plan_identity=lifecycle.execution_plan_identity,
            target_profile_identity=original_root.package_plan.target_identity,
            original_recipe_identity=candidate.recipe_identity,
            original_generation_plan_identity=candidate.component_generation_plan_identity,
            original_bounded_request_identity=candidate.source_generation_request_identity,
            qualified_dependency_binding_identities=(),
        )
        package = NativeRootPackageBinding(
            original_root.artifact_graph.identity,
            original_root.link_plan.identity,
            original_root.package_plan.identity,
            original_root.package_result.identity,
            original_root.root_generated_integration_test_identity,
            original_root.packaged_execution_identity,
        )
        attempt = replace(
            contract.root0,
            run_binding_identity=self.run.identity,
            bounded_generation_request_identity=candidate.source_generation_request_identity,
            workspace_allocation_identity=candidate.workspace_allocation_identity,
            source_output_identity=self.final.source_output.identity,
            node_lifecycle_result_identity=self.before.identity,
            legacy_node_chain_identity=None,
            legacy_node_attempt_index=None,
            outcome="root-accepted",
            failure_evidence_identity=None,
            diagnostic_identity=None,
            retryability="none",
            actual_packaged_acceptance_identity=original_root.independent_acceptance_identity,
            final_packaged_binding=package,
        )
        self.ledger = NativeRootContinuationLedger(
            self.run.identity, (attempt,), (), "accepted", None
        )
        self.closure = NativeRootAcceptanceClosure(
            self.run.identity,
            self.ledger.identity,
            original_root.independent_acceptance_identity,
            self.final.source_output.identity,
            original_root.package_plan.identity,
            original_root.package_result.identity,
        )
        root = replace(
            original_root, independent_acceptance_identity=self.closure.identity
        )
        aggregate = replace(
            lifecycle.aggregate_receipt,
            root_integration_evidence_identity=root.identity,
        )
        self.lifecycle = replace(
            lifecycle,
            root_integration=root,
            root_integration_evidence_identity=root.identity,
            aggregate_receipt=aggregate,
            receipt_identity=aggregate.identity,
        )
        receipt = replace(
            execution.receipt,
            result_identity=self.lifecycle.identity,
            subject_identity=aggregate.identity,
        )
        self.member = replace(
            result.runs[0],
            lifecycle_result_identity=self.lifecycle.identity,
            project_receipt_identity=receipt.identity,
        )
        self.result = replace(result, runs=(self.member, *result.runs[1:]))
        self.audit = NativeRootExecutionResult(
            self.run.identity,
            self.ledger.identity,
            self.lifecycle.identity,
            self.closure.identity,
            "accepted",
        )
        for record in (
            contract.policy,
            contract.deadline,
            self.run,
            attempt,
            self.ledger,
            self.closure,
            root,
            aggregate,
            receipt,
            self.result,
            self.audit,
            self.final.source_output,
        ):
            self.put_json(record.to_dict())
        self.put_json(self.lifecycle.identity_document())
        self.policy = contract.policy
        self.authority = NativeRootReplayAuthority(
            **{
                item.name: getattr(self.run, item.name)
                for item in fields(NativeRootReplayAuthority)
            }
        )
        self.projection = self.project()

    def put_json(self, document):
        identity = canonical_identity(document)
        self.records[identity] = canonical_json_bytes(document)
        return identity

    def make_reader(self):
        return QualificationEvidenceReader(
            tuple(sorted(self.records.items(), key=lambda row: row[0].uri)),
            max_bytes=10_000_000,
            max_records=3000,
        )

    def project(self, **changes):
        arguments = dict(
            expected_qualification_result=self.result,
            member=self.member,
            lifecycle=self.lifecycle,
            prepublication_node_identity=self.before.identity,
        )
        arguments.update(changes)
        return verify_native_root_publication_projection(
            self.make_reader(), **arguments
        )

    def recheck(self, projection=None):
        recheck_native_root_publication_projection(
            read_json=self.make_reader().read_json,
            projection=self.projection if projection is None else projection,
            lifecycle_identity=self.lifecycle.identity,
            published_node_identity=self.final.identity,
            prepublication_node_identity=(
                self.projection if projection is None else projection
            ).prepublication_node_identity,
            source_output_identity=self.final.source_output.identity,
        )

    def core(self, **changes):
        arguments = dict(
            read_record=self.make_reader().read_bytes,
            selected_policy=self.policy,
            authority=self.authority,
            subject=NativeRootReplaySubject(
                self.lifecycle.identity,
                self.lifecycle.root_integration,
                self.final.identity,
                self.final.source_output.identity,
            ),
            qualified_dependencies=(),
        )
        arguments.update(changes)
        return verify_closed_native_root_bindings(**arguments)

    def test_explicit_projection_preserves_original_closed_records_and_exact_core(self):
        before = dict(self.records)
        self.assertEqual(self.projection.published_node_identity, self.final.identity)
        self.assertEqual(
            self.projection.prepublication_node_identity, self.before.identity
        )
        self.assertNotEqual(self.final.identity, self.before.identity)
        self.assertEqual(self.core(publication_projection=self.projection), self.audit)
        self.assertEqual(self.records, before)

    def test_no_projection_matcher_still_refuses_different_immutable_ledger_node(self):
        with self.assertRaisesRegex(NativeRootReplayError, "final_subject_changed"):
            self.core()

    def test_missing_exact_prepublication_record_refuses(self):
        del self.records[self.before.identity]
        with self.assertRaises(QualificationCaptureError):
            self.project()

    def test_every_additional_rehashed_prepublication_field_change_refuses(self):
        document = self.before.identity_document()
        for key in document:
            if key == "source_cache_publication_identity":
                continue
            with self.subTest(field=key):
                changed = copy.deepcopy(document)
                changed[key] = "coherently rehashed foreign field"
                identity = self.put_json(changed)
                with self.assertRaisesRegex(
                    NativeRootPublicationProjectionError, "node_projection_changed"
                ):
                    self.project(prepublication_node_identity=identity)

    def test_wrong_current_qualification_membership_cannot_be_adopted(self):
        member = replace(
            self.member,
            lifecycle_result_identity=canonical_identity("foreign lifecycle"),
        )
        result = replace(self.result, runs=(member, *self.result.runs[1:]))
        self.put_json(result.to_dict())
        with self.assertRaisesRegex(
            NativeRootPublicationProjectionError, "current_qualification_changed"
        ):
            self.project(expected_qualification_result=result)

    def test_forged_constructor_coordinates_and_boolean_cannot_bypass_core(self):
        with self.assertRaises(TypeError):
            self.core(publication_projection=True)
        changed = replace(
            self.projection, source_output_identity=canonical_identity("foreign source")
        )
        with self.assertRaisesRegex(
            NativeRootPublicationProjectionError, "subject_changed"
        ):
            self.core(publication_projection=changed)

    def test_already_published_record_cannot_be_renamed_prepublication(self):
        with self.assertRaisesRegex(
            NativeRootPublicationProjectionError, "node_projection_changed"
        ):
            self.project(prepublication_node_identity=self.final.identity)

    def test_core_rechecks_complete_publication_membership_not_constructor_claim(self):
        # Rehash a whole candidate graph coherently, but remove the actual
        # publication attestation. Public construction is not a validation token.
        membership = self.lifecycle.lifecycle_membership
        decisions = tuple(
            replace(row, publication_identity=None)
            if row.component_revision == self.final.component_revision
            else row
            for row in membership.cache_decisions
        )
        forged = StandardProjectLifecycleMembership(
            membership.execution_plan_identity, membership.planned_nodes, decisions
        )
        self.put_json(forged.to_dict())
        aggregate = replace(
            self.lifecycle.aggregate_receipt,
            lifecycle_membership_identity=forged.identity,
        )
        self.put_json(aggregate.to_dict())
        data = self.lifecycle.identity_document()
        data.update(
            lifecycle_membership_identity=forged.identity.uri,
            aggregate_receipt_identity=aggregate.identity.uri,
            receipt_identity=aggregate.identity.uri,
        )
        lifecycle_id = self.put_json(data)
        original_receipt = self.make_reader().read_json(
            self.member.project_receipt_identity
        )
        original_receipt.update(result=lifecycle_id.uri, subject=aggregate.identity.uri)
        receipt_id = self.put_json(original_receipt)
        member = replace(
            self.member,
            lifecycle_result_identity=lifecycle_id,
            project_receipt_identity=receipt_id,
            cache_decision_identities=tuple(
                sorted((row.identity for row in decisions), key=lambda value: value.uri)
            ),
        )
        result = replace(self.result, runs=(member, *self.result.runs[1:]))
        self.put_json(result.to_dict())
        projection = replace(
            self.projection,
            lifecycle_identity=lifecycle_id,
            qualification_result_identity=result.identity,
        )
        with self.assertRaisesRegex(
            NativeRootPublicationProjectionError, "cache_decision_changed"
        ):
            recheck_native_root_publication_projection(
                read_json=self.make_reader().read_json,
                projection=projection,
                lifecycle_identity=lifecycle_id,
                published_node_identity=self.final.identity,
                prepublication_node_identity=self.before.identity,
                source_output_identity=self.final.source_output.identity,
            )
