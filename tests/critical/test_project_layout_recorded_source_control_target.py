"""Actual renewed wrapper target remains current across control-only closure.

Historical conversion execution remains a fixture seam. This exercises source
owners and native files, not installed or supported-platform qualification.
"""

from __future__ import annotations

import os
import shutil
import unittest

from literate_ai.adapters import project_layout_framework_finalization as finalization
from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters import project_layout_framework_source_controls as controls
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_recorded_source_controls as recovery
from tests.critical import test_project_layout_recorded_target as support


@unittest.skipUnless(
    os.name == "posix", "actual POSIX controls; Windows remains required"
)
class RecordedSourceControlTargetTests(unittest.TestCase):
    def test_real_renewed_target_reprepares_after_control_closure_and_rolls_back(self):
        helper = support.RecordedTargetJourneyTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, selected, endpoint = helper.fixture()
        original = dict(selected.original_contents)
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.apply_framework_authority(selected, public["plan_identity"])
        native = {
            path: (project.root / path).stat().st_ino
            for path in endpoint.coordination_paths
        }
        source = project.root / endpoint.source_root
        implementation = source / "implementation/main.py"
        original_nodes = source.stat().st_ino, implementation.stat().st_ino
        alternate = project.root / "local-flavor-fixture/alternate"
        shutil.copytree(project.root / "litai/flavors/legacy-project-shim", alternate)
        flavor = alternate / "flavor.md"
        text = flavor.read_text()
        self.assertIn('name: "build-legacy-shim"', text)
        flavor.write_text(
            text.replace(
                'name: "build-legacy-shim"', 'name: "build-legacy-shim-alternate"', 1
            ).replace("../../skills/", "../../litai/skills/")
        )
        spec = alternate / "openspec/spec.md"
        spec.write_bytes(
            spec.read_bytes()
            + b"\nThe alternate keeps retained implementation native.\n"
        )
        authored = flavor.read_bytes(), spec.read_bytes()
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = helper.prepare(project, endpoint, alternate=True)
            result = renewal.renew_framework_component(
                endpoint,
                ProjectConfigurationStore(project.root).read(),
                prepared=prepared,
                layout_lease=current_layout_lease(project.root),
                plan_identity=public["plan_identity"],
            )
            self.assertTrue(result["writes"])
        journal, intent = framework._decode(project.root, public["plan_identity"])
        history = (journal / "intent.json").read_bytes()
        # Each finalization obtains a new Root lease and prepares the actual
        # selected normal producer again; no old prepared object is passed in.
        for _restart in range(2):
            with ProjectConfigurationStore.layout_lock(project.root):
                result = finalization.finalize_framework_components(
                    project.root, public["plan_identity"]
                )
            self.assertTrue(result["components_finalized"])
            self.assertFalse(result["full_containment"])
            self.assertFalse(result["qualification"])
            self.assertEqual(len(result["normal_producers"]), 1)
            self.assertTrue(result["normal_producers"][0]["current"])
        ((_, _, rows),) = controls.records(project.root, journal, intent)
        self.assertTrue(all(archived for _, _, archived in rows))
        for coordinate, actual, _ in rows:
            self.assertEqual(actual.stat().st_ino, native[coordinate])
        self.assertEqual((journal / "intent.json").read_bytes(), history)
        helper = recovery.RecordedSourceControlTests("runTest")
        helper.recover(project, public, original, native)
        self.assertEqual(
            (source.stat().st_ino, implementation.stat().st_ino), original_nodes
        )
        self.assertEqual((flavor.read_bytes(), spec.read_bytes()), authored)
