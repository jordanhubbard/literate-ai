"""Original seven-output default composition, with modeled historical execution.

Actual source/read owners, normal catalog/producer readers and native journal
moves remain production paths. These are not installed/native release evidence.
"""

from __future__ import annotations

import copy
import json
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from literate_ai.adapters import project_layout_component_transition as core
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_resources as resource_owner
from literate_ai.adapters import project_layout_framework_selection as selection
from literate_ai.adapters import project_layout_framework_transaction as transaction
from literate_ai.adapters import project_layout_recorded_wrapper_projection as projector
from literate_ai.adapters import project_layout_recorded_wrapper_source as source
from literate_ai.adapters import (
    project_layout_retained_source_observation as retained_owner,
)
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.project_layout_framework_plan import (
    decode_framework_authority_plan,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
    _git_state,
)
from literate_ai.adapters.retained_layout import resolve_structural_layout
from literate_ai.contracts import CatalogImportsFile, canonical_json_bytes
from literate_ai.projects import (
    ProjectConfigurationStore,
    serialize_project_configuration,
)
from tests.critical import test_project_layout_recorded_wrapper_source as support


class RecordedCompositionTests(unittest.TestCase):
    def fixture(self, *, without_imports=False):
        helper = support.RecordedWrapperSourceTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, resources, retained = helper.fixture()
        if without_imports:
            # This case starts without the separate inherited Skill in the
            # generic resource fixture. The mixed-catalog case remains below;
            # neither this setup nor wrapper ownership adopts that Skill.
            (project.root / "skills/demo/SKILL.md").unlink()
            (project.root / "skills/demo").rmdir()
            # The import-free project chooses an ACTUAL retained wrapper Skill;
            # it must not keep pointing at the removed sample imported Skill.
            project.definition = replace(
                project.definition,
                agent_skill="skills/specification-to-source/legacy-project-shim/SKILL.md",
            )
            project.write(
                project.manifest, serialize_project_configuration(project.definition)
            )
            project.imports = CatalogImportsFile(())
            project.write(
                "litai/.literate/imports.json",
                canonical_json_bytes(project.imports.to_dict()) + b"\n",
            )
            project.refresh()
            project.inventory["retained_implementation"] = (
                "components/legacy-project-wrapper/implementation"
            )
            project.rehash()
            observation = ProjectLayoutObservation(
                project.snapshot,
                project.context,
                project.inventory,
                project.observations,
                project.contents,
                project.bases,
            )
            resources = resource_owner.observe_original_framework_resources(observation)
            retained = retained_owner.observe_original_bounded_retained_source(
                observation, resources
            )
            self.addCleanup(
                retained_owner.close_original_bounded_retained_source, retained
            )
        return project, resources, retained

    def observe(self, project, resources):
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        result = ingress.observe_existing_framework_authority(
            observed, resources=resources
        )
        self.addCleanup(ingress.close_observed_framework_selection, result[1])
        return result

    def test_default_observer_composes_all_seven_original_outputs(self):
        project, resources, _retained = self.fixture()
        original = dict(project.contents)
        public, selected = self.observe(project, resources)
        wrapper = selected.recorded_wrapper_source
        self.assertIs(wrapper.resources, resources)
        self.assertIs(wrapper.snapshot, project.snapshot)
        (endpoint,) = selected.component_endpoints
        self.assertEqual(endpoint.source_kind, "recorded-wrapper")
        self.assertIs(endpoint.recorded_source, wrapper)
        self.assertIsNone(endpoint.initialized_source)
        self.assertIsNone(endpoint.imported_source)
        self.assertEqual(endpoint.target_names, ())
        self.assertFalse(
            any(
                row["owner"] == "component-producer"
                for row in public["required_owners"]
            )
        )
        for entry in wrapper.projection.entries:
            row = public["placements"][entry.original_coordinate]
            self.assertEqual(row["owner"], "recorded-converter-file")
            self.assertEqual(row["source_proof"], wrapper.identity)
            self.assertEqual(row["destination"], "litai/" + entry.logical)
            self.assertEqual(
                selected.rewritten_contents[row["destination"]], entry.original_bytes
            )
        implementation = "components/legacy-project-wrapper/implementation/main.py"
        self.assertNotIn(implementation, public["placements"])
        self.assertNotIn("litai/" + implementation, selected.rewritten_contents)
        self.assertEqual(decode_framework_authority_plan(public), public)
        schema = json.loads(
            (
                Path(__file__).parents[2]
                / "schemas/v2/project-layout-framework-authority.schema.json"
            ).read_bytes()
        )
        Draft202012Validator(schema).validate(public)
        changed = copy.deepcopy(public)
        changed["placements"]["litai.harness.mk"]["logical"] = ".env"
        changed.pop("plan_identity")
        from literate_ai.contracts import canonical_identity

        changed["plan_identity"] = canonical_identity(changed).uri
        with self.assertRaises(ProjectLayoutPlanError):
            decode_framework_authority_plan(changed)
        for path, content in original.items():
            self.assertEqual((project.root / path).read_bytes(), content)
        ingress.require_current_observed_framework_selection(selected)

    def test_missing_actual_component_owner_keeps_plan_blocked(self):
        project, resources, retained = self.fixture()
        wrapper = support.RecordedWrapperSourceTests.admit(
            self, project, resources, retained
        )
        public, selected = selection.select_existing_framework_authority(
            project.snapshot,
            project.context,
            project.inventory,
            resources=resources,
            source_proofs=(),
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
            protected_paths=frozenset(
                {"components/legacy-project-wrapper/implementation/main.py"}
            ),
            recorded_wrapper_source=wrapper,
        )
        self.assertFalse(public["applicable"])
        self.assertTrue(
            any(
                row["owner"] == "component-producer"
                for row in public["required_owners"]
            )
        )
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_original_observed_framework_selection(selected)

    def test_changed_any_seven_output_expires_original_default_observation(self):
        project, resources, _retained = self.fixture()
        _public, selected = self.observe(project, resources)
        project.write(
            "routing/legacy-adoption.json",
            project.contents["routing/legacy-adoption.json"] + b"\n",
        )
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_current_observed_framework_selection(selected)

    def test_closed_and_copied_selection_cannot_restore_wrapper_custody(self):
        project, resources, _retained = self.fixture()
        _public, selected = self.observe(project, resources)
        wrapper = selected.recorded_wrapper_source
        with self.assertRaises(ProjectLayoutPlanError):
            ingress.require_original_observed_framework_selection(copy.copy(selected))
        ingress.close_observed_framework_selection(selected)
        with self.assertRaises(ProjectLayoutPlanError):
            source.require_original_recorded_wrapper_source(wrapper)

    def test_real_default_placement_and_rollback_preserve_retained_source(self):
        project, _resources, _retained = self.fixture(without_imports=True)
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
                "Original recorded wrapper fixture",
            ),
        ):
            subprocess.run(
                ["git", *arguments], cwd=project.root, check=True, capture_output=True
            )
        # The actual reader supplies the same finite header identity that apply
        # reobserves inside the original Root/Component fences.
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        original = dict(selected.original_contents)
        seven = tuple(selected.recorded_wrapper_source.projection.entries)
        implementation = (
            project.root / "components/legacy-project-wrapper/implementation/main.py"
        )
        native = implementation.stat()
        with ProjectConfigurationStore.layout_lock(project.root):
            result = transaction.apply_framework_authority(
                selected, public["plan_identity"]
            )
        self.assertFalse(result["full_containment"])
        destination = project.root / "litai/components/legacy-project-wrapper"
        catalog = FilesystemLockedGenerationAuthorityReader().load_catalog(destination)
        self.assertEqual(
            catalog.project.definition,
            ProjectConfigurationStore(project.root).read().definition,
        )
        self.assertEqual(
            catalog.component_authoring_content(catalog.root_authoring.identity),
            next(
                entry.original_bytes
                for entry in seven
                if entry.logical.endswith("/component.md")
            ),
        )
        catalog.require_unchanged()
        layout = resolve_structural_layout(
            project.root,
            json.loads(
                (project.root / "litai/.literate/legacy-lift-shift.json").read_bytes()
            ),
        )
        self.assertEqual(layout.wrapper_root, destination)
        self.assertEqual(layout.implementation_root, implementation.parent)
        self.assertEqual(_git_state(project.root), public["git_state"])
        for entry in seven:
            self.assertFalse((project.root / entry.original_coordinate).exists())
            self.assertEqual(
                (project.root / "litai" / entry.logical).read_bytes(),
                entry.original_bytes,
            )
        self.assertEqual(
            (implementation.stat().st_dev, implementation.stat().st_ino),
            (native.st_dev, native.st_ino),
        )
        self.assertEqual(
            implementation.read_bytes(),
            original[implementation.relative_to(project.root).as_posix()],
        )
        for _repeat in range(2):
            with ProjectConfigurationStore.layout_lock(project.root):
                recovered = transaction.recover_framework_authority(
                    project.root, public["plan_identity"]
                )
            self.assertTrue(recovered["rolled_back"])
        for path, content in original.items():
            self.assertEqual((project.root / path).read_bytes(), content)

    def test_distinct_inherited_skill_keeps_its_original_mixed_catalog_blocker(self):
        project, resources, _retained = self.fixture()
        before = (project.root / "skills/demo/SKILL.md").read_bytes()
        public, selected = self.observe(project, resources)
        self.assertFalse(public["applicable"])
        self.assertNotIn("skills/demo/SKILL.md", public["placements"])
        self.assertTrue(
            any(
                row["path"] == "skills"
                and row["owner"] == "initialized-catalog-resolver"
                for row in public["required_owners"]
            )
        )
        self.assertEqual((project.root / "skills/demo/SKILL.md").read_bytes(), before)

    def test_changed_normal_store_constructor_refuses_before_foreign_call(self):
        project, resources, _retained = self.fixture()
        calls = []

        def foreign(*args, **kwargs):
            calls.append(True)

        with patch.object(core.ComponentLockStore, "__init__", foreign):
            with self.assertRaises(ProjectLayoutPlanError):
                self.observe(project, resources)
        self.assertEqual(calls, [])

    def test_additional_projection_data_cannot_redirect_or_overlap_wrapper(self):
        project, resources, retained = self.fixture()
        wrapper = support.RecordedWrapperSourceTests.admit(
            self, project, resources, retained
        )
        records = {
            name: content
            for name, content in wrapper.projection.record_bytes
            if name not in {"initialization_origin", "initialization_baseline"}
        }
        for additional in (
            {"SKILL.md": "application/SKILL.md"},
            {"litai.harness.mk": "litai/litai.harness.mk"},
        ):
            with self.subTest(additional=additional), self.assertRaises(ValueError):
                projector.project_recorded_legacy_wrapper_authority(
                    resources=resources,
                    before_definition_bytes=project.snapshot.content,
                    prospective_definition_bytes=project.snapshot.content,
                    original_coordinates=dict(wrapper.coordinates),
                    prospective_coordinates=dict(wrapper.coordinates),
                    record_bytes=records,
                    implementation_directory=wrapper.retained_source.layout.implementation_directory,
                    source_tree_identity=wrapper.projection.source_tree_identity,
                    original_entry_bytes={
                        entry.logical: entry.original_bytes
                        for entry in wrapper.projection.entries
                    },
                    additional_coordinates=additional,
                )
