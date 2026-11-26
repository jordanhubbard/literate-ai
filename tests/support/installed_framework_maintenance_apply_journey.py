"""Installed maintenance application after genuine migration/finalization.

Use an explicitly selected immutable installed prefix. Keep the resulting fixture
for inspection; this cell covers update and unchanged-parent application, not
changed-parent acceptance or complete supported-platform containment.
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
from tests.support.installed_framework_maintenance_resume import file_state


class InstalledFrameworkMaintenanceJourney(unittest.TestCase):
    run_command = metadata.InstalledLayoutMigrationJourney.run_command
    cli = metadata.InstalledLayoutMigrationJourney.cli
    probe = metadata.InstalledLayoutMigrationJourney.probe

    def test_update_and_unchanged_reparent_apply_after_finalization(self):
        helper = metadata.InstalledLayoutMigrationJourney(
            "test_real_legacy_metadata_public_migration_and_recovery"
        )
        self.addCleanup(helper.doCleanups)
        helper.test_real_legacy_metadata_public_migration_and_recovery()
        self.root, self.environment = helper.root, helper.environment
        self.results = list(helper.results)
        project = self.root / "legacy"
        prefix = Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        layout = HostInstallLayout.for_prefix(prefix)
        launcher = Path(layout.launcher)
        python = Path(layout.environment) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        distribution = self.probe(python, "maintenance-distribution-before")
        implementation = project / "components/legacy-project-wrapper/implementation"
        snapshot = adoption.InstalledNativeAdoptionJourney.snapshot
        original_source = snapshot(implementation)
        index = file_state(project / ".git/index")[0]
        head = self.run_command(
            "maintenance-head-before",
            ["git", "--no-optional-locks", "rev-parse", "HEAD"],
            project,
        ).stdout
        common = ("--project", str(project))
        selection = ("--rewrite-reference", "docs/user/project-layout.md")
        metadata_plan = self.cli(
            "maintenance-metadata-plan",
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
            "maintenance-metadata-apply",
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
        plan = self.cli(
            "maintenance-framework-plan",
            launcher,
            "project",
            "layout",
            "plan",
            "--migration",
            "--place-framework-authority",
            *common,
            cwd=self.root,
        )["result"]
        identity = plan["plan_identity"]
        placed = self.cli(
            "maintenance-framework-apply",
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
        self.assertTrue(placed["applied"], placed)
        self.assertFalse(placed["full_containment"])
        component = "litai/components/legacy-project-wrapper"
        lock = json.loads((project / component / "component.lock.json").read_bytes())
        continuation = (
            "--project",
            str(project / "litai/components"),
            "--place-framework-authority",
            "--plan-identity",
            identity,
            "--acknowledge",
        )
        renewed = self.cli(
            "maintenance-producer-renew",
            launcher,
            "project",
            "layout",
            "renew",
            *continuation,
            "--component",
            component,
            "--target",
            lock["target_name"],
            cwd=self.root,
        )["result"]
        self.assertTrue(renewed["current"], renewed)
        for repeat in range(2):
            finalized = self.cli(
                f"maintenance-finalize-{repeat}",
                launcher,
                "project",
                "layout",
                "finalize",
                *continuation,
                cwd=self.root,
            )["result"]
            self.assertTrue(finalized["components_finalized"], finalized)
            self.assertFalse(finalized["full_containment"])

        journal = Path(placed["journal"])
        self.assertTrue(journal.is_relative_to(project / "litai/.literate"))
        self.exercise_maintenance(
            project=project,
            launcher=launcher,
            python=python,
            distribution=distribution,
            implementation=implementation,
            original_source=original_source,
            index=index,
            head=head,
            journal=journal,
            identity=identity,
        )

    def exercise_maintenance(
        self,
        *,
        project,
        launcher,
        python,
        distribution,
        implementation,
        original_source,
        index,
        head,
        journal,
        identity,
        original_update_framework=None,
        label_prefix="maintenance",
        receipt_name="maintenance-receipt.json",
    ):
        """Keep the same source/Git/history assertions for fresh and retained input."""
        snapshot = adoption.InstalledNativeAdoptionJourney.snapshot
        receipt_path = self.root / receipt_name
        self.assertFalse(receipt_path.exists())
        intent = file_state(journal / "intent.json")[0]
        authority_paths = [
            project / "litai/literate.project.json",
            project / "litai/.literate/initialization-baseline.json",
            project / "litai/.literate/initialization-origin.json",
            project / "litai/.literate/update-bases.json",
            journal / "intent.json",
        ]
        outcomes = {}
        passed = False
        try:
            for operation in ("update", "reparent"):
                before = {path: file_state(path) for path in authority_paths}
                identities = []
                for coordinate, selected in (
                    ("root", project),
                    ("descendant", project / "litai/components"),
                ):
                    arguments = (
                        ("update", str(selected))
                        if operation == "update"
                        else ("reparent", "none", "--project", str(selected))
                    )
                    result = self.cli(
                        f"{label_prefix}-{operation}-plan-{coordinate}",
                        launcher,
                        *arguments,
                        cwd=self.root,
                    )["result"]
                    self.assertEqual(result["mode"], "read-only-plan")
                    if operation == "update" and original_update_framework is not None:
                        for key in (
                            "baseline_identity",
                            "project_identity",
                            "previous_origin",
                            "update_bases_identity",
                        ):
                            self.assertEqual(
                                result["framework"][key],
                                original_update_framework[key],
                                key,
                            )
                    identities.append(
                        result["plan_identity" if operation == "update" else "identity"]
                    )
                    for path, state in before.items():
                        self.assertEqual(file_state(path), state, path)
                    self.assertEqual(snapshot(implementation), original_source)
                    self.assertEqual(file_state(project / ".git/index")[0], index)
                self.assertEqual(identities[0], identities[1])
                arguments = (
                    ("update", str(project / "litai/components"), "--apply")
                    if operation == "update"
                    else ("reparent", "none", "--project", str(project), "--apply")
                )
                result = self.cli(
                    f"{label_prefix}-{operation}-apply",
                    launcher,
                    *arguments,
                    cwd=self.root,
                )["result"]
                self.assertEqual(result["mode"], "applied")
                self.assertEqual(
                    result["plan_identity" if operation == "update" else "identity"],
                    identities[0],
                )
                if operation == "reparent":
                    self.assertFalse(result["changed"])
                else:
                    self.assertFalse(result["source_moved"])
                self.assertEqual(snapshot(implementation), original_source)
                self.assertEqual(file_state(project / ".git/index")[0], index)
                self.assertEqual(file_state(journal / "intent.json")[0], intent)
                outcomes[operation] = result
            self.assertEqual(
                self.run_command(
                    f"{label_prefix}-head-after",
                    ["git", "--no-optional-locks", "rev-parse", "HEAD"],
                    project,
                ).stdout,
                head,
            )
            self.assertEqual(
                self.probe(python, f"{label_prefix}-distribution-after"), distribution
            )
            passed = True
        finally:
            with receipt_path.open("x") as stream:
                stream.write(
                    json.dumps(
                        {
                            "record_version": 1,
                            "installed_distribution": distribution,
                            "fixture": str(project.parent),
                            "observation": str(self.root),
                            "framework_plan_identity": identity,
                            "migration_intent_sha256": hashlib.sha256(
                                intent
                            ).hexdigest(),
                            "original_source": original_source,
                            "index_sha256": hashlib.sha256(index).hexdigest(),
                            "maintenance_outcomes": outcomes,
                            "commands": self.results,
                            "passed": passed,
                            "scope": (
                                "Installed update and unchanged-parent application "
                                "after real finalization; changed-parent and complete "
                                "containment/platform/release acceptance remain open."
                            ),
                            "release_qualification": False,
                        },
                        indent=2,
                    )
                    + "\n"
                )
