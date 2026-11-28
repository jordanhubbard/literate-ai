"""Actual local source/catalog/producer owners; no execution or migration proof."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.component_lock_application import update_component_lock
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
)
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.project_layout_component_transition import (
    observe_component_layout_transition,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutPlanError,
    _capture,
)
from literate_ai.contracts import (
    CatalogImportsFile,
    RepositoryLineage,
    RepositoryParentSelection,
    canonical_json_bytes,
)
from literate_ai.contracts.catalog_imports import (
    CatalogImport,
    CatalogImportFile,
    CatalogImportSource,
)
from literate_ai.projects import (
    ProjectConfigurationStore,
    serialize_project_configuration,
)
from tests.support.fixtures_test_component_lock_planning import _fixture
from tests.support.fixtures_test_project_configuration import _definition


class ComponentProducerTransitionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        component, self.flavors = _fixture(self.root)
        (self.root / "components").mkdir()
        self.component = self.root / "components/greeting"
        component.rename(self.component)
        definition = replace(
            _definition(),
            framework_directory="litai",
            agent_skill="SKILL.md",
            component_roots=("components",),
            flavor_roots=("flavors",),
            skill_roots=("skills",),
            workflow_roots=("workflows",),
            routing_roots=("routing",),
            documentation_roots=("docs",),
            source_cache=None,
        )
        (self.root / "litai").mkdir()
        (self.root / "litai/literate.project.json").write_bytes(
            serialize_project_configuration(definition)
        )
        metadata = self.root / "litai/.literate"
        metadata.mkdir()
        parent = RepositoryParentSelection.root()
        lineage = RepositoryLineage(parent, (), ())
        for name, value in (
            ("repository-parent", parent),
            ("repository-lineage", lineage),
        ):
            (metadata / (name + ".json")).write_bytes(
                canonical_json_bytes(value.to_dict()) + b"\n"
            )
        _nodes, files = _capture(self.component)
        self.imported = CatalogImport(
            "component",
            "greeting",
            CatalogImportSource(
                "source",
                "sha256:" + "1" * 64,
                "git:https://example.test/source.git@" + "a" * 40,
                (),
            ),
            tuple(
                CatalogImportFile(
                    "components/greeting/" + path,
                    "sha256:" + hashlib.sha256(content).hexdigest(),
                )
                for path, content in sorted(files.items())
            ),
            "2026-11-24T00:00:00Z",
        )

    def select(self, with_lock=False):
        self.snapshot = ProjectConfigurationStore(self.root).read()
        self.context = ProjectConfigurationStore.context(self.root)
        self.nodes, self.contents = _capture(self.root)
        reader = FilesystemLockedGenerationAuthorityReader()
        self.catalog = reader.load_catalog(self.component)
        self.store = ComponentLockStore(self.component)
        self.audit_store = (
            ComponentResolutionAuditStore(self.component, "macos-host")
            if with_lock
            else None
        )
        return observe_component_layout_transition(
            self.snapshot,
            self.context,
            self.imported,
            source_root="components/greeting",
            contents=self.contents,
            observations=self.nodes,
            original_catalog=self.catalog,
            original_lock_store=self.store,
            original_audit_store=self.audit_store,
        )

    def produce(self):
        return update_component_lock(
            self.component,
            target_name="macos-host",
            flavor_selectors=("+macos", "+python"),
            flavor_roots=(self.flavors,),
        )

    def test_empty_inventory_is_original_owned_absence_without_invented_target(self):
        before = _capture(self.root)
        selection = self.select()
        selection.require_current()
        self.assertEqual(selection.target_names, ())
        self.assertFalse(selection.records)
        self.assertEqual(
            set(selection.coordination_paths),
            {
                "components/greeting/.component.operation.write.lock",
                "components/greeting/.component.lock.write.lock",
            },
        )
        self.assertEqual(_capture(self.root), before)

    def test_typed_actual_lock_and_audit_join_and_retain_original_bytes(self):
        self.produce()
        selection = self.select(with_lock=True)
        self.assertEqual(selection.target_names, ("macos-host",))
        self.assertEqual(len(selection.records), 2)
        for path, row in selection.records.items():
            self.assertEqual(
                selection.original_contents[path], (self.root / path).read_bytes()
            )
            self.assertEqual(row["identity"], self.nodes[path]["identity"])
            self.assertNotIn(path, selection.coordination_paths)
        selection.require_current()

    def test_new_producer_record_after_proved_absence_refuses(self):
        selection = self.select()
        (self.component / "component.resolution-audit.unproven.json").write_text("{}")
        with self.assertRaises(ProjectLayoutPlanError):
            selection.require_current()

    def test_original_store_pointer_change_refuses_before_new_path_read(self):
        selection = self.select()
        self.store.path = self.root / "must-not-open"
        with patch.object(
            Path, "open", side_effect=AssertionError("foreign path opened")
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                selection.require_current()

    def test_foreign_audit_lock_identity_and_unjoined_extra_target_refuse(self):
        self.produce()
        audit_store = ComponentResolutionAuditStore(self.component, "macos-host")
        audit = audit_store.read()
        wrong = replace(
            audit,
            component_lock_identity=replace(
                audit.component_lock_identity, digest="2" * 64
            ),
        )
        audit_store.path.write_bytes(canonical_json_bytes(wrong.to_dict()) + b"\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(with_lock=True)
        audit_store.path.write_bytes(canonical_json_bytes(audit.to_dict()) + b"\n")
        (self.component / "component.resolution-audit.other.json").write_bytes(
            canonical_json_bytes(audit.to_dict()) + b"\n"
        )
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(with_lock=True)

    def test_descriptor_replacement_never_dispatches_foreign_guard(self):
        selection = self.select()
        calls = []

        class Foreign:
            def __get__(self, obj, owner):
                calls.append(obj)
                raise AssertionError("foreign descriptor")

        with patch.object(ComponentLockStore, "snapshot", Foreign()):
            with self.assertRaises(ProjectLayoutPlanError):
                selection.require_current()
        self.assertEqual(calls, [])

    def test_matrix_environment_change_refuses_without_reopening_new_mapping(self):
        selection = self.select()
        with patch.dict("os.environ", {"LITAI_MATRIX_CELL_ROOT": "/must-not-open"}):
            with self.assertRaises(ProjectLayoutPlanError):
                selection.require_current()

    def test_destination_uses_new_original_owner_and_never_reuses_source_guard(self):
        selection = self.select()
        destination = self.root / "litai/components/greeting"
        destination.parent.mkdir()
        # Fixture setup only: this is NOT a test of the migration writer.
        self.component.rename(destination)
        relocated = replace(
            self.imported,
            files=tuple(
                replace(row, path="litai/" + row.path) for row in self.imported.files
            ),
        )
        metadata = self.root / "litai/.literate"
        (metadata / "imports.json").write_bytes(
            canonical_json_bytes(CatalogImportsFile((relocated,)).to_dict()) + b"\n"
        )
        current = ProjectConfigurationStore(self.root).read()
        changed = replace(
            current.definition, component_roots=("components", "litai/components")
        )
        current.manifest_path.write_bytes(serialize_project_configuration(changed))
        expected = ProjectConfigurationStore(self.root).read()
        with self.assertRaises((ProjectLayoutPlanError, OSError, ValueError)):
            selection.require_current()
        selection.verify_destination_current(expected)
        with self.assertRaises(ProjectLayoutPlanError):
            selection.verify_destination_current(
                replace(expected, definition=replace(changed, project_id="foreign"))
            )

    def test_pure_selector_keeps_original_producer_and_coordination_boundaries(
        self,
    ):
        from literate_ai.adapters.project_layout_catalog_continuation import (
            select_contained_catalog_continuation,
        )
        from literate_ai.adapters.update_merge import UpdateBases
        from literate_ai.contracts import (
            CatalogImportsFile,
            ContentIdentity,
            ProjectInitializationBaseline,
            ProjectInitializationBaselineFile,
            canonical_identity,
        )
        from tests.support.fixtures_test_repository_lineage import fixture, identity

        self.produce()
        parent, source, _child, lineage = fixture()
        self.imported = replace(
            self.imported,
            source=CatalogImportSource(
                source.project_id,
                source.project_identity.uri,
                f"git:{source.repository_url}@{source.resolved_revision}",
                (),
            ),
        )
        imports = CatalogImportsFile((self.imported,))
        current = ProjectConfigurationStore(self.root).read()
        manifest = "litai/literate.project.json"
        baseline = ProjectInitializationBaseline(
            identity("1"),
            "literate-ai/project-template@1",
            (
                ProjectInitializationBaselineFile(
                    manifest, len(current.content), current.content_identity
                ),
            ),
        )
        for name, value in (
            ("imports", imports),
            ("initialization-baseline", baseline),
            ("repository-parent", parent),
            ("repository-lineage", lineage),
        ):
            path = self.root / ("litai/.literate/" + name + ".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(canonical_json_bytes(value.to_dict()) + b"\n")
        bases = UpdateBases(self.root)
        bases.remember_catalog(imports.imports)
        for row in self.imported.files:
            bases.retain((self.root / row.path).read_bytes())
        (self.root / "litai/.literate/update-bases.json").write_bytes(
            bases.serialized()
        )
        transition = self.select(with_lock=True)
        bases = UpdateBases(self.root)
        # Actual current typed/byte observations with an explicitly modeled
        # inventory role seam, as in the initial continuation controls.
        inventory = {
            "inventory_scope": "curated-contained-canonical",
            "project_id": self.snapshot.definition.project_id,
            "manifest": manifest,
            "retained_implementation": "application",
            "protected_application_members": [],
            "opaque_git_boundaries": [],
            "reference_documents": [],
            "git_state": None,
            "framework_git_state": None,
            "members": [
                {
                    "path": path,
                    "identity": row["identity"],
                    "mode": row["mode"],
                    "role": "producer evidence"
                    if path in transition.records
                    else "authority",
                }
                for path, row in self.nodes.items()
                if row["kind"] == "file"
            ],
        }
        inventory["plan_identity"] = canonical_identity(inventory).uri
        with (
            patch.object(Path, "open", side_effect=AssertionError("pure selection IO")),
            patch.object(
                Path, "stat", side_effect=AssertionError("pure selection stat")
            ),
        ):
            selected = select_contained_catalog_continuation(
                self.snapshot,
                self.context,
                inventory,
                contents=self.contents,
                observations=self.nodes,
                imports=imports,
                lineage=lineage,
                baseline=baseline,
                update_bases=bases,
                component_transitions=(transition,),
            )
        self.assertTrue(selected.public_plan["applicable"])
        self.assertEqual(selected.component_endpoints[0].target_names, ("macos-host",))
        self.assertIs(selected.component_endpoints[0].producer_transition, transition)
        for path in transition.records:
            self.assertEqual(
                selected.placements[path]["from"], selected.placements[path]["to"]
            )
        self.assertFalse(set(transition.coordination_paths) & set(selected.placements))
        self.assertEqual(
            ContentIdentity.parse_uri(
                selected.placements["components/greeting/component.md"]["from"]
            ).uri,
            next(
                row.identity
                for row in self.imported.files
                if row.path == "components/greeting/component.md"
            ),
        )
