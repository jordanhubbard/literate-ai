"""Public native adoption preserves source, native checks and forge discovery."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from tests.support.native_repository import NativeRepositoryFixture


class NativeProjectBootstrapTests(NativeRepositoryFixture):
    def test_retained_placement_options_require_explicit_conversion(self):
        plan = self.cli("onboard", "adopt", self.root)["result"]
        indexed = self.git("ls-files", "--stage")
        for option, value in (
            ("--implementation-directory", "scheduler"),
            ("--implementation-directory", ""),
            ("--wrapper-component", "components/scheduler-wrapper"),
            ("--wrapper-component", ""),
        ):
            for apply in (
                (),
                ("--apply", "--acknowledge", "--expect-plan", plan["plan_identity"]),
            ):
                with self.subTest(option=option, value=value, apply=bool(apply)):
                    result = self.cli(
                        "onboard",
                        "adopt",
                        self.root,
                        option,
                        value,
                        *apply,
                        success=False,
                    )
                    self.assertEqual(
                        result["error"]["code"], "operator.native_profile_options"
                    )
        self.assertEqual(self.git("ls-files", "--stage"), indexed)
        self.assertFalse((self.root / "litai").exists())
        self.assert_original()

    def test_redirected_root_refuses_plan_and_apply_without_publication(self):
        plan = self.cli("onboard", "adopt", self.root)["result"]
        alias = self.root.parent / "redirected"
        parent_alias = self.root.parent / "redirected-parent"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
            parent_alias.symlink_to(self.root.parent, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"directory symlinks unavailable: {exc}")
        indexed = self.git("ls-files", "--stage")
        for redirected in (alias, parent_alias / self.root.name):
            for options in (
                (),
                ("--apply", "--acknowledge", "--expect-plan", plan["plan_identity"]),
            ):
                with self.subTest(path=redirected.name, apply=bool(options)):
                    refused = self.cli(
                        "onboard", "adopt", redirected, *options, success=False
                    )
                    self.assertEqual(
                        refused["error"]["code"], "original_adoption.unsafe-root"
                    )
        self.assertEqual(self.git("ls-files", "--stage"), indexed)
        self.assertFalse((self.root / "litai").exists())
        self.assert_original()

    def test_alternate_git_index_cannot_hide_dirty_native_state(self):
        plan = self.cli("onboard", "adopt", self.root)["result"]
        alternate = self.root.parent / "alternate-index"
        shutil.copyfile(self.root / ".git/index", alternate)
        source = self.root / "src/native.py"
        original = source.read_bytes()
        source.write_text("def value():\n    return 9\n")
        self.git("add", "src/native.py")
        source.write_bytes(original)
        indexed = self.git("ls-files", "--stage", "src/native.py")
        self.assertIn("MM src/native.py", self.git("status", "--porcelain"))
        with patch.dict(os.environ, {"GIT_INDEX_FILE": str(alternate)}):
            for options in (
                (),
                ("--apply", "--acknowledge", "--expect-plan", plan["plan_identity"]),
            ):
                refused = self.cli(
                    "onboard", "adopt", self.root, *options, success=False
                )
                self.assertEqual(
                    refused["error"]["code"], "original_adoption.git-scope-override"
                )
        self.assertEqual(self.git("ls-files", "--stage", "src/native.py"), indexed)
        self.assertFalse((self.root / "litai").exists())
        self.assertEqual(source.read_bytes(), original)

    def test_optional_legacy_owners_refuse_the_minimal_profile_before_work(self):
        plan = self.cli("onboard", "adopt", self.root)["result"]
        self.cli(
            "onboard",
            "adopt",
            self.root,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
        )
        # An unrelated application-root policy cannot select framework release work.
        policy = self.root / "literate.release.json"
        policy.write_bytes(
            (Path(__file__).resolve().parents[2] / "literate.release.json").read_bytes()
        )
        commands = (
            (
                (
                    "catalog",
                    "copy",
                    str(self.root.parent / "unavailable-source"),
                    "skill:demo",
                    "--project",
                    self.root,
                ),
                "catalog.native_profile_unsupported",
            ),
            (
                ("release", "plan", "--project", self.root, "--version", "1.0.0"),
                "release.native_profile_unsupported",
            ),
            (
                ("reparent", "none", "--project", self.root, "--apply"),
                "repository_reparent.native_profile_unsupported",
            ),
        )
        for arguments, code in commands:
            with self.subTest(command=arguments[0]):
                refused = self.cli(*arguments, success=False)
                self.assertEqual(refused["error"]["code"], code)
        self.assertFalse((self.root / ".literate").exists())
        self.assertFalse((self.root / "skills").exists())
        self.assertFalse((self.root / "_build").exists())
        self.assertTrue((self.root / "litai/literate.project.json").is_file())

    def test_public_native_bootstrap_and_source_failure_recovery(self):
        before = sorted(
            str(path.relative_to(self.root))
            for path in self.root.rglob("*")
            if ".git" not in path.parts
        )
        plan = self.cli("onboard", "adopt", self.root)["result"]
        self.assertFalse(plan["writes"])
        self.assertFalse(plan["admitted"])
        self.assertEqual(plan["external_files"], [])
        self.assertEqual(
            before,
            sorted(
                str(path.relative_to(self.root))
                for path in self.root.rglob("*")
                if ".git" not in path.parts
            ),
        )
        result = self.cli(
            "onboard",
            "adopt",
            self.root,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
        )["result"]["initialization"]
        self.assertFalse(result["admitted"])
        self.assertTrue(all(name.startswith("litai/") for name in result["created"]))
        self.assert_original()
        for selected in (self.root, self.root / "litai", self.root / "src"):
            self.cli("project", "validate", selected)
            status = self.cli("status", "--project", selected)["result"]
            self.assertEqual(
                status["project"]["conversion_authority"]["stage"], "original"
            )
            self.assertEqual(status["native_delivery"]["state"], "bootstrap-only")
            self.assertEqual(status["next_verb"], "litai project validate .")
        self.cli("onboard", "adopt", self.root, success=False)
        self.assert_original()
        before_update = {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in (self.root / "litai").rglob("*")
            if p.is_file()
        }
        self.cli("update", self.root)
        self.cli("update", self.root, "--apply")
        after_update = {
            str(p.relative_to(self.root)): p.read_bytes()
            for p in (self.root / "litai").rglob("*")
            if p.is_file() and ".litai-locks" not in p.parts
        }
        self.assertEqual(before_update, after_update)
        self.assert_original()
        source = self.root / "src/native.py"
        original_source = source.read_bytes()
        source.write_text("def value():\n    return 5\n")
        failed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=self.root,
            capture_output=True,
            timeout=30,
        )
        self.assertNotEqual(failed.returncode, 0)
        source.write_bytes(original_source)
        # Avoid timestamp-based native bytecode reuse during the immediate repair.
        fixed = subprocess.run(
            [
                sys.executable,
                "-X",
                "pycache_prefix=" + str(self.root.parent / "fresh-cache"),
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
            ],
            cwd=self.root,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(fixed.returncode, 0, fixed.stderr)
        self.assert_original()

    def test_stale_source_plan_refuses_before_any_framework_publication(self):
        plan = self.cli("onboard", "adopt", self.root)["result"]
        (self.root / "src/native.py").write_text("def value():\n    return 5\n")
        result = self.cli(
            "onboard",
            "adopt",
            self.root,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
            success=False,
        )
        self.assertEqual(result["error"]["code"], "original_adoption.dirty-source")
        self.assertFalse((self.root / "litai").exists())
        self.assertEqual(
            (self.root / "src/native.py").read_text(), "def value():\n    return 5\n"
        )

    def test_branch_policy_never_infers_remote_default_from_feature_upstream(self):
        self.git("remote", "add", "origin", "https://example.invalid/native.git")
        self.git("update-ref", "refs/remotes/origin/feature", "HEAD")
        self.git(
            "config",
            "branch." + self.git("branch", "--show-current") + ".remote",
            "origin",
        )
        self.git(
            "config",
            "branch." + self.git("branch", "--show-current") + ".merge",
            "refs/heads/feature",
        )
        refused = self.cli("onboard", "adopt", self.root, success=False)
        self.assertEqual(
            refused["error"]["code"], "original_adoption.default-branch-required"
        )
        plan = self.cli("onboard", "adopt", self.root, "--default-branch", "main")[
            "result"
        ]
        self.assertEqual(
            plan["project_definition"]["repository_policy"]["default_branch"], "main"
        )
        self.assertFalse((self.root / "litai").exists())
