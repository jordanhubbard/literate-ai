"""Separate provider-receipt integrity; qualification/live owners are MODELED.

The typed artifact graph, acceptance contracts, memberships, hash checks and
four-field capture are real. No fixture here qualifies a native provider.
"""

import hashlib
import unittest
from dataclasses import fields, replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_archive as original_archives
from literate_ai.adapters import native_root_external_runtime as runtime
from literate_ai.adapters.native_root_external_archive import (
    CapturedQualifiedProviderArchive,
)
from literate_ai.adapters.native_root_external_libraries import (
    BorrowedExternalQualifiedLibraries,
)
from literate_ai.adapters.qualification import FilesystemStandardQualificationAdapter
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceRecorder,
    QualificationRunCapture,
    capture_qualification_run,
)
from literate_ai.application.artifact_graph import create_artifact_build_graph
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.library_products import LibraryArtifactProduct
from literate_ai.contracts.retained_libraries import RetainedLibraryExportSet
from tests.support import fixtures_test_artifact_graph_contracts as artifact_fixture
from tests.support.fixtures_test_qualification_capture import fixture


def _acceptance(original, export):
    build = replace(
        original.build,
        component_revision=export.component_revision,
        exports=(export,),
        resolved_sbom_export_identities=(export.identity,),
    )
    tests = replace(
        original.generated_tests,
        component_revision=export.component_revision,
        build_evidence_identity=build.identity,
        export_identities=build.export_identities,
    )
    execution = replace(
        original.execution,
        component_revision=export.component_revision,
        build_evidence_identity=build.identity,
        export_identities=build.export_identities,
        root_export_identity=export.identity,
    )
    return replace(
        original,
        component_revision=export.component_revision,
        build=build,
        generated_tests=tests,
        execution=execution,
    )


