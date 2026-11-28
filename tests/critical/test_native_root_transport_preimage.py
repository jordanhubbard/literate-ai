"""Binding preimages with real bounded CAS/recorder and modeled CLI observation.

The native capture controls use the existing original-owner protocol fixture.
No provider CLI, compiler or generated native process executes. Independent
promotion ancestry of an expected binding remains a caller precondition.
"""

import copy
import os
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_transport as transport
from literate_ai.adapters.models.coding_cli import CodingCliSelection
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
)
from literate_ai.application.native_root_run import NativeRootRunError
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.storage import FileSystemCAS
from tests.critical import test_native_root_preparation_retention as fixture
from tests.support import (
    fixtures_test_cached_coding_cli_source_generation_runner as source,
)


def _selection():
    return CodingCliSelection(
        "claude", "/private/nonexistent/provider-credential-path", "sha256:" + "e" * 64
    )


def _document(selection):
    return {
        "schema": "literate-ai/coding-cli-tool-binding@1",
        "coding_cli": selection.name,
        "executable_identity": selection.executable_identity,
        "isolation": selection.isolation.to_dict(),
    }


class NativeRootTransportPreimageTests(unittest.TestCase):
    def reader(self, document):
        recorder = QualificationEvidenceRecorder(max_bytes=100_000, max_records=10)
        identity = recorder.remember_json(document)
        return QualificationEvidenceReader(
            recorder.entries, max_bytes=100_000, max_records=10
        ), identity

    def test_exact_existing_binding_preimage_reopens_without_live_cli(self):
        selection = _selection()
        document = _document(selection)
        reader, identity = self.reader(document)
        self.assertEqual(identity.uri, selection.tool_binding_identity)
        with mock.patch.object(
            CodingCliSelection,
            "require_unchanged",
            side_effect=AssertionError("live CLI"),
        ):
            actual = transport.reopen_native_root_transport_preimage(
                reader,
                expected_provider_id=selection.name,
                expected_tool_binding_identity=identity,
            )
        self.assertEqual(actual.executable_identity, selection.executable_identity)
        self.assertEqual(actual.tool_binding_identity, identity.uri)
        self.assertEqual(actual.isolation.to_dict(), selection.isolation.to_dict())
        self.assertEqual(
            set(document), {"schema", "coding_cli", "executable_identity", "isolation"}
        )
        self.assertNotIn(selection.executable.encode(), canonical_json_bytes(document))

    def test_missing_independently_expected_binding_and_wrong_provider_refuse(self):
        reader, identity = self.reader(_document(_selection()))
        with self.assertRaisesRegex(QualificationCaptureError, "record-missing"):
            transport.reopen_native_root_transport_preimage(
                reader,
                expected_provider_id="claude",
                expected_tool_binding_identity=canonical_identity("other-binding"),
            )
        with self.assertRaisesRegex(
            transport.NativeRootTransportError, "preimage_changed"
        ):
            transport.reopen_native_root_transport_preimage(
                reader,
                expected_provider_id="codex",
                expected_tool_binding_identity=identity,
            )

    def test_changed_preimage_under_expected_identity_refuses(self):
        document = _document(_selection())
        reader, identity = self.reader(document)
        changed = copy.deepcopy(document)
        changed["isolation"]["hermetic"] = True
        with (
            mock.patch.object(reader, "read_json", return_value=changed),
            self.assertRaisesRegex(
                transport.NativeRootTransportError, "preimage_changed"
            ),
        ):
            transport.reopen_native_root_transport_preimage(
                reader,
                expected_provider_id="claude",
                expected_tool_binding_identity=identity,
            )

    def test_coherently_hashed_wrong_schema_extra_fields_and_bad_policy_types_refuse(
        self,
    ):
        for change in (
            {"schema": "unreviewed-binding"},
            {"executable": "/must-not-be-in-policy"},
            {"isolation": {**_document(_selection())["isolation"], "hermetic": 0}},
        ):
            reader, identity = self.reader({**_document(_selection()), **change})
            with (
                self.subTest(change=change),
                self.assertRaises(transport.NativeRootTransportError),
            ):
                transport.reopen_native_root_transport_preimage(
                    reader,
                    expected_provider_id="claude",
                    expected_tool_binding_identity=identity,
                )

    def test_absent_native_non_coding_source_keeps_legacy_record_call_shape(self):
        owned = source.CachedCodingCliSourceGenerationRunnerTests()
        self.addCleanup(owned.tearDown)
        owned.setUp()
        with (
            mock.patch.object(
                transport,
                "begin_native_root_transport_capture",
                side_effect=AssertionError("legacy admitted native transport"),
            ),
            mock.patch.object(
                owned.runner, "_record", wraps=owned.runner._record
            ) as record,
        ):
            owned.runner(owned.node)
        self.assertNotIn("native_transport_capture", record.call_args.kwargs)

    def test_cas_constructor_witness_is_immutable_and_passive_to_read(self):
        with tempfile.TemporaryDirectory() as directory:
            cas = FileSystemCAS(Path(directory) / "candidate-cas")
            expected = tuple(
                (path, (metadata.st_dev, metadata.st_ino, metadata.st_mode))
                for path in (cas.root, cas.blob_root)
                for metadata in (path.stat(),)
            )
            with mock.patch.object(
                Path, "stat", side_effect=AssertionError("new probe")
            ):
                witness = cas.original_namespace_witness
                self.assertIs(cas.original_namespace_witness, witness)
            self.assertEqual(witness, expected)
            self.assertIsInstance(witness, tuple)
            with self.assertRaises(AttributeError):
                cas.original_namespace_witness = ()


