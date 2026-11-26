"""Real local v2 receiving/namespace custody with modeled producer qualification.

These controls exercise existing strict archive reopening and actual package
trees. They do not execute or qualify a native producer/consumer, grant host
execution, or implement the separate held-provider planning/membership boundary.
"""

import copy
import inspect
import os
import pickle
import shutil
import unittest
from dataclasses import asdict, fields, replace
from unittest import mock

from literate_ai.adapters import native_root_qualified_provider as bridge
from literate_ai.adapters.native_sdk_consumer import NativeSdkConsumerInput
from literate_ai.adapters.qualification_capture import QualificationRunCapture
from literate_ai.application import native_root_run
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from tests.support.fixtures_retained_cargo_receiving_v2 import (
    initialize_retained_cargo_receiving_v2_fixture,
    receive_retained_cargo_fixture,
)


@unittest.skipUnless(
    os.name == "posix" and shutil.which("git") and shutil.which("make"),
    "local v2 receiving fixture requires POSIX adoption/Git/Make",
)
class NativeRootQualifiedProviderTests(unittest.TestCase):
    def setUp(self):
        initialize_retained_cargo_receiving_v2_fixture(self)

    def receive(self):
        return receive_retained_cargo_fixture(self)

    def test_runtime_metadata_is_exact_selected_run_not_last_member(self):
        materialized = self.receive()
        capture = materialized.capture
        result = materialized.current.current.promotion.qualification_lifecycle_result
        self.assertGreaterEqual(len(result.runs), 2)
        self.assertNotEqual(capture.run.run_identity, result.runs[-1].run_identity)
        self.assertEqual(
            capture.verified_lifecycle.identity, capture.run.lifecycle_result_identity
        )
        self.assertNotEqual(
            capture.verified_lifecycle.identity,
            result.runs[-1].lifecycle_result_identity,
        )

    def test_four_field_constructor_dataclass_json_equality_repr_stay_unchanged(self):
        capture = self.receive().capture
        names = ("run", "exports", "acceptances", "blobs")
        self.assertEqual(tuple(field.name for field in fields(capture)), names)
        self.assertEqual(
            tuple(inspect.signature(QualificationRunCapture).parameters), names
        )
        self.assertEqual(tuple(asdict(capture)), names)
        ordinary = replace(capture)
        self.assertIsNone(ordinary.verified_lifecycle)
        self.assertEqual(capture, ordinary)
        self.assertEqual(repr(capture), repr(ordinary))
        with self.assertRaises(TypeError):
            QualificationRunCapture(
                capture.run,
                capture.exports,
                capture.acceptances,
                capture.blobs,
                verified_lifecycle=capture.verified_lifecycle,
            )

    def test_pickle_copy_and_replace_never_restore_verified_runtime_metadata(self):
        capture = self.receive().capture
        self.assertEqual(len(capture.__getstate__()), 4)
        for cloned in (
            copy.copy(capture),
            copy.deepcopy(capture),
            pickle.loads(pickle.dumps(capture)),
            replace(capture),
        ):
            with self.subTest(copy_type=type(cloned)):
                self.assertEqual(cloned, capture)
                self.assertIsNone(cloned.verified_lifecycle)

    def test_held_binding_joins_actual_root_product_receipts_and_original_source(self):
        materialized = self.receive()
        with bridge.hold_native_root_qualified_provider(materialized) as held:
            node, binding = held.root_node, held.binding
            self.assertIs(held.lifecycle, materialized.capture.verified_lifecycle)
            self.assertEqual(
                binding.component_revision,
                materialized.current.current.authority.lock.root_revision,
            )
            self.assertEqual(
                binding.acceptance_identity, node.acceptance_evidence.identity
            )
            self.assertEqual(binding.qualified_product_identity, held.product.identity)
            self.assertEqual(
                binding.source_provenance_identity,
                node.source_output.provenance.identity,
            )
            self.assertEqual(held.source_output, node.source_output)
            self.assertEqual(held.build_plan.identity, node.build_plan_identity)
            self.assertEqual(
                held.product.native_layout,
                materialized.current.current.current_commands[
                    binding.component_revision
                ].native_layout,
            )
            self.assertEqual(
                binding.artifact_export_identities,
                tuple(export.identity for export in held.exports),
            )
            self.assertTrue(binding.toolchain_binding_identities)
            self.assertEqual(binding.sdk_binding_identities, ())
            self.assertIn(node.acceptance_evidence, held.accepted_receipts)
            self.assertEqual(held.root_integration, held.lifecycle.root_integration)
            self.assertEqual(
                held.run.run_identity, materialized.capture.run.run_identity
            )
            self.assertEqual(
                held.qualification_result.identity,
                materialized.files.reviewed.binding.common.qualification_identity,
            )
            payloads = dict(materialized.capture.blobs)
            for export in held.exports:
                self.assertEqual(
                    held.read_artifact_blob(export.blob), payloads[export.blob]
                )
        with self.assertRaisesRegex(bridge.NativeRootQualifiedProviderError, "closed"):
            held.require_current()
        # This layer never closes another owner's receiving namespace.
        materialized.require_unchanged()

    def test_bare_records_missing_metadata_and_ordinary_sdk_data_cannot_admit(self):
        materialized = self.receive()
        for value in (
            materialized.capture,
            materialized.capture.exports,
            materialized.capture.verified_lifecycle,
            # Portable SDK descriptor shape only; no SDK build or qualification.
            NativeSdkConsumerInput(build=object()),
            object(),
        ):
            with self.subTest(value_type=type(value)), self.assertRaises(ValueError):
                with bridge.hold_native_root_qualified_provider(value):
                    self.fail("ordinary data restored a qualified provider")
        capture = materialized.capture
        object.__setattr__(materialized, "capture", replace(capture))
        try:
            with self.assertRaisesRegex(ValueError, "verified_lifecycle_required"):
                with bridge.hold_native_root_qualified_provider(materialized):
                    self.fail("unverified capture admitted")
        finally:
            object.__setattr__(materialized, "capture", capture)

    def test_equal_capture_replacement_closes_original_holder_permanently(self):
        materialized = self.receive()
        capture = materialized.capture
        with bridge.hold_native_root_qualified_provider(materialized) as held:
            substituted = replace(capture)
            object.__setattr__(
                substituted, "_verified_lifecycle", capture.verified_lifecycle
            )
            object.__setattr__(materialized, "capture", substituted)
            try:
                with self.assertRaises(ValueError):
                    held.require_current()
            finally:
                object.__setattr__(materialized, "capture", capture)
            with self.assertRaisesRegex(ValueError, "closed"):
                held.require_current()

    def test_other_lifecycle_metadata_cannot_become_selected_provider_proof(self):
        materialized = self.receive()
        capture = materialized.capture
        original = capture.verified_lifecycle
        changed = replace(original, validation_identity=canonical_identity("other-run"))
        object.__setattr__(capture, "_verified_lifecycle", changed)
        try:
            with self.assertRaisesRegex(ValueError, "qualification_mismatch"):
                with bridge.hold_native_root_qualified_provider(materialized):
                    self.fail("foreign lifecycle became selected qualification")
        finally:
            object.__setattr__(capture, "_verified_lifecycle", original)

    def test_package_byte_change_revokes_live_held_input(self):
        materialized = self.receive()
        with bridge.hold_native_root_qualified_provider(materialized) as held:
            tree = materialized.packages[0]
            path = tree.root / tree.files[0].path
            path.write_bytes(b"changed qualified package")
            with self.assertRaises(ValueError):
                held.require_current()
            with self.assertRaisesRegex(ValueError, "closed"):
                held.read_artifact_blob(held._values.exports[0].blob)

    def test_rebasing_package_guard_cannot_adopt_changed_qualified_bytes(self):
        materialized = self.receive()
        with bridge.hold_native_root_qualified_provider(materialized) as held:
            tree = materialized.packages[0]
            changed = replace(tree.files[0], content=b"replacement bytes")
            (tree.root / changed.path).write_bytes(changed.content)
            files = (changed, *tree.files[1:])
            directories, nodes = tree._observe(tree.root, files)
            object.__setattr__(tree, "files", files)
            object.__setattr__(tree, "directories", directories)
            object.__setattr__(tree, "nodes", nodes)
            tree.require_unchanged()
            with self.assertRaisesRegex(ValueError, "binding_changed"):
                held.require_current()

    def test_original_scratch_scope_end_revokes_holder(self):
        materialized = self.receive()
        with bridge.hold_native_root_qualified_provider(materialized) as held:
            self.scratch_manager.__exit__(None, None, None)
            with self.assertRaises(ValueError):
                held.require_current()

    def test_holder_and_portable_binding_cannot_restore_live_ownership(self):
        materialized = self.receive()
        with bridge.hold_native_root_qualified_provider(materialized) as held:
            for operation in (
                lambda: copy.copy(held),
                lambda: copy.deepcopy(held),
                lambda: pickle.dumps(held),
                bridge.HeldNativeRootQualifiedProvider,
            ):
                with self.subTest(operation=operation), self.assertRaises(TypeError):
                    operation()
            decoded = type(held.binding).from_dict(held.binding.to_dict())
            with self.assertRaises(ValueError):
                with bridge.hold_native_root_qualified_provider(decoded):
                    self.fail("decoded evidence restored original namespace")
            with mock.patch.object(bridge.os, "getpid", return_value=os.getpid() + 1):
                with self.assertRaisesRegex(ValueError, "owner_invalid"):
                    held.require_current()

    def test_unknown_blob_is_not_available_through_held_export_reader(self):
        materialized = self.receive()
        with bridge.hold_native_root_qualified_provider(materialized) as held:
            with self.assertRaisesRegex(ValueError, "blob_not_held"):
                held.read_artifact_blob(BlobRef("0" * 64, 0))

    def test_existing_original_run_is_retained_without_minting_another_deadline(self):
        materialized = self.receive()
        with (
            native_root_run.open_native_root_run(
                NativeRootRunPolicy(120, 3),
                project_identity=canonical_identity("consumer"),
                framework_distribution_identity=canonical_identity("framework"),
                lifecycle_policy_identity=canonical_identity("policy"),
                require_current=lambda: None,
            ) as original,
            native_root_run.activate_native_root_run(original),
        ):
            with bridge.hold_native_root_qualified_provider(materialized) as held:
                self.assertIs(held._run, original)
                original.close()
                with self.assertRaises(native_root_run.NativeRootRunError):
                    held.require_current()
