"""Factual failure capture with real owner/CAS and modeled command completion.

The producer patches must be collected with this file. No compiler, provider or
generated command executes: only the existing subprocess return seam is modeled.
Framework source registration and BUILD input authority use the existing typed
native binding fixture's explicit modeled boundaries.
"""

import json
import os
import shutil
import subprocess
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_continuation as backend
from literate_ai.adapters.candidate_repair import (
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecycleError
from literate_ai.application import native_root_continuation as application
from literate_ai.application import native_root_failed_stage as capture
from literate_ai.contracts import ComponentCommandPhase, ComponentCommandRole
from literate_ai.contracts.executable_components import CandidateFailureClassification
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailureEvidence,
    StandardNodeFailurePhase,
)
from tests.critical import test_native_root_cargo_failure as cargo_fixture
from tests.critical import test_native_root_preparation_retention as fixture


@unittest.skipUnless(os.name == "posix", "existing original-owner POSIX fixture")
class NativeRootFailedStageCaptureTests(unittest.TestCase):
    setUp = fixture.NativeRootPreparationRetentionTests.setUp
    observe = fixture.NativeRootPreparationRetentionTests.observe
    metadata = fixture.NativeRootPreparationRetentionTests.metadata
    library_current = fixture.NativeRootPreparationRetentionTests.library_current
    native_protocol = fixture.NativeRootPreparationRetentionTests.native_protocol
    opened = fixture.NativeRootPreparationRetentionTests.opened
    controller = fixture.NativeRootPreparationRetentionTests.controller
    modeled_registered_candidate = (
        fixture.NativeRootPreparationRetentionTests.modeled_registered_candidate
    )

    @contextmanager
    def operation(self):
        with self.modeled_registered_candidate() as (_output, plan, _stage, _tree):
            self.ports._plans_by_revision[plan.component_revision.uri] = plan
            source = self.ports.source_trees.evidence(plan.request.source_tree_identity)
            self.case_ids = tuple(
                case.case_id for case in self.modeled_node.generated_test_evidence.cases
            )
            source.generated_test_suite = SimpleNamespace(
                content_identity=self.modeled_node.generated_test_evidence.generated_test_suite_identity.uri,
                case_ids=self.case_ids,
            )
            with (
                self.controller() as (scope, _sequence, controller),
                mock.patch.object(
                    self.ports.source_trees,
                    "resolve",
                    return_value=Path(self.node.workspace.locator),
                ),
            ):
                token = application._ACTIVE.set(controller)
                try:
                    yield scope, controller, plan
                finally:
                    controller.contexts.close()
                    application._ACTIVE.reset(token)

    def command(
        self,
        *,
        returncode=7,
        stdout="",
        stderr="compiler rejected public source",
        phase="build",
        argv=None,
        cwd=None,
    ):
        contract = self.ports._contract(self.lock.root_revision)
        identity = (
            contract.build_system_toolchain_identity
            if phase == "build"
            else contract.tool_binding(ComponentCommandPhase.TEST).toolchain_identity
        )
        if argv is None:
            argv = (*self.ports.tool_bindings[identity.uri].command, "build")
        with mock.patch(
            "literate_ai.adapters.lifecycle.standard_local.run_with_tree_kill",
            return_value=subprocess.CompletedProcess(argv, returncode, stdout, stderr),
        ):
            return self.ports._run_with_environment(
                argv, cwd=self.root if cwd is None else cwd, environment={}
            )

    def failure(self, controller, plan, error, *, phase="build"):
        enum = (
            StandardNodeFailurePhase.BUILD
            if phase == "build"
            else StandardNodeFailurePhase.TEST
        )
        code = "build.failed" if phase == "build" else "generated-test.failed"
        subject = capture.native_root_failed_stage_subject(
            plan.component_revision, enum, plan.identity, error, code
        )
        failure = StandardNodeFailureEvidence(
            plan.component_revision, enum, code, subject, "bounded public failure"
        )
        return failure, capture.native_root_failed_stage_retryable(controller, failure)

    def cargo_completion(self, plan):
        """Model metadata/JSON subprocess output; real source bytes and CAS joins."""
        source = Path(self.node.workspace.locator)
        source.mkdir(parents=True, exist_ok=True)
        (source / "lib.rs").write_bytes(b"invalid\n")
        projection = self.root / "failed-cargo-projection"
        projection.mkdir(exist_ok=True)
        (projection / "lib.rs").write_bytes(b"invalid\n")
        manifest = projection / "Cargo.toml"
        oracle = cargo_fixture.NativeRootCargoFailureTests()
        oracle.setUp()
        target = {**oracle.target, "src_path": str(projection / "lib.rs")}
        metadata = {
            "packages": [
                {
                    "id": oracle.error["package_id"],
                    "manifest_path": str(manifest),
                    "targets": [target],
                }
            ]
        }
        arguments = (
            "build",
            "--locked",
            "--manifest-path",
            str(manifest),
            "--lib",
            "--message-format=json",
        )
        capture.prepare_native_root_cargo_attribution(
            self.ports, metadata, source, projection, manifest, arguments
        )
        error = oracle.error
        error["target"] = target
        error["manifest_path"] = str(manifest)
        error["message"]["spans"][0]["file_name"] = str(projection / "lib.rs")
        output = oracle.payload()
        return (*self.cargo.command, *arguments), projection, output

    def test_original_current_cargo_compiler_error_is_repairable(self):
        with self.operation() as (_scope, controller, plan):
            with self.assertRaises(LocalStandardLifecycleError) as raised:
                with capture.observe_native_root_stage(self.ports, plan, "build"):
                    argv, cwd, output = self.cargo_completion(plan)
                    error = LocalStandardLifecycleError("original compiler error")
                    capture.observe_native_root_process(
                        self.ports, argv, cwd, 101, output, b"", failure_error=error
                    )
                    raise error
            failure, retryable = self.failure(controller, plan, raised.exception)
            self.assertTrue(retryable)
            row = dict(self.recorder.entries)[failure.subject_identity]
            self.assertIn(b"cargo-generated-compiler-error", row)

    def test_actual_build_code_uses_original_issuance_after_context_retirement(self):
        with self.operation() as (scope, controller, plan):
            controller._register_current_candidate()
            with self.assertRaises(LocalStandardLifecycleError) as raised:
                with capture.observe_native_root_stage(self.ports, plan, "build"):
                    argv, cwd, output = self.cargo_completion(plan)
                    error = LocalStandardLifecycleError("original compiler error")
                    capture.observe_native_root_process(
                        self.ports, argv, cwd, 101, output, b"", failure_error=error
                    )
                    raise error
            failure, retryable = self.failure(controller, plan, raised.exception)
            self.assertTrue(retryable)
            adapter = FilesystemStandardCandidateRepairAdapter({})
            self.assertIs(
                adapter.diagnose(
                    failure, self.modeled_node.source_output
                ).classification,
                CandidateFailureClassification.TERMINAL,
            )
            diagnostic = capture.diagnose_native_root_failed_stage(controller, failure)
            self.assertEqual(diagnostic.code, "build.failed")
            self.assertIs(
                diagnostic.classification, CandidateFailureClassification.RETRYABLE
            )
            failed_node = replace(
                self.modeled_node,
                failure_code=failure.code,
                failure_evidence=failure,
                build_plan_identity=None,
                build_identity=None,
                test_identity=None,
                execution_identity=None,
                acceptance_identity=None,
                build_evidence=None,
                exports=(),
                generated_test_evidence=None,
                execution_evidence=None,
                acceptance_evidence=None,
                source_cache_membership=None,
                source_cache_publication_identity=None,
            )
            attempt = controller._record_attempt(
                failed_node, "node-rejected", failure, diagnostic, "retryable"
            )
            controller.contexts.close()
            self.assertTrue(
                capture.require_issued_native_root_failed_stage_diagnostic(
                    diagnostic, attempt
                )
            )
            with self.assertRaisesRegex(ValueError, "diagnostic_changed"):
                capture.require_issued_native_root_failed_stage_diagnostic(
                    replace(diagnostic), attempt
                )
            original = controller._issued_failed_stage_diagnostic
            with self.assertRaises(TypeError):
                type(original)()
            forged = object.__new__(type(original))
            forged.__dict__.update(original.__dict__)
            object.__setattr__(forged, "_seal", forged)
            controller._issued_failed_stage_diagnostic = forged
            try:
                with self.assertRaisesRegex(ValueError, "diagnostic_changed"):
                    capture.require_issued_native_root_failed_stage_diagnostic(
                        diagnostic, attempt
                    )
            finally:
                controller._issued_failed_stage_diagnostic = original
            prepared_before = controller.prepared_candidate
            original_attempts = type(controller.sequence).attempts.fget

            def drift_after_attempts(sequence):
                result = original_attempts(sequence)
                controller.prepared_candidate = object()
                return result

            try:
                with (
                    mock.patch.object(
                        type(controller.sequence),
                        "attempts",
                        property(drift_after_attempts),
                    ),
                    self.assertRaisesRegex(ValueError, "diagnostic_changed"),
                ):
                    capture.require_issued_native_root_failed_stage_diagnostic(
                        diagnostic, attempt
                    )
            finally:
                controller.prepared_candidate = prepared_before
            prepared, request = adapter.prepare_root_repair(
                scope.prepared_root,
                scope.run_binding,
                controller.sequence.attempts,
                diagnostic,
                live_run=scope.original_run,
                project_authority_identity=scope.run_binding.project_authority_identity,
                execution_plan_identity=scope.run_binding.execution_plan_identity,
            )
            self.assertNotEqual(
                prepared.workspace.allocation_identity,
                scope.prepared_root.workspace.allocation_identity,
            )
            self.assertNotEqual(
                request.identity, scope.prepared_root.request.request.identity
            )

    def test_prerequisite_cannot_borrow_later_compiler_attribution(self):
        with self.operation() as (_scope, controller, plan):
            with self.assertRaises(LocalStandardLifecycleError) as raised:
                with capture.observe_native_root_stage(self.ports, plan, "build"):
                    _argv, cwd, output = self.cargo_completion(plan)
                    error = LocalStandardLifecycleError("prerequisite error")
                    capture.observe_native_root_process(
                        self.ports,
                        (*self.cargo.command, "metadata"),
                        cwd,
                        101,
                        output,
                        b"",
                        failure_error=error,
                    )
                    raise error
            _failure, retryable = self.failure(controller, plan, raised.exception)
            self.assertFalse(retryable)

    def test_projection_changed_during_process_is_terminal(self):
        with self.operation() as (_scope, controller, plan):
            with self.assertRaises(LocalStandardLifecycleError) as raised:
                with capture.observe_native_root_stage(self.ports, plan, "build"):
                    argv, cwd, output = self.cargo_completion(plan)
                    (cwd / "lib.rs").write_bytes(b"changed\n")
                    error = LocalStandardLifecycleError("original compiler error")
                    capture.observe_native_root_process(
                        self.ports, argv, cwd, 101, output, b"", failure_error=error
                    )
                    raise error
            _failure, retryable = self.failure(controller, plan, raised.exception)
            self.assertFalse(retryable)

    def test_nested_manifest_keeps_generated_sibling_diagnostic_alias(self):
        projected = self.root / "projection" / "outside.rs"
        manifest = self.root / "projection" / "inner" / "Cargo.toml"
        self.assertEqual(
            capture._diagnostic_spellings(projected, manifest),
            (str(projected), os.path.join("..", "outside.rs")),
        )

    def test_bounded_generated_read_refuses_oversize_and_link_without_following(self):
        path = self.root / "bounded-public.rs"
        path.write_bytes(b"12345")
        with self.assertRaises(ValueError):
            capture._read_generated_file(path, 4)
        link = self.root / "bounded-link.rs"
        link.symlink_to(path)
        with self.assertRaises(ValueError):
            capture._read_generated_file(link, 8)

    def test_multiargument_shared_executable_selects_exact_phase_role(self):
        class Binding:
            _authority_guard = None

            def __init__(self, command):
                self.command = command

            def require_command_unchanged(self):
                pass

            def require_unchanged(self):
                pass

        with self.operation() as (scope, _controller, plan):
            # Model only admission custody to isolate ambiguous-prefix selection;
            # original scope still retains the real plan as ordinary data.
            source = self.ports.source_trees.evidence(plan.request.source_tree_identity)
            contract = self.ports._contract(plan.component_revision)
            build_id = contract.build_system_toolchain_identity
            test_id = contract.tool_binding(
                ComponentCommandPhase.TEST
            ).toolchain_identity
            build = Binding(("/modeled/python", "cargo_proxy.py"))
            test = Binding(("/modeled/python",))
            ports = SimpleNamespace(
                build_execution_inputs=lambda _plan: None,
                _plans_by_revision={plan.component_revision.uri: plan},
                _contract=lambda _component: contract,
                source_trees=SimpleNamespace(evidence=lambda _identity: source),
                tool_bindings={build_id.uri: build, test_id.uri: test},
            )
            for phase, identity, binding in (
                ("build", build_id, build),
                ("test", test_id, test),
            ):
                with self.subTest(phase=phase):
                    cap = capture._Capture(
                        None, None, ports, plan, phase, self.node, scope, None, 0
                    )
                    cap.exports = self.modeled_node.exports
                    with (
                        mock.patch.object(cap, "require_current", return_value=None),
                        mock.patch.object(
                            scope,
                            "retain_failed_test_context",
                            return_value=(plan.identity, lambda: None),
                        ),
                    ):
                        cap.admit()
                    self.assertEqual(cap.tools, ((identity, binding, binding.command),))

    def test_actual_public_build_nonzero_is_retained_but_alone_terminal(self):
        with self.operation() as (scope, controller, plan):
            with mock.patch.object(
                self.ports, "_build_locked", side_effect=lambda *_: self.command()
            ):
                with self.assertRaises(LocalStandardLifecycleError) as raised:
                    self.ports.build(plan, ())
            failure, retryable = self.failure(controller, plan, raised.exception)
            self.assertFalse(retryable)
            self.assertNotEqual(failure.subject_identity, plan.identity)
            registry = controller._native_failed_stage_registry
            self.assertEqual(len(registry.holders), 1)
            issued = registry.holders[0]
            self.assertIs(issued.cause, raised.exception)
            self.assertEqual(issued.reason, "terminal")
            self.assertEqual(issued.processes[-1][1]["returncode"], 7)
            self.assertEqual(
                issued.processes[-1][1]["argv"], [*self.cargo.command, "build"]
            )
            self.assertIn(failure.subject_identity, dict(self.recorder.entries))
            self.assertEqual(
                json.loads(dict(self.recorder.entries)[plan.identity]), plan.to_dict()
            )
            self.assertEqual(controller.sequence.attempts, ())

    def test_actual_public_test_failed_case_protocol_requires_complete_inventory(self):
        with self.operation() as (scope, controller, plan):
            output = json.dumps(
                {
                    "schema": "literate-ai/generated-test-results@1",
                    "cases": [
                        {
                            "case_id": name,
                            "outcome": "failed" if index == 0 else "passed",
                        }
                        for index, name in enumerate(self.case_ids)
                    ],
                }
            )

            with (
                mock.patch.object(
                    backend,
                    "_capture_native_root_export",
                    wraps=backend._capture_native_root_export,
                ) as capture_export,
                mock.patch.object(
                    scope,
                    "retain_failed_test_context",
                    wraps=scope.retain_failed_test_context,
                ) as inputs,
                self.assertRaises(LocalStandardLifecycleError) as raised,
            ):
                self.real_test_parser(plan, output)
            self.assertEqual(inputs.call_count, 1)
            self.assertEqual(capture_export.call_count, 1)
            _failure, retryable = self.failure(
                controller, plan, raised.exception, phase="test"
            )
            self.assertTrue(retryable)
            self.assertEqual(
                controller._native_failed_stage_registry.holders[0].reason,
                "test-case-failed",
            )

    def real_test_parser(
        self, plan, output, *, mutate_artifact=False, mutate_before_admission=False
    ):
        """Enter actual public TEST/custody/parser, model only process completion."""
        artifact = self.root / "failed-case-artifact"
        artifact.mkdir(exist_ok=True)
        marker = artifact / "public-input.txt"
        marker.write_text("before")
        export = self.modeled_node.exports[0]
        owned_export = artifact / export.export_id
        if owned_export.exists():
            shutil.rmtree(owned_export)
        shutil.copytree(self.fixture.export, owned_export)
        if mutate_before_admission:
            target = next(owned_export.rglob("*.rs"))
            target.write_bytes(target.read_bytes() + b"\n// changed after BUILD\n")

        def run(*_args, **_kwargs):
            contract = self.ports._contract(plan.component_revision)
            command = contract.command(ComponentCommandPhase.TEST)
            tool_id = contract.tool_binding(
                ComponentCommandPhase.TEST
            ).toolchain_identity
            values = {
                ComponentCommandRole.TOOL: self.ports.tool_bindings[
                    tool_id.uri
                ].command,
                ComponentCommandRole.SOURCE_ROOT: (str(_kwargs["source_root"]),),
                ComponentCommandRole.OBJECT_ROOT: (str(_kwargs["object_root"]),),
                ComponentCommandRole.ARTIFACT_ROOT: (str(_kwargs["artifact_root"]),),
                ComponentCommandRole.EXPORT_PATH: (str(_kwargs["export_path"]),),
                ComponentCommandRole.PROVIDER_ARTIFACTS: self.ports._provider_roots(
                    _kwargs["providers"]
                ),
            }
            argv = command.substitute({role: values[role] for role in command.roles})
            result = self.command(
                returncode=0,
                stdout=output,
                stderr="",
                phase="test",
                argv=argv,
                cwd=artifact,
            )
            if mutate_artifact:
                marker.write_text("after")
            return result

        with (
            mock.patch.dict(
                self.ports._artifact_paths,
                {
                    self.modeled_node.exports[0].identity.uri: artifact,
                },
            ),
            mock.patch.object(self.ports, "_run_locked", side_effect=run),
            mock.patch.object(self.ports, "artifact_path", return_value=owned_export),
            mock.patch.object(
                self.ports,
                "_build_evidence_for_exports",
                return_value=self.modeled_node.build_evidence,
            ),
        ):
            return self.ports.test(plan, self.modeled_node.exports)

    def test_actual_public_test_artifact_mutation_cannot_borrow_failed_protocol(self):
        with self.operation() as (_scope, controller, plan):
            payload = json.dumps(
                {
                    "schema": "literate-ai/generated-test-results@1",
                    "cases": [
                        {"case_id": name, "outcome": "failed"} for name in self.case_ids
                    ],
                }
            )
            with self.assertRaisesRegex(
                LocalStandardLifecycleError, "mutated the built artifact"
            ) as raised:
                self.real_test_parser(plan, payload, mutate_artifact=True)
            _failure, retryable = self.failure(
                controller, plan, raised.exception, phase="test"
            )
            self.assertFalse(retryable)
            self.assertEqual(
                controller._native_failed_stage_registry.holders[0].issued_errors, []
            )

    def test_export_drift_before_test_admission_never_starts_child(self):
        with self.operation() as (_scope, controller, plan):
            with (
                mock.patch(
                    "literate_ai.adapters.lifecycle.standard_local.run_with_tree_kill"
                ) as child,
                self.assertRaises(ValueError),
            ):
                self.real_test_parser(plan, "{}", mutate_before_admission=True)
            child.assert_not_called()
            registry = controller._native_failed_stage_registry
            self.assertTrue(registry.holders)
            self.assertEqual(registry.holders[0].reason, "terminal")
            self.assertEqual(registry.holders[0].issued_errors, [])

    def test_matching_error_code_without_issued_process_object_is_terminal(self):
        with self.operation() as (_scope, controller, plan):
            error = LocalStandardLifecycleError("modeled fabricated failure")
            error.code = "builder.generated-source-rejected"
            with self.assertRaises(LocalStandardLifecycleError):
                with capture.observe_native_root_stage(self.ports, plan, "build"):
                    capture.observe_native_root_process(
                        self.ports,
                        (*self.cargo.command, "build"),
                        str(self.root),
                        7,
                        b"",
                        b"failure",
                    )
                    raise error
            _failure, retryable = self.failure(controller, plan, error)
            self.assertFalse(retryable)

    def test_failures_before_process_timeout_storage_and_missing_export_are_terminal(
        self,
    ):
        for error in (
            TimeoutError("timeout"),
            OSError("storage refused"),
            LocalStandardLifecycleError("missing export"),
        ):
            with (
                self.subTest(kind=type(error).__name__),
                self.operation() as (_scope, controller, plan),
            ):
                error.code = "builder.generated-source-rejected"
                with self.assertRaises(type(error)):
                    with capture.observe_native_root_stage(self.ports, plan, "build"):
                        raise error
                failure, retryable = self.failure(controller, plan, error)
                self.assertFalse(retryable)
                self.assertIn(failure.subject_identity, dict(self.recorder.entries))

    def test_unrelated_error_cannot_borrow_a_real_issued_process_failure(self):
        with self.operation() as (_scope, controller, plan):
            with self.assertRaises(LocalStandardLifecycleError) as raised:
                with capture.observe_native_root_stage(self.ports, plan, "build"):
                    self.command()
            other = LocalStandardLifecycleError(str(raised.exception))
            other.code = "builder.generated-source-rejected"
            failure, retryable = self.failure(controller, plan, other)
            self.assertEqual(failure.subject_identity, plan.identity)
            self.assertFalse(retryable)

    def test_capture_storage_refusal_preserves_original_command_error_and_is_terminal(
        self,
    ):
        with self.operation() as (scope, controller, plan):
            with self.assertRaisesRegex(
                LocalStandardLifecycleError, "local command failed"
            ) as raised:
                with capture.observe_native_root_stage(self.ports, plan, "build"):
                    with mock.patch.object(
                        scope,
                        "retain_bytes",
                        side_effect=OSError("modeled store refusal"),
                    ):
                        self.command()
            _failure, retryable = self.failure(controller, plan, raised.exception)
            self.assertFalse(retryable)
            self.assertIsInstance(
                controller._native_failed_stage_registry.holders[0].issue, OSError
            )

    def test_registry_cleanup_releases_error_holders_without_erasing_records(self):
        with self.operation() as (_scope, controller, plan):
            with self.assertRaises(LocalStandardLifecycleError) as raised:
                with capture.observe_native_root_stage(self.ports, plan, "build"):
                    self.command()
            failure, retryable = self.failure(controller, plan, raised.exception)
            self.assertFalse(retryable)
            before = self.recorder.entries
            registry = controller._native_failed_stage_registry
            controller.contexts.close()
            self.assertTrue(registry.closed)
            self.assertEqual(registry.holders, [])
            self.assertEqual(self.recorder.entries, before)
            self.assertFalse(
                capture.native_root_failed_stage_retryable(controller, failure)
            )

    def test_partial_duplicate_or_all_matching_case_protocol_never_implies_failure(
        self,
    ):
        for rows in (
            [{"case_id": "first", "outcome": "failed"}],
            [{"case_id": "first", "outcome": "failed"}] * 2,
            [{"case_id": name, "outcome": "passed"} for name in ("first", "second")],
        ):
            with self.subTest(rows=rows):
                self.assertFalse(
                    capture.failed_case_protocol(
                        json.dumps(
                            {
                                "schema": "literate-ai/generated-test-results@1",
                                "cases": rows,
                            }
                        ),
                        ("first", "second"),
                    )
                )
        self.assertFalse(capture.failed_case_protocol(b"not json", ("first",)))
