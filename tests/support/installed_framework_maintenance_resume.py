"""Qualify maintenance on the exact retained, finalized installed fixture.

Bind the original failed receipt, install an immutable SDK subject, then use its
public launcher. Do not reconstruct the fixture, apply updates, renew reviews or
repin drivers/receipts. This is scoped maintenance-plan evidence, not release
or complete containment qualification.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.user_paths import HostInstallLayout
from tests.support import installed_layout_migration_journey as metadata
from tests.support import installed_native_adoption_journey as adoption
from tests.support import installed_project_layout_journey as journey


def file_state(path):
    require_safe_directory(path.parent)
    node = path.lstat()
    if not stat.S_ISREG(node.st_mode):
        raise AssertionError(f"Expected original regular authority file: {path}")
    return (
        path.read_bytes(),
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_mtime_ns,
        node.st_ctime_ns,
    )


class InstalledFrameworkMaintenanceResume(unittest.TestCase):
    run_command = journey.InstalledProjectLayoutJourney.run_command
    cli = journey.InstalledProjectLayoutJourney.cli
    probe = metadata.InstalledLayoutMigrationJourney.probe
    assert_clean_source = metadata.InstalledLayoutMigrationJourney.assert_clean_source

    def test_exact_finalized_fixture_accepts_root_and_descendant_maintenance(self):
        receipt_path = Path(os.environ["LITAI_MAINTENANCE_RECEIPT"]).absolute()
        encoded = file_state(receipt_path)[0]
        receipt_sha = hashlib.sha256(encoded).hexdigest()
        self.assertEqual(receipt_sha, os.environ["LITAI_MAINTENANCE_RECEIPT_SHA256"])
        original = json.loads(encoded)
        self.assertEqual(original["terminal_exit"], 2)
        self.assertFalse(original["source_drift"])
        self.assertTrue(original["fully_finalized_before_maintenance"])
        self.assertEqual(len(original["independent_outcomes"]), 4)
        for row in original["independent_outcomes"].values():
            self.assertEqual(row["execution"]["returncode"], 2)
        fixture = Path(original["fixture"])
        self.assertTrue(fixture.is_absolute())
        require_safe_directory(fixture)
        project = fixture / "legacy"
        require_safe_directory(project)
        plan = json.loads((fixture / "framework-plan.stdout").read_bytes())["result"]
        node = project.lstat()
        self.assertEqual([node.st_dev, node.st_ino, node.st_mode], plan["root_node"])
        finalized = json.loads(
            (fixture / "framework-producer-finalize-1.stdout").read_bytes()
        )["result"]
        self.assertTrue(finalized["components_finalized"])
        self.assertFalse(
            (project / "components/legacy-project-wrapper/component.md").exists()
        )

        parent = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(parent)
        self.root = Path(tempfile.mkdtemp(prefix="iu-", dir=parent))
        print("retained original maintenance observation:", self.root, flush=True)
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

        applied = json.loads((fixture / "framework-apply.stdout").read_bytes())[
            "result"
        ]
        journal = Path(applied["journal"])
        self.assertTrue(journal.is_relative_to(project / "litai/.literate"))
        require_safe_directory(journal)
        selected = {
            "litai/literate.project.json",
            "litai/.literate/initialization-baseline.json",
            "litai/.literate/initialization-origin.json",
            "litai/.literate/update-bases.json",
            "litai/.literate/repository-parent.json",
            "litai/.literate/repository-lineage.json",
            *plan["delegate_edits"],
        }
        authority = {}
        for relative in selected:
            parsed = PurePosixPath(relative)
            self.assertFalse(parsed.is_absolute())
            self.assertNotIn("..", parsed.parts)
            authority[project / relative] = file_state(project / relative)
        authority[journal / "intent.json"] = file_state(journal / "intent.json")
        implementation = project / "components/legacy-project-wrapper/implementation"
        require_safe_directory(implementation)
        snapshot = adoption.InstalledNativeAdoptionJourney.snapshot
        before = snapshot(implementation)
        index = file_state(project / ".git/index")[0]
        head = self.run_command(
            "git-head-before",
            ["git", "--no-optional-locks", "rev-parse", "HEAD"],
            project,
        ).stdout
        self.assertEqual(head, (fixture / "framework-head-before.stdout").read_bytes())
        identities = {}
        for coordinate, selected_project in (
            ("root", project),
            ("descendant", project / "litai/components"),
        ):
            for operation in ("reparent", "update"):
                arguments = (
                    ("reparent", "none", "--project", str(selected_project))
                    if operation == "reparent"
                    else ("update", str(selected_project))
                )
                result = self.cli(
                    f"maintenance-{operation}-{coordinate}",
                    launcher,
                    *arguments,
                    cwd=self.root,
                )["result"]
                self.assertEqual(result["mode"], "read-only-plan")
                if operation == "reparent":
                    self.assertFalse(result["changed"])
                else:
                    self.assertFalse(result["source_moved"])
                identity = (
                    result["identity"]
                    if operation == "reparent"
                    else result["plan_identity"]
                )
                self.assertEqual(identity, identities.setdefault(operation, identity))
                self.assertEqual(snapshot(implementation), before)
                self.assertEqual(file_state(project / ".git/index")[0], index)
                for path, expected in authority.items():
                    self.assertEqual(file_state(path), expected, path)
        self.assertEqual(
            self.run_command(
                "git-head-after",
                ["git", "--no-optional-locks", "rev-parse", "HEAD"],
                project,
            ).stdout,
            head,
        )
        self.assertEqual(self.probe(python, "installed-distribution-after"), probe)
        if source is not None:
            self.assert_clean_source(source, "after")
        (self.root / "receipt.json").write_text(
            json.dumps(
                {
                    "schema": (
                        "literate-ai/installed-original-maintenance-observation@1"
                    ),
                    "original_receipt_sha256": receipt_sha,
                    "original_subject": original["subject"],
                    "fixture": str(fixture),
                    "plan_identity": plan["plan_identity"],
                    "installed_distribution": probe,
                    "maintenance_identities": identities,
                    "original_intent_sha256": hashlib.sha256(
                        authority[journal / "intent.json"][0]
                    ).hexdigest(),
                    "source": before,
                    "index_sha256": hashlib.sha256(index).hexdigest(),
                    "authority_file_sha256": {
                        str(path.relative_to(project)): hashlib.sha256(
                            value[0]
                        ).hexdigest()
                        for path, value in authority.items()
                    },
                    "commands": self.results,
                    "scope": (
                        "Exact finalized original fixture: installed root/descendant "
                        "maintenance plans; source, Git and original authority/history "
                        "preserved. Not update/reparent application, full containment, "
                        "other-platform, native build or release qualification."
                    ),
                    "release_qualification": False,
                },
                indent=2,
            )
            + "\n"
        )
