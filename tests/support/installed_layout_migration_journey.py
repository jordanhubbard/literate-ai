"""Installed public migration on real producers in explicit legacy fixture mode.

The internal initializer selector constructs historical coordinates only. It does
not simulate a released historical distribution or bypass baseline producers.
The migration/recovery commands use the installed public launcher. Retain outputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.user_paths import HostInstallLayout
from tests.support import installed_native_adoption_journey as adoption
from tests.support import installed_project_layout_journey as journey

MIGRATION_IMPORT_PROBE = r"""
import importlib,json,sys
from pathlib import Path
assert sys.flags.isolated and sys.prefix != sys.base_prefix
prefix=Path(sys.prefix).resolve()
observed={}
for name in (
    'literate_ai.adapters.project_layout_continuation',
    'literate_ai.adapters.project_layout_framework_ingress',
    'literate_ai.adapters.project_layout_framework_transaction',
    'literate_ai.adapters.project_layout_framework_renewal',
    'literate_ai.cli.layout_component_commands',
):
    module=importlib.import_module(name)
    path=Path(module.__file__).resolve()
    assert path.is_relative_to(prefix), name
    observed[name]=str(path)
print(json.dumps(observed,sort_keys=True))
"""

SETUP = r"""
import json,sys
from pathlib import Path
from literate_ai.adapters.project_initialization import (
    FilesystemProjectInitializationAdapter, detect_repo_flavors,
    host_platform_selector,
)
from literate_ai.adapters.project_scaffold_placement import ScaffoldLayout
from literate_ai.contracts import RepositoryParentSelection
root=Path(sys.argv[1])
selectors=tuple('+'+s for s in detect_repo_flavors(root))+(host_platform_selector(),)
result=FilesystemProjectInitializationAdapter().initialize(
    root, flavor_selectors=selectors, convert=True, run_baseline=True,
    bootstrap_tools=False, parent_selection=RepositoryParentSelection.root(),
    _layout=ScaffoldLayout.LEGACY_ROOT_FIXTURE,
)
Path(sys.argv[2]).write_text(json.dumps(result,default=str,indent=2)+'\n')
"""


class InstalledLayoutMigrationJourney(unittest.TestCase):
    run_command = journey.InstalledProjectLayoutJourney.run_command
    cli = journey.InstalledProjectLayoutJourney.cli

    def test_real_legacy_metadata_public_migration_and_recovery(self):
        parent = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(parent)
        self.root = Path(tempfile.mkdtemp(prefix="im-", dir=parent))
        print("retained installed migration fixture:", self.root, flush=True)
        self.environment = journey.isolated_layout_environment(self.root)
        self.results = []
        source_value = os.environ.get("LITAI_INSTALLED_MIGRATION_SOURCE")
        source = Path(source_value).absolute() if source_value else None
        if source is not None:
            require_safe_directory(source)
            self.assert_clean_source(source, "before")
            prefix = self.root / "prefix"
            self.run_command(
                "install",
                [
                    sys.executable,
                    "-I",
                    "-c",
                    journey.INSTALL,
                    str(source),
                    str(prefix),
                    str(self.root / "installation.json"),
                ],
                self.root,
            )
        else:
            prefix = Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        require_safe_directory(prefix)
        layout = HostInstallLayout.for_prefix(prefix)
        python = Path(layout.environment) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        launcher = Path(layout.launcher)
        probe = self.probe(python, "installed-distribution")
        self.assertEqual(
            probe["origin"]["git_revision"],
            os.environ["LITAI_INSTALLED_LAYOUT_REVISION"],
        )
        if source is None:
            self.assertEqual(
                probe["distribution_identity"],
                os.environ["LITAI_INSTALLED_LAYOUT_DISTRIBUTION"],
            )
        self.run_command(
            "installed-migration-import-closure",
            [str(python), "-I", "-c", MIGRATION_IMPORT_PROBE],
            self.root,
        )
        project = self.root / "legacy"
        project.mkdir()
        executable = "python3"
        (project / "app.py").write_text("def add(a, b):\n    return a + b\n")
        (project / "test_app.py").write_text(
            "import unittest\nfrom app import add\n"
            "class AddTests(unittest.TestCase):\n"
            "    def test_positive(self): self.assertEqual(add(2, 3), 5)\n"
            "    def test_negative(self): self.assertEqual(add(-3, 1), -2)\n"
        )
        (project / "Makefile").write_text(
            "build:\n\t" + executable + " -m py_compile app.py\n"
            "test:\n\t" + executable + " -m unittest -v test_app\n"
            "package:\n\t" + executable + " -m zipfile -c app.zip app.py\n"
        )
        (project / ".gitignore").write_text("__pycache__/\napp.zip\n")
        self.run_command(
            "legacy-fixture-initialize",
            [
                str(python),
                "-I",
                "-c",
                SETUP,
                str(project),
                str(self.root / "setup.json"),
            ],
            self.root,
        )
        for phase, argv in (
            ("git-init", ["git", "init", "-b", "main"]),
            ("git-add", ["git", "add", "."]),
            (
                "git-commit",
                [
                    "git",
                    "-c",
                    "user.name=Layout fixture",
                    "-c",
                    "user.email=layout@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    "commit",
                    "-m",
                    "Original legacy fixture",
                ],
            ),
        ):
            self.run_command(phase, argv, project)
        head = self.run_command(
            "git-head-before", ["git", "rev-parse", "HEAD"], project
        ).stdout
        index = (project / ".git/index").read_bytes()
        manifest = (project / "literate.project.json").read_bytes()
        implementation = project / "components/legacy-project-wrapper/implementation"
        require_safe_directory(implementation)
        source_before = adoption.InstalledNativeAdoptionJourney.snapshot(implementation)
        tree_before = adoption.InstalledNativeAdoptionJourney.snapshot(project)
        plan = self.cli(
            "migration-plan",
            launcher,
            "project",
            "layout",
            "plan",
            "--migration",
            "--project",
            str(project),
            cwd=self.root,
        )["result"]
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(project), tree_before
        )
        self.assertFalse((project / "litai").exists())
        self.assertEqual(
            {row["path"] for row in plan["blocked_references"]},
            {"docs/user/project-layout.md"},
        )
        selection = ("--rewrite-reference", "docs/user/project-layout.md")
        plan = self.cli(
            "migration-reviewed-plan",
            launcher,
            "project",
            "layout",
            "plan",
            "--migration",
            "--project",
            str(project),
            *selection,
            cwd=self.root,
        )["result"]
        self.assertTrue(plan["applicable"], plan.get("blocked_references"))
        identity = plan["plan_identity"]
        applied = self.cli(
            "migration-apply",
            launcher,
            "project",
            "layout",
            "apply",
            "--project",
            str(project),
            "--plan-identity",
            identity,
            "--acknowledge",
            *selection,
            cwd=self.root,
        )["result"]
        self.assertTrue(applied["applied"])
        self.assertFalse((project / "literate.project.json").exists())
        self.assertTrue((project / "litai/literate.project.json").is_file())
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(implementation),
            source_before,
        )
        recovered = self.cli(
            "migration-recover",
            launcher,
            "project",
            "layout",
            "recover",
            "--project",
            str(project),
            "--plan-identity",
            identity,
            "--acknowledge",
            cwd=self.root,
        )["result"]
        self.assertTrue(recovered["rolled_back"])
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(implementation),
            source_before,
        )
        self.assertEqual((project / "literate.project.json").read_bytes(), manifest)
        self.assertEqual((project / ".git/index").read_bytes(), index)
        self.assertEqual(
            self.run_command(
                "git-head-after", ["git", "rev-parse", "HEAD"], project
            ).stdout,
            head,
        )
        self.assertEqual(self.probe(python, "installed-distribution-after"), probe)
        if source is not None:
            self.assert_clean_source(source, "after")
        (self.root / "receipt.json").write_text(
            json.dumps(
                {
                    "schema": "literate-ai/installed-layout-migration-observation@1",
                    "installed_distribution": probe,
                    "plan_identity": identity,
                    "index_sha256": hashlib.sha256(index).hexdigest(),
                    "retained_source_tree": source_before,
                    "commands": self.results,
                    "scope": (
                        "Installed public legacy metadata migration/recovery on real "
                        "initializer producers with explicit legacy fixture mode; "
                        "not historical-wheel upgrade or full authority/platform "
                        "qualification."
                    ),
                    "release_qualification": False,
                },
                indent=2,
            )
            + "\n"
        )

    def probe(self, python, phase):
        return json.loads(
            self.run_command(
                phase,
                [str(python), "-I", "-c", journey.PROBE],
                self.root,
            ).stdout
        )

    def assert_clean_source(self, source, phase):
        head = (
            self.run_command(
                f"source-head-{phase}", ["git", "rev-parse", "HEAD"], source
            )
            .stdout.decode()
            .strip()
        )
        self.assertEqual(head, os.environ["LITAI_INSTALLED_LAYOUT_REVISION"])
        self.assertFalse(
            self.run_command(
                f"source-clean-{phase}",
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                source,
            ).stdout
        )
