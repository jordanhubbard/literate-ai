"""Bounded external archive/receipt joins with explicitly MODELED live guards.

Typed fixture lifecycles, records, acceptance DAGs and ZIP/CAS codecs are real.
Provider/native observations in the reused fixture and the receiving live owner
seams here are modeled source protocols, never native qualification evidence.
No native processes, remote readers or execution grants are supplied by these
controls. The real archive decoder and all exact-record joins remain active.
"""

import hashlib
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_qualification as replay
from literate_ai.adapters.native_root_external_libraries import (
    BorrowedExternalQualifiedLibraries,
)
from literate_ai.adapters.native_root_qualified_provider import (
    HeldNativeRootQualifiedProvider,
)
from literate_ai.adapters.qualification_archive import encode_qualification_archive
from literate_ai.adapters.qualification_capture import (
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
    reopen_qualification_lifecycle,
)
from literate_ai.adapters.retained_cargo_import import RetainedCargoImportInputs
from literate_ai.adapters.retained_cargo_import_v2 import RetainedCargoCurrentInputsV2
from literate_ai.adapters.retained_cargo_review_v2 import RetainedCargoReviewedFilesV2
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity
from tests.support import fixtures_test_qualification_capture as capture_fixtures


class ExternalQualificationRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = capture_fixtures.QualificationCaptureTests()
        cls.result, cls.captures, cls.records = fixture.typed_product_fixture()
        cls.lock = fixture.current_lock
        cls.capture = cls.captures[0]
        cls.lifecycle = reopen_qualification_lifecycle(
            QualificationEvidenceReader(
                cls.records, max_bytes=10_000_000, max_records=10_000
            ),
            cls.capture.run.lifecycle_result_identity,
        )
        cls.payload = encode_qualification_archive(
            cls.records, max_bytes=10_000_000, max_records=10_000
        )
        cls.reference = BlobRef(
            hashlib.sha256(cls.payload).hexdigest(),
            len(cls.payload),
            media_type="application/zip",
        )

    def setUp(self):
        self.binding = SimpleNamespace(
            identity=canonical_identity("modeled independently reviewed binding"),
            common=SimpleNamespace(
                source_store_id="original-provider-store",
                qualification_archive=self.reference,
            ),
        )
        self.holder = object.__new__(HeldNativeRootQualifiedProvider)
        self.materialized = SimpleNamespace(
            files=SimpleNamespace(reviewed=SimpleNamespace(binding=self.binding)),
            capture=self.capture,
        )
        self.holder._materialized = self.materialized
        self.selection = SimpleNamespace(
            provider_component_revision=self.lock.root_revision
        )
        self.inputs = object.__new__(BorrowedExternalQualifiedLibraries)
        self.inputs._asset = object()
        self.inputs._members = ((self.selection, self.holder),)
        self.provider = SimpleNamespace(
            binding=SimpleNamespace(
                identity=canonical_identity("modeled original held dependency"),
                component_revision=self.lock.root_revision,
            ),
            qualification_result=self.result,
            run=self.capture.run,
            lifecycle=self.lifecycle,
        )
        self.projection = SimpleNamespace(providers=(self.provider,))
        self.runtime = object()
        # Only receiving authority/currentness is modeled. Never replace the
        # archive reader, archive helper or exact result/run/lifecycle joins.
        self.actual_selection = replay.require_current_qualified_library_selection
        self.selection_guard = self.enterContext(
            mock.patch.object(replay, "require_current_qualified_library_selection")
        )
        self.runtime_read = self.enterContext(
            mock.patch(
                "literate_ai.adapters.native_root_external_runtime."
                "qualified_library_runtime_data",
                return_value=self.runtime,
            )
        )
        self.owner_guard = self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries, "require_current", autospec=True
            )
        )
        self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries,
                "data_projection",
                autospec=True,
                return_value=self.projection,
            )
        )

    def reader(self, *, omit=(), include_payload=True):
        recorder = QualificationEvidenceRecorder(
            max_bytes=20_000_000, max_records=20_000
        )
        for identity, payload in self.records:
            if identity not in omit:
                self.assertEqual(recorder.remember_bytes(payload), identity)
        if include_payload:
            recorder.remember_bytes(self.payload)
        return QualificationEvidenceReader(
            recorder.entries, max_bytes=20_000_000, max_records=20_000
        )

    def reopen(self, reader=None):
        return replay.require_qualified_library_archive_records(
            reader or self.reader(), self.inputs, component_lock=self.lock
        )

    def test_original_archive_all_records_and_exact_provider_subject_join(self):
        reader = self.reader()
        self.assertIs(self.reopen(reader), self.runtime)
        self.runtime_read.assert_called_with(self.inputs, self.lock.root_revision)
        self.assertEqual(
            reader.read_json(self.capture.run.lifecycle_result_identity),
            self.lifecycle.identity_document(),
        )
        self.assertEqual(reader.read_json(self.result.identity), self.result.to_dict())
        self.assertGreater(self.owner_guard.call_count, 0)
        self.assertFalse(hasattr(self.runtime, "require_current"))

    def test_loose_inner_records_without_original_payload_do_not_select_archive(self):
        with self.assertRaisesRegex(ValueError, "record-missing"):
            self.reopen(self.reader(include_payload=False))

    def test_original_archive_payload_does_not_replace_required_outer_records(self):
        with self.assertRaisesRegex(ValueError, "record-missing"):
            self.reopen(self.reader(omit=(self.result.identity,)))

    def test_other_real_run_cannot_be_joined_to_original_lifecycle(self):
        self.provider.run = self.captures[1].run
        with self.assertRaisesRegex(ValueError, "original_provider_subject_changed"):
            self.reopen()

    def test_other_real_export_set_cannot_replace_original_capture(self):
        self.materialized.capture = self.captures[1]
        # Its lifecycle is still first run: selected membership and original
        # export document alone cannot make another product the held subject.
        self.provider.run = self.captures[1].run
        with self.assertRaisesRegex(ValueError, "original_provider_subject_changed"):
            self.reopen()

    def test_first_live_callback_cannot_readopt_holder_or_members(self):
        original = self.inputs._members

        def substitute(*args):
            self.inputs._members = tuple(list(original))
            return self.runtime

        self.runtime_read.side_effect = substitute
        with self.assertRaisesRegex(ValueError, "original_owner_changed"):
            self.reopen()

    def test_first_live_callback_cannot_readopt_original_archive_ref(self):
        def substitute(*args):
            self.binding.common.qualification_archive = BlobRef("0" * 64, 1)
            return self.runtime

        self.runtime_read.side_effect = substitute
        with self.assertRaises(ValueError):
            self.reopen()

    def test_original_guard_failure_remains_same_error(self):
        failure = RuntimeError("original receiving owner closed")
        self.owner_guard.side_effect = failure
        with self.assertRaises(RuntimeError) as caught:
            self.reopen()
        self.assertIs(caught.exception, failure)

    def test_none_noasset_never_queries_live_owner_or_archive(self):
        self.assertIsNone(
            replay.require_qualified_library_archive_records(
                self.reader(), None, component_lock=self.lock
            )
        )
        self.runtime_read.assert_not_called()
        self.owner_guard.assert_not_called()

    def test_real_absent_asset_none_selection_has_no_live_callbacks(self):
        self.actual_selection(None, component_lock=self.lock)
        self.runtime_read.assert_not_called()
        self.owner_guard.assert_not_called()

    def test_declared_asset_without_owner_is_never_archive_selected(self):
        from literate_ai.contracts.native_root_external_libraries import (
            QUALIFIED_LIBRARY_ASSET_ROLE,
        )

        with mock.patch(
            "literate_ai.application.component_execution_planning."
            "authored_assets_from_lock",
            return_value=(SimpleNamespace(role=QUALIFIED_LIBRARY_ASSET_ROLE),),
        ):
            with self.assertRaisesRegex(ValueError, "current_owner_required"):
                self.actual_selection(None, component_lock=self.lock)
        self.runtime_read.assert_not_called()
        self.owner_guard.assert_not_called()

    def test_actual_receipt_dag_keeps_own_membership_separate(self):
        own = tuple(
            row
            for row in self.capture.acceptances
            if row.component_revision == self.lock.root_revision
        )
        external = tuple(row for row in self.capture.acceptances if row not in own)
        self.assertEqual(len(own), 1)
        self.assertTrue(external)
        # The capture fixture has late artifact-graph edges, not export receipt
        # edges. Model an explicit typed B -> A receipt DAG for this pure selector;
        # these adjusted records are not qualification or native observations.
        before = self.capture.acceptances
        exports = tuple(
            replace(
                row,
                dependency_artifact_identities=(external[0].build.exports[0].identity,),
            )
            for row in own[0].build.exports
        )
        identities = tuple(row.identity for row in exports)
        build = replace(
            own[0].build,
            exports=exports,
            resolved_sbom_export_identities=identities,
        )
        own = (
            replace(
                own[0],
                build=build,
                generated_tests=replace(
                    own[0].generated_tests,
                    build_evidence_identity=build.identity,
                    export_identities=identities,
                ),
                execution=replace(
                    own[0].execution,
                    build_evidence_identity=build.identity,
                    export_identities=identities,
                    root_export_identity=next(
                        new.identity
                        for old, new in zip(own[0].build.exports, exports, strict=True)
                        if old.identity == own[0].execution.root_export_identity
                    ),
                ),
            ),
        )
        roots = tuple(sorted(own[0].build.exports, key=lambda row: row.identity.uri))
        selected = replay.select_qualified_provider_receipt_closure(
            roots, own, external
        )
        self.assertEqual(
            {row.identity for row in selected},
            {own[0].identity, external[0].identity},
        )
        self.assertIs(self.capture.acceptances, before)
        self.assertEqual(len(own), 1)
        self.assertNotEqual(selected, own)
        with self.assertRaisesRegex(ValueError, "no accepted receipt"):
            replay.select_qualified_provider_receipt_closure(roots, own)
        with self.assertRaisesRegex(ValueError, "receipt_overlap"):
            replay.select_qualified_provider_receipt_closure(roots, own, own)

    def test_no_native_acceptance_or_root_membership_is_manufactured(self):
        before = self.capture.acceptances
        self.reopen()
        self.assertIs(self.capture.acceptances, before)
        self.assertEqual(
            self.capture.run.lifecycle_result_identity, self.lifecycle.identity
        )
        self.assertFalse(hasattr(self.runtime, "accepted"))
        self.assertFalse(hasattr(self.runtime, "native_root_execution"))


