"""Live foreign provider receipts cannot supply another SDK owner's custody."""

import os
import shutil
import sys
import unittest
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from unittest import mock

from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecycleError
from tests.smoke import test_canonical_sdk_admission as canonical


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "macOS native-observer cell requires selected Node/npm/TypeScript",
)
class ForeignProviderRegistryTests(unittest.TestCase):
    def test_live_foreign_receipts_refuse_before_grants_and_keep_local_owner(self):
        outer = canonical.CanonicalSDKAdmissionTests()
        self.addCleanup(outer.doCleanups)
        authored, probed, local_ports_seen = [], [], []

        class ProbeComplete(Exception):
            pass

        class ForeignFixture(canonical.CanonicalSDKAdmissionTests):
            def _build_canonical_provider(inner_self, root, **kwargs):
                target = (
                    root
                    / kwargs["provider_contract"]
                    .library_import_surface.declarations[0]
                    .runtime
                )
                original_write = Path.write_text

                def write(path, content, *args, **options):
                    if path == target:
                        self.assertEqual(content, "exports.add=(a,b)=>a+b;\n")
                        content += "// Independently authored foreign fixture.\n"
                        authored.append(path)
                    return original_write(path, content, *args, **options)

                # Change only authored fixture bytes before source registration.
                # BUILD, TEST, EXEC, acceptance and custody use the real owners.
                with mock.patch.object(Path, "write_text", write):
                    return super()._build_canonical_provider(root, **kwargs)

        foreign = ForeignFixture()
        self.addCleanup(foreign.doCleanups)

        def before_outer(local):
            local_ports_seen.append(local.ports)

            def before_foreign(other):
                local_receipts = {
                    receipt.component_revision.uri: receipt
                    for receipt in local.receipts
                }
                other_receipts = {
                    receipt.component_revision.uri: receipt
                    for receipt in other.receipts
                }
                self.assertEqual(len(local_receipts), 2)
                self.assertEqual(set(local_receipts), set(other_receipts))
                self.assertEqual(local.execution.identity, other.execution.identity)
                self.assertIsNot(local.ports, other.ports)
                self.assertIsNot(local.ports.source_trees, other.ports.source_trees)
                for revision, receipt in other_receipts.items():
                    self.assertNotEqual(
                        receipt.build.exports[0].blob,
                        local_receipts[revision].build.exports[0].blob,
                    )
                self.assertEqual(local.grants, [])
                self.assertEqual(other.grants, [])

                def forbidden(*_args):
                    self.fail("foreign acceptance entered the local SDK operation")

                with ExitStack() as stack:
                    scopes = [
                        stack.enter_context(
                            other.ports.accepted_library_provider(
                                receipt,
                                require_current=other.configuration.snapshot.require_unchanged,
                            )
                        )
                        for receipt in other.receipts
                    ]
                    self.assertEqual(len(other.ports._library_provider_scopes), 2)
                    for scope in scopes:
                        other.ports._require_library_provider_membership(scope)
                    with self.assertRaisesRegex(
                        LocalStandardLifecycleError,
                        "ACCEPT requires registered stages",
                    ):
                        local.admission.with_invocation(
                            local.execution,
                            local.prepared,
                            other.receipts,
                            consume=forbidden,
                        )
                    self.assertEqual(local.grants, [])
                    self.assertEqual(other.grants, [])
                    self.assertEqual(local.ports._library_provider_scopes, {})
                    self.assertEqual(local.ports._library_provider_scope_count, 0)
                    self.assertEqual(local.ports._library_provider_scope_bytes, 0)
                    for scope in scopes:
                        other.ports._require_library_provider_membership(scope)
                    probed.append(True)
                    print(
                        "Live foreign acceptance refused; original scopes retained",
                        flush=True,
                    )
                self.assertEqual(other.ports._library_provider_scopes, {})
                self.assertEqual(other.ports._library_provider_scope_count, 0)
                self.assertEqual(other.ports._library_provider_scope_bytes, 0)
                # Stop before starting an unrelated foreign SDK invocation.
                raise ProbeComplete()

            with self.assertRaises(ProbeComplete):
                foreign.with_canonical_sdk(
                    second_provider=True,
                    public_host=True,
                    provider_runtime="source/counter/runtime/add.cjs",
                    before_invocation=before_foreign,
                )
            self.assertEqual(len(authored), 2)
            self.assertEqual(probed, [True])
            self.assertEqual(local.grants, [])

        outer.with_canonical_sdk(
            second_provider=True,
            public_host=True,
            provider_runtime="source/counter/runtime/add.cjs",
            before_invocation=before_outer,
            verifier_lifetime=timedelta(minutes=10),
        )
        self.assertEqual(probed, [True])
        self.assertEqual(local_ports_seen[0]._library_provider_scopes, {})
        self.assertEqual(local_ports_seen[0]._library_provider_scope_count, 0)
        self.assertEqual(local_ports_seen[0]._library_provider_scope_bytes, 0)
