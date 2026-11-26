"""Actual owner/CAS retention of already-read Cargo data, no compiler execution."""

import os
import unittest
from unittest import mock

from literate_ai.application import native_root_failed_stage as capture
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from tests.critical import test_native_root_failed_stage_capture as fixture


@unittest.skipUnless(os.name == "posix", "existing original owner fixture")
class NativeRootCargoAttributionPreimageTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixture.NativeRootFailedStageCaptureTests()
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)

    def test_exact_already_read_lock_and_native_record_retained_before_process(self):
        lock = b'version = 4\n[[package]]\nname="modeled-root"\nversion="1.0.0"\n'
        native = {"schema": "modeled-public-native-evidence", "value": 1}
        original = capture.prepare_native_root_cargo_attribution

        def prepare(*arguments):
            return original(*arguments, lock_bytes=lock, native_evidence=native)

        with self.fx.operation() as (scope, _controller, plan):
            with capture.observe_native_root_stage(self.fx.ports, plan, "build"):
                with mock.patch.object(
                    capture,
                    "prepare_native_root_cargo_attribution",
                    side_effect=prepare,
                ):
                    self.fx.cargo_completion(plan)
                cap = capture._ACTIVE.get()
                row = cap.cargo[1]
                self.assertEqual(
                    row["schema"], "literate-ai/native-root-cargo-attribution@2"
                )
                lock_id = row["lockfile_identity"]
                self.assertEqual(
                    scope._evidence.get_bytes(
                        BlobRef(lock_id.removeprefix("sha256:"), len(lock))
                    ),
                    lock,
                )
                encoded = canonical_json_bytes(native)
                self.assertEqual(
                    row["native_provider_evidence_identity"],
                    canonical_identity(native).uri,
                )
                self.assertEqual(
                    scope._evidence.get_bytes(
                        BlobRef(canonical_identity(native).digest, len(encoded))
                    ),
                    encoded,
                )
                self.assertEqual(cap.processes, [])

    def test_no_native_graph_has_explicit_none_and_old_fixture_shape_stays_v1(self):
        original = capture.prepare_native_root_cargo_attribution
        with self.fx.operation() as (_scope, _controller, plan):
            with capture.observe_native_root_stage(self.fx.ports, plan, "build"):
                with mock.patch.object(
                    capture,
                    "prepare_native_root_cargo_attribution",
                    side_effect=lambda *args: original(
                        *args, lock_bytes=b"public lock"
                    ),
                ):
                    self.fx.cargo_completion(plan)
                row = capture._ACTIVE.get().cargo[1]
                self.assertEqual(
                    row["schema"], "literate-ai/native-root-cargo-attribution@2"
                )
                self.assertIsNone(row["native_provider_evidence_identity"])
        with self.fx.operation() as (_scope, _controller, plan):
            with capture.observe_native_root_stage(self.fx.ports, plan, "build"):
                self.fx.cargo_completion(plan)
                row = capture._ACTIVE.get().cargo[1]
                self.assertEqual(
                    row["schema"], "literate-ai/native-root-cargo-attribution@1"
                )
                self.assertNotIn("lockfile_identity", row)

    def test_no_active_native_capture_does_not_inspect_new_data_arguments(self):
        with mock.patch.object(capture, "_ACTIVE") as active:
            active.get.return_value = None
            self.assertFalse(
                capture.prepare_native_root_cargo_attribution(
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    lock_bytes=object(),
                    native_evidence=object(),
                )
            )
