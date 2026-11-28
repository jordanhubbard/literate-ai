"""Real typed wrapper targets, normal selection/publication and exact rollback.

Original conversion execution and current distribution lookup remain explicit
fixture seams. These are not installed, native-build or platform attestations.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest
from unittest.mock import patch

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import component_locks
from literate_ai.adapters import project_layout_component_destination as destination
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_lock_application import update_component_lock
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.component_locks import ComponentLockStoreError
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_recorded_composition as support

TARGET = "legacy-shim"
FLAVOR = "+flavor://legacy-adoption/build-legacy-shim"
ALTERNATE = "+flavor://legacy-adoption/build-legacy-shim-alternate"


class RecordedTargetJourneyTests(unittest.TestCase):
    def fixture(self):
        helper = support.RecordedCompositionTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _resources, _retained = helper.fixture(without_imports=True)
        component = project.root / "components/legacy-project-wrapper"
        update_component_lock(
            component,
            target_name=TARGET,
            flavor_selectors=(FLAVOR,),
            flavor_roots=(project.root / "flavors",),
        )
        for args in (
            ("init", "-q"),
            ("add", "."),
            (
                "-c",
                "user.name=Layout Fixture",
                "-c",
                "user.email=layout@example.test",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "Original actual wrapper target",
            ),
        ):
            subprocess.run(
                ["git", *args], cwd=project.root, check=True, capture_output=True
            )
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        (endpoint,) = selected.component_endpoints
        return project, public, selected, endpoint

    def prepare(self, project, endpoint, *, alternate=False):
        return operations.prepare_component_lock(
            project.root / endpoint.destination_root,
            target=TARGET,
            flavors=(ALTERNATE,) if alternate else (FLAVOR,),
            flavor_roots=(
                project.root / "litai/flavors",
                project.root / "local-flavor-fixture",
            )
            if alternate
            else (project.root / "litai/flavors",),
            planner=FilesystemComponentLockPlanner(),
        )

    def test_actual_target_inventory_uses_normal_typed_lock_and_audit(self):
        project, public, selected, endpoint = self.fixture()
        self.assertEqual(endpoint.source_kind, "recorded-wrapper")
        self.assertEqual(endpoint.target_names, (TARGET,))
        self.assertEqual(len(endpoint.records), 2)
        self.assertIs(endpoint.recorded_source, selected.recorded_wrapper_source)
        for path, content in endpoint.original_contents.items():
            row = public["placements"][path]
            self.assertEqual(row["owner"], "original-component-producer")
            self.assertEqual(row["from"], row["to"])
            self.assertEqual((project.root / path).read_bytes(), content)
        self.assertEqual(
            {row["kind"] for row in endpoint.records.values()},
            {"ComponentLock", "ComponentResolutionAudit"},
        )

    def test_normal_destination_selection_and_real_renewal_restore_exact_history(self):
        project, public, selected, endpoint = self.fixture()
        original = dict(selected.original_contents)
        source_store = endpoint.original_lock_store
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.apply_framework_authority(selected, public["plan_identity"])
            prepared = self.prepare(project, endpoint)
            classified = destination.classify_framework_component_destination(
                endpoint,
                ProjectConfigurationStore(project.root).read(),
                prepared=prepared,
                layout_lease=current_layout_lease(project.root),
                plan_identity=public["plan_identity"],
            )
            self.assertIn(classified["state"], {"current", "renewal-required"})
            self.assertEqual(classified["source_kind"], "recorded-wrapper")
        with patch.object(
            component_locks,
            "exclusive_cache_lock",
            side_effect=AssertionError("retired source creating open"),
        ) as opener:
            with self.assertRaises(ComponentLockStoreError):
                with source_store.operation():
                    self.fail("retired source store entered normal operation")
        opener.assert_not_called()
        # A genuinely new local policy is authored AFTER migration. This is not
        # a rewrite of original source history or a synthesized selected target.
        alternate = project.root / "local-flavor-fixture/alternate"
        shutil.copytree(project.root / "litai/flavors/legacy-project-shim", alternate)
        flavor = alternate / "flavor.md"
        value = flavor.read_text()
        self.assertIn('name: "build-legacy-shim"', value)
        value = value.replace(
            'name: "build-legacy-shim"', 'name: "build-legacy-shim-alternate"', 1
        )
        value = value.replace("../../skills/", "../../litai/skills/")
        flavor.write_text(value)
        spec = alternate / "openspec/spec.md"
        spec.write_bytes(
            spec.read_bytes()
            + b"\nThe alternate local policy keeps retained implementation native.\n"
        )
        authored = flavor.read_bytes(), spec.read_bytes()
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = self.prepare(project, endpoint, alternate=True)
            classified = destination.classify_framework_component_destination(
                endpoint,
                ProjectConfigurationStore(project.root).read(),
                prepared=prepared,
                layout_lease=current_layout_lease(project.root),
                plan_identity=public["plan_identity"],
            )
            self.assertEqual(classified["state"], "renewal-required")
            result = renewal.renew_framework_component(
                endpoint,
                ProjectConfigurationStore(project.root).read(),
                prepared=prepared,
                layout_lease=current_layout_lease(project.root),
                plan_identity=public["plan_identity"],
            )
            self.assertTrue(result["current"])
            self.assertTrue(result["writes"])
            journal, intent = framework._decode(project.root, public["plan_identity"])
            for path, content in endpoint.original_contents.items():
                self.assertEqual(
                    (journal / "before" / intent["entries"][path]["slot"]).read_bytes(),
                    content,
                )
        for _repeat in range(2):
            with ProjectConfigurationStore.layout_lock(project.root):
                report = framework.recover_framework_authority(
                    project.root, public["plan_identity"]
                )
            self.assertTrue(report["rolled_back"])
        for path, content in original.items():
            self.assertEqual((project.root / path).read_bytes(), content)
        self.assertEqual((flavor.read_bytes(), spec.read_bytes()), authored)
