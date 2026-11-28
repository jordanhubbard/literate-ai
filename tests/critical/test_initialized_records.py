"""Canonical owner compatibility and finite coordinate publication checks."""

import json
import os
import pickle
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import literate_ai.projects as projects
from literate_ai.adapters import initialized_records as records
from literate_ai.adapters import project_updates as updates
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters import retained_scaffold_coordinates as coordinates
from literate_ai.contracts import ProjectInitializationOrigin, canonical_json_bytes
from tests.critical import test_retained_recorded_coordinates as fixtures


class InitializedRecordTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RecordedRetainedCoordinatesTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root
        self.origin = self.fixture.origin
        self.baseline = self.fixture.baseline

    def reader(self):
        payloads = {
            ".literate/initialization-origin.json": canonical_json_bytes(
                self.origin.to_dict()
            )
            + b"\n",
            ".literate/initialization-baseline.json": canonical_json_bytes(
                self.baseline.to_dict()
            )
            + b"\n",
        }
        calls = []

        class Reader:
            def read(self, name, *, optional=False):
                calls.append(("read", name, optional))
                return payloads.get(name)

            def json_value(self, content, label):
                calls.append(("json", label))
                return json.loads(content)

        return Reader(), calls, payloads

    def test_original_exports_and_exception_qualified_identity_are_preserved(self):
        self.assertIs(updates.ProjectUpdateError, records.ProjectUpdateError)
        self.assertIs(updates._parse_contract_bytes, records._parse_contract_bytes)
        self.assertIs(updates._project_path, records._project_path)
        self.assertEqual(
            records.ProjectUpdateError.__module__,
            "literate_ai.adapters.project_updates",
        )
        self.assertIs(
            pickle.loads(pickle.dumps(records.ProjectUpdateError)),
            records.ProjectUpdateError,
        )

    def test_original_canonical_parser_preserves_utf16_classification(self):
        content = canonical_json_bytes(self.origin.to_dict()) + b"\n"
        self.assertEqual(
            records._parse_contract_bytes(
                content, "origin", ProjectInitializationOrigin
            ),
            self.origin,
        )
        for payload, code in (
            (content.decode().encode("utf-16"), "project.update_evidence_noncanonical"),
            (content + b"\n", "project.update_evidence_noncanonical"),
            (b"{", "project.update_evidence_invalid"),
            (b"x" * (16 * 1024**2 + 1), "project.update_evidence_oversized"),
        ):
            with self.subTest(code=code, size=len(payload)):
                with self.assertRaises(records.ProjectUpdateError) as caught:
                    records._parse_contract_bytes(
                        payload, "origin", ProjectInitializationOrigin
                    )
                self.assertEqual(caught.exception.code, code)

    def test_original_origin_url_schema_remains_in_use(self):
        for url in (
            "https://example.test/repository.git",
            "https://例え.test/repository.git",
            "https://[::1]/repository.git",
            "https://[v1.example]/repository.git",
            "ssh://git@example.test/repository.git",
        ):
            with self.subTest(url=url):
                origin = ProjectInitializationOrigin(
                    url, "a" * 40, "literate-ai", "1.3.1"
                )
                self.assertEqual(
                    records._parse_contract_bytes(
                        canonical_json_bytes(origin.to_dict()) + b"\n",
                        "origin",
                        ProjectInitializationOrigin,
                    ),
                    origin,
                )

    def test_normal_pair_keeps_three_original_context_selections(self):
        self.fixture.write_pair()
        code = projects.ProjectConfigurationStore.context.__code__
        calls = 0

        def observe(frame, event, arg):
            nonlocal calls
            if event == "call" and frame.f_code is code:
                calls += 1

        previous = sys.getprofile()
        try:
            sys.setprofile(observe)
            result = projects.initialization_coordinate_baseline(self.root)
        finally:
            sys.setprofile(previous)
        self.assertEqual(result, self.baseline)
        self.assertEqual(calls, 3)

    def test_observed_pair_keeps_two_optional_reads_and_two_json_charges(self):
        reader, calls, payloads = self.reader()
        with (
            mock.patch.object(
                Path, "exists", side_effect=AssertionError("ambient exists")
            ),
            mock.patch.object(
                Path, "is_file", side_effect=AssertionError("ambient file")
            ),
            mock.patch.object(
                Path, "read_bytes", side_effect=AssertionError("ambient read")
            ),
        ):
            self.assertEqual(
                projects.initialization_coordinate_baseline(
                    self.root, _observation=reader
                ),
                self.baseline,
            )
        names = tuple(payloads)
        self.assertEqual(
            calls,
            [
                ("read", names[0], True),
                ("read", names[1], True),
                ("json", names[0]),
                ("json", names[1]),
            ],
        )

    def test_missing_partial_and_invalid_pairs_keep_original_error_cause(self):
        reader, calls, payloads = self.reader()
        payloads.clear()
        self.assertIsNone(
            projects.initialization_coordinate_baseline(self.root, _observation=reader)
        )
        self.assertEqual(len(calls), 2)
        payloads[".literate/initialization-origin.json"] = b"{}"
        with self.assertRaises(projects.ProjectError) as caught:
            projects.initialization_coordinate_baseline(self.root, _observation=reader)
        self.assertEqual(caught.exception.code, "project.skill_placement_conflict")
        self.assertEqual(
            str(caught.exception.__cause__),
            "initialization provenance pair is incomplete",
        )
        payloads[".literate/initialization-baseline.json"] = b"{}"
        with self.assertRaises(projects.ProjectError) as caught:
            projects.initialization_coordinate_baseline(self.root, _observation=reader)
        self.assertIs(type(caught.exception.__cause__), records.ProjectUpdateError)
        self.assertEqual(
            caught.exception.__cause__.code, "project.update_evidence_invalid"
        )

    def test_foreign_leaf_exports_are_refused_before_any_reader_callback(self):
        for name in (
            "_parse_contract_bytes",
            "_read_contract_at",
            "_initialization_pair",
        ):
            reader, calls, _ = self.reader()
            with self.subTest(port=name):
                foreign = mock.Mock(side_effect=AssertionError("foreign record port"))
                with mock.patch.object(records, name, foreign):
                    with self.assertRaisesRegex(ValueError, "initialized-record"):
                        projects.initialization_coordinate_baseline(
                            self.root, _observation=reader
                        )
                    foreign.assert_not_called()
                    self.assertEqual(calls, [])

    def test_changed_original_parser_code_refuses_before_any_reader_callback(self):
        reader, calls, _ = self.reader()
        function = records._parse_contract_bytes
        original = function.__code__
        try:
            function.__code__ = original.replace(co_name="foreign_parser")
            with self.assertRaisesRegex(ValueError, "initialized-record"):
                projects.initialization_coordinate_baseline(
                    self.root, _observation=reader
                )
            self.assertEqual(calls, [])
        finally:
            function.__code__ = original

    def test_foreign_schema_front_door_refuses_before_dispatch(self):
        reader, calls, _ = self.reader()
        foreign = mock.Mock(side_effect=AssertionError("foreign origin parser"))
        with mock.patch.object(ProjectInitializationOrigin, "from_dict", foreign):
            with self.assertRaisesRegex(ValueError, "initialized-record"):
                projects.initialization_coordinate_baseline(
                    self.root, _observation=reader
                )
            foreign.assert_not_called()
            self.assertEqual(calls, [])

    def test_defining_coordinate_export_cannot_replace_captured_path_port(self):
        foreign = mock.Mock(side_effect=AssertionError("foreign coordinate"))
        with mock.patch.object(coordinates, "retained_scaffold_coordinate", foreign):
            with self.assertRaisesRegex(ValueError, "coordinate path port"):
                transaction.retained_scaffold_path(self.root, "litai.harness.mk")
            foreign.assert_not_called()

    def test_direct_coordinate_closes_defining_export_after_reader_callback(self):
        snapshot = projects.ProjectConfigurationStore(self.root).read()
        context = projects.ProjectConfigurationStore.context(self.root)
        original = coordinates.retained_scaffold_coordinate
        foreign = mock.Mock(side_effect=AssertionError("foreign coordinate"))
        reader, _, _ = self.reader()

        def observed_context():
            coordinates.retained_scaffold_coordinate = foreign
            return snapshot, context

        # This modeled DATA reader grants no native/source ownership.
        reader.project_context = observed_context
        reader.read_coordinate = lambda name, *, optional=False: None
        with mock.patch.object(coordinates, "retained_scaffold_coordinate", original):
            with self.assertRaisesRegex(ValueError, "coordinate boundary changed"):
                original(self.root, "litai.harness.mk", _observation=reader)
            foreign.assert_not_called()

    def test_direct_coordinate_preserves_original_reader_exception(self):
        original = coordinates.retained_scaffold_coordinate
        foreign = mock.Mock(side_effect=AssertionError("foreign coordinate"))
        expected = RuntimeError("original reader refused")
        reader, _, _ = self.reader()

        def observed_context():
            coordinates.retained_scaffold_coordinate = foreign
            raise expected

        reader.project_context = observed_context
        with mock.patch.object(coordinates, "retained_scaffold_coordinate", original):
            with self.assertRaises(RuntimeError) as caught:
                original(self.root, "litai.harness.mk", _observation=reader)
            self.assertIs(caught.exception, expected)
            foreign.assert_not_called()

    def test_actual_cold_import_orders_remain_acyclic(self):
        modules = (
            "literate_ai.projects",
            "literate_ai.adapters.initialized_records",
            "literate_ai.adapters.project_updates",
            "literate_ai.adapters.retained_scaffold_coordinates",
        )
        source = str(Path(projects.__file__).parents[1])
        for first in modules:
            with self.subTest(first=first):
                order = (first,) + tuple(name for name in modules if name != first)
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        "-c",
                        (
                            "import importlib,sys\n"
                            f"sys.path.insert(0, {source!r})\n"
                            f"for name in {order!r}: importlib.import_module(name)\n"
                            "sys.stdout.buffer.write(b'ok\\n')\n"
                        ),
                    ],
                    cwd=self.root,
                    env=dict(os.environ),
                    timeout=30,
                    capture_output=True,
                    check=True,
                )
                self.assertEqual(result.stdout, b"ok\n")
