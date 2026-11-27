"""Explicit SDK output authority; no generated lifecycle qualification claims."""

import copy
import hashlib
import unittest
from dataclasses import replace

import yaml

from literate_ai.adapters.component_markdown import _render_library_import
from literate_ai.application.library_artifacts import project_library_import_surface
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.executable_components.commands import (
    LibraryCapabilityImport,
    LibraryImportSurface,
)
from literate_ai.contracts.library_imports import (
    AuthoredLibraryImport,
    validate_library_imports,
)
from literate_ai.contracts.node_sdk import (
    NodeSDKExportDeclaration,
    node_sdk_package_boundary_files,
    node_sdk_package_boundary_records,
)
from literate_ai.schema_catalog import verify_schema_catalog
from tests.smoke import test_node_sdk_composition as composition_fixtures
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


class NodeSDKDualExportTests(unittest.TestCase):
    def setUp(self):
        self.package = "@example/counter"
        self.cap = LibraryCapabilityImport(
            "counter.add",
            canonical_identity("numeric counter API"),
            self.package,
            ("add",),
        )
        self.root = NodeSDKExportDeclaration(self.package, "index")
        self.subpath = replace(self.root, module=self.package + "/counter")
        self.surface = LibraryImportSurface(
            "typescript",
            self.package,
            (self.cap,),
            node_sdk_exports=(self.root, self.subpath),
        )
        self.authored = AuthoredLibraryImport(
            "typescript",
            self.package,
            self.cap.capability,
            self.cap.module,
            self.cap.symbols,
            node_sdk_exports=(self.root, self.subpath),
        )

    def test_explicit_dual_paths_and_boundaries_roundtrip(self):
        wire = self.surface.to_dict()
        self.assertEqual(
            wire["schema"], "urn:literate-ai:schema:v2:library-import-surface@3"
        )
        self.assertEqual(LibraryImportSurface.from_dict(wire), self.surface)
        self.assertEqual(
            NodeSDKExportDeclaration.from_dict(self.root.to_dict()), self.root
        )
        self.assertEqual(
            self.root.paths,
            ("cjs/index.js", "cjs/index.d.ts", "esm/index.js", "esm/index.d.ts"),
        )
        for record, (path, content) in zip(
            wire["package_boundaries"], node_sdk_package_boundary_files(), strict=True
        ):
            self.assertEqual(record["path"], path)
            self.assertEqual(record["sha256"], hashlib.sha256(content).hexdigest())
        altered = wire["package_boundaries"]
        altered[0]["type"] = "module"
        self.assertEqual(node_sdk_package_boundary_records()[0]["type"], "commonjs")

    def test_old_typescript_v1_codec_and_identity_remain_unchanged(self):
        old = LibraryImportSurface(
            "typescript", "counter", (replace(self.cap, module="counter/index"),)
        )
        wire = old.to_dict()
        self.assertEqual(
            wire["schema"], "urn:literate-ai:schema:v2:library-import-surface@1"
        )
        self.assertEqual(LibraryImportSurface.from_dict(wire), old)
        self.assertEqual(old.identity, canonical_identity(wire))
        self.assertNotIn("node_sdk_exports", wire)

    def test_aliases_share_exact_files_without_inventing_capabilities(self):
        self.assertEqual(len(self.surface.capabilities), 1)
        self.assertEqual(len(self.surface.node_sdk_exports), 2)
        self.assertEqual(self.root.paths, self.subpath.paths)
        changed = replace(self.subpath, stem="other")
        with self.assertRaisesRegex(ValueError, "aliases must share"):
            replace(self.surface, node_sdk_exports=(self.root, changed))

    def test_exports_require_canonical_coverage_and_root(self):
        for exports in [
            (),
            (self.subpath,),
            (self.subpath, self.root),
            (self.root, self.root),
        ]:
            # Empty preserves v1 construction, but the explicit @3 wire must
            # reject an empty export list rather than downgrade its authority.
            if not exports:
                wire = self.surface.to_dict()
                wire["node_sdk_exports"] = []
                with self.assertRaises(ValueError):
                    LibraryImportSurface.from_dict(wire)
            else:
                with self.subTest(exports=exports), self.assertRaises(ValueError):
                    replace(self.surface, node_sdk_exports=exports)
        with self.assertRaises(ValueError):
            replace(
                self.surface,
                capabilities=(replace(self.cap, module=self.package + "/missing"),),
            )

    def test_codec_rejects_path_boundary_version_and_extra_field_drift(self):
        for mutation in ("runtime", "declaration", "boundary", "version", "extra"):
            wire = copy.deepcopy(self.surface.to_dict())
            if mutation == "runtime":
                wire["node_sdk_exports"][0]["require"]["runtime"] = "cjs/other.js"
            if mutation == "declaration":
                wire["node_sdk_exports"][0]["import"]["declaration"] = "cjs/index.d.ts"
            if mutation == "boundary":
                wire["package_boundaries"][0]["sha256"] = "0" * 64
            if mutation == "version":
                wire["schema"] = "urn:literate-ai:schema:v2:library-import-surface@4"
            if mutation == "extra":
                wire["node_sdk_exports"][0]["extra"] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                LibraryImportSurface.from_dict(wire)

    def test_scoped_names_are_exclusive_to_explicit_sdk_branch(self):
        for language in ("javascript", "python", "rust"):
            with self.subTest(language=language), self.assertRaises(ValueError):
                LibraryImportSurface(language, self.package, (self.cap,))
            with self.assertRaises(ValueError):
                replace(self.surface, language=language)
        for package in (
            "@example/../escape",
            "@Example/counter",
            "node_modules",
            "_providers",
            "node:fs",
        ):
            with self.subTest(package=package), self.assertRaises(ValueError):
                replace(self.surface, package=package)

    def test_portable_stems_and_output_directory_aliases_are_closed(self):
        for stem in (
            "../index",
            "CON",
            "foo\\bar",
            "foo%20bar",
            "node_modules/x",
            "_providers/x",
            "index.d",
        ):
            with self.subTest(stem=stem), self.assertRaises(ValueError):
                replace(self.root, stem=stem)
        other = replace(
            self.cap, capability="counter.other", module=self.package + "/other"
        )
        for left, right in [("Foo/index", "foo/other"), ("index", "index.js/other")]:
            with self.subTest(left=left, right=right), self.assertRaises(ValueError):
                replace(
                    self.surface,
                    capabilities=(self.cap, other),
                    node_sdk_exports=(
                        replace(self.root, stem=left),
                        NodeSDKExportDeclaration(other.module, right),
                    ),
                )

    def test_authored_projection_and_markdown_metadata_roundtrip(self):
        validate_library_imports(
            (self.authored,), kind="library", capabilities=(self.cap.capability,)
        )
        self.assertEqual(
            AuthoredLibraryImport.from_dict(self.authored.to_dict()), self.authored
        )
        raw = yaml.safe_load("\n".join(_render_library_import(self.authored)))
        self.assertEqual(AuthoredLibraryImport.from_dict(raw), self.authored)
        projected = project_library_import_surface(
            "counter",
            "typescript",
            ((self.cap.capability, self.cap.interface_identity),),
            declarations=(self.authored,),
        )
        self.assertEqual(projected, self.surface)
        with self.assertRaises(ValueError):
            replace(
                self.authored,
                node_sdk_exports=(self.root, replace(self.subpath, stem="other")),
            )
        with self.assertRaises(ValueError):
            replace(self.authored, node_sdk_exports=())
        old = {
            "language": "javascript",
            "package": "counter",
            "capability": "counter.add",
            "module": "counter/index",
            "symbols": ["add"],
            "node_sdk_exports": [],
        }
        with self.assertRaises(ValueError):
            AuthoredLibraryImport.from_dict(old)

    def test_public_catalog_and_authored_item_schema_match_writers(self):
        verify_schema_catalog("v2")
        catalog = SchemaCatalog()
        catalog.validate(self.surface.to_dict()["schema"], self.surface.to_dict())
        catalog.validate(self.root.SCHEMA, self.root.to_dict())
        catalog.validate(
            "urn:literate-ai:schema:v2:component-authoring-lock-contracts#/$defs/authoring/properties/library_imports/items",
            self.authored.to_dict(),
        )

    def test_generated_plan_requires_exact_output_authority_before_provider_reads(self):
        f = composition_fixtures.NodeSDKCompositionTests(
            "test_relocated_cjs_esm_root_subpath_and_error_identity"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)
        original = f.fixture.consumer
        consumer = replace(
            original,
            artifact_export=replace(original.artifact_export, role="library"),
            library_import_surface=self.surface,
        )
        f.fixture.consumer = consumer
        plan = f.prepare(name=self.package)
        self.assertEqual(plan.consumer_contract, consumer.identity)

        def no_read(_blob):
            raise AssertionError("mismatched output authority read provider bytes")

        for changes in (
            {"name": "other-sdk"},
            {"name": self.package, "entrypoints": f.arguments["entrypoints"][:1]},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaisesRegex(
                    ValueError, "differ from its current library authority"
                ),
            ):
                f.prepare(read_blob=no_read, **changes)

    def test_consumer_contract_change_invalidates_plan_with_same_source_and_outputs(
        self,
    ):
        f = composition_fixtures.NodeSDKCompositionTests(
            "test_relocated_cjs_esm_root_subpath_and_error_identity"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)
        first = f.prepare()
        f.fixture.consumer = replace(
            f.fixture.consumer,
            locked_build_authority_identity=canonical_identity(
                "changed current build policy"
            ),
        )
        second = f.prepare()
        self.assertEqual(first.consumer, second.consumer)
        self.assertEqual(first.source, second.source)
        self.assertEqual(first.files, second.files)
        self.assertNotEqual(first.consumer_contract, second.consumer_contract)
        self.assertNotEqual(first.identity, second.identity)

    def test_sdk_surface_cannot_be_read_as_a_v1_commonjs_provider(self):
        f = composition_fixtures.NodeSDKCompositionTests(
            "test_relocated_cjs_esm_root_subpath_and_error_identity"
        )
        f.setUp()
        self.addCleanup(f.doCleanups)
        contract = replace(f.provider_contract, library_import_surface=self.surface)

        def no_read(_blob):
            raise AssertionError("unsupported SDK provider was read")

        with self.assertRaisesRegex(ValueError, "surface @3"):
            f.prepare(
                contracts={contract.component_revision.uri: contract}, read_blob=no_read
            )
