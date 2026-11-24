"""Public result validation; these controls do not perform placement."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.project_layout_continuation import journal_path
from literate_ai.adapters.project_layout_continuation_result import (
    SCHEMA,
    decode_catalog_continuation_result,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_project_layout_catalog_continuation as plans
from tests.support.fixtures_test_schema_catalog import V2_ROOT, SchemaCatalog


class CatalogContinuationResultTests(unittest.TestCase):
    def setUp(self):
        fixture = plans.CatalogContinuationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.plan = fixture.select(approved_references=("docs/guide.md",)).public_plan
        self.value = {
            "schema": SCHEMA,
            "operation": "apply",
            "plan": self.plan,
            "writes": True,
            "full_containment": False,
            "qualification": False,
            "journal": str(journal_path(fixture.root, self.plan["plan_identity"])),
            "retained_scaffolding": [],
            "applied": True,
        }

    def test_apply_and_recover_use_distinct_result_schema_and_unchanged_plan(self):
        catalog = SchemaCatalog(V2_ROOT)
        for operation in ("apply", "recover"):
            value = copy.deepcopy(self.value)
            if operation == "recover":
                value["operation"] = operation
                value.pop("applied")
                value["rolled_back"] = True
                value["retained_scaffolding"] = ["litai/skills", "litai/skills/demo"]
            catalog.validate(SCHEMA, value)
            result = decode_catalog_continuation_result(value)
            self.assertEqual(result, value)
            self.assertEqual(result["plan"], self.plan)
            self.assertIsNot(result["plan"], value["plan"])

    def test_codec_performs_no_filesystem_access(self):
        with (
            patch.object(Path, "open", side_effect=AssertionError("codec opened")),
            patch.object(Path, "stat", side_effect=AssertionError("codec statted")),
        ):
            self.assertEqual(decode_catalog_continuation_result(self.value), self.value)

    def test_qualification_containment_boolean_and_write_substitution_refuse(self):
        for key, value in (
            ("qualification", True),
            ("full_containment", True),
            ("writes", False),
            ("writes", 1),
            ("applied", 1),
        ):
            with self.subTest(key=key, value=value):
                candidate = {**self.value, key: value}
                with self.assertRaises(ProjectLayoutPlanError):
                    decode_catalog_continuation_result(candidate)

    def test_operation_and_success_flag_must_agree(self):
        for delta in (
            {"operation": "recover"},
            {"rolled_back": True},
            {"operation": "renew"},
            {"operation": None},
        ):
            with self.subTest(delta=delta), self.assertRaises(ProjectLayoutPlanError):
                decode_catalog_continuation_result({**self.value, **delta})

    def test_changed_nested_plan_is_never_a_valid_outcome(self):
        candidate = copy.deepcopy(self.value)
        candidate["plan"]["writes"] = True
        with self.assertRaises(ProjectLayoutPlanError):
            decode_catalog_continuation_result(candidate)

    def test_private_journal_fields_are_not_public_result_fields(self):
        with self.assertRaises(ProjectLayoutPlanError):
            decode_catalog_continuation_result({**self.value, "before": {}})

    def test_journal_must_match_original_project_and_plan(self):
        candidate = {**self.value, "journal": self.value["journal"] + "-foreign"}
        with self.assertRaises(ProjectLayoutPlanError):
            decode_catalog_continuation_result(candidate)

    def test_scaffolding_cannot_describe_unselected_or_escaping_state(self):
        for paths in (
            ["../outside"],
            ["litai/unrelated"],
            ["application"],
            ["litai/skills", "litai/skills"],
            [True],
        ):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                decode_catalog_continuation_result(
                    {**self.value, "retained_scaffolding": paths}
                )
