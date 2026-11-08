"""The public signed promotion flow keeps reviewed singleton authority."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.cli._wire import result_from_wire, result_to_wire
from literate_ai.generated_test_coverage import PUBLIC_CALLABLE_CONTRACT_PATH
from literate_ai.source_to_specification import DraftArtifact
from tests.e2e import test_cli_arbitrary_source as source_fixture


class CallableMetadataPromotionTests(unittest.TestCase):
    def test_signed_acceptance_materializes_and_locks_exact_declaration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = source_fixture.create_source(root)
            key = root / "trust.key"
            key.write_bytes(source_fixture.KEY)

            def invoke(*arguments):
                status, output, errors = source_fixture.invoke(*arguments)
                self.assertEqual((status, errors), (0, ""), output)
                return output

            attestation = root / "attestation.json"
            attestation.write_text(
                invoke(
                    "spec",
                    "attest",
                    str(source),
                    "--signer",
                    "reviewer",
                    "--machine",
                    "fixture",
                    "--key",
                    str(key),
                )
            )
            envelope = json.loads(
                invoke(
                    "spec",
                    "derive",
                    str(source),
                    "--attestation",
                    str(attestation),
                    "--trust-key",
                    str(key),
                )
            )
            bundle = envelope["result"]
            graph = source_fixture.reviewed_static_graph(bundle)
            graph["nodes"][0]["library_imports"] = [
                {
                    "language": "python",
                    "package": "singleton",
                    "capability": capability,
                    "module": "singleton.api",
                    "symbols": ["launch"],
                }
                for capability in graph["nodes"][0]["provided_capabilities"]
            ]
            for contract in graph["nodes"][0]["capability_contracts"]:
                contract["contract"] = (
                    "The shared launch() callable takes no arguments."
                )
            declaration = DraftArtifact(
                PUBLIC_CALLABLE_CONTRACT_PATH,
                json.dumps(
                    {
                        "schema": "literate-ai/generated-test-coverage-request@1",
                        "mode": "exhaustive-zero-argument",
                        "signature": {
                            "schema": "literate-ai/public-callable-signature@1",
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
            result = result_from_wire(bundle["result"])
            draft = replace(
                result.draft,
                draft_id="reviewed-singleton-supporting-artifact",
                artifacts=(*result.draft.artifacts, declaration),
            )
            bundle["result"] = result_to_wire(replace(result, draft=draft))
            bundle_path = root / "bundle.json"
            bundle_path.write_text(json.dumps(envelope))
            graph_path = root / "graph.json"
            graph_path.write_text(json.dumps(graph))
            review_arguments = [
                "spec",
                "review",
                str(bundle_path),
                "--actor",
                "reviewer",
                "--key",
                str(key),
                "--component-graph",
                str(graph_path),
            ]
            for uncertainty in bundle["review_gate"]["blocking_uncertainty_ids"]:
                review_arguments.extend(("--resolve", uncertainty))
            review_path = root / "review.json"
            review_path.write_text(invoke(*review_arguments))
            accepted, promoted = root / "accepted", root / "promoted"
            accepted_result = json.loads(
                invoke(
                    "spec",
                    "accept",
                    str(source),
                    str(bundle_path),
                    "--review",
                    str(review_path),
                    "--target",
                    str(accepted),
                    "--project-target",
                    str(promoted),
                    "--trust-key",
                    str(key),
                )
            )["result"]
            component = (
                promoted / Path(accepted_result["promoted_project"]["component"]).parent
            )
            expected = declaration.content.encode()
            self.assertEqual((accepted / declaration.path).read_bytes(), expected)
            self.assertEqual((component / declaration.path).read_bytes(), expected)
            lock = json.loads((component / "component.lock.json").read_text())
            specifications = lock["nodes"][0]["revision"]["specifications"]
            reference = next(
                item for item in specifications if item["uri"] == declaration.path
            )
            self.assertEqual(
                reference["identity"]["digest"], hashlib.sha256(expected).hexdigest()
            )
            self.assertFalse((component / "main.py").exists())


if __name__ == "__main__":
    unittest.main()
