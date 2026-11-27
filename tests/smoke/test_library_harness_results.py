"""Shared exact runtime result checks, including finite numeric semantics."""

import copy
import json
import unittest

from literate_ai.adapters.library_harness_results import (
    LibraryHarnessResultError,
    validate_library_harness_results,
)
from tests.smoke import test_node_library_acceptance as fixture


class LibraryHarnessResultTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.NodeLibraryOracleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.oracle = self.fixture.load()
        self.original = self.oracle.identity
        self.document = {
            "schema": "literate-ai/library-acceptance-results@1",
            "cases": [{"case_id": "add", "capability": "add", "result": 3}],
        }

    def validate(self, content=None):
        return validate_library_harness_results(
            self.oracle,
            json.dumps(self.document) if content is None else content,
            oracle_identity=self.original,
        )

    def test_exact_cases_and_equivalent_integer_float_spellings(self):
        self.assertEqual(self.validate()["add"]["result"], 3)
        self.document["cases"][0]["result"] = 3.0
        self.assertEqual(self.validate()["add"]["result"], 3.0)

    def test_wrong_values_and_capabilities_do_not_pass(self):
        for changes in (
            {"result": True},
            {"result": 3.001},
            {"result": "3"},
            {"result": [3]},
            {"result": None},
            {"capability": "other"},
        ):
            with self.subTest(changes=changes):
                self.document["cases"][0] = {
                    "case_id": "add",
                    "capability": "add",
                    "result": 3,
                    **changes,
                }
                with self.assertRaises(LibraryHarnessResultError):
                    self.validate()

    def test_missing_duplicate_unknown_and_extra_case_fields_are_rejected(self):
        case = self.document["cases"][0]
        for cases in (
            [],
            [case, case],
            [{**case, "case_id": "unknown"}],
            [{**case, "extra": True}],
            [{"case_id": "add"}],
        ):
            self.document["cases"] = cases
            with (
                self.subTest(cases=cases),
                self.assertRaises(LibraryHarnessResultError),
            ):
                self.validate()

    def test_duplicate_json_fields_at_any_depth_and_nonfinite_values_rejected(self):
        encoded = json.dumps(self.document)
        for content in (
            encoded[:-1] + ', "cases": []}',
            encoded.replace('"result": 3', '"result": 999, "result": 3'),
            encoded.replace('"result": 3', '"result": NaN'),
            encoded.replace('"result": 3', '"result": Infinity'),
            encoded.replace('"result": 3', '"result": -Infinity'),
            b"\xff",
            "not JSON",
            None,
        ):
            with (
                self.subTest(content=content),
                self.assertRaises(LibraryHarnessResultError),
            ):
                validate_library_harness_results(
                    self.oracle, content, oracle_identity=self.original
                )

    def test_closed_protocol_and_original_oracle_identity(self):
        original = copy.deepcopy(self.document)
        for document in (
            [],
            None,
            {**original, "schema": "another"},
            {**original, "extra": True},
            {"cases": original["cases"]},
        ):
            with self.assertRaises(LibraryHarnessResultError):
                self.validate(json.dumps(document))
        self.oracle.cases[0].arguments.append(99)
        with self.assertRaisesRegex(LibraryHarnessResultError, "oracle changed"):
            self.validate()