@unittest.skipUnless(os.name == "posix", "existing owned local POSIX protocol fixture")
class NativeRootTransportCaptureTests(unittest.TestCase):
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
    def capture(self, *, replace_before_capture=None):
        selection = _selection()
        cas = FileSystemCAS(self.root / "transport-candidate-cas")
        generator = SimpleNamespace(selection=selection)
        runner = SimpleNamespace(
            generator=generator,
            _original_source_generator=generator,
            _original_coding_cli_selection=selection,
            _original_coding_cli_binding=ContentIdentity.parse_uri(
                selection.tool_binding_identity
            ),
            retained_source=None,
            cas=cas,
            _original_candidate_cas=cas,
            _original_candidate_cas_root=cas.root,
            _original_candidate_blob_root=cas.blob_root,
            _original_candidate_namespace_witness=cas.original_namespace_witness,
        )
        generation = SimpleNamespace(
            coding_cli=selection.name,
            executable_identity=selection.executable_identity,
            coding_cli_tool_binding_identity=selection.tool_binding_identity,
            isolation_profile=selection.isolation.profile,
            hermetic=selection.isolation.hermetic,
        )
        guard = mock.Mock()

        def measure_original(original_selection):
            self.assertIs(original_selection, selection)
            guard()

        with (
            self.controller() as (scope, _sequence, controller),
            mock.patch.object(
                transport, "current_native_root_controller", return_value=controller
            ),
            mock.patch.object(
                CodingCliSelection, "require_unchanged", measure_original
            ),
        ):
            runner._original_coding_cli_guard = selection.require_unchanged
            replaced = None
            if replace_before_capture is not None:
                path = cas.root if replace_before_capture == "root" else cas.blob_root
                backup = path.with_name(path.name + "-original")
                path.rename(backup)
                path.mkdir(mode=0o700)
                replaced = path, backup
            try:
                capture = transport.begin_native_root_transport_capture(
                    controller, runner, self.node
                )
                yield capture, runner, generation, scope, guard
            finally:
                if replaced is not None:
                    path, backup = replaced
                    path.rmdir()
                    backup.rename(path)

    def test_original_capture_retains_same_binding_only_in_real_cas_and_recorder(self):
        with self.capture() as (capture, runner, generation, _scope, guard):
            expected = ContentIdentity.parse_uri(
                capture.selection.tool_binding_identity
            )
            capture.retain(generation)
            reader = QualificationEvidenceReader(
                self.recorder.entries,
                max_bytes=self.recorder.max_bytes,
                max_records=self.recorder.max_records,
            )
            self.assertEqual(reader.read_json(expected), _document(capture.selection))
            actual = transport.reopen_native_root_transport_preimage(
                reader,
                expected_provider_id="claude",
                expected_tool_binding_identity=expected,
            )
            self.assertEqual(actual.tool_binding_identity, expected.uri)
            reference = runner.cas.put_manifest(_document(capture.selection))
            self.assertEqual(
                runner.cas.get_bytes(reference),
                canonical_json_bytes(_document(capture.selection)),
            )
            self.assertGreater(guard.call_count, 2)

    def test_wrong_recorded_stage_binding_refuses_before_retention(self):
        with self.capture() as (capture, _runner, generation, scope, _guard):
            generation.coding_cli_tool_binding_identity = canonical_identity(
                "foreign-stage"
            ).uri
            with mock.patch.object(
                scope, "retain_record", wraps=scope.retain_record
            ) as retain:
                with self.assertRaisesRegex(
                    transport.NativeRootTransportError, "stage_transport_changed"
                ):
                    capture.retain(generation)
                retain.assert_not_called()

    def test_generator_selection_candidate_and_cas_substitution_refuse(self):
        for field in ("generator", "selection", "candidate", "cas"):
            with (
                self.subTest(field=field),
                self.capture() as (capture, runner, _generation, _scope, _guard),
            ):
                if field == "generator":
                    target, attribute, value = (
                        runner,
                        "generator",
                        SimpleNamespace(selection=capture.selection),
                    )
                elif field == "selection":
                    target, attribute, value = (
                        runner.generator,
                        "selection",
                        replace(capture.selection),
                    )
                elif field == "candidate":
                    target, attribute, value = (
                        capture.controller,
                        "prepared_candidate",
                        replace(self.node),
                    )
                else:
                    target, attribute, value = (
                        runner,
                        "cas",
                        FileSystemCAS(self.root / "foreign-candidate-cas"),
                    )
                with mock.patch.object(target, attribute, value):
                    with self.assertRaisesRegex(
                        transport.NativeRootTransportError, "original_custody_changed"
                    ):
                        capture.require_current()

    def test_physical_candidate_cas_root_replacement_refuses(self):
        with self.capture() as (capture, runner, _generation, _scope, _guard):
            root = capture.cas_root
            backup = root.with_name(root.name + "-original")
            root.rename(backup)
            root.mkdir()
            try:
                with self.assertRaisesRegex(
                    transport.NativeRootTransportError, "original_custody_changed"
                ):
                    capture.require_current()
                # A second candidate cannot silently adopt the replacement.
                with self.assertRaisesRegex(
                    transport.NativeRootTransportError, "original_custody_changed"
                ):
                    transport.begin_native_root_transport_capture(
                        capture.controller, runner, self.node
                    )
            finally:
                root.rmdir()
                backup.rename(root)

    def test_original_root_and_blob_namespace_replacement_before_first_capture_refuse(
        self,
    ):
        for namespace in ("root", "blob-root"):
            with (
                self.subTest(namespace=namespace),
                self.assertRaisesRegex(
                    transport.NativeRootTransportError, "original_custody_changed"
                ),
            ):
                with self.capture(replace_before_capture=namespace):
                    self.fail("first native capture adopted replacement namespace")

    def test_original_guard_callback_cannot_redirect_the_final_cas_check(self):
        with self.capture() as (capture, runner, _generation, _scope, guard):
            original = runner.cas

            def redirect():
                runner.cas = object()

            guard.side_effect = redirect
            try:
                with self.assertRaisesRegex(
                    transport.NativeRootTransportError, "original_custody_changed"
                ):
                    capture.require_current()
            finally:
                guard.side_effect = None
                runner.cas = original

    def test_closed_original_owner_cannot_retain_more_transport_records(self):
        with self.capture() as (capture, _runner, generation, _scope, _guard):
            before = self.recorder.entries
        with self.assertRaises(NativeRootRunError):
            capture.retain(generation)
        self.assertEqual(self.recorder.entries, before)

    def test_later_capture_cannot_readopt_changed_original_selection_value(self):
        with self.capture() as (capture, runner, _generation, _scope, _guard):
            original = capture.selection.executable_identity
            object.__setattr__(
                capture.selection,
                "executable_identity",
                canonical_identity("changed").uri,
            )
            try:
                with self.assertRaisesRegex(
                    transport.NativeRootTransportError, "original_binding_changed"
                ):
                    transport.begin_native_root_transport_capture(
                        capture.controller, runner, self.node
                    )
            finally:
                object.__setattr__(capture.selection, "executable_identity", original)

    def test_post_admission_noop_guard_substitution_cannot_remove_measurement(self):
        with self.capture() as (capture, _runner, _generation, _scope, guard):
            substituted = mock.Mock()
            for replacement in (substituted, property(substituted)):
                with mock.patch.object(
                    CodingCliSelection, "require_unchanged", replacement
                ):
                    with self.assertRaisesRegex(
                        transport.NativeRootTransportError, "original_custody_changed"
                    ):
                        capture.require_current()
            substituted.assert_not_called()
            before = guard.call_count
            capture.require_current()
            self.assertGreater(guard.call_count, before)

    def test_hostile_annotation_baseexception_cannot_mask_primary(self):
        class HostileNotes(RuntimeError):
            @property
            def __notes__(self):
                raise self.annotation_failure

        for annotation_failure in (KeyboardInterrupt(), SystemExit(19)):
            with self.subTest(kind=type(annotation_failure).__name__):
                with self.capture() as (capture, runner, _generation, _scope, _guard):
                    primary = HostileNotes("primary modeled generation refusal")
                    primary.annotation_failure = annotation_failure
                    old = runner.cas
                    try:
                        with self.assertRaises(HostileNotes) as raised:
                            with capture.guarded():
                                runner.cas = object()
                                raise primary
                        self.assertIs(raised.exception, primary)
                    finally:
                        runner.cas = old

    def test_primary_generation_and_recording_errors_survive_closing_refusal(self):
        for phase in ("generation", "recording"):
            with (
                self.subTest(phase=phase),
                self.capture() as (capture, runner, generation, scope, _guard),
            ):
                primary = RuntimeError("primary modeled " + phase + " error")
                old = runner.cas

                def fail(*_args, original_error=primary, original_runner=runner):
                    original_runner.cas = object()
                    raise original_error

                try:
                    with self.assertRaises(RuntimeError) as raised:
                        if phase == "generation":
                            with capture.guarded():
                                fail()
                        else:
                            with mock.patch.object(
                                scope, "retain_record", side_effect=fail
                            ):
                                capture.retain(generation)
                    self.assertIs(raised.exception, primary)
                    self.assertIn(
                        "original native source transport closing guard refused",
                        raised.exception.__notes__,
                    )
                finally:
                    runner.cas = old
