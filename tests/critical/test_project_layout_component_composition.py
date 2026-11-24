"""Original normal producers through default planning; no effects/qualification.

Current distribution-origin lookup is the established explicit fixture seam.
Actual template/defaults/lock/audit and read owners remain production paths.
"""

from __future__ import annotations

import copy
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_component_transition as transition
from literate_ai.adapters import project_layout_finite_creations as finite
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_resources as resource_module
from literate_ai.adapters import project_layout_framework_selection as selector
from literate_ai.adapters.project_layout_framework_plan import (
    decode_framework_authority_plan,
)
from literate_ai.adapters.project_layout_initialized_component_capture import (
    capture_initialized_framework_component_transitions,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.contracts import canonical_identity
from tests.critical import test_project_layout_initialized_component_capture as support


class InitializedComponentCompositionTests(unittest.TestCase):
    def fixture(self, *, with_lock=True, contained=False):
        helper = support.InitializedComponentCaptureTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper.fixture(with_lock=with_lock, contained=contained)

    def observe(self, project, resources):
        observation = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        result = ingress.observe_existing_framework_authority(
            observation, resources=resources
        )
        self.addCleanup(ingress.close_observed_framework_selection, result[1])
        return result

    def capture(self, project, resources, proof):
        return capture_initialized_framework_component_transitions(
            project.snapshot,
            project.context,
            resources=resources,
            source_proofs=(proof,),
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
            source_held=(),
        )

    def select(self, project, resources, proof, endpoints=()):
        return selector.select_existing_framework_authority(
            project.snapshot,
            project.context,
            project.inventory,
            resources=resources,
            source_proofs=(proof,),
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
            component_endpoints=endpoints,
        )

    def rehash(self, plan):
        plan["plan_identity"] = canonical_identity(
            {key: value for key, value in plan.items() if key != "plan_identity"}
        ).uri
        return plan

    def test_default_observer_joins_actual_initialized_typed_producers(self):
        project, resources, _proof = self.fixture()
        before = dict(project.contents)
        public, selected = self.observe(project, resources)
        (endpoint,) = selected.component_endpoints
        self.assertEqual(endpoint.source_kind, "initialized")
        self.assertIsNone(endpoint.imported_source)
        self.assertTrue(
            any(
                proof is endpoint.initialized_source for proof in selected.source_proofs
            )
        )
        self.assertEqual(len(endpoint.records), 2)
        for path, content in endpoint.original_contents.items():
            row = public["placements"][path]
            self.assertEqual(row["owner"], "original-component-producer")
            self.assertEqual(row["from"], row["to"])
            self.assertEqual(row["destination"], "litai/" + path)
            self.assertEqual(selected.rewritten_contents[row["destination"]], content)
        self.assertFalse(
            any(
                row["owner"] == "component-producer"
                for row in public["required_owners"]
            )
        )
        for path, content in before.items():
            self.assertEqual((project.root / path).read_bytes(), content)
        ingress.require_current_observed_framework_selection(selected)

    def test_original_read_entrypoint_reaches_component_capture(self):
        project, _resources, _proof = self.fixture()
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertEqual(len(selected.component_endpoints), 1)
        self.assertEqual(
            {row["owner"] for row in public["placements"].values()},
            {"initialized-file", "original-component-producer"},
        )
        ingress.require_current_observed_framework_selection(selected)

    def test_empty_inventory_has_no_invented_target_or_record(self):
        project, resources, _proof = self.fixture(with_lock=False)
        public, selected = self.observe(project, resources)
        (endpoint,) = selected.component_endpoints
        self.assertEqual(endpoint.target_names, ())
        self.assertEqual(dict(endpoint.records), {})
        self.assertTrue(
            all(
                row["owner"] != "original-component-producer"
                for row in public["placements"].values()
            )
        )
        self.assertIn(endpoint.initialized_source.source_path, public["placements"])

    def test_typed_records_are_not_fabricated_initialization_rows(self):
        project, resources, _proof = self.fixture()
        _public, selected = self.observe(project, resources)
        (endpoint,) = selected.component_endpoints
        baseline = json.loads(
            selected.rewritten_contents["litai/.literate/initialization-baseline.json"]
        )
        original = json.loads(
            project.contents["litai/.literate/initialization-baseline.json"]
        )
        self.assertEqual(len(baseline["files"]), len(original["files"]))
        paths = {row["path"] for row in baseline["files"]}
        self.assertFalse(paths & {"litai/" + path for path in endpoint.records})
        self.assertFalse(set(endpoint.coordination_paths) & set(selected.placements))
        definition = json.loads(selected.rewritten_contents[project.manifest])
        self.assertEqual(definition["component_roots"], ["litai/samples"])

    def test_missing_original_transition_remains_explicit_blocker(self):
        project, resources, proof = self.fixture()
        public, selected = self.select(project, resources, proof)
        self.assertEqual(selected.component_endpoints, ())
        self.assertFalse(public["applicable"])
        self.assertTrue(
            any(
                row["owner"] == "component-producer"
                for row in public["required_owners"]
            )
        )

    def test_copied_or_foreign_original_transition_refuses(self):
        project, resources, proof = self.fixture()
        (endpoint,) = self.capture(project, resources, proof)
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, resources, proof, (copy.copy(endpoint),))
        other, other_resources, other_proof = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(other, other_resources, other_proof, (endpoint,))

    def test_pure_component_projection_does_not_reopen_source(self):
        project, resources, proof = self.fixture()
        endpoints = self.capture(project, resources, proof)
        with (
            patch.object(Path, "open", side_effect=AssertionError("pure file read")),
            patch.object(Path, "stat", side_effect=AssertionError("pure file stat")),
            patch.object(Path, "lstat", side_effect=AssertionError("pure file lstat")),
            patch.object(os, "open", side_effect=AssertionError("pure native open")),
        ):
            public, selected = self.select(project, resources, proof, endpoints)
        self.assertIs(selected.component_endpoints, endpoints)
        self.assertEqual(
            len(
                [
                    row
                    for row in public["placements"].values()
                    if row["owner"] == "original-component-producer"
                ]
            ),
            2,
        )

    def test_duplicate_original_transition_refuses(self):
        project, resources, proof = self.fixture()
        (endpoint,) = self.capture(project, resources, proof)
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, resources, proof, (endpoint, endpoint))

    def test_decoded_producer_plan_does_not_restore_original_admission(self):
        project, resources, _proof = self.fixture()
        public, _selected = self.observe(project, resources)
        decoded = decode_framework_authority_plan(public)
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_original_observed_framework_selection(decoded)
        with self.assertRaises(ProjectLayoutPlanError):
            transition.require_original_component_transition(
                next(iter(decoded["placements"].values()))
            )

    def test_codec_refuses_mixed_component_producer_variants(self):
        project, resources, _proof = self.fixture()
        public, selected = self.observe(project, resources)
        path = next(iter(selected.component_endpoints[0].records))
        for field, value in (
            ("projection", "finite-template"),
            ("logical", "elsewhere/record.json"),
            ("destination", "elsewhere/record.json"),
            ("to", "sha256:" + "f" * 64),
            ("source_proof", None),
            ("resource_identity", "sha256:" + "f" * 64),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(public)
                changed["placements"][path][field] = value
                with self.assertRaises((ProjectLayoutPlanError, ValueError)):
                    decode_framework_authority_plan(self.rehash(changed))

    def test_component_tuple_is_sealed_by_original_observation(self):
        project, resources, _proof = self.fixture()
        _public, selected = self.observe(project, resources)
        old = selected.component_endpoints
        object.__setattr__(selected, "component_endpoints", ())
        try:
            with self.assertRaises(ProjectLayoutPlanError):
                ingress.require_original_observed_framework_selection(selected)
        finally:
            object.__setattr__(selected, "component_endpoints", old)
        ingress.require_current_observed_framework_selection(selected)

    def test_actual_record_drift_expires_observation(self):
        project, resources, _proof = self.fixture()
        _public, selected = self.observe(project, resources)
        path = next(iter(selected.component_endpoints[0].records))
        (project.root / path).write_bytes(project.contents[path] + b"\n")
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_current_observed_framework_selection(selected)

    def test_original_producer_destination_alias_is_not_overwritten(self):
        project, resources, proof = self.fixture()
        target = (
            "litai/"
            + proof.source_path.removesuffix("/component.md")
            + "/Component.lock.json"
        )
        project.write(target, b"foreign target\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.observe(project, resources)
        self.assertEqual((project.root / target).read_bytes(), b"foreign target\n")

    def test_origin_callback_cannot_replace_destination_failure_dispatch(self):
        project, resources, _proof = self.fixture()
        _public, selected = self.observe(project, resources)
        calls = []
        original = finite._fail

        def origin():
            finite._fail = lambda *_args: calls.append(True)
            return resources.origin

        try:
            with patch.object(resource_module, "_read_current_origin", origin):
                with self.assertRaises(ProjectLayoutPlanError):
                    ingress.require_current_observed_framework_selection(selected)
        finally:
            finite._fail = original
        self.assertEqual(calls, [])

    def test_late_producer_destination_alias_expires_original_observation(self):
        project, resources, proof = self.fixture()
        _public, selected = self.observe(project, resources)
        target = (
            "litai/"
            + proof.source_path.removesuffix("/component.md")
            + "/Component.lock.json"
        )
        project.write(target, b"late unrelated target\n")
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_current_observed_framework_selection(selected)
        self.assertEqual(
            (project.root / target).read_bytes(), b"late unrelated target\n"
        )

    def test_occupied_producer_destination_is_rejected_without_payload_open(self):
        project, resources, proof = self.fixture()
        relative = (
            "litai/"
            + proof.source_path.removesuffix("/component.md")
            + "/component.lock.json"
        )
        project.write(relative, b"unrelated existing payload\n")
        target = project.root / relative
        original = os.open
        calls = []

        def guarded(path, *args, **kwargs):
            if isinstance(path, (str, os.PathLike)) and str(path) == str(target):
                calls.append(True)
                raise AssertionError("occupied target payload opened")
            return original(path, *args, **kwargs)

        with patch.object(os, "open", guarded):
            with self.assertRaises(ProjectLayoutPlanError):
                self.observe(project, resources)
        self.assertEqual(calls, [])
        self.assertEqual(target.read_bytes(), b"unrelated existing payload\n")

    def test_default_observer_does_not_open_held_private_component_child(self):
        project, resources, proof = self.fixture()
        secret = project.root / proof.source_path.removesuffix("/component.md") / ".env"
        secret.write_bytes(b"modeled private fixture, no real credential\n")
        original = os.open
        calls = []

        def guarded(path, *args, **kwargs):
            if isinstance(path, (str, os.PathLike)) and str(path) == str(secret):
                calls.append(True)
                raise AssertionError("held private child opened")
            return original(path, *args, **kwargs)

        with patch.object(os, "open", guarded):
            with self.assertRaises(ProjectLayoutPlanError):
                self.observe(project, resources)
        self.assertEqual(calls, [])
