"""Real initialized/inherited owners, normal pairs and ordered native journals.

Historical initialization and import-origin declarations are fixture data. Actor
issuance, normal producers, public migration owners and native rollback are real;
this does not qualify installed acquisition or complete project containment.
"""

from __future__ import annotations

import hashlib
import subprocess
import unittest
from dataclasses import replace

from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_lock_application import update_component_lock
from literate_ai.adapters.project_layout_migration import (
    apply_legacy_layout_migration,
    plan_legacy_layout_migration,
    recover_legacy_layout_migration,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutPlanError,
    plan_contained_catalog_continuation,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from literate_ai.contracts.catalog_imports import CatalogImport, CatalogImportFile
from literate_ai.projects import (
    ProjectConfigurationStore,
    serialize_project_configuration,
)
from tests.critical import test_project_layout_initialized_component_capture as support


class MixedComponentChannelTests(unittest.TestCase):
    def fixture(
        self,
        *,
        shared_parent=False,
        with_peer_lock=True,
        import_flavor=False,
        original_skill_content=None,
    ):
        helper = support.InitializedComponentCaptureTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _old_resources, _old_proof = helper.fixture(
            with_lock=True, original_skill_content=original_skill_content
        )
        project.definition = replace(
            project.definition,
            component_roots=(
                ("samples",)
                if shared_parent
                else ("samples", "litai/samples", "components", "litai/components")
            ),
        )
        project.write(
            project.manifest, serialize_project_configuration(project.definition)
        )
        peer_root = "samples/peer" if shared_parent else "components/peer"
        peer = peer_root + "/component.md"
        content = (project.root / "samples/hello-component/component.md").read_bytes()
        content = content.replace(
            b"Portable greeting application", b"Independent peer application"
        )
        project.write(peer, content)
        if not shared_parent:
            (project.root / "litai/components").mkdir()
        imported = CatalogImport(
            "component",
            "peer",
            project.source,
            (CatalogImportFile(peer, "sha256:" + hashlib.sha256(content).hexdigest()),),
            "2026-11-25T00:00:00Z",
        )
        imports = [imported]
        if import_flavor:
            flavor_files = tuple(
                CatalogImportFile(
                    path.relative_to(project.root).as_posix(),
                    "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
                )
                for path in sorted((project.root / "flavors/os-base").rglob("*"))
                if path.is_file()
            )
            imports.append(
                CatalogImport(
                    "flavor",
                    "os-base",
                    project.source,
                    flavor_files,
                    "2026-11-25T00:00:00Z",
                )
            )
        project.imports = CatalogImportsFile(tuple(imports))
        project.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(project.imports.to_dict()) + b"\n",
        )
        bases = UpdateBases(project.root)
        bases.remember_catalog(project.imports.imports)
        for item in project.imports.imports:
            for member in item.files:
                bases.retain((project.root / member.path).read_bytes())
        if import_flavor:
            # Model actual initialized framework payloads beside the inherited
            # Flavor. Their common catalog-created parent has no coordination.
            rows = {row.path: row for row in project.baseline.files}
            for (
                logical,
                resource,
            ) in support.resources.initialization._TEMPLATE_FILES.items():
                if not logical.startswith("flavors/os-macos/"):
                    continue
                payload = support.resources.initialization._template_text(
                    resource
                ).encode()
                self.assertEqual((project.root / logical).read_bytes(), payload)
                rows[logical] = ProjectInitializationBaselineFile(
                    logical,
                    len(payload),
                    ContentIdentity.parse_uri(
                        "sha256:" + hashlib.sha256(payload).hexdigest()
                    ),
                )
                bases.advance("framework", logical, payload)
            project.baseline = replace(
                project.baseline, files=tuple(rows[path] for path in sorted(rows))
            )
            project.write(
                "litai/.literate/initialization-baseline.json",
                canonical_json_bytes(project.baseline.to_dict()) + b"\n",
            )
        project.write("litai/.literate/update-bases.json", bases.serialized())
        project.write("docs/user/bootstrap.md", b"# Application bootstrap notes\n")
        project.write("docs/README.md", b"# Application documentation\n")
        if with_peer_lock:
            update_component_lock(
                project.root / peer_root,
                target_name="macos-host",
                flavor_selectors=(),
                flavor_roots=(project.root / "flavors",),
            )
        if shared_parent:
            # The original lock fixture precreates this empty catalog. This
            # journey requires the acknowledged catalog transaction to create it.
            (project.root / "litai/samples").rmdir()
        project.refresh()
        original = dict(project.contents)
        native = {path: (project.root / path).stat().st_ino for path in original}
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
                "Original two-owner project",
            ),
        ):
            subprocess.run(
                ["git", *args], cwd=project.root, check=True, capture_output=True
            )
        return project, original, native

    def test_catalog_then_framework_scopes_reverse_exact_original_two_component_state(
        self,
    ):
        project, original, native = self.fixture()
        catalog = plan_legacy_layout_migration(
            project.root, (), place_forward_skills=False, place_imported_catalogs=True
        )
        self.assertTrue(catalog["applicable"], catalog.get("blocked_references"))
        self.assertIn("components/peer/component.md", catalog["placements"])
        self.assertIn("components/peer/component.lock.json", catalog["placements"])
        same_plan, original_catalog = plan_contained_catalog_continuation(project.root)
        self.assertEqual(same_plan["plan_identity"], catalog["plan_identity"])
        (inherited_endpoint,) = original_catalog.component_endpoints
        inherited = inherited_endpoint.producer_transition
        self.assertEqual(inherited.source_kind, "inherited")
        result = apply_legacy_layout_migration(
            project.root,
            catalog["plan_identity"],
            acknowledge=True,
            references=(),
            place_forward_skills=False,
            place_imported_catalogs=True,
        )
        self.assertTrue(result["applied"])
        # File placement is complete, while normal destination currentness
        # still refuses the old audit. These are distinct, actual owners/checks.
        with ProjectConfigurationStore.layout_lock(project.root):
            destination = ProjectConfigurationStore(project.root).read()
            inherited.verify_destination_placement(destination)
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "audit requires ordinary producer renewal"
            ):
                inherited.verify_destination_current(destination)
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        (endpoint,) = selected.component_endpoints
        self.assertEqual(endpoint.source_kind, "initialized")
        self.assertEqual(endpoint.source_root, "samples/hello-component")
        with ProjectConfigurationStore.layout_lock(project.root):
            self.assertTrue(
                framework.apply_framework_authority(selected, public["plan_identity"])[
                    "applied"
                ]
            )
        for root in ("components/peer", "samples/hello-component"):
            for leaf in (
                "component.md",
                "component.lock.json",
                "component.resolution-audit.macos-host.json",
            ):
                self.assertTrue((project.root / "litai" / root / leaf).is_file())
        with ProjectConfigurationStore.layout_lock(project.root):
            self.assertTrue(
                framework.recover_framework_authority(
                    project.root, public["plan_identity"]
                )["rolled_back"]
            )
        for _repeat in range(2):
            recover_legacy_layout_migration(
                project.root, catalog["plan_identity"], acknowledge=True
            )
        for path, payload in original.items():
            self.assertEqual((project.root / path).read_bytes(), payload)
            self.assertEqual((project.root / path).stat().st_ino, native[path])
