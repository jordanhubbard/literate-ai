"""Bounded durable recorder snapshots, without native acceptance claims.

Package fixture metadata/stages are modeled; original file pins, package trees,
recorder bytes and scope CAS are real. Late-close tests stop BEFORE success-ledger
recording and do not run native commands or qualify any package.
"""

import unittest
from unittest import mock

from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecycleError
from literate_ai.adapters.native_root_continuation import NativeRootContinuationError
from literate_ai.application.native_root_run import NativeRootRunError
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.standard_root_integration import (
    StandardRootIntegrationEvidence,
)
from literate_ai.storage.cas import BlobNotFoundError
from tests.critical import test_native_root_package_capture as fixture


class _BeforeLedger(Exception):
    """Stop a modeled closing path before any accepted ledger can be recorded."""


@unittest.skipUnless(fixture.os.name == "posix", "owned POSIX protocol fixtures")
class NativeRootSnapshotTests(unittest.TestCase):
    setUp = fixture.NativeRootPackageCaptureTests.setUp
    observe = fixture.NativeRootPackageCaptureTests.observe
    metadata = fixture.NativeRootPackageCaptureTests.metadata
    library_current = fixture.NativeRootPackageCaptureTests.library_current
    native_protocol = fixture.NativeRootPackageCaptureTests.native_protocol
    opened = fixture.NativeRootPackageCaptureTests.opened
    modeled_registered_candidate = (
        fixture.NativeRootPackageCaptureTests.modeled_registered_candidate
    )
    package = fixture.NativeRootPackageCaptureTests.package

    def assert_bytes(self, scope, identity, content):
        self.assertEqual(
            scope._evidence.get_bytes(BlobRef(identity.digest, len(content))), content
        )

    def integration(self, arguments, acceptance):
        project, graph, link, plan, result, root_test, execution = arguments
        return StandardRootIntegrationEvidence(
            self.lock.identity,
            self.execution.identity,
            project.identity,
            graph,
            link,
            plan,
            result,
            root_test,
            execution,
            acceptance,
        )

    def test_pre_native_snapshot_persists_nested_original_raw_streams(
        self,
    ):
        with self.package() as (
            scope,
            controller,
            arguments,
            custody,
            _export,
            _payload,
            recorder,
        ):
            stdout, stderr = (
                b"\x00actual original root stdout\xff",
                b"original root stderr\n",
            )
            stdout_id = recorder.remember_bytes(stdout)
            stderr_id = recorder.remember_bytes(stderr)
            root = {
                "schema": "literate-ai/packaged-library-root-integration@1",
                "package_plan_identity": arguments[3].identity.uri,
                "package_result_identity": arguments[4].identity.uri,
                "package_tree_identity": custody.tree_identity.uri,
                "stdout_identity": stdout_id.uri,
                "stderr_identity": stderr_id.uri,
                "status": "modeled original test observation",
            }
            root_id = recorder.remember_json(root)
            arguments = (*arguments[:5], root_id, arguments[6])
            controller.package_binding = fixture.NativeRootPackageBinding(
                arguments[1].identity,
                arguments[2].identity,
                arguments[3].identity,
                arguments[4].identity,
                root_id,
                arguments[6],
            )
            scope.retain_package_context(*arguments)
            held = tuple(recorder.entries)
            for identity, content in held:
                self.assert_bytes(scope, identity, content)
            self.assert_bytes(scope, stdout_id, stdout)
            self.assert_bytes(scope, stderr_id, stderr)
            # Durability is independent of subsequent in-memory recorder loss.
            recorder._records.clear()
            recorder._retained_bytes = 0
            self.assert_bytes(scope, root_id, canonical_json_bytes(root))
            self.assert_bytes(scope, stdout_id, stdout)

    def test_late_summary_is_durable_after_context_close_before_success_ledger(self):
        with self.package() as (
            scope,
            controller,
            arguments,
            _custody,
            _export,
            _payload,
            recorder,
        ):
            controller._register_current_candidate()
            scope.retain_package_context(*arguments)
            summary = {
                "schema": "modeled-independent-acceptance-summary@1",
                "package": arguments[4].identity.uri,
            }
            identity = recorder.remember_json(summary)
            content = canonical_json_bytes(summary)
            with self.assertRaises(BlobNotFoundError):
                scope._evidence.get_bytes(BlobRef(identity.digest, len(content)))
            phases = []
            controller.contexts.callback(lambda: phases.append("contexts closed"))

            def before_ledger(_attempt):
                self.assertEqual(phases, ["contexts closed"])
                self.assert_bytes(scope, identity, content)
                phases.append("before ledger")
                raise _BeforeLedger()

            with mock.patch.object(
                controller.sequence, "record_attempt", side_effect=before_ledger
            ):
                with self.assertRaises(_BeforeLedger):
                    controller.close_accepted_root(
                        self.integration(arguments, identity)
                    )
            self.assertEqual(phases, ["contexts closed", "before ledger"])
            self.assertIsNone(controller._accepted_ledger)
            self.assertIsNotNone(controller.sequence._pending)
            self.assertEqual(controller.sequence._attempts, ())

    def test_failed_context_close_does_not_snapshot_or_create_success_ledger(self):
        with self.package() as (
            scope,
            controller,
            arguments,
            _custody,
            _export,
            _payload,
            recorder,
        ):
            controller._register_current_candidate()
            scope.retain_package_context(*arguments)
            identity = recorder.remember_json({"schema": "modeled late summary@1"})
            failure = OSError("original modeled verifier-context close failure")

            def refuse():
                raise failure

            controller.contexts.callback(refuse)
            with mock.patch.object(
                scope,
                "_snapshot_recorded_evidence",
                wraps=scope._snapshot_recorded_evidence,
            ) as snapshot:
                with self.assertRaises(OSError) as raised:
                    controller.close_accepted_root(
                        self.integration(arguments, identity)
                    )
                self.assertIs(raised.exception, failure)
                snapshot.assert_not_called()
            self.assertIsNone(controller._accepted_ledger)
            self.assertEqual(controller.sequence._attempts, ())

    def test_lost_late_summary_cannot_close_success_ledger(self):
        with self.package() as (
            scope,
            controller,
            arguments,
            _custody,
            _export,
            _payload,
            recorder,
        ):
            controller._register_current_candidate()
            scope.retain_package_context(*arguments)
            identity = recorder.remember_json({"schema": "modeled lost late summary@1"})
            controller.contexts.callback(lambda: recorder._records.pop(identity))
            with mock.patch.object(controller.sequence, "record_attempt") as record:
                with self.assertRaisesRegex(
                    NativeRootContinuationError, "record_snapshot_required_missing"
                ):
                    controller.close_accepted_root(
                        self.integration(arguments, identity)
                    )
                record.assert_not_called()
            self.assertIsNone(controller._accepted_ledger)
            self.assertEqual(controller.sequence._attempts, ())
            self.assertIsNotNone(controller.sequence._pending)

    def test_each_snapshot_has_fresh_source_boundaries_instead_of_cached_success(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            _export,
            _payload,
            _recorder,
        ):
            scope.retain_package_context(*arguments)
            with mock.patch.object(
                scope, "require_generated_source", wraps=scope.require_generated_source
            ) as source:
                scope._snapshot_recorded_evidence()
                self.assertEqual(source.call_count, 2)
                scope._snapshot_recorded_evidence()
                self.assertEqual(source.call_count, 4)

    def test_physical_package_mutation_during_copy_refuses_at_closing_boundary(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            custody,
            _export,
            _payload,
            _recorder,
        ):
            scope.retain_package_context(*arguments)
            original = scope._evidence.put_bytes
            changed = []

            def write(content, **kwargs):
                reference = original(content, **kwargs)
                if not changed:
                    changed.append(True)
                    (custody.root / "changed-during-data-snapshot").write_bytes(
                        b"changed"
                    )
                return reference

            with mock.patch.object(scope._evidence, "put_bytes", side_effect=write):
                with self.assertRaises(LocalStandardLifecycleError):
                    scope._snapshot_recorded_evidence()
            self.assertFalse(scope._active)

    def test_original_remaining_deadline_refuses_during_copy_without_renewal(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            _export,
            _payload,
            _recorder,
        ):
            scope.retain_package_context(*arguments)
            deadline = scope.original_run.deadline
            original = scope._evidence.put_bytes
            writes = []

            def write(content, **kwargs):
                reference = original(content, **kwargs)
                writes.append(True)
                scope.original_run._expires_monotonic_ns = 0
                return reference

            with mock.patch.object(scope._evidence, "put_bytes", side_effect=write):
                with self.assertRaises(NativeRootRunError) as raised:
                    scope._snapshot_recorded_evidence()
            self.assertEqual(raised.exception.code, "native_root_run.expired")
            self.assertEqual(writes, [True])
            self.assertIs(scope.original_run.deadline, deadline)
            self.assertFalse(scope._active)

    def test_original_recorder_limit_growth_during_copy_is_refused(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            _export,
            _payload,
            recorder,
        ):
            scope.retain_package_context(*arguments)
            original = scope._evidence.put_bytes

            def write(content, **kwargs):
                reference = original(content, **kwargs)
                recorder.max_records += 1
                return reference

            with mock.patch.object(scope._evidence, "put_bytes", side_effect=write):
                with self.assertRaisesRegex(
                    NativeRootContinuationError, "record_snapshot_changed"
                ):
                    scope._snapshot_recorded_evidence()
            self.assertFalse(scope._active)

    def test_corrupt_held_payload_cannot_fabricate_expected_identity(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            _export,
            _payload,
            recorder,
        ):
            scope.retain_package_context(*arguments)
            identity = recorder.remember_bytes(
                b"actual original bytes not yet snapshotted"
            )
            recorder._records[identity] = b"changed bytes with unchanged identity"
            with self.assertRaisesRegex(
                NativeRootContinuationError, "record_snapshot_changed"
            ):
                scope._snapshot_recorded_evidence()
            with self.assertRaises(BlobNotFoundError):
                scope._evidence.get_bytes(
                    BlobRef(
                        identity.digest,
                        len(b"actual original bytes not yet snapshotted"),
                    )
                )

    def test_recorder_append_during_copy_cannot_claim_complete_moving_snapshot(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            _export,
            _payload,
            recorder,
        ):
            scope.retain_package_context(*arguments)
            original = scope._evidence.put_bytes
            added = []

            def write(content, **kwargs):
                reference = original(content, **kwargs)
                if not added:
                    added.append(
                        recorder.remember_bytes(b"new stream arrived during snapshot")
                    )
                return reference

            with mock.patch.object(scope._evidence, "put_bytes", side_effect=write):
                with self.assertRaisesRegex(
                    NativeRootContinuationError, "record_snapshot_changed"
                ):
                    scope._snapshot_recorded_evidence()
            self.assertEqual(len(added), 1)
            self.assertFalse(scope._active)

    def test_changed_cas_readback_refuses_without_success(self):
        with self.package() as (
            scope,
            _controller,
            arguments,
            _custody,
            _export,
            _payload,
            _recorder,
        ):
            scope.retain_package_context(*arguments)
            with mock.patch.object(
                scope._evidence, "get_bytes", return_value=b"wrong readback"
            ):
                with self.assertRaisesRegex(
                    NativeRootContinuationError, "record_snapshot_changed"
                ):
                    scope._snapshot_recorded_evidence()
            self.assertFalse(scope._active)
