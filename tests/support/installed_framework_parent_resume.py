"""Resume the hash-bound failed parent fixture through installed public commands.

The original journey remains unchanged. No initializer, source reconstruction,
producer renewal or authority repin is used by this continuation.
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
from tests.support import installed_framework_parent_journey as original
from tests.support import installed_project_layout_journey as journey
from tests.support.installed_framework_maintenance_resume import file_state


class InstalledFrameworkParentResume(unittest.TestCase):
    def test_original_local_parent_transition_and_inherited_update(self):
        binding_path = Path(os.environ["LITAI_PARENT_FAILURE_BINDING"]).absolute()
        binding_bytes = file_state(binding_path)[0]
        binding_sha = hashlib.sha256(binding_bytes).hexdigest()
        self.assertEqual(binding_sha, os.environ["LITAI_PARENT_FAILURE_BINDING_SHA256"])
        binding = json.loads(binding_bytes)
        fixture = Path(binding["fixture"])
        child, parent = Path(binding["child"]), Path(binding["parent"])
        for path in (fixture, child, parent):
            require_safe_directory(path)
        self.assertEqual(child.parent, fixture)
        self.assertEqual(parent.parent, fixture)
        for name, identity in binding["phase_sha256"].items():
            self.assertEqual(
                hashlib.sha256(file_state(fixture / name)[0]).hexdigest(), identity
            )
        self.assertEqual(
            hashlib.sha256(
                file_state(fixture / "new-parent-plan.stderr")[0]
            ).hexdigest(),
            binding["failure_stderr_sha256"],
        )
        self.assertEqual(
            original.adoption.InstalledNativeAdoptionJourney.snapshot(child),
            binding["post_failure_source_snapshot"],
        )
        index = file_state(child / ".git/index")[0]
        self.assertEqual(hashlib.sha256(index).hexdigest(), binding["git_index_sha256"])
        paths = [child / "litai/.literate" / name for name in binding["lineage_sha256"]]
        for path in paths:
            self.assertEqual(
                hashlib.sha256(file_state(path)[0]).hexdigest(),
                binding["lineage_sha256"][path.name],
            )

        helper = original.InstalledFrameworkParentJourney(
            "test_real_root_update_then_local_parent_plan_apply_and_update"
        )
        output = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(output)
        helper.root = Path(tempfile.mkdtemp(prefix="ipr-", dir=output))
        print("retained installed parent continuation:", helper.root, flush=True)
        helper.environment = journey.isolated_layout_environment(helper.root)
        helper.results = []
        helper.child = child
        helper.source = binding["post_failure_source_snapshot"]
        helper.index = index
        layout = HostInstallLayout.for_prefix(
            Path(os.environ["LITAI_INSTALLED_LAYOUT_PREFIX"]).absolute()
        )
        helper.launcher = Path(layout.launcher)
        python = Path(layout.environment) / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        passed = False
        try:
            distribution = helper.probe(python, "resume-distribution-before")
            self.assertEqual(
                distribution["origin"]["git_revision"],
                os.environ["LITAI_INSTALLED_LAYOUT_REVISION"],
            )
            self.assertEqual(
                distribution["distribution_identity"],
                os.environ["LITAI_INSTALLED_LAYOUT_DISTRIBUTION"],
            )
            for name, selected, expected in (
                ("child", child, binding["child_head"].strip()),
                ("parent", parent, binding["parent_revision"]),
            ):
                self.assertEqual(
                    helper.run_command(
                        f"resume-{name}-head-before",
                        ["git", "--no-optional-locks", "rev-parse", "HEAD"],
                        selected,
                    )
                    .stdout.decode()
                    .strip(),
                    expected,
                )
            reference = f"{parent.as_uri()}#{binding['parent_revision']}"
            before = {path: file_state(path) for path in paths}
            plans = []
            for label, selected in (
                ("root", child),
                ("descendant", child / "litai/components"),
            ):
                plan = helper.child_cli(
                    f"resume-parent-plan-{label}",
                    "reparent",
                    reference,
                    "--project",
                    str(selected),
                )
                self.assertTrue(plan["changed"], plan)
                plans.append(plan["identity"])
                for path, state in before.items():
                    self.assertEqual(file_state(path), state)
            self.assertEqual(plans[0], plans[1])
            applied = helper.child_cli(
                "resume-parent-apply",
                "reparent",
                reference,
                "--project",
                str(child),
                "--apply",
            )
            self.assertEqual(applied["identity"], plans[0])
            self.assertEqual(applied["applied"]["state"], "applied")
            self.assertTrue(applied["applied"]["changed"])
            self.assertTrue(applied["applied"]["authority_review_required"])
            self.assertNotEqual(
                {path: file_state(path)[0] for path in paths},
                {path: state[0] for path, state in before.items()},
            )
            plan = helper.child_cli(
                "resume-inherited-update-plan",
                "update",
                str(child / "litai/components"),
            )
            self.assertEqual(plan["mode"], "read-only-plan")
            updated = helper.child_cli(
                "resume-inherited-update-apply",
                "update",
                str(child),
                "--apply",
                "--adopt-added",
            )
            self.assertEqual(updated["mode"], "applied")
            self.assertEqual(
                helper.run_command(
                    "resume-child-head-after",
                    ["git", "--no-optional-locks", "rev-parse", "HEAD"],
                    child,
                ).stdout.decode(),
                binding["child_head"],
            )
            self.assertEqual(
                helper.probe(python, "resume-distribution-after"), distribution
            )
            passed = True
        finally:
            self.assertEqual(file_state(binding_path)[0], binding_bytes)
            helper.assert_source_current()
            with (helper.root / "parent-resume-receipt.json").open("x") as stream:
                json.dump(
                    {
                        "record_version": 1,
                        "original_binding_sha256": binding_sha,
                        "original_fixture": str(fixture),
                        "passed": passed,
                        "commands": helper.results,
                        "scope": (
                            "Original failed local-parent fixture continuation; "
                            "changed-parent/inherited update only. Migrated-parent, "
                            "native/platform/full-containment/release acceptance "
                            "remain separate."
                        ),
                        "release_qualification": False,
                    },
                    stream,
                    indent=2,
                )
                stream.write("\n")
