"""Committed removal preserves native changes and recovers interrupted deletions."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.support.native_repository import (
    NativeRepositoryFixture,
    commit_independent_repository,
    git_at,
)


class NativeProjectRemovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed = NativeRepositoryFixture()
        cls.seed.setUp()
        cls.addClassCleanup(cls.seed.doCleanups)
        plan = cls.seed.cli("onboard", "adopt", cls.seed.root)["result"]
        cls.seed.cli(
            "onboard",
            "adopt",
            cls.seed.root,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
        )
        cls.seed.git("add", "litai")
        cls.seed.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "native adoption",
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.fixture = NativeRepositoryFixture()
        self.root = Path(temporary.name).resolve() / "native"
        shutil.copytree(self.seed.root, self.root)
        self.fixture.root = self.root
        self.fixture.original = self.seed.original
        self.git = self.fixture.git
        self.cli = self.fixture.cli

    def plan(self, *args):
        return self.cli("onboard", "remove", self.root, *args)["result"]

    def apply(self, plan, *args, success=True):
        return self.cli(
            "onboard",
            "remove",
            self.root,
            *args,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
            success=success,
        )

    def recovery(self, plan):
        return tuple(plan["recovery_argv"][4:])

    def test_nested_git_repository_blocks_existing_plan_and_recovery(self):
        plan = self.plan()
        child = self.root / "litai"
        commit_independent_repository(child)
        manifest = child / "literate.project.json"
        original = manifest.read_bytes()
        oid = git_at(child, "hash-object", "-w", "--stdin", content=original + b"\n")
        git_at(
            child,
            "update-index",
            "--cacheinfo",
            "100644",
            oid.decode().strip(),
            manifest.name,
        )
        indexed = git_at(child, "ls-files", "--stage")
        status = git_at(child, "status", "--porcelain")
        parent_index = self.git("ls-files", "--stage")
        self.assertIn(b"MM ", status)
        for response in (
            self.apply(plan, success=False),
            self.cli("onboard", "remove", self.root, success=False),
            self.cli(
                "onboard", "remove", self.root, *self.recovery(plan), success=False
            ),
        ):
            self.assertEqual(
                response["error"]["code"], "native_removal.nested_git_boundary"
            )
        self.assertEqual(self.git("ls-files", "--stage"), parent_index)
        self.assertEqual(git_at(child, "ls-files", "--stage"), indexed)
        self.assertEqual(git_at(child, "status", "--porcelain"), status)
        self.assertEqual(manifest.read_bytes(), original)

    def test_nested_linked_worktree_blocks_missing_manifest_recovery(self):
        plan = self.plan()
        docs = self.root / "litai/docs"
        external = self.root.parent / "external"
        docs.rename(external)
        commit_independent_repository(external)
        git_at(external, "worktree", "add", "--detach", str(docs), "HEAD")
        self.assertTrue((docs / ".git").is_file())
        self.git("rm", "--", "litai/literate.project.json")
        linked = git_at(external, "worktree", "list", "--porcelain")
        index = self.git("ls-files", "--stage")
        response = self.cli(
            "onboard", "remove", self.root, *self.recovery(plan), success=False
        )
        self.assertEqual(
            response["error"]["code"], "native_removal.nested_git_boundary"
        )
        self.assertEqual(self.git("ls-files", "--stage"), index)
        self.assertEqual(git_at(external, "worktree", "list", "--porcelain"), linked)
        self.assertEqual(git_at(docs, "status", "--porcelain"), b"")
        self.assertTrue((docs / "adoption.md").is_file())
        self.assertTrue((self.root / "litai/SKILL.md").is_file())

    @unittest.skipUnless(os.name == "posix", "requires POSIX symlinks and FIFOs")
    def test_unsafe_nested_git_markers_are_refused_without_following(self):
        marker = self.root / "litai/docs/.git"
        for create in (lambda: marker.symlink_to("missing"), lambda: os.mkfifo(marker)):
            create()
            try:
                response = self.cli("onboard", "remove", self.root, success=False)
                self.assertEqual(
                    response["error"]["code"], "native_removal.nested_git_boundary"
                )
                self.assertTrue(os.path.lexists(marker))
            finally:
                marker.unlink()

    def test_outer_linked_worktree_and_unrelated_nested_checkout_are_preserved(self):
        self._outer_linked_worktree_removal()

    def test_crlf_linked_worktree_preserves_native_checkout_and_nested_child(self):
        self.git("config", "core.autocrlf", "true")
        self._outer_linked_worktree_removal()

    def test_crlf_attribute_race_cannot_launch_a_content_filter(self):
        from literate_ai.adapters import native_project_removal as removal

        self.git("config", "core.autocrlf", "true")
        self.git("config", "filter.removal-fixture.clean", "echo ran >filter-ran")
        manifest = self.root / "litai/literate.project.json"
        content = manifest.read_bytes().replace(b"\r\n", b"\n")
        manifest.write_bytes(content.replace(b"\n", b"\r\n"))
        original = removal._git
        injected = False

        def change_attributes(root, *args, **kwargs):
            nonlocal injected
            result = original(root, *args, **kwargs)
            if (
                args[0] == "check-attr"
                and kwargs.get("content") == b"litai/literate.project.json\0"
                and not injected
            ):
                (self.root / ".gitattributes").write_bytes(
                    b"litai/literate.project.json filter=removal-fixture\n"
                )
                injected = True
            return result

        with (
            patch.object(removal, "_git", side_effect=change_attributes),
            self.assertRaises(removal.NativeProjectRemovalError) as raised,
        ):
            removal.plan_native_project_removal(self.root)
        self.assertTrue(injected)
        self.assertFalse((self.root / "filter-ran").exists())
        self.assertEqual(raised.exception.code, "native_removal.transform_unsupported")

    def test_explicit_text_attributes_admit_exact_crlf_checkout_bytes(self):
        self.git("config", "core.autocrlf", "false")
        manifest = self.root / "litai/literate.project.json"
        content = manifest.read_bytes().replace(b"\r\n", b"\n")
        manifest.write_bytes(content.replace(b"\n", b"\r\n"))
        for attribute in (b"text", b"text=auto", b"eol=lf", b"eol=crlf"):
            with self.subTest(attribute=attribute):
                (self.root / ".gitattributes").write_bytes(
                    b"litai/literate.project.json " + attribute + b"\n"
                )
                plan = self.plan()
                self.assertIn("litai/literate.project.json", plan["selected"])
                self.assertEqual(manifest.read_bytes(), content.replace(b"\n", b"\r\n"))

    def test_raw_newline_change_after_plan_refuses_even_when_git_normalizes_it(self):
        self.git("config", "core.autocrlf", "true")
        plan = self.plan()
        index = self.git("ls-files", "--stage")
        manifest = self.root / "litai/literate.project.json"
        content = manifest.read_bytes().replace(b"\r\n", b"\n")
        # Always change the raw bytes, including on an initial Windows checkout.
        replacement = (
            content
            if b"\r\n" in manifest.read_bytes()
            else content.replace(b"\n", b"\r\n")
        )
        manifest.write_bytes(replacement)
        refused = self.apply(plan, success=False)
        self.assertEqual(refused["error"]["code"], "native_removal.plan_changed")
        self.assertEqual(manifest.read_bytes(), replacement)
        self.assertEqual(self.git("ls-files", "--stage"), index)

    def test_crlf_edit_to_unconverted_metadata_is_preserved(self):
        self.git("config", "core.autocrlf", "true")
        (self.root / ".gitattributes").write_bytes(
            b"litai/literate.project.json -text\n"
        )
        manifest = self.root / "litai/literate.project.json"
        content = manifest.read_bytes().replace(b"\r\n", b"\n")
        manifest.write_bytes(content.replace(b"\n", b"\r\n"))
        before = manifest.read_bytes()
        refused = self.cli("onboard", "remove", self.root, success=False)
        self.assertEqual(refused["error"]["code"], "native_removal.worktree_changed")
        self.assertEqual(manifest.read_bytes(), before)

    def test_crlf_conversion_never_invokes_configured_content_filter(self):
        self.git("config", "core.autocrlf", "true")
        self.git("config", "filter.removal-fixture.clean", "echo ran >filter-ran")
        (self.root / ".gitattributes").write_bytes(
            b"litai/literate.project.json filter=removal-fixture\n"
        )
        manifest = self.root / "litai/literate.project.json"
        content = manifest.read_bytes().replace(b"\r\n", b"\n")
        manifest.write_bytes(content.replace(b"\n", b"\r\n"))
        before = manifest.read_bytes()
        refused = self.cli("onboard", "remove", self.root, success=False)
        self.assertEqual(
            refused["error"]["code"], "native_removal.transform_unsupported"
        )
        self.assertFalse((self.root / "filter-ran").exists())
        self.assertEqual(manifest.read_bytes(), before)

    def _outer_linked_worktree_removal(self):
        outer = self.root
        linked = outer.parent / "linked"
        self.git("worktree", "add", "--detach", str(linked), "HEAD")
        self.root = self.fixture.root = linked
        self.assertTrue((linked / ".git").is_file())
        self.assertEqual(self.git("status", "--porcelain"), "")
        child = linked / "litai/unrelated"
        child.mkdir()
        notes = child / "notes.txt"
        notes.write_bytes(b"Independent repository notes.\n")
        commit_independent_repository(child)
        head = git_at(child, "rev-parse", "HEAD")
        plan = self.plan()
        self.assertEqual(self.apply(plan)["result"]["state"], "removed")
        self.assertEqual(git_at(child, "rev-parse", "HEAD"), head)
        self.assertEqual(git_at(child, "status", "--porcelain"), b"")
        self.assertEqual(notes.read_bytes(), b"Independent repository notes.\n")
        self.assertTrue((linked / ".git").is_file())

    def test_git_boundary_added_while_constructing_patch_refuses_publication(self):
        self._late_git_boundary(self.root / "litai/docs")

    def test_profile_git_boundary_added_during_patch_keeps_manifest_lock(self):
        from literate_ai.projects import ProjectConfigurationStore

        child = self.root / "litai"
        lock = ProjectConfigurationStore.lock_path(self.root)
        self._late_git_boundary(child)
        self.assertEqual(lock.read_bytes(), git_at(child, "show", "HEAD:" + lock.name))

    def _late_git_boundary(self, child):
        from literate_ai.adapters import native_project_removal as removal
        from literate_ai.cli.dispatch import main
        from literate_ai.projects import ProjectConfigurationStore

        plan = self.plan()
        lock = ProjectConfigurationStore.lock_path(self.root)
        locked_files = {lock: b"\0"} if lock.is_relative_to(child) else {}
        index = self.git("ls-files", "--stage")
        original = removal._git
        injected = False

        def git(root, *args, **kwargs):
            nonlocal injected
            result = original(root, *args, **kwargs)
            if args[0] == "diff" and not injected:
                commit_independent_repository(child, locked_files=locked_files)
                injected = True
            return result

        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(removal, "_git", side_effect=git),
            patch.dict(os.environ, {"LITAI_NO_SELF_UPDATE": "1"}),
        ):
            status = main(
                [
                    "--json",
                    "onboard",
                    "remove",
                    str(self.root),
                    "--apply",
                    "--acknowledge",
                    "--expect-plan",
                    plan["plan_identity"],
                ],
                stdout=stdout,
                stderr=stderr,
            )
        self.assertTrue(injected)
        self.assertEqual(status, 2)
        response = json.loads(stderr.getvalue())
        self.assertEqual(
            response["error"]["code"], "native_removal.nested_git_boundary"
        )
        self.assertEqual(self.git("ls-files", "--stage"), index)
        for path, content in locked_files.items():
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(
                path.read_bytes(),
                git_at(child, "show", "HEAD:" + path.relative_to(child).as_posix()),
            )
        self.assertEqual(git_at(child, "status", "--porcelain"), b"")
        for path in plan["selected"]:
            self.assertTrue((self.root / path).is_file(), path)

    def test_removal_preserves_custom_content_and_unrelated_staging(self):
        custom = self.root / "litai/docs/adoption.md"
        custom.write_bytes(custom.read_bytes() + b"\nRepository review policy.\n")
        self.git("add", "litai/docs/adoption.md")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "custom policy",
        )
        untracked = self.root / "litai/local-notes.txt"
        untracked.write_text("Keep my notes.\n")
        source = self.root / "src/native.py"
        source.write_text("def value():\n    return 6\n")
        self.git("add", "src/native.py")
        staged = self.git("ls-files", "--stage", "src/native.py")
        source.write_text("def value():\n    return 7\n")
        before = self.git("status", "--porcelain")
        plan = self.plan()
        self.assertEqual(before, self.git("status", "--porcelain"))
        self.assertEqual(plan["retained"]["litai/docs/adoption.md"], "customized")
        head = self.git("rev-parse", "HEAD")
        result = self.apply(plan)["result"]
        self.assertEqual(result["state"], "removed")
        self.assertFalse(result["committed"])
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertEqual(self.git("ls-files", "--stage", "src/native.py"), staged)
        self.assertIn("return 7", source.read_text())
        self.assertIn("Repository review policy", custom.read_text())
        self.assertEqual(untracked.read_text(), "Keep my notes.\n")
        for path in plan["selected"]:
            self.assertFalse((self.root / path).exists(), path)
        self.assertTrue((self.root / ".github/workflows/native.yml").is_file())

    def test_recovery_handles_partial_index_and_filesystem_states(self):
        plan = self.plan()
        paths = [
            path for path in plan["selected"] if path != "litai/literate.project.json"
        ]
        (self.root / paths[0]).unlink()  # Unlink happened before index publication.
        self.git("rm", "--cached", "--", paths[1])  # Index-only interrupted state.
        self.git("rm", "--", paths[2])  # Already complete.
        arguments = self.recovery(plan)
        refused = self.cli("onboard", "remove", self.root, *arguments, success=False)
        self.assertEqual(
            refused["error"]["code"], "native_removal.index_disposition_required"
        )
        self.assertTrue((self.root / paths[1]).exists())
        # Explicit native disposition belongs to the operator. Removal cannot
        # restore an entry over a concurrent writer's newly staged content.
        self.git(
            "restore", "--source=" + plan["source_commit"], "--staged", "--", paths[1]
        )
        fresh = self.plan(*arguments)
        result = self.apply(fresh, *arguments)["result"]
        self.assertEqual(result["state"], "removed")
        self.assertEqual(self.git("ls-files", "--", "litai"), "")
        self.assertFalse((self.root / "litai/literate.project.json").exists())
        replay = self.plan(*arguments)
        repeated = self.apply(replay, *arguments)["result"]
        self.assertEqual(repeated["state"], "removed")
        self.assertEqual(
            len(repeated["already_absent_at_start"]), len(plan["selected"])
        )
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "reviewed removal",
        )
        after_commit = self.plan(*arguments)
        self.assertEqual(
            self.apply(after_commit, *arguments)["result"]["staged_deletions"], []
        )

    def test_process_exit_after_supporting_deletions_recovers_with_manifest_last(self):
        self._interrupted_removal(after_group=1)

    def test_new_staging_during_missing_file_recovery_is_never_overwritten(self):
        from literate_ai.adapters import native_project_removal as removal
        from literate_ai.cli.dispatch import main

        plan = self.plan()
        relative = "litai/SKILL.md"
        target = self.root / relative
        original = target.read_text()
        customized = original.replace(
            "# Native repository delivery", "# Native  repository delivery"
        )
        self.assertNotEqual(customized, original)
        self.git("config", "apply.ignoreWhitespace", "change")
        target.unlink()
        arguments = self.recovery(plan)
        fresh = self.plan(*arguments)
        run = removal.run_bounded_process
        raced = False

        def concurrent_writer(command, **kwargs):
            nonlocal raced
            if "apply" in command and "--cached" in command and not raced:
                raced = True
                target.write_text(customized)
                self.git("add", "--", relative)
                target.unlink()
            return run(command, **kwargs)

        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(removal, "run_bounded_process", side_effect=concurrent_writer),
            patch.dict(os.environ, {"LITAI_NO_SELF_UPDATE": "1"}),
        ):
            status = main(
                [
                    "--json",
                    "onboard",
                    "remove",
                    str(self.root),
                    *arguments,
                    "--apply",
                    "--acknowledge",
                    "--expect-plan",
                    fresh["plan_identity"],
                ],
                stdout=stdout,
                stderr=stderr,
            )
        self.assertTrue(raced)
        self.assertNotEqual(status, 0, stdout.getvalue() + stderr.getvalue())
        self.assertEqual(self.git("show", ":" + relative), customized.strip())
        self.assertTrue((self.root / "litai/literate.project.json").exists())

    def test_git_diff_preferences_cannot_retarget_an_application_file(self):
        skill = self.root / "litai/SKILL.md"
        application_skill = self.root / "SKILL.md"
        application_skill.write_bytes(skill.read_bytes())
        self.git("add", "SKILL.md")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "application-owned instructions",
        )
        for key, value in (
            ("diff.noprefix", "true"),
            ("diff.mnemonicPrefix", "true"),
            ("diff.relative", "true"),
            ("color.diff", "always"),
            ("diff.srcPrefix", "wrong/"),
            ("diff.dstPrefix", "wrong/"),
            ("apply.whitespace", "fix"),
        ):
            self.git("config", key, value)
        before = application_skill.read_bytes()
        index = self.git("ls-files", "--stage", "SKILL.md")
        arguments = (
            "--source",
            self.git("rev-parse", "HEAD"),
            "--only",
            "litai/SKILL.md",
            "--only",
            "litai/literate.project.json",
        )
        plan = self.plan(*arguments)
        self.assertEqual(self.apply(plan, *arguments)["result"]["state"], "removed")
        self.assertEqual(application_skill.read_bytes(), before)
        self.assertEqual(self.git("ls-files", "--stage", "SKILL.md"), index)
        self.assertFalse(skill.exists())

    def test_process_exit_after_manifest_deletion_recovers_without_discovery(self):
        self._interrupted_removal(after_group=2)

    def _interrupted_removal(self, *, after_group):
        plan = self.plan()
        script = """
