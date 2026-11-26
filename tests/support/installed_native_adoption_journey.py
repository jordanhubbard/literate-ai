"""Explicit installed native-adoption cell; never execute native application code.

Use the canonical managed python-check runner with this filename as its pattern.
The caller supplies a previously observed noneditable LITAI_INSTALLED_LAYOUT_PREFIX,
its exact REVISION and DISTRIBUTION identity, and a local OUTPUT parent. Verify the
actual installed bytes again before operating on this test's new private Git tree.
All outputs remain retained. This is one local platform, not release qualification.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.user_paths import HostInstallLayout
from tests.support import installed_project_layout_journey as journey


class InstalledNativeAdoptionJourney(unittest.TestCase):
    run_command = journey.InstalledProjectLayoutJourney.run_command
    cli = journey.InstalledProjectLayoutJourney.cli

    def test_native_plan_apply_preserves_custom_source_and_git(self):
        prefix = Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        parent = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(prefix)
        require_safe_directory(parent)
        self.root = Path(tempfile.mkdtemp(prefix="ia-", dir=parent))
        print("retained native adoption fixture:", self.root, flush=True)
        self.environment = journey.isolated_layout_environment(self.root)
        self.results = []
        layout = HostInstallLayout.for_prefix(prefix)
        environment = Path(layout.environment)
        python = environment / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        launcher = Path(layout.launcher)
        probe = json.loads(
            self.run_command(
                "installed-distribution",
                [str(python), "-I", "-c", journey.PROBE],
                self.root,
            ).stdout
        )
        self.assertEqual(
            probe["origin"]["git_revision"],
            os.environ["LITAI_INSTALLED_LAYOUT_REVISION"],
        )
        self.assertEqual(
            probe["distribution_identity"],
            os.environ["LITAI_INSTALLED_LAYOUT_DISTRIBUTION"],
        )
        native = self.root / "native"
        native.mkdir()
        original = {
            "src/main.py": b"print('native fixture only; never executed')\n",
            "Makefile": b"all:\n\t@echo native fixture only\n",
            "README.md": b"# Existing application documentation\n",
            "AGENTS.md": b"# Existing agent instructions\nPreserve native tools.\n",
            "SKILL.md": b"# Custom application instructions\nKeep these bytes.\n",
            "docs/notes.md": b"Existing application design notes.\n",
            ".literate/app-metadata.txt": b"Synthetic application-owned metadata.\n",
        }
        for relative, content in original.items():
            path = native / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        (native / "src/main.py").chmod(0o755)
        self.run_command("git-init", ["git", "init", "-b", "main"], native)
        self.run_command("git-add", ["git", "add", "."], native)
        self.run_command(
            "git-commit",
            [
                "git",
                "-c",
                "user.name=Installed layout fixture",
                "-c",
                "user.email=layout@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "Original application",
            ],
            native,
        )
        before = self.snapshot(native)
        head = self.run_command(
            "git-head-before", ["git", "rev-parse", "HEAD"], native
        ).stdout
        index = (native / ".git/index").read_bytes()
        plan = self.cli(
            "adopt-plan", launcher, "onboard", "adopt", str(native), cwd=self.root
        )["result"]
        self.assertFalse(plan["writes"])
        self.assertTrue(plan["apply_supported"])
        self.assertEqual(plan["external_files"], [])
        self.assertEqual(self.snapshot(native), before)
        self.assertFalse((native / "litai").exists())
        result = self.cli(
            "adopt-apply",
            launcher,
            "onboard",
            "adopt",
            str(native),
            "--apply",
            "--acknowledge",
            "--expect-plan",
            plan["plan_identity"],
            cwd=self.root,
        )["result"]
        self.assertTrue(result["applied"])
        self.assertEqual(self.snapshot(native), before)
        self.assertEqual((native / ".git/index").read_bytes(), index)
        self.assertEqual(
            self.run_command(
                "git-head-after", ["git", "rev-parse", "HEAD"], native
            ).stdout,
            head,
        )
        allowed = {Path(relative).parts[0] for relative in original} | {".git", "litai"}
        self.assertEqual({p.name for p in native.iterdir()}, allowed)
        manifest = json.loads((native / "litai/literate.project.json").read_bytes())
        self.assertEqual(manifest["framework_directory"], "litai")
        self.assertFalse((native / "literate.project.json").exists())
        self.cli(
            "adopt-validate-root",
            launcher,
            "project",
            "validate",
            str(native),
            cwd=self.root,
        )
        self.assertEqual(self.snapshot(native), before)
        self.cli(
            "adopt-validate-native-subdirectory",
            launcher,
            "project",
            "validate",
            str(native / "src"),
            cwd=self.root,
        )
        self.assertEqual(self.snapshot(native), before)
        closing = json.loads(
            self.run_command(
                "installed-distribution-after",
                [str(python), "-I", "-c", journey.PROBE],
                self.root,
            ).stdout
        )
        self.assertEqual(closing, probe)
        receipt = {
            "schema": "literate-ai/installed-native-adoption-observation@1",
            "fixture": str(self.root),
            "installed_distribution": probe,
            "native_head": head.decode().strip(),
            "index_sha256": hashlib.sha256(index).hexdigest(),
            "original_application_tree": before,
            "commands": self.results,
            "scope": (
                "Actual installed native plan/apply and root/subdirectory "
                "validation; original source/custom instructions/modes/inodes/Git "
                "preserved. No build, model, worker, migration, update/reparent, "
                "other-platform or full release qualification."
            ),
            "release_qualification": False,
        }
        (self.root / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    @staticmethod
    def snapshot(root):
        """Observe every application entry without following redirects.

        Git administration is checked separately. Only the root framework
        directory is allowed to appear; nested application metadata is included.
        """
        result = {}
        pending = [root]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                children = sorted(entries, key=lambda entry: entry.name)
            for entry in children:
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if directory == root and entry.name in {".git", "litai"}:
                    continue
                node = entry.stat(follow_symlinks=False)
                redirected = stat.S_ISLNK(node.st_mode) or bool(
                    getattr(node, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                )
                if redirected:
                    raise AssertionError(f"Application redirect: {relative}")
                if stat.S_ISDIR(node.st_mode):
                    kind = "directory"
                    pending.append(path)
                elif stat.S_ISREG(node.st_mode):
                    kind = "file"
                else:
                    raise AssertionError(f"Unsupported application entry: {relative}")
                result[relative] = {
                    "kind": kind,
                    "device": node.st_dev,
                    "inode": node.st_ino,
                    "mode": stat.S_IMODE(node.st_mode),
                    "uid": node.st_uid,
                    "gid": node.st_gid,
                    "mtime_ns": node.st_mtime_ns,
                }
                if kind == "file":
                    result[relative]["sha256"] = hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
        return result
