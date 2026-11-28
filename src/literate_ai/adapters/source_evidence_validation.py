"""Portable recipe-derived inputs for revalidating transferred source evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass

from literate_ai.adapters.dependencies import validate_cyclonedx_bom
from literate_ai.adapters.dependencies.managed_python import (
    ManagedPythonImports,
    managed_python_import_map,
    recipe_document_python_imports,
    require_managed_python_imports,
)
from literate_ai.adapters.models.coding_cli import (
    _acceptance_argument_vectors,
    _acceptance_result_shape,
    _recipe_managed_python_imports,
)
from literate_ai.contracts import (
    ContentIdentity,
    CycloneDxLifecycle,
    CycloneDxManagedGraph,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.generated_test_coverage import GeneratedTestCoverageAuthority
from literate_ai.generated_tests import validate_generated_test_suite

_SCHEMA = "literate-ai/source-evidence-validation@1"
_V2_SCHEMA = "literate-ai/source-evidence-validation@2"
_V3_SCHEMA = "literate-ai/source-evidence-validation@3"
_V4_SCHEMA = "literate-ai/source-evidence-validation@4"
_MAX_BYTES = 16 * 1024 * 1024
_FIELDS = frozenset(
    {
        "schema",
        "recipe_identity",
        "managed_graph",
        "specification_references",
        "acceptance",
    }
)


@dataclass(frozen=True, slots=True)
class SourceEvidenceValidationInputs:
    """An immutable snapshot of validation authority, without host locations."""

    recipe_identity: str
    managed_graph: CycloneDxManagedGraph
    specification_references: tuple[str, ...]
    acceptance_document: bytes
    coverage_authority: GeneratedTestCoverageAuthority | None = None
    managed_python_imports: ManagedPythonImports = ()
    recipe_document: bytes | None = None

    def __post_init__(self):
        if self.coverage_authority is not None and not isinstance(
            self.coverage_authority, GeneratedTestCoverageAuthority
        ):
            raise TypeError("source validation coverage requires typed authority")
        ContentIdentity.parse_uri(self.recipe_identity)
        if not isinstance(self.managed_graph, CycloneDxManagedGraph):
            raise TypeError("source validation requires a managed dependency graph")
        managed_python_import_map(self.managed_graph, self.managed_python_imports)
        if self.recipe_document is not None:
            if not isinstance(self.recipe_document, bytes):
                raise TypeError("portable recipe preimage requires immutable bytes")
            document = json.loads(self.recipe_document)
            if (
                not isinstance(document, dict)
                or canonical_json_bytes(document) != self.recipe_document
                or canonical_identity(document).uri != self.recipe_identity
                or document.get("managed_sbom_graph_identity")
                != self.managed_graph.identity.uri
                or recipe_document_python_imports(document, self.managed_graph)
                != self.managed_python_imports
            ):
                raise ValueError(
                    "portable recipe preimage differs from original identity"
                )
        if (
            not isinstance(self.specification_references, tuple)
            or any(
                not isinstance(item, str) or not item
                for item in self.specification_references
            )
            or self.specification_references
            != tuple(sorted(set(self.specification_references)))
        ):
            raise ValueError("source validation references must be canonical strings")
        if not isinstance(self.acceptance_document, bytes):
            raise TypeError("source validation acceptance must be immutable JSON bytes")
        value = json.loads(self.acceptance_document)
        if (
            not isinstance(value, dict)
            or set(value) != {"arguments", "result_shape"}
            or not isinstance(value["arguments"], list)
            or any(not isinstance(item, list) for item in value["arguments"])
            or canonical_json_bytes(value) != self.acceptance_document
        ):
            raise ValueError(
                "source validation acceptance must use exact canonical fields"
            )

    @classmethod
    def from_recipe(cls, recipe):
        return cls(
            str(recipe.identity),
            recipe.managed_sbom_graph,
            tuple(getattr(recipe, "non_acceptance_document_paths", ())),
            canonical_json_bytes(
                {
                    "arguments": list(_acceptance_argument_vectors(recipe)),
                    "result_shape": _acceptance_result_shape(recipe),
                }
            ),
            recipe.generated_test_coverage_authority,
            _recipe_managed_python_imports(recipe),
            canonical_json_bytes(recipe.identity_document())
            if _recipe_managed_python_imports(recipe)
            else None,
        )

    def to_dict(self):
        value = {
            "schema": _SCHEMA if self.coverage_authority is None else _V2_SCHEMA,
            "recipe_identity": self.recipe_identity,
            "managed_graph": self.managed_graph.to_dict(),
            "specification_references": list(self.specification_references),
            "acceptance": json.loads(self.acceptance_document),
        }
        if self.coverage_authority is not None:
            value["coverage"] = self.coverage_authority.to_dict()
        if self.managed_python_imports:
            value["schema"] = _V3_SCHEMA
            value["coverage"] = (
                None
                if self.coverage_authority is None
                else self.coverage_authority.to_dict()
            )
            value["managed_python_imports"] = [
                {"provider_revision": revision.to_dict(), "top_level_import": alias}
                for revision, alias in self.managed_python_imports
            ]
        if self.recipe_document is not None:
            value["schema"] = _V4_SCHEMA
            value["coverage"] = (
                None
                if self.coverage_authority is None
                else self.coverage_authority.to_dict()
            )
            value["managed_python_imports"] = [
                {"provider_revision": revision.to_dict(), "top_level_import": alias}
                for revision, alias in self.managed_python_imports
            ]
            value["recipe"] = json.loads(self.recipe_document)
        return value

    @classmethod
    def from_dict(cls, value):
        v2 = isinstance(value, dict) and value.get("schema") == _V2_SCHEMA
        v3 = isinstance(value, dict) and value.get("schema") == _V3_SCHEMA
        v4 = isinstance(value, dict) and value.get("schema") == _V4_SCHEMA
        fields = (
            _FIELDS | {"coverage", "managed_python_imports", "recipe"}
            if v4
            else _FIELDS | {"coverage", "managed_python_imports"}
            if v3
            else (_FIELDS | {"coverage"} if v2 else _FIELDS)
        )
        if (
            not isinstance(value, dict)
            or set(value) != fields
            or value["schema"] not in {_SCHEMA, _V2_SCHEMA, _V3_SCHEMA, _V4_SCHEMA}
            or not isinstance(value["specification_references"], list)
            or len(canonical_json_bytes(value)) > _MAX_BYTES
        ):
            raise ValueError("invalid portable source validation inputs")
        declarations = value.get("managed_python_imports", [])
        if (v3 or v4) and (
            not isinstance(declarations, list)
            or (v3 and not declarations)
            or any(
                not isinstance(item, dict)
                or set(item) != {"provider_revision", "top_level_import"}
                for item in declarations
            )
        ):
            raise ValueError("invalid portable managed Python imports")
        return cls(
            value["recipe_identity"],
            CycloneDxManagedGraph.from_dict(value["managed_graph"]),
            tuple(value["specification_references"]),
            canonical_json_bytes(value["acceptance"]),
            GeneratedTestCoverageAuthority.from_dict(value["coverage"])
            if v2 or ((v3 or v4) and value["coverage"] is not None)
            else None,
            tuple(
                (
                    ContentIdentity.from_dict(item["provider_revision"]),
                    item["top_level_import"],
                )
                for item in declarations
            ),
            canonical_json_bytes(value["recipe"]) if v4 else None,
        )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def validate(self, source_bom_content: bytes, suite_content: bytes):
        acceptance = json.loads(self.acceptance_document)
        bom = validate_cyclonedx_bom(
            source_bom_content,
            lifecycle=CycloneDxLifecycle.SOURCE,
            managed_graph=self.managed_graph,
        )
        require_managed_python_imports(
            json.loads(source_bom_content),
            self.managed_graph,
            self.managed_python_imports,
        )
        suite = validate_generated_test_suite(
            suite_content,
            recipe_identity=self.recipe_identity,
            specification_references=self.specification_references,
            acceptance_arguments=acceptance["arguments"],
            result_shape=acceptance["result_shape"],
            coverage_authority=self.coverage_authority,
        )
        return bom, suite
