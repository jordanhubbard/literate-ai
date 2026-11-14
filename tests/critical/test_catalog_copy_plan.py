"""Actual bounded catalog/DAG observations, with no copy or ownership effects."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

from literate_ai.adapters import catalog_copy_plan as plans
from literate_ai.adapters.catalog_import import CatalogImportError, catalog_copy
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from tests.support.fixtures_test_catalog_import import make_project


class CatalogCopyPlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = make_project(self.base / "source", "source-project")
        self.root = make_project(self.base / "dest", "destination-project")
        self.item = self.source / "flavors/local-toolchain"
        self.item.mkdir(parents=True)
        self.payload = self.item / "flavor.md"
        self.payload.write_bytes(b"---\nname: local-toolchain\n---\n")
        self.budget = RetainedCargoInputBudget(1024, 8192, 4 * 1024**2, 64 * 1024**2)

    def plan(self, **kwargs):
        return plans.plan_catalog_copy(
            self.root,
            self.source,
            ("flavor:local-toolchain",),
            budget=kwargs.pop("budget", self.budget),
            maximum_metadata_bytes=2 * 1024**3,
            **kwargs,
        )

    def test_plan_is_read_only_and_document_is_detached(self):
        before = {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in self.root.rglob("*")
            if p.is_file()
        }
        plan = self.plan()
        plan.require_current()
        document = plan.document
        document["items"].append(["flavor", "forged"])
        self.assertEqual(plan.document["items"], [["flavor", "local-toolchain"]])
        self.assertFalse((self.root / "flavors").exists())
        self.assertFalse(hasattr(plan, "spend"))
        with self.assertRaises(FrozenInstanceError):
            plan.overwrite = True
        self.assertEqual(
            before,
            {
                str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*")
                if p.is_file()
            },
        )

    def test_actual_canonical_selector_mapping_and_nested_skill_are_observed(self):
        item = self.source / "skills/agent/nested"
        item.mkdir(parents=True)
        (item / "SKILL.md").write_bytes(b"nested skill\n")
        plan = plans.plan_catalog_copy(
            self.root,
            self.source,
            ("skill:agent/nested", "flavor:local-toolchain"),
            budget=self.budget,
            maximum_metadata_bytes=2 * 1024**3,
        )
        self.assertEqual(plan.items[0], ("skill", "agent/nested"))
        self.assertEqual(len(plan.document["namespaces"]), 3)

    def test_missing_optional_metadata_remains_a_bound_absence(self):
        for root in (self.root, self.source):
            (root / ".literate/initialization-origin.json").unlink()
            (root / ".literate").rmdir()
        plan = self.plan()
        plan.require_current()
        (self.source / ".literate").mkdir()
        with self.assertRaises(ValueError):
            plan.require_current()

    def test_unknown_destination_entries_remain_in_complete_census(self):
        (self.root / "ignored-looking").mkdir()
        unknown = self.root / "ignored-looking/.foreign"
        unknown.write_bytes(b"original unknown bytes\n")
        plan = self.plan()
        self.assertIn("ignored-looking/.foreign", plan._censuses[0].other_files)
        unknown.write_bytes(b"foreign changed bytes\n")
        with self.assertRaises(ValueError):
            plan.require_current()
        self.assertEqual(unknown.read_bytes(), b"foreign changed bytes\n")

    def test_source_payload_and_new_members_refuse_without_mutation(self):
        plan = self.plan()
        added = self.item / "future-file"
        added.write_bytes(b"new member\n")
        with self.assertRaises(ValueError):
            plan.require_current()
        self.assertTrue(added.is_file())
        self.assertFalse((self.root / "flavors").exists())

    def test_overwrite_plan_binds_old_tree_without_deleting_it(self):
        old = self.root / "flavors/local-toolchain"
        old.mkdir(parents=True)
        (old / "foreign-neighbor").write_bytes(b"preserve old neighbor\n")
        plan = self.plan(overwrite=True)
        self.assertTrue(plan.overwrite)
        self.assertEqual(
            (old / "foreign-neighbor").read_bytes(), b"preserve old neighbor\n"
        )
        with self.assertRaises(CatalogImportError) as raised:
            self.plan()
        self.assertEqual(raised.exception.code, "catalog.import_conflict")

    def test_dag_cycle_uses_actual_canonical_ancestry_reader(self):
        imports = self.source / ".literate/imports.json"
        imports.write_text(
            json.dumps(
                {
                    "imports": [
                        {
                            "kind": "flavor",
                            "name": "ancestry",
                            "source": {
                                "project_id": "destination-project",
                                "project_identity": "sha256:" + "a" * 64,
                                "ref": "local:descriptive-only",
                                "transitive_ancestors": [],
                            },
                            "files": [],
                            "copied_at": "2026-01-01T00:00:00+00:00",
                        }
                    ]
                }
            )
        )
        with self.assertRaises(CatalogImportError) as raised:
            self.plan()
        self.assertEqual(raised.exception.code, "catalog.import_cycle")
        self.assertFalse((self.root / "flavors").exists())

    def test_full_namespace_and_metadata_share_file_allowance(self):
        budget = RetainedCargoInputBudget(4, 8192, 4 * 1024**2, 16 * 1024**2)
        with self.assertRaisesRegex(ValueError, "shared allowance"):
            self.plan(budget=budget)
        self.assertFalse((self.root / "flavors").exists())

    def test_decoded_metadata_consumes_entry_allowance(self):
        budget = RetainedCargoInputBudget(32, 32, 4 * 1024**2, 64 * 1024**2)
        with self.assertRaisesRegex(ValueError, "decoded canonical metadata"):
            self.plan(budget=budget)

    def test_oversized_selected_payload_is_refused_without_legacy_reads(self):
        self.payload.write_bytes(b"x" * (64 * 1024 + 1))
        budget = RetainedCargoInputBudget(1024, 8192, 64 * 1024, 16 * 1024**2)
        with (
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("legacy")),
            mock.patch.object(Path, "read_text", side_effect=AssertionError("legacy")),
            self.assertRaises(ValueError),
        ):
            self.plan(budget=budget)
        self.assertEqual(self.payload.stat().st_size, 64 * 1024 + 1)

    def test_strict_canonical_readers_do_not_use_legacy_payload_methods(self):
        with (
            mock.patch.object(Path, "read_bytes", side_effect=AssertionError("legacy")),
            mock.patch.object(Path, "read_text", side_effect=AssertionError("legacy")),
        ):
            plan = self.plan()
            plan.require_current()

    def test_source_change_after_final_metadata_payload_is_closed(self):
        plan = self.plan()
        last = plan._inputs[-1].path
        original = plans._file
        changed = False

        def read_then_change(path, **kwargs):
            nonlocal changed
            item = original(path, **kwargs)
            if path == last and not changed:
                changed = True
                self.payload.write_bytes(b"changed after metadata read\n")
            return item

        with mock.patch.object(plans, "_file", read_then_change):
            with self.assertRaises(ValueError):
                plan.require_current()
        self.assertTrue(changed)
        self.assertEqual(self.payload.read_bytes(), b"changed after metadata read\n")

    def test_metadata_change_after_last_namespace_traversal_refuses(self):
        plan = self.plan()
        close = plans._close_tree
        changed = False
        source_manifest = self.source / "literate.project.json"

        def close_then_change(tree, native, **kwargs):
            nonlocal changed
            close(tree, native, **kwargs)
            if tree.root == self.item and not changed:
                changed = True
                value = json.loads(source_manifest.read_bytes())
                value["project_id"] = "changed-after-last-enumeration"
                source_manifest.write_text(json.dumps(value))

        with mock.patch.object(plans, "_close_tree", close_then_change):
            with self.assertRaises(ValueError):
                plan.require_current()
        self.assertTrue(changed)
        self.assertEqual(
            json.loads(source_manifest.read_bytes())["project_id"],
            "changed-after-last-enumeration",
        )

    def test_destination_insertion_after_last_source_traversal_refuses(self):
        plan = self.plan()
        close = plans._close_tree
        changed = False
        added = self.root / "foreign-after-last-enumeration"

        def close_then_add(tree, native, **kwargs):
            nonlocal changed
            close(tree, native, **kwargs)
            if tree.root == self.item and not changed:
                changed = True
                added.write_bytes(b"foreign destination member\n")

        with mock.patch.object(plans, "_close_tree", close_then_add):
            with self.assertRaises(ValueError):
                plan.require_current()
        self.assertTrue(changed)
        self.assertEqual(added.read_bytes(), b"foreign destination member\n")

    def test_actual_selector_mapping_change_refuses(self):
        plan = self.plan()
        with mock.patch.dict(plans.catalog_import._KIND_DIR, {"flavor": "other"}):
            with self.assertRaisesRegex(ValueError, "selector mapping changed"):
                plan.require_current()

    def test_saved_import_rows_do_not_remove_unknown_destination_members(self):
        unknown = self.root / "unknown-input"
        unknown.write_bytes(b"still an actual namespace member\n")
        imports = self.root / ".literate/imports.json"
        imports.write_text(
            json.dumps(
                {
                    "imports": [
                        {
                            "kind": "flavor",
                            "name": "forged",
                            "source": {
                                "project_id": "unverified-source",
                                "project_identity": "sha256:" + "a" * 64,
                                "ref": "local:descriptive-only",
                                "transitive_ancestors": [],
                            },
                            "files": [
                                {"path": "unknown-input", "identity": "arbitrary"}
                            ],
                            "copied_at": "2026-01-01T00:00:00+00:00",
                        }
                    ]
                }
            )
        )
        plan = self.plan()
        self.assertIn("unknown-input", plan._censuses[0].other_files)
        self.assertEqual(plan._censuses[0].framework_files, ())

    def test_later_metadata_growth_keeps_the_original_read_bound(self):
        plan = self.plan()
        origin = self.source / ".literate/initialization-origin.json"
        original_size = origin.stat().st_size
        origin.write_bytes(b" " * (4 * 1024**2 + 1))
        read = plans._file
        limits = []

        def observe_bound(path, **kwargs):
            if path == origin:
                limits.append(kwargs["maximum_bytes"])
            return read(path, **kwargs)

        with mock.patch.object(plans, "_file", observe_bound):
            with self.assertRaises(ValueError):
                plan.require_current()
        self.assertEqual(limits, [original_size])
        self.assertEqual(origin.stat().st_size, 4 * 1024**2 + 1)

    def test_invalid_selectors_and_same_source_destination_refuse(self):
        for selectors in ([], (), ("flavor:../escape",), ("flavor:/absolute",)):
            with self.subTest(selectors=selectors), self.assertRaises(ValueError):
                plans.plan_catalog_copy(
                    self.root,
                    self.source,
                    selectors,
                    budget=self.budget,
                    maximum_metadata_bytes=2 * 1024**3,
                )
        with self.assertRaisesRegex(ValueError, "overlaps"):
            plans.plan_catalog_copy(
                self.source,
                self.source,
                ("flavor:local-toolchain",),
                budget=self.budget,
                maximum_metadata_bytes=2 * 1024**3,
                overwrite=True,
            )

    @unittest.skipUnless(os.name == "posix", "native internal links")
    def test_internal_aliases_modes_and_complete_hardlinks_are_observed(self):
        os.chmod(self.payload, 0o755)
        os.link(self.payload, self.item / "hardlink")
        (self.item / "symlink").symlink_to("flavor.md")
        plan = self.plan()
        tree = plan._censuses[-1].tree
        self.assertEqual({a.kind for a in tree.aliases}, {"hardlink", "symlink"})
        self.assertTrue(tree.files[0][2])
        plan.require_current()

    def test_ordinary_invalid_destination_retains_typed_error(self):
        (self.root / "literate.project.json").write_bytes(b"{}\n")
        with self.assertRaises(CatalogImportError) as raised:
            catalog_copy(self.root, str(self.source), ["flavor:local-toolchain"])
        self.assertEqual(raised.exception.code, "catalog.import_destination_invalid")
