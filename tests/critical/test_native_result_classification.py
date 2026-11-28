"""Result protocol classification only; no native execution qualification."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from literate_ai.adapters import rust_library_harness_execution as executor
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError


class NativeResultClassificationTests(unittest.TestCase):
    def setUp(self):
        self.oracle = SimpleNamespace(
            cases=(
                SimpleNamespace(
                    case_id="first", capability="application.json", expected_result=42
                ),
                SimpleNamespace(
                    case_id="second",
                    capability="application.json",
                    expected_result=True,
                ),
            )
        )
        self.document = {
            "schema": "literate-ai/library-acceptance-results@1",
            "cases": [
                {"case_id": "second", "capability": "application.json", "result": True},
                {"case_id": "first", "capability": "application.json", "result": 42},
            ],
        }

    def raw(self):
        return json.dumps(self.document).encode()

    def assert_refused(self, code):
        for classify in (executor._result_values_differ, executor._require_results):
            with self.subTest(classify=classify.__name__):
                with self.assertRaises(ComponentAcceptanceError) as caught:
                    classify(self.raw(), self.oracle)
                self.assertEqual(caught.exception.code, "component_acceptance." + code)

    def test_exact_inventory_permits_reordering_and_equivalent_numbers(self):
        self.document["cases"][1]["result"] = 42.0
        self.assertFalse(executor._result_values_differ(self.raw(), self.oracle))
        executor._require_results(self.raw(), self.oracle)

    def test_value_difference_is_classified_without_changing_public_refusal(self):
        self.document["cases"][1]["result"] = 43
        self.assertTrue(executor._result_values_differ(self.raw(), self.oracle))
        with self.assertRaises(ComponentAcceptanceError) as caught:
            executor._require_results(self.raw(), self.oracle)
        self.assertEqual(
            caught.exception.code, "component_acceptance.rust_harness_result_mismatch"
        )

    def test_boolean_result_is_distinct_from_equal_integer(self):
        self.document["cases"][0]["result"] = 1
        self.assertTrue(executor._result_values_differ(self.raw(), self.oracle))

    def test_foreign_same_count_case_inventory_is_not_a_value_difference(self):
        self.document["cases"][0]["case_id"] = "foreign"
        self.assert_refused("rust_harness_result_mismatch")

    def test_foreign_or_nonstring_capability_is_not_a_value_difference(self):
        for capability in ("application.foreign", True, None, 1, [], {}):
            with self.subTest(capability=capability):
                self.document["cases"][0]["capability"] = capability
                self.assert_refused("rust_harness_result_mismatch")

    def test_inventory_is_checked_even_after_a_wrong_value(self):
        self.document["cases"][0]["result"] = False
        self.document["cases"][1]["capability"] = "application.foreign"
        self.assert_refused("rust_harness_result_mismatch")

    def test_duplicate_case_or_incomplete_document_remains_protocol_failure(self):
        self.document["cases"][0]["case_id"] = "first"
        self.assert_refused("rust_harness_result_protocol")
        self.document["cases"].pop()
        self.assert_refused("rust_harness_result_protocol")

    def test_duplicate_fields_and_nonfinite_values_remain_protocol_refusals(self):
        for raw, suffix in (
            (b'{"schema":"x","schema":"y"}', "duplicate_field"),
            (b'{"value":NaN}', "nonfinite_json"),
        ):
            with self.subTest(suffix=suffix):
                with self.assertRaises(ComponentAcceptanceError) as caught:
                    executor._result_values_differ(raw, self.oracle)
                self.assertEqual(
                    caught.exception.code, "component_acceptance.rust_harness_" + suffix
                )
