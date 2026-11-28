"""Whole public retained packaging uses authored intent and real native custody."""

import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.component_lock_application import (
    current_project_component_locks,
)
from literate_ai.cli import main
from literate_ai.contracts.executable_components.packages import PackageResult
from literate_ai.contracts.flavors import FlavorAxis
from literate_ai.contracts.retained_project_package import RetainedProjectPackageResult
from literate_ai.projects import load_project
from literate_ai.storage.cas import FileSystemCAS
from tests.critical.test_retained_receipt_promotion import snapshot
from tests.support.fixtures_public_retained_promotion import (
    author_public_retained_project,
)


@unittest.skipUnless(os.name != "nt" and shutil.which("cc"), "native POSIX C required")
class RetainedPackagePublicTests(unittest.TestCase):
    def test_public_package_retains_exact_payload_and_refuses_stale_source(self):
        with tempfile.TemporaryDirectory(prefix="retained zip public ") as temporary:
            root = Path(temporary).resolve()
            with patch.dict(
                os.environ,
                {
                    "LITAI_CONFIG_DIR": str(root / "operator"),
                    "LITAI_STATE_DIR": str(root / "state"),
                },
            ):

                def invoke(arguments):
                    output, errors = io.StringIO(), io.StringIO()
                    status = main(["--json", *arguments], stdout=output, stderr=errors)
                    return status, json.loads(output.getvalue() or errors.getvalue())

                project, _policy = author_public_retained_project(
                    root, invoke, package_zip=True
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
