"""Real installed wheel/byte custody with explicit source/dependency fixtures.

No model generation, qualified provider, retained consumer or release is claimed.
"""

import hashlib
import unittest
from unittest import mock

import tests.smoke.test_standard_python_lifecycle as lifecycle_fixture
import tests.support.fixtures_test_standard_python_evidence as evidence_fixture
from literate_ai.adapters.dependencies.types import DependencyObservationError
from literate_ai.adapters.lifecycle import standard_python_capture as capture
from literate_ai.adapters.lifecycle.standard_local import _local_tree_document
from literate_ai.adapters.lifecycle.standard_python import (
    StandardPythonDependencyObserver,
)
from literate_ai.adapters.qualification_capture import (
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
)
from literate_ai.contracts import ContentIdentity


class PythonArtifactCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        evidence_fixture.StandardPythonEvidenceTests.setUpClass()

    def setUp(self):
        self.fixture = evidence_fixture.StandardPythonEvidenceTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.evidence = self.fixture.retain()
        self.root = self.fixture.root.resolve(strict=True)
        self.export = self.root / "library/source/original.py"
        self.export.parent.mkdir(parents=True)
        self.export.write_bytes(b"import example\nVALUE = example.VALUE\n")
        self.observer = StandardPythonDependencyObserver(
            self.root,
            self.evidence.identity,
            self.fixture.binding,
            self.fixture.source,
            self.fixture.fixture.toolchain,
        )
        self.recorder = QualificationEvidenceRecorder(
            max_bytes=64 * 1024**2, max_records=4096
        )
        self.tree = self.recorder.remember_json(_local_tree_document(self.root))

    def run_capture(self, **overrides):
        return capture.capture_standard_python_artifact_records(
            self.root,
            **{
                "expected_tree": self.tree,
                "observer": self.observer,
                "recorder": self.recorder,
                **overrides,
            },
        )

    def test_complete_actual_artifact_reopens_after_original_root_retirement(self):
        originals = {
            entry["path"]: (self.root / entry["path"]).read_bytes()
            for entry in _local_tree_document(self.root)["files"]
        }
        before = self.recorder.retained_bytes
        retained = self.run_capture()
        self.assertGreater(self.recorder.retained_bytes, before)
        reader = QualificationEvidenceReader(
            self.recorder.entries, max_bytes=64 * 1024**2, max_records=4096
        )
        self.root.rename(self.root.with_name("retired-artifact"))
        for name, content in originals.items():
            with self.subTest(path=name):
                identity = ContentIdentity.parse_uri(
                    "sha256:" + hashlib.sha256(content).hexdigest()
                )
                self.assertIn(identity, retained)
                self.assertEqual(reader.read_bytes(identity), content)
        self.assertIn("python-dependencies.json", originals)
        self.assertIn("python-runtime/site/example/__init__.py", originals)
        self.assertIn("library/source/original.py", originals)
        with self.assertRaises((DependencyObservationError, ValueError, OSError)):
            self.observer()

    def test_record_and_byte_bounds_refuse_before_capture_payload_allocation(self):
        for bounds in (
            {"max_bytes": 1, "max_records": 4096},
            {"max_bytes": 64 * 1024**2, "max_records": 1},
        ):
            recorder = QualificationEvidenceRecorder(
                max_bytes=64 * 1024**2, max_records=4096
            )
            recorder.remember_json(_local_tree_document(self.root))
            # Narrow an actual recorder's remaining allowance after its original
            # tree record exists. No native or success owner is substituted.
            recorder.max_bytes = bounds["max_bytes"]
            recorder.max_records = bounds["max_records"]
            with (
                self.subTest(bounds=bounds),
                mock.patch.object(
                    capture, "_stream", side_effect=AssertionError("unfunded capture")
                ),
            ):
                with self.assertRaisesRegex(
                    DependencyObservationError, "remaining qualification"
                ):
                    self.run_capture(recorder=recorder)
            self.assertEqual(len(recorder.entries), 1)

    def test_original_tree_record_required_before_original_native_callback(self):
        recorder = QualificationEvidenceRecorder(
            max_bytes=64 * 1024**2, max_records=4096
        )
        with mock.patch.object(
            StandardPythonDependencyObserver,
            "__call__",
            side_effect=AssertionError("unbound observer"),
        ):
            with self.assertRaisesRegex(
                DependencyObservationError, "already belong to build custody"
            ):
                self.run_capture(recorder=recorder)

    def test_actual_runtime_byte_change_during_capture_is_preserved_and_refused(self):
        original = capture._stream
        target = self.evidence.payload_root / "site/example/__init__.py"
        changed = b"VALUE = 'changed during capture'\n"
        hit = []

        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            if not hit:
                target.write_bytes(changed)
                hit.append(True)
            return result

        with mock.patch.object(capture, "_stream", side_effect=mutate):
            with self.assertRaises(
                (DependencyObservationError, ValueError, OSError)
            ) as failed:
                self.run_capture()
        self.assertEqual(hit, [True], str(failed.exception))
        self.assertEqual(target.read_bytes(), changed)
        self.assertEqual(len(self.recorder.entries), 1)

    def test_last_real_observer_callback_cannot_change_an_earlier_export(self):
        original = StandardPythonDependencyObserver.__call__
        calls = []
        changed = b"preserve actual late export mutation\n"

        def mutate(observer):
            result = original(observer)
            calls.append(True)
            if len(calls) == 2:
                self.export.write_bytes(changed)
            return result

        with mock.patch.object(
            StandardPythonDependencyObserver, "__call__", new=mutate
        ):
            with self.assertRaisesRegex(
                DependencyObservationError, "original complete tree"
            ):
                self.run_capture()
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.export.read_bytes(), changed)
        self.assertEqual(len(self.recorder.entries), 1)

    def test_existing_raw_records_do_not_skip_actual_current_tree_observation(self):
        self.run_capture()
        before = self.recorder.entries
        self.run_capture()
        self.assertEqual(self.recorder.entries, before)
        self.export.write_bytes(b"changed known export\n")
        with self.assertRaisesRegex(
            DependencyObservationError, "original complete tree"
        ):
            self.run_capture()
        self.assertEqual(self.export.read_bytes(), b"changed known export\n")
        self.assertEqual(self.recorder.entries, before)


