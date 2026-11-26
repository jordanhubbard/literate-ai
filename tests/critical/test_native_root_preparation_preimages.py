"""Actual public preparation CAS preimages, without native qualification.

The existing fixture owns real bounded requests and replacement allocations.
Only its lifecycle stages are modeled. The controller delegation is patched in
this test until the separately owned integration patch is collected.
"""

import hashlib
import os
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.application.native_root_continuation import NativeRootController
from literate_ai.application.native_root_preparation_retention import (
    retain_native_root_preparation,
)
from literate_ai.application.native_root_run import NativeRootRunError
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from tests.critical import test_native_root_preparation_retention as fixture


@unittest.skipUnless(os.name == "posix", "owned local POSIX protocol fixture")
class NativeRootPreparationPreimageTests(unittest.TestCase):
    setUp = fixture.NativeRootPreparationRetentionTests.setUp
    observe = fixture.NativeRootPreparationRetentionTests.observe
    metadata = fixture.NativeRootPreparationRetentionTests.metadata
    library_current = fixture.NativeRootPreparationRetentionTests.library_current
    native_protocol = fixture.NativeRootPreparationRetentionTests.native_protocol
    opened = fixture.NativeRootPreparationRetentionTests.opened
    modeled_registered_candidate = (
        fixture.NativeRootPreparationRetentionTests.modeled_registered_candidate
    )
    preparation_records = (
        fixture.NativeRootPreparationRetentionTests.preparation_records
    )

    @contextmanager
    def controller(self, **kwargs):
        with (
            fixture.NativeRootPreparationRetentionTests.controller(
                self, **kwargs
            ) as opened,
            mock.patch.object(
                NativeRootController,
                "_retain_current_preparation",
                retain_native_root_preparation,
            ),
        ):
            yield opened

    def assert_preparation_retained(self, scope, prepared):
        records = (
            *self.preparation_records(prepared),
            (scope.execution_plan.identity, scope.execution_plan.to_dict()),
            (prepared.plan.identity, prepared.plan.to_dict()),
        )
        retained = dict(self.recorder.entries)
        for identity, document in records:
            payload = canonical_json_bytes(document)
            self.assertEqual(canonical_identity(document), identity)
            self.assertEqual(retained[identity], payload)
            self.assertEqual(
                scope._evidence.get_bytes(BlobRef(identity.digest, len(payload))),
                payload,
            )
        request, prompt = prepared.request.request, prepared.request.prompt
        self.assertEqual(retained[request.prompt_identity], prompt)
        self.assertEqual(
            scope._evidence.get_bytes(
                BlobRef(request.prompt_identity.digest, len(prompt))
            ),
            prompt,
        )
        self.assertEqual(
            request.context_manifest_identity, request.context_manifest.identity
        )
        self.assertEqual(
            request.budget_decision.budget_identity, request.budget.identity
        )
        self.assertLessEqual(len(prompt), request.budget.max_prompt_bytes)

    def test_original_five_records_and_public_prompt_precede_pipeline(
        self,
    ):
        fixture.NativeRootPreparationRetentionTests.test_original_records_are_retained_before_pipeline_with_exact_ids(
            self
        )

    def test_replacement_keeps_original_context_budget_and_decision_with_new_prompt(
        self,
    ):
        original = self.node.request.request
        checked = self.assert_preparation_retained
        replacements = []

        def inspect(scope, prepared):
            checked(scope, prepared)
            if prepared is not self.node:
                request = prepared.request.request
                self.assertEqual(request.context_manifest, original.context_manifest)
                self.assertEqual(request.budget, original.budget)
                self.assertEqual(request.budget_decision, original.budget_decision)
                self.assertNotEqual(prepared.request.prompt, self.node.request.prompt)
                self.assertNotEqual(request.prompt_identity, original.prompt_identity)
                replacements.append(prepared)

        with mock.patch.object(
            self, "assert_preparation_retained", side_effect=inspect
        ):
            fixture.NativeRootPreparationRetentionTests.test_replacement_records_and_root_request_exist_before_checkpoint(
                self
            )
        self.assertTrue(replacements)

    def test_missing_or_tampered_public_prompt_refuses_before_any_retention(self):
        for payload in (None, b"tampered public prompt"):
            with (
                self.subTest(payload=payload),
                self.controller() as (scope, _sequence, controller),
            ):
                original = self.node.request.prompt
                object.__setattr__(self.node.request, "prompt", payload)
                try:
                    with mock.patch.object(
                        scope, "retain_record", wraps=scope.retain_record
                    ) as record:
                        with self.assertRaises((TypeError, ValueError)):
                            retain_native_root_preparation(controller)
                    record.assert_not_called()
                finally:
                    object.__setattr__(self.node.request, "prompt", original)

    def test_equal_recreated_or_missing_generation_plan_cannot_replace_held_plan(self):
        for plan in (None, replace(self.node.plan)):
            with (
                self.subTest(plan=plan),
                self.controller() as (scope, _sequence, controller),
            ):
                controller.prepared_candidate = replace(self.node, plan=plan)
                with mock.patch.object(
                    scope, "retain_record", wraps=scope.retain_record
                ) as record:
                    with self.assertRaises((TypeError, ValueError)):
                        retain_native_root_preparation(controller)
                record.assert_not_called()

    def test_valid_hash_does_not_permit_prompt_beyond_original_byte_budget(self):
        original = self.node.request
        prompt = b"p" * (original.request.budget.max_prompt_bytes + 1)
        request = replace(
            original.request,
            prompt_identity=ContentIdentity.parse_uri(
                "sha256:" + hashlib.sha256(prompt).hexdigest()
            ),
        )
        self.node = replace(
            self.node, request=replace(original, request=request, prompt=prompt)
        )
        with self.controller() as (scope, _sequence, controller):
            with mock.patch.object(
                scope, "retain_record", wraps=scope.retain_record
            ) as record:
                with self.assertRaisesRegex(ValueError, "original byte budget"):
                    retain_native_root_preparation(controller)
            record.assert_not_called()

    def test_candidate_change_in_record_callback_refuses_before_next_write(self):
        with self.controller() as (scope, _sequence, controller):
            original = scope.retain_record

            def change(record):
                identity = original(record)
                controller.prepared_candidate = replace(self.node)
                return identity

            with mock.patch.object(
                scope, "retain_record", side_effect=change
            ) as record:
                with self.assertRaisesRegex(ValueError, "changed during retention"):
                    retain_native_root_preparation(controller)
            self.assertEqual(record.call_count, 1)

    def test_closed_owner_during_prompt_write_preserves_primary_and_pending_count(
        self,
    ):
        with self.controller() as (scope, sequence, controller):
            failure = OSError("controlled public prompt retention failure")
            original = scope.retain_bytes

            def retain(payload):
                if payload is self.node.request.prompt:
                    scope.original_run.close()
                    raise failure
                return original(payload)

            with (
                mock.patch.object(
                    scope, "retain_record", wraps=scope.retain_record
                ) as records,
                mock.patch.object(scope, "retain_bytes", side_effect=retain),
                self.assertRaises(OSError) as caught,
            ):
                controller.execute(mock.Mock())
            self.assertIs(caught.exception, failure)
            self.assertEqual(records.call_count, 5)
            self.assertEqual(sequence._attempts, ())
            self.assertIsNotNone(sequence._pending)
            self.assertIn(
                "native root terminal evidence could not close", failure.__notes__
            )
            with self.assertRaises(NativeRootRunError):
                sequence.require_current()
