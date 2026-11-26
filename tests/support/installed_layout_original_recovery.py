"""Explicit recovery of the original retained failed installed migration fixture.

The caller binds the exact original receipt and current installed subject. Run
only through managed Make after the repaired wheel's ordinary journey passes.
No fixture reconstruction, historical receipt renewal or application execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.user_paths import HostInstallLayout
from tests.support import installed_native_adoption_journey as adoption
from tests.support import installed_project_layout_journey as journey


class InstalledOriginalLayoutRecovery(unittest.TestCase):
    run_command = journey.InstalledProjectLayoutJourney.run_command
    cli = journey.InstalledProjectLayoutJourney.cli

    def test_original_failed_wheel_journal_recovers_without_source_changes(self):
        receipt_path = Path(os.environ["LITAI_ORIGINAL_LAYOUT_RECEIPT"]).absolute()
        require_safe_directory(receipt_path.parent)
        self.assertFalse(receipt_path.is_symlink())
        encoded = receipt_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(encoded).hexdigest(),
            os.environ["LITAI_ORIGINAL_LAYOUT_RECEIPT_SHA256"],
        )
        original = json.loads(encoded)
        fixture = Path(original["fixture"])
        self.assertTrue(fixture.is_absolute())
        require_safe_directory(fixture)
        project = fixture / "legacy"
        require_safe_directory(project)
        prefix = Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        parent = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(prefix)
        require_safe_directory(parent)
        self.root = Path(tempfile.mkdtemp(prefix="ir-", dir=parent))
        print("retained original recovery observation:", self.root, flush=True)
        self.environment = journey.isolated_layout_environment(self.root)
        self.results = []
        layout = HostInstallLayout.for_prefix(prefix)
        python = Path(layout.environment) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        probe = self.probe(python, "installed-distribution")
        self.assertEqual(
            probe["origin"]["git_revision"],
            os.environ["LITAI_INSTALLED_LAYOUT_REVISION"],
        )
        self.assertEqual(
            probe["distribution_identity"],
            os.environ["LITAI_INSTALLED_LAYOUT_DISTRIBUTION"],
        )
        relative = "legacy/.git/literate-layout-migration/intent.json"
        intent_path = fixture / relative
        require_safe_directory(intent_path.parent)
        self.assertFalse(intent_path.is_symlink())
        intent_bytes = intent_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(intent_bytes).hexdigest(),
            original["files"][relative]["sha256"],
        )
        intent = json.loads(intent_bytes)
        self.assertEqual(intent["plan"]["project"], str(project))
        self.assertEqual(intent["plan"]["plan_identity"], original["plan_identity"])
        head = self.run_command(
            "git-head-before", ["git", "rev-parse", "HEAD"], project
        ).stdout
        self.assertEqual(head, (fixture / "git-head-before.stdout").read_bytes())
        index = (project / ".git/index").read_bytes()
        implementation = project / "components/legacy-project-wrapper/implementation"
        require_safe_directory(implementation)
        source = adoption.InstalledNativeAdoptionJourney.snapshot(implementation)
        self.assertFalse((project / "literate.project.json").exists())
        self.assertTrue((project / "litai/literate.project.json").is_file())
        result = self.cli(
            "recover-original-journal",
            Path(layout.launcher),
            "project",
            "layout",
            "recover",
            "--project",
            str(project),
            "--plan-identity",
            original["plan_identity"],
            "--acknowledge",
            cwd=self.root,
        )["result"]
        self.assertTrue(result["rolled_back"])
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(implementation), source
        )
        self.assertEqual((project / ".git/index").read_bytes(), index)
        self.assertEqual(
            self.run_command(
                "git-head-after", ["git", "rev-parse", "HEAD"], project
            ).stdout,
            head,
        )
        self.assertFalse(
            self.run_command(
                "git-tracked-state-after",
                [
                    "git",
                    "--no-optional-locks",
                    "status",
                    "--porcelain=v1",
                    "--untracked-files=no",
                ],
                project,
            ).stdout
        )
        archive = Path(result["journal"])
        self.assertEqual(archive.parent, project / ".git")
        require_safe_directory(archive)
        self.assertEqual((archive / "intent.json").read_bytes(), intent_bytes)
        self.assertEqual(self.probe(python, "installed-distribution-after"), probe)
        self.assertEqual((project / ".git/index").read_bytes(), index)
        observation = {
            "schema": "literate-ai/installed-original-layout-recovery@1",
            "original_receipt_sha256": hashlib.sha256(encoded).hexdigest(),
            "original_subject": original["subject"],
            "installed_distribution": probe,
            "plan_identity": original["plan_identity"],
            "original_intent_sha256": hashlib.sha256(intent_bytes).hexdigest(),
            "native_source_tree": source,
            "index_sha256": hashlib.sha256(index).hexdigest(),
            "commands": self.results,
            "scope": (
                "Recover the exact original failed installed metadata journal; "
                "source/Git and archived intent preserved. No native build, "
                "complete containment, other-platform or release qualification."
            ),
            "release_qualification": False,
        }
        (self.root / "receipt.json").write_text(
            json.dumps(observation, indent=2) + "\n"
        )

    def probe(self, python, phase):
        return json.loads(
            self.run_command(
                phase,
                [str(python), "-I", "-c", journey.PROBE],
                self.root,
            ).stdout
        )
