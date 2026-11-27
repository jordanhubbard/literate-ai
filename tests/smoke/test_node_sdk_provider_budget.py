"""Actual two-provider custody budget refusal, separate from SDK lifecycle proof."""

import os
import shutil
import sys
import unittest
from unittest import mock

from literate_ai.adapters.lifecycle import standard_local
from tests.smoke import test_canonical_sdk_admission as canonical


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "macOS native-observer cell requires selected Node/npm/TypeScript",
)
class CanonicalSDKProviderBudgetTests(unittest.TestCase):
    def test_second_actual_provider_exhausts_aggregate_custody_byte_budget(self):
        fixture = canonical.CanonicalSDKAdmissionTests()
        self.addCleanup(fixture.doCleanups)
        observed, ports_seen, grants_seen = [], [], []

        def observer(_request, rows, grants, ports):
            if observed:
                return
            self.assertEqual(len(rows), 2)
            self.assertEqual(grants, [])
            self.assertEqual(ports._library_provider_scope_count, 1)
            self.assertEqual(len(ports._library_provider_scopes), 1)
            charged = ports._library_provider_scope_bytes
            self.assertGreater(charged, 0)
            self.assertLess(charged, standard_local._MAX_LIBRARY_PROVIDER_SCOPE_BYTES)
            # Lower this fixture's budget to the first real scope's charge.
            # The original bytes, receipts and accounting owner are unchanged.
            patcher = mock.patch.object(
                standard_local, "_MAX_LIBRARY_PROVIDER_SCOPE_BYTES", charged
            )
            patcher.start()
            self.addCleanup(patcher.stop)
            observed.append(charged)
            ports_seen.append(ports)
            grants_seen.append(grants)
            print("SDK aggregate custody budget set to first live charge", flush=True)

        def forbidden(*_args):
            self.fail("SDK operation entered after aggregate custody exhaustion")

        with self.assertRaisesRegex(
            standard_local.LocalStandardLifecycleError,
            "library provider custody capacity exhausted",
        ):
            fixture.with_canonical_sdk(
                forbidden,
                second_provider=True,
                public_host=True,
                verifier_observer=observer,
            )
        self.assertEqual(len(observed), 1)
        self.assertEqual(len(grants_seen[0]), 1)
        self.assertEqual(ports_seen[0]._library_provider_scope_count, 0)
        self.assertEqual(ports_seen[0]._library_provider_scope_bytes, 0)
        self.assertEqual(ports_seen[0]._library_provider_scopes, {})
