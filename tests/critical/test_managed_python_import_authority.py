"""Selected internal Python imports retain managed revision and portable custody."""

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.dependencies import (
    CycloneDxBomError,
    build_cyclonedx_bom,
    validate_resolved_cyclonedx_bom,
)
from literate_ai.adapters.dependencies.admission import reconcile_generated_dependencies
from literate_ai.adapters.dependencies.managed_python import (
    PYTHON_IMPORT_PROPERTY,
    managed_python_import_map,
    require_managed_python_imports,
)
from literate_ai.adapters.dependencies.types import DependencyObservationError
from literate_ai.adapters.models.coding_cli import (
    RecipeDocument,
    RecipeLibraryDependency,
    _recipe_managed_python_imports,
    _reconcile_authoritative_source_sbom,
    _require_recipe_authority_sbom,
)
from literate_ai.adapters.source_evidence_validation import (
    SourceEvidenceValidationInputs,
)
from literate_ai.contracts import (
    CYCLONEDX_SOURCE_SBOM_PATH,
    CycloneDxLifecycle,
    CycloneDxManagedEdge,
    LibraryCapabilityImport,
    LibraryImportSurface,
    canonical_identity,
    canonical_json_bytes,
    component_bom_ref,
)
from literate_ai.generated_test_coverage import (
    COVERAGE_REQUEST_SCHEMA,
    PUBLIC_CALLABLE_CONTRACT_PATH,
    PUBLIC_CALLABLE_SIGNATURE_SCHEMA,
    ZERO_ARGUMENT_COVERAGE_MODE,
)
from literate_ai.generated_tests import GENERATED_TEST_SUITE_V2_SCHEMA
from tests.smoke.test_cyclonedx_sbom import _identity, _managed_graph
from tests.support.fixtures_test_coding_cli_generation import (
    flavor,
    generated_test_suite,
    recipe,
)


class ManagedPythonImportAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.graph = _managed_graph()
        self.provider = _identity("b")
        self.interface = _identity("d")
        surface = LibraryImportSurface(
            "python",
            "provider",
            (
                LibraryCapabilityImport(
                    "read", self.interface, "provider.api", ("read",)
                ),
                LibraryCapabilityImport(
                    "unused", self.interface, "unselected.api", ("unused",)
                ),
                LibraryCapabilityImport(
                    "write", self.interface, "provider.writer", ("write",)
                ),
            ),
        )
        self.dependencies = tuple(
            RecipeLibraryDependency(self.provider, capability, self.interface, surface)
            for capability in ("read", "write")
        )
        self.recipe = replace(
            recipe(flavor("python")),
            managed_sbom_graph=self.graph,
            library_dependencies=self.dependencies,
        )
        self.declarations = ((self.provider, "provider"),)

    def source(self):
        content, _ = build_cyclonedx_bom(
            lifecycle=CycloneDxLifecycle.SOURCE,
            managed_graph=self.graph,
            managed_python_imports=self.declarations,
        )
        return content

    def canonical_source(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, CYCLONEDX_SOURCE_SBOM_PATH).parent.mkdir(parents=True)
            files = {CYCLONEDX_SOURCE_SBOM_PATH: self.source().decode()}
            _reconcile_authoritative_source_sbom(self.recipe, Path(directory), files)
            return files[CYCLONEDX_SOURCE_SBOM_PATH].encode()

    def test_only_selected_typed_capabilities_determine_aliases(self):
        self.assertEqual(_recipe_managed_python_imports(self.recipe), self.declarations)
        with self.assertRaisesRegex(ValueError, "canonical and unique"):
            replace(
                self.recipe, library_dependencies=tuple(reversed(self.dependencies))
            )
        non_python = replace(
            self.dependencies[0],
            import_surface=LibraryImportSurface(
                "rust",
                "provider",
                (
                    LibraryCapabilityImport(
                        "read", self.interface, "provider::api", ("read",)
                    ),
                ),
            ),
        )
        self.assertEqual(
            _recipe_managed_python_imports(
                replace(self.recipe, library_dependencies=(non_python,))
            ),
            (),
        )

    def test_equal_import_names_keep_distinct_provider_revisions(self):
        second = _identity("e")
        provider = next(c for c in self.graph.components if c.identity == self.provider)
        second_provider = replace(
            provider, identity=second, bom_ref=component_bom_ref(second)
        )
        graph = replace(
            self.graph,
            components=tuple(
                sorted(
                    (*self.graph.components, second_provider), key=lambda c: c.bom_ref
                )
            ),
            edges=tuple(
                sorted(
                    (
                        *self.graph.edges,
                        CycloneDxManagedEdge(
                            self.graph.root_ref, second_provider.bom_ref
                        ),
                    )
                )
            ),
        )
        declarations = (*self.declarations, (second, "provider"))
        self.assertEqual(
            managed_python_import_map(graph, declarations),
            {
                component_bom_ref(self.provider): ("provider",),
                component_bom_ref(second): ("provider",),
            },
        )
        source, _ = build_cyclonedx_bom(
            lifecycle=CycloneDxLifecycle.SOURCE,
            managed_graph=graph,
            managed_python_imports=declarations,
        )
        require_managed_python_imports(json.loads(source), graph, declarations)

    def test_foreign_root_indirect_and_noncanonical_declarations_refuse(self):
        for declarations in (
            ((_identity("e"), "provider"),),
            ((_identity("a"), "provider"),),
            self.declarations * 2,
            ((self.provider, "provider.api"),),
            ((self.provider, "class"),),
        ):
            with self.subTest(declarations=declarations), self.assertRaises(ValueError):
                managed_python_import_map(self.graph, declarations)
        with self.assertRaises(ValueError):
            managed_python_import_map(replace(self.graph, edges=()), self.declarations)

    def test_model_alias_poison_is_replaced_and_cached_alias_drift_refuses(self):
        source = json.loads(self.source())
        provider = next(
            c
            for c in source["components"]
            if c["bom-ref"] == component_bom_ref(self.provider)
        )
        provider["properties"].append(
            {"name": PYTHON_IMPORT_PROPERTY, "value": "poison"}
        )
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, CYCLONEDX_SOURCE_SBOM_PATH).parent.mkdir(parents=True)
            files = {CYCLONEDX_SOURCE_SBOM_PATH: json.dumps(source)}
            _reconcile_authoritative_source_sbom(self.recipe, Path(directory), files)
        content = files[CYCLONEDX_SOURCE_SBOM_PATH].encode()
        _require_recipe_authority_sbom(content, self.recipe)
        self.assertNotIn(b"poison", content)
        current = json.loads(content)
        for change in ("drop", "extra", "move"):
            bad = copy.deepcopy(current)
            provider = next(
                c
                for c in bad["components"]
                if c["bom-ref"] == component_bom_ref(self.provider)
            )
            if change == "extra":
                provider["properties"].append(
                    {"name": PYTHON_IMPORT_PROPERTY, "value": "poison"}
                )
            else:
                provider["properties"] = [
                    p
                    for p in provider["properties"]
                    if p["name"] != PYTHON_IMPORT_PROPERTY
                ]
                if change == "move":
                    bad["metadata"]["component"]["properties"].append(
                        {"name": PYTHON_IMPORT_PROPERTY, "value": "provider"}
                    )
            with self.subTest(change=change), self.assertRaises(ValueError):
                _require_recipe_authority_sbom(canonical_json_bytes(bad), self.recipe)

    def test_portable_alias_authority_roundtrips_and_revalidates_transferred_bytes(
        self,
    ):
        inputs = SourceEvidenceValidationInputs.from_recipe(self.recipe)
        self.assertEqual(
            inputs.to_dict()["schema"], "literate-ai/source-evidence-validation@4"
        )
        restored = SourceEvidenceValidationInputs.from_dict(
            json.loads(canonical_json_bytes(inputs.to_dict()))
        )
        self.assertEqual(restored, inputs)
        self.assertEqual(restored.identity, inputs.identity)
        suite = generated_test_suite(self.recipe).encode()
        restored.validate(self.canonical_source(), suite)
        with self.assertRaises(ValueError):
            restored.validate(
                build_cyclonedx_bom(
                    lifecycle=CycloneDxLifecycle.SOURCE, managed_graph=self.graph
                )[0],
                suite,
            )
        for change in ("empty", "extra-field", "null-v2"):
            bad = copy.deepcopy(inputs.to_dict())
            if change == "empty":
                bad["managed_python_imports"] = []
            elif change == "extra-field":
                bad["managed_python_imports"][0]["ambient"] = True
            else:
                bad["schema"] = "literate-ai/source-evidence-validation@2"
                del bad["managed_python_imports"]
                del bad["recipe"]
            with (
                self.subTest(change=change),
                self.assertRaises((ValueError, TypeError)),
            ):
                SourceEvidenceValidationInputs.from_dict(bad)

    def test_source_to_resolved_preserves_aliases_and_refuses_added_alias(self):
        source = self.source()
        resolved, _ = build_cyclonedx_bom(
            lifecycle=CycloneDxLifecycle.RESOLVED,
            managed_graph=self.graph,
            source_bom=source,
        )
        require_managed_python_imports(
            json.loads(resolved), self.graph, self.declarations
        )
        validate_resolved_cyclonedx_bom(
            resolved, source_content=source, source_managed_graph=self.graph
        )
        bad = json.loads(resolved)
        provider = next(
            c
            for c in bad["components"]
            if c["bom-ref"] == component_bom_ref(self.provider)
        )
        provider["properties"].append(
            {"name": PYTHON_IMPORT_PROPERTY, "value": "poison"}
        )
        with self.assertRaises(CycloneDxBomError):
            validate_resolved_cyclonedx_bom(
                canonical_json_bytes(bad),
                source_content=source,
                source_managed_graph=self.graph,
            )
        with self.assertRaises(CycloneDxBomError):
            build_cyclonedx_bom(
                lifecycle=CycloneDxLifecycle.RESOLVED,
                managed_graph=self.graph,
                source_bom=source,
                managed_python_imports=tuple(
                    sorted(
                        (*self.declarations, (self.provider, "poison")),
                        key=lambda d: (d[0].uri, d[1]),
                    )
                ),
            )

    def test_recipe_preimage_is_bound_and_alias_only_v3_remains_explicit(self):
        modern = SourceEvidenceValidationInputs.from_recipe(self.recipe)
        self.assertEqual(
            modern.recipe_document,
            canonical_json_bytes(self.recipe.identity_document()),
        )
        self.assertEqual(
            canonical_identity(json.loads(modern.recipe_document)).uri,
            self.recipe.identity,
        )
        legacy = replace(modern, recipe_document=None)
        self.assertEqual(
            legacy.to_dict()["schema"], "literate-ai/source-evidence-validation@3"
        )
        self.assertNotIn("recipe", legacy.to_dict())
        self.assertEqual(
            SourceEvidenceValidationInputs.from_dict(legacy.to_dict()), legacy
        )
        self.assertNotEqual(legacy.identity, modern.identity)
        bad = modern.to_dict()
        bad["recipe"]["library_dependencies"][0]["capability"] = "unused"
        with self.assertRaises(ValueError):
            SourceEvidenceValidationInputs.from_dict(bad)
        bad = modern.to_dict()
        del bad["recipe"]
        with self.assertRaises(ValueError):
            SourceEvidenceValidationInputs.from_dict(bad)

    def test_aliases_with_coverage_and_legacy_wire_preimages_are_exact(self):
        public = RecipeDocument.create(
            PUBLIC_CALLABLE_CONTRACT_PATH,
            json.dumps(
                {
                    "schema": COVERAGE_REQUEST_SCHEMA,
                    "mode": ZERO_ARGUMENT_COVERAGE_MODE,
                    "signature": {
                        "schema": PUBLIC_CALLABLE_SIGNATURE_SCHEMA,
                        "arity": 0,
                        "optional": False,
                        "variadic": False,
                    },
                }
            ),
        )
        acceptance = RecipeDocument.create(
            "acceptance/execution.json",
            json.dumps(
                {
                    "invocations": [{"arguments": [], "expected": 7}],
                    "result_shape": "integer",
                }
            ),
        )
        value = replace(
            self.recipe, documents=(*self.recipe.documents, public, acceptance)
        )
        inputs = SourceEvidenceValidationInputs.from_recipe(value)
        restored = SourceEvidenceValidationInputs.from_dict(inputs.to_dict())
        self.assertEqual(restored, inputs)
        self.assertEqual(
            inputs.to_dict()["schema"], "literate-ai/source-evidence-validation@4"
        )
        suite = canonical_json_bytes(
            {
                "schema": GENERATED_TEST_SUITE_V2_SCHEMA,
                "recipe_identity": value.identity,
                "generation_mode": "major-rebuild",
                "coverage": inputs.coverage_authority.to_dict(),
                "cases": [
                    {
                        "case_id": "complete",
                        "category": "example",
                        "specification_refs": ["openspec/spec.md"],
                        "arguments": [],
                        "expected_result": 7,
                    }
                ],
            }
        )
        restored.validate(self.canonical_source(), suite)
        for with_coverage in (False, True):
            legacy = replace(
                inputs,
                managed_python_imports=(),
                recipe_document=None,
                coverage_authority=inputs.coverage_authority if with_coverage else None,
            )
            expected = {
                "schema": "literate-ai/source-evidence-validation@2"
                if with_coverage
                else "literate-ai/source-evidence-validation@1",
                "recipe_identity": legacy.recipe_identity,
                "managed_graph": legacy.managed_graph.to_dict(),
                "specification_references": list(legacy.specification_references),
                "acceptance": json.loads(legacy.acceptance_document),
            }
            if with_coverage:
                expected["coverage"] = legacy.coverage_authority.to_dict()
            self.assertEqual(
                canonical_json_bytes(legacy.to_dict()), canonical_json_bytes(expected)
            )
            self.assertEqual(legacy.identity, canonical_identity(expected))
            self.assertEqual(SourceEvidenceValidationInputs.from_dict(expected), legacy)

    def test_native_alias_is_separate_from_unobserved_third_party_imports(self):
        source = self.source()
        reconcile_generated_dependencies(
            {"source/main.py": "import provider.api\n"},
            source,
            observed_python_imports=frozenset(),
            observed_managed_python_imports=frozenset({"provider"}),
        )
        with self.assertRaisesRegex(
            DependencyObservationError, "third-party|third_party"
        ):
            reconcile_generated_dependencies(
                {"source/main.py": "import provider.api\nimport third_party\n"},
                source,
                observed_python_imports=frozenset(),
                observed_managed_python_imports=frozenset({"provider"}),
            )
        with self.assertRaises(DependencyObservationError):
            reconcile_generated_dependencies(
                {"source/main.py": "import provider.api\n"},
                source,
                observed_python_imports=frozenset(),
            )
