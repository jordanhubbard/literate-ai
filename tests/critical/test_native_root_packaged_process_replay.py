"""Real typed package records with modeled successful/failed process streams.

These data controls compare the existing positive-root wrapper with its extracted
closed-coordinate implementation. They execute no generated/native command and
establish neither historical qualification nor caller trust.
"""

import json
import os
import unittest
from dataclasses import replace

from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
    capture_lifecycle_records,
    verify_qualification_packaged_library_processes,
)
from tests.critical import test_native_root_binding as fixture
from tests.support import fixtures_test_standard_project_lifecycle as model


@unittest.skipUnless(os.name == "posix", "existing typed model setup")
class NativeRootPackagedProcessReplayTests(unittest.TestCase):
    def setUp(self):
        fixture.NativeRootBindingTests.setUp(self)
        names = {self.lock.root_revision.uri: "qualified-fixture"}
        ports = model.ContractEvidenceLifecyclePorts(
            self.execution, names, library_exports=True
        )
        ports.artifact_target_identity = self.lock.target_profile_identity
        self.lifecycle = model._service(ports).execute(
            self.execution,
            component_lock=self.lock,
            invalidation=model._decision(
                self.execution, names, "qualified-fixture", ("qualified-fixture",)
            ),
            prepared_nodes={self.lock.root_revision.uri: self.node},
            max_parallelism=1,
        )
        self.root = self.lifecycle.root_integration
        self.tests = self.lifecycle.node_results[0].generated_test_evidence
        self.recorder = QualificationEvidenceRecorder(
            max_bytes=16 * 1024**2, max_records=2000
        )
        capture_lifecycle_records(self.lifecycle, self.recorder)

    def records(
        self, *, returncode=0, phase="packaged-root-generated-test", cases=None
    ):
        if cases is None:
            cases = [
                {"case_id": item.case_id, "outcome": "passed"}
                for item in self.tests.cases
            ]
        stderr = self.recorder.remember_json("")
        test_stdout = self.recorder.remember_json(
            json.dumps(
                {
                    "schema": "literate-ai/generated-test-results@1",
                    "cases": cases,
                }
            )
        )
        execute_stdout = self.recorder.remember_json("modeled smoke output")
        test = self.recorder.remember_json(
            {
                "schema": "literate-ai/local-process-observation@1",
                "phase": phase,
                "plan_identity": self.root.package_plan.identity.uri,
                "returncode": returncode,
                "stdout_identity": test_stdout.uri,
                "stderr_identity": stderr.uri,
            }
        )
        execution = self.recorder.remember_json(
            {
                "schema": "literate-ai/local-process-observation@1",
                "phase": "packaged-project-execution",
                "plan_identity": self.root.package_plan.identity.uri,
                "returncode": 0,
                "stdout_identity": execute_stdout.uri,
                "stderr_identity": stderr.uri,
            }
        )
        root = replace(
            self.root,
            root_generated_integration_test_identity=test,
            packaged_execution_identity=execution,
        )
        reader = QualificationEvidenceReader(
            self.recorder.entries, max_bytes=16 * 1024**2, max_records=2000
        )
        return root, reader

    def verify(self, root, reader, *, closed):
        if not closed:
            return verify_qualification_packaged_library_processes(
                reader, root=root, tests=self.tests
            )
        from literate_ai.adapters.qualification_capture import (
            _verify_qualification_packaged_library_process_records,
        )

        return _verify_qualification_packaged_library_process_records(
            reader,
            package_plan=root.package_plan,
            package_result=root.package_result,
            project_build_plan_identity=root.project_build_plan_identity,
            root_test_identity=root.root_generated_integration_test_identity,
            packaged_execution_identity=root.packaged_execution_identity,
            tests=self.tests,
        )

    def test_positive_and_coordinate_entrypoints_accept_identical_complete_protocol(
        self,
    ):
        root, reader = self.records()
        for closed in (False, True):
            with self.subTest(closed=closed):
                self.assertIsNone(self.verify(root, reader, closed=closed))

    def test_both_entrypoints_refuse_nonzero_or_foreign_phase(self):
        for changes in ({"returncode": 7}, {"phase": "foreign-phase"}):
            root, reader = self.records(**changes)
            for closed in (False, True):
                with self.subTest(closed=closed, changes=changes):
                    with self.assertRaises(QualificationCaptureError):
                        self.verify(root, reader, closed=closed)

    def test_both_entrypoints_refuse_failed_partial_or_duplicate_cases(self):
        first = self.tests.cases[0].case_id
        for cases in (
            [{"case_id": first, "outcome": "failed"}],
            [],
            [{"case_id": first, "outcome": "passed"}] * 2,
        ):
            root, reader = self.records(cases=cases)
            for closed in (False, True):
                with self.subTest(closed=closed, cases=cases):
                    with self.assertRaises(QualificationCaptureError):
                        self.verify(root, reader, closed=closed)

    def test_public_wrapper_still_requires_original_positive_root_type(self):
        _root, reader = self.records()
        with self.assertRaisesRegex(QualificationCaptureError, "root-process-invalid"):
            verify_qualification_packaged_library_processes(
                reader, root=object(), tests=self.tests
            )
