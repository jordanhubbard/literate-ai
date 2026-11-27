"""Installed template application and a real local Git parent transition.

Fixture roots use the installed initializer's ordinary canonical root selection.
The tested maintenance commands use its public launcher; no mocked execution,
credential source, worker, driver rebind or documentation-review recording.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.user_paths import HostInstallLayout
from tests.support import installed_layout_migration_journey as metadata
from tests.support import installed_native_adoption_journey as adoption
from tests.support import installed_project_layout_journey as journey

SETUP = r"""
import json,sys
from pathlib import Path
from literate_ai.adapters.project_initialization import (
    FilesystemProjectInitializationAdapter, host_platform_selector,
)
from literate_ai.contracts import RepositoryParentSelection
root=Path(sys.argv[1])
result=FilesystemProjectInitializationAdapter().initialize(
    root, project_id=root.name, empty=True, bootstrap_tools=False,
    source_intelligence_provider='none',
    flavor_selectors=('+python',host_platform_selector()),
    parent_selection=RepositoryParentSelection.root(),
)
Path(sys.argv[2]).write_text(json.dumps(result,default=str,indent=2)+'\n')
"""


class InstalledFrameworkParentJourney(unittest.TestCase):
    run_command = journey.InstalledProjectLayoutJourney.run_command
    cli = journey.InstalledProjectLayoutJourney.cli
    probe = metadata.InstalledLayoutMigrationJourney.probe

    def assert_source_current(self):
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(self.child), self.source
        )
        self.assertEqual((self.child / ".git/index").read_bytes(), self.index)

    def child_cli(self, label, *arguments):
        try:
            return self.cli(label, self.launcher, *arguments, cwd=self.root)["result"]
        finally:
            self.assert_source_current()

    def test_real_root_update_then_local_parent_plan_apply_and_update(self):
        output = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(output)
        self.root = Path(tempfile.mkdtemp(prefix="ipar-", dir=output))
        print("retained installed parent fixture:", self.root, flush=True)
        self.environment = journey.isolated_layout_environment(self.root)
        self.results = []
        prefix = Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        require_safe_directory(prefix)
        layout = HostInstallLayout.for_prefix(prefix)
        python = Path(layout.environment) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        self.launcher = Path(layout.launcher)
        probe = self.probe(python, "installed-distribution")
        self.assertEqual(
            probe["origin"]["git_revision"],
            os.environ["LITAI_INSTALLED_LAYOUT_REVISION"],
        )
        self.assertEqual(
            probe["distribution_identity"],
            os.environ["LITAI_INSTALLED_LAYOUT_DISTRIBUTION"],
        )
        parent, self.child = self.root / "parent", self.root / "child"
        for name, project in (("parent", parent), ("child", self.child)):
            self.run_command(
                f"{name}-initialize",
                [
                    str(python),
                    "-I",
                    "-c",
                    SETUP,
                    str(project),
                    str(self.root / f"{name}-initialization.json"),
                ],
                self.root,
            )
            self.assertTrue((project / "litai/literate.project.json").is_file())
            self.assertFalse((project / "literate.project.json").exists())
            if name == "child":
                (project / "application.txt").write_bytes(
                    b"Application-owned source fixture.\n"
                )
                private = project / ".literate"
                private.mkdir()
                (private / "private.txt").write_bytes(
                    b"Application-owned metadata fixture.\n"
                )
                with (project / "AGENTS.md").open("a") as stream:
                    stream.write("\nKeep the application's custom instructions.\n")
            for phase, command in (
                ("git-init", ["git", "init", "-b", "main"]),
                ("git-add", ["git", "add", "."]),
                (
                    "git-commit",
                    [
                        "git",
                        "-c",
                        "user.name=Parent Fixture",
                        "-c",
                        "user.email=parent@example.invalid",
                        "-c",
                        "commit.gpgsign=false",
                        "commit",
                        "-m",
                        "Original canonical fixture",
                    ],
                ),
            ):
                self.run_command(f"{name}-{phase}", command, project)
        revision = (
            self.run_command("parent-head", ["git", "rev-parse", "HEAD"], parent)
            .stdout.decode()
            .strip()
        )
        reference = f"{parent.as_uri()}#{revision}"
        head = self.run_command(
            "child-head-before",
            ["git", "--no-optional-locks", "rev-parse", "HEAD"],
            self.child,
        ).stdout
        self.source = adoption.InstalledNativeAdoptionJourney.snapshot(self.child)
        self.index = (self.child / ".git/index").read_bytes()
        root_plan = self.child_cli("root-update-plan", "update", str(self.child))
        self.assertEqual(root_plan["mode"], "read-only-plan")
        applied = self.child_cli(
            "root-update-apply", "update", str(self.child), "--apply"
        )
        self.assertEqual(applied["mode"], "applied")
        self.assertFalse(applied["source_moved"])
        lineage_paths = [
            self.child / "litai/.literate" / name
            for name in ("repository-parent.json", "repository-lineage.json")
        ]
        before = {path: path.read_bytes() for path in lineage_paths}
        plan = self.child_cli(
            "new-parent-plan", "reparent", reference, "--project", str(self.child)
        )
        self.assertTrue(plan["changed"], plan)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)
        reparented = self.child_cli(
            "new-parent-apply",
            "reparent",
            reference,
            "--project",
            str(self.child),
            "--apply",
        )
        self.assertEqual(reparented["applied"]["state"], "applied")
        self.assertTrue(reparented["applied"]["changed"])
        self.assertTrue(reparented["applied"]["authority_review_required"])
        self.assertNotEqual({path: path.read_bytes() for path in lineage_paths}, before)
        inherited = self.child_cli(
            "inherited-update-plan", "update", str(self.child / "litai/components")
        )
        self.assertEqual(inherited["mode"], "read-only-plan")
        updated = self.child_cli(
            "inherited-update-apply",
            "update",
            str(self.child),
            "--apply",
            "--adopt-added",
        )
        self.assertEqual(updated["mode"], "applied")
        self.assertEqual(
            self.run_command(
                "child-head-after",
                ["git", "--no-optional-locks", "rev-parse", "HEAD"],
                self.child,
            ).stdout,
            head,
        )
        self.assertEqual(self.probe(python, "installed-distribution-after"), probe)
        (self.root / "receipt.json").write_text(
            json.dumps(
                {
                    "schema": "literate-ai/installed-parent-maintenance-observation@1",
                    "installed_distribution": probe,
                    "parent_reference": reference,
                    "source": self.source,
                    "commands": self.results,
                    "scope": (
                        "Canonical initializer fixture setup; public installed "
                        "root update and local changed-parent/update application "
                        "with source/Git preservation. Not fresh public onboarding, "
                        "migrated-project application, native build, "
                        "other-platform, full containment or release qualification."
                    ),
                    "release_qualification": False,
                },
                indent=2,
            )
            + "\n"
        )
