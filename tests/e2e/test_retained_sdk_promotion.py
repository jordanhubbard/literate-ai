"""Real native SDK capture and historical context joins; no installed release claim.

The maintained fixture supplies the external Standard binding/project placement.
SDK production, commands, admission and captured CAS metadata use their real owners.
"""

import os
import shutil
import unittest
from unittest.mock import patch

from literate_ai.adapters.retained_project_inputs import verify_retained_project_inputs
from literate_ai.adapters.retained_project_runtime import execute_local_retained_project
from literate_ai.adapters.retained_receipt_promotion_evidence import (
    read_retained_receipt_promotion_evidence,
)
from literate_ai.adapters.retained_sdk_authority import current_retained_sdk_snapshots
from literate_ai.contracts import ContentIdentity
from tests.e2e import test_retained_sdk_public as fixtures
from tests.support.fixtures_public_retained_promotion import forge_public_run_evidence

LITAI_TEST_PRIORITY = 10
LITAI_TEST_SERIAL = True


@unittest.skipUnless(
    os.name != "nt" and shutil.which("cc") and shutil.which("cmake"),
    "requires native POSIX CMake SDK fixture",
)
class RetainedSdkPromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.PublicRetainedSdkRuntimeTests.setUpClass.__func__(cls)

    setUp = fixtures.PublicRetainedSdkRuntimeTests.setUp
    public_runtime_arguments = (
        fixtures.PublicRetainedSdkRuntimeTests.public_runtime_arguments
    )

    def test_sdk_capture_reopens_readonly_and_rejects_coherent_command_context_forgery(
        self,
    ):
        args, kwargs = self.public_runtime_arguments()
        captured = []
        with patch(
            "literate_ai.adapters.retained_sdk_authority.project_component_roots",
            return_value=(self.sdk_fixture.recipe_fixture.component,),
        ):
            admission, _workspace = execute_local_retained_project(
                *args, **kwargs, promotion_evidence_consumer=captured.append
            )
            self.assertEqual(len(captured), 1)
            snapshots = current_retained_sdk_snapshots(
                kwargs["sdk_project"], kwargs["component_locks"]
            )
            store = admission.store

            def reopen(receipt_identity, evidence_identity):
                with (
                    patch.object(
                        store,
                        "put_bytes",
                        side_effect=AssertionError("historical read wrote CAS"),
                    ),
                    patch(
                        "literate_ai.adapters.retained_project_execution.run_bounded_process",
                        side_effect=AssertionError(
                            "historical read executed a retained command"
                        ),
                    ),
                    patch(
                        "literate_ai.adapters.retained_project_acceptance.run_bounded_process",
                        side_effect=AssertionError(
                            "historical read executed acceptance"
                        ),
                    ),
                    patch(
                        "literate_ai.adapters.retained_project_sdk_runtime.NativeSdkProjectAcquisition",
                        side_effect=AssertionError(
                            "historical read acquired SDK execution authority"
                        ),
                    ),
                ):
                    return read_retained_receipt_promotion_evidence(
                        store,
                        receipt_identity,
                        evidence_identity,
                        source=args[0],
                        source_manifest=args[1],
                        planning=args[2],
                        component_locks=kwargs["component_locks"],
                        test_receipt_policy=kwargs["test_receipt_policy"],
                        require_current=lambda: verify_retained_project_inputs(
                            args[0], args[1]
                        ),
                        current_sdk_snapshots=snapshots,
                    )

            _inputs, completed, _assertion = reopen(
                admission.receipt.identity,
                ContentIdentity.parse_uri(captured[0].identity),
            )
            self.assertEqual(completed.identity, admission.run.identity)
            for kind in ("command-environment", "command-dependency"):
                with self.subTest(coherent_forgery=kind):
                    receipt, evidence = forge_public_run_evidence(
                        store, admission.receipt.to_dict(), captured[0], kind=kind
                    )
                    with self.assertRaisesRegex(
                        ValueError,
                        "retained.sdk.historical-command-observation-context-differs",
                    ):
                        reopen(
                            ContentIdentity.parse_uri(receipt.identity),
                            ContentIdentity.parse_uri(evidence.identity),
                        )
