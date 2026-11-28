"""Refined command preparation preserves actual installed ownership and evidence."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import monorepo_components as components
from literate_ai.adapters import retained_component_commands as renewal
from literate_ai.adapters.monorepo_adoption import (
    SELECTION_SCHEMA,
    MonorepoAdoptionError,
)
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from tests.e2e import test_monorepo_components as fixtures


class RetainedComponentCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="component-command-template-")
        cls.addClassCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        fixture = fixtures.MonorepoComponentTests()
        fixture._init_source(base)
        manifest = fixture.stage()
        receipts = {name: fixture.run_component(name)[0] for name in ("kit", "runtime")}
        cls.template = base / "project"
        cls.template.mkdir()
        source = cls.template / "retained"
        shutil.copytree(fixture.source, source)
        components.install_monorepo_components(
            source,
            fixture.bundle,
            cls.template,
            receipts,
            expected_bundle_identity=manifest["bundle_identity"],
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="component-command-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.project = self.base / "project"
        shutil.copytree(self.template, self.project)
        self.selection_path = self.base / "commands.json"
        self.selection = {
            "schema": SELECTION_SCHEMA,
            "components": [
                {
                    "name": "kit",
                    "root": "kit",
                    "commands": [
                        {
                            "id": "build",
                            "command": "make -f Makefile",
                            "cwd": "kit",
                            "evidence": "kit/Makefile",
                        }
                    ],
                }
            ],
            "shared_sources": [],
        }
        self.write_selection()

    def write_selection(self):
        self.selection_path.write_bytes(canonical_json_bytes(self.selection))

    def plan(self):
        return renewal.plan_installed_component_command_renewal(
            self.project, self.selection_path
        )

    def reopen(self, value, identity=None):
        return renewal.reopen_installed_component_command_renewal_plan(
            self.project,
            canonical_json_bytes(value),
            command_selection=self.selection_path,
            reviewed_plan_identity=identity or value["plan_identity"],
        )

    def snapshot(self):
        return {
            path.relative_to(self.project).as_posix(): (
                path.read_bytes(),
                path.stat().st_ino,
                path.stat().st_mtime_ns,
            )
            for path in self.project.rglob("*")
            if path.is_file()
        }

    def test_readonly_plan_preserves_other_owner_test_and_shared_inputs(self):
        before = self.snapshot()
        with (
            mock.patch.object(
                components, "stage_monorepo_components", side_effect=AssertionError
            ),
            mock.patch.object(
                components, "run_component_retained_harness", side_effect=AssertionError
            ),
            mock.patch("pathlib.Path.write_bytes", side_effect=AssertionError),
            mock.patch("pathlib.Path.write_text", side_effect=AssertionError),
        ):
            plan = self.plan()
        self.assertEqual(self.snapshot(), before)
        old = plan["old_selection"]
        new = plan["new_refinement"]["selection"]
        self.assertEqual(new["shared_sources"], old["shared_sources"])
        old_owners = {item["name"]: item for item in old["components"]}
        new_owners = {item["name"]: item for item in new["components"]}
        self.assertEqual(new_owners["runtime"], old_owners["runtime"])
        self.assertEqual(
            new_owners["kit"]["commands"][0], old_owners["kit"]["commands"][0]
        )
        self.assertEqual(new_owners["kit"]["commands"][1]["id"], "build")
        self.assertEqual(plan["selected_components"], ["kit"])
        self.assertEqual(plan["compilation_coverage"], "unknown")
        self.assertFalse(plan["apply_supported"])
        self.assertFalse(plan["execution_performed"])
        self.assertEqual(self.reopen(plan), plan)

    def test_empty_duplicate_or_foreign_phase_and_owner_requests_refuse(self):
        original = copy.deepcopy(self.selection)
        for case in (
            "empty",
            "duplicate",
            "duplicate-owner",
            "phase",
            "owner",
            "root",
            "shared",
            "evidence",
        ):
            with self.subTest(case=case):
                self.selection = copy.deepcopy(original)
                item = self.selection["components"][0]
                if case == "empty":
                    item["commands"] = []
                elif case == "duplicate":
                    item["commands"] *= 2
                elif case == "duplicate-owner":
                    self.selection["components"] *= 2
                elif case == "phase":
                    item["commands"][0]["id"] = "remove"
                elif case == "owner":
                    item["name"] = "foreign"
                elif case == "root":
                    item["root"] = "runtime"
                elif case == "shared":
                    self.selection["shared_sources"] = [
                        {"path": "shared", "owner": "runtime", "consumers": ["kit"]}
                    ]
                else:
                    item["commands"][0]["evidence"] = "runtime/Makefile"
                self.write_selection()
                before = self.snapshot()
                with self.assertRaises(MonorepoAdoptionError):
                    self.plan()
                self.assertEqual(self.snapshot(), before)

    def test_replacement_preserves_admitted_phase_order_and_other_owner(self):
        initial = self.plan()
        old = initial["old_selection"]
        old_owners = {item["name"]: item for item in old["components"]}
        previous = old_owners["kit"]["commands"][0]
        replacement = {**previous, "command": previous["command"] + " -q"}
        self.selection["components"][0]["commands"] = [replacement]
        self.write_selection()
        plan = self.plan()
        new_owners = {
            item["name"]: item
            for item in plan["new_refinement"]["selection"]["components"]
        }
        self.assertEqual(new_owners["kit"]["commands"], [replacement])
        self.assertEqual(new_owners["runtime"], old_owners["runtime"])
        self.assertEqual(plan["old_selection"], old)

    def test_current_real_receipts_are_bound_without_becoming_new_evidence(self):
        plan = self.plan()
        before = self.snapshot()
        for name in ("kit", "runtime"):
            path = f"{components.INSTALLATION_ROOT}/receipts/{name}.json"
            self.assertIn(path, plan["old_documents"])
        self.assertEqual(self.snapshot(), before)
        path = self.project / f"{components.INSTALLATION_ROOT}/receipts/kit.json"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(MonorepoAdoptionError):
            self.reopen(plan)

    def test_self_rehashed_nested_grants_and_old_review_identity_refuse(self):
        plan = self.plan()
        for key in ("apply_supported", "extra_grant"):
            with self.subTest(key=key):
                changed = copy.deepcopy(plan)
                changed["new_refinement"][key] = (
                    False if key == "apply_supported" else True
                )
                changed["plan_identity"] = canonical_identity(
                    {
                        name: value
                        for name, value in changed.items()
                        if name != "plan_identity"
                    }
                ).uri
                with self.assertRaises(MonorepoAdoptionError):
                    self.reopen(changed)
        with self.assertRaises(MonorepoAdoptionError):
            self.reopen(plan, "sha256:" + "0" * 64)
        changed = copy.deepcopy(plan)
        changed["apply_supported"] = True
        with self.assertRaises(MonorepoAdoptionError) as refused:
            self.reopen(changed)
        self.assertEqual(refused.exception.code, "monorepo.plan_invalid")

    def test_late_foreign_metadata_and_source_mutations_survive_refusal(self):
        original = renewal._plan_monorepo_selection
        receipt = self.project / f"{components.INSTALLATION_ROOT}/receipts/kit.json"
        old = receipt.read_bytes()

        def replaced(*args, **kwargs):
            value = original(*args, **kwargs)
            receipt.write_bytes(old + b"\n")
            return value

        with mock.patch.object(renewal, "_plan_monorepo_selection", replaced):
            with self.assertRaises(MonorepoAdoptionError) as refused:
                self.plan()
        self.assertEqual(refused.exception.code, "monorepo.installation_changed")
        self.assertEqual(receipt.read_bytes(), old + b"\n")
        receipt.write_bytes(old)
        source = self.project / "retained/kit/value.py"

        def changed_source(*args, **kwargs):
            value = original(*args, **kwargs)
            source.write_text("VALUE = 2\n")
            return value

        with mock.patch.object(renewal, "_plan_monorepo_selection", changed_source):
            with self.assertRaises(MonorepoAdoptionError) as refused:
                self.plan()
        self.assertEqual(refused.exception.code, "monorepo.source_changed")
        self.assertEqual(source.read_text(), "VALUE = 2\n")

    def test_saved_plan_is_stale_after_original_source_or_selection_changes(self):
        plan = self.plan()
        original_selection = copy.deepcopy(self.selection)
        self.selection["components"][0]["commands"][0]["command"] += " all"
        self.write_selection()
        with self.assertRaises(MonorepoAdoptionError) as refused:
            self.reopen(plan)
        self.assertEqual(refused.exception.code, "monorepo.plan_stale")
        self.selection = original_selection
        self.write_selection()
        (self.project / "retained/kit/value.py").write_text("VALUE = 2\n")
        with self.assertRaises(MonorepoAdoptionError) as refused:
            self.reopen(plan)
        self.assertEqual(refused.exception.code, "monorepo.plan_stale")

    def test_malformed_owner_metadata_and_nonretained_owner_refuse(self):
        path = self.project / f"{components.INSTALLATION_ROOT}/installation.json"
        before = path.read_bytes()
        for field in ("receipt_identities", "boundary_transfer"):
            with self.subTest(field=field):
                value = json.loads(before)
                value[field] = []
                path.write_bytes(canonical_json_bytes(value) + b"\n")
                with self.assertRaises(MonorepoAdoptionError) as refused:
                    self.plan()
                self.assertEqual(
                    refused.exception.code, "monorepo.installation_invalid"
                )
        for boundary in (True, {"state": "authored", "authority": "native-source"}):
            value = json.loads(before)
            value["boundary_transfer"]["kit"] = boundary
            path.write_bytes(canonical_json_bytes(value) + b"\n")
            with self.assertRaises(MonorepoAdoptionError) as refused:
                self.plan()
            self.assertEqual(refused.exception.code, "monorepo.command_owner_invalid")

    def test_payload_count_limit_refuses_before_any_execution(self):
        before = self.snapshot()
        with mock.patch.object(renewal, "DEFAULT_MAXIMUM_PINNED_INPUT_FILES", 1):
            with self.assertRaises(MonorepoAdoptionError) as refused:
                self.plan()
        self.assertEqual(refused.exception.code, "monorepo.input_limit")
        self.assertEqual(self.snapshot(), before)
