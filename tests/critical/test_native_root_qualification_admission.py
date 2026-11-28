"""Real manifest/run custody around modeled qualification composition.

Standard execution and capture protocols are controlled. These tests execute no
model/generated/native code and establish no qualification or release evidence.
"""

import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_run_admission, qualification
from literate_ai.adapters.native_root_run_admission import admit_native_root_command
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    current_native_root_run,
)
from literate_ai.contracts.authored_qualification_requests import (
    AuthoredQualificationLifecycleRequest,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.qualification_origins import AuthoredQualificationOrigin
from literate_ai.projects import (
    ProjectError,
    load_project,
    serialize_project_configuration,
)
from literate_ai.source_to_specification.qualification_lifecycle import (
    QualificationLifecycleRequest,
    QualificationWorkspaceAllocation,
)
from tests.critical import test_native_root_run_admission as admission_fixture
from tests.support import fixtures_test_qualification_lifecycle_runner as results
from tests.support import fixtures_test_standard_rebuild_adapter as rebuild_fixture


class NativeRootQualificationAdmissionTests(unittest.TestCase):
    setUp = admission_fixture.NativeRootRunAdmissionTests.setUp

    def compose(self, *, capture=True):
        model = rebuild_fixture.FilesystemStandardRebuildAdapterTests()
        model.setUp()
        self.addCleanup(model.doCleanups)
        lifecycle = results._lifecycle("modeled-clean-run")
        receipt = results._receipt(lifecycle)
        snapshot = model.prepared.locked_authority_snapshot
        snapshot.authority.lock.root_revision = lifecycle.node_results[
            0
        ].component_revision
        self.events = []
        self.owners = []
        self.port = object.__new__(
            qualification.FilesystemStandardQualificationLifecyclePort
        )
        self.port.project, self.port.binding = self.project, self.binding
        self.port.prepared = model.prepared
        self.port.invalidation = model.invalidation
        self.port.authored_oracles = self.port.authored_plan = None
        self.port.acceptance_oracle = object()
        self.port.max_parallelism = 1
        self.port.pipeline_model = None
        self.port.retain_library_products = True
        self.port.run_roots, self.port.generated_roots = {}, {}
        self.port.root_generated_roots, self.port.product_sources = {}, {}
        self.port.workspaces = SimpleNamespace(resolve=self.resolve_workspace)
        self.port.require_current_authority = mock.Mock(
            side_effect=lambda: self.observe("authority")
        )
        ports = SimpleNamespace(retain_evidence_with=mock.Mock())
        plan = SimpleNamespace(
            identity=lifecycle.execution_plan_identity,
            generation_plans=tuple(
                SimpleNamespace(component_revision=node.component_revision)
                for node in lifecycle.node_results
            ),
        )
        self.adapter = SimpleNamespace(
            runtime=SimpleNamespace(
                lifecycle_ports=ports,
                application=SimpleNamespace(lifecycle=SimpleNamespace(indexer=ports)),
                source_trees=SimpleNamespace(
                    resolve=lambda _identity: self.root / "modeled-source"
                ),
                node_preparation=SimpleNamespace(
                    project=lambda *_: SimpleNamespace(recipe=object())
                ),
            ),
            rebuild=self.rebuild,
        )
        self.rebuilt = SimpleNamespace(
            execution=SimpleNamespace(
                lifecycle=lifecycle, planned=SimpleNamespace(execution_plan=plan)
            ),
            receipt=receipt,
            lifecycle_request_identity=results.identity("request"),
            lifecycle_invocation_identity=results.identity("invocation"),
        )
        self.capture_action = None
        self.port.evidence_recorder = (
            None
            if not capture
            else SimpleNamespace(
                remember_json=lambda *_: self.observe("receipt capture"),
                entries=(),
                max_bytes=1024**2,
                max_records=100,
            )
        )
        return snapshot

    def observe(self, phase):
        owner = current_native_root_run()
        self.events.append((phase, owner))
        return owner

    def resolve_workspace(self, _identity):
        self.observe("workspace preparation")
        return self.root

    def assemble(self, **kwargs):
        owner = self.observe("assembly")
        self.assertIs(kwargs.get("live_run"), owner)
        if (
            getattr(self.port.project.definition, "native_root_run_policy", None)
            is None
        ):
            self.assertNotIn("live_run", kwargs)
        self.owners.append(owner)
        return self.adapter

    def rebuild(self, request):
        self.assertIs(request.live_run, self.owners[-1])
        self.assertIs(self.observe("rebuild"), request.live_run)
        return self.rebuilt

    def capture(self, *_args, **_kwargs):
        self.observe("source capture")
        if self.capture_action is not None:
            self.capture_action()

    def patches(self):
        stack = ExitStack()
        stack.enter_context(
            mock.patch.object(
                qualification,
                "assemble_filesystem_standard_rebuild_adapter",
                side_effect=self.assemble,
            )
        )
        stack.enter_context(
            mock.patch.object(
                qualification,
                "capture_lifecycle_records",
                side_effect=lambda *_: self.observe("lifecycle capture"),
            )
        )
        stack.enter_context(
            mock.patch.object(
                qualification,
                "capture_qualification_source_records",
                side_effect=self.capture,
            )
        )
        stack.enter_context(
            mock.patch.object(qualification, "verify_qualification_generated_suite")
        )
        stack.enter_context(
            mock.patch.object(qualification, "QualificationEvidenceReader")
        )
        stack.enter_context(mock.patch.object(qualification, "FileSystemCAS"))
        return stack

    def request(self, label):
        identity = canonical_identity({"clean-run": label})
        return QualificationLifecycleRequest(
            identity,
            results.identity("target"),
            self.port.prepared.locked_authority_snapshot.authority.lock.identity,
            results.identity("specification"),
            results.identity("original-source"),
            results.identity("input-audit"),
            results.identity("promotion"),
            QualificationWorkspaceAllocation(
                results.identity("workspace-" + label), True
            ),
        )

    def test_modeled_controller_audit_captures_history_inside_same_original_owner(self):
        from literate_ai.adapters import native_root_capture
        from literate_ai.contracts.native_root_continuation import (
            NativeRootExecutionResult,
        )

        self.compose()
        lifecycle = self.rebuilt.execution.lifecycle
        audit = NativeRootExecutionResult(
            results.identity("modeled-run-binding"),
            results.identity("modeled-ledger"),
            lifecycle.identity,
            results.identity("modeled-closure"),
            "accepted",
        )
        # This existing fixture deliberately constructs a partial lifecycle.
        # Attach only the modeled nonserialized controller metadata used here.
        object.__setattr__(lifecycle, "native_root_execution", audit)
        observed = []

        def capture_history(actual, recorder, *, cas):
            self.assertIs(actual, lifecycle)
            self.assertIs(recorder, self.port.evidence_recorder)
            self.assertIsNotNone(cas)
            self.assertIs(current_native_root_run(), self.owners[-1])
            observed.append(actual.native_root_execution)
            return ()

        with (
            self.patches(),
            mock.patch.object(
                native_root_capture,
                "capture_native_root_source_history",
                side_effect=capture_history,
            ),
        ):
            execution = self.port.execute(self.request("history-forwarding"))
        self.assertIs(execution.lifecycle, lifecycle)
        self.assertEqual(observed, [audit])
        self.assertIsNone(current_native_root_run())

    def test_two_clean_requests_have_distinct_owners_through_assembly_and_capture(
        self,
    ):
        self.compose()
        with self.patches():
            for label in ("first", "second"):
                start = len(self.events)
                result = self.port.execute(self.request(label))
                self.assertIs(result.lifecycle, self.rebuilt.execution.lifecycle)
                owner = self.owners[-1]
                self.assertIsNotNone(owner)
                selected = [
                    (phase, observed)
                    for phase, observed in self.events[start:]
                    if phase != "authority"
                ]
                self.assertIn("source capture", [phase for phase, _ in selected])
                self.assertTrue(all(observed is owner for _, observed in selected))
                with self.assertRaises(NativeRootRunError):
                    owner.require_current()
                self.assertIsNone(current_native_root_run())
        self.assertIsNot(self.owners[0], self.owners[1])
        self.assertNotEqual(
            self.owners[0].deadline.run_nonce, self.owners[1].deadline.run_nonce
        )

    def test_closed_owner_during_capture_refuses_without_retaining_product(self):
        self.compose()
        self.capture_action = lambda: current_native_root_run().close()
        request = self.request("closed")
        with (
            self.patches(),
            self.assertRaises(qualification.FilesystemQualificationError) as caught,
        ):
            self.port.execute(request)
        self.assertEqual(caught.exception.code, "native_root_run.closed")
        self.assertIsInstance(caught.exception.__cause__, NativeRootRunError)
        self.assertNotIn(request.run_identity.uri, self.port.product_sources)
        self.assertIsNone(current_native_root_run())

    def test_changed_original_manifest_during_capture_refuses_without_new_owner(self):
        self.compose()
        self.capture_action = lambda: self.path.write_bytes(
            serialize_project_configuration(replace(self.definition, version="1.0.1"))
        )
        with (
            self.patches(),
            self.assertRaises(
                (qualification.FilesystemQualificationError, ProjectError)
            ),
        ):
            self.port.execute(self.request("changed"))
        self.assertEqual(len(self.owners), 1)
        self.assertFalse(self.port.product_sources)
        self.assertIsNone(current_native_root_run())

    def test_existing_outer_owner_cannot_be_replaced_by_a_clean_run_owner(self):
        self.compose()
        with admit_native_root_command(self.project, self.binding) as original:
            with (
                self.patches(),
                self.assertRaises(qualification.FilesystemQualificationError) as caught,
            ):
                self.port.execute(self.request("nested"))
            self.assertEqual(caught.exception.code, "native_root_run.owner_mismatch")
            self.assertIsInstance(caught.exception.__cause__, NativeRootRunError)
            self.assertIs(current_native_root_run(), original)
            self.assertEqual(self.owners, [])

    def test_authored_specs_keep_original_owner_through_namespace_and_capture(
        self,
    ):
        self.compose()
        lock = self.port.prepared.locked_authority_snapshot.authority.lock
        origin = AuthoredQualificationOrigin(
            self.project.definition.identity,
            results.identity("authored-authority"),
            lock.identity,
            results.identity("authored-inputs"),
        )

        @contextmanager
        def held(phase):
            owner = self.observe(phase + " enter")
            self.assertIsNotNone(owner)
            yield
            self.assertIs(self.observe(phase + " exit"), owner)

        self.port.authored_plan_identity = results.identity("authored-plan")
        self.port.authored_oracles = SimpleNamespace(
            authority=SimpleNamespace(origin=origin),
            identity=results.identity("authored-oracles"),
            capture_current=lambda: held("authored oracle"),
        )
        self.port.authored_plan = SimpleNamespace(
            plan=SimpleNamespace(
                execution_plan=self.rebuilt.execution.planned.execution_plan
            )
        )
        self.port.workspaces.capture_authored_run = lambda *_: held(
            "authored namespace"
        )
        request = AuthoredQualificationLifecycleRequest(
            origin,
            self.port.authored_plan_identity,
            self.port.authored_oracles.identity,
            results.identity("authored-clean-run"),
            results.identity("authored-workspace"),
        )
        with self.patches():
            self.port.execute(request)
        owner = self.owners[0]
        for phase, observed in self.events:
            if phase != "authority":
                self.assertIs(observed, owner)
        self.assertIn("authored namespace exit", [phase for phase, _ in self.events])
        self.assertIsNone(current_native_root_run())

    def test_no_policy_preserves_original_private_and_assembly_request_call_shapes(
        self,
    ):
        self.compose()
        self.path.write_bytes(
            serialize_project_configuration(
                replace(self.definition, native_root_run_policy=None)
            )
        )
        self.port.project = load_project(self.root)
        original = qualification.FilesystemStandardRebuildRequest
        with (
            self.patches(),
            mock.patch.object(
                qualification, "FilesystemStandardRebuildRequest", wraps=original
            ) as rebuild_request,
        ):
            self.port.execute(self.request("legacy"))
        self.assertEqual(self.owners, [None])
        self.assertNotIn("live_run", rebuild_request.call_args.kwargs)
        with mock.patch.object(
            self.port, "_execute_current", return_value="legacy-result"
        ) as execute:
            request = self.request("legacy-shape")
            self.assertEqual(self.port.execute(request), "legacy-result")
            execute.assert_called_once_with(request)
        self.assertEqual(self.port.require_current_authority.call_count, 4)

    def test_absent_policy_attribute_preserves_legacy_public_call_shape(self):
        self.compose()
        self.port.project = SimpleNamespace(definition=SimpleNamespace())
        request = self.request("absent-attribute")
        with (
            mock.patch.object(
                native_root_run_admission, "admit_native_root_command"
            ) as admit,
            mock.patch.object(
                self.port, "_execute_current", return_value="legacy"
            ) as execute,
        ):
            self.assertEqual(self.port.execute(request), "legacy")
        admit.assert_not_called()
        execute.assert_called_once_with(request)

    def test_public_error_boundary_preserves_native_code_and_exact_cause(self):
        self.compose()
        original = NativeRootRunError("expired")
        with (
            mock.patch.object(self.port, "_execute_current", side_effect=original),
            self.assertRaises(qualification.FilesystemQualificationError) as caught,
        ):
            self.port.execute(self.request("public-error"))
        self.assertEqual(caught.exception.code, original.code)
        self.assertEqual(caught.exception.message, str(original))
        self.assertIs(caught.exception.__cause__, original)
        self.assertIsNone(current_native_root_run())

    def test_pipeline_failure_is_not_masked_when_original_owner_also_closes(self):
        self.compose(capture=False)
        original = OSError("original controlled lifecycle failure")

        def fail(_request):
            current_native_root_run().close()
            raise original

        self.adapter.rebuild = fail
        with self.patches(), self.assertRaises(OSError) as caught:
            self.port.execute(self.request("pipeline-error"))
        self.assertIs(caught.exception, original)
        self.assertIsNone(current_native_root_run())
