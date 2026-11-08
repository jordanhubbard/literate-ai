"""Reviewed singleton declarations survive source-free Component promotion."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.models import RecipeDocument
from literate_ai.adapters.specifications import OpenSpecProvider
from literate_ai.generated_test_coverage import (
    COVERAGE_REQUEST_SCHEMA,
    PUBLIC_CALLABLE_CONTRACT_PATH,
    PUBLIC_CALLABLE_SIGNATURE_SCHEMA,
    ZERO_ARGUMENT_COVERAGE_MODE,
)
from literate_ai.source_to_specification import (
    ComponentCapabilityContractDraft,
    ComponentGraphDraft,
    ComponentGraphEdgeDraft,
    ComponentGraphNodeDraft,
    DraftArtifact,
)
from literate_ai.source_to_specification.synthesis import (
    promoted_component_specification_projection,
)
from tests.support.fixtures_test_coding_cli_generation import flavor, recipe


def node(name):
    capability = f"{name}.value"
    return ComponentGraphNodeDraft(
        coordinate=f"local/{name}",
        title=name,
        kind="library",
        profiles=("library",),
        provided_capabilities=(capability,),
        capability_contracts=(
            ComponentCapabilityContractDraft(
                capability, "Return seven with no arguments.", (f"evidence:{name}",)
            ),
        ),
        entrypoints=(),
        build_needs=("implementation.language-ecosystem",),
        source_paths=(f"{name}.py",),
        observation_ids=(f"observation:{name}",),
        evidence_ids=(f"evidence:{name}",),
    )


class PromotedCallableMetadataTests(unittest.TestCase):
    def setUp(self):
        self.graph = ComponentGraphDraft(
            "sha256:" + "a" * 64, "local/singleton", (node("singleton"),), ()
        )
        self.declaration = DraftArtifact(
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
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )

    def projection(self, provider, artifacts, graph=None):
        graph = graph or self.graph
        return promoted_component_specification_projection(
            provider=provider,
            graph=graph,
            artifacts=artifacts,
            coordinate=graph.root_coordinate,
        )

    def specification(self, provider):
        if provider == "openspec":
            return DraftArtifact(
                "specs/derived/spec.md",
                "# Singleton\n\n### Requirement: Return seven\n"
                "The public callable takes no arguments and returns 7.\n"
                "#### Scenario: Call\n- **WHEN** invoked\n- **THEN** return 7\n",
            )
        return DraftArtifact(
            "specs/derived/components/local-singleton/spec.md",
            "---\nname: Singleton\nsummary: Return seven\nkind: component\n"
            "---\n# Behavior\n"
            "The public callable takes no arguments and returns 7.\n",
        )

    def test_openspec_preserves_exact_reviewed_declaration_and_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            projected = self.projection(
                "openspec", (self.specification("openspec"), self.declaration)
            )
            declarations = [
                (source, artifact)
                for source, artifact in projected
                if artifact.path == PUBLIC_CALLABLE_CONTRACT_PATH
            ]
            self.assertEqual(
                declarations, [(PUBLIC_CALLABLE_CONTRACT_PATH, self.declaration)]
            )
            root = Path(tmp)
            paths = []
            documents = []
            for _, artifact in projected:
                path = root / artifact.path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(artifact.content.encode())
                paths.append(artifact.path)
                documents.append(RecipeDocument.create(artifact.path, artifact.content))
            loaded = OpenSpecProvider().load(root, paths)
            loaded.require_unchanged(root)
            current = replace(recipe(flavor("python")), documents=tuple(documents))
            authority = current.generated_test_coverage_authority
            self.assertIsNotNone(authority)
            self.assertEqual(
                authority.public_interface_identity, self.declaration.content_digest
            )
            self.assertIn("Generate exactly one case", current.prompt())
            self.assertNotIn("Generate 3 through 256", current.prompt())

    def test_nested_markdown_corpus_refuses_unprojectable_declaration(self):
        with self.assertRaisesRegex(ValueError, "single-Component OpenSpec"):
            self.projection(
                "literate-markdown",
                (self.specification("literate-markdown"), self.declaration),
            )

    def test_absent_declaration_preserves_default_projection(self):
        for provider in ("openspec", "literate-markdown"):
            with self.subTest(provider=provider):
                spec = self.specification(provider)
                projected = self.projection(provider, (spec,))
                self.assertEqual(len(projected), 1)
                self.assertEqual(projected[0][0], spec.path)
                self.assertEqual(projected[0][1].content, spec.content)
                current = replace(
                    recipe(flavor("python")),
                    documents=(
                        RecipeDocument.create(
                            *(projected[0][1].path, projected[0][1].content)
                        ),
                    ),
                )
                self.assertIsNone(current.generated_test_coverage_authority)

    def test_multi_component_declaration_refuses_ambiguous_owner(self):
        second = node("other")
        edge = ComponentGraphEdgeDraft(
            self.graph.root_coordinate,
            second.coordinate,
            "other",
            "other.value",
            "*",
            "generation",
            False,
            ("evidence:other",),
        )
        graph = replace(self.graph, nodes=(*self.graph.nodes, second), edges=(edge,))
        for provider in ("openspec", "literate-markdown"):
            with (
                self.subTest(provider=provider),
                self.assertRaisesRegex(ValueError, "unambiguous Component owner"),
            ):
                self.projection(provider, (self.declaration,), graph)

    def test_unrecognized_neighbor_metadata_is_excluded(self):
        neighbor = DraftArtifact("interfaces/other.json", self.declaration.content)
        for provider in ("openspec", "literate-markdown"):
            with self.subTest(provider=provider):
                projected = self.projection(
                    provider, (self.specification(provider), neighbor)
                )
                self.assertFalse(
                    any(artifact.path == neighbor.path for _, artifact in projected)
                )


if __name__ == "__main__":
    unittest.main()
