"""Strict result data; no migration, source restoration or qualification grant."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch

from literate_ai.adapters.project_layout_framework_result import (
    SCHEMA,
    decode_framework_authority_result,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity
from tests.critical import test_project_layout_framework_selection as support
from tests.support.fixtures_test_schema_catalog import V2_ROOT, SchemaCatalog


class FrameworkAuthorityResultTests(unittest.TestCase):
    def setUp(self):
        helper = support.ExistingFrameworkSelectionTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, resources, proof = helper.fixture()
        plan, _selection = helper.select(project, resources, proof)
        self.assertTrue(plan["applicable"], plan["required_owners"])
        self.value = {
            "schema": SCHEMA,
            "operation": "apply",
            "plan": plan,
            "journal": str(
                project.root
                / "litai/.literate"
                / (
                    "framework-placement-"
                    + canonical_identity({"layout_plan": plan["plan_identity"]}).digest
                )
            ),
            "writes": True,
            "applied": True,
            "producer_state": "unclassified",
            "full_containment": False,
            "qualification": False,
        }

    def test_apply_and_recover_preserve_original_plan_and_do_not_share_mutable_data(
        self,
    ):
        catalog = SchemaCatalog(V2_ROOT)
        for operation in ("apply", "recover"):
            value = copy.deepcopy(self.value)
            if operation == "recover":
                value["operation"] = operation
                value.pop("applied")
                value.pop("producer_state")
                value["rolled_back"] = True
                value["retained_scaffolding"] = []
            catalog.validate(SCHEMA, value)
            result = decode_framework_authority_result(value)
            self.assertEqual(result, value)
            self.assertIsNot(result["plan"], value["plan"])

    def test_standard_schema_registry_resolves_the_original_embedded_plan(self):
        from jsonschema import Draft202012Validator
        from jsonschema.exceptions import ValidationError
        from referencing import Registry, Resource

        registry = Registry()
        documents = {}
        for name in (
            "project-layout-framework-authority",
            "project-layout-framework-authority-result",
        ):
            document = json.loads((V2_ROOT / (name + ".schema.json")).read_bytes())
            documents[name] = document
            registry = registry.with_resource(
                document["$id"], Resource.from_contents(document)
            )
        registry = registry.crawl()
        self.assertEqual(registry.resolver().lookup(SCHEMA).contents["$id"], SCHEMA)
        validator = Draft202012Validator(
            documents["project-layout-framework-authority-result"], registry=registry
        )
        validator.validate(self.value)
        changed = copy.deepcopy(self.value)
        changed["plan"]["writes"] = True
        with self.assertRaises(ValidationError):
            validator.validate(changed)

    def test_codec_never_reopens_source_or_journal(self):
        with (
            patch.object(Path, "open", side_effect=AssertionError("codec opened")),
            patch.object(Path, "stat", side_effect=AssertionError("codec statted")),
            patch.object(Path, "lstat", side_effect=AssertionError("codec lstat")),
        ):
            self.assertEqual(decode_framework_authority_result(self.value), self.value)

    def test_placement_cannot_claim_renewal_containment_or_qualification(self):
        for field, replacement in (
            ("producer_state", "current"),
            ("full_containment", True),
            ("qualification", True),
            ("writes", False),
            ("writes", 1),
            ("applied", 1),
            ("operation", []),
        ):
            with self.subTest(field=field):
                value = copy.deepcopy(self.value)
                value[field] = replacement
                with self.assertRaises(ProjectLayoutPlanError):
                    decode_framework_authority_result(value)

    def test_unknown_fields_and_operation_substitution_refuse(self):
        for addition in (
            {"restored_owner": {}},
            {"rolled_back": True},
            {"operation": "recover"},
            {"operation": "finalize"},
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                decode_framework_authority_result({**self.value, **addition})

    def test_callback_shaped_fields_are_not_compared_or_copied(self):
        calls = []

        class Foreign:
            def __eq__(self, _other):
                calls.append("comparison")
                return True

            def __deepcopy__(self, _memo):
                calls.append("copy")
                return self

        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_result(
                {**self.value, "producer_state": Foreign()}
            )
        self.assertEqual(calls, [])

    def test_journal_must_match_the_exact_acknowledged_project_and_plan(self):
        for journal in (
            self.value["journal"] + "-other",
            "litai/.literate/relative",
            "",
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                decode_framework_authority_result({**self.value, "journal": journal})

    def test_foreign_native_path_spelling_is_data_only_and_not_host_dependent(self):
        for project, path_type in (
            (r"C:\work\project", PureWindowsPath),
            (r"\\server\share\project", PureWindowsPath),
            ("/tmp/project", PurePosixPath),
        ):
            value = copy.deepcopy(self.value)
            value["plan"]["project"] = project
            value["plan"]["plan_identity"] = canonical_identity(
                {
                    key: item
                    for key, item in value["plan"].items()
                    if key != "plan_identity"
                }
            ).uri
            value["journal"] = str(
                path_type(project)
                / "litai/.literate"
                / (
                    "framework-placement-"
                    + canonical_identity(
                        {"layout_plan": value["plan"]["plan_identity"]}
                    ).digest
                )
            )
            self.assertEqual(decode_framework_authority_result(value), value)

    def test_recovery_scaffolding_must_remain_in_original_destination_scope(self):
        value = copy.deepcopy(self.value)
        value["operation"] = "recover"
        value.pop("applied")
        value.pop("producer_state")
        value["rolled_back"] = True
        for retained in (
            ["../outside"],
            ["application"],
            ["litai/foreign"],
            ["litai/scripts", "litai/scripts"],
        ):
            with self.assertRaises((ProjectLayoutPlanError, ValueError)):
                decode_framework_authority_result(
                    {**value, "retained_scaffolding": retained}
                )
