"""Genuine initialized file, catalog and producer owners; origin lookup modeled.

No imported Component record, migration writer, execution or native acceptance.
"""

from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_component_transition as production
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters.component_lock_application import update_component_lock
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
)
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from literate_ai.projects import (
    ProjectConfigurationStore,
    serialize_project_configuration,
)
from tests.critical import test_project_layout_framework_source_proofs as support
from tests.support.fixtures_test_component_lock_planning import _fixture


class InitializedComponentTransitionTests(unittest.TestCase):
    def fixture(self, *, with_lock=False):
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, previous = helper.fixture()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        input_root = Path(temporary.name).resolve() / "original-inputs"
        original, _flavors = _fixture(input_root)
        logical = "samples/hello-component/component.md"
        source_relative = "samples/hello-component"
        component = project.root / source_relative
        component.parent.mkdir()
        shutil.copytree(original, component)
        for name in ("skills", "flavors", "workflows", "routing"):
            shutil.copytree(input_root / name, project.root / name, dirs_exist_ok=True)
        # This fixture has a genuine local Component, with no inherited catalog.
        (project.root / "skills/demo/SKILL.md").unlink()
        (project.root / "skills/demo").rmdir()
        project.imports = CatalogImportsFile(())
        project.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(project.imports.to_dict()) + b"\n",
        )
        project.write("SKILL.md", (input_root / "SKILL.md").read_bytes())
        project.definition = replace(
            project.definition, agent_skill="SKILL.md", component_roots=("samples",)
        )
        project.write(
            project.manifest, serialize_project_configuration(project.definition)
        )
        authored = (component / "component.md").read_bytes()
        project.baseline = replace(
            project.baseline,
            files=tuple(
                sorted(
                    (
                        *project.baseline.files,
                        ProjectInitializationBaselineFile(
                            logical,
                            len(authored),
                            ContentIdentity.parse_uri(support.identity(authored)),
                        ),
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        bases = UpdateBases(project.root)
        bases.advance("framework", logical, authored)
        project.write("litai/.literate/update-bases.json", bases.serialized())
        if with_lock:
            update_component_lock(
                component,
                target_name="macos-host",
                flavor_selectors=("+macos", "+python"),
                flavor_roots=(project.root / "flavors",),
            )
        project.refresh()
        project.inventory["retained_implementation"] = None
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        self.enterContext(
            patch.object(
                resources, "_read_current_origin", return_value=previous.origin
            )
        )
        owner = resources.observe_original_framework_resources(observed)
        proof = helper.prove(project, owner, logical=logical, source_path=logical)
        catalog = FilesystemLockedGenerationAuthorityReader().load_catalog(component)
        store = ComponentLockStore(component)
        audit = (
            ComponentResolutionAuditStore(component, "macos-host")
            if with_lock
            else None
        )
        kwargs = dict(
            source_root=source_relative,
            contents=project.contents,
            observations=project.observations,
            original_catalog=catalog,
            original_lock_store=store,
            original_audit_store=audit,
        )
        return project, proof, kwargs

    def select(self, project, proof, kwargs):
        return production.observe_initialized_component_layout_transition(
            project.snapshot, project.context, proof, **kwargs
        )

    def test_actual_initialized_source_uses_shared_original_core_without_import(self):
        project, proof, kwargs = self.fixture()
        owner = self.select(project, proof, kwargs)
        production.require_original_component_transition(owner)
        production.require_current_component_transition(owner)
        self.assertEqual(owner.source_kind, "initialized")
        self.assertIsNone(owner.imported_source)
        self.assertIs(owner.initialized_source, proof)
        self.assertEqual(owner.manifest_identity, proof.source_identity)
        self.assertEqual(owner.target_names, ())
        self.assertEqual(owner.records, {})
        self.assertEqual(project.imports.imports, ())

    def test_real_existing_typed_producer_is_joined_by_original_catalog_and_stores(
        self,
    ):
        project, proof, kwargs = self.fixture(with_lock=True)
        owner = self.select(project, proof, kwargs)
        self.assertEqual(owner.target_names, ("macos-host",))
        self.assertEqual(
            {row["kind"] for row in owner.records.values()},
            {"ComponentLock", "ComponentResolutionAudit"},
        )
        production.require_current_component_transition(owner)

    def test_initialized_owner_cannot_enter_inherited_catalog_writer_protocol(self):
        from literate_ai.adapters import project_layout_continuation as writer

        project, proof, kwargs = self.fixture()
        owner = self.select(project, proof, kwargs)
        with self.assertRaisesRegex(ProjectLayoutPlanError, "inherited provenance"):
            writer._admit_transition(owner)

    def test_copied_proof_refuses_before_catalog_dispatch(self):
        project, proof, kwargs = self.fixture()
        with patch.object(
            production,
            "_CATALOG_CONTENT",
            side_effect=AssertionError("foreign catalog dispatch"),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                self.select(project, copy.copy(proof), kwargs)

    def test_inherited_ingress_does_not_reclassify_initialized_provenance(self):
        project, proof, kwargs = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            production.observe_component_layout_transition(
                project.snapshot, project.context, proof, **kwargs
            )

    def test_source_provenance_field_substitution_cannot_adopt_a_callback(self):
        project, proof, kwargs = self.fixture()
        owner = self.select(project, proof, kwargs)
        object.__setattr__(owner, "initialized_source", copy.copy(proof))
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_component_transition(owner)

    def test_resource_producer_drift_refuses_before_original_catalog_read(self):
        project, proof, kwargs = self.fixture()
        path = project.root / "litai/.literate/initialization-baseline.json"
        path.write_bytes(path.read_bytes() + b" ")
        with patch.object(
            production,
            "_CATALOG_CONTENT",
            side_effect=AssertionError("catalog after producer drift"),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                self.select(project, proof, kwargs)

    def test_fresh_destination_owner_does_not_reuse_expired_source_resource_guard(self):
        project, proof, kwargs = self.fixture()
        owner = self.select(project, proof, kwargs)
        source = project.root / kwargs["source_root"]
        target = project.root / owner.destination_root
        target.parent.mkdir(parents=True)
        source.rename(target)
        store = ProjectConfigurationStore(project.root)
        original = store.read()
        expected = store.update(
            original, replace(original.definition, component_roots=("litai/samples",))
        )
        with patch.object(
            production,
            "_initialized_resources_current",
            side_effect=AssertionError("expired source owner reused"),
        ):
            production.verify_component_transition_destination_current(owner, expected)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_component_transition(owner)
