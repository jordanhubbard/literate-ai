"""Actual initialized Component placement; current origin/init lineage modeled.

No installed acquisition, build, native-platform or release qualification claim.
"""

from __future__ import annotations

import copy
import subprocess
import unittest
from unittest.mock import patch

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_component_destination as destination
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_transaction as transaction
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_initialized_component_capture as support
from tests.support.fixtures_test_component_lock_planning import _flavor_variant


class FrameworkComponentJourneyTests(unittest.TestCase):
    def fixture(self, *, alternate=False, with_lock=True):
        helper = support.InitializedComponentCaptureTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _owner, _proof = helper.fixture(with_lock=with_lock)
        if alternate:
            # A real separately authored local Flavor selects a genuinely new
            # normal producer result; no stale record or check result is forged.
            _flavor_variant(
                project.root / "flavors/lang-python",
                project.root / "flavors/lang-python-alternate",
                name="lang-python-alternate",
                value="python",
            )
        # Application documentation referenced by the original framework Skill.
        # These are application-owned fixture files, not invented framework proof.
        project.write("docs/user/bootstrap.md", b"# Application bootstrap notes\n")
        project.write("docs/README.md", b"# Application documentation\n")
        for arguments in (
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
                "Original initialized Component fixture",
            ),
        ):
            subprocess.run(
                ["git", "-C", str(project.root), *arguments],
                check=True,
                capture_output=True,
            )
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        return project, public, selected

    def test_actual_initialized_component_and_producer_pair_roundtrip(self):
        project, public, selected = self.fixture()
        (endpoint,) = selected.component_endpoints
        self.assertEqual(len(endpoint.records), 2)
        original = dict(selected.original_contents)
        with ProjectConfigurationStore.layout_lock(project.root):
            result = transaction.apply_framework_authority(
                selected, public["plan_identity"]
            )
        self.assertTrue(result["applied"])
        for path, payload in endpoint.original_contents.items():
            self.assertEqual((project.root / ("litai/" + path)).read_bytes(), payload)
            self.assertFalse((project.root / path).exists())
        with ProjectConfigurationStore.layout_lock(project.root):
            restored = transaction.recover_framework_authority(
                project.root, public["plan_identity"]
            )
        self.assertTrue(restored["rolled_back"])
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)

    def test_original_transition_unchanged_pair_is_current_without_write(self):
        self.normal_journey(alternate=False)

    def test_original_transition_changed_flavor_needs_normal_renewal(self):
        self.normal_journey(alternate=True)

    def normal_journey(self, *, alternate):
        project, public, selected = self.fixture(alternate=alternate)
        (endpoint,) = selected.component_endpoints
        old_records = dict(endpoint.original_contents)
        with ProjectConfigurationStore.layout_lock(project.root):
            transaction.apply_framework_authority(selected, public["plan_identity"])
            expected = ProjectConfigurationStore(project.root).read()
            planner = FilesystemComponentLockPlanner()
            flavors = (
                ("+flavor://literate-ai/lang-python-alternate",) if alternate else ()
            )
            roots = (project.root / "flavors",)
            prepared = operations.prepare_component_lock(
                project.root / endpoint.destination_root,
                target="macos-host",
                flavors=flavors,
                flavor_roots=roots,
                planner=planner,
            )

            def classify(transition=endpoint):
                return destination.classify_framework_component_destination(
                    transition,
                    expected,
                    prepared=prepared,
                    layout_lease=current_layout_lease(project.root),
                    plan_identity=public["plan_identity"],
                )

            with self.assertRaises(ProjectLayoutPlanError):
                classify(copy.copy(endpoint))
            calls = []
            with patch.object(
                transaction, "_decode", lambda *_args: calls.append(True)
            ):
                with self.assertRaises(ProjectLayoutPlanError):
                    classify()
            self.assertEqual(calls, [])
            state = classify()
            self.assertEqual(
                state["state"], "renewal-required" if alternate else "current"
            )
            self.assertFalse(state["writes"])
            self.assertFalse(state["finalized"])
            if alternate:
                report, status = operations.operate_component_lock(
                    prepared,
                    target="macos-host",
                    flavors=flavors,
                    flavor_roots=roots,
                    planner=planner,
                    check=False,
                    difference=False,
                )
                self.assertEqual(status, 0)
                self.assertEqual(report["mode"], "update")
            state = classify()
            self.assertEqual(state["state"], "current")
            self.assertFalse(state["finalized"])
            # Old source provenance remains the same exact retained native bytes;
            # normal renewal never rebases those records to current evidence.
            journal, intent = transaction._decode(project.root, public["plan_identity"])
            for path, payload in old_records.items():
                archived = journal / "before" / intent["entries"][path]["slot"]
                self.assertEqual(archived.read_bytes(), payload)

            original_coordinate = project.root / next(iter(old_records))
            self.assertFalse(original_coordinate.exists())
            unrelated = b"Unrelated newly created original-coordinate data\n"
            original_coordinate.write_bytes(unrelated)
            with self.assertRaises(ProjectLayoutPlanError):
                classify()
            self.assertEqual(original_coordinate.read_bytes(), unrelated)
