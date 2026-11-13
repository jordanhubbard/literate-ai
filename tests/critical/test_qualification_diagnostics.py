"""Actual parity subprocesses at the adapter boundary, without model generation."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    encode_directory_export,
    read_directory_export,
)
from literate_ai.adapters.evidence_storage import FileSystemEvidenceStore
from literate_ai.adapters.qualification import (
    FilesystemQualificationError,
    FilesystemQualificationParityVerifier,
    _observe,
)
from literate_ai.adapters.qualification_archive import reopen_qualification_archive
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceRecorder,
)
from literate_ai.adapters.qualification_diagnostics import (
    encode_qualification_failure_diagnostic,
    publish_qualification_failure_diagnostic,
    reopen_qualification_failure_diagnostic,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.source_to_specification import SourceToSpecificationError
from literate_ai.source_to_specification.host_qualification import (
    LocalQualificationCase,
    LocalQualificationProfile,
)
from literate_ai.source_to_specification.inventory import inventory_source
from literate_ai.source_to_specification.qualification_lifecycle import (
    QualificationLifecycleRunner,
)
from tests.critical import test_qualification_capture as captures


def reference(content):
    return BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/zip"
    )


class QualificationDiagnosticTests(unittest.TestCase):
    def failed_process_fixture(
        self,
        root,
        *,
        invalid_json=False,
        later_run=False,
        timeout=False,
        missing_executable=False,
    ):
        adapter, plan, _, _, _ = captures.QualificationCaptureTests().adapter_fixture()
        source = root / "original"
        source.mkdir()
        (source / "reference.py").write_text('print("{\\"value\\":1}")\n')
        snapshot = ContentIdentity.parse_uri(inventory_source(source).identity)
        lifecycle = adapter.lifecycle
        lifecycle.generated_roots = {}
        lifecycle.root_generated_roots = {}
        lifecycle.run_roots = {}
        for ordinal, run in enumerate(plan.run_identities):
            generated = root / f"run-{ordinal}"
            (generated / "source").mkdir(parents=True)
            script = (
                'print("{\\"value\\":1}")\n'
                if later_run and ordinal == 0
                else (
                    "import json,os,sys,time\n"
                    'print(json.dumps({"pid":os.getpid()}),flush=True)\n'
                    'sys.stderr.write("original-timeout-marker\\n")\nsys.stderr.flush()\ntime.sleep(10)\n'
                )
                if timeout
                else (
                    'import sys\nsys.stderr.write("original-parity-marker\\n")\n'
                    + (
                        'print("invalid JSON")\n'
                        if invalid_json
                        else "raise SystemExit(7)\n"
                    )
                )
            )
            (generated / "source/generated.py").write_text(script)
            tree = ContentIdentity.parse_uri(inventory_source(generated).identity)
            lifecycle.generated_roots[run.uri] = ((tree, generated),)
            lifecycle.root_generated_roots[run.uri] = generated
            lifecycle.run_roots[run.uri] = generated
        profile = LocalQualificationProfile(
            "failure-diagnostic-fixture@1",
            (sys.executable, "-c", "pass"),
            ((sys.executable, "-c", "pass"),),
            (sys.executable, "-I", "-S", str(source / "reference.py")),
            (
                (str(root / "missing-qualification-tool"),)
                if missing_executable
                else (sys.executable, "-I", "-S", "{workspace}/source/generated.py")
            ),
            (LocalQualificationCase("case-value", (), {"value": 1}),),
            ("value",),
            timeout_seconds=1 if timeout else 10,
            maximum_output_bytes=4096,
        )
        verifier = FilesystemQualificationParityVerifier(
            source_root=source,
            source_snapshot_identity=snapshot,
            profile=profile,
            lifecycle=lifecycle,
        )
        plan = replace(
            plan, source_snapshot_identity=snapshot, case_map=verifier.case_map
        )
        adapter.parity = verifier

        def run(actual_plan):
            for run_identity in actual_plan.run_identities:
                trees = tuple(
                    item[0] for item in lifecycle.generated_roots[run_identity.uri]
                )
                parity = verifier.verify(
                    run_identity=run_identity,
                    source_snapshot_identity=snapshot,
                    generated_tree_identities=trees,
                    case_map=actual_plan.case_map,
                )
                QualificationLifecycleRunner._covered_surfaces(
                    actual_plan, parity, trees, run_identity
                )
            self.fail("fixture must reach the real parity refusal")

        adapter.runner = SimpleNamespace(run=run)
        return adapter, plan

    def test_timeout_retains_partial_streams_and_the_active_run_case(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            adapter, plan = self.failed_process_fixture(root, timeout=True)
            with self.assertRaises(FilesystemQualificationError) as failure:
                adapter.qualify(plan)
            self.assertEqual(
                failure.exception.code, "qualification.parity_command_failed"
            )
            ref = publish_qualification_failure_diagnostic(
                root / "retained",
                plan,
                failure.exception.code,
                adapter.diagnostic_evidence_blobs,
                max_bytes=adapter.max_capture_bytes,
                case_records=adapter.diagnostic_case_record_identities,
                active_case=adapter.diagnostic_active_case,
            )
            content = FileSystemEvidenceStore(root / "retained/diagnostics").get_bytes(
                ref
            )
            diagnostic = reopen_qualification_failure_diagnostic(
                content, ref, max_bytes=adapter.max_capture_bytes, max_records=100_000
            )
            active = diagnostic.active_case
            self.assertEqual(active["run_identity"], plan.run_identities[0].uri)
            self.assertEqual(active["case_id"], "case-value")
            self.assertEqual(active["process_role"], "generated")
            self.assertEqual(active["process_status"], "timeout")
            self.assertEqual(active["capture_status"], "available")
            self.assertIsNone(active["generated_observation_identity"])
            self.assertEqual(diagnostic.case_records, ())
            self.assertEqual(
                diagnostic.records.read_bytes(
                    ContentIdentity.parse_uri(active["partial_stderr_identity"])
                ),
                b"original-timeout-marker\n",
            )
            child = json.loads(
                diagnostic.records.read_bytes(
                    ContentIdentity.parse_uri(active["partial_stdout_identity"])
                )
            )
            if os.name != "nt":
                with self.assertRaises(ProcessLookupError):
                    os.kill(child["pid"], 0)
            self.assertIsNone(adapter.lifecycle.diagnostic_active_case)
            self.assertEqual(adapter.library_captures, ())
            self.assertEqual(adapter.evidence_blobs, ())

            files = read_directory_export(
                content, ref, max_bytes=adapter.max_capture_bytes, max_entries=100_000
            )
            for field in ("run_identity", "partial_stderr_identity"):
                header = json.loads(
                    next(
                        item.content for item in files if item.path == "diagnostic.json"
                    )
                )
                header["active_case"][field] = "sha256:" + "f" * 64
                altered = encode_directory_export(
                    tuple(
                        DirectoryExportFile(
                            item.path,
                            canonical_json_bytes(header)
                            if item.path == "diagnostic.json"
                            else item.content,
                            item.mode,
                        )
                        for item in files
                    ),
                    max_bytes=adapter.max_capture_bytes,
                    max_entries=100_000,
                )
                with self.subTest(field=field), self.assertRaises(ValueError):
                    reopen_qualification_failure_diagnostic(
                        altered,
                        reference(altered),
                        max_bytes=adapter.max_capture_bytes,
                        max_records=100_000,
                    )

    def test_timeout_retention_bounds_never_replace_the_original_refusal(self):
        for budget, status in ((1000, "output_limit"), (1, "retention_unavailable")):
            with (
                self.subTest(budget=budget),
                tempfile.TemporaryDirectory() as temporary,
            ):
                recorder = QualificationEvidenceRecorder(
                    max_bytes=budget, max_records=100
                )
                expired = subprocess.TimeoutExpired(
                    ("fixture-command",), 1, output=b"x" * 17, stderr=b"kept"
                )
                with patch(
                    "literate_ai.adapters.qualification.run_with_tree_kill",
                    side_effect=expired,
                ):
                    with self.assertRaises(FilesystemQualificationError) as failure:
                        _observe(
                            ("fixture-command",),
                            cwd=Path(temporary),
                            environment={},
                            timeout_seconds=1,
                            maximum_output_bytes=16,
                            recorder=recorder,
                        )
                self.assertEqual(
                    failure.exception.code, "qualification.parity_command_failed"
                )
                self.assertIs(failure.exception.__cause__, expired)
                self.assertEqual(failure.exception.diagnostic_capture_status, status)
                self.assertLessEqual(recorder.retained_bytes, budget)
                self.assertNotIn(
                    b"x" * 17, [payload for _, payload in recorder.entries]
                )

    def test_launch_failure_binds_the_active_case_without_an_invented_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            adapter, plan = self.failed_process_fixture(root, missing_executable=True)
            with self.assertRaises(FilesystemQualificationError) as failure:
                adapter.qualify(plan)
            ref = publish_qualification_failure_diagnostic(
                root / "retained",
                plan,
                failure.exception.code,
                adapter.diagnostic_evidence_blobs,
                max_bytes=adapter.max_capture_bytes,
                active_case=adapter.diagnostic_active_case,
            )
            content = FileSystemEvidenceStore(root / "retained/diagnostics").get_bytes(
                ref
            )
            diagnostic = reopen_qualification_failure_diagnostic(
                content, ref, max_bytes=adapter.max_capture_bytes, max_records=100_000
            )
            active = diagnostic.active_case
            self.assertEqual(active["run_identity"], plan.run_identities[0].uri)
            self.assertEqual(active["case_id"], "case-value")
            self.assertEqual(active["process_status"], "launch_failed")
            self.assertIsNotNone(active["baseline_observation_identity"])
            self.assertIsNone(active["generated_observation_identity"])
            self.assertIsNone(active["partial_stdout_identity"])
            self.assertIsNone(active["partial_stderr_identity"])
            self.assertEqual(adapter.library_captures, ())
            self.assertEqual(adapter.evidence_blobs, ())

    def test_original_process_failure_records_survive_and_cannot_admit_products(self):
        for invalid_json, later_run in ((False, False), (True, False), (False, True)):
            with self.subTest(invalid_json=invalid_json, later_run=later_run):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary).resolve()
                    adapter, plan = self.failed_process_fixture(
                        root, invalid_json=invalid_json, later_run=later_run
                    )
                    with self.assertRaises(SourceToSpecificationError) as failure:
                        adapter.qualify(plan)
                    self.assertEqual(
                        failure.exception.code, "qualification_lifecycle.parity_failed"
                    )
                    self.assertEqual(adapter.library_captures, ())
                    self.assertEqual(adapter.evidence_blobs, ())
                    self.assertIsNone(adapter.lifecycle.evidence_recorder)
                    self.assertEqual(adapter.lifecycle.product_sources, {})
                    ref = publish_qualification_failure_diagnostic(
                        root / "retained",
                        plan,
                        failure.exception.code,
                        adapter.diagnostic_evidence_blobs,
                        max_bytes=adapter.max_capture_bytes,
                        case_records=adapter.diagnostic_case_record_identities,
                    )
                    content = FileSystemEvidenceStore(
                        root / "retained/diagnostics"
                    ).get_bytes(ref)
                    reopened = reopen_qualification_failure_diagnostic(
                        content,
                        ref,
                        max_bytes=adapter.max_capture_bytes,
                        max_records=100_000,
                    )
                    self.assertEqual(reopened.plan, plan)
                    self.assertEqual(len(reopened.case_records), 2 if later_run else 1)
                    cases = [
                        reopened.records.read_json(item)
                        for item in reopened.case_records
                    ]
                    failed = next(item for item in cases if not item["case"]["passed"])
                    case = failed["case"]
                    generated = reopened.records.read_json(
                        ContentIdentity.from_dict(
                            case["generated_observation_identity"]
                        )
                    )
                    self.assertEqual(generated["exit_status"], 0 if invalid_json else 7)
                    self.assertFalse(generated["json_output_valid"])
                    self.assertEqual(
                        reopened.records.read_bytes(
                            ContentIdentity.parse_uri(generated["stderr"])
                        ),
                        b"original-parity-marker\n",
                    )
                    if later_run:
                        self.assertTrue(any(item["case"]["passed"] for item in cases))
                        self.assertEqual(
                            failed["run_identity"], plan.run_identities[1].uri
                        )
                    with self.assertRaisesRegex(
                        QualificationCaptureError, "archive.member-invalid"
                    ):
                        reopen_qualification_archive(
                            content,
                            ref,
                            max_bytes=adapter.max_capture_bytes,
                            max_records=100_000,
                        )

    def test_later_adapter_failure_drops_every_prior_qualified_capture(self):
        adapter, plan, _, _, _ = captures.QualificationCaptureTests().adapter_fixture()
        adapter.qualify(plan)
        self.assertTrue(adapter.library_captures)
        self.assertTrue(adapter.evidence_blobs)

        def fail(_plan):
            adapter.lifecycle.evidence_recorder.remember_bytes(
                b"only the new failed attempt"
            )
            raise FilesystemQualificationError("qualification.failed", "failed attempt")

        adapter.runner = SimpleNamespace(run=fail)
        with self.assertRaises(FilesystemQualificationError):
            adapter.qualify(plan)
        self.assertEqual(adapter.library_captures, ())
        self.assertEqual(adapter.evidence_blobs, ())
        self.assertEqual(adapter.diagnostic_case_record_identities, ())
        self.assertEqual(
            [payload for _, payload in adapter.diagnostic_evidence_blobs],
            [b"only the new failed attempt"],
        )

    def test_rehashed_success_header_and_cross_plan_case_records_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            adapter, plan = self.failed_process_fixture(Path(temporary).resolve())
            with self.assertRaises(SourceToSpecificationError):
                adapter.qualify(plan)
            content = encode_qualification_failure_diagnostic(
                plan,
                "qualification.failed",
                adapter.diagnostic_evidence_blobs,
                max_bytes=adapter.max_capture_bytes,
                max_records=100_000,
                case_records=adapter.diagnostic_case_record_identities,
            )
            files = read_directory_export(
                content, reference(content), max_bytes=1_000_000, max_entries=100_000
            )
            for changed in ("outcome", "run_identities"):
                document = json.loads(
                    next(
                        item.content for item in files if item.path == "diagnostic.json"
                    )
                )
                if changed == "outcome":
                    document["outcome"] = "passed"
                else:
                    document["plan"]["run_identities"] = [
                        "sha256:" + "a" * 64,
                        "sha256:" + "b" * 64,
                    ]
                replaced = tuple(
                    DirectoryExportFile(
                        item.path,
                        canonical_json_bytes(document)
                        if item.path == "diagnostic.json"
                        else item.content,
                        item.mode,
                    )
                    for item in files
                )
                altered = encode_directory_export(
                    replaced, max_bytes=1_000_000, max_entries=100_000
                )
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    reopen_qualification_failure_diagnostic(
                        altered,
                        reference(altered),
                        max_bytes=1_000_000,
                        max_records=100_000,
                    )

    def test_existing_byte_and_record_bounds_include_diagnostic_metadata(self):
        _, plan, _, _, _ = captures.QualificationCaptureTests().adapter_fixture()
        payload = b"retained stream"
        entries = (
            (
                ContentIdentity.parse_uri(
                    "sha256:" + hashlib.sha256(payload).hexdigest()
                ),
                payload,
            ),
        )
        for limits in ((64, 100), (1_000_000, 1)):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                encode_qualification_failure_diagnostic(
                    plan,
                    "qualification.failed",
                    entries,
                    max_bytes=limits[0],
                    max_records=limits[1],
                )

    def test_stream_bytes_cannot_assign_themselves_a_case_role(self):
        _, plan, _, _, _ = captures.QualificationCaptureTests().adapter_fixture()
        recorder = QualificationEvidenceRecorder(max_bytes=100_000, max_records=100)
        forged = {
            "schema": "literate-ai/qualification-diagnostic-case@1",
            "run_identity": "sha256:" + "f" * 64,
            "case": {"untrusted": "process stdout"},
        }
        identity = recorder.remember_bytes(canonical_json_bytes(forged))
        self.assertEqual(recorder.diagnostic_case_record_identities, ())
        content = encode_qualification_failure_diagnostic(
            plan,
            "qualification.failed",
            recorder.entries,
            max_bytes=100_000,
            max_records=100,
        )
        diagnostic = reopen_qualification_failure_diagnostic(
            content,
            reference(content),
            max_bytes=100_000,
            max_records=100,
        )
        self.assertEqual(diagnostic.case_records, ())
        self.assertEqual(diagnostic.records.read_json(identity), forged)
