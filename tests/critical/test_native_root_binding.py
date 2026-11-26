"""Original binding controls with explicitly modeled framework/tool observations.

Loaded verifier inputs and command files use real local filesystem custody.
Framework planning and measured tool observations are synthetic fixtures. No
native command, source provider, installed framework or qualification runs.
"""

from __future__ import annotations

import copy
import hashlib
import os
import pickle
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_continuation as continuation
from literate_ai.adapters import rust_library_harness_execution as executor
from literate_ai.adapters.action_build_result import _capture_files
from literate_ai.adapters.candidate_repair import (
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.adapters.directory_artifacts import encode_directory_export
from literate_ai.adapters.generation_preparation import PreparedLockedGeneration
from literate_ai.adapters.lifecycle.standard_cargo import (
    StandardCargoLifecyclePorts,
    StandardCargoTarget,
    _retain_rust_harness_compilers,
)
from literate_ai.adapters.lifecycle.standard_local import LocalSourceTreeRegistry
from literate_ai.adapters.qualification_capture import QualificationEvidenceRecorder
from literate_ai.application.native_root_run import open_native_root_run
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.component_locking import ComponentLock
from literate_ai.contracts.executable_components import (
    CandidateFailureClassification,
    CandidateRepairDiagnostic,
    ComponentCommandPhase,
    SourceGenerationDisposition,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_root_continuation import (
    NATIVE_ROOT_RESULT_MISMATCH,
    NativeRootPackageBinding,
    NativeRootRunPolicy,
)
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailureEvidence,
    StandardNodeFailurePhase,
)
from literate_ai.projects import PinnedInputClosure
from literate_ai.storage.cas import FileSystemCAS
from tests.critical import test_rust_harness_guard_budget as protocol
from tests.support import fixtures_test_component_lock_contracts as locks
from tests.support import fixtures_test_standard_project_lifecycle as model


@unittest.skipUnless(os.name == "posix", "owned POSIX protocol fixtures")
class NativeRootBindingTests(unittest.TestCase):
    observe = protocol.RustHarnessGuardBudgetTests.observe
    metadata = protocol.RustHarnessGuardBudgetTests.metadata
    library_current = protocol.RustHarnessGuardBudgetTests.library_current

    def native_protocol(self, argv, **kwargs):
        result = protocol.RustHarnessGuardBudgetTests.native_protocol(
            self, argv, **kwargs
        )
        if argv[0] != self.cargo.command[0]:
            import json

            document = json.loads(result.stdout)
            document["cases"][0]["result"] = {"synthetic": "wrong native value"}
            result.stdout = json.dumps(document).encode()
        return result

    def setUp(self):
        protocol.RustHarnessGuardBudgetTests.setUp(self)
        authoring = locks.component_authoring(
            "qualified-fixture", interface=("qualified.answer", "fixture-interface")
        )
        revision = locks.locked_revision(
            "qualified-fixture",
            selected_flavor="rust",
            interface=("qualified.answer", "fixture-interface"),
            authoring=authoring,
        )
        target_profile = canonical_identity({"target": "host"})
        self.lock = ComponentLock(
            target_name="host",
            target_profile_identity=target_profile,
            selection_policy_identity=locks.identity("selection-policy"),
            resolver_identity=locks.identity("resolver"),
            root_revision=revision.identity,
            nodes=(
                locks.node(
                    revision,
                    selected_flavor="rust",
                    capability="qualified.answer",
                    target_profile_identity=target_profile,
                ),
            ),
            edges=(),
            _authorings=(authoring,),
        )
        self.execution, requests = model._prepared_execution(self.lock)
        self.node = model._prepared_nodes(self.execution, requests)[
            revision.identity.uri
        ]
        workspace = self.root / "candidate-workspace"
        workspace.mkdir()
        self.node = replace(
            self.node,
            workspace=replace(
                self.node.workspace,
                locator=str(workspace),
                allocation_identity=canonical_identity(
                    {
                        "schema": "literate-ai/component-workspace-allocation@1",
                        "component_revision": self.node.plan.component_revision.uri,
                        "generation_plan_identity": self.node.plan.identity.uri,
                        "locator": str(workspace),
                    }
                ),
            ),
        )
        interface = revision.public_interfaces[0].identity
        self.fixture.interface = interface
        self.fixture.surface = replace(
            self.fixture.surface,
            capabilities=(
                replace(
                    self.fixture.surface.capabilities[0], interface_identity=interface
                ),
            ),
        )
        self.fixture.author_oracle(
            specification_identity=revision.specification_set_identity
        )
        contract = model.command_contract_fixture(
            revision.identity, "qualified-fixture", library_exports=True
        )
        target = StandardCargoTarget(
            revision.identity,
            contract.build_system_resolver_identity,
            self.cargo.authority_identity,
            self.rustc.authority_identity,
            "Cargo.toml",
            "qualified_fixture",
            self.rustc.command,
            library=True,
        )
        contract = replace(
            contract,
            locked_build_authority_identity=target.identity,
            build_system_toolchain_identity=self.cargo.authority_identity,
            language_compiler_identity=self.rustc.authority_identity,
            tool_bindings=tuple(
                replace(
                    item,
                    toolchain_identity=(
                        self.cargo.authority_identity
                        if item.phase is ComponentCommandPhase.BUILD
                        else self.rustc.authority_identity
                    ),
                )
                for item in contract.tool_bindings
            ),
            artifact_export=replace(
                contract.artifact_export,
                target_identity=target_profile,
                producer_identity=self.rustc.authority_identity,
            ),
            library_import_surface=self.fixture.surface,
        )
        self.ports = StandardCargoLifecyclePorts(
            source_trees=LocalSourceTreeRegistry(),
            object_root=self.root / "objects",
            contracts=(contract,),
            tool_bindings=(self.cargo, self.rustc),
            cargo_targets=(target,),
            rust_harness_compilers=_retain_rust_harness_compilers((self.rust_owner,)),
            execution_plan=self.execution,
            independent_acceptance_oracle=self.fixture.oracle,
        )
        self.closure = PinnedInputClosure()
        self.closure.pin(
            self.fixture.oracle_path, boundary=self.fixture.root, label="oracle"
        )
        # Explicit source-framework seam, not a claim of actual project admission.
        self.snapshot = SimpleNamespace(
            authority=SimpleNamespace(lock=self.lock),
            require_unchanged=self.closure.require_unchanged,
        )
        self.prepared = PreparedLockedGeneration(
            component_root=self.fixture.root,
            boundary=self.root,
            definition=authoring,
            recipe=self.node.recipe,
            selected_flavors=(),
            component_revision=revision,
            toolchain_constraints=(),
            input_closure=self.closure,
            flavor_catalog_audit_identity=canonical_identity({"catalog": 1}),
            locked_authority_snapshot=self.snapshot,
        )

    @contextmanager
    def opened(self, **changes):
        with open_native_root_run(
            NativeRootRunPolicy(180, 3),
            project_identity=canonical_identity({"project": 1}),
            framework_distribution_identity=canonical_identity({"framework": 1}),
            lifecycle_policy_identity=canonical_identity({"policy": 1}),
            require_current=self.closure.require_unchanged,
        ) as run:
            arguments = dict(
                original_run=run,
                approved_project_authority_identity=canonical_identity({"approved": 1}),
                component_lock=self.lock,
                execution_plan=self.execution,
                prepared_root=self.node,
                accepted_source_only=False,
                retained_source=None,
            )
            arguments.update(changes)
            with continuation._native_root_continuation(
                self.prepared, self.ports, **arguments
            ) as owner:
                yield owner, run

    def assert_reason(self, operation, reason):
        with self.assertRaises(continuation.NativeRootContinuationError) as caught:
            operation()
        self.assertEqual(caught.exception.code, "native_root_continuation." + reason)

    def test_original_bindings_are_exact_and_context_exit_revokes(self):
        with self.opened() as (owner, run):
            self.assertIs(owner.prepared_root, self.node)
            self.assertIs(owner.ports, self.ports)
            self.assertIs(owner.original_run, run)
            self.assertEqual(owner.run_binding.root_revision, self.lock.root_revision)
            self.assertEqual(
                owner.run_binding.original_bounded_request_identity,
                self.node.request.request.identity,
            )
            self.assertEqual(
                owner.run_binding.target_profile_identity,
                self.lock.target_profile_identity,
            )
            owner.require_current()
        self.assert_reason(owner.require_current, "closed")
        self.assertEqual(self.commands, [])

    def test_factory_cannot_reseal_authority_changed_by_an_admission_callback(self):
        authority = canonical_identity({"approved-original": 1})
        replacement = canonical_identity({"substituted": "authority"})

        def current():
            self.closure.require_unchanged()
            object.__setattr__(authority, "digest", replacement.digest)

        self.snapshot.require_unchanged = current
        with self.assertRaises(continuation.NativeRootContinuationError):
            with self.opened(approved_project_authority_identity=authority):
                self.fail(
                    "admission callback changed approved authority before sealing"
                )

    def test_original_recipe_uri_string_uses_same_binding_identity(self):
        self.node = replace(
            self.node,
            recipe=replace(self.node.recipe, identity=self.node.recipe.identity.uri),
        )
        with self.opened() as (owner, _run):
            self.assertEqual(
                owner.run_binding.original_recipe_identity.uri,
                self.node.recipe.identity,
            )

    def test_retained_and_accepted_only_are_initially_unsupported(self):
        for change in ({"retained_source": object()}, {"accepted_source_only": True}):
            with (
                self.subTest(change=change),
                mock.patch.object(
                    self.ports,
                    "retain_evidence_with",
                    wraps=self.ports.retain_evidence_with,
                ) as install,
                self.opened(**change) as (owner, _run),
            ):
                self.assertIsNone(owner)
                install.assert_not_called()
                self.assertIsNone(self.ports._evidence_recorder)

    def test_drift_never_downgrades_and_restoration_cannot_revive(self):
        with self.opened() as (owner, _run):
            oracle = self.ports.independent_acceptance_oracle
            self.ports.independent_acceptance_oracle = copy.copy(oracle)
            self.assert_reason(owner.require_current, "binding_changed")
            self.ports.independent_acceptance_oracle = oracle
            self.assert_reason(owner.require_current, "closed")

    def test_decoded_binding_copy_pickle_and_fork_do_not_restore_scope(self):
        with self.opened() as (owner, _run):
            for operation in (
                lambda: copy.copy(owner),
                lambda: copy.deepcopy(owner),
                lambda: pickle.dumps(owner),
                continuation._LiveNativeRootContinuation,
            ):
                with self.assertRaises(TypeError):
                    operation()
            with mock.patch.object(
                continuation.os, "getpid", return_value=owner._pid + 1
            ):
                with mock.patch.object(owner, "_lock") as lock:
                    lock.__enter__.side_effect = AssertionError(
                        "inherited lock touched"
                    )
                    self.assert_reason(owner.require_current, "owner_invalid")
                    owner.close()
                    lock.__enter__.assert_not_called()
            owner.require_current()

    def test_generic_acceptance_data_cannot_assert_fresh_generation(self):
        with self.opened() as (owner, _run):
            self.assert_reason(
                lambda: owner.require_candidate(None, None, object()),
                "candidate_stage_invalid",
            )
            self.assert_reason(owner.require_current, "closed")

    def test_unsupplied_recorder_is_bounded_original_storage_with_actual_cas_bytes(
        self,
    ):
        self.assertIsNone(self.ports._evidence_recorder)
        with (
            mock.patch.object(
                self.ports,
                "retain_evidence_with",
                wraps=self.ports.retain_evidence_with,
            ) as install,
            self.opened() as (owner, _run),
        ):
            install.assert_called_once()
            recorder = self.ports._evidence_recorder
            self.assertIsInstance(recorder, QualificationEvidenceRecorder)
            self.assertIs(owner._recorder, recorder)
            self.assertEqual(recorder.max_bytes, 256 * 1024**2)
            self.assertEqual(recorder.max_records, 100_000)
            self.assertEqual(self.ports._build_evidence, {})
            self.assertEqual(self.ports._build_observations, {})
            raw = b"actual immutable evidence bytes"
            identity = owner.retain_bytes(raw)
            record = owner.retain_record(owner.run_binding)
            self.assertEqual(record, owner.run_binding.identity)
            store = FileSystemCAS(
                self.ports.object_root / "native-root-continuation-evidence",
                create=False,
            )
            self.assertEqual(store.get_bytes(BlobRef(identity.digest, len(raw))), raw)
            self.assertEqual(dict(recorder.entries)[identity], raw)
            content = canonical_json_bytes(owner.run_binding.to_dict())
            self.assertEqual(
                store.get_bytes(BlobRef(record.digest, len(content))), content
            )

    def test_recorder_replacement_cannot_rebind_original_scope(self):
        with self.opened() as (owner, _run):
            original = owner._recorder
            self.ports._evidence_recorder = QualificationEvidenceRecorder(
                max_bytes=original.max_bytes, max_records=original.max_records
            )
            self.assert_reason(owner.require_current, "binding_changed")
            self.ports._evidence_recorder = original
            self.assert_reason(owner.require_current, "closed")

    def test_original_recorder_limits_cannot_grow_during_scope(self):
        with self.opened() as (owner, _run):
            recorder = owner._recorder
            original = recorder.max_bytes
            recorder.max_bytes += 1
            self.assert_reason(owner.require_current, "binding_changed")
            recorder.max_bytes = original
            self.assert_reason(owner.require_current, "closed")

    def test_retention_also_joins_installed_bounded_recorder(self):
        recorder = QualificationEvidenceRecorder(max_bytes=1024**2, max_records=100)
        self.ports._evidence_recorder = recorder
        with self.opened() as (owner, _run):
            self.assertIs(owner._recorder, recorder)
            self.assertIs(self.ports._evidence_recorder, recorder)
            self.assertEqual((recorder.max_bytes, recorder.max_records), (1024**2, 100))
            raw = b"native executable protocol bytes"
            self.assertEqual(owner.retain_bytes(raw), recorder.remember_bytes(raw))
            self.assertEqual(
                owner.retain_record(owner.run_binding),
                recorder.remember_json(owner.run_binding.to_dict()),
            )

    @contextmanager
    def modeled_registered_candidate(self, prepared=None):
        """Actual typed lifecycle fixture; framework registration is modeled here."""
        prepared = self.node if prepared is None else prepared
        names = {self.lock.root_revision.uri: "qualified-fixture"}
        ports = model.ContractEvidenceLifecyclePorts(
            self.execution, names, library_exports=True
        )
        # The modeled producer must use the same target approved by the
        # original native contract; a generic test target is another authority.
        ports.artifact_target_identity = self.lock.target_profile_identity
        result = model._service(ports).execute(
            self.execution,
            component_lock=self.lock,
            invalidation=model._decision(
                self.execution, names, "qualified-fixture", ("qualified-fixture",)
            ),
            prepared_nodes={self.lock.root_revision.uri: prepared},
            max_parallelism=1,
        )
        node = result.node_results[0]
        plan = ports.plans[self.lock.root_revision.uri]
        old = node.build_evidence
        tree = self.fixture.export
        files, _native = _capture_files(tree, lambda: None)
        archive = encode_directory_export(
            files,
            max_bytes=1024**2,
            max_entries=10,
        )
        original_export = old.exports[0]
        export = replace(
            original_export,
            blob=BlobRef(
                hashlib.sha256(archive).hexdigest(),
                len(archive),
                media_type=original_export.media_type,
            ),
        )
        exports = tuple(
            export if item == original_export else item for item in old.exports
        )
        build = replace(
            old,
            exports=exports,
            resolved_sbom_export_identities=tuple(
                sorted((item.identity for item in exports), key=lambda value: value.uri)
            ),
        )
        tests = replace(
            node.generated_test_evidence,
            build_evidence_identity=build.identity,
            export_identities=build.export_identities,
        )
        execution = replace(
            node.execution_evidence,
            build_evidence_identity=build.identity,
            export_identities=build.export_identities,
            root_export_identity=export.identity,
        )
        accepted = replace(
            node.acceptance_evidence,
            build=build,
            generated_tests=tests,
            execution=execution,
        )
        stage = continuation.NativeRootCandidateStage(
            prepared, node.source_generation, accepted
        )
        membership = replace(
            node.source_cache_membership, acceptance_identity=accepted.identity
        )
        self.modeled_node = replace(
            node,
            exports=build.exports,
            build_identity=build.identity,
            test_identity=tests.identity,
            execution_identity=execution.identity,
            acceptance_identity=accepted.identity,
            build_evidence=build,
            generated_test_evidence=tests,
            execution_evidence=execution,
            acceptance_evidence=accepted,
            source_cache_membership=membership,
            source_cache_publication_identity=None,
        )
        self.ports._planned_exports[self.lock.root_revision.uri] = export
        source = SimpleNamespace(
            source_generation_identity=node.source_output.identity,
            candidate=node.source_output.candidate,
        )
        with ExitStack() as mocks:
            mocks.enter_context(
                mock.patch.object(
                    self.ports, "build_execution_inputs", return_value=None
                )
            )
            mocks.enter_context(
                mock.patch.object(
                    self.ports,
                    "acceptance_stage_evidence",
                    return_value=(build, tests, execution),
                )
            )
            mocks.enter_context(
                mock.patch.object(self.ports, "artifact_path", return_value=tree)
            )
            mocks.enter_context(
                mock.patch.object(
                    self.ports.source_trees, "evidence", return_value=source
                )
            )
            mocks.enter_context(
                mock.patch.object(
                    self.ports.source_trees,
                    "registered_root",
                    return_value=Path(prepared.workspace.locator),
                )
            )
            yield node.source_output, plan, stage, tree

    def test_fresh_generated_stage_joins_registered_export_bytes(self):
        with self.modeled_registered_candidate() as (output, plan, stage, _tree):
            with self.opened() as (owner, _run):
                build, _tests, _execution, export = owner.require_candidate(
                    output, plan, stage
                )
                self.assertIn(export, build.exports)

    def test_reused_and_changed_workspace_cannot_borrow_generated_stage(self):
        with self.modeled_registered_candidate() as (output, plan, stage, _tree):
            reused = replace(
                stage,
                source_generation=replace(
                    stage.source_generation,
                    disposition=SourceGenerationDisposition.REUSED,
                ),
            )
            workspace = replace(
                self.node.workspace,
                allocation_identity=canonical_identity({"other-workspace": 1}),
            )
            changed = replace(
                stage, prepared_candidate=replace(self.node, workspace=workspace)
            )
            for candidate in (reused, changed):
                with self.subTest(candidate=candidate), self.opened() as (owner, _run):
                    self.assert_reason(
                        lambda candidate=candidate: owner.require_candidate(
                            output, plan, candidate
                        ),
                        "candidate_not_fresh",
                    )
                    self.assert_reason(owner.require_current, "closed")

    def test_registered_export_mutation_refuses_actual_bytes(self):
        with self.modeled_registered_candidate() as (output, plan, stage, tree):
            with self.opened() as (owner, _run):
                (tree / "src/lib.rs").write_bytes(b"// changed physical export\n")
                self.assert_reason(
                    lambda: owner.require_candidate(output, plan, stage),
                    "candidate_export_changed",
                )

    def test_generated_source_guard_does_not_require_positive_build(self):
        with self.modeled_registered_candidate() as (output, _plan, stage, _tree):
            with (
                self.opened() as (owner, _run),
                mock.patch.object(
                    self.ports,
                    "build_execution_inputs",
                    side_effect=AssertionError("BUILD required too early"),
                ),
            ):
                source = owner.require_generated_source(
                    stage.prepared_candidate, stage.source_generation, output
                )
                self.assertIs(source.candidate, output.candidate)

    def test_copied_original_preparation_pointer_cannot_borrow_scope(self):
        with self.opened() as (owner, _run):
            owner._prepared_root = replace(self.node)
            self.assert_reason(owner.require_current, "binding_changed")

    def with_outcome(self, scope, action):
        @contextmanager
        def observe(oracle, **arguments):
            arguments["record_bytes"] = scope.retain_bytes
            with executor._observe_rust_library_harness_outcome(
                oracle,
                **arguments,
                original_run=scope.original_run,
                run_binding=scope.run_binding,
                continuation_owner=scope.continuation_owner,
                approved_project_authority_identity=scope.run_binding.project_authority_identity,
            ) as outcome:
                action(outcome)
                yield outcome.result, outcome.observation

        with mock.patch.object(executor, "execute_rust_library_harness", observe):
            protocol.RustHarnessGuardBudgetTests.operate(self)

    def failed_node(self, outcome, *, foreign_subject=False):
        subject = canonical_identity(outcome.observation)
        if foreign_subject:
            subject = canonical_identity({"foreign": "observation"})
        failure = StandardNodeFailureEvidence(
            self.lock.root_revision,
            StandardNodeFailurePhase.ACCEPT,
            NATIVE_ROOT_RESULT_MISMATCH,
            subject,
            "independent native public results differ",
        )
        return replace(
            self.modeled_node,
            failure_code=failure.code,
            failure_evidence=failure,
            acceptance_identity=None,
            acceptance_evidence=None,
            source_cache_membership=None,
            source_cache_publication_identity=None,
        )

    def test_early_seal_is_acyclic_and_retains_original_native_bytes(self):
        with self.modeled_registered_candidate() as (output, plan, stage, _tree):
            with self.opened() as (owner, _run):

                def seal(outcome):
                    node = self.failed_node(outcome)
                    rejection = owner.seal_native_rejection(
                        outcome,
                        candidate_ordinal=0,
                        prepared_candidate=self.node,
                        source_generation=stage.source_generation,
                        output=output,
                        plan=plan,
                        node_result=node,
                        acceptance_evidence=stage.acceptance_evidence,
                        acceptance_scope="node-native-precheck",
                    )
                    self.assertEqual(
                        rejection.node_lifecycle_result_identity, node.identity
                    )
                    self.assertEqual(
                        node.failure_evidence.subject_identity,
                        canonical_identity(outcome.observation),
                    )
                    self.assertNotEqual(
                        node.failure_evidence.subject_identity, rejection.identity
                    )
                    raw = outcome.native_executable_bytes
                    store = FileSystemCAS(
                        self.ports.object_root / "native-root-continuation-evidence",
                        create=False,
                    )
                    self.assertEqual(
                        store.get_bytes(
                            BlobRef(
                                rejection.native_executable_identity.digest, len(raw)
                            )
                        ),
                        raw,
                    )

                self.with_outcome(owner, seal)

    def test_generic_failure_subject_cannot_be_upgraded_by_matching_code(self):
        with self.modeled_registered_candidate() as (output, plan, stage, _tree):
            with self.opened() as (owner, _run):

                def refuse(outcome):
                    node = self.failed_node(outcome, foreign_subject=True)
                    self.assert_reason(
                        lambda: owner.seal_native_rejection(
                            outcome,
                            candidate_ordinal=0,
                            prepared_candidate=self.node,
                            source_generation=stage.source_generation,
                            output=output,
                            plan=plan,
                            node_result=node,
                            acceptance_evidence=stage.acceptance_evidence,
                            acceptance_scope="node-native-precheck",
                        ),
                        "native_rejection_changed",
                    )

                self.with_outcome(owner, refuse)

    def test_late_seal_preserves_accepted_node_and_package_coordinates(self):
        with self.modeled_registered_candidate() as (output, plan, stage, _tree):
            with self.opened() as (owner, _run):
                before = self.modeled_node.identity
                package = NativeRootPackageBinding(
                    *(
                        canonical_identity({"modeled-package": index})
                        for index in range(6)
                    )
                )

                def seal(outcome):
                    rejection = owner.seal_native_rejection(
                        outcome,
                        candidate_ordinal=0,
                        prepared_candidate=self.node,
                        source_generation=stage.source_generation,
                        output=output,
                        plan=plan,
                        node_result=self.modeled_node,
                        acceptance_evidence=stage.acceptance_evidence,
                        acceptance_scope="packaged-root",
                        packaged_binding=package,
                    )
                    self.assertEqual(rejection.packaged_binding, package)
                    self.assertEqual(self.modeled_node.identity, before)

                self.with_outcome(owner, seal)

    def test_late_replacement_uses_actual_prepared_request_and_workspace(self):
        diagnostic = CandidateRepairDiagnostic(
            self.lock.root_revision,
            StandardNodeFailurePhase.TEST,
            "generated-test.failed",
            "generated source did not pass its public generated test",
            CandidateFailureClassification.RETRYABLE,
            canonical_identity({"original-generated-test": "failed"}),
        )
        replacement = FilesystemStandardCandidateRepairAdapter({}).prepare_repair(
            self.node,
            diagnostic,
            (canonical_identity({"original-attempt": 1}),),
        )
        self.assertNotEqual(
            replacement.request.request.identity, self.node.request.request.identity
        )
        self.assertNotEqual(
            replacement.workspace.allocation_identity,
            self.node.workspace.allocation_identity,
        )
        with self.modeled_registered_candidate(replacement) as (
            output,
            plan,
            stage,
            _tree,
        ):
            with self.opened() as (owner, _run):
                package = NativeRootPackageBinding(
                    *(canonical_identity({"replacement-package": i}) for i in range(6))
                )

                def seal(outcome):
                    rejection = owner.seal_native_rejection(
                        outcome,
                        candidate_ordinal=1,
                        prepared_candidate=replacement,
                        source_generation=stage.source_generation,
                        output=output,
                        plan=plan,
                        node_result=self.modeled_node,
                        acceptance_evidence=stage.acceptance_evidence,
                        acceptance_scope="packaged-root",
                        packaged_binding=package,
                    )
                    self.assertEqual(
                        rejection.bounded_generation_request_identity,
                        replacement.request.request.identity,
                    )
                    self.assertEqual(
                        rejection.workspace_allocation_identity,
                        replacement.workspace.allocation_identity,
                    )
                    self.assertEqual(rejection.packaged_binding, package)

                self.with_outcome(owner, seal)


if __name__ == "__main__":
    unittest.main()
