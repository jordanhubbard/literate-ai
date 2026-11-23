"""Reviewed renewal planning preserves the original admitted command authority."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters.monorepo_adoption import SELECTION_SCHEMA
from tests.e2e import test_retained_harness_readmission as fixtures


class RetainedCommandRenewalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RetainedHarnessReadmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedHarnessReadmissionTests.setUp(self)
        self.selection_path = self.base / "commands.json"
        self.selection = {
            "schema": SELECTION_SCHEMA,
            "components": [
                {
                    "name": "legacy-project-wrapper",
                    "root": ".",
                    "commands": [
                        {
                            "id": "build",
                            "command": "make -f Makefile package",
                            "cwd": ".",
                            "evidence": "Makefile",
                        }
                    ],
                }
            ],
            "shared_sources": [],
        }
        self.write_selection()

    def write_selection(self):
        self.selection_path.write_text(json.dumps(self.selection), encoding="utf-8")

    def plan(self):
        return readmission.plan_retained_harness_readmission(
            self.root, command_selection=self.selection_path
        )

    def snapshot(self):
        return {
            p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file() and not p.is_symlink()
        }

    def test_plan_is_read_only_and_retains_every_unselected_admitted_phase(self):
        original = json.loads((self.root / readmission.INVENTORY).read_bytes())
        before = self.snapshot()
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch.object(
                readmission, "_parity_report", side_effect=AssertionError
            ),
        ):
            plan = self.plan()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(
            plan["schema"], "literate-ai/retained-harness-readmission-plan@2"
        )
        actual = plan["new_inventory"]["stages"]
        self.assertEqual(
            [s for s in actual if s["id"].split(".", 1)[0] != "build"],
            [s for s in original["stages"] if s["id"].split(".", 1)[0] != "build"],
        )
        self.assertEqual(
            [s["command"] for s in actual if s["id"] == "build"],
            ["make -f Makefile package"],
        )
        self.assertEqual(plan["command_renewal"]["compilation_coverage"], "unknown")
        self.assertFalse(plan["command_renewal"]["execution_performed"])
        self.assertFalse(plan["apply_supported"])

    def test_old_custom_unselected_stage_is_preserved_without_rediscovery(self):
        path = self.root / readmission.INVENTORY
        inventory = json.loads(path.read_bytes())
        old = {
            "id": "test.original-custom",
            "command": "printf 'original custom test\\n'",
            "cwd": ".",
            "evidence": "Makefile",
            "cost": "host-heavy",
        }
        inventory["stages"].append(old)
        path.write_text(json.dumps(inventory), encoding="utf-8")
        self.assertIn(old, self.plan()["new_inventory"]["stages"])

    def test_selection_changes_plan_identity_and_binds_exact_old_commands(self):
        first = self.plan()
        self.selection["components"][0]["commands"][0]["command"] = "make build"
        self.write_selection()
        second = self.plan()
        self.assertNotEqual(first["plan_identity"], second["plan_identity"])
        inventory = json.loads((self.root / readmission.INVENTORY).read_bytes())
        self.assertEqual(first["command_renewal"]["old_stages"], inventory["stages"])

    def test_empty_selection_cannot_remove_an_admitted_phase(self):
        self.selection["components"][0]["commands"] = []
        self.write_selection()
        before = self.snapshot()
        with self.assertRaises(ValueError) as caught:
            self.plan()
        self.assertEqual(caught.exception.code, "monorepo.commands_missing")
        self.assertEqual(self.snapshot(), before)

    def test_foreign_wrapper_owner_refuses(self):
        self.selection["components"][0]["name"] = "other-wrapper"
        self.write_selection()
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.plan()
        self.assertEqual(
            caught.exception.code, "retained_harness.command_owner_invalid"
        )

    def test_late_selection_change_refuses_before_exposing_plan(self):
        original = readmission.observe_retained_tree

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.selection["components"][0]["commands"][0]["command"] = "make test"
            self.write_selection()
            return result

        with mock.patch.object(
            readmission, "observe_retained_tree", side_effect=changed
        ):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                self.plan()
        self.assertEqual(
            caught.exception.code, "retained_harness.command_selection_stale"
        )

    def test_late_source_change_refuses_before_exposing_plan(self):
        original = readmission.observe_retained_tree

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            (self.source / "app.py").write_text("print('concurrent edit')\n")
            return result

        with mock.patch.object(
            readmission, "observe_retained_tree", side_effect=changed
        ):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                self.plan()
        self.assertEqual(
            caught.exception.code, "retained_harness.command_selection_stale"
        )
        self.assertEqual(
            (self.source / "app.py").read_text(), "print('concurrent edit')\n"
        )

    def test_renewal_plan_cannot_acquire_existing_apply_authority(self):
        plan = self.plan()
        # The existing mutation lock intentionally retains its stable lock file.
        # Seed that real owner before comparing all bytes across the refusal.
        with readmission.project_lifecycle_lock(
            self.root, operation="test.preexisting"
        ):
            pass
        before = self.snapshot()
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch.object(
                readmission, "_parity_report", side_effect=AssertionError
            ),
        ):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                readmission.apply_retained_harness_readmission(
                    self.root,
                    expected_plan_identity=plan["plan_identity"],
                    acknowledge=True,
                    timeout_seconds=1800,
                    execution_worker=None,
                    worker_catalog_identity=None,
                )
        self.assertEqual(caught.exception.code, "retained_harness.plan_stale")
        self.assertEqual(self.snapshot(), before)

    def test_newly_detected_unselected_phase_gains_no_command_authority(self):
        path = self.root / readmission.INVENTORY
        inventory = json.loads(path.read_bytes())
        inventory["stages"] = [
            stage for stage in inventory["stages"] if stage["id"] != "package"
        ]
        inventory["commands"].pop("package", None)
        path.write_text(json.dumps(inventory), encoding="utf-8")
        plan = self.plan()
        self.assertTrue(
            any(
                stage["id"] == "package"
                for stage in plan["command_renewal"]["detected_stages"]
            )
        )
        self.assertFalse(
            any(stage["id"] == "package" for stage in plan["new_inventory"]["stages"])
        )

    def test_default_plan_keeps_its_existing_version_and_identity(self):
        first = readmission.plan_retained_harness_readmission(self.root)
        second = readmission.plan_retained_harness_readmission(
            self.root, command_selection=None
        )
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], readmission.PLAN_SCHEMA)
        self.assertNotIn("command_renewal", first)

    def test_conflicting_old_stage_selection_refuses(self):
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            readmission.plan_retained_harness_readmission(
                self.root,
                command_selection=self.selection_path,
                retained_stage_ids=("build",),
            )
        self.assertEqual(
            caught.exception.code, "retained_harness.command_selection_conflict"
        )

    def test_unknown_retained_stage_refuses_in_renewal_mode(self):
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            readmission.plan_retained_harness_readmission(
                self.root,
                command_selection=self.selection_path,
                retained_stage_ids=("test.foreign",),
            )
        self.assertEqual(caught.exception.code, "retained_harness.stage_not_admitted")

    def test_source_change_during_final_metadata_read_refuses(self):
        original = readmission._safe_path
        inventory_reads = 0

        def changed(root, relative, **kwargs):
            nonlocal inventory_reads
            path = original(root, relative, **kwargs)
            if root == self.root and relative == readmission.INVENTORY:
                inventory_reads += 1
                if inventory_reads == 2:
                    (self.source / "app.py").write_text("print('late metadata edit')\n")
            return path

        with mock.patch.object(readmission, "_safe_path", side_effect=changed):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                self.plan()
        self.assertEqual(
            caught.exception.code, "retained_harness.command_selection_stale"
        )
        self.assertEqual(inventory_reads, 2)

    def test_same_byte_source_replacement_during_metadata_read_refuses(self):
        original = readmission._safe_path
        inventory_reads = 0
        source = self.source / "app.py"
        before = source.read_bytes()
        original_inode = source.stat().st_ino

        def changed(root, relative, **kwargs):
            nonlocal inventory_reads
            path = original(root, relative, **kwargs)
            if root == self.root and relative == readmission.INVENTORY:
                inventory_reads += 1
                if inventory_reads == 2:
                    replacement = self.source / "replacement.py"
                    replacement.write_bytes(before)
                    replacement.chmod(source.stat().st_mode)
                    replacement.replace(source)
            return path

        with mock.patch.object(readmission, "_safe_path", side_effect=changed):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                self.plan()
        self.assertEqual(
            caught.exception.code, "retained_harness.command_selection_stale"
        )
        self.assertEqual(source.read_bytes(), before)
        self.assertNotEqual(source.stat().st_ino, original_inode)

    def test_new_source_in_preexisting_empty_directory_during_metadata_read_refuses(
        self,
    ):
        directory = self.source / "original-empty"
        directory.mkdir()
        original = readmission._safe_path
        inventory_reads = 0

        def changed(root, relative, **kwargs):
            nonlocal inventory_reads
            path = original(root, relative, **kwargs)
            if root == self.root and relative == readmission.INVENTORY:
                inventory_reads += 1
                if inventory_reads == 2:
                    (directory / "late.py").write_text("print('new source')\n")
            return path

        with mock.patch.object(readmission, "_safe_path", side_effect=changed):
            with self.assertRaises(
                readmission.RetainedHarnessReadmissionError
            ) as caught:
                self.plan()
        self.assertEqual(
            caught.exception.code, "retained_harness.command_selection_stale"
        )
        self.assertEqual((directory / "late.py").read_text(), "print('new source')\n")
