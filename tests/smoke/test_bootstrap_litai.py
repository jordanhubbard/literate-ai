"""Generated bootstrap works before LitAI exists and never changes project pins."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import project_initialization
from literate_ai.adapters.project_update_apply import apply_project_update
from literate_ai.adapters.project_updates import FilesystemProjectUpdateAdapter
from literate_ai.contracts import (
    ProjectInitializationOrigin,
    ProjectUpdateClassification,
)
from tests.smoke.test_project_reparenting import initialize_root


class GeneratedBootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "project"
        initialize_root(self.root)
        manifest = self.root / "literate.project.json"
        definition = json.loads(manifest.read_text())
        definition["lifecycle_driver"] = {
            "binding": "standard",
            "framework_distribution_identity": {
                "algorithm": "sha256",
                "digest": "a" * 64,
            },
        }
        manifest.write_text(json.dumps(definition))
        self.script = self.root / "scripts/bootstrap_litai.py"

    def module(self):
        spec = importlib.util.spec_from_file_location(
            "generated_bootstrap", self.script
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_generated_route_and_missing_cli_are_read_only(self) -> None:
        self.assertTrue(self.script.is_file())
        self.assertTrue((self.root / "docs/user/bootstrap.md").is_file())
        self.assertIn("user/bootstrap.md", (self.root / "docs/README.md").read_text())
        skill = (self.root / "SKILL.md").read_text()
        self.assertLess(
            skill.index("docs/user/bootstrap.md"), skill.index("`litai doctor`")
        )
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertIn("SKILL.md", (self.root / name).read_text())
        before = (self.root / "literate.project.json").read_bytes()
        process = subprocess.run(
            [sys.executable, "-I", str(self.script), "--json"],
            cwd=self.root,
            env={**os.environ, "PATH": ""},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(process.returncode, 1, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["state"], "missing")
        self.assertEqual(report["required_distribution"], "sha256:" + "a" * 64)
        self.assertEqual((self.root / "literate.project.json").read_bytes(), before)

    def test_incompatible_and_ready_runtime_checks_preserve_custom_rules(self) -> None:
        module = self.module()
        custom = b"# Custom rules\r\n\r\nKeep our workflow. Read SKILL.md.\r\n"
        (self.root / "AGENTS.md").write_bytes(custom)
        before = (self.root / "literate.project.json").read_bytes()

        def completed(matches: bool) -> subprocess.CompletedProcess[str]:
            error = (
                None if matches else {"code": "standard_binding.distribution_mismatch"}
            )
            return subprocess.CompletedProcess(
                ["litai"],
                0 if matches else 1,
                stdout=json.dumps(
                    {
                        "ok": matches,
                        "result": {
                            "ok": matches,
                            "project": {
                                "derived_identities": {
                                    "driver_identity_matches": matches,
                                    "driver_resolution_error": error,
                                }
                            },
                        },
                    }
                ),
            )

        with mock.patch.object(module.subprocess, "run", return_value=completed(False)):
            incompatible = module.check(self.root, "litai")
        self.assertEqual(incompatible["state"], "incompatible")
        with mock.patch.object(module.subprocess, "run", return_value=completed(True)):
            ready = module.check(self.root, "litai")
        self.assertEqual(ready["state"], "ready")
        self.assertEqual((self.root / "literate.project.json").read_bytes(), before)
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), custom)

    def test_wheel_checksum_and_missing_file_fail_closed(self) -> None:
        module = self.module()
        wheel = self.root / "wheel.whl"
        wheel.write_bytes(b"wheel bytes")
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        self.assertEqual(module.verify_wheel(wheel, digest)["state"], "wheel-verified")
        self.assertEqual(
            module.verify_wheel(wheel, "0" * 64)["state"], "checksum-mismatch"
        )
        self.assertEqual(
            module.verify_wheel(wheel.with_name("absent.whl"), digest)["state"],
            "wheel-unavailable",
        )

    def test_update_adds_bootstrap_files_without_replacing_custom_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "older-project"
            old_files = {
                path: resource
                for path, resource in project_initialization._TEMPLATE_FILES.items()
                if path not in {"scripts/bootstrap_litai.py", "docs/user/bootstrap.md"}
            }
            old_starter_docs = dict(project_initialization._STARTER_DOCS)
            old_starter_docs["docs/README.md"] = old_starter_docs[
                "docs/README.md"
            ].replace(
                "Before running LitAI, follow "
                "[project bootstrap](user/bootstrap.md).\n",
                "",
            )
            current_template = project_initialization._template_text

            def older_template(resource: str) -> str:
                text = current_template(resource)
                if resource == "SKILL.md":
                    prefix, rest = text.split("Before any `litai` command", 1)
                    _, suffix = rest.split("Treat specifications", 1)
                    return prefix + "Treat specifications" + suffix
                return text

            with (
                mock.patch.object(project_initialization, "_TEMPLATE_FILES", old_files),
                mock.patch.object(
                    project_initialization, "_STARTER_DOCS", old_starter_docs
                ),
                mock.patch.object(
                    project_initialization,
                    "_template_text",
                    side_effect=older_template,
                ),
            ):
                initialize_root(target)
            custom = b"# Project agent rules\n\nPreserve our workflow. Read SKILL.md.\n"
            (target / "AGENTS.md").write_bytes(custom)
            before = (target / "literate.project.json").read_bytes()
            successor = ProjectInitializationOrigin(
                "https://example.test/literate-ai.git",
                "b" * 40,
                "literate-ai",
                "0.3.0",
            )
            plan = FilesystemProjectUpdateAdapter(
                origin_provider=lambda: successor
            ).plan(target)
            by_path = {item.path: item.classification for item in plan.files}
            for path in ("scripts/bootstrap_litai.py", "docs/user/bootstrap.md"):
                self.assertEqual(
                    by_path[path], ProjectUpdateClassification.UPSTREAM_ADDED
                )
            self.assertEqual(
                by_path["SKILL.md"], ProjectUpdateClassification.UPSTREAM_ONLY
            )
            apply_project_update(plan, target, adopt_added=True)
            self.assertTrue((target / "scripts/bootstrap_litai.py").is_file())
            self.assertTrue((target / "docs/user/bootstrap.md").is_file())
            self.assertIn("user/bootstrap.md", (target / "docs/README.md").read_text())
            updated_skill = (target / "SKILL.md").read_text()
            self.assertLess(
                updated_skill.index("docs/user/bootstrap.md"),
                updated_skill.index("`litai doctor`"),
            )
            self.assertEqual((target / "AGENTS.md").read_bytes(), custom)
            self.assertEqual((target / "literate.project.json").read_bytes(), before)
