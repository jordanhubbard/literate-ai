"""Original captured files + modeled inventory classifications; no migration claim.

The fixture uses actual project/provenance contracts, UpdateBases and no-follow
capture. Inventory classification is explicit data; writer fencing/recovery and
native retained-harness renewal remain separate integration controls.
"""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jsonschema import Draft202012Validator

from literate_ai.adapters.harness_tree import SOURCE_SCOPE_SCHEMA, _identity
from literate_ai.adapters.project_layout_catalog_continuation import (
    SCHEMA,
    decode_catalog_continuation_plan,
    select_contained_catalog_continuation,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutPlanError,
    _capture,
    _curated_canonical_scopes,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    ContentIdentity,
    ProjectInitializationBaseline,
    ProjectInitializationBaselineFile,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.catalog_imports import (
    CatalogImport,
    CatalogImportFile,
    CatalogImportSource,
)
from literate_ai.projects import (
    PROJECT_FILENAME,
    ProjectConfigurationSnapshot,
    ProjectContext,
    serialize_project_configuration,
)
from tests.support.fixtures_test_project_configuration import _definition
from tests.support.fixtures_test_repository_lineage import fixture, identity


def digest(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


class CatalogContinuationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.definition = replace(
            _definition(),
            framework_directory="litai",
            agent_skill="skills/demo/SKILL.md",
            component_roots=("components",),
            flavor_roots=("flavors",),
            skill_roots=("skills",),
            workflow_roots=("workflows",),
            routing_roots=("routing",),
            documentation_roots=("docs",),
            source_cache=None,
        )
        self.manifest = "litai/" + PROJECT_FILENAME
        self.write(self.manifest, serialize_project_configuration(self.definition))
        self.write("skills/demo/SKILL.md", b"# Imported demo\n")
        self.write("docs/guide.md", b"See [demo](../skills/demo/SKILL.md).\n")
        self.write("application/main.py", b"print('untouched')\n")
        selection, source, _child, self.lineage = fixture()
        self.source = CatalogImportSource(
            source.project_id,
            source.project_identity.uri,
            f"git:{source.repository_url}@{source.resolved_revision}",
            (),
        )
        self.imports = CatalogImportsFile(
            (
                CatalogImport(
                    "skill",
                    "demo",
                    self.source,
                    (
                        CatalogImportFile(
                            "skills/demo/SKILL.md", digest(b"# Imported demo\n")
                        ),
                    ),
                    "2026-11-24T00:00:00Z",
                ),
            )
        )
        manifest = (self.root / self.manifest).read_bytes()
        self.baseline = ProjectInitializationBaseline(
            identity("1"),
            "literate-ai/project-template@1",
            (
                ProjectInitializationBaselineFile(
                    self.manifest,
                    len(manifest),
                    ContentIdentity.parse_uri(digest(manifest)),
                ),
            ),
        )
        for name, value in (
            ("imports", self.imports),
            ("initialization-baseline", self.baseline),
            ("repository-parent", selection),
            ("repository-lineage", self.lineage),
        ):
            self.write(
                "litai/.literate/" + name + ".json",
                canonical_json_bytes(value.to_dict()) + b"\n",
            )
        bases = UpdateBases(self.root)
        bases.remember_catalog(self.imports.imports)
        bases.retain(b"# Imported demo\n")
        self.write("litai/.literate/update-bases.json", bases.serialized())
        self.refresh()

    def write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def refresh(self):
        self.context = ProjectContext.observe(self.root, self.root / "litai")
        self.snapshot = ProjectConfigurationSnapshot(
            self.root,
            self.definition,
            (self.root / self.manifest).read_bytes(),
            self.root / self.manifest,
            self.context.directory_binding,
        )
        self.bases = UpdateBases(self.root)
        self.observations, self.contents = _capture(self.root)
        self.inventory = {
            "inventory_scope": "curated-contained-canonical",
            "project_id": self.definition.project_id,
            "manifest": self.manifest,
            "retained_implementation": "application",
            "protected_application_members": ["application/main.py"],
            "opaque_git_boundaries": [],
            "reference_documents": ["docs/guide.md"],
            "git_state": None,
            "framework_git_state": None,
            "members": [
                {
                    "path": name,
                    "identity": row["identity"],
                    "mode": row["mode"],
                    "role": "application"
                    if name == "application/main.py"
                    else "authority",
                }
                for name, row in self.observations.items()
                if row["kind"] == "file"
            ],
        }
        self.rehash()

    def rehash(self):
        self.inventory.pop("plan_identity", None)
        self.inventory["plan_identity"] = canonical_identity(self.inventory).uri

    def select(self, **kwargs):
        return select_contained_catalog_continuation(
            self.snapshot,
            self.context,
            self.inventory,
            contents=self.contents,
            observations=self.observations,
            imports=self.imports,
            lineage=self.lineage,
            baseline=self.baseline,
            update_bases=self.bases,
            **kwargs,
        )

    def test_selection_is_pure_and_preserves_imported_bytes_and_source(self):
        with (
            patch.object(
                Path, "open", side_effect=AssertionError("pure selector opened file")
            ),
            patch.object(
                Path, "stat", side_effect=AssertionError("pure selector statted")
            ),
        ):
            selected = self.select(approved_references=("docs/guide.md",))
        row = selected.placements["skills/demo/SKILL.md"]
        self.assertEqual(row["from"], row["to"])
        self.assertEqual(row["destination"], "litai/skills/demo/SKILL.md")
        self.assertTrue(selected.public_plan["applicable"])
        self.assertEqual(
            selected.original_contents["skills/demo/SKILL.md"], b"# Imported demo\n"
        )
        reopened = CatalogImportsFile.from_dict(
            json.loads(selected.rewritten_contents["litai/.literate/imports.json"])
        )
        self.assertEqual(reopened.imports[0].source, self.source)
        self.assertEqual(reopened.imports[0].files[0].identity, row["from"])
        self.assertEqual(reopened.imports[0].files[0].path, row["destination"])
        self.assertNotIn("original_contents", selected.public_plan)
        self.assertNotIn("Imported demo", json.dumps(selected.public_plan))
        self.assertEqual(
            selected.rewritten_contents["docs/guide.md"],
            b"See [demo](../litai/skills/demo/SKILL.md).\n",
        )
        changed = json.loads(selected.rewritten_contents[self.manifest])
        self.assertEqual(changed["agent_skill"], "litai/skills/demo/SKILL.md")

    def test_reference_approval_required_and_unknown_approval_refuses(self):
        self.assertFalse(self.select().public_plan["applicable"])
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(approved_references=("application/main.py",))

    def test_stale_bytes_and_foreign_typed_imports_refuse(self):
        self.contents["skills/demo/SKILL.md"] = b"foreign"
        with self.assertRaises(ProjectLayoutPlanError):
            self.select()
        self.refresh()
        self.imports = replace(self.imports, imports=())
        with self.assertRaises(ProjectLayoutPlanError):
            self.select()

    def test_mutated_update_base_and_snapshot_definition_refuse(self):
        self.bases.sources.clear()
        with self.assertRaises(ProjectLayoutPlanError):
            self.select()
        self.refresh()
        self.snapshot = replace(
            self.snapshot, definition=replace(self.definition, project_id="foreign")
        )
        with self.assertRaises(ProjectLayoutPlanError):
            self.select()

    def test_collision_application_and_producer_evidence_hold_whole_item(self):
        for role in ("application", "producer evidence", "coordination candidate"):
            with self.subTest(role=role):
                for row in self.inventory["members"]:
                    if row["path"] == "skills/demo/SKILL.md":
                        row["role"] = role
                self.rehash()
                self.assertFalse(self.select().placements)
        self.refresh()
        self.write("litai/skills/demo/SKILL.md", b"occupied")
        self.refresh()
        self.assertFalse(self.select().placements)

    def test_literal_root_script_reference_is_blocked_without_rewrite(self):
        self.write("skills/demo/tool.py", b"print('owned')\n")
        self.write("skills/demo/SKILL.md", b"Run `python skills/demo/tool.py`.\n")
        files = tuple(
            CatalogImportFile(path, digest((self.root / path).read_bytes()))
            for path in ("skills/demo/SKILL.md", "skills/demo/tool.py")
        )
        self.imports = replace(
            self.imports, imports=(replace(self.imports.imports[0], files=files),)
        )
        self.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(self.imports.to_dict()) + b"\n",
        )
        self.refresh()
        selected = self.select()
        self.assertFalse(selected.placements)
        self.assertTrue(
            any(
                "literal application-root script" in row["reason"]
                for row in selected.public_plan["blockers"]
            )
        )

    def test_imported_markdown_that_would_need_edit_is_held(self):
        self.write(
            "skills/demo/SKILL.md", b"[application](../../application/main.py)\n"
        )
        item = self.imports.imports[0]
        self.imports = replace(
            self.imports,
            imports=(
                replace(
                    item,
                    files=(
                        replace(
                            item.files[0],
                            identity=digest(
                                (self.root / item.files[0].path).read_bytes()
                            ),
                        ),
                    ),
                ),
            ),
        )
        self.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(self.imports.to_dict()) + b"\n",
        )
        self.refresh()
        self.assertFalse(self.select().placements)

    def test_curated_capture_includes_old_catalog_not_unrelated_output(self):
        self.write("unrelated/huge-output.bin", b"outside")
        scope = {
            "schema": SOURCE_SCOPE_SCHEMA,
            "paths": ["main.py"],
            "excluded_roots": [],
            "paths_identity": _identity(["main.py"]),
        }
        data = {
            "litai/.literate/legacy-lift-shift.json": b"{}",
            "litai/.literate/harness-inventory.json": json.dumps(
                {"source_scope": scope}
            ).encode(),
        }
        # Explicit modeled retained-layout seam; original source-scope decoder,
        # actual native observation and actual selected catalog roots remain real.
        with patch(
            "literate_ai.adapters.retained_layout.resolve_structural_layout",
            return_value=SimpleNamespace(implementation_directory="application"),
        ):
            scopes, protected, _implementation = _curated_canonical_scopes(
                self.snapshot, self.context, data
            )
        _old_nodes, old = _capture(self.context.framework_root)
        self.assertNotIn(
            "skills/demo/SKILL.md", old
        )  # previous contained-only omission
        nodes, current = _capture(self.root, selected_scopes=scopes)
        self.assertIn("skills/demo/SKILL.md", current)
        self.assertIn("skills", nodes)
        self.assertIn("application/main.py", protected)
        self.assertNotIn("unrelated/huge-output.bin", current)

    def test_curated_git_boundary_is_opaque_and_source_symlink_refuses(self):
        self.write("skills/demo/.git", b"gitdir: foreign\n")
        nodes, current = _capture(self.root, selected_scopes=("litai", "skills"))
        self.assertEqual(nodes["skills/demo"]["kind"], "git-boundary")
        self.assertNotIn("skills/demo/SKILL.md", current)
        (self.root / "skills/demo/.git").unlink()
        (self.root / "skills/demo/SKILL.md").unlink()
        (self.root / "skills/demo/SKILL.md").symlink_to(
            self.root / "application/main.py"
        )
        with self.assertRaises(ProjectLayoutPlanError):
            _capture(self.root, selected_scopes=("litai", "skills"))

    def test_codec_and_catalog_schema_refuse_unknown_mixed_private_fields(self):
        plan = self.select(approved_references=("docs/guide.md",)).public_plan
        root = Path(__file__).parents[2]
        schema = json.loads(
            (
                root / "schemas/v2/project-layout-catalog-continuation.schema.json"
            ).read_bytes()
        )
        validator = Draft202012Validator(schema)
        validator.validate(plan)
        index = json.loads((root / "schemas/v2/index.json").read_bytes())
        self.assertTrue(
            any(
                SCHEMA in (row["root_id"], *row["public_ids"])
                for row in index["schemas"]
            )
        )
        self.assertEqual(decode_catalog_continuation_plan(plan), plan)
        for field, payload in (
            ("schema", SCHEMA.replace("@1", "@2")),
            ("original_contents", {}),
            ("writes", True),
        ):
            bad = copy.deepcopy(plan)
            bad[field] = payload
            with self.subTest(field=field):
                self.assertFalse(validator.is_valid(bad))
                with self.assertRaises(ProjectLayoutPlanError):
                    decode_catalog_continuation_plan(bad)
        bad = copy.deepcopy(plan)
        bad["placements"]["skills/demo/SKILL.md"]["content"] = "private"
        self.assertFalse(validator.is_valid(bad))
        with self.assertRaises(ProjectLayoutPlanError):
            decode_catalog_continuation_plan(bad)

    def test_component_endpoints_are_exact_data_and_require_original_target_selection(
        self,
    ):
        path = "components/demo/component.md"
        content = b"# Original imported Component bytes\n"
        self.write(path, content)
        item = CatalogImport(
            "component",
            "demo",
            self.source,
            (CatalogImportFile(path, digest(content)),),
            "2026-11-24T00:00:00Z",
        )
        self.imports = CatalogImportsFile((item,))
        self.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(self.imports.to_dict()) + b"\n",
        )
        self.refresh()
        selected = self.select()
        self.assertEqual(len(selected.component_endpoints), 1)
        endpoint = selected.component_endpoints[0]
        self.assertEqual(endpoint.source_root, "components/demo")
        self.assertEqual(endpoint.destination_root, "litai/components/demo")
        self.assertEqual(endpoint.manifest_identity, digest(content))
        self.assertIs(endpoint.imported_source, item.source)
        self.assertIsNone(endpoint.target_names)  # no invented audit target inventory
        for parent in ("litai", "components", "components/demo"):
            self.assertEqual(selected.observations[parent]["kind"], "directory")
            self.assertEqual(len(selected.observations[parent]["stamp"]), 7)

    def test_generic_inventory_or_native_profile_cannot_opt_into_continuation(self):
        self.inventory.pop("inventory_scope")
        self.rehash()
        with self.assertRaises(ProjectLayoutPlanError):
            self.select()
        self.refresh()
        self.baseline = replace(self.baseline, profile="native")
        with self.assertRaises(ProjectLayoutPlanError):
            self.select()

    def test_duplicate_import_ownership_is_held(self):
        self.imports = replace(self.imports, imports=self.imports.imports * 2)
        self.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(self.imports.to_dict()) + b"\n",
        )
        self.refresh()
        self.assertFalse(self.select().placements)

    def test_local_extra_file_holds_item_and_directory_reference_is_explicit(self):
        self.write("skills/demo/local.txt", b"local ownership\n")
        self.refresh()
        self.assertFalse(self.select().placements)
        (self.root / "skills/demo/local.txt").unlink()
        self.write("docs/guide.md", b"[catalog item](../skills/demo/)\n")
        self.refresh()
        self.assertFalse(self.select().public_plan["applicable"])
        selected = self.select(approved_references=("docs/guide.md",))
        self.assertEqual(
            selected.rewritten_contents["docs/guide.md"],
            b"[catalog item](../litai/skills/demo)\n",
        )
        self.write("README.md", b"Application command uses skills/demo\n")
        self.refresh()
        self.assertFalse(self.select().placements)
