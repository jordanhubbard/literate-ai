"""Complete catalog registration is required even for unrelated evidence readers."""

import json
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from literate_ai.schema_catalog import schema_catalog_root


def promotion_validators():
    """Use the actual fully verified catalog and standard JSON Schema resolver."""
    documents = [
        json.loads(path.read_bytes())
        for version in ("v1", "v2")
        for path in schema_catalog_root(version).glob("*.schema.json")
    ]
    registry = (
        Registry()
        .with_resources(
            (document["$id"], Resource.from_contents(document))
            for document in documents
        )
        .crawl()
    )
    return {
        document["$defs"]["record"]["$id"]: Draft202012Validator(
            document, registry=registry
        )
        for document in documents
        if document["$id"].startswith("urn:literate-ai:schema:v2:retained-project-")
        and document["$id"].endswith(
            (
                "promotion-evidence-contracts",
                "historical-admission-contracts",
                "test-runner-contracts",
            )
        )
    }


class PromotionSchemaCatalogTests(unittest.TestCase):
    def test_complete_current_catalog_resolves_all_three_writers(self):
        # schema_catalog_root validates index/resource/ref/compatibility equality;
        # checking just the new files would miss the original CI counterexample.
        self.assertEqual(
            set(promotion_validators()),
            {
                "literate-ai/retained-project-promotion-evidence@1",
                "literate-ai/retained-project-historical-admission@1",
                "literate-ai/retained-project-test-runner@2",
            },
        )