class ExternalQualifiedProductCaptureTests(unittest.TestCase):
    def setUp(self):
        run, exports, original, content = fixture()
        source_product = exports.libraries[0]
        payload = b"original already-qualified provider bytes"
        provider_export = replace(
            source_product.artifact_export,
            component_revision=canonical_identity("external-provider"),
            export_id="external-library",
            blob=BlobRef(
                hashlib.sha256(payload).hexdigest(),
                len(payload),
                media_type=source_product.artifact_export.media_type,
            ),
        )
        self.provider = _acceptance(original, provider_export)
        root_export = replace(
            source_product.artifact_export,
            dependency_artifact_identities=(provider_export.identity,),
        )
        self.root = _acceptance(original, root_export)
        graph_fixture = artifact_fixture.ArtifactGraphTests()
        graph = create_artifact_build_graph(
            build_system_driver_identity=exports.graph.build_system_driver_identity,
            manifests=(
                graph_fixture.manifest(root_export, dependencies=(provider_export,)),
                graph_fixture.manifest(provider_export),
            ),
            link_roots=(root_export.identity,),
        )
        product = LibraryArtifactProduct(provider_export, source_product.import_surface)
        self.exports = RetainedLibraryExportSet(
            graph,
            graph.link_plans[0].identity,
            tuple(
                sorted(
                    (replace(source_product, artifact_export=root_export), product),
                    key=lambda value: value.artifact_export.identity.uri,
                )
            ),
        )
        self.run = replace(
            run,
            build_evidence_identities=(self.root.build.identity,),
            acceptance_evidence_identities=(self.root.identity,),
            generated_test_evidence_identities=(self.root.generated_tests.identity,),
        )
        self.owner = object.__new__(BorrowedExternalQualifiedLibraries)
        self.owner._asset = SimpleNamespace(
            component_revision=root_export.component_revision,
            target_identity=self.run.target_profile_identity,
            authorization_identity=self.run.component_lock_identity,
            identity=canonical_identity("reviewed-root-asset"),
        )
        self.external = SimpleNamespace(
            accepted_receipts=(self.provider,), products=(product,)
        )
        self.projector = self.enterContext(
            mock.patch.object(
                runtime, "qualified_library_runtime_data", return_value=self.external
            )
        )
        self.guard = self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries, "require_current", autospec=True
            )
        )
        self.payloads = {root_export.blob: content, provider_export.blob: payload}
        self.reader = mock.Mock(side_effect=self.payloads.__getitem__)

    def capture(self, owner=True):
        return capture_qualification_run(
            self.run,
            self.exports,
            (self.root,),
            read_blob=self.reader,
            max_bytes=65536,
            **({"qualified_library_inputs": self.owner} if owner else {}),
        )

    def test_explicit_original_channel_preserves_root_membership_and_four_fields(self):
        captured = self.capture()
        self.assertEqual(captured.acceptances, (self.root,))
        self.assertEqual(
            captured.run.acceptance_evidence_identities, (self.root.identity,)
        )
        self.assertNotIn(
            self.provider.identity, captured.run.acceptance_evidence_identities
        )
        self.assertEqual(dict(captured.blobs), self.payloads)
        self.assertEqual(
            tuple(field.name for field in fields(QualificationRunCapture)),
            ("run", "exports", "acceptances", "blobs"),
        )

    def test_extra_graph_manifests_do_not_opt_in_to_provider_admission(self):
        with self.assertRaisesRegex(QualificationCaptureError, "export-mismatch"):
            self.capture(owner=False)
        self.projector.assert_not_called()
        self.reader.assert_not_called()

    def test_ordinary_receipts_cannot_restore_original_owner(self):
        with self.assertRaises(QualificationCaptureError):
            capture_qualification_run(
                self.run,
                self.exports,
                (self.root,),
                read_blob=self.reader,
                max_bytes=65536,
                qualified_library_inputs=(self.provider,),
            )
        self.reader.assert_not_called()

    def test_missing_original_external_receipt_keeps_exact_graph_equality(self):
        self.external.accepted_receipts = ()
        with self.assertRaisesRegex(QualificationCaptureError, "export-mismatch"):
            self.capture()
        self.reader.assert_not_called()

    def test_missing_original_product_cannot_be_synthesized_from_exports(self):
        self.external.products = ()
        with self.assertRaisesRegex(
            QualificationCaptureError, "qualified-input-subject-mismatch"
        ):
            self.capture()
        self.reader.assert_not_called()

    def test_foreign_root_lock_refuses_before_provider_or_blob_read(self):
        self.owner._asset.authorization_identity = canonical_identity("foreign-lock")
        with self.assertRaisesRegex(
            QualificationCaptureError, "qualified-input-subject-mismatch"
        ):
            self.capture()
        self.projector.assert_not_called()
        self.reader.assert_not_called()

    def test_original_guard_refusal_after_blob_callback_is_preserved(self):
        refusal = RuntimeError("original holder expired during capture")

        def expired(reference):
            self.guard.side_effect = refusal
            return self.payloads[reference]

        self.reader.side_effect = expired
        with self.assertRaises(RuntimeError) as caught:
            self.capture()
        self.assertIs(caught.exception, refusal)

    def test_consumer_run_cannot_change_during_foreign_blob_callback(self):
        def changed(reference):
            object.__setattr__(
                self.run,
                "project_receipt_identity",
                canonical_identity("changed-root-receipt"),
            )
            return self.payloads[reference]

        self.reader.side_effect = changed
        with self.assertRaisesRegex(
            QualificationCaptureError, "qualified-input-subject-mismatch"
        ):
            self.capture()

    def test_portable_origin_and_all_original_bytes_use_same_root_recorder(self):
        adapter = object.__new__(FilesystemStandardQualificationAdapter)
        origin = mock.Mock()
        adapter._original_qualified_library_inputs = self.owner
        adapter._original_qualified_library_archive_reader = origin
        adapter._qualified_capture_data = mock.Mock(return_value=self.external)
        adapter.max_capture_bytes = 65536
        payload = b"original bound provider archive envelope"
        raw_record = b"original digest-named provider history"
        record_id = ContentIdentity.parse_uri(
            "sha256:" + hashlib.sha256(raw_record).hexdigest()
        )
        archive_ref = BlobRef(
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            media_type="application/zip",
        )
        captured = CapturedQualifiedProviderArchive(
            canonical_identity("reviewed-binding"),
            canonical_identity("qualified-binding"),
            "original-store",
            archive_ref,
            payload,
            ((record_id, raw_record),),
        )
        recorder = QualificationEvidenceRecorder(max_bytes=65536, max_records=10)
        with mock.patch.object(
            original_archives,
            "read_qualified_library_archives",
            return_value=(captured,),
        ) as reader:
            adapter._capture_qualified_archives(recorder, self.owner, origin)
            self.assertIs(reader.call_args.args[0], self.owner)
            self.assertIs(reader.call_args.kwargs["read_archive"], origin)
            origin.assert_not_called()
        entries = dict(recorder.entries)
        self.assertEqual(
            entries[ContentIdentity.parse_uri(archive_ref.identity)], payload
        )
        self.assertEqual(entries[record_id], raw_record)
        self.assertIn(captured.identity, entries)
