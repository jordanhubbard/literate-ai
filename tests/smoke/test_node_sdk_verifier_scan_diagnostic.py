"""Explicit opt-in original native scan diagnostic, never SDK qualification."""

import os
import shutil
import sys
import unittest
from pathlib import Path

from tests.smoke import test_node_sdk_verifier_scan_native as fixture
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
    "requires explicit output and actual selected macOS SDK runtime fixture",
)
class NativeSDKScanDiagnosticTests(unittest.TestCase):
    def test_original_scan_diagnostic_without_qualification(self):
        root = Path(__file__).resolve().parents[2]
        output = diagnostic_output_path(
            root, os.environ["LITAI_NODE_SDK_RUNTIME_DIAGNOSTIC_OUTPUT"]
        )
        observer = SDKRuntimeDiagnostic(root)
        try:
            with observer.observe():
                fixture.NativeEnrolledSDKScanTests._exercise_original_scan(
                    self, diagnostic=observer
                )
        finally:
            # The original helper has already drained actual fixture cleanups.
            # Metadata/persistence failures must never replace its exception.
            def persist():
                persist_runtime_diagnostic(root, output, observer.snapshot())
                return True

            saved = observer._capture(persist)
            observer._capture(
                lambda: print(
                    "SDK diagnostic only; never qualification; metadata "
                    + ("persisted" if saved is True else "unavailable/incomplete"),
                    flush=True,
                )
            )
