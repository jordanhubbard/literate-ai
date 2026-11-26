"""Real closed joins and source CAS through the mandatory dispatch boundary.

Source production, post-source lifecycle and current-provider authority are
explicit modeled seams. Actual canonical source bytes/manifests, typed lifecycle,
root/package/attempt/ledger/closure/audit and qualification-member joins run.
The final full-history verifier is controlled here; no native or qualification
success is claimed by a successful dispatch control.
"""

import sys
import types
import unittest
from contextlib import contextmanager
from dataclasses import fields, replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_retained_ingress as ingress
from literate_ai.adapters import qualification_capture as capture
from literate_ai.adapters.native_root_replay import NativeRootReplayAuthority
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceClosure,
    NativeRootContinuationLedger,
    NativeRootExecutionResult,
    NativeRootPackageBinding,
)
from tests.critical import test_native_root_source_history_replay as source_fixture
from tests.support import fixtures_test_qualification_capture as qualification_fixture
from tests.support import fixtures_test_standard_project_lifecycle as model

_FULL_HISTORY_MODULE = "literate_ai.adapters.native_root_qualification_replay"


class NativeRootIngressDispatchTests(unittest.TestCase):
    def setUp(self):
        source = source_fixture.NativeRootSourceHistoryReplayTests()
        self.addCleanup(source.doCleanups)
        source.setUp()
        self.source = source
        execution = source.current.execution_plan
        root = execution.root_revision
        names = {root.uri: "ingress-fixture"}
        ports = model.ContractEvidenceLifecyclePorts(
            execution, names, library_exports=True
        )
        ports.generated_outputs[root.uri] = source.output
        service = model._service(ports)
        # Generation bytes/CAS are the existing real source-capture fixture;
        # the modeled post-source lifecycle performs no compiler/native process.
        service.generator = lambda prepared: source.output
        lifecycle = service.execute(
            execution,
            component_lock=source.current.snapshot.authority.lock,
            invalidation=model._decision(
                execution, names, "ingress-fixture", ("ingress-fixture",)
            ),
            prepared_nodes={root.uri: source.prepared},
        )
        self.assertTrue(lifecycle.successful)
        self.node = lifecycle.node_results[0]
        self.before = replace(self.node, source_cache_publication_identity=None)
        self.assertEqual(self.node.source_output, source.output)
        package = lifecycle.root_integration
        coordinates = NativeRootPackageBinding(
            package.artifact_graph.identity,
            package.link_plan.identity,
            package.package_plan.identity,
            package.package_result.identity,
            package.root_generated_integration_test_identity,
            package.packaged_execution_identity,
        )
        self.run = replace(
            source.run, target_profile_identity=package.package_plan.target_identity
        )
        self.attempt = replace(
            source.attempt,
            run_binding_identity=self.run.identity,
            node_lifecycle_result_identity=self.before.identity,
            legacy_node_chain_identity=None,
            legacy_node_attempt_index=None,
            outcome="root-accepted",
            failure_evidence_identity=None,
            diagnostic_identity=None,
            retryability="none",
            actual_packaged_acceptance_identity=package.independent_acceptance_identity,
            final_packaged_binding=coordinates,
        )
        self.ledger = NativeRootContinuationLedger(
            self.run.identity, (self.attempt,), (), "accepted", None
        )
        self.closure = NativeRootAcceptanceClosure(
            self.run.identity,
            self.ledger.identity,
            package.independent_acceptance_identity,
            source.output.identity,
            package.package_plan.identity,
            package.package_result.identity,
        )
        package = replace(
            package, independent_acceptance_identity=self.closure.identity
        )
        receipt = replace(
            lifecycle.aggregate_receipt,
            root_integration_evidence_identity=package.identity,
        )
        self.lifecycle = replace(
            lifecycle,
            root_integration=package,
            root_integration_evidence_identity=package.identity,
            aggregate_receipt=receipt,
            receipt_identity=receipt.identity,
        )
        self.audit = NativeRootExecutionResult(
            self.run.identity,
            self.ledger.identity,
            self.lifecycle.identity,
            self.closure.identity,
            "accepted",
        )
        authority = NativeRootReplayAuthority(
            **{
                item.name: getattr(self.run, item.name)
                for item in fields(NativeRootReplayAuthority)
            }
        )
        contract = source_fixture.contracts.NativeRootContinuationContractTests()
        contract.setUp()
        self.context = SimpleNamespace(
            provider_id=source.provider,
            preparation=source.current,
            policy=contract.policy,
            command=SimpleNamespace(component_revision=root),
            binding_expectations=lambda: authority,
            qualified_dependencies=(),
        )
        fixture = qualification_fixture.QualificationCaptureTests()
        original, _products, original_entries = fixture.typed_product_fixture()
        from literate_ai.contracts.testing import ProjectTestReceipt, ProjectTestSummary
        from literate_ai.source_to_specification.qualification_lifecycle import (
            QualificationLifecycleExecution,
            QualificationLifecycleRunner,
        )

        original_reader = capture.QualificationEvidenceReader(
            original_entries, max_bytes=10_000_000, max_records=2000
        )
        total = sum(
            node.generated_test_evidence.executed_count
            for node in self.lifecycle.node_results
        )
        self.project_receipt = replace(
            ProjectTestReceipt.from_dict(
                original_reader.read_json(original.runs[0].project_receipt_identity)
            ),
            result_identity=self.lifecycle.identity,
            subject_identity=self.lifecycle.aggregate_receipt.identity,
            summary=ProjectTestSummary(total, total, 0, 0),
        )
        first = original.runs[0]
        derived = QualificationLifecycleRunner._derive_standard(
            QualificationLifecycleExecution(
                self.lifecycle,
                self.project_receipt,
                first.lifecycle_request_identity,
                first.lifecycle_invocation_identity,
                first.driver_identity,
                first.lifecycle_policy_identity,
                first.framework_distribution_identity,
            )
        )
        names = (
            "source_tree_identities",
            "source_index_identities",
            "build_evidence_identities",
            "resolved_sbom_identities",
            "generated_test_suite_identities",
            "generated_test_evidence_identities",
            "generated_test_case_identities",
            "acceptance_evidence_identities",
            "cache_decision_identities",
            "node_workspace_identities",
        )
        parity = replace(
            original.parity_evidence[0], generated_tree_identities=derived[0]
        )
        self.member = replace(
            first,
            lifecycle_result_identity=self.lifecycle.identity,
            project_receipt_identity=self.project_receipt.identity,
            parity_evidence_identity=parity.identity,
            generated_test_total=total,
            **dict(zip(names, derived, strict=True)),
        )
        self.result = replace(
            original,
            runs=(self.member, *original.runs[1:]),
            parity_evidence=(parity, *original.parity_evidence[1:]),
        )
        # This explicit modeled current promotion/result is independent of the
        # reader passed below. Current filesystem guard behavior has its own tests.
        self.selected = ingress.NativeRootRetainedQualificationIngress(
            None,
            self.context,
            self.result,
            (),
            canonical_identity("modeled current ingress"),
        )
        self.recorder = capture.QualificationEvidenceRecorder(
            max_bytes=10_000_000, max_records=2000
        )
        capture.capture_qualification_source_records(
            self.recorder, candidate=source.output.candidate, cas=source.cas
        )
        for record in (
            contract.policy,
            contract.deadline,
            self.run,
            self.attempt,
            self.ledger,
            self.closure,
            self.audit,
            source.output,
            self.result,
        ):
            self.recorder.remember_json(record.to_dict())
        capture.capture_lifecycle_records(self.lifecycle, self.recorder)
        self.recorder.remember_json(self.project_receipt.to_dict())
        for record in (self.node, self.before, self.lifecycle):
            self.recorder.remember_json(record.identity_document())
        self.recorder.remember_json(package.to_dict())
        self.expected_c = source_fixture.ContentIdentity.parse_uri(
            source.transport.tool_binding_identity
        )

    def reader(self, omit=()):
        return capture.QualificationEvidenceReader(
            tuple(entry for entry in self.recorder.entries if entry[0] not in omit),
            max_bytes=10_000_000,
            max_records=2000,
        )

    def verify(self, reader=None):
        return self.selected.verify_member(
            self.reader() if reader is None else reader,
            result=self.result,
            member=self.member,
            lifecycle=self.lifecycle,
            product="explicit modeled product seam",
            max_package_bytes=4096,
        )

    @contextmanager
    def current_guard(self):
        def current(selected):
            self.assertIs(selected, self.selected)
            self.assertIs(selected.qualification_result, self.result)

        with mock.patch.object(
            ingress.NativeRootRetainedQualificationIngress, "require_unchanged", current
        ):
            yield

    def module(self, delegate):
        module = types.ModuleType(_FULL_HISTORY_MODULE)
        module.verify_closed_native_root_qualification_history = delegate
        return module

    def test_exact_real_joins_select_c_and_dispatch_original_context(self):
        history = mock.Mock()
        with (
            self.current_guard(),
            mock.patch.dict(
                sys.modules,
                {
                    _FULL_HISTORY_MODULE: self.module(history),
                },
            ),
        ):
            self.assertIsNone(self.verify())
        history.assert_called_once()
        self.assertIs(history.call_args.kwargs["context"], self.context)
        self.assertEqual(history.call_args.kwargs["audit"], self.audit)
        self.assertIs(history.call_args.kwargs["lifecycle"], self.lifecycle)
        self.assertEqual(
            history.call_args.kwargs["expected_tool_binding_identity"], self.expected_c
        )
        self.assertEqual(history.call_args.kwargs["max_package_bytes"], 4096)

    def test_missing_full_verifier_refuses_after_real_joins_without_legacy_fallback(
        self,
    ):
        with (
            self.current_guard(),
            mock.patch.dict(
                sys.modules,
                {_FULL_HISTORY_MODULE: None},
            ),
            mock.patch.object(
                capture,
                "verify_qualification_library_acceptance",
                side_effect=AssertionError("legacy fallback"),
            ) as legacy,
        ):
            with self.assertRaisesRegex(
                ingress.NativeRootRetainedIngressError, "full_history_verifier_required"
            ):
                self.verify()
        legacy.assert_not_called()

    def test_full_history_refusal_is_same_primary_and_has_no_legacy_fallback(self):
        primary = ValueError("actual mandatory history refusal seam")
        history = mock.Mock(side_effect=primary)
        with (
            self.current_guard(),
            mock.patch.dict(
                sys.modules,
                {_FULL_HISTORY_MODULE: self.module(history)},
            ),
            mock.patch.object(
                capture,
                "verify_qualification_library_acceptance",
                side_effect=AssertionError("legacy fallback"),
            ) as legacy,
        ):
            with self.assertRaises(ValueError) as caught:
                self.verify()
        self.assertIs(caught.exception, primary)
        history.assert_called_once()
        legacy.assert_not_called()

    def test_missing_exact_audit_or_source_stage_refuses_before_full_dispatch(self):
        for identity in (
            self.audit.identity,
            self.source.output.provenance.model_stage_output_identities[0],
        ):
            with self.subTest(identity=identity):
                history = mock.Mock()
                with (
                    self.current_guard(),
                    mock.patch.dict(
                        sys.modules,
                        {
                            _FULL_HISTORY_MODULE: self.module(history),
                        },
                    ),
                ):
                    with self.assertRaises(capture.QualificationCaptureError):
                        self.verify(self.reader(omit=(identity,)))
                history.assert_not_called()
