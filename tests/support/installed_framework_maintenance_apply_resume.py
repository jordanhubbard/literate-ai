"""Resume maintenance on the hash-bound original failed finalized fixture.

No migration, producer renewal, fixture reconstruction or authority repinning is
performed. A separately installed immutable repair subject owns the public calls.
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
from tests.support import installed_framework_maintenance_apply_journey as application
from tests.support import installed_native_adoption_journey as adoption
from tests.support import installed_project_layout_journey as journey
from tests.support.installed_framework_maintenance_resume import file_state


class InstalledFrameworkMaintenanceApplyResume(unittest.TestCase):
    def test_original_failed_fixture_accepts_installed_maintenance_application(self):
        receipt = Path(os.environ["LITAI_MAINTENANCE_APPLICATION_RECEIPT"]).absolute()
        original_receipt = file_state(receipt)
        encoded = original_receipt[0]
        identity = hashlib.sha256(encoded).hexdigest()
        self.assertEqual(
            identity, os.environ["LITAI_MAINTENANCE_APPLICATION_RECEIPT_SHA256"]
        )
        original = json.loads(encoded)
        self.assertFalse(original["passed"])
        failures = [row for row in original["commands"] if row["returncode"] != 0]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["phase"], "maintenance-update-apply")
        self.assertEqual(failures[0]["returncode"], 2)
        fixture = Path(original["fixture"])
        self.assertTrue(fixture.is_absolute())
        require_safe_directory(fixture)
        self.assertEqual(receipt.parent, fixture)
        project = fixture / "legacy"
        require_safe_directory(project)

        def phase_bytes(label, suffix="stdout"):
            row = next(row for row in original["commands"] if row["phase"] == label)
            content = file_state(fixture / f"{label}.{suffix}")[0]
            self.assertEqual(
                hashlib.sha256(content).hexdigest(), row[f"{suffix}_sha256"]
            )
            return content

        old_error = json.loads(
            phase_bytes("maintenance-update-apply", "stderr").splitlines()[-1]
        )
        self.assertEqual(old_error["error"]["code"], "cli.invalid_input")
        plan = json.loads(phase_bytes("maintenance-framework-plan"))["result"]
        self.assertEqual(plan["plan_identity"], original["framework_plan_identity"])
        node = project.lstat()
        self.assertEqual([node.st_dev, node.st_ino, node.st_mode], plan["root_node"])
        applied = json.loads(phase_bytes("maintenance-framework-apply"))["result"]
        journal = Path(applied["journal"])
        self.assertTrue(journal.is_relative_to(project / "litai/.literate"))
        require_safe_directory(journal)
        self.assertEqual(
            hashlib.sha256(file_state(journal / "intent.json")[0]).hexdigest(),
            original["migration_intent_sha256"],
        )
        implementation = project / "components/legacy-project-wrapper/implementation"
        require_safe_directory(implementation)
        self.assertEqual(
            adoption.InstalledNativeAdoptionJourney.snapshot(implementation),
            original["original_source"],
        )
        index = file_state(project / ".git/index")[0]
        self.assertEqual(hashlib.sha256(index).hexdigest(), original["index_sha256"])
        head = phase_bytes("maintenance-head-before")
        update = json.loads(phase_bytes("maintenance-update-plan-root"))["result"]

        helper = application.InstalledFrameworkMaintenanceJourney(
            "test_update_and_unchanged_reparent_apply_after_finalization"
        )
        parent = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(parent)
        helper.root = Path(tempfile.mkdtemp(prefix="ir-", dir=parent))
        print("retained installed maintenance continuation:", helper.root, flush=True)
        helper.environment = journey.isolated_layout_environment(helper.root)
        helper.results = []
        layout = HostInstallLayout.for_prefix(
            Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        )
        python = Path(layout.environment) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        distribution = helper.probe(python, "resume-distribution-before")
        self.assertEqual(
            distribution["origin"]["git_revision"],
            os.environ["LITAI_INSTALLED_LAYOUT_REVISION"],
        )
        self.assertEqual(
            distribution["distribution_identity"],
            os.environ["LITAI_INSTALLED_LAYOUT_DISTRIBUTION"],
        )
        self.assertEqual(
            helper.run_command(
                "resume-head-before",
                ["git", "--no-optional-locks", "rev-parse", "HEAD"],
                project,
            ).stdout,
            head,
        )
        try:
            helper.exercise_maintenance(
                project=project,
                launcher=Path(layout.launcher),
                python=python,
                distribution=distribution,
                implementation=implementation,
                original_source=original["original_source"],
                index=index,
                head=head,
                journal=journal,
                identity=plan["plan_identity"],
                original_update_framework=update["framework"],
                label_prefix="resume",
                receipt_name="resume-receipt.json",
            )
        finally:
            self.assertEqual(file_state(receipt), original_receipt)
            output = helper.root / "resume-receipt.json"
            with (helper.root / "resume-binding.json").open("x") as stream:
                json.dump(
                    {
                        "original_receipt_sha256": identity,
                        "original_fixture": str(fixture),
                        "original_distribution": original["installed_distribution"],
                        "repair_distribution": distribution,
                        "continuation_receipt_sha256": (
                            hashlib.sha256(output.read_bytes()).hexdigest()
                            if output.is_file()
                            else None
                        ),
                        "scope": (
                            "Original failed fixture continuation with a separate "
                            "immutable repair; changed-parent and complete release "
                            "acceptance remain open."
                        ),
                        "release_qualification": False,
                    },
                    stream,
                    indent=2,
                )
