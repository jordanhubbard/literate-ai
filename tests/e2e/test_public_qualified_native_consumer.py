"""Actual public producer→genuine V2 receiving→native consumer SOURCE journey.

No qualification, promotion, original-currentness, receiving, archive reader,
Cargo/native process, streams, receipt or independent oracle outcome is mocked.
The editable-source distribution observation and source-producing CLI alone are
controlled. This is not installed, remote-worker or full release qualification.
"""

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.contracts.library_products import LibraryArtifactProduct
from literate_ai.contracts.testing import ProjectTestReceiptFinalizedCandidate
from tests.support.fixtures_public_qualified_native_consumer import (
    prepare_public_qualified_native_consumer,
)
from tests.support.fixtures_public_qualified_native_provider import (
    prepare_public_qualified_native_provider,
)
from tests.support.fixtures_public_qualified_native_receiver import (
    prepare_public_qualified_native_receiver,
)
from tests.support.fixtures_public_qualified_native_scope import (
    actual_public_native_source_scope,
)
from tests.support.fixtures_rust_library_harness import prepare_native_verifier_class


@unittest.skipUnless(
    os.name == "posix" and shutil.which("make") and shutil.which("git"),
    "SOURCE public receiver journey requires the existing POSIX native fixture",
)
class ActualPublicQualifiedNativeConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare_native_verifier_class(cls)

    def test_actual_qualified_provider_then_public_native_consumer(
        self,
    ):
        base = Path(tempfile.mkdtemp(prefix="actual public native consumer ")).resolve()
        base.chmod(0o700)
        succeeded = False

        def cleanup():
            if (
                succeeded
                and os.environ.get("LITAI_TEST_RETAIN_NATIVE_LATE_FIXTURE") != "1"
            ):
                shutil.rmtree(base)
            else:
                # Failed fixtures may retain a disposable fixture signing key.
                # Keep the entire owner private, and never print secret bytes.
                print(f"Retained private public-native consumer fixture: {base}")

        self.addCleanup(cleanup)
        with actual_public_native_source_scope(
            base, self.cargo, self.rustc, self.environment
        ) as (environment, invoke, driver, receipt, calls, agent_hash):
            provider = prepare_public_qualified_native_provider(
                base / "producer",
                self.seed,
                self.cargo,
                self.rustc,
                invoke=invoke,
                environment=environment,
            )
            self.assertEqual(len(agent_hash), 1)
            agent = base / "producer/tools/claude"
            self.assertEqual(
                hashlib.sha256(agent.read_bytes()).hexdigest(), agent_hash[0]
            )
            original_oracle = provider.oracle.oracle_path.read_bytes()
            original_promotion = provider.qualification_record.read_bytes()
            receiver = prepare_public_qualified_native_receiver(
                base / "receiver",
                provider,
                self.cargo,
                self.rustc,
                environment=environment,
            )
            self.assertEqual(receiver.closed_history_reopens, 2)
            original_archive = receiver.archive_path.read_bytes()
            project, component, oracle, configuration = (
                prepare_public_qualified_native_consumer(
                    base / "consumer",
                    self.seed,
                    self.cargo,
                    self.rustc,
                    receiver,
                    invoke=invoke,
                    environment=environment,
                    driver=driver,
                    receipt=receipt,
                )
            )
            oracle_before = oracle.oracle_path.read_bytes()
            candidate_path = base / "consumer-finalized-receipt.json"
            status, envelope = invoke(
                [
                    "rebuild",
                    component.relative_to(project).as_posix(),
                    "--project",
                    str(project),
                    "--qualified-library-receivers",
                    str(configuration),
                    "--runtime-root",
                    str(base / "consumer-runtime"),
                    "--candidate-receipt",
                    str(candidate_path),
                    "--allow-host-execution",
                    "--update-receipt",
                ]
            )
            self.assertEqual(status, 0, envelope)
            result = envelope["result"]
            self.assertIs(result["passed"], True)
            self.assertIs(result["receipt_committed"], True)
            self.assertEqual(result["test_summary"]["failed"], 0)
            self.assertEqual(result["test_summary"]["skipped"], 0)
            self.assertGreater(result["test_summary"]["passed"], 0)
            finalized = ProjectTestReceiptFinalizedCandidate.from_dict(
                json.loads(candidate_path.read_bytes())
            )
            self.assertEqual(finalized.receipt_identity.uri, result["receipt_identity"])
            self.assertEqual(
                finalized.identity.uri, result["finalized_candidate_identity"]
            )
            lock = (
                FilesystemLockedGenerationAuthorityReader()
                .read(component, target_name="host")
                .authority.lock
            )
            self.assertEqual(len(lock.nodes), 1)
            self.assertEqual(lock.edges, ())
            self.assertEqual(set(result["source_generation"]), {lock.root_revision.uri})
            self.assertEqual(result["dag"]["edges"], [])
            self.assertEqual(
                [
                    row["revision"]
                    for layer in result["dag"]["layers"]
                    for row in layer["components"]
                ],
                [lock.root_revision.uri],
            )
            product = LibraryArtifactProduct.from_dict(result["library_artifact"])
            self.assertEqual(
                product.artifact_export.component_revision, lock.root_revision
            )
            self.assertEqual(product.import_surface.package, "qualified_consumer")
            self.assertTrue(Path(result["artifact"]).exists())
            self.assertEqual(oracle.oracle_path.read_bytes(), oracle_before)
            self.assertEqual(provider.oracle.oracle_path.read_bytes(), original_oracle)
            self.assertEqual(
                provider.qualification_record.read_bytes(), original_promotion
            )
            self.assertEqual(receiver.archive_path.read_bytes(), original_archive)
            self.assertEqual(
                hashlib.sha256(agent.read_bytes()).hexdigest(), agent_hash[0]
            )
            requests = [
                json.loads(line)
                for line in provider.request_log.read_text().splitlines()
            ]
            packages = []
            for row in requests:
                section = (
                    row["request"]
                    .split("## Required importable library artifact", 1)[1]
                    .split("```json", 1)[1]
                    .split("```", 1)[0]
                )
                packages.append(json.loads(section)["package"])
            # The original executable is reused, while provider A has no third
            # generation/qualification run during B's native consumer lifecycle.
            self.assertEqual(
                packages,
                ["qualified_fixture", "qualified_fixture", "qualified_consumer"],
            )
            self.assertEqual(len({row["workspace"] for row in requests}), 3)
            (base / "consumer-source-receipt.json").write_text(
                json.dumps(
                    {
                        "schema": "actual-public-qualified-native-consumer-source@1",
                        "actual_provider_clean_runs": 2,
                        "actual_provider_closed_history_reopens": (
                            receiver.closed_history_reopens
                        ),
                        "provider_qualification_identity": provider.retained_evidence[
                            "qualification_identity"
                        ],
                        "provider_product_identity": (
                            receiver.original_product.identity.uri
                        ),
                        "consumer_library_product_identity": product.identity.uri,
                        "consumer_receipt_identity": finalized.receipt_identity.uri,
                        "consumer_generated_node_count": 1,
                        "source_requests": packages,
                        "source_distribution_observation": "explicitly synthetic",
                        "external_source_provider": "controlled original local process",
                        "installed_qualification": "pending",
                        "consumer_historical_qualification": "pending",
                        "calls": calls,
                    },
                    indent=2,
                )
            )
        succeeded = True
