"""`litai rebuild` of a fresh starter project with only the model provider faked.

The fake `claude` executable stands at the model-provider boundary and writes the
source a model would. Initialization, locking, source admission, Make build,
generated tests, execution, independent acceptance and receipt commit are real.
An editable checkout cannot pin a Standard lifecycle distribution, so the test
supplies a synthetic distribution through the same seams installed wheels use.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.project_initialization import (
    FilesystemProjectInitializationAdapter,
)
from literate_ai.adapters.standard_lifecycle_binding import (
    InstalledFrameworkDistribution,
    InstalledFrameworkDistributionMember,
    resolve_standard_project_lifecycle_driver,
)
from literate_ai.cli import main
from literate_ai.contracts import (
    ProjectInitializationOrigin,
    ProjectTestReceiptPolicy,
    RepositoryParentSelection,
    StandardProjectLifecycleDriver,
    load_current_standard_lifecycle_policy,
)

FAKE_CLAUDE = Path(__file__).resolve().parents[1] / "support" / "fake_claude.py"


def install_fake_claude(directory: Path) -> Path:
    """Copy the fake as a regular executable named `claude`; never a symlink."""
    path = directory / "claude"
    path.write_text(
        f"#!{sys.executable}\n" + FAKE_CLAUDE.read_text("utf-8"), encoding="utf-8"
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@unittest.skipUnless(
    shutil.which("make") and os.name == "posix",
    "the starter Make build needs GNU make on a POSIX host",
)
class ModelFreeRebuildTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.distribution = InstalledFrameworkDistribution(
            "literate-ai",
            "1.1.0",
            (
                InstalledFrameworkDistributionMember(
                    "literate_ai/__init__.py", 1, "sha256:" + "a" * 64
                ),
            ),
        )
        policy = load_current_standard_lifecycle_policy()
        driver = StandardProjectLifecycleDriver(
            self.distribution.identity, policy.identity
        )
        receipt = ProjectTestReceiptPolicy(
            policy.policy_id,
            policy.policy_version,
            driver.identity,
            policy.required_evidence_kinds,
            policy.minimum_test_count,
        )
        self.project = self.root / "project"
        self.project.mkdir()
        FilesystemProjectInitializationAdapter(
            standard_binding_provider=lambda: (driver, receipt),
            initialization_origin_provider=lambda: ProjectInitializationOrigin(
                repository_url="https://github.com/jordanhubbard/literate-ai.git",
                git_revision="a" * 40,
                distribution_name="literate-ai",
                distribution_version="1.1.0",
            ),
        ).initialize(
            self.project,
            parent_selection=RepositoryParentSelection.root(),
            source_intelligence_provider="none",
        )
        tools = self.root / "tools"
        tools.mkdir()
        install_fake_claude(tools)
        self.environment = {
            "CODING_CLI": "claude",
            "PATH": str(tools) + os.pathsep + os.environ.get("PATH", ""),
            "BUILD_DIR": str(self.root / "build"),
            "OBJ_DIR": str(self.root / "obj"),
        }

    def rebuild(self, *extra: str) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        with (
            patch.dict(os.environ, self.environment),
            patch(
                "literate_ai.cli.rebuild.resolve_standard_project_lifecycle_driver",
                lambda driver: resolve_standard_project_lifecycle_driver(
                    driver, distribution_observer=lambda: self.distribution
                ),
            ),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(output),
        ):
            status = main(
                [
                    "--json",
                    "rebuild",
                    "samples/hello-component",
                    "--project",
                    str(self.project),
                    "--allow-host-execution",
                    "--update-receipt",
                    *extra,
                ]
            )
        return status, json.loads(output.getvalue())

    def test_starter_rebuilds_and_commits_a_receipt_without_a_model(self):
        status, envelope = self.rebuild()
        self.assertEqual(status, 0, envelope)
        self.assertTrue(envelope["ok"], envelope)
        result = envelope["result"]
        self.assertTrue(result["passed"], result)
        self.assertTrue(result["receipt_committed"], result)


if __name__ == "__main__":
    unittest.main()
