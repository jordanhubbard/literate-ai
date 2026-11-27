"""Original two-provider/root-subpath scans; no production grant qualification."""

import hashlib
import json
import os
import shutil
import sys
import unittest

from literate_ai.adapters.node_sdk_verifier_scan import (
    scan_enrolled_node_verifier_inputs,
)
from tests.smoke import test_node_sdk_verifier_runtime_native as runtime_fixture


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected macOS authored SDK runtime fixture",
)
class NativeEnrolledSDKScanTests(unittest.TestCase):
    def test_original_two_provider_root_subpath_scan_and_publication(self):
        self._exercise_original_scan()

    def _exercise_original_scan(self, *, diagnostic=None):
        records = []

        def scan_capture(operation, handle, ticket):
            encoded = scan_enrolled_node_verifier_inputs(operation, handle, ticket)
            document = json.loads(encoded)
            self.assertEqual(
                document["schema"], "literate-ai/local-node-sdk-verifier-scan@1"
            )
            self.assertEqual(document["policy"]["maximum_findings"], 1024)
            self.assertLessEqual(len(document["report"]["findings"]), 1024)
            self.assertTrue(document["inventory"])
            self.assertTrue(document["report"]["module_digests"])
            schema = document["inputs_preimage"]["schema"]
            self.assertIn(
                schema,
                (
                    "literate-ai/local-node-provider-verifier-inputs@1",
                    "literate-ai/local-node-sdk-project-verifier-inputs@1",
                ),
            )
            role = "root" if "sdk-project" in schema else "provider"
            records.append(
                (operation, role, "sha256:" + hashlib.sha256(encoded).hexdigest())
            )

        runtime_fixture.NativeRuntimeInspectionEnrollmentTests._exercise_enrolled_runtime(
            self, scan_capture=scan_capture, diagnostic=diagnostic
        )
        self.assertEqual(sum(role == "root" for _, role, _ in records), 1)
        operations = {operation for operation, _, _ in records}
        self.assertGreaterEqual(len(operations), 3)
        for operation in operations:
            self.assertEqual(
                sum(op is operation and role == "provider" for op, role, _ in records),
                2,
            )
            with self.assertRaises(ValueError):
                operation.require_current()
