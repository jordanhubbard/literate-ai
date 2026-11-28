"""Explicit installed framework-placement cell using real legacy producers.

Reuse the metadata journey's real initializer and rollback, then exercise the
public framework placement plan/apply/recovery without invented provenance.
"""

from __future__ import annotations

import hashlib
import json
import os
import unittest
from pathlib import Path

from literate_ai.adapters.user_paths import HostInstallLayout
from tests.support import installed_layout_migration_journey as metadata
from tests.support import installed_native_adoption_journey as adoption


class InstalledFrameworkLayoutJourney(unittest.TestCase):
    run_command = metadata.InstalledLayoutMigrationJourney.run_command
    cli = metadata.InstalledLayoutMigrationJourney.cli
    probe = metadata.InstalledLayoutMigrationJourney.probe

    def after_framework_apply(self, project, launcher, plan):
        """Allow an explicit installed cell to exercise placed producers."""

    def test_installed_framework_placement_after_metadata_rollback(self):
        helper = metadata.InstalledLayoutMigrationJourney(
            "test_real_legacy_metadata_public_migration_and_recovery"
        )
        self.addCleanup(helper.doCleanups)
        helper.test_real_legacy_metadata_public_migration_and_recovery()
        self.root = helper.root
        self.environment = helper.environment
        self.results = list(helper.results)
        project = self.root / "legacy"
        prefix = (
            helper.root / "prefix"
            if os.environ.get("LITAI_INSTALLED_MIGRATION_SOURCE")
            else Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        )
        layout = HostInstallLayout.for_prefix(prefix)
        launcher = Path(layout.launcher)
        python = Path(layout.environment) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        probe = self.probe(python, "framework-distribution-before")
        implementation = project / "components/legacy-project-wrapper/implementation"
        source_before = adoption.InstalledNativeAdoptionJourney.snapshot(implementation)
        index = (project / ".git/index").read_bytes()
        head = self.run_command(
            "framework-head-before", ["git", "rev-parse", "HEAD"], project
        ).stdout
        common = ("--project", str(project))
        selection = ("--rewrite-reference", "docs/user/project-layout.md")
        metadata_plan = self.cli(
            "metadata-replan",
            launcher,
            "project",
            "layout",
            "plan",
            "--migration",
            *common,
            *selection,
            cwd=self.root,
        )["result"]
        self.assertTrue(metadata_plan["applicable"], metadata_plan)
        self.cli(
            "metadata-reapply",
            launcher,
            "project",
            "layout",
            "apply",
            *common,
            *selection,
            "--plan-identity",
            metadata_plan["plan_identity"],
            "--acknowledge",
            cwd=self.root,
        )
        originals = {
            name: (project / name).read_bytes()
            for name in ("litai.harness.mk", "SKILL.md")
        }
        before = adoption.InstalledNativeAdoptionJourney.snapshot(project)
        plan = self.cli(
            "framework-plan",
            launcher,
            "project",
            "layout",
            "plan",
            "--migration",
            "--place-framework-authority",
            *common,
            cwd=self.root,
        )["result"]
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(project), before
        )
        self.assertTrue(plan["applicable"], plan["required_owners"])
        self.assertFalse(plan["full_containment"])
        descendant = self.cli(
            "framework-descendant-plan",
            launcher,
            "project",
            "layout",
            "plan",
            "--migration",
            "--place-framework-authority",
            "--project",
            str(project / "components"),
            cwd=self.root,
        )["result"]
        identity = plan["plan_identity"]
        self.assertEqual(descendant["plan_identity"], identity)
        applied = self.cli(
            "framework-apply",
            launcher,
            "project",
            "layout",
            "apply",
            *common,
            "--place-framework-authority",
            "--plan-identity",
            identity,
            "--acknowledge",
            cwd=self.root,
        )["result"]
        self.assertTrue(applied["applied"])
        self.assertFalse(applied["full_containment"])
        self.assertFalse((project / "litai.harness.mk").exists())
        self.assertEqual(
            (project / "litai/litai.harness.mk").read_bytes(),
            originals["litai.harness.mk"],
        )
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(implementation),
            source_before,
        )
        self.after_framework_apply(project, launcher, plan)
        for repeat in range(2):
            recovered = self.cli(
                f"framework-recover-{repeat}",
                launcher,
                "project",
                "layout",
                "recover",
                *common,
                "--place-framework-authority",
                "--plan-identity",
                identity,
                "--acknowledge",
                cwd=self.root,
            )["result"]
            self.assertTrue(recovered["rolled_back"])
        for name, content in originals.items():
            self.assertEqual((project / name).read_bytes(), content)
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(implementation),
            source_before,
        )
        self.assertEqual((project / ".git/index").read_bytes(), index)
        self.assertEqual(
            self.run_command(
                "framework-head-after", ["git", "rev-parse", "HEAD"], project
            ).stdout,
            head,
        )
        self.assertEqual(self.probe(python, "framework-distribution-after"), probe)
        (self.root / "framework-receipt.json").write_text(
            json.dumps(
                {
                    "schema": "literate-ai/installed-framework-layout-observation@1",
                    "installed_distribution": probe,
                    "plan_identity": identity,
                    "index_sha256": hashlib.sha256(index).hexdigest(),
                    "retained_source_tree": source_before,
                    "commands": self.results,
                    "scope": (
                        "Installed metadata reapply and framework placement/rollback; "
                        "Not full containment, producer renewal or release "
                        "qualification."
                    ),
                    "release_qualification": False,
                },
                indent=2,
            )
            + "\n"
        )
