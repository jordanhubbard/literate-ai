"""Real source closure refusal/empty-producer and legacy format controls."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_finalization as finalization
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_component_journey as journey
from tests.critical import test_project_layout_framework_producer_renewal as support


@unittest.skipUnless(
    os.name == "posix", "POSIX closure tests; Windows qualification separate"
)
class FrameworkSourceClosureControls(unittest.TestCase):
    def fixture(self):
        helper = support.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper, *helper.fixture(alternate=False)

    def test_actual_empty_producer_inventory_needs_no_invented_target(self):
        helper = journey.FrameworkComponentJourneyTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, selected = helper.fixture(with_lock=False)
        (endpoint,) = selected.component_endpoints
        self.assertEqual(endpoint.target_names, ())
        self.assertEqual(dict(endpoint.records), {})
        original = dict(selected.original_contents)
        with ProjectConfigurationStore.layout_lock(project.root):
            try:
                framework.apply_framework_authority(selected, public["plan_identity"])
            except ProjectLayoutPlanError:
                fresh, observed = ingress.read_existing_framework_authority(
                    project.root
                )
                try:
                    print(
                        "COORDINATE_DIFF",
                        {
                            key: (
                                selected.coordinate_map.get(key),
                                observed.coordinate_map.get(key),
                            )
                            for key in set(selected.coordinate_map)
                            | set(observed.coordinate_map)
                            if selected.coordinate_map.get(key)
                            != observed.coordinate_map.get(key)
                        },
                        flush=True,
                    )
                    print(
                        "CONTROL_PATHS",
                        [
                            list(row.coordination_paths)
                            for row in selected.component_endpoints
                        ],
                        [
                            list(row.coordination_paths)
                            for row in observed.component_endpoints
                        ],
                        flush=True,
                    )
                    print(
                        json.dumps(
                            {
                                key: {"before": public[key], "after": fresh[key]}
                                for key in public
                                if public[key] != fresh[key]
                            },
                            indent=2,
                        ),
                        flush=True,
                    )
                finally:
                    ingress.close_observed_framework_selection(observed)
                raise
            result = finalization.finalize_framework_components(
                project.root, public["plan_identity"]
            )
            self.assertEqual(result["normal_producers"], [])
            self.assertTrue(result["components_finalized"])
            self.assertFalse((project.root / endpoint.source_root).exists())
            framework.recover_framework_authority(project.root, public["plan_identity"])
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)

    def test_actual_v1_writer_format_still_recovers_without_source_closure(self):
        helper = journey.FrameworkComponentJourneyTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, selected = helper.fixture()
        original = dict(selected.original_contents)
        # Explicit format seam: stage/write the actual v1 four-directory intent
        # BEFORE native moves; no sealed v2 intent, history or payload is edited.
        with ProjectConfigurationStore.layout_lock(project.root):
            with (
                patch.object(framework, "_SCHEMA", framework._JOURNAL_V1),
                patch.object(
                    framework,
                    "_DIRECTORIES",
                    framework._journal_directories(framework._JOURNAL_V1),
                ),
            ):
                framework.apply_framework_authority(selected, public["plan_identity"])
            journal, intent = framework._decode(project.root, public["plan_identity"])
            self.assertEqual(intent["schema"], framework._JOURNAL_V1)
            self.assertFalse((journal / "retired-source").exists())
            with self.assertRaises(ProjectLayoutPlanError):
                finalization.finalize_framework_components(
                    project.root, public["plan_identity"]
                )
            framework.recover_framework_authority(project.root, public["plan_identity"])
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)

    def test_unrelated_private_residual_is_refused_without_open(self):
        helper, project, public, endpoint, original = self.fixture()
        private = project.root / endpoint.source_root / ".env"
        private.write_bytes(b"synthetic private fixture; not a real credential\n")
        real_open, calls = os.open, []

        def guarded(path, *args, **kwargs):
            if isinstance(path, (str, os.PathLike)) and str(path) == str(private):
                calls.append(True)
                raise AssertionError("private residual payload opened")
            return real_open(path, *args, **kwargs)

        with ProjectConfigurationStore.layout_lock(project.root):
            with patch.object(os, "open", guarded):
                with self.assertRaisesRegex(ProjectLayoutPlanError, "unrelated data"):
                    finalization.finalize_framework_components(
                        project.root, public["plan_identity"]
                    )
        self.assertEqual(calls, [])
        self.assertTrue(private.exists())
        private.unlink()  # test-owned synthetic leaf only
        helper.recover(project, public, original)

    def test_replaced_project_reader_refuses_before_invocation(self):
        helper, project, public, _endpoint, original = self.fixture()
        calls = []
        with ProjectConfigurationStore.layout_lock(project.root):
            with patch.object(
                ProjectConfigurationStore, "read", lambda *_a: calls.append(True)
            ):
                with self.assertRaises(ProjectLayoutPlanError):
                    finalization.finalize_framework_components(
                        project.root, public["plan_identity"]
                    )
        self.assertEqual(calls, [])
        helper.recover(project, public, original)
