"""Whole public retained packaging uses authored intent and real native custody."""

import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import literate_ai
from literate_ai.adapters.component_lock_application import (
    current_project_component_locks,
)
from literate_ai.adapters.standard_lifecycle_binding import (
    InstalledFrameworkDistribution,
    InstalledFrameworkDistributionMember,
    resolve_standard_project_lifecycle_driver,
)
from literate_ai.cli import main
from literate_ai.contracts import (
    ProjectTestReceiptPolicy,
    StandardProjectLifecycleDriver,
    load_current_standard_lifecycle_policy,
)
from literate_ai.contracts.executable_components.packages import PackageResult
from literate_ai.contracts.flavors import FlavorAxis
from literate_ai.contracts.retained_project_package import RetainedProjectPackageResult
from literate_ai.projects import load_project
from literate_ai.storage.cas import FileSystemCAS
from literate_ai.version import DISTRIBUTION_VERSION
from tests.critical.test_retained_promotion_public_readonly import snapshot
from tests.support.fixtures_public_retained_promotion import (
    author_public_retained_project,
)


@unittest.skipUnless(os.name != "nt" and shutil.which("cc"), "native POSIX C required")
class RetainedPackagePublicTests(unittest.TestCase):
    def test_public_package_retains_exact_payload_and_refuses_stale_source(self):
        # Editable/source suites must explicitly supply framework observations,
        # as in the existing public promotion fixture. Installed runs use the
        # actual noneditable defaults. Neither mode mocks project discovery,
        # command execution, live admission or archive verification.
        library = Path(literate_ai.__file__).resolve()
        repository = Path(__file__).resolve().parents[2]
        observations = {}
        binding_context = nullcontext()
        if library.is_relative_to(repository / "src"):
            content = library.read_bytes()
            distribution = InstalledFrameworkDistribution(
                "literate-ai",
                DISTRIBUTION_VERSION,
                (
                    InstalledFrameworkDistributionMember(
                        "literate_ai/__init__.py",
                        len(content),
                        "sha256:" + hashlib.sha256(content).hexdigest(),
                    ),
                ),
            )
            policy = load_current_standard_lifecycle_policy()
            driver = StandardProjectLifecycleDriver(
                distribution.identity, policy.identity
            )
            observations = {
                "driver": driver,
                "receipt": ProjectTestReceiptPolicy(
                    policy.policy_id,
                    policy.policy_version,
                    driver.identity,
                    policy.required_evidence_kinds,
                    policy.minimum_test_count,
                ),
            }
            binding_context = patch(
                "literate_ai.cli.rebuild.resolve_standard_project_lifecycle_driver",
                lambda value: resolve_standard_project_lifecycle_driver(
                    value, distribution_observer=lambda: distribution
                ),
            )
        with tempfile.TemporaryDirectory(prefix="retained zip public ") as temporary:
            root = Path(temporary).resolve()
            with (
                binding_context,
                patch.dict(
                    os.environ,
                    {
                        "LITAI_CONFIG_DIR": str(root / "operator"),
                        "LITAI_STATE_DIR": str(root / "state"),
                    },
                ),
            ):

                def invoke(arguments):
                    output, errors = io.StringIO(), io.StringIO()
                    status = main(["--json", *arguments], stdout=output, stderr=errors)
                    return status, json.loads(output.getvalue() or errors.getvalue())

                project, _policy = author_public_retained_project(
                    root, invoke, package_zip=True, **observations
                )
                selected = []
                for lock in current_project_component_locks(load_project(project)):
                    node = next(
                        n
                        for n in lock.nodes
                        if n.revision.identity == lock.root_revision
                    )
                    if any(
                        v.value == "zip"
                        for slot in node.target_flavor_selection.slots
                        if slot.slot.axis is FlavorAxis.PACKAGING
                        for v in slot.selected
                    ):
                        selected.append(lock)
                self.assertEqual(len(selected), 1)
                selectors = [
                    "--project",
                    str(project),
                    "--retained-project",
                    "manifest.json",
                    "--retained-project-profile",
                    "build/profile.json",
                    "--provider-lock",
                    selected[0].identity.uri,
                    "--build-dir",
                    str(root / "generated"),
                    "--obj-dir",
                    str(root / "objects"),
                ]
                before = snapshot(project)
                status, envelope = invoke(
                    [
                        "package",
                        "retained-project",
                        *selectors,
                        "--retained-project-plan",
                    ]
                )
                self.assertEqual(status, 0, envelope)
                self.assertEqual(snapshot(project), before)
                plan = envelope["result"]
                self.assertFalse(plan["package_qualified"])
                authorization = (
                    plan.get("plan_identity") or plan["authorization_identity"]
                )
                command = [
                    "package",
                    "retained-project",
                    *selectors,
                    "--authorize-retained-project",
                    authorization,
                    "--allow-host-execution",
                ]
                status, envelope = invoke(command)
                self.assertEqual(status, 0, envelope)
                result = envelope["result"]
                self.assertTrue(result["admitted"])
                self.assertTrue(result["package_qualified"])
                self.assertFalse(result["project_receipt_qualified"])
                self.assertFalse(result["release_authorized"])
                self.assertFalse(result["conversion_advanced"])
                self.assertEqual(result["source_authority"], "original")
                package = RetainedProjectPackageResult.from_dict(
                    result["retained_package"]["result"]
                )
                with self.assertRaises(ValueError):
                    PackageResult.from_dict(package.to_dict())
                store = FileSystemCAS(Path(result["custody_root"]), create=False)
                archive = store.get_bytes(package.artifacts[0].blob)
                with zipfile.ZipFile(io.BytesIO(archive)) as opened:
                    self.assertEqual(
                        opened.read("app.bin"), (project / "tools/runner").read_bytes()
                    )
                    self.assertEqual(
                        opened.read("docs.txt"),
                        b"Original native suite and independent byte-stream oracle.\n",
                    )
                    self.assertEqual(
                        json.loads(opened.read(".literate-ai/receipt.json")),
                        result["retained_receipt"],
                    )
                    self.assertTrue(
                        any(
                            n.startswith(".literate-ai/specifications/")
                            for n in opened.namelist()
                        )
                    )
                    self.assertNotIn("test-result.json", opened.namelist())
                evidence_before = sorted(
                    (root / "objects").rglob("command-diagnostics.json")
                )
                original = project / "original/runner.c"
                original.write_bytes(
                    original.read_bytes() + b"\n/* changed original source */\n"
                )
                status, rejected = invoke(command)
                self.assertNotEqual(status, 0, rejected)
                self.assertFalse(rejected["ok"])
                self.assertEqual(
                    sorted((root / "objects").rglob("command-diagnostics.json")),
                    evidence_before,
                )


if __name__ == "__main__":
    unittest.main()
