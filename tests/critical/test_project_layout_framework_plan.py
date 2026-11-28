"""Strict public data contract, not origin/currentness or writer admission."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from literate_ai._filesystem import stat_identity_value
from literate_ai.adapters.project_layout_framework_plan import (
    decode_framework_authority_plan,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity
from tests.critical import test_project_layout_framework_selection as support


class FrameworkPlanCodecTests(unittest.TestCase):
    def setUp(self):
        helper = support.ExistingFrameworkSelectionTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, owner, proof = helper.fixture()
        self.plan, _private = helper.select(project, owner, proof)

    def seal(self, value):
        value.pop("plan_identity", None)
        value["plan_identity"] = canonical_identity(value).uri
        return value

    def test_schema_and_codec_join_actual_projection_and_return_detached_data(self):
        schema_path = (
            Path(__file__).parents[2]
            / "schemas/v2/project-layout-framework-authority.schema.json"
        )
        schema = json.loads(schema_path.read_bytes())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.plan)
        reopened = decode_framework_authority_plan(self.plan)
        self.assertEqual(reopened, self.plan)
        self.assertIsNot(reopened, self.plan)
        reopened["owned_placements"].clear()
        self.assertTrue(self.plan["owned_placements"])

    def test_unknown_field_version_and_old_mode_refuse_even_with_rehashed_record(self):
        for key, replacement in (
            ("raw_source", "not public"),
            ("schema", "literate-ai/project-layout-framework-authority@2"),
            ("transaction_mode", "contained-catalog-continuation"),
        ):
            changed = copy.deepcopy(self.plan)
            changed[key] = replacement
            with self.subTest(key=key), self.assertRaises(ProjectLayoutPlanError):
                decode_framework_authority_plan(self.seal(changed))

    def test_foreign_mixed_action_field_is_not_legacy_compatible_by_accident(self):
        changed = copy.deepcopy(self.plan)
        changed["owned_placements"]["SKILL.md"]["links"] = []
        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_plan(self.seal(changed))

    def test_immutable_byte_mode_cannot_claim_transformed_bytes(self):
        changed = copy.deepcopy(self.plan)
        row = changed["owned_placements"].pop("SKILL.md")
        row["projection"] = "original-bytes"
        row["to"] = "sha256:" + "f" * 64
        changed["placements"]["SKILL.md"] = row
        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_plan(self.seal(changed))

    def test_portable_aliases_and_aliased_file_ancestors_refuse(self):
        for source in ("skill.md", "skill.md/child.md"):
            changed = copy.deepcopy(self.plan)
            row = copy.deepcopy(changed["owned_placements"]["SKILL.md"])
            row["destination"] = "litai/independent-target.md"
            row["logical"] = source
            changed["owned_placements"][source] = row
            with self.subTest(source=source), self.assertRaises(ProjectLayoutPlanError):
                decode_framework_authority_plan(self.seal(changed))

    def test_moved_destination_cannot_also_be_a_resident_edit(self):
        changed = copy.deepcopy(self.plan)
        row = dict(changed["owned_placements"]["SKILL.md"])
        destination = row.pop("destination")
        changed["resident_edits"][destination] = row
        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_plan(self.seal(changed))

    def test_lossless_native_ids_accept_canonical_wide_reject_small_strings_bool(self):
        changed = copy.deepcopy(self.plan)
        changed["root_node"][1] = stat_identity_value(1 << 100)
        self.assertEqual(decode_framework_authority_plan(self.seal(changed)), changed)
        for value in ("5", True, 1 << 100):
            changed = copy.deepcopy(self.plan)
            changed["root_node"][1] = value
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ProjectLayoutPlanError, "native identity"),
            ):
                # Invalid wide integers cannot themselves be canonically hashed.
                # The decoder must reject native representation before plan hash.
                decode_framework_authority_plan(changed)

    def test_requirements_effect_claim_and_hash_cannot_be_overridden(self):
        for key, replacement in (("writes", True), ("full_containment", True)):
            changed = copy.deepcopy(self.plan)
            changed[key] = replacement
            with self.subTest(key=key), self.assertRaises(ProjectLayoutPlanError):
                decode_framework_authority_plan(self.seal(changed))
        changed = copy.deepcopy(self.plan)
        changed["required_owners"] = [
            {"path": "SKILL.md", "owner": "original", "reason": "not admitted"}
        ]
        changed["applicable"] = True
        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_plan(self.seal(changed))
        changed = copy.deepcopy(self.plan)
        changed["project_id"] += "-foreign"
        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_plan(changed)
