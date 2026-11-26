"""Real root conversion without fabricated empty catalog provenance."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.project_layout_migration import (
    apply_legacy_layout_migration,
    plan_legacy_layout_migration,
    recover_legacy_layout_migration,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_json_bytes
from tests.e2e import test_retained_harness_receipts as original


class LayoutMigrationWithoutImportsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.template = Path(temporary.name).resolve() / "legacy"
        original._legacy_project(cls.template)
        original._adapter().initialize(
            cls.template,
            flavor_selectors=original._selectors(cls.template),
            source_intelligence_provider="none",
            convert=True,
        )
        assert not (cls.template / ".literate/imports.json").exists()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "project"
        shutil.copytree(self.template, self.root)
        for arguments in (
            ("init", "-q", "-b", "main"),
            ("add", "."),
            (
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=layout@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "Original",
            ),
        ):
            self.git(*arguments)

    def git(self, *arguments):
        return subprocess.check_output(
            ["git", *arguments], cwd=self.root, stderr=subprocess.STDOUT, timeout=15
        )

    def plan(self, **options):
        return plan_legacy_layout_migration(
            self.root, (), place_forward_skills=False, **options
        )

    def test_root_metadata_apply_and_repeated_recovery_preserve_absence(self):
        head, index = (
            self.git("rev-parse", "HEAD"),
            (self.root / ".git/index").read_bytes(),
        )
        manifest = (self.root / "literate.project.json").read_bytes()
        plan = self.plan()
        self.assertEqual(
            {row["path"] for row in plan["blocked_references"]},
            {"docs/user/project-layout.md"},
        )
        references = ("docs/user/project-layout.md",)
        plan = plan_legacy_layout_migration(
            self.root, references, place_forward_skills=False
        )
        self.assertTrue(plan["applicable"], plan["blocked_references"])
        self.assertNotIn(".literate/imports.json", plan["move"])
        result = apply_legacy_layout_migration(
            self.root,
            plan["plan_identity"],
            acknowledge=True,
            references=references,
            place_forward_skills=False,
        )
        self.assertTrue(result["applied"])
        self.assertFalse((self.root / "litai/.literate/imports.json").exists())
        self.assertFalse((self.root / "literate.project.json").exists())
        result = recover_legacy_layout_migration(
            self.root, plan["plan_identity"], acknowledge=True
        )
        self.assertTrue(result["rolled_back"])
        with self.assertRaises(ProjectLayoutPlanError) as raised:
            recover_legacy_layout_migration(
                self.root, plan["plan_identity"], acknowledge=True
            )
        self.assertEqual(raised.exception.code, "project.layout.recovery_unavailable")
        self.assertEqual((self.root / "literate.project.json").read_bytes(), manifest)
        self.assertFalse((self.root / ".literate/imports.json").exists())
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual((self.root / ".git/index").read_bytes(), index)

    def test_missing_other_producer_is_not_optional(self):
        (self.root / ".literate/update-bases.json").unlink()
        with self.assertRaises(ProjectLayoutPlanError):
            self.plan()

    def test_catalog_history_without_imports_refuses(self):
        path = self.root / ".literate/update-bases.json"
        value = json.loads(path.read_bytes())
        value["catalog"]["application.py"] = "sha256:" + "a" * 64
        path.write_bytes(canonical_json_bytes(value))
        with self.assertRaises(ProjectLayoutPlanError) as raised:
            self.plan()
        self.assertEqual(raised.exception.code, "project.layout.migration_profile")

    def test_missing_imports_does_not_authorize_imported_placement(self):
        with self.assertRaises(ProjectLayoutPlanError):
            self.plan(place_imported_catalogs=True)

    def test_malformed_present_imports_still_refuses(self):
        (self.root / ".literate/imports.json").write_bytes(b'{"schema":"wrong"}')
        with self.assertRaises(ValueError):
            self.plan()