import os,sys
from pathlib import Path
from literate_ai.adapters import native_project_removal as removal
root=Path(sys.argv[1]); stop=int(sys.argv[2]); calls=0
original=removal._remove_group
def interrupted(*args, **kwargs):
    global calls
    original(*args, **kwargs); calls += 1
    if calls == stop: os._exit(86)
removal._remove_group=interrupted
plan=removal.plan_native_project_removal(root)
removal.apply_native_project_removal(root,expected=plan['plan_identity'],acknowledge=True)
"""
        result = subprocess.run(
            [sys.executable, "-c", script, str(self.root), str(after_group)],
            env={**os.environ, "LITAI_NO_SELF_UPDATE": "1"},
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 86, result.stderr)
        self.assertEqual(
            (self.root / "litai/literate.project.json").exists(), after_group == 1
        )
        self.assertFalse((self.root / "litai/SKILL.md").exists())
        arguments = self.recovery(plan)
        fresh = self.plan(*arguments)
        self.assertEqual(self.apply(fresh, *arguments)["result"]["state"], "removed")
        self.assertEqual(self.git("ls-files", "--", "litai"), "")

    def test_unknown_git_lock_and_new_custom_recovery_content_are_preserved(self):
        plan = self.plan()
        lock = self.root / ".git/index.lock"
        lock.write_bytes(b"another Git operation")
        refused = self.apply(plan, success=False)
        self.assertEqual(refused["error"]["code"], "native_removal.git_lock_present")
        self.assertEqual(lock.read_bytes(), b"another Git operation")
        lock.unlink()  # The fixture owns this injected lock, not removal.
        custom = self.root / "litai/SKILL.md"
        custom.write_text("New policy after the reviewed plan.\n")
        self.apply(plan, success=False)
        refused = self.cli(
            "onboard", "remove", self.root, *self.recovery(plan), success=False
        )
        self.assertEqual(refused["error"]["code"], "native_removal.worktree_changed")
        self.assertEqual(custom.read_text(), "New policy after the reviewed plan.\n")
        self.assertTrue((self.root / "litai/literate.project.json").exists())

    def test_selected_staging_and_index_flags_are_never_silently_discarded(self):
        custom = self.root / "litai/SKILL.md"
        original = custom.read_bytes()
        custom.write_bytes(original + b"\nStaged custom policy.\n")
        self.git("add", "litai/SKILL.md")
        before = self.git("ls-files", "--stage", "litai/SKILL.md")
        refused = self.cli("onboard", "remove", self.root, success=False)
        self.assertEqual(refused["error"]["code"], "native_removal.index_changed")
        self.assertEqual(self.git("ls-files", "--stage", "litai/SKILL.md"), before)
        self.git("restore", "--staged", "--", "litai/SKILL.md")
        custom.write_bytes(original)
        self.git("update-index", "--assume-unchanged", "litai/SKILL.md")
        refused = self.cli("onboard", "remove", self.root, success=False)
        self.assertEqual(
            refused["error"]["code"], "native_removal.index_flags_unsupported"
        )
        self.assertTrue((self.root / "litai/literate.project.json").exists())
        self.git("update-index", "--no-assume-unchanged", "litai/SKILL.md")
        self.git("config", "core.sparseCheckout", "true")
        refused = self.cli("onboard", "remove", self.root, success=False)
        self.assertEqual(refused["error"]["code"], "native_removal.sparse_unsupported")

    def test_replaced_directory_with_same_member_inodes_invalidates_the_plan(self):
        plan = self.plan()
        directory = self.root / "litai/.literate"
        previous = self.root / "litai/previous-metadata"
        directory.rename(previous)
        directory.mkdir()
        for path in previous.iterdir():
            path.rename(directory / path.name)
        refused = self.apply(plan, success=False)
        self.assertEqual(refused["error"]["code"], "native_removal.plan_changed")
        self.assertTrue((self.root / "litai/literate.project.json").exists())
        self.assertEqual(self.git("diff", "--name-only", "HEAD"), "")

    def test_changed_authority_metadata_requires_disposition_before_any_deletion(self):
        authority = self.root / "litai/.literate/conversion-authority.json"
        authority.write_bytes(authority.read_bytes() + b"\n")
        before = authority.read_bytes()
        refused = self.cli("onboard", "remove", self.root, success=False)
        self.assertEqual(refused["error"]["code"], "native_removal.worktree_changed")
        self.git("add", "litai/.literate/conversion-authority.json")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "changed authority",
        )
        refused = self.cli("onboard", "remove", self.root, success=False)
        self.assertEqual(
            refused["error"]["code"], "native_removal.authority_customized"
        )
        self.assertEqual(authority.read_bytes(), before)
        self.assertTrue((self.root / "litai/literate.project.json").exists())
        self.assertEqual(self.git("diff", "--name-only", "HEAD"), "")

    def test_inconsistent_or_malformed_committed_ownership_is_preserved(self):
        baseline_path = self.root / "litai/.literate/initialization-baseline.json"
        original = baseline_path.read_bytes()
        baseline = json.loads(original)
        incomplete = {**baseline, "files": baseline["files"][:-1]}
        wrong_origin = {
            **baseline,
            "origin_identity": {**baseline["origin_identity"], "digest": "0" * 64},
        }
        for value in (incomplete, wrong_origin, []):
            with self.subTest(value_type=type(value).__name__):
                baseline_path.write_text(json.dumps(value))
                self.git("add", "litai/.literate/initialization-baseline.json")
                self.git(
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.test",
                    "commit",
                    "-qm",
                    "invalid ownership",
                )
                before = baseline_path.read_bytes()
                refused = self.cli("onboard", "remove", self.root, success=False)
                self.assertIn(
                    refused["error"]["code"],
                    {
                        "native_removal.profile_unsupported",
                        "native_removal.authority_invalid",
                    },
                )
                self.assertEqual(baseline_path.read_bytes(), before)
                self.assertTrue((self.root / "litai/literate.project.json").exists())
                self.assertEqual(self.git("diff", "--name-only", "HEAD"), "")

    @unittest.skipUnless(os.name == "posix", "uses actual POSIX directory permissions")
    def test_native_permission_failure_keeps_manifest_and_reports_recovery(self):
        if os.geteuid() == 0:
            self.skipTest("privileged user can bypass the permission fault")
        directory = self.root / "litai/docs"
        directory.chmod(0o555)
        self.addCleanup(lambda: directory.chmod(0o755) if directory.exists() else None)
        plan = self.plan()
        refused = self.apply(plan, success=False)
        message = refused["error"]["message"]
        self.assertIn("Removal may be partial", message)
        self.assertIn("supporting-files", message)
        self.assertIn(plan["source_commit"], message)
        self.assertIn("litai/literate.project.json", message)
        self.assertTrue((self.root / "litai/literate.project.json").exists())
        directory.chmod(0o755)
        arguments = self.recovery(plan)
        present_without_index = [
            path
            for path in plan["selected"]
            if (self.root / path).is_file() and not self.git("ls-files", "--", path)
        ]
        if present_without_index:
            refused = self.cli(
                "onboard", "remove", self.root, *arguments, success=False
            )
            self.assertEqual(
                refused["error"]["code"], "native_removal.index_disposition_required"
            )
            # The fixture owns these exact before-images. This explicit native
            # staging decision is deliberately outside the removal command.
            self.git(
                "restore",
                "--source=" + plan["source_commit"],
                "--staged",
                "--",
                *present_without_index,
            )
        repaired = self.plan(*arguments)
        self.assertEqual(self.apply(repaired, *arguments)["result"]["state"], "removed")
