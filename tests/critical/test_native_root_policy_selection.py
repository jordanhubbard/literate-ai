"""Explicit project policy selection; no runtime or native qualification."""

from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.contracts.projects import (
    MINIMUM_PROJECT_REBUILD_PHASES,
    ProjectDefinition,
    ProjectLifecycleDriver,
    ProjectSourceIntelligencePolicy,
    SourceIntelligenceArtifactPublication,
    SourceIntelligenceMode,
    SourceIntelligenceStage,
    StandardProjectLifecycleDriver,
)


def _project():
    return ProjectDefinition(
        project_id="run-policy-fixture",
        version="1.0.0",
        profile="canonical",
        agent_skill="SKILL.md",
        component_roots=("components",),
        flavor_roots=("flavors",),
        skill_roots=("skills",),
        workflow_roots=("workflows",),
        routing_roots=("routing",),
        documentation_roots=("docs",),
        source_intelligence=ProjectSourceIntelligencePolicy(
            provider_id="none",
            command=None,
            minimum_version=None,
            artifact_path=None,
            stages=tuple(
                (stage, SourceIntelligenceMode.OFF) for stage in SourceIntelligenceStage
            ),
            artifact_publication=SourceIntelligenceArtifactPublication.METADATA_ONLY,
        ),
        lifecycle_driver=StandardProjectLifecycleDriver(
            canonical_identity({"wheel": 1}), canonical_identity({"policy": 1})
        ),
    )


class NativeRootPolicySelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        resources = []
        for version in ("v1", "v2"):
            for path in sorted((root / "schemas" / version).glob("*.schema.json")):
                document = json.loads(path.read_text())
                resources.append((document["$id"], Resource.from_contents(document)))
        cls.registry = Registry().with_resources(resources).crawl()

    def validate(self, wire):
        Draft202012Validator(
            {"$ref": ProjectDefinition.SCHEMA}, registry=self.registry
        ).validate(wire)

    def test_absent_policy_preserves_pre_extension_identity_and_wire(self):
        # Captured from the same fixture on unchanged projects.py before adding
        # this optional field. An accidental default/null changes this identity.
        project = _project()
        self.assertEqual(
            project.identity.uri,
            "sha256:fe1364c91e06806dfd530eef1c316aebe353204ad9ce8ba7968c8cc910f686e5",
        )
        wire = project.to_dict()
        self.assertNotIn("native_root_run_policy", wire)
        restored = ProjectDefinition.from_dict(wire)
        self.assertIsNone(restored.native_root_run_policy)
        self.assertEqual(
            canonical_json_bytes(restored.to_dict()), canonical_json_bytes(wire)
        )
        self.assertEqual(restored.identity, project.identity)
        self.validate(wire)

    def test_present_policy_changes_project_authority_without_changing_driver(self):
        original = _project()
        selected = replace(
            original, native_root_run_policy=NativeRootRunPolicy(1800, 3)
        )
        self.assertNotEqual(selected.identity, original.identity)
        self.assertIs(selected.lifecycle_driver, original.lifecycle_driver)
        self.assertEqual(
            selected.lifecycle_driver.to_dict(), original.lifecycle_driver.to_dict()
        )
        self.assertEqual(ProjectDefinition.from_dict(selected.to_dict()), selected)
        self.validate(selected.to_dict())

    def test_published_resource_is_explicit_closed_policy_without_absent_fallback(self):
        resource = files("literate_ai.standard_policies").joinpath(
            "native-root-run-v1.json"
        )
        wire = json.loads(resource.read_text(encoding="utf-8"))
        self.assertEqual(
            wire,
            {
                "schema": NativeRootRunPolicy.SCHEMA,
                "max_duration_seconds": 1800,
                "candidate_limit": 3,
            },
        )
        policy = NativeRootRunPolicy.from_dict(wire)
        self.assertEqual(policy.to_dict(), wire)
        self.validate(replace(_project(), native_root_run_policy=policy).to_dict())
        self.assertIsNone(
            ProjectDefinition.from_dict(_project().to_dict()).native_root_run_policy
        )

    def test_explicit_longer_policy_is_distinct_from_the_shipped_selection(self):
        selected = replace(
            _project(), native_root_run_policy=NativeRootRunPolicy(3600, 3)
        )
        restored = ProjectDefinition.from_dict(selected.to_dict())
        self.assertEqual(restored.native_root_run_policy.max_duration_seconds, 3600)
        self.validate(selected.to_dict())
        shipped = replace(
            _project(), native_root_run_policy=NativeRootRunPolicy(1800, 3)
        )
        self.assertNotEqual(selected.identity, shipped.identity)

    def test_invalid_closed_policy_refuses_in_contract_and_project_schema(self):
        original = replace(
            _project(), native_root_run_policy=NativeRootRunPolicy(1800, 3)
        ).to_dict()
        policy = original["native_root_run_policy"]
        malformed = [
            None,
            {},
            policy | {"schema": "literate-ai/native-root-run-policy@0"},
            policy | {"unreviewed": True},
            {key: value for key, value in policy.items() if key != "candidate_limit"},
        ]
        malformed.extend(
            policy | {"max_duration_seconds": value}
            for value in (True, 0, -1, 86401, "1800", 1.5)
        )
        malformed.extend(
            policy | {"candidate_limit": value} for value in (True, 1, 2, 4, "3")
        )
        for changed in malformed:
            with self.subTest(changed=changed):
                wire = original | {"native_root_run_policy": changed}
                with self.assertRaises(ValueError):
                    ProjectDefinition.from_dict(wire)
                with self.assertRaises(ValidationError):
                    self.validate(wire)

    def test_unbound_external_and_minimal_catalog_scopes_refuse(self):
        selected = replace(
            _project(), native_root_run_policy=NativeRootRunPolicy(1800, 3)
        ).to_dict()
        external = ProjectLifecycleDriver(
            driver_id="fixture",
            version="1.0.0",
            implementation_paths=("scripts/driver.py",),
            implementation_identity=canonical_identity({"external": 1}),
            argv=(
                "python",
                "scripts/driver.py",
                "{allow_host_execution}",
                "{candidate_receipt}",
                "{lifecycle_request_identity}",
                "{project_revision_identity}",
                "{project}",
                "{runtime_root}",
                "{specification}",
            ),
            environment_keys=(),
            phases=MINIMUM_PROJECT_REBUILD_PHASES,
            specification_scope="project",
        )
        unbound = copy.deepcopy(selected)
        del unbound["lifecycle_driver"]
        for wire in (
            unbound,
            selected | {"lifecycle_driver": external.to_dict()},
            selected | {"component_roots": []},
        ):
            with self.subTest(wire=wire):
                legacy = {
                    key: value
                    for key, value in wire.items()
                    if key != "native_root_run_policy"
                }
                self.assertEqual(ProjectDefinition.from_dict(legacy).to_dict(), legacy)
                self.validate(legacy)
                with self.assertRaises(ValueError):
                    ProjectDefinition.from_dict(wire)
                with self.assertRaises(ValidationError):
                    self.validate(wire)

    def test_direct_construction_requires_typed_policy(self):
        for value in ({"max_duration_seconds": 1800, "candidate_limit": 3}, True, 1800):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    replace(_project(), native_root_run_policy=value)


if __name__ == "__main__":
    unittest.main()
