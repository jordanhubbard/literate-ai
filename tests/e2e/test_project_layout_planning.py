"""Public containment observations preserve source and refuse unsafe inputs."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.cli import main
from tests.support.fixtures_test_repository_initialization_e2e import initialize_root
from tests.support.native_repository import NativeRepositoryFixture


def snapshot(root: Path):
    result = {}
    for path in root.rglob("*"):
        value = path.lstat()
        result[path.relative_to(root).as_posix()] = (
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest()
            if stat.S_ISREG(value.st_mode)
            else None,
        )
    return result


class ProjectLayoutPlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.template = Path(temporary.name).resolve() / "template"
        initialize_root(cls.template)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "project"
        shutil.copytree(self.template, self.root)

    def invoke(self, *extra, project=None):
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch(
                "literate_ai.cli.dispatch.maybe_host_self_update",
                side_effect=AssertionError("self update"),
            ),
            patch(
                "literate_ai.cli.dispatch.ensure_user_mcp_catalog",
                side_effect=AssertionError("host configuration"),
            ),
            patch(
                "literate_ai.cli.dispatch._run_operator_mcp_discovery",
                side_effect=AssertionError("MCP discovery"),
            ),
            patch(
                "literate_ai.cli.dispatch.PerformanceRecorder.span",
                side_effect=AssertionError("performance write"),
            ),
        ):
            code = main(
                [
                    "--json",
                    *extra,
                    "project",
                    "layout",
                    "plan",
                    "--project",
                    str(project or self.root),
                ],
                stdout=output,
                stderr=errors,
            )
        return (
            code,
            json.loads(output.getvalue() or errors.getvalue()),
            errors.getvalue(),
        )

    def test_public_plan_is_blocked_useful_repeatable_and_has_no_host_writers(self):
        nested = self.root / "nested"
        nested.mkdir()
        (self.root / "AGENTS.md").write_text("Custom operator rules: preserve these.\n")
        before = snapshot(self.root)
        code, packet, errors = self.invoke()
        self.assertEqual(code, 1, errors)
        result = packet["result"]
        self.assertEqual(result["schema"], "literate-ai/project-layout-plan@1")
        self.assertFalse(result["apply_supported"])
        self.assertFalse(result["writes"])
        self.assertFalse(result["qualification"])
        self.assertTrue(result["blockers"])
        members = {item["path"]: item for item in result["members"]}
        self.assertEqual(members["AGENTS.md"]["role"], "shared integration")
        self.assertIsNone(members["AGENTS.md"]["target"])
        self.assertEqual(
            members["literate.project.json"]["target"], "litai/literate.project.json"
        )
        component_edit = next(
            edit
            for edit in result["reference_edits"]
            if edit["field"] == "component_roots"
        )
        self.assertIsNone(component_edit["to"])
        other_code, other, _ = self.invoke(project=nested)
        self.assertEqual(other_code, code)
        self.assertEqual(other["result"], result)
        self.assertEqual(snapshot(self.root), before)

    def test_custom_source_changes_identity_without_gaining_move_authority(self):
        source = self.root / "application.py"
        source.write_text("print('native')\n")
        first = self.invoke()[1]["result"]
        source.write_text("print('changed native')\n")
        before = snapshot(self.root)
        second = self.invoke()[1]["result"]
        self.assertNotEqual(first["plan_identity"], second["plan_identity"])
        member = next(item for item in second["members"] if item["path"] == source.name)
        self.assertEqual(member["role"], "unresolved")
        self.assertIsNone(member["target"])
        self.assertEqual(snapshot(self.root), before)

    def test_malformed_provenance_and_occupied_target_refuse_without_changes(self):
        path = self.root / ".literate/imports.json"
        old = path.read_bytes() if path.exists() else None
        path.write_text('{"schema":"wrong", "imports":[]}')
        before = snapshot(self.root)
        code, packet, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(packet["error"]["code"], "project.layout.provenance_invalid")
        self.assertEqual(snapshot(self.root), before)
        if old is None:
            path.unlink()
        else:
            path.write_bytes(old)
        (self.root / "litai").mkdir()
        (self.root / "litai/host-owned").write_bytes(b"preserve")
        before = snapshot(self.root)
        code, packet, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(packet["error"]["code"], "project.layout.target_occupied")
        self.assertEqual(snapshot(self.root), before)

    @unittest.skipUnless(hasattr(os, "symlink"), "requires native symbolic links")
    def test_linked_application_member_refuses_instead_of_following_it(self):
        outside = self.base / "outside"
        outside.write_bytes(b"outside application boundary")
        (self.root / "linked").symlink_to(outside)
        code, packet, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(packet["error"]["code"], "project.layout.path_unsafe")
        self.assertTrue((self.root / "linked").is_symlink())
        self.assertEqual(outside.read_bytes(), b"outside application boundary")

    def test_read_only_side_effect_options_refuse_before_any_writer(self):
        before = snapshot(self.root)
        for options in [
            ("--discover-mcps",),
            ("--debug", str(self.base / "debug.json")),
        ]:
            with self.subTest(options=options):
                code, packet, _ = self.invoke(*options)
                self.assertEqual(code, 2)
                self.assertEqual(
                    packet["error"]["code"], "project.layout.read_only_options"
                )
                self.assertEqual(snapshot(self.root), before)
                self.assertFalse((self.base / "debug.json").exists())

    def test_empty_directory_and_evidence_requirements_are_bound(self):
        first = self.invoke()[1]["result"]
        (self.root / "empty-authority").mkdir()
        evidence = self.root / "components/example/component.lock.json"
        evidence.parent.mkdir(parents=True)
        evidence.write_text('{"historical":"producer fixture"}\n')
        before = snapshot(self.root)
        second = self.invoke()[1]["result"]
        self.assertNotEqual(first["plan_identity"], second["plan_identity"])
        self.assertIn("empty-authority", {item["path"] for item in second["topology"]})
        member = next(
            item
            for item in second["members"]
            if item["path"].endswith("/component.lock.json")
        )
        self.assertEqual(member["role"], "producer evidence")
        self.assertIsNone(member["target"])
        self.assertEqual(member["renewal"], "Component resolution")
        self.assertEqual(snapshot(self.root), before)

    def test_changed_input_during_public_observation_refuses(self):
        from literate_ai.adapters import project_layout_planning as planning

        original = planning._capture
        calls = 0

        def change_after_capture(root):
            nonlocal calls
            result = original(root)
            calls += 1
            if calls == 1:
                (self.root / "AGENTS.md").write_text("changed concurrently\n")
            return result

        with patch.object(planning, "_capture", side_effect=change_after_capture):
            code, packet, _ = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(packet["error"]["code"], "project.layout.capture_changed")
        self.assertEqual(
            (self.root / "AGENTS.md").read_text(), "changed concurrently\n"
        )

    def test_import_and_catalog_base_provenance_remain_independent(self):
        from literate_ai.adapters.update_merge import UpdateBases
        from literate_ai.contracts.catalog_imports import (
            CatalogImport,
            CatalogImportFile,
            CatalogImportsFile,
            CatalogImportSource,
        )

        relative = "skills/agent/SKILL.md"
        content = (self.root / relative).read_bytes()
        identity = "sha256:" + hashlib.sha256(content).hexdigest()
        imported = CatalogImport(
            "skill",
            "agent",
            CatalogImportSource(
                "parent",
                "sha256:" + "a" * 64,
                "git:https://example.test/parent.git@" + "b" * 40,
                (),
            ),
            (CatalogImportFile(relative, identity),),
            "2026-01-01T00:00:00Z",
        )
        CatalogImportsFile(imports=(imported,)).save(self.root)
        bases = UpdateBases(self.root)
        bases.advance("catalog", relative, content)
        bases.write()
        first = self.invoke()[1]["result"]
        member = next(item for item in first["members"] if item["path"] == relative)
        self.assertEqual(member["provenance"]["catalog_base"], identity)
        self.assertEqual(member["provenance"]["imports"][0]["identity"], identity)
        (self.root / CatalogImportsFile.PATH).unlink()
        before = snapshot(self.root)
        second = self.invoke()[1]["result"]
        member = next(item for item in second["members"] if item["path"] == relative)
        self.assertEqual(member["provenance"]["catalog_base"], identity)
        self.assertEqual(member["provenance"]["imports"], [])
        self.assertNotEqual(first["plan_identity"], second["plan_identity"])
        self.assertEqual(snapshot(self.root), before)

    def test_project_inside_enclosing_git_worktree_binds_its_staged_index(self):
        def git(*arguments):
            return subprocess.run(
                ["git", "-C", str(self.base), *arguments],
                capture_output=True,
                check=True,
                timeout=15,
            ).stdout

        git("init", "-q")
        git("add", "project/literate.project.json")
        git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "project authority",
        )
        first = self.invoke()[1]["result"]
        path = self.root / "literate.project.json"
        content = path.read_bytes()
        path.write_bytes(content + b"\n")
        git("add", "project/literate.project.json")
        path.write_bytes(content)
        staged = git("ls-files", "--stage")
        second = self.invoke()[1]["result"]
        self.assertIsNotNone(first["git_state"])
        self.assertNotEqual(first["git_state"]["index"], second["git_state"]["index"])
        self.assertNotEqual(first["plan_identity"], second["plan_identity"])
        self.assertEqual(first["members"], second["members"])
        self.assertEqual(git("ls-files", "--stage"), staged)
        self.assertEqual(path.read_bytes(), content)

    @unittest.skipIf(os.name == "nt", "requires POSIX directory permission modes")
    def test_root_directory_mode_changes_plan_identity(self):
        first = self.invoke()[1]["result"]
        old = stat.S_IMODE(self.root.stat().st_mode)
        try:
            self.root.chmod(old ^ stat.S_IXGRP)
            second = self.invoke()[1]["result"]
            self.assertNotEqual(first["plan_identity"], second["plan_identity"])
            root = next(item for item in second["topology"] if item["path"] == ".")
            self.assertEqual(root["mode"], old ^ stat.S_IXGRP)
        finally:
            self.root.chmod(old)


class ContainedNativeLayoutTests(NativeRepositoryFixture):
    @classmethod
    def setUpClass(cls):
        fixture = NativeRepositoryFixture()
        fixture.setUp()
        cls.addClassCleanup(fixture.doCleanups)
        plan = fixture.cli("onboard", "adopt", fixture.root)["result"]
        fixture.cli(
            "onboard",
            "adopt",
            fixture.root,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
        )
        cls.template = fixture.root
        cls.original_files = fixture.original

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "native"
        shutil.copytree(self.template, self.root)
        self.original = self.original_files.copy()

    def test_native_scope_excludes_unrelated_large_outputs(self):
        output = self.root / "native-output.bin"
        with output.open("wb") as stream:
            stream.truncate(20 * 1024 * 1024)
        before = snapshot(self.root / "litai")
        indexed = self.git("ls-files", "--stage")
        result = self.cli("project", "layout", "plan", "--project", self.root)["result"]
        self.assertTrue(result["planning_complete"])
        self.assertFalse(result["qualification"])
        self.assertEqual(result["reference_edits"], [])
        self.assertTrue(
            all(member["path"].startswith("litai/") for member in result["members"])
        )
        self.assertEqual(snapshot(self.root / "litai"), before)
        self.assertEqual(self.git("ls-files", "--stage"), indexed)
        self.assertEqual(output.stat().st_size, 20 * 1024 * 1024)
        self.assert_original()

    def test_index_changes_cannot_reuse_an_identical_worktree_plan(self):
        first = self.cli("project", "layout", "plan", "--project", self.root)["result"]
        path = self.root / "README.md"
        content = path.read_bytes()
        path.write_bytes(content + b"staged application edit\n")
        self.git("add", "README.md")
        path.write_bytes(content)
        indexed = self.git("ls-files", "--stage")
        second = self.cli("project", "layout", "plan", "--project", self.root)["result"]
        self.assertNotEqual(first["plan_identity"], second["plan_identity"])
        self.assertNotEqual(first["git_state"]["index"], second["git_state"]["index"])
        self.assertEqual(first["members"], second["members"])
        self.assertEqual(self.git("ls-files", "--stage"), indexed)
        self.assertEqual(path.read_bytes(), content)

    def test_nested_framework_git_index_is_bound_and_rechecked(self):
        from literate_ai.adapters import project_layout_planning as planning

        framework = self.root / "litai"

        def git(*arguments, input_bytes=None):
            return subprocess.run(
                ["git", "-C", str(framework), *arguments],
                input=input_bytes,
                capture_output=True,
                check=True,
                timeout=15,
            ).stdout

        git("init", "-q")
        git("add", ".")
        git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "framework authority",
        )
        parent_index = self.git("ls-files", "--stage")
        manifest = framework / "literate.project.json"
        content = manifest.read_bytes()
        mode = git("ls-files", "--stage", "--", manifest.name).split()[0].decode()
        observed_paths = (framework, manifest)

        def topology():
            return tuple(
                (value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
                for value in (path.stat() for path in observed_paths)
            )

        before = topology()
        first = self.cli("project", "layout", "plan", "--project", self.root)["result"]

        def stage_only(suffix):
            oid = git("hash-object", "-w", "--stdin", input_bytes=content + suffix)
            git(
                "update-index", "--cacheinfo", mode, oid.decode().strip(), manifest.name
            )
            self.assertEqual(topology(), before)
            self.assertEqual(manifest.read_bytes(), content)

        stage_only(b"\n")
        child_index = git("ls-files", "--stage")
        second = self.cli("project", "layout", "plan", "--project", self.root)["result"]
        self.assertEqual(first["git_state"], second["git_state"])
        self.assertEqual(first["members"], second["members"])
        self.assertNotEqual(
            first["framework_git_state"]["index"],
            second["framework_git_state"]["index"],
        )
        self.assertNotEqual(first["plan_identity"], second["plan_identity"])
        self.assertEqual(git("ls-files", "--stage"), child_index)

        original = planning._capture
        injected = False

        def change_index_during_capture(root):
            nonlocal injected
            captured = original(root)
            if not injected:
                stage_only(b"\n\n")
                injected = True
            return captured

        output, errors = io.StringIO(), io.StringIO()
        with patch.object(
            planning, "_capture", side_effect=change_index_during_capture
        ):
            code = main(
                ["--json", "project", "layout", "plan", "--project", str(self.root)],
                stdout=output,
                stderr=errors,
            )
        self.assertEqual(code, 2)
        self.assertEqual(
            json.loads(errors.getvalue())["error"]["code"],
            "project.layout.capture_changed",
        )
        self.assertNotEqual(git("ls-files", "--stage"), child_index)
        self.assertEqual(self.git("ls-files", "--stage"), parent_index)
        self.assertEqual(topology(), before)
        self.assertEqual(manifest.read_bytes(), content)

    def test_competing_root_authority_during_native_observation_refuses(self):
        from literate_ai.adapters import project_layout_planning as planning

        indexed = self.git("ls-files", "--stage")
        content = (self.root / "litai/literate.project.json").read_bytes()
        original = planning._capture
        injected = False

        def inject_root_manifest(root):
            nonlocal injected
            result = original(root)
            if not injected:
                (self.root / "literate.project.json").write_bytes(content)
                injected = True
            return result

        output, errors = io.StringIO(), io.StringIO()
        with patch.object(planning, "_capture", side_effect=inject_root_manifest):
            code = main(
                ["--json", "project", "layout", "plan", "--project", str(self.root)],
                stdout=output,
                stderr=errors,
            )
        self.assertEqual(code, 2)
        packet = json.loads(errors.getvalue())
        self.assertEqual(packet["error"]["code"], "project.manifest_ambiguous")
        self.assertEqual((self.root / "literate.project.json").read_bytes(), content)
        self.assertEqual(self.git("ls-files", "--stage"), indexed)
