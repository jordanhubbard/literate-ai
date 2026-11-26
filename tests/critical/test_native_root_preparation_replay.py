"""Real current public projection with modeled closed preparation histories.

No historical path is opened, workspace allocated, execution owner created or
generated command run. These controls establish preparation joins only.
"""

import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthorityReaderError,
)
from literate_ai.adapters.native_root_preparation_replay import (
    NativeRootPreparationReplayError,
    project_current_native_root_preparation,
    verify_closed_native_root_preparation_history,
)
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
)
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectPlanningAdapter,
    FilesystemStandardProjectRuntime,
    _default_generation_budget,
)
from literate_ai.application.component_generation_preparation import (
    ComponentGenerationWorkspaceDescriptor,
)
from literate_ai.application.native_root_repair_prompt import (
    render_native_root_repair_prompt,
)
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_json_bytes,
)
from literate_ai.contracts.native_root_continuation import (
    NativeRootContinuationLedger,
    NativeRootRepairRequest,
)
from tests.critical import test_native_root_continuation_contracts as contracts
from tests.support.fixtures_test_standard_command_projection import _locked_snapshot


class NativeRootPreparationReplayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.component, self.snapshot, _unused = _locked_snapshot(
            self.root, generation_ready=True
        )
        self.provider = "claude"
        self.execution = FilesystemStandardProjectPlanningAdapter().plan_for_coding_cli(
            self.snapshot, coding_cli=self.provider
        )
        self.current = self.project()
        self.records = {}
        self.fixture = contracts.NativeRootContinuationContractTests()
        self.fixture.setUp()
        self.run = replace(
            self.fixture.run,
            component_lock_identity=self.execution.component_lock_identity,
            execution_plan_identity=self.execution.identity,
            root_revision=self.execution.root_revision,
            original_generation_plan_identity=self.current.generation_plan.identity,
            original_recipe_identity=self.current.recipe_identity,
            original_bounded_request_identity=self.current.original.request.identity,
            qualified_dependency_binding_identities=(),
        )
        self.put(self.execution)
        self.put(self.current.generation_plan)
        self.attempts, self.preparations = [], []
        for index in range(3):
            if index == 0:
                request, prompt = (
                    self.current.original.request,
                    self.current.original.prompt,
                )
                incoming = None
            else:
                prior = self.attempts[-1]
                diagnostic = self.diagnostics[-1]
                request, prompt = render_native_root_repair_prompt(
                    self.current.original, tuple(self.attempts), diagnostic
                )
                incoming = NativeRootRepairRequest(
                    self.run.identity,
                    index,
                    self.run.original_recipe_identity,
                    tuple(attempt.identity for attempt in self.attempts),
                    diagnostic.identity,
                    None,
                    request.identity,
                    self.allocation(index),
                    "node-build-test",
                    prior.failure_evidence_identity,
                )
                self.put(incoming)
            diagnostic = replace(
                self.fixture.build_diagnostic,
                component_revision=self.run.root_revision,
                failure_evidence_identity=contracts.ci("failure-" + str(index)),
            )
            if index == 0:
                self.diagnostics = []
            self.diagnostics.append(diagnostic)
            self.put(diagnostic)
            attempt = replace(
                self.fixture.root0,
                run_binding_identity=self.run.identity,
                ordinal=index,
                predecessor_root_attempt_identities=tuple(
                    attempt.identity for attempt in self.attempts
                ),
                incoming_request_kind="initial" if index == 0 else "native-root-repair",
                incoming_request_identity=None
                if incoming is None
                else incoming.identity,
                bounded_generation_request_identity=request.identity,
                workspace_allocation_identity=self.allocation(index),
                source_output_identity=contracts.ci("source-" + str(index)),
                node_lifecycle_result_identity=contracts.ci("node-" + str(index)),
                legacy_node_chain_identity=None,
                legacy_node_attempt_index=None,
                failure_evidence_identity=diagnostic.failure_evidence_identity,
                diagnostic_identity=diagnostic.identity,
            )
            self.put(request)
            self.record(prompt)
            workspace = ComponentGenerationWorkspaceDescriptor(
                self.current.generation_plan.component_revision,
                self.current.generation_plan.identity,
                self.current.generation_plan.generation_key.identity,
                self.allocation(index),
                self.locator(index),
            )
            self.put_json(
                {
                    "schema": "literate-ai/component-generation-workspace@1",
                    "component_revision": workspace.component_revision.uri,
                    "generation_plan_identity": workspace.generation_plan_identity.uri,
                    "generation_key_identity": workspace.generation_key_identity.uri,
                    "allocation_identity": workspace.allocation_identity.uri,
                    "locator": workspace.locator,
                    "workspace": workspace.workspace.value,
                }
            )
            self.attempts.append(attempt)
            self.preparations.append((request, prompt, workspace))
        self.ledger = NativeRootContinuationLedger(
            self.run.identity, tuple(self.attempts), (), "exhausted", None
        )

    def project(self, **changes):
        arguments = dict(
            snapshot=self.snapshot,
            execution_plan=self.execution,
            provider_id=self.provider,
            pipeline_model=None,
            budget_selector=_default_generation_budget,
        )
        arguments.update(changes)
        return project_current_native_root_preparation(**arguments)

    def record(self, payload):
        identity = ContentIdentity.parse_uri(
            "sha256:" + hashlib.sha256(payload).hexdigest()
        )
        self.records[identity] = payload
        return identity

    def put_json(self, document):
        return self.record(canonical_json_bytes(document))

    def put(self, record):
        return self.put_json(record.to_dict())

    def locator(self, index):
        return "Z:\\historical-only\\candidate-" + str(index)

    def allocation(self, index):
        plan = self.current.generation_plan
        return self.put_json(
            {
                "schema": "literate-ai/component-workspace-allocation@1",
                "component_revision": plan.component_revision.uri,
                "generation_plan_identity": plan.identity.uri,
                "locator": self.locator(index),
            }
        )

    def reader(self):
        return QualificationEvidenceReader(
            tuple(sorted(self.records.items(), key=lambda item: item[0].uri)),
            max_bytes=32 * 1024**2,
            max_records=128,
        )

    def verify(self, **changes):
        kwargs = dict(
            reader=self.reader(), current=self.current, run=self.run, ledger=self.ledger
        )
        kwargs.update(changes)
        return verify_closed_native_root_preparation_history(**kwargs)

    def test_current_projection_and_three_preparations_have_no_allocator_or_execution(
        self,
    ):
        before = sorted(path.relative_to(self.root) for path in self.root.rglob("*"))
        with (
            mock.patch.object(
                FilesystemComponentWorkspaceAllocator,
                "allocate",
                side_effect=AssertionError("replay allocated"),
            ) as allocate,
            mock.patch.object(
                FilesystemStandardProjectRuntime,
                "prepare",
                side_effect=AssertionError("replay prepared runtime"),
            ) as runtime,
        ):
            projected = self.project()
            self.assertEqual(projected.original, self.current.original)
            verified = self.verify()
        self.assertEqual(
            tuple((item.request, item.prompt, item.workspace) for item in verified),
            tuple(self.preparations),
        )
        self.assertFalse(hasattr(verified[0], "require_current"))
        self.assertEqual(
            before, sorted(path.relative_to(self.root) for path in self.root.rglob("*"))
        )
        allocate.assert_not_called()
        runtime.assert_not_called()

    def test_wrong_current_execution_plan_refuses_before_authority_projection(self):
        changed = replace(
            self.execution, planner_identity=contracts.ci("foreign-planner")
        )
        with mock.patch.object(
            LockedComponentNodePreparationAdapter, "project"
        ) as project:
            with self.assertRaises(NativeRootPreparationReplayError):
                self.project(execution_plan=changed)
        project.assert_not_called()

    def test_missing_any_plan_prompt_request_or_descriptor_refuses(self):
        identities = [self.execution.identity, self.current.generation_plan.identity]
        for request, _prompt, workspace in self.preparations:
            identities.extend(
                (
                    request.identity,
                    request.prompt_identity,
                    workspace.identity,
                    workspace.allocation_identity,
                )
            )
        for identity in set(identities):
            payload = self.records.pop(identity)
            with (
                self.subTest(identity=identity),
                self.assertRaises(QualificationCaptureError),
            ):
                self.verify()
            self.records[identity] = payload

    def test_original_request_cannot_be_trusted_from_mutated_run_assertion(self):
        with self.assertRaises(NativeRootPreparationReplayError):
            self.verify(
                run=replace(
                    self.run,
                    original_bounded_request_identity=self.preparations[1][0].identity,
                )
            )

    def test_archive_prompt_is_not_adopted_even_with_new_content_identity(self):
        request, _prompt, _workspace = self.preparations[1]
        changed = replace(
            request, prompt_identity=self.record(b"foreign public prompt")
        )
        self.put(changed)
        incoming = NativeRootRepairRequest.from_dict(
            self.reader().read_json(self.attempts[1].incoming_request_identity)
        )
        incoming = replace(
            incoming, bounded_generation_request_identity=changed.identity
        )
        self.put(incoming)
        second = replace(
            self.attempts[1],
            bounded_generation_request_identity=changed.identity,
            incoming_request_identity=incoming.identity,
        )
        ledger = NativeRootContinuationLedger(
            self.run.identity, (self.attempts[0], second), (), "pending", None
        )
        # All affected metadata is rehashed consistently. The independently
        # rendered public request, rather than the archive's new IDs, must win.
        with self.assertRaisesRegex(
            NativeRootPreparationReplayError, "request_changed"
        ):
            self.verify(ledger=ledger)

    def test_changed_trusted_budget_and_changed_current_source_refuse(self):
        old = _default_generation_budget()
        with self.assertRaises(NativeRootPreparationReplayError):
            self.verify(
                current=replace(
                    self.current,
                    _budget_selector=lambda: replace(
                        old, max_prompt_bytes=old.max_prompt_bytes + 1
                    ),
                )
            )
        document = self.component / "component.md"
        document.write_bytes(
            document.read_bytes() + b"\nchanged current public source\n"
        )
        with self.assertRaises(LockedGenerationAuthorityReaderError) as raised:
            self.verify()
        self.assertEqual(raised.exception.code, "component_lock.stale")

    def test_native_replacement_requires_exact_rejection_and_fixed_public_prompt(self):
        original = self.attempts[0]
        rejection = replace(
            self.fixture.rejection,
            run_binding_identity=self.run.identity,
            component_revision=self.run.root_revision,
            candidate_ordinal=0,
            bounded_generation_request_identity=original.bounded_generation_request_identity,
            source_output_identity=original.source_output_identity,
            workspace_allocation_identity=original.workspace_allocation_identity,
            node_lifecycle_result_identity=original.node_lifecycle_result_identity,
            acceptance_scope="node-native-precheck",
            packaged_binding=None,
        )
        diagnostic = replace(
            self.fixture.native_diagnostic,
            component_revision=self.run.root_revision,
            acceptance_rejection_identity=rejection.identity,
        )
        first = replace(
            original,
            outcome="native-precheck-rejected",
            failure_evidence_identity=rejection.identity,
            diagnostic_identity=diagnostic.identity,
        )
        request, prompt = render_native_root_repair_prompt(
            self.current.original, (first,), diagnostic
        )
        incoming = NativeRootRepairRequest(
            self.run.identity,
            1,
            self.run.original_recipe_identity,
            (first.identity,),
            diagnostic.identity,
            rejection.identity,
            request.identity,
            self.attempts[1].workspace_allocation_identity,
            "native-acceptance",
            rejection.identity,
        )
        second = replace(
            self.attempts[1],
            predecessor_root_attempt_identities=(first.identity,),
            incoming_request_identity=incoming.identity,
            bounded_generation_request_identity=request.identity,
        )
        ledger = NativeRootContinuationLedger(
            self.run.identity, (first, second), (), "pending", None
        )
        for record in (rejection, diagnostic, incoming, request):
            self.put(record)
        self.record(prompt)
        verified = self.verify(ledger=ledger)
        self.assertEqual(verified[1].prompt, prompt)
        self.records.pop(rejection.identity)
        with self.assertRaises(QualificationCaptureError):
            self.verify(ledger=ledger)
