"""Original rejection-context lifetime with controlled native protocol results.

Real scope/sequence/package/storage and repair allocation run. Native commands
and version observations are explicit protocol fixtures, not qualification.
"""

import unittest
from contextlib import contextmanager
from unittest import mock

from literate_ai.adapters import rust_library_harness_execution as executor
from literate_ai.adapters.candidate_repair import (
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    activate_native_root_run,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceRejection,
    NativeRootCandidateAttempt,
    NativeRootContinuationLedger,
    NativeRootRepairDiagnostic,
)
from tests.critical import test_native_root_package_capture as package_fixture
from tests.critical import test_rust_harness_guard_budget as protocol


@unittest.skipUnless(
    package_fixture.os.name == "posix", "owned POSIX protocol fixtures"
)
class NativeRootRejectionCloseTests(unittest.TestCase):
    setUp = package_fixture.NativeRootPackageCaptureTests.setUp
    observe = package_fixture.NativeRootPackageCaptureTests.observe
    metadata = package_fixture.NativeRootPackageCaptureTests.metadata
    library_current = package_fixture.NativeRootPackageCaptureTests.library_current
    native_protocol = package_fixture.NativeRootPackageCaptureTests.native_protocol
    opened = package_fixture.NativeRootPackageCaptureTests.opened
    modeled_registered_candidate = (
        package_fixture.NativeRootPackageCaptureTests.modeled_registered_candidate
    )
    package = package_fixture.NativeRootPackageCaptureTests.package

    def operate_held(self, action, *, expire_at_close=False, close_root=False):
        with self.package() as (
            scope,
            controller,
            arguments,
            custody,
            export,
            _payload,
            _recorder,
        ):
            controller._register_current_candidate()
            repair = FilesystemStandardCandidateRepairAdapter({})
            controller.repair_port = repair
            phases, close_errors, diagnostic_ids = [], [], []
            original_close = controller.contexts.close
            original_seal = scope.seal_native_rejection
            original_retain = scope.retain_record
            original_prepare = repair.prepare_root_repair
            node = controller.node_observation[2]
            original_node = node.identity_document()
            deadline = scope.original_run.deadline

            def close():
                before = len(self.probes)
                try:
                    result = original_close()
                except BaseException as error:
                    close_errors.append(error)
                    phases.append("close refused")
                    raise
                phases.append("contexts closed")
                if "native close probe count" not in phases:
                    self.assertGreater(len(self.probes), before)
                    phases.append("native close probe count")
                return result

            def seal(*args, **kwargs):
                rejection = original_seal(*args, **kwargs)
                self.sealed_rejection = rejection
                phases.append("full native seal returned")
                if expire_at_close:
                    self.clock = self.fixture.oracle.rust_harness.timeout_seconds + 1.0
                return rejection

            def retain(record):
                if type(record) is NativeRootRepairDiagnostic:
                    phases.append("diagnostic")
                    diagnostic_ids.append(record.identity)
                elif type(record) is NativeRootCandidateAttempt:
                    phases.append("attempt")
                elif type(record) is NativeRootContinuationLedger:
                    phases.append("ledger")
                return original_retain(record)

            def prepare(*args, **kwargs):
                phases.append("fresh repair")
                return original_prepare(*args, **kwargs)

            @contextmanager
            def observe(oracle, **kwargs):
                original_current = kwargs["require_library_current"]

                def package_current():
                    original_current()
                    controller.require_current()
                    self.ports.project_package_custody(arguments[3], arguments[4])

                actual_export = custody.artifact_paths[export.identity.uri]
                kwargs.update(
                    export=actual_export,
                    library_manifest=actual_export / "Cargo.toml",
                    require_library_current=package_current,
                    record_bytes=scope.retain_bytes,
                )
                if close_root:
                    # Registered before the native context: original native
                    # final guards finish before this real root revocation.
                    controller.contexts.callback(scope.original_run.close)
                held = executor._observe_rust_library_harness_outcome(
                    oracle,
                    **kwargs,
                    original_run=scope.original_run,
                    run_binding=scope.run_binding,
                    continuation_owner=scope.continuation_owner,
                    approved_project_authority_identity=scope.run_binding.project_authority_identity,
                )
                outcome = controller.contexts.enter_context(held)
                generation, plan, actual_node = controller.node_observation
                self.assertTrue(outcome.values_differ)
                controller.observe_native_outcome(
                    outcome,
                    plan=plan,
                    source_generation=generation,
                    output=actual_node.source_output,
                    acceptance_evidence=actual_node.acceptance_evidence,
                    acceptance_scope="packaged-root",
                )
                action(scope, controller, outcome, phases, close_errors, diagnostic_ids)
                self.assertEqual(node.identity_document(), original_node)
                self.assertIs(scope.original_run.deadline, deadline)
                yield outcome.result, outcome.observation

            with (
                activate_native_root_run(scope.original_run),
                # The genuine protocol metadata/currentness helpers must name
                # the actual materialized package, not the earlier export path.
                mock.patch.object(
                    self.fixture, "export", custody.artifact_paths[export.identity.uri]
                ),
                mock.patch.object(controller.contexts, "close", side_effect=close),
                mock.patch.object(scope, "seal_native_rejection", side_effect=seal),
                mock.patch.object(scope, "retain_record", side_effect=retain),
                mock.patch.object(repair, "prepare_root_repair", side_effect=prepare),
                mock.patch.object(executor, "execute_rust_library_harness", observe),
            ):
                try:
                    protocol.RustHarnessGuardBudgetTests.operate(self)
                finally:
                    # Preserve original cleanup on all ordinary error routes.
                    original_close()

    def test_genuine_close_precedes_diagnostic_history_and_actual_fresh_repair(self):
        def action(scope, controller, outcome, phases, _errors, diagnostics):
            rejection, diagnostic = controller._seal_native(
                controller.node_observation[2]
            )
            self.assertIs(type(rejection), NativeRootAcceptanceRejection)
            self.assertFalse(outcome._active)
            self.assertTrue(outcome._consumed)
            self.assertLess(
                phases.index("full native seal returned"),
                phases.index("contexts closed"),
            )
            self.assertLess(phases.index("contexts closed"), phases.index("diagnostic"))
            old_request = controller.prepared_candidate.request.request.identity
            old_workspace = controller.prepared_candidate.workspace.allocation_identity
            controller._record_attempt(
                controller.node_observation[2],
                "package-rejected",
                rejection,
                diagnostic,
                "retryable",
            )
            controller._prepare_next(diagnostic, rejection)
            self.assertLess(phases.index("diagnostic"), phases.index("attempt"))
            self.assertLess(phases.index("ledger"), phases.index("fresh repair"))
            self.assertEqual(diagnostics, [diagnostic.identity])
            self.assertEqual(controller.sequence.consumed_candidates, 2)
            self.assertNotEqual(
                controller.prepared_candidate.request.request.identity, old_request
            )
            self.assertNotEqual(
                controller.prepared_candidate.workspace.allocation_identity,
                old_workspace,
            )
            self.assertIsNone(controller._accepted_ledger)
            self.assertEqual(
                controller.sequence._attempts[0].outcome, "package-rejected"
            )
            scope.original_run.require_current()

        self.operate_held(action)

    def test_original_operation_expiry_during_close_prevents_diagnostic_and_repair(
        self,
    ):
        def action(scope, controller, outcome, phases, errors, diagnostics):
            with self.assertRaises(ComponentAcceptanceError) as raised:
                controller._seal_native(controller.node_observation[2])
            self.assertEqual(
                raised.exception.code, "component_acceptance.rust_harness_deadline"
            )
            self.assertIs(raised.exception, errors[0])
            self.assertFalse(outcome._active)
            self.assertTrue(outcome._consumed)
            self.assertEqual(diagnostics, [])
            content = canonical_json_bytes(self.sealed_rejection.to_dict())
            self.assertEqual(
                scope._evidence.get_bytes(
                    BlobRef(self.sealed_rejection.identity.digest, len(content))
                ),
                content,
            )
            self.assertNotIn("attempt", phases)
            self.assertNotIn("fresh repair", phases)
            self.assertIsNone(controller._accepted_ledger)
            self.assertEqual(controller.sequence._attempts, ())
            self.assertIsNotNone(controller.sequence._pending)
            scope.original_run.require_current()

        self.operate_held(action, expire_at_close=True)

    def test_root_authority_is_freshly_required_after_successful_native_close(self):
        def action(_scope, controller, outcome, phases, errors, diagnostics):
            with self.assertRaises(NativeRootRunError):
                controller._seal_native(controller.node_observation[2])
            self.assertEqual(errors, [])
            self.assertIn("contexts closed", phases)
            self.assertFalse(outcome._active)
            self.assertEqual(diagnostics, [])
            self.assertNotIn("attempt", phases)
            self.assertNotIn("fresh repair", phases)
            self.assertIsNone(controller._accepted_ledger)
            self.assertEqual(controller.sequence._attempts, ())

        self.operate_held(action, close_root=True)
