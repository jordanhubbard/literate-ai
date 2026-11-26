"""Factual failure capture with real owner/CAS and modeled command completion.

The producer patches must be collected with this file. No compiler, provider or
generated command executes: only the existing subprocess return seam is modeled.
Framework source registration and BUILD input authority use the existing typed
native binding fixture's explicit modeled boundaries.
"""

import json
import os
import subprocess
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecycleError
from literate_ai.application import native_root_continuation as application
from literate_ai.application import native_root_failed_stage as capture
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailureEvidence,
    StandardNodeFailurePhase,
)
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
        self, *, returncode=7, stdout="", stderr="compiler rejected public source"
    ):
        argv = (*self.cargo.command, "build")
        with mock.patch(
            "literate_ai.adapters.lifecycle.standard_local.run_with_tree_kill",
            return_value=subprocess.CompletedProcess(argv, returncode, stdout, stderr),
        ):
            return self.ports._run_with_environment(argv, cwd=self.root, environment={})

    def failure(self, controller, plan, error, *, phase="build"):
        enum = (
            StandardNodeFailurePhase.BUILD
            if phase == "build"
            else StandardNodeFailurePhase.TEST
        )
        code = (
            "builder.generated-source-rejected"
            if phase == "build"
            else "generated-test.failed"
        )
        subject = capture.native_root_failed_stage_subject(
            plan.component_revision, enum, plan.identity, error, code
        )
        failure = StandardNodeFailureEvidence(
            plan.component_revision, enum, code, subject, "bounded public failure"
        )
        return failure, capture.native_root_failed_stage_retryable(controller, failure)

    def test_actual_public_build_failure_retains_observed_nonzero_before_raise(self):
        with self.operation() as (_scope, controller, plan):
            with mock.patch.object(
                self.ports, "_build_locked", side_effect=lambda *_: self.command()
            ):
                with self.assertRaises(LocalStandardLifecycleError) as raised:
                    self.ports.build(plan, ())
            failure, retryable = self.failure(controller, plan, raised.exception)
            self.assertTrue(retryable)
            self.assertNotEqual(failure.subject_identity, plan.identity)
            registry = controller._native_failed_stage_registry
            self.assertEqual(len(registry.holders), 1)
            issued = registry.holders[0]
            self.assertIs(issued.cause, raised.exception)
            self.assertEqual(issued.reason, "process-nonzero")
            self.assertEqual(issued.processes[-1][1]["returncode"], 7)
            self.assertEqual(
                issued.processes[-1][1]["argv"], [*self.cargo.command, "build"]
            )
            self.assertIn(failure.subject_identity, dict(self.recorder.entries))
            self.assertEqual(controller.sequence.attempts, ())

    def test_actual_public_test_failed_case_protocol_requires_complete_inventory(self):
        with self.operation() as (_scope, controller, plan):
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

            def tested(*_args):
                self.command(returncode=0, stdout=output, stderr="")
                raise LocalStandardLifecycleError(
                    "generated-test runner emitted a failed case"
                )

            with mock.patch.object(self.ports, "_test_locked", side_effect=tested):
                with self.assertRaises(LocalStandardLifecycleError) as raised:
                    self.ports.test(plan, self.modeled_node.exports)
            _failure, retryable = self.failure(
                controller, plan, raised.exception, phase="test"
            )
            self.assertTrue(retryable)
            self.assertEqual(
                controller._native_failed_stage_registry.holders[0].reason,
                "test-case-failed",
            )

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
            with mock.patch.object(
                scope, "retain_bytes", side_effect=OSError("modeled store refusal")
            ):
                with self.assertRaisesRegex(
                    LocalStandardLifecycleError, "local command failed"
                ) as raised:
                    with capture.observe_native_root_stage(self.ports, plan, "build"):
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
            self.assertTrue(retryable)
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
