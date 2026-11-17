"""Opt-in declaration authority without changing existing library wire identities."""

import copy
import unittest
from dataclasses import replace

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
from literate_ai.contracts.node_sdk import CommonJSModuleDeclaration


class NodeSDKSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.cap = LibraryCapabilityImport(
            "counter.add", canonical_identity("interface"), "counter/index", ("add",)
        )
        self.old = LibraryImportSurface("javascript", "counter", (self.cap,))
        self.module = CommonJSModuleDeclaration(
            "counter/index", "source/counter/index.js", "source/counter/index.d.ts"
        )

    def test_old_wire_identity_is_unchanged(self):
        wire = {
            "schema": "urn:literate-ai:schema:v2:library-import-surface@1",
            "language": "javascript",
            "package": "counter",
            "capabilities": [self.cap.to_dict()],
        }
        self.assertEqual(self.old.to_dict(), wire)
        self.assertEqual(self.old.identity, canonical_identity(wire))
        self.assertEqual(LibraryImportSurface.from_dict(wire), self.old)

    def test_declared_surface_roundtrips_and_changes_identity(self):
        surface = replace(self.old, declarations=(self.module,))
        self.assertEqual(
            surface.to_dict()["schema"],
            "urn:literate-ai:schema:v2:library-import-surface@2",
        )
        self.assertEqual(LibraryImportSurface.from_dict(surface.to_dict()), surface)
        self.assertNotEqual(surface.identity, self.old.identity)
        changed = replace(
            surface,
            declarations=(
                replace(self.module, declaration="source/counter/other.d.ts"),
            ),
        )
        self.assertNotEqual(surface.identity, changed.identity)

    def test_authored_declaration_projects_through_shared_owner(self):
        authored = AuthoredLibraryImport(
            "javascript",
            "counter",
            "counter.add",
            "counter/index",
            ("add",),
            self.module,
        )
        validate_library_imports(
            (authored,), kind="library", capabilities=("counter.add",)
        )
        self.assertEqual(AuthoredLibraryImport.from_dict(authored.to_dict()), authored)
        surface = project_library_import_surface(
            "counter",
            "javascript",
            (("counter.add", self.cap.interface_identity),),
            declarations=(authored,),
        )
        self.assertEqual(surface, replace(self.old, declarations=(self.module,)))
        with self.assertRaises(ValueError):
            replace(authored, language="python")
        with self.assertRaises(ValueError):
            replace(authored, node_module=replace(self.module, module="counter/other"))

    def test_incomplete_or_conflicting_authored_surfaces_fail(self):
        first = AuthoredLibraryImport(
            "javascript",
            "counter",
            "counter.add",
            "counter/index",
            ("add",),
            self.module,
        )
        second = replace(first, capability="counter.other", node_module=None)
        with self.assertRaises(ValueError):
            validate_library_imports(
                (first, second),
                kind="library",
                capabilities=("counter.add", "counter.other"),
            )
        with self.assertRaises(ValueError):
            project_library_import_surface(
                "counter",
                "javascript",
                (
                    ("counter.add", self.cap.interface_identity),
                    ("counter.other", self.cap.interface_identity),
                ),
                declarations=(
                    first,
                    replace(
                        second,
                        node_module=replace(
                            self.module, runtime="source/counter/other.js"
                        ),
                    ),
                ),
            )

    def test_root_module_requires_explicit_opt_in(self):
        with self.assertRaises(ValueError):
            AuthoredLibraryImport(
                "javascript", "counter", "counter.add", "counter", ("add",)
            )
        authored = AuthoredLibraryImport(
            "javascript",
            "counter",
            "counter.add",
            "counter",
            ("add",),
            replace(self.module, module="counter"),
        )
        self.assertEqual(AuthoredLibraryImport.from_dict(authored.to_dict()), authored)

    def test_declared_surface_matches_public_schema(self):
        from literate_ai.schema_catalog import verify_schema_catalog
        from tests.support.fixtures_test_schema_catalog import SchemaCatalog

        verify_schema_catalog("v2")
        surface = replace(self.old, declarations=(self.module,))
        SchemaCatalog().validate(surface.to_dict()["schema"], surface.to_dict())

    def test_root_and_subpath_modules_are_allowed(self):
        root = replace(self.cap, capability="counter", module="counter")
        surface = replace(
            self.old,
            capabilities=(root, self.cap),
            declarations=(
                replace(
                    self.module,
                    module="counter",
                    runtime="source/counter/root.js",
                    declaration="source/counter/root.d.ts",
                ),
                self.module,
            ),
        )
        self.assertEqual(LibraryImportSurface.from_dict(surface.to_dict()), surface)

    def test_explicit_module_aliases_may_share_exact_files(self):
        root = replace(self.cap, capability="counter", module="counter")
        surface = replace(
            self.old,
            capabilities=(root, self.cap),
            declarations=(replace(self.module, module="counter"), self.module),
        )
        self.assertEqual(LibraryImportSurface.from_dict(surface.to_dict()), surface)

    def test_declared_surface_caps_capabilities_as_well_as_modules(self):
        capabilities = tuple(
            replace(self.cap, capability=f"counter.fn{i:03}") for i in range(257)
        )
        with self.assertRaises(ValueError):
            replace(self.old, capabilities=capabilities, declarations=(self.module,))

    def test_v2_requires_exact_nonempty_closed_fields(self):
        wire = replace(self.old, declarations=(self.module,)).to_dict()
        for key, value in [
            ("declarations", []),
            ("declarations", None),
            ("extra", True),
        ]:
            with (
                self.subTest(key=key, value=value),
                self.assertRaises((ValueError, TypeError)),
            ):
                bad = copy.deepcopy(wire)
                bad[key] = value
                LibraryImportSurface.from_dict(bad)
        old = self.old.to_dict()
        old["declarations"] = [self.module.to_dict()]
        with self.assertRaises(ValueError):
            LibraryImportSurface.from_dict(old)

    def test_paths_formats_namespace_and_cover_are_closed(self):
        for change in [
            {"format": "module"},
            {"runtime": "../index.js"},
            {"runtime": "source/counter/CON.js"},
            {"declaration": "source/counter/index.ts"},
            {"runtime": "source\\counter\\index.js"},
            {"runtime": "source/counter/x%23.js"},
            {"declaration": "source/counter/node_modules/types.d.ts"},
        ]:
            with (
                self.subTest(change=change),
                self.assertRaises((ValueError, TypeError)),
            ):
                replace(self.module, **change)
        for declarations in [
            (replace(self.module, module="other/index"),),
            (replace(self.module, runtime="source/other/index.js"),),
            (self.module, self.module),
        ]:
            with self.subTest(declarations=declarations), self.assertRaises(ValueError):
                replace(self.old, declarations=declarations)
        with self.assertRaises(ValueError):
            replace(self.old, language="python", declarations=(self.module,))

    def test_artifact_paths_cannot_alias_or_be_file_ancestors(self):
        cap = replace(self.cap, capability="counter.other", module="counter/other")
        for module in [
            replace(
                self.module,
                module="counter/other",
                runtime="source/counter/INDEX.js",
                declaration="source/counter/other.d.ts",
            ),
            replace(
                self.module,
                module="counter/other",
                runtime="source/counter/index.js/child.js",
                declaration="source/counter/other.d.ts",
            ),
        ]:
            with self.subTest(module=module), self.assertRaises(ValueError):
                replace(
                    self.old,
                    capabilities=(self.cap, cap),
                    declarations=(self.module, module),
                )
