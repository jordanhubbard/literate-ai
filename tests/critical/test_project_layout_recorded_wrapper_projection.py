"""Pure recorded converter joins, not conversion/source/native qualification.

The existing resource fixture models current distribution-origin observation.
Retained records below model executed evidence DATA ONLY. No such modeled data
can issue an original live retained-source owner or grant movement authority.
"""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import harness_inventory as renderer
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import (
    project_layout_recorded_wrapper_projection as production,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutObservation
from literate_ai.adapters.retained_harness_receipts import (
    retained_harness_receipt_policy,
)
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
)
from literate_ai.projects import serialize_project_configuration
from tests.critical import test_project_layout_framework_resources as support


def canonical(value):
    return canonical_json_bytes(value) + b"\n"


class RecordedWrapperProjectionTests(unittest.TestCase):
    def fixture(self):
        inventory = {
            "schema": renderer.HARNESS_INVENTORY_SCHEMA,
            "commands": {
                phase: {"command": "make " + phase, "evidence": "Makefile"}
                for phase in ("build", "test", "package")
            },
            "stages": [
                {
                    "id": phase,
                    "command": "make " + phase,
                    "evidence": "Makefile",
                    "cwd": ".",
                }
                for phase in ("build", "test", "package")
            ],
            "source_scope": {"paths": ["Makefile", "main.c"]},
        }
        source = {"identity": "sha256:" + "a" * 64, "scope": "authored-source"}
        phases = [
            {
                "phase": phase,
                "exit_code": 0,
                "timed_out": False,
                "source_tree": source,
            }
            for phase in ("build", "test", "package")
        ]
        baseline = {
            "schema": renderer.HARNESS_BASELINE_SCHEMA,
            "state": "passed",
            "phase_count": len(phases),
            "phases": phases,
            "source_scope": inventory["source_scope"],
            "legacy_source_tree_before": source,
            "legacy_source_tree_after": source,
        }
        parity = {
            "schema": renderer.HARNESS_PARITY_SCHEMA,
            "state": "passed",
            "phase_count": len(phases),
            "phases": [
                {**phase, "baseline_source_tree": source, "parity": True}
                for phase in phases
            ],
        }
        implementation = "components/legacy-project-wrapper/implementation"
        lift = {
            "schema": "literate-ai/legacy-lift-shift@1",
            "state": "passed",
            "implementation_directory": implementation,
            "phase_11_parity_identity": canonical_identity(parity).uri,
            "phase_12_parity": copy.deepcopy(parity),
        }
        project, _observed, origin = support.framework_fixture(self)
        project.definition = replace(
            project.definition,
            test_receipt_policy=retained_harness_receipt_policy(inventory),
        )
        project.write(
            project.manifest, serialize_project_configuration(project.definition)
        )
        project.refresh()
        project.inventory["retained_implementation"] = None
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        with patch.object(resources, "_read_current_origin", return_value=origin):
            owner = resources.observe_original_framework_resources(observed)
        original = {name: name for name in production._LOGICAL}
        after = {name: "litai/" + name for name in original}
        definition_after = replace(
            project.definition,
            component_roots=("litai/components",),
            skill_roots=("skills", "litai/skills"),
            flavor_roots=("litai/flavors",),
            workflow_roots=("litai/workflows",),
            routing_roots=("litai/routing",),
        )
        conversion = ConversionAuthorityState(
            project_id=project.definition.project_id,
            stage=ConversionAuthorityStage.WRAPPED,
            evidence_identities=(ContentIdentity.parse_uri("sha256:" + "d" * 64),),
        )
        return {
            "resources": owner,
            "before_definition_bytes": project.snapshot.content,
            "prospective_definition_bytes": serialize_project_configuration(
                definition_after
            ),
            "original_coordinates": original,
            "prospective_coordinates": after,
            "record_bytes": {
                name: canonical(value)
                for name, value in dict(
                    inventory=inventory,
                    baseline=baseline,
                    parity=parity,
                    lift_shift=lift,
                    conversion_authority=conversion.to_dict(),
                ).items()
            },
            "implementation_directory": implementation,
            "source_tree_identity": source["identity"],
            "original_entry_bytes": {
                **{
                    name: text.encode()
                    for name, text in renderer.legacy_shim_authority(
                        inventory, baseline
                    ).items()
                },
                "litai.harness.mk": renderer.render_harness_wrapper(
                    inventory, legacy_directory=implementation
                ).encode(),
            },
        }

    def alter_record(self, args, name, alter):
        import json

        value = json.loads(args["record_bytes"][name])
        alter(value)
        args["record_bytes"][name] = canonical(value)

    def test_exact_original_seven_outputs_no_filesystem_or_source_dispatch(self):
        args = self.fixture()
        with (
            patch.object(Path, "open", side_effect=AssertionError("opened")),
            patch.object(Path, "resolve", side_effect=AssertionError("resolved")),
            patch.object(renderer, "files", side_effect=AssertionError("rediscovered")),
            patch.object(
                renderer, "execute_harness_baseline", side_effect=AssertionError("ran")
            ),
        ):
            result = production.project_recorded_legacy_wrapper_authority(**args)
        self.assertEqual(len(result.entries), 7)
        self.assertIs(result.resources, args["resources"])
        for entry in result.entries:
            self.assertEqual(entry.original_bytes, entry.prospective_bytes)
            self.assertEqual(entry.prospective_coordinate, "litai/" + entry.logical)
        self.assertEqual(
            result.implementation_directory, args["implementation_directory"]
        )
        self.assertFalse(hasattr(result, "require_current"))

    def test_private_original_resource_hook_preserves_default_renderer_exactly(self):
        args = self.fixture()
        import json

        inventory, baseline = (
            json.loads(args["record_bytes"][name]) for name in ("inventory", "baseline")
        )
        resource = (
            files("literate_ai.project_template")
            .joinpath("workflows/production/staging/dev/workflow.md")
            .read_bytes()
        )
        self.assertEqual(
            renderer.legacy_shim_authority(inventory, baseline),
            renderer.legacy_shim_authority(
                inventory, baseline, _workflow_template=resource
            ),
        )

    def test_user_edited_wrapper_not_owned_by_filename(self):
        args = self.fixture()
        args["original_entry_bytes"]["litai.harness.mk"] += b"\n# custom\n"
        with self.assertRaises(ValueError):
            production.project_recorded_legacy_wrapper_authority(**args)

    def test_missing_phase_refuses_despite_passed_state(self):
        args = self.fixture()
        self.alter_record(args, "baseline", lambda value: value["phases"].pop())
        with self.assertRaises(ValueError):
            production.project_recorded_legacy_wrapper_authority(**args)

    def test_phase_exit_true_is_not_zero(self):
        args = self.fixture()
        self.alter_record(
            args, "baseline", lambda value: value["phases"][0].update(exit_code=True)
        )
        with self.assertRaises(ValueError):
            production.project_recorded_legacy_wrapper_authority(**args)

    def test_original_source_identity_and_scope_are_both_bound(self):
        for change in ("identity", "scope"):
            with self.subTest(change=change):
                args = self.fixture()
                if change == "identity":
                    args["source_tree_identity"] = "sha256:" + "b" * 64
                else:
                    self.alter_record(
                        args,
                        "inventory",
                        lambda value: value.update(source_scope={"paths": []}),
                    )
                with self.assertRaises(ValueError):
                    production.project_recorded_legacy_wrapper_authority(**args)

    def test_post_lift_stages_cannot_be_replaced_with_passed_label(self):
        args = self.fixture()
        self.alter_record(
            args,
            "lift_shift",
            lambda value: value.update(phase_12_parity={"state": "passed"}),
        )
        with self.assertRaises(ValueError):
            production.project_recorded_legacy_wrapper_authority(**args)

    def test_original_implementation_cannot_be_rebased_into_litai(self):
        args = self.fixture()
        args["implementation_directory"] = "litai/" + args["implementation_directory"]
        with self.assertRaises(ValueError):
            production.project_recorded_legacy_wrapper_authority(**args)

    def test_extra_outputs_or_foreign_coordinates_do_not_gain_ownership(self):
        for change in ("extra", "source", "alias"):
            with self.subTest(change=change):
                args = self.fixture()
                if change == "extra":
                    args["prospective_coordinates"]["application/main.c"] = (
                        "litai/main.c"
                    )
                elif change == "source":
                    args["prospective_coordinates"]["litai.harness.mk"] = (
                        "application/main.c"
                    )
                else:
                    args["prospective_coordinates"]["litai.harness.mk"] = (
                        "LitAI/litai.harness.mk"
                    )
                with self.assertRaises(ValueError):
                    production.project_recorded_legacy_wrapper_authority(**args)

    def test_unselected_original_configuration_is_not_new_project_defaults(self):
        args = self.fixture()
        old = production.parse_project_configuration(
            args["prospective_definition_bytes"]
        )
        args["prospective_definition_bytes"] = serialize_project_configuration(
            replace(old, log_dir="new-logs")
        )
        with self.assertRaises(ValueError):
            production.project_recorded_legacy_wrapper_authority(**args)

    def test_record_canonical_bytes_and_original_snapshot_are_required(self):
        for change in ("canonical", "snapshot"):
            with self.subTest(change=change):
                args = self.fixture()
                if change == "canonical":
                    args["record_bytes"]["inventory"] += b"\n"
                else:
                    old = production.parse_project_configuration(
                        args["before_definition_bytes"]
                    )
                    args["before_definition_bytes"] = serialize_project_configuration(
                        replace(old, project_id="other")
                    )
                    args["prospective_definition_bytes"] = args[
                        "before_definition_bytes"
                    ]
                with self.assertRaises(ValueError):
                    production.project_recorded_legacy_wrapper_authority(**args)

    def test_custom_generated_skill_is_not_owned_by_rendered_component(self):
        args = self.fixture()
        args["original_entry_bytes"][
            "skills/specification-to-source/legacy-project-shim/SKILL.md"
        ] += b"\nOperator custom text\n"
        with self.assertRaises(ValueError):
            production.project_recorded_legacy_wrapper_authority(**args)

    def test_new_unselected_roots_and_changed_driver_policy_refuse(self):
        for change in ("root", "policy"):
            with self.subTest(change=change):
                args = self.fixture()
                original = production.parse_project_configuration(
                    args["prospective_definition_bytes"]
                )
                changed = (
                    replace(original, component_roots=("other-components",))
                    if change == "root"
                    else replace(original, test_receipt_policy=None)
                )
                args["prospective_definition_bytes"] = serialize_project_configuration(
                    changed
                )
                with self.assertRaises(ValueError):
                    production.project_recorded_legacy_wrapper_authority(**args)

    def test_original_renderer_substitution_refuses_without_call(self):
        args = self.fixture()
        with patch.object(
            renderer, "legacy_shim_authority", side_effect=AssertionError("foreign")
        ) as foreign:
            with self.assertRaises(ValueError):
                production.project_recorded_legacy_wrapper_authority(**args)
            foreign.assert_not_called()
