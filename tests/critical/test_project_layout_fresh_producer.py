"""Fresh Python process, real normal preparation and native migration journal.

Original conversion execution is modeled by the established fixture. The child
imports production code anew; it receives no source owner, lease or transition.
This is source-process evidence, not installed/platform release qualification.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_finalization as finalization
from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_lock_planning import ComponentLockPlanningError
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_producer_renewal as initialized
from tests.critical import test_project_layout_recorded_target as support

CHILD = """
import json,sys
from pathlib import Path
from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.projects import ProjectConfigurationStore
root=Path(sys.argv[1]); plan=sys.argv[2]; request=json.loads(sys.argv[3])
with ProjectConfigurationStore.layout_lock(root):
    prepared=operations.prepare_component_lock(
        root/request['component'], target=request['target'],
        flavors=tuple(request['flavors']),
        flavor_roots=tuple(root/path for path in request['roots']),
        planner=FilesystemComponentLockPlanner(),
    )
    result=renewal.renew_placed_framework_component(
        root,plan,prepared=prepared,layout_lease=current_layout_lease(root)
    )
print(json.dumps(result))
"""


class FreshProducerTests(unittest.TestCase):
    def fixture(self):
        helper = support.RecordedTargetJourneyTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, selected, endpoint = helper.fixture()
        original = dict(selected.original_contents)
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.apply_framework_authority(selected, public["plan_identity"])
        return helper, project, public, endpoint, original

    def child(
        self, project, public, endpoint, *, alternate=False, flavors=None, roots=None
    ):
        environment = dict(os.environ)
        repository = Path(__file__).parents[2]
        environment["PYTHONPATH"] = str(repository / "src")
        request = {
            "component": endpoint.destination_root,
            "target": endpoint.target_names[0],
            "flavors": list(flavors)
            if flavors is not None
            else [support.ALTERNATE if alternate else support.FLAVOR],
            "roots": list(roots)
            if roots is not None
            else (
                ["litai/flavors", "local-flavor-fixture"]
                if alternate
                else ["litai/flavors"]
            ),
        }
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                CHILD,
                str(project.root),
                public["plan_identity"],
                json.dumps(request),
            ],
            cwd=repository,
            env=environment,
            text=True,
            capture_output=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def recover(self, project, public, original):
        for _repeat in range(2):
            with ProjectConfigurationStore.layout_lock(project.root):
                self.assertTrue(
                    framework.recover_framework_authority(
                        project.root, public["plan_identity"]
                    )["rolled_back"]
                )
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)

    def alternate(self, project):
        alternate = project.root / "local-flavor-fixture/alternate"
        shutil.copytree(project.root / "litai/flavors/legacy-project-shim", alternate)
        flavor, spec = alternate / "flavor.md", alternate / "openspec/spec.md"
        value = flavor.read_text()
        self.assertIn('name: "build-legacy-shim"', value)
        flavor.write_text(
            value.replace(
                'name: "build-legacy-shim"', 'name: "build-legacy-shim-alternate"', 1
            ).replace("../../skills/", "../../litai/skills/")
        )
        spec.write_bytes(
            spec.read_bytes() + b"\nRetained implementation stays native.\n"
        )
        return flavor, spec

    def test_fresh_process_current_pair_preserves_placed_inodes_without_journal(self):
        helper = initialized.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, endpoint, original = helper.fixture(alternate=False)
        paths = [project.root / ("litai/" + path) for path in endpoint.records]
        native = [path.stat().st_ino for path in paths]
        for _restart in range(2):
            result = self.child(
                project, public, endpoint, flavors=(), roots=("flavors",)
            )
            self.assertTrue(result["current"])
            self.assertFalse(result["writes"])
            self.assertIsNone(result["journal"])
        self.assertEqual([path.stat().st_ino for path in paths], native)
        self.recover(project, public, original)

    @unittest.skipUnless(os.name == "posix", "POSIX closure; Windows remains required")
    def test_fresh_process_real_renewal_finalization_and_exact_rollback(self):
        _helper, project, public, endpoint, original = self.fixture()
        flavor, spec = self.alternate(project)
        authored = flavor.read_bytes(), spec.read_bytes()
        implementation = project.root / endpoint.source_root / "implementation/main.py"
        inode = implementation.stat().st_ino
        journal, intent = framework._decode(project.root, public["plan_identity"])
        history = (journal / "intent.json").read_bytes()
        result = self.child(project, public, endpoint, alternate=True)
        self.assertTrue(result["current"])
        self.assertTrue(result["writes"])
        for _restart in range(2):
            with ProjectConfigurationStore.layout_lock(project.root):
                report = finalization.finalize_framework_components(
                    project.root, public["plan_identity"]
                )
            self.assertTrue(report["components_finalized"])
            self.assertTrue(report["normal_producers"][0]["current"])
            self.assertFalse(report["qualification"])
        self.assertEqual((journal / "intent.json").read_bytes(), history)
        for path, payload in endpoint.original_contents.items():
            self.assertEqual(
                (journal / "before" / intent["entries"][path]["slot"]).read_bytes(),
                payload,
            )
        self.recover(project, public, original)
        self.assertEqual(implementation.stat().st_ino, inode)
        self.assertEqual((flavor.read_bytes(), spec.read_bytes()), authored)

    def test_copied_preparation_and_new_git_boundary_refuse_before_intent(self):
        helper, project, public, endpoint, original = self.fixture()
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = helper.prepare(project, endpoint)
            with self.assertRaises(ComponentLockPlanningError):
                renewal.renew_placed_framework_component(
                    project.root,
                    public["plan_identity"],
                    prepared=copy.copy(prepared),
                    layout_lease=current_layout_lease(project.root),
                )
            calls = []
            with patch.object(
                ProjectConfigurationStore, "read", lambda *_a: calls.append(True)
            ):
                with self.assertRaises(ProjectLayoutPlanError):
                    renewal.renew_placed_framework_component(
                        project.root,
                        public["plan_identity"],
                        prepared=prepared,
                        layout_lease=current_layout_lease(project.root),
                    )
            self.assertEqual(calls, [])
            marker = prepared.component_root / ".git"
            marker.mkdir()
            try:
                with self.assertRaises(ProjectLayoutPlanError):
                    renewal.renew_placed_framework_component(
                        project.root,
                        public["plan_identity"],
                        prepared=prepared,
                        layout_lease=current_layout_lease(project.root),
                    )
            finally:
                marker.rmdir()  # only this test's exact synthetic Git boundary
        self.assertEqual(
            list((project.root / "litai/.literate").glob("framework-renewal-*")), []
        )
        self.recover(project, public, original)
