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
from tests.support.native_repository import (
    NativeRepositoryFixture,
    commit_independent_repository,
    git_at,
)


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

    def update(self, *options, success=True):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {"LITAI_NO_SELF_UPDATE": "1"}):
            status = main(
                ["--json", "update", str(self.root), *options],
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(
            status, 0 if success else 2, stdout.getvalue() + stderr.getvalue()
        )
        if success:
            return json.loads(stdout.getvalue())["result"]
        return json.loads(stderr.getvalue())["error"]

    def test_update_refuses_nested_profile_checkout_and_preserves_staged_edits(self):
        relative = "litai/docs/adoption.md"
        target = self.root / relative
        original = target.read_bytes()
        self.templates[relative] = original + b"\nNew upstream policy.\n"
        checkpoint = self.root / "litai/.literate/update-bases.json"
        recorded = checkpoint.read_bytes()
        child = self.root / "litai"
        self.assertEqual(self.update()["mode"], "read-only-plan")
        commit_independent_repository(child)
        staged = git_at(
            child,
            "hash-object",
            "-w",
            "--stdin",
            content=original + b"\nChild staged policy.\n",
        )
        git_at(
            child,
            "update-index",
            "--cacheinfo",
            "100644",
            staged.decode().strip(),
            "docs/adoption.md",
        )
        index = git_at(child, "ls-files", "--stage")
        status = git_at(child, "status", "--porcelain")
        for args in ((), ("--apply",)):
            error = self.update(*args, success=False)
            self.assertEqual(error["code"], "project.native_update_nested_git")
        self.assertEqual(git_at(child, "ls-files", "--stage"), index)
        self.assertEqual(git_at(child, "status", "--porcelain"), status)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(checkpoint.read_bytes(), recorded)
        self.assertFalse((child / ".litai-locks").exists())
        self.fixture.assert_original()

    def test_unrelated_nested_checkout_does_not_block_selected_template_update(self):
        child = self.root / "litai/unrelated"
        child.mkdir()
        (child / "notes.txt").write_bytes(b"Independent repository notes.\n")
        commit_independent_repository(child)
        relative = "litai/SKILL.md"
        self.templates[relative] += b"\nNew upstream guidance.\n"
        index = git_at(child, "ls-files", "--stage")
        self.assertEqual(self.update()["mode"], "read-only-plan")
        result = self.update("--apply")
        self.assertEqual(result["application"]["applied"], [relative])
        self.assertEqual((self.root / relative).read_bytes(), self.templates[relative])
        self.assertEqual(git_at(child, "ls-files", "--stage"), index)
        self.assertEqual(git_at(child, "status", "--porcelain"), b"")

    def test_update_refuses_nested_checkpoint_even_without_template_changes(self):
        child = self.root / "litai/.literate"
        commit_independent_repository(child)
        for args in ((), ("--apply",)):
            error = self.update(*args, success=False)
            self.assertEqual(error["code"], "project.native_update_nested_git")
        self.assertEqual(git_at(child, "status", "--porcelain"), b"")

    def test_new_checkpoint_boundary_rolls_back_only_earlier_owned_writes(self):
        from literate_ai.adapters.update_merge import UpdateBases

        relative = "litai/SKILL.md"
        target = self.root / relative
        previous = target.read_bytes()
        self.templates[relative] = previous + b"\nNew upstream guidance.\n"
        child = self.root / "litai/.literate"
        checkpoint = child / "update-bases.json"
        original = checkpoint.read_bytes()
        advance = UpdateBases.advance
        injected = False

        def create_boundary(bases, scope, path, content):
            nonlocal injected
            advance(bases, scope, path, content)
            if path == relative and not injected:
                self.assertEqual(target.read_bytes(), self.templates[relative])
                commit_independent_repository(child)
                injected = True

        with patch.object(UpdateBases, "advance", create_boundary):
            error = self.update("--apply", success=False)
        self.assertTrue(injected)
        self.assertEqual(error["code"], "project.native_update_nested_git")
        self.assertEqual(target.read_bytes(), previous)
        self.assertEqual(checkpoint.read_bytes(), original)
        self.assertEqual(git_at(child, "status", "--porcelain"), b"")

    def test_interrupted_checkpoint_replace_rolls_back_template_and_metadata(self):
        from literate_ai.adapters import project_update_apply

        relative = "litai/SKILL.md"
        target = self.root / relative
        before = target.read_bytes()
        self.templates[relative] += b"\nNew upstream guidance.\n"
        checkpoint = self.root / "litai/.literate/update-bases.json"
        original = checkpoint.read_bytes()
        actual = project_update_apply._write_exact
        interrupted = False

        def write(path, content):
            nonlocal interrupted
            actual(path, content)
            if path == checkpoint and not interrupted:
                self.assertNotEqual(checkpoint.read_bytes(), original)
                interrupted = True
                raise OSError("interrupted after checkpoint replacement")

        with patch.object(project_update_apply, "_write_exact", write):
            self.update("--apply", success=False)
        self.assertTrue(interrupted)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(checkpoint.read_bytes(), original)

    def test_late_lifecycle_boundary_keeps_child_owner_diagnostic(self):
        from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock_path
        from literate_ai.adapters.update_merge import UpdateBases

        relative = "litai/SKILL.md"
        target = self.root / relative
        before = target.read_bytes()
        self.templates[relative] += b"\nNew upstream guidance.\n"
        checkpoint = self.root / "litai/.literate/update-bases.json"
        original = checkpoint.read_bytes()
        lifecycle = project_lifecycle_lock_path(self.root)
        owner = lifecycle.with_name(lifecycle.name + ".owner.json")
        child = self.root / "litai/.litai-locks"
        advance = UpdateBases.advance
        committed = None

        def create_boundary(bases, scope, path, content):
            nonlocal committed
            advance(bases, scope, path, content)
            if path == relative and committed is None:
                commit_independent_repository(child)
                committed = git_at(
                    child, "show", "HEAD:" + owner.relative_to(child).as_posix()
                )

        with patch.object(UpdateBases, "advance", create_boundary):
            error = self.update("--apply", success=False)
        self.assertEqual(error["code"], "project.native_update_nested_git")
        self.assertIsNotNone(committed)
        self.assertEqual(owner.read_bytes(), committed)
        self.assertEqual(git_at(child, "status", "--porcelain"), b"")
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(checkpoint.read_bytes(), original)

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
