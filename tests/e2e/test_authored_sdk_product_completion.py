"""Real native SDK source-build products retain original comparison-only CAS facts."""

import copy
import pickle
import time
import unittest
from unittest.mock import patch

from literate_ai.adapters.authored_sdk_product_completion import (
    _capture_authored_sdk_products,
)
from literate_ai.adapters.native_sdk_consumer import NativeSdkConsumerInputs
from literate_ai.adapters.native_sdk_source_build import NativeSdkSourceBuildService
from literate_ai.storage.cas import BlobIntegrityError, BlobNotFoundError, FileSystemCAS
from tests.support import fixtures_test_native_sdk_consumer as fixtures


class AuthoredSdkProductCompletionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NativeSdkConsumerTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.build = self.fixture.service.build()
        self.owner = self.fixture.inputs()

    def capture(self):
        return _capture_authored_sdk_products(self.owner)

    def test_original_cas_products_survive_temporary_materialization_retirement(self):
        original = self.capture()
        with self.owner.materialize(
            self.build.selection.component_revision,
            target_identity=self.build.selection.target_identity,
            parent=self.fixture.parent,
        ) as values:
            roots = tuple(value.root for value in values)
        self.assertTrue(roots)
        self.assertTrue(all(not root.exists() for root in roots))
        self.fixture.fixture.fixture.remove_source()
        trap = AssertionError("local SDK completion invoked admission or producer")
        with (
            patch.object(
                NativeSdkConsumerInputs, "require_unchanged", side_effect=trap
            ),
            patch.object(
                NativeSdkSourceBuildService, "completed_result", side_effect=trap
            ),
            patch.object(FileSystemCAS, "__init__", side_effect=trap),
            patch.object(FileSystemCAS, "put_file", side_effect=trap),
            patch.object(FileSystemCAS, "put_bytes", side_effect=trap),
            patch("subprocess.run", side_effect=trap),
            patch("subprocess.Popen", side_effect=trap),
        ):
            original.require_original_files()
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with self.subTest(operation=operation.__name__):
                with self.assertRaises(TypeError):
                    operation(original)

    def test_each_original_metadata_and_member_blob_is_verified_without_repair(self):
        original = self.capture()
        product = self.build.product
        member = next(
            item.blob
            for item in product.snapshot.files
            if item.path == product.snapshot.native_libraries[0]
        )
        for reference in (
            product.snapshot_blob,
            product.runtime_observation,
            product.result_blob,
            member,
        ):
            with self.subTest(reference=reference.digest):
                path = self.fixture.service.store.path_for(reference)
                content = path.read_bytes()
                path.chmod(0o600)
                changed = content + b"preserve foreign corruption"
                path.write_bytes(changed)
                with self.assertRaises(BlobIntegrityError):
                    original.require_original_files()
                self.assertEqual(path.read_bytes(), changed)
                path.write_bytes(content)

    def test_missing_original_member_refuses_without_recreating_it(self):
        original = self.capture()
        reference = self.build.product.snapshot.files[0].blob
        path = self.fixture.service.store.path_for(reference)
        path.unlink()
        with self.assertRaises(BlobNotFoundError):
            original.require_original_files()
        self.assertFalse(path.exists())

    def test_same_path_replacement_store_cannot_replace_the_original_service_owner(
        self,
    ):
        original = self.capture()
        replacement = FileSystemCAS(self.fixture.service.store.root, create=False)
        self.fixture.service.store = replacement
        with self.assertRaisesRegex(ValueError, "original-sdk-products-changed"):
            original.require_original_files()
        self.assertIs(self.fixture.service.store, replacement)

    def test_original_store_coordinates_cannot_be_retargeted(self):
        original = self.capture()
        store = self.fixture.service.store
        replacement = self.fixture.parent
        store.root = replacement
        with self.assertRaisesRegex(ValueError, "original-sdk-store-changed"):
            original.require_original_files()
        self.assertEqual(store.root, replacement)

    def test_final_actual_refresh_callback_cannot_replace_original_binding(self):
        original = self.capture()
        actual = NativeSdkConsumerInputs.require_unchanged
        changed = tuple(list(self.owner._inputs))
        self.assertIsNot(changed, self.owner._inputs)
        calls = []

        def late(owner):
            result = actual(owner)
            if owner is self.owner:
                calls.append(owner)
                owner._inputs = changed
            return result

        with patch.object(NativeSdkConsumerInputs, "require_unchanged", new=late):
            with self.assertRaisesRegex(ValueError, "original-sdk-products-changed"):
                original.refresh_current(deadline=time.monotonic() + 900)
        self.assertEqual(calls, [self.owner])
        self.assertIs(self.owner._inputs, changed)

    def test_original_deadline_refuses_before_callback_and_after_actual_callback(self):
        original = self.capture()
        with patch.object(NativeSdkConsumerInputs, "require_unchanged") as refresh:
            with self.assertRaisesRegex(ValueError, "sdk-refresh-deadline-expired"):
                original.refresh_current(deadline=time.monotonic() - 1)
        refresh.assert_not_called()
        actual = NativeSdkConsumerInputs.require_unchanged
        clock = [10.0]
        calls = []

        def late(owner):
            result = actual(owner)
            if owner is self.owner:
                calls.append(owner)
                clock[0] = 12.0
            return result

        with (
            patch.object(NativeSdkConsumerInputs, "require_unchanged", new=late),
            patch(
                "literate_ai.adapters.authored_sdk_product_completion.time.monotonic",
                side_effect=lambda: clock[0],
            ),
        ):
            with self.assertRaisesRegex(ValueError, "sdk-refresh-deadline-expired"):
                original.refresh_current(deadline=11.0)
        self.assertEqual(calls, [self.owner])

    def test_invalid_deadlines_refuse_before_any_owner_callback(self):
        original = self.capture()
        for deadline in (float("nan"), float("inf"), float("-inf"), True, 0, -1, "900"):
            with self.subTest(deadline=deadline):
                with patch.object(
                    NativeSdkConsumerInputs, "require_unchanged"
                ) as refresh:
                    with self.assertRaisesRegex(
                        ValueError, "sdk-refresh-deadline-invalid"
                    ):
                        original.refresh_current(deadline=deadline)
                refresh.assert_not_called()
