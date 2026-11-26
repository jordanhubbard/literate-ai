"""Real root conversion without fabricated empty catalog provenance."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.project_layout_migration import (
    _reference_framework_base_transition,
    apply_legacy_layout_migration,
    plan_legacy_layout_migration,
    recover_legacy_layout_migration,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import canonical_json_bytes
from literate_ai.contracts.catalog_imports import (
    CatalogImportFile,
    CatalogImportsFile,
    CatalogImportSource,
    CatalogInheritanceDecision,
)
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
        return original._fixture_git(self.root, *arguments)

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
        checkpoint = (self.root / ".literate/update-bases.json").read_bytes()
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
        reference = "docs/user/project-layout.md"
        rewritten = (self.root / reference).read_bytes()
        identity = "sha256:" + hashlib.sha256(rewritten).hexdigest()
        bases = UpdateBases(self.root)
        self.assertEqual(bases.scopes["framework"].get(reference), identity)
        self.assertEqual(bases.blobs[identity], rewritten)
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
        self.assertEqual(
            (self.root / ".literate/update-bases.json").read_bytes(), checkpoint
        )
        self.assertFalse((self.root / ".literate/imports.json").exists())
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual((self.root / ".git/index").read_bytes(), index)

    def test_approved_application_reference_does_not_acquire_framework_base(self):
        path = "docs/application-notes.md"
        original = b"# Local notes\nSee [manifest](../literate.project.json).\n"
        (self.root / path).write_bytes(original)
        references = ("docs/user/project-layout.md", path)
        self.assertNotIn(path, UpdateBases(self.root).scopes["framework"])
        plan = plan_legacy_layout_migration(
            self.root, references, place_forward_skills=False
        )
        self.assertTrue(plan["applicable"], plan["blocked_references"])
        apply_legacy_layout_migration(
            self.root,
            plan["plan_identity"],
            acknowledge=True,
            references=references,
            place_forward_skills=False,
        )
        self.assertNotIn(path, UpdateBases(self.root).scopes["framework"])
        self.assertIn(
            b"](../litai/literate.project.json)", (self.root / path).read_bytes()
        )
        recover_legacy_layout_migration(
            self.root, plan["plan_identity"], acknowledge=True
        )
        self.assertEqual((self.root / path).read_bytes(), original)

    def test_edited_framework_reference_keeps_original_framework_base(self):
        path = "docs/user/project-layout.md"
        before = dict(UpdateBases(self.root).scopes["framework"])
        original = (
            self.root / path
        ).read_bytes() + b"\nApplication-owned local notes.\n"
        (self.root / path).write_bytes(original)
        references = (path,)
        plan = plan_legacy_layout_migration(
            self.root, references, place_forward_skills=False
        )
        self.assertTrue(plan["applicable"], plan["blocked_references"])
        apply_legacy_layout_migration(
            self.root,
            plan["plan_identity"],
            acknowledge=True,
            references=references,
            place_forward_skills=False,
        )
        self.assertEqual(
            UpdateBases(self.root).scopes["framework"].get(path), before.get(path)
        )
        self.assertIn(
            b"Application-owned local notes.", (self.root / path).read_bytes()
        )
        recover_legacy_layout_migration(
            self.root, plan["plan_identity"], acknowledge=True
        )
        self.assertEqual((self.root / path).read_bytes(), original)

    def test_inheritance_decisions_do_not_acquire_framework_reference_bases(self):
        # Explicitly modeled history tests only the original data join; it does
        # not claim a qualified import, parent transition or whole migration.
        path = "skills/specification-to-source/legacy-project-shim/SKILL.md"
        original = (self.root / path).read_bytes()
        identity = "sha256:" + hashlib.sha256(original).hexdigest()
        baseline = json.loads(
            (self.root / ".literate/initialization-baseline.json").read_bytes()
        )
        self.assertIn(path, {row["path"] for row in baseline["files"]})
        checkpoint = (self.root / ".literate/update-bases.json").read_bytes()
        records = (
            ".literate/initialization-baseline.json",
            ".literate/initialization-origin.json",
            ".literate/update-bases.json",
        )
        eligible = {
            name: {
                "identity": "sha256:"
                + hashlib.sha256((self.root / name).read_bytes()).hexdigest()
            }
            for name in records
        }
        self.assertTrue(
            _reference_framework_base_transition(
                self.root,
                eligible,
                {},
                {path: {"from": identity}},
                {path: original + b"\nExplicit reference rewrite fixture.\n"},
            )
            is not None,
            "fixture must independently qualify before inherited history is added",
        )
        source = CatalogImportSource(
            "historical-upstream",
            "sha256:" + "c" * 64,
            "git:https://example.invalid/upstream.git@" + "a" * 40,
            (),
        )
        for disposition in ("effective", "shadowed", "withheld"):
            with self.subTest(disposition=disposition):
                decision = CatalogInheritanceDecision(
                    "skill",
                    "specification-to-source/legacy-project-shim",
                    source,
                    (CatalogImportFile(path, identity),),
                    disposition,
                    "selected-upstream" if disposition == "shadowed" else None,
                )
                self.root.joinpath(".literate/imports.json").write_bytes(
                    canonical_json_bytes(
                        CatalogImportsFile((), decisions=(decision,)).to_dict()
                    )
                    + b"\n"
                )
                files = {}
                for name in (
                    ".literate/initialization-baseline.json",
                    ".literate/initialization-origin.json",
                    ".literate/update-bases.json",
                    ".literate/imports.json",
                ):
                    raw = (self.root / name).read_bytes()
                    files[name] = {
                        "identity": "sha256:" + hashlib.sha256(raw).hexdigest()
                    }
                result = _reference_framework_base_transition(
                    self.root,
                    files,
                    {},
                    {path: {"from": identity}},
                    {path: original + b"\nExplicit reference rewrite fixture.\n"},
                )
                self.assertTrue(
                    result is None, "inherited history gained framework base"
                )
                self.assertEqual(
                    (self.root / ".literate/update-bases.json").read_bytes(), checkpoint
                )
                self.assertEqual((self.root / path).read_bytes(), original)

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
