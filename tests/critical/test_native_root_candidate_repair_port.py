"""Root preparation custody using real prepared nodes and local empty workspaces.

Native observations here are symbolic typed records. No native witness is minted
or consumed, no generated source executes and no qualification is claimed.
"""

import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters.candidate_repair import (
    AllocatedNativeRootRepairPreparationError,
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.application import native_root_run as live
from literate_ai.contracts.executable_components import (
    CandidateFailureClassification,
    CandidateRepairDiagnostic,
)
from literate_ai.contracts.executable_components.context import (
    deterministic_token_estimate,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NATIVE_ROOT_REPAIR_MESSAGE,
    NATIVE_ROOT_RESULT_MISMATCH,
    NativeRootAcceptanceRejection,
    NativeRootCandidateAttempt,
    NativeRootPackageBinding,
    NativeRootQualifiedDependencyBinding,
    NativeRootRepairDiagnostic,
    NativeRootRunBinding,
    NativeRootRunPolicy,
)
from literate_ai.contracts.standard_lifecycle_membership import StandardNodeFailurePhase
from tests.support import fixtures_test_source_generation_scheduling as fixture


def ci(label):
    return canonical_identity({"controlled-root-preparation": label})


class NativeRootCandidateRepairPortTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture._PreparedFixture()
        self.addCleanup(self.fixture.close)
        self.original = next(
            n
            for n in self.fixture.nodes
            if n.plan.component_revision == self.fixture.execution.root_revision
        )
        self.canary = "PRIVATE_ORACLE_AND_OLD_GENERATED_SOURCE_b3e5d090"
        self.old_file = Path(self.original.workspace.locator) / "private-old-source.txt"
        self.old_file.write_text(self.canary)
        self.adapter = FilesystemStandardCandidateRepairAdapter(
            {self.original.plan.component_revision.uri: self.canary}
        )
        self.authority = ci("approved-project-authority")
        self.dependencies = ()

    def owner(self, **arguments):
        return live.open_native_root_run(
            NativeRootRunPolicy(120, 3),
            project_identity=ci("project-definition"),
            framework_distribution_identity=ci("framework"),
            lifecycle_policy_identity=ci("lifecycle-policy"),
            require_current=lambda: None,
            **arguments,
        )

    def binding(self, owner):
        return NativeRootRunBinding(
            run_nonce=owner.deadline.run_nonce,
            project_definition_identity=owner.bindings[0],
            project_authority_identity=self.authority,
            root_revision=self.original.plan.component_revision,
            component_lock_identity=self.original.plan.component_graph_identity,
            execution_plan_identity=self.fixture.execution.identity,
            original_recipe_identity=ContentIdentity.parse_uri(
                self.original.recipe.identity
            ),
            original_generation_plan_identity=self.original.plan.identity,
            original_bounded_request_identity=self.original.request.request.identity,
            framework_distribution_identity=owner.bindings[1],
            lifecycle_policy_identity=owner.bindings[2],
            target_profile_identity=ci("target"),
            verifier_profile_identity=ci("verifier"),
            oracle_identity=ci("oracle"),
            original_deadline_identity=owner.deadline.identity,
            qualified_dependency_binding_identities=tuple(
                sorted((d.identity for d in self.dependencies), key=lambda v: v.uri)
            ),
            candidate_limit=3,
        )

    def build_failure(self):
        return CandidateRepairDiagnostic(
            self.original.plan.component_revision,
            StandardNodeFailurePhase.BUILD,
            "builder.generated-source-rejected",
            "generated build failed",
            CandidateFailureClassification.RETRYABLE,
            ci("actual-build-failure"),
        )

    def native_failure(self, run, prepared=None, predecessors=(), incoming=None):
        prepared = self.original if prepared is None else prepared
        ordinal = len(predecessors)
        package = NativeRootPackageBinding(
            *(ci(f"package-{ordinal}-{n}") for n in range(6))
        )
        rejection = NativeRootAcceptanceRejection(
            run.identity,
            ordinal,
            run.root_revision,
            prepared.request.request.identity,
            ci(f"source-output-{ordinal}"),
            ci(f"source-tree-{ordinal}"),
            prepared.workspace.allocation_identity,
            ci(f"node-result-{ordinal}"),
            ci(f"build-plan-{ordinal}"),
            ci(f"build-result-{ordinal}"),
            ci(f"export-{ordinal}"),
            run.verifier_profile_identity,
            run.oracle_identity,
            ci(f"native-execution-{ordinal}"),
            ci(f"native-program-{ordinal}"),
            (ci("tool-observation"),),
            run.target_profile_identity,
            run.original_deadline_identity,
            "packaged-root",
            package,
            "result-values-differ",
            NATIVE_ROOT_RESULT_MISMATCH,
        )
        diagnostic = NativeRootRepairDiagnostic(
            run.root_revision,
            rejection.identity,
            NATIVE_ROOT_RESULT_MISMATCH,
            "retryable",
            NATIVE_ROOT_REPAIR_MESSAGE,
        )
        attempt = self.attempt(
            run,
            prepared,
            predecessors,
            incoming,
            "package-rejected",
            rejection.identity,
            diagnostic.identity,
            package,
        )
        return attempt, diagnostic, rejection

    def attempt(
        self,
        run,
        prepared,
        predecessors,
        incoming,
        outcome,
        failure,
        diagnostic,
        package=None,
    ):
        return NativeRootCandidateAttempt(
            run.identity,
            len(predecessors),
            tuple(p.identity for p in predecessors),
            "initial" if not predecessors else "native-root-repair",
            None if incoming is None else incoming.identity,
            prepared.request.request.identity,
            prepared.workspace.allocation_identity,
            ci(f"source-output-{len(predecessors)}"),
            ci(f"node-result-{len(predecessors)}"),
            None,
            None,
            outcome,
            failure,
            diagnostic,
            "retryable",
            None,
            package,
        )

    def prepare(self, owner, run, predecessors, diagnostic, rejection=None, **changes):
        arguments = dict(
            live_run=owner,
            project_authority_identity=self.authority,
            execution_plan_identity=self.fixture.execution.identity,
            rejection=rejection,
            qualified_dependencies=self.dependencies,
        )
        arguments.update(changes)
        return self.adapter.prepare_root_repair(
            self.original, run, predecessors, diagnostic, **arguments
        )

    def test_native_preparation_keeps_budget_recipe_and_private_feedback_boundary(self):
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            before = first.to_dict()
            prepared, request = self.prepare(
                owner, run, (first,), diagnostic, rejection
            )
            self.assertEqual(first.to_dict(), before)
            self.assertIs(prepared.plan, self.original.plan)
            self.assertIs(prepared.recipe, self.original.recipe)
            self.assertIs(
                prepared.request.request.budget, self.original.request.request.budget
            )
            self.assertIs(
                prepared.request.request.budget_decision,
                self.original.request.request.budget_decision,
            )
            self.assertNotEqual(
                prepared.request.request.identity,
                self.original.request.request.identity,
            )
            self.assertNotEqual(
                prepared.workspace.allocation_identity,
                self.original.workspace.allocation_identity,
            )
            self.assertEqual(
                Path(prepared.workspace.locator).parent,
                Path(self.original.workspace.locator).parent,
            )
            self.assertEqual(list(Path(prepared.workspace.locator).iterdir()), [])
            self.assertEqual(self.old_file.read_text(), self.canary)
            self.assertNotIn(self.canary.encode(), prepared.request.prompt)
            self.assertIn(NATIVE_ROOT_REPAIR_MESSAGE.encode(), prepared.request.prompt)
            self.assertTrue(
                prepared.request.prompt.startswith(self.original.request.prompt)
            )
            self.assertEqual(request.candidate_ordinal, 1)
            self.assertEqual(
                request.predecessor_root_attempt_identities, (first.identity,)
            )
            self.assertEqual(request.cause_kind, "native-acceptance")
            request.require_records(run, (first,), diagnostic, rejection=rejection)

    def test_build_then_native_uses_remaining_last_candidate_without_legacy_chain(self):
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            build = self.build_failure()
            first = self.attempt(
                run,
                self.original,
                (),
                None,
                "node-rejected",
                build.failure_evidence_identity,
                build.identity,
            )
            middle_prepared, incoming = self.prepare(owner, run, (first,), build)
            second, diagnostic, rejection = self.native_failure(
                run, middle_prepared, (first,), incoming
            )
            prepared, request = self.prepare(
                owner, run, (first, second), diagnostic, rejection
            )
            self.assertEqual(request.candidate_ordinal, 2)
            self.assertNotEqual(
                prepared.request.request.identity,
                middle_prepared.request.request.identity,
            )
            self.assertNotEqual(
                prepared.workspace.allocation_identity,
                middle_prepared.workspace.allocation_identity,
            )
            third = self.attempt(
                run,
                prepared,
                (first, second),
                request,
                "node-rejected",
                build.failure_evidence_identity,
                build.identity,
            )
            with mock.patch(
                "literate_ai.adapters.candidate_repair.FilesystemComponentWorkspaceAllocator.allocate"
            ) as allocate:
                with self.assertRaises(ValueError):
                    self.prepare(owner, run, (first, second, third), build)
                allocate.assert_not_called()

    def test_other_run_project_recipe_plan_and_request_refuse_before_allocation(self):
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            fields = (
                "project_definition_identity",
                "project_authority_identity",
                "framework_distribution_identity",
                "lifecycle_policy_identity",
                "component_lock_identity",
                "execution_plan_identity",
                "original_recipe_identity",
                "original_generation_plan_identity",
                "original_bounded_request_identity",
                "original_deadline_identity",
                "root_revision",
            )
            for name in fields:
                with (
                    self.subTest(field=name),
                    mock.patch(
                        "literate_ai.adapters.candidate_repair.FilesystemComponentWorkspaceAllocator.allocate"
                    ) as allocate,
                ):
                    with self.assertRaises(ValueError):
                        self.prepare(
                            owner,
                            replace(run, **{name: ci("foreign-" + name)}),
                            (first,),
                            diagnostic,
                            rejection,
                        )
                    allocate.assert_not_called()

    def test_wrong_ambient_owner_and_projection_never_allocate(self):
        with self.owner() as owner, self.owner() as other:
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            with mock.patch(
                "literate_ai.adapters.candidate_repair.FilesystemComponentWorkspaceAllocator.allocate"
            ) as allocate:
                with self.assertRaises(ValueError):
                    self.prepare(owner, run, (first,), diagnostic, rejection)
                with (
                    live.activate_native_root_run(other),
                    self.assertRaises(ValueError),
                ):
                    self.prepare(owner, run, (first,), diagnostic, rejection)
                with self.assertRaises(TypeError):
                    self.prepare(owner.deadline, run, (first,), diagnostic, rejection)
                allocate.assert_not_called()

    def test_actual_native_candidate_coordinates_and_diagnostic_must_match(self):
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            for name in (
                "source_output_identity",
                "node_lifecycle_result_identity",
                "workspace_allocation_identity",
                "bounded_generation_request_identity",
            ):
                changed = replace(rejection, **{name: ci("other-" + name)})
                changed_diag = replace(
                    diagnostic, acceptance_rejection_identity=changed.identity
                )
                changed_first = replace(
                    first,
                    failure_evidence_identity=changed.identity,
                    diagnostic_identity=changed_diag.identity,
                )
                with (
                    self.subTest(field=name),
                    mock.patch(
                        "literate_ai.adapters.candidate_repair.FilesystemComponentWorkspaceAllocator.allocate"
                    ) as allocate,
                ):
                    with self.assertRaises(ValueError):
                        self.prepare(
                            owner, run, (changed_first,), changed_diag, changed
                        )
                    allocate.assert_not_called()

    def test_nonretryable_or_reordered_prefix_never_allocates(self):
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            terminal = replace(first, retryability="terminal", diagnostic_identity=None)
            for predecessors in ((), (terminal,), (first, first)):
                with (
                    self.subTest(prefix=predecessors),
                    mock.patch(
                        "literate_ai.adapters.candidate_repair.FilesystemComponentWorkspaceAllocator.allocate"
                    ) as allocate,
                ):
                    with self.assertRaises(ValueError):
                        self.prepare(owner, run, predecessors, diagnostic, rejection)
                    allocate.assert_not_called()

    def test_true_build_test_only_and_native_diagnostic_is_never_legacy_cast(self):
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            build = self.build_failure()
            for changed in (
                replace(build, classification=CandidateFailureClassification.TERMINAL),
                replace(
                    build,
                    phase=StandardNodeFailurePhase.TEST,
                    code="not-an-admitted-build-test-failure",
                ),
            ):
                first = self.attempt(
                    run,
                    self.original,
                    (),
                    None,
                    "node-rejected",
                    changed.failure_evidence_identity,
                    changed.identity,
                )
                with mock.patch(
                    "literate_ai.adapters.candidate_repair.FilesystemComponentWorkspaceAllocator.allocate"
                ) as allocate:
                    with self.assertRaises(ValueError):
                        self.prepare(owner, run, (first,), changed)
                    allocate.assert_not_called()
            first, diagnostic, rejection = self.native_failure(run)
            with self.assertRaises(ValueError):
                CandidateRepairDiagnostic.from_dict(diagnostic.to_dict())
            with self.assertRaises(TypeError):
                self.prepare(owner, run, (first,), diagnostic)

    def test_actual_held_dependency_records_are_required_and_must_match(self):
        dependency = NativeRootQualifiedDependencyBinding(
            ci("provider"),
            ci("acceptance"),
            ci("product"),
            ci("provenance"),
            (ci("export"),),
            ci("target"),
            (ci("tool"),),
            (),
        )
        self.dependencies = (dependency,)
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            with mock.patch(
                "literate_ai.adapters.candidate_repair.FilesystemComponentWorkspaceAllocator.allocate"
            ) as allocate:
                with self.assertRaises(ValueError):
                    self.prepare(
                        owner,
                        run,
                        (first,),
                        diagnostic,
                        rejection,
                        qualified_dependencies=(),
                    )
                allocate.assert_not_called()
            self.prepare(owner, run, (first,), diagnostic, rejection)

    def test_bounded_feedback_cannot_expand_original_prompt_budget(self):
        old = self.original.request.request
        budget = replace(
            old.budget, max_prompt_bytes=len(self.original.request.prompt) + 1
        )
        decision = replace(old.budget_decision, budget_identity=budget.identity)
        request = replace(
            old,
            budget=budget,
            budget_decision=decision,
            complexity_decision_identity=decision.identity,
        )
        self.original = replace(
            self.original, request=replace(self.original.request, request=request)
        )
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            with mock.patch(
                "literate_ai.adapters.candidate_repair.FilesystemComponentWorkspaceAllocator.allocate"
            ) as allocate:
                with self.assertRaisesRegex(ValueError, "original prompt budget"):
                    self.prepare(owner, run, (first,), diagnostic, rejection)
                allocate.assert_not_called()

    def test_full_original_prompt_framing_counts_against_retained_token_cap(self):
        # A valid public preparation path renders additional repair framing
        # while retaining the original context manifest. This does not claim
        # that the final root controller restarts an already repaired budget.
        public_feedback = replace(
            self.build_failure(),
            sanitized_text="controlled public build diagnostic detail; " * 100,
        )
        self.original = self.adapter.prepare_repair(
            self.original, public_feedback, (ci("prior-public-repair"),)
        )
        old = self.original.request.request
        full_original_tokens = deterministic_token_estimate(
            len(self.original.request.prompt)
        )
        self.assertGreater(
            full_original_tokens - old.context_manifest.estimated_tokens, 1000
        )
        budget = replace(old.budget, max_estimated_tokens=full_original_tokens)
        decision = replace(old.budget_decision, budget_identity=budget.identity)
        request = replace(
            old,
            budget=budget,
            budget_decision=decision,
            complexity_decision_identity=decision.identity,
        )
        self.original = replace(
            self.original, request=replace(self.original.request, request=request)
        )
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            from literate_ai.adapters.generation_preparation import (
                FilesystemComponentWorkspaceAllocator,
            )

            allocate = FilesystemComponentWorkspaceAllocator.allocate
            with mock.patch.object(
                FilesystemComponentWorkspaceAllocator,
                "allocate",
                autospec=True,
                side_effect=allocate,
            ) as allocated:
                with self.assertRaisesRegex(ValueError, "original prompt budget"):
                    self.prepare(owner, run, (first,), diagnostic, rejection)
                allocated.assert_not_called()

    def test_closure_after_real_allocation_retains_actual_records_for_controller(self):
        from literate_ai.adapters.generation_preparation import (
            FilesystemComponentWorkspaceAllocator,
        )

        allocate = FilesystemComponentWorkspaceAllocator.allocate
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            original_record = first.to_dict()

            allocated = []

            def closed(allocator, plan):
                workspace = allocate(allocator, plan)
                allocated.append(workspace)
                owner.close()
                return workspace

            with mock.patch.object(
                FilesystemComponentWorkspaceAllocator, "allocate", closed
            ):
                with self.assertRaises(
                    AllocatedNativeRootRepairPreparationError
                ) as caught:
                    self.prepare(owner, run, (first,), diagnostic, rejection)
            error = caught.exception
            evidence = error.native_root_repair_allocation
            self.assertIsInstance(error.original_error, live.NativeRootRunError)
            self.assertIs(error.__cause__, error.original_error)
            self.assertEqual(error.code, "native_root_run.closed")
            self.assertIs(evidence.workspace, allocated[0])
            self.assertIs(evidence.prepared.workspace, allocated[0])
            self.assertIs(evidence.prepared.request, evidence.generation_request)
            self.assertEqual(
                evidence.repair_request.workspace_allocation_identity,
                allocated[0].allocation_identity,
            )
            self.assertEqual(
                evidence.repair_request.bounded_generation_request_identity,
                evidence.generation_request.request.identity,
            )
            self.assertEqual(first.to_dict(), original_record)

    def test_interrupt_preserves_exact_object_and_actual_allocation_evidence(self):
        from literate_ai.adapters import candidate_repair as module

        validate = module.validate_prepared_component_generation_node
        interruption = KeyboardInterrupt("controlled post-allocation interrupt")
        calls = []

        def checked(prepared):
            calls.append(prepared)
            if len(calls) == 2:
                raise interruption
            return validate(prepared)

        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            with mock.patch.object(
                module,
                "validate_prepared_component_generation_node",
                side_effect=checked,
            ):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    self.prepare(owner, run, (first,), diagnostic, rejection)
            self.assertIs(caught.exception, interruption)
            evidence = interruption.native_root_repair_allocation
            self.assertIs(evidence.prepared, calls[1])
            self.assertIs(evidence.generation_request, calls[1].request)
            self.assertEqual(
                evidence.repair_request.workspace_allocation_identity,
                evidence.workspace.allocation_identity,
            )
            self.assertNotEqual(
                evidence.workspace.allocation_identity,
                self.original.workspace.allocation_identity,
            )
            self.assertTrue(Path(evidence.workspace.locator).is_dir())
            owner.require_current()

    def test_constructor_failure_retains_raw_allocation_without_fabricated_records(
        self,
    ):
        from literate_ai.adapters import candidate_repair as module

        constructor_error = ValueError("controlled request constructor refusal")
        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            with mock.patch.object(
                module, "NativeRootRepairRequest", side_effect=constructor_error
            ):
                with self.assertRaises(
                    AllocatedNativeRootRepairPreparationError
                ) as caught:
                    self.prepare(owner, run, (first,), diagnostic, rejection)
            evidence = caught.exception.native_root_repair_allocation
            self.assertIsNone(evidence.prepared)
            self.assertIsNone(evidence.repair_request)
            self.assertTrue(Path(evidence.workspace.locator).is_dir())
            self.assertNotEqual(
                evidence.generation_request.request.identity,
                self.original.request.request.identity,
            )
            self.assertIs(caught.exception.original_error, constructor_error)
            self.assertIs(caught.exception.__cause__, constructor_error)

    def test_returned_reused_allocation_is_refused_with_raw_evidence(self):
        from literate_ai.adapters.generation_preparation import (
            FilesystemComponentWorkspaceAllocator,
        )

        allocate = FilesystemComponentWorkspaceAllocator.allocate
        raw = []

        def substituted(allocator, plan):
            actual = allocate(allocator, plan)
            actual = replace(
                actual, allocation_identity=self.original.workspace.allocation_identity
            )
            raw.append(actual)
            return actual

        with self.owner() as owner, live.activate_native_root_run(owner):
            run = self.binding(owner)
            first, diagnostic, rejection = self.native_failure(run)
            with mock.patch.object(
                FilesystemComponentWorkspaceAllocator, "allocate", substituted
            ):
                with self.assertRaises(
                    AllocatedNativeRootRepairPreparationError
                ) as caught:
                    self.prepare(owner, run, (first,), diagnostic, rejection)
            self.assertIs(
                caught.exception.native_root_repair_allocation.workspace, raw[0]
            )
            self.assertIn("fresh workspace", str(caught.exception))