class PythonLibraryBuildCaptureTests(unittest.TestCase):
    library = True
    source_projection = False
    setUp = lifecycle_fixture.StandardPythonLibraryLifecycleTests.setUp
    runtime_instance = (
        lifecycle_fixture.StandardPythonLibraryLifecycleTests.runtime_instance
    )
    _admit_source = lifecycle_fixture.StandardPythonLibraryLifecycleTests._admit_source
    build = lifecycle_fixture.StandardPythonLibraryLifecycleTests.build

    @classmethod
    def setUpClass(cls):
        lifecycle_fixture.StandardPythonLibraryLifecycleTests.setUpClass()

    def test_real_offline_library_build_retains_runtime_siblings_without_export_changes(
        self,
    ):
        recorder = QualificationEvidenceRecorder(
            max_bytes=64 * 1024**2, max_records=8192
        )
        self.ports.retain_evidence_with(recorder)
        output = self.build()
        reader = QualificationEvidenceReader(
            recorder.entries, max_bytes=64 * 1024**2, max_records=8192
        )
        files = _local_tree_document(self.artifact)["files"]
        self.assertTrue(
            any(f["path"].startswith("python-runtime/site/") for f in files)
        )
        for record in files:
            content = (self.artifact / record["path"]).read_bytes()
            self.assertEqual(
                reader.read_bytes(
                    ContentIdentity.parse_uri("sha256:" + record["sha256"])
                ),
                content,
            )
        self.assertEqual(output.exports, self.ports.build(self.plan, ()).exports)
        self.assertEqual(self.ports.build_cache_hits, 1)
