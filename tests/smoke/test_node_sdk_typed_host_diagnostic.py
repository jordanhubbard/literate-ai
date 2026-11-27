"""Explicit sampling-only typed runtime diagnostic; never native qualification."""

import os
import shutil
import sys
import unittest
from pathlib import Path

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_sdk_verifier_authority as membership
from literate_ai.adapters import node_sdk_verifier_authorization as authority
from literate_ai.adapters import node_sdk_verifier_runtime as runtime
from literate_ai.adapters.process_liveness import _close_preserving_primary_failure
from tests.smoke import test_canonical_sdk_runtime as fixture
from tests.support.sdk_runtime_diagnostic import (
    SDKRuntimeDiagnostic,
    diagnostic_output_path,
    persist_runtime_diagnostic,
)


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node")
    and os.environ.get("LITAI_NODE_SDK_RUNTIME_DIAGNOSTIC_OUTPUT"),
    "requires explicit diagnostic output and actual selected macOS SDK inputs",
)
class TypedHostSamplingDiagnosticTests(unittest.TestCase):
    def test_original_typed_runtime_sampling_without_qualification(self):
        root = Path(__file__).resolve().parents[2]
        output = diagnostic_output_path(
            root, os.environ["LITAI_NODE_SDK_RUNTIME_DIAGNOSTIC_OUTPUT"]
        )
        observer = SDKRuntimeDiagnostic(root)
        scenario = fixture.CanonicalSDKRuntimeTests()

        def resources():
            return (
                captures._RESOURCE_POOL.statistics(),
                len(captures._LIVE),
                len(captures._RESERVED),
                len(captures._PENDING_CLEANUP),
                len(runtime._OPERATIONS),
                len(runtime._GRANT_OPERATIONS),
                len(authority._OPERATION_GRANTS),
                len(membership._ACKNOWLEDGEMENTS),
            )

        baseline = resources()
        try:
            with observer.observe(observe_grants=False):
                primary = None
                try:
                    scenario._exercise_authored_runtime(
                        second_provider=True,
                        public_subpath=True,
                        provider_runtime="source/counter/runtime/add.cjs",
                        typed_verifier=True,
                    )
                except BaseException as error:
                    primary = error
                    raise
                finally:

                    def cleanup():
                        cleaned = scenario.doCleanups()
                        settled = resources() == baseline
                        observer.record_lifecycle_cleanup(cleaned is True and settled)
                        if cleaned is not True or not settled:
                            raise RuntimeError(
                                "original typed fixture cleanup incomplete"
                            )

                    _close_preserving_primary_failure(cleanup, primary)
        finally:

            def persist():
                persist_runtime_diagnostic(root, output, observer.snapshot())
                return True

            saved = observer._capture(persist)
            observer._capture(
                lambda: print(
                    "Typed SDK sampling diagnostic only; never qualification; metadata "
                    + ("persisted" if saved is True else "unavailable/incomplete"),
                    flush=True,
                )
            )