class ExternalCurrentOwnerPointerTests(unittest.TestCase):
    """Modeled original guard delegates; actual CurrentV2 pointer protocol."""

    def setUp(self):
        self.reviewed = object.__new__(RetainedCargoReviewedFilesV2)
        self.current = object.__new__(RetainedCargoImportInputs)
        object.__setattr__(self.current, "authority", SimpleNamespace(lock=object()))
        self.owner = object.__new__(BorrowedExternalQualifiedLibraries)
        self.other = object.__new__(BorrowedExternalQualifiedLibraries)
        self.selection = self.enterContext(
            mock.patch.object(replay, "require_current_qualified_library_selection")
        )
        self.review_guard = self.enterContext(
            mock.patch.object(
                RetainedCargoReviewedFilesV2, "require_unchanged", autospec=True
            )
        )
        self.current_guard = mock.Mock()
        object.__setattr__(self.current, "require_unchanged", self.current_guard)
        self.owner_guard = self.enterContext(
            mock.patch.object(
                BorrowedExternalQualifiedLibraries, "require_current", autospec=True
            )
        )

    def test_policy_absent_still_holds_exact_independent_owner(self):
        value = RetainedCargoCurrentInputsV2(
            self.reviewed, self.current, qualified_library_inputs=self.owner
        )
        self.assertIsNone(value.native_root_ingress)
        value.require_unchanged()
        self.owner_guard.assert_called_once_with(self.owner)
        self.assertIs(value.qualified_library_inputs, self.owner)
        self.assertIs(value._original_qualified_library_inputs, self.owner)

    def test_none_keeps_old_shape_and_no_owner_callback(self):
        value = RetainedCargoCurrentInputsV2(self.reviewed, self.current)
        value.require_unchanged()
        self.assertIsNone(value.qualified_library_inputs)
        self.owner_guard.assert_not_called()

    def test_replacement_before_first_guard_never_runs_foreign_owner(self):
        value = RetainedCargoCurrentInputsV2(
            self.reviewed, self.current, qualified_library_inputs=self.owner
        )
        object.__setattr__(value, "qualified_library_inputs", self.other)
        with self.assertRaisesRegex(ValueError, "owner-changed"):
            value.require_unchanged()
        self.review_guard.assert_not_called()
        self.current_guard.assert_not_called()
        self.owner_guard.assert_not_called()

    def test_first_foreign_callback_cannot_readopt_replacement_owner(self):
        value = RetainedCargoCurrentInputsV2(
            self.reviewed, self.current, qualified_library_inputs=self.owner
        )
        self.review_guard.side_effect = lambda *args: object.__setattr__(
            value, "qualified_library_inputs", self.other
        )
        with self.assertRaisesRegex(ValueError, "owner-changed"):
            value.require_unchanged()
        self.owner_guard.assert_not_called()

    def test_closing_foreign_guard_cannot_return_substituted_owner(self):
        value = RetainedCargoCurrentInputsV2(
            self.reviewed, self.current, qualified_library_inputs=self.owner
        )
        calls = 0

        def closing(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                object.__setattr__(value, "qualified_library_inputs", self.other)

        self.review_guard.side_effect = closing
        with self.assertRaisesRegex(ValueError, "owner-changed"):
            value.require_unchanged()
        self.owner_guard.assert_called_once_with(self.owner)

    def test_original_owner_error_identity_preserved(self):
        value = RetainedCargoCurrentInputsV2(
            self.reviewed, self.current, qualified_library_inputs=self.owner
        )
        error = RuntimeError("original owner refused")
        self.owner_guard.side_effect = error
        with self.assertRaises(RuntimeError) as caught:
            value.require_unchanged()
        self.assertIs(caught.exception, error)
