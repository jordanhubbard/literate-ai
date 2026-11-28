"""Real journal/CAS projection boundaries with modeled source results only.

No generated process, native acceptance or release qualification is exercised.
"""

import hashlib
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.adapters.context_journal import (
    FilesystemForwardGenerationContextEvidenceRecorder,
    FilesystemForwardGenerationContextJournal,
    ForwardGenerationContextJournalError,
)
from literate_ai.application import native_root_continuation as controller_module
from literate_ai.application.component_generation_preparation import (
    PreparedComponentGenerationRequest,
)
from literate_ai.application.native_root_run import NativeRootRunError
from literate_ai.application.standard_project_lifecycle import (
    StandardProjectLifecycleService,
)
from literate_ai.contracts.identity import ContentIdentity
from tests.critical import test_native_root_binding as binding
from tests.support import fixtures_test_standard_project_lifecycle as model


class NativeRootContextProjectionTests(unittest.TestCase):
    setUp = binding.NativeRootBindingTests.setUp
    opened = binding.NativeRootBindingTests.opened

    def recorder(self, name="context-journal"):
        return FilesystemForwardGenerationContextEvidenceRecorder(
            FilesystemForwardGenerationContextJournal(self.root / name),
            cache_key=lambda prepared: prepared.request.request.generation_key_identity,
        )

    def service(self, recorder, checkpoint=None):
        # Actual callback owner; unrelated stage ports are never executed here.
        service = object.__new__(StandardProjectLifecycleService)
        service.context_evidence_recorder = recorder
        service.checkpoint_recorder = checkpoint
        return service

    def result_pairs(self):
        names = {self.lock.root_revision.uri: "qualified-fixture"}
        ports = model.ContractEvidenceLifecyclePorts(
            self.execution, names, library_exports=True
        )
        result = (
            model._service(ports)
            .execute(
                self.execution,
                component_lock=self.lock,
                invalidation=model._decision(
                    self.execution, names, "qualified-fixture", ("qualified-fixture",)
                ),
                prepared_nodes={self.lock.root_revision.uri: self.node},
            )
            .node_results[0]
            .source_generation
        )
        prompt = self.node.request.prompt + b"\nroot-replacement"
        identity = ContentIdentity.parse_uri(
            "sha256:" + hashlib.sha256(prompt).hexdigest()
        )
        request = replace(self.node.request.request, prompt_identity=identity)
        replacement = replace(
            self.node, request=PreparedComponentGenerationRequest(request, prompt)
        )
        return (self.node, result), (
            replacement,
            replace(result, prompt_identity=identity),
        )

    def test_replacement_resets_projection_preserves_old_cas_and_original_bounds(self):
        recorder = self.recorder()
        first, second = self.result_pairs()
        recorder.record(*first)
        old = recorder.records[0]
        with self.opened() as (scope, run):
            deadline = run.deadline
            checkpoint = mock.Mock()
            service = self.service(recorder, checkpoint)
            callback = service._native_root_replacement_callback(scope, self.execution)
            callback()
            checkpoint.start_replacement.assert_called_once_with(
                self.execution.identity, self.execution.root_revision
            )
            self.assertEqual(recorder.records, ())
            recorder.record(*second)
            self.assertEqual(len(recorder.records), 1)
            self.assertNotEqual(
                first[0].request.request.identity, second[0].request.request.identity
            )
            self.assertNotEqual(
                recorder.records[0].journal.identity, old.journal.identity
            )
            self.assertEqual(
                recorder.journal.get_prompt_journal(old.journal_reference), old.journal
            )
            self.assertEqual(
                recorder.journal.get_benchmark_record(old.benchmark_reference),
                old.benchmark,
            )
            self.assertIs(run.deadline, deadline)
            self.assertEqual(scope.run_binding.candidate_limit, 3)

    def test_same_candidate_conflicting_result_still_refused(self):
        recorder = self.recorder()
        first, second = self.result_pairs()
        recorder.record(*first)
        original = recorder.records
        with self.assertRaises(ForwardGenerationContextJournalError) as caught:
            recorder.record(*second)
        self.assertEqual(
            caught.exception.code, "context_journal.component_result_changed"
        )
        self.assertEqual(recorder.records, original)

    def test_closed_original_owner_refuses_before_reset_or_next_pipeline(self):
        recorder = self.recorder()
        with self.opened() as (scope, run):
            service = self.service(recorder)
            callback = service._native_root_replacement_callback(scope, self.execution)
            with mock.patch.object(
                recorder, "start_attempt", wraps=recorder.start_attempt
            ) as reset:
                # Owner refusal precedes the changed method lookup or call.
                run.close()
                with self.assertRaises(NativeRootRunError):
                    callback()
                reset.assert_not_called()

    def test_substituted_recorder_and_reset_delegate_refuse(self):
        for substitution in ("recorder", "delegate"):
            with (
                self.subTest(substitution=substitution),
                self.opened() as (scope, _run),
            ):
                recorder = self.recorder(substitution)
                service = self.service(recorder)
                callback = service._native_root_replacement_callback(
                    scope, self.execution
                )
                foreign = mock.Mock()
                if substitution == "recorder":
                    service.context_evidence_recorder = foreign
                else:
                    recorder.start_attempt = foreign
                with self.assertRaisesRegex(ValueError, "changed"):
                    callback()
                foreign.assert_not_called()
                foreign.start_attempt.assert_not_called()

    def test_checkpoint_substitution_stops_before_clearing_original_projection(self):
        recorder = self.recorder()
        recorder.record(*self.result_pairs()[0])
        original = recorder.records
        with self.opened() as (scope, _run):
            service = self.service(recorder, mock.Mock())
            callback = service._native_root_replacement_callback(scope, self.execution)
            foreign = self.recorder("foreign")
            service.checkpoint_recorder.start_replacement.side_effect = lambda *args: (
                setattr(service, "context_evidence_recorder", foreign)
            )
            with self.assertRaisesRegex(ValueError, "changed"):
                callback()
            self.assertEqual(recorder.records, original)
            self.assertEqual(foreign.records, ())

    def test_reset_error_remains_primary_when_callback_also_closes_owner(self):
        recorder = self.recorder()
        with self.opened() as (scope, run):
            primary = OSError("original reset failure")

            def refuse():
                run.close()
                raise primary

            recorder.start_attempt = refuse
            service = self.service(recorder)
            callback = service._native_root_replacement_callback(scope, self.execution)
            next_pipeline = mock.Mock()
            with self.assertRaises(OSError) as caught:
                callback()
                next_pipeline()
            self.assertIs(caught.exception, primary)
            next_pipeline.assert_not_called()

    def test_successful_reset_that_closes_owner_refuses_next_pipeline(self):
        recorder = self.recorder()
        with self.opened() as (scope, run):
            original_reset = recorder.start_attempt

            def reset_and_close():
                original_reset()
                run.close()

            recorder.start_attempt = reset_and_close
            service = self.service(recorder)
            callback = service._native_root_replacement_callback(scope, self.execution)
            next_pipeline = mock.Mock()
            with self.assertRaises(NativeRootRunError):
                callback()
                next_pipeline()
            next_pipeline.assert_not_called()

    def test_first_guard_cannot_adopt_a_substituted_recorder(self):
        recorder = self.recorder()
        foreign = self.recorder("first-guard-foreign")
        with self.opened() as (scope, _run):
            service = self.service(recorder)
            original_current = scope.require_current

            def substitute():
                original_current()
                service.context_evidence_recorder = foreign

            with mock.patch.object(scope, "require_current", side_effect=substitute):
                with self.assertRaisesRegex(ValueError, "recorder changed"):
                    service._native_root_replacement_callback(scope, self.execution)
            self.assertEqual(recorder.records, ())
            self.assertEqual(foreign.records, ())

    def test_closing_guard_cannot_replace_recorder_or_delegate(self):
        for substitution in ("recorder", "delegate"):
            with (
                self.subTest(substitution=substitution),
                self.opened() as (scope, _run),
            ):
                recorder = self.recorder("closing-" + substitution)
                service = self.service(recorder)
                callback = service._native_root_replacement_callback(
                    scope, self.execution
                )
                original_current = scope.require_current
                calls = 0
                foreign = mock.Mock()

                def substitute_on_closing_guard(
                    original_current=original_current,
                    substitution=substitution,
                    service=service,
                    recorder=recorder,
                    foreign=foreign,
                ):
                    nonlocal calls
                    original_current()
                    calls += 1
                    if calls == 2:
                        if substitution == "recorder":
                            service.context_evidence_recorder = foreign
                        else:
                            recorder.start_attempt = foreign

                with mock.patch.object(
                    scope, "require_current", side_effect=substitute_on_closing_guard
                ):
                    with self.assertRaisesRegex(ValueError, "changed"):
                        callback()
                self.assertEqual(calls, 2)
                foreign.assert_not_called()
                foreign.start_attempt.assert_not_called()

    def test_hostile_note_storage_does_not_mask_reset_error(self):
        class HostileResetError(OSError):
            @property
            def __notes__(self):
                raise RuntimeError("hostile note storage")

            def add_note(self, note):
                raise RuntimeError("hostile note dispatch")

        recorder = self.recorder()
        with self.opened() as (scope, run):
            primary = HostileResetError("original reset failure")

            def refuse():
                run.close()
                raise primary

            recorder.start_attempt = refuse
            service = self.service(recorder)
            callback = service._native_root_replacement_callback(scope, self.execution)
            with self.assertRaises(HostileResetError) as caught:
                callback()
            self.assertIs(caught.exception, primary)

    def test_execute_installs_reset_on_actual_continuation_callback(self):
        recorder = self.recorder()
        recorder.record(*self.result_pairs()[0])
        service = self.service(recorder)
        service.candidate_repair_port = mock.Mock()
        with self.opened() as (scope, run):

            @contextmanager
            def factory(**kwargs):
                self.assertIs(kwargs["original_run"], run)
                yield scope

            service.native_root_continuation_factory = factory
            service.project_finalizer = None

            def continuation(actual_scope, repair, pipeline, *, start_replacement):
                self.assertIs(actual_scope, scope)
                self.assertTrue(recorder.records)
                start_replacement()
                self.assertEqual(recorder.records, ())
                return "controlled dispatch"

            with mock.patch.object(
                controller_module,
                "execute_native_root_continuation",
                side_effect=continuation,
            ):
                result = service.execute(
                    self.execution,
                    component_lock=self.lock,
                    invalidation=mock.Mock(),
                    prepared_nodes={self.lock.root_revision.uri: self.node},
                    live_run=run,
                    project_authority_identity=scope.run_binding.project_authority_identity,
                )
            self.assertEqual(result, "controlled dispatch")
