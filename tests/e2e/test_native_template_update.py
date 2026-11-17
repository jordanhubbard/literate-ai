"""Contained upgrades reuse three-way merging and preserve native application files."""

from __future__ import annotations

import io
import json
import os
import unittest
from unittest.mock import patch

from literate_ai.adapters import native_project_bootstrap
from literate_ai.cli.dispatch import main
from literate_ai.contracts import (
    CatalogImport,
    CatalogImportFile,
    CatalogImportsFile,
    CatalogImportSource,
)
from literate_ai.project_authority_graph import project_authority_graph
from tests.support.native_repository import NativeRepositoryFixture


class NativeTemplateUpdateTests(unittest.TestCase):
    def setUp(self):
        self.fixture = NativeRepositoryFixture()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        plan = self.fixture.cli("onboard", "adopt", self.root)["result"]
        self.fixture.cli(
            "onboard",
            "adopt",
            self.root,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
        )
        self.templates = native_project_bootstrap.native_template_files()
        self.addCleanup(patch.stopall)
        patch.object(
            native_project_bootstrap,
            "native_template_files",
            side_effect=lambda: dict(self.templates),
        ).start()

    def update(self, *options):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"LITAI_NO_SELF_UPDATE": "1"}):
            status = main(
                ["--json", "update", str(self.root), *options],
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(status, 0, stdout.getvalue() + stderr.getvalue())
        return json.loads(stdout.getvalue())["result"]

    def test_two_upgrades_keep_local_policy_and_advance_the_base(self):
        relative = "litai/docs/adoption.md"
        path = self.root / relative
        original = path.read_bytes()
        local = original + b"\nLocal review policy stays with this repository.\n"
        path.write_bytes(local)
        for version in ("Second", "Third"):
            self.templates[relative] = original.replace(
                b"# Native repository adoption", f"# {version} native adoption".encode()
            )
            planned = self.update()
            self.assertEqual(
                path.read_bytes(), local, "planning must not write the local overlay"
            )
            applied = self.update("--apply")
            self.assertIn(relative, applied["application"]["merged"])
            self.assertTrue(applied["authority_review_required"])
            local = self.templates[relative] + (
                b"\nLocal review policy stays with this repository.\n"
            )
            self.assertEqual(path.read_bytes(), local)
            self.assertEqual(planned["mode"], "read-only-plan")
            self.fixture.assert_original()
        current = self.update("--apply")
        self.assertEqual(current["application"]["applied"], [])
        self.assertEqual(current["application"]["merged"], [])
        self.assertEqual(path.read_bytes(), local)
        self.fixture.assert_original()
        self.fixture.git("add", "litai")
        self.fixture.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "reviewed template upgrades",
        )
        removal = self.fixture.cli("onboard", "remove", self.root)["result"]
        self.assertEqual(removal["retained"][relative], "customized")
        self.fixture.cli(
            "onboard",
            "remove",
            self.root,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            removal["plan_identity"],
        )
        self.assertEqual(path.read_bytes(), local)
        self.assertTrue((self.root / ".github/workflows/native.yml").is_file())

    def test_overlapping_policy_edit_is_preserved_as_an_unresolved_conflict(self):
        relative = "litai/docs/adoption.md"
        path = self.root / relative
        original = path.read_bytes()
        local = original.replace(b"# Native repository adoption", b"# Local policy")
        path.write_bytes(local)
        self.templates[relative] = original.replace(
            b"# Native repository adoption", b"# Changed upstream policy"
        )
        checkpoint = self.root / "litai/.literate/update-bases.json"
        before = checkpoint.read_bytes()
        result = self.update("--apply")
        self.assertIn(relative, result["application"]["refused"]["conflict"])
        self.assertEqual(path.read_bytes(), local)
        self.assertEqual(checkpoint.read_bytes(), before)
        self.fixture.assert_original()

    def test_application_catalog_lookalikes_cannot_suppress_native_policy_updates(self):
        relative = "litai/docs/adoption.md"
        self.templates[relative] += b"\nNew upstream policy.\n"
        planned = self.update()["framework"]
        graph = project_authority_graph(self.root).to_dict()
        imports = CatalogImportsFile(
            (
                CatalogImport(
                    "skill",
                    "unrelated-application-catalog",
                    CatalogImportSource(
                        "application-owned", "sha256:" + "a" * 64, "local:unused", ()
                    ),
                    (CatalogImportFile(relative, "sha256:" + "b" * 64),),
                    "2026-01-01T00:00:00Z",
                ),
            )
        )
        path = self.root / CatalogImportsFile.PATH
        path.parent.mkdir()
        for content in (json.dumps(imports.to_dict()).encode(), b"not framework JSON"):
            with self.subTest(content=content[:20]):
                path.write_bytes(content)
                self.assertEqual(self.update()["framework"], planned)
                self.assertEqual(project_authority_graph(self.root).to_dict(), graph)
                self.assertEqual(path.read_bytes(), content)
        result = self.update("--apply")
        self.assertIn(relative, result["application"]["applied"])
        self.assertEqual((self.root / relative).read_bytes(), self.templates[relative])
        self.assertEqual(path.read_bytes(), b"not framework JSON")
        self.fixture.assert_original()
