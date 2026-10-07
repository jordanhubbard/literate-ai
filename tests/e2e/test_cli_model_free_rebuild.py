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

    def test_rebuild_routes_lifecycle_actions_through_an_admitted_worker(self):
        """The CLI admits a private command worker and dispatches actions to it."""
        from datetime import UTC, datetime

        from literate_ai import worker_storage_probe
        from literate_ai.contracts.execution_dispatch import (
            LIFECYCLE_ACTION_WIRE_PROTOCOL,
            ExecutionWorker,
            ExecutionWorkerCatalog,
            ExecutionWorkerEnvironment,
            ExecutionWorkerKind,
        )
        from literate_ai.contracts.identity import canonical_json_bytes
        from literate_ai.contracts.worker_capabilities import (
            NvidiaProbeStatus,
            WorkerHardwareObservation,
            WorkerHardwareObservationCatalog,
        )
        from literate_ai.storage import FileSystemCAS
        from tests.support import fixtures_test_cli_worker_health as health_fixture

        private = self.root / "private"
        cas = private / "source-cas"
        workspace = private / "worker-jobs"
        workspace.mkdir(parents=True)
        FileSystemCAS(cas)  # the operator initializes the shared CAS layout
        log = private / "receiver.log"
        receiver = (
            "import runpy,sys;"
            f"open({str(log)!r},'a').write(' '.join(sys.argv[1:])+'\\n');"
            "sys.argv[0]='action_worker';"
            "runpy.run_module('literate_ai.action_worker',run_name='__main__')"
        )
        worker = ExecutionWorker(
            "cli-worker",
            ExecutionWorkerKind.COMMAND,
            command=(
                sys.executable,
                "-I",
                "-c",
                receiver,
                "--cas",
                str(cas),
                "--workspace",
                str(workspace),
            ),
            environment=(
                ExecutionWorkerEnvironment(
                    "LITAI_ACTION_WORKER_IDENTITY", "CLI_WORKER_IDENTITY", True
                ),
            ),
            action_protocol=LIFECYCLE_ACTION_WIRE_PROTOCOL,
        )
        catalog = private / "workers.json"
        catalog.write_bytes(
            canonical_json_bytes(ExecutionWorkerCatalog((worker,)).to_dict())
        )
        family = {"darwin": "macos", "linux": "linux"}[sys.platform]
        observations = private / "worker-observations.json"
        observations.write_bytes(
            canonical_json_bytes(
                WorkerHardwareObservationCatalog(
                    (
                        WorkerHardwareObservation(
                            "cli-worker",
                            datetime.now(UTC).isoformat(),
                            family,
                            family,
                            "1",
                            "arm64" if os.uname().machine == "arm64" else "x86_64",
                            os.cpu_count() or 1,
                            os.cpu_count() or 1,
                            16384,
                            (),
                            NvidiaProbeStatus.NOT_APPLICABLE,
                        ),
                    )
                ).to_dict()
            )
        )
        health = health_fixture.WorkerHealthCliTests()
        health.setUp()
        self.addCleanup(health.doCleanups)
        health.config["worker_id"] = "cli-worker"
        health.config["health_command"] = {
            "schema": "literate-ai/private-worker-storage-command@1",
            "command": [sys.executable, "-B", worker_storage_probe.__file__],
            "environment": [],
        }
        health.write_config()
        configuration = private / "action-execution.json"
        configuration.write_bytes(
            canonical_json_bytes(
                {
                    "schema": "literate-ai/private-action-execution@1",
                    "source_cas_root": str(cas),
                    "source_handoff": "filesystem-cas",
                    "duration_seconds": 600,
                    "maximum_hardware_age_seconds": 600,
                    "health_configurations": {"cli-worker": str(health.config_file)},
                    "result_sources": {"cli-worker": {"kind": "shared-cas"}},
                }
            )
        )
        self.environment |= {
            "LITAI_ACTION_EXECUTION_CONFIG": str(configuration),
            "LITAI_WORKER_CONFIG": str(catalog),
            "LITAI_WORKER_OBSERVATIONS": str(observations),
            "CLI_WORKER_IDENTITY": worker.identity.uri,
        }
        status, envelope = self.rebuild()
        self.assertEqual(status, 0, envelope)
        self.assertTrue(envelope["result"]["passed"], envelope)
        invocations = log.read_text("utf-8").splitlines()
        self.assertTrue(any("--describe" in line for line in invocations))
        self.assertTrue(
            any("--describe" not in line for line in invocations), invocations
        )


if __name__ == "__main__":
    unittest.main()
