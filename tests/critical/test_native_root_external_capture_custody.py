"""Capture operation owner seals; foreign provider currentness is modeled."""

import unittest
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_external_runtime as runtime
from literate_ai.adapters.qualification import (
    FilesystemQualificationError,
    FilesystemStandardQualificationAdapter,
)


class QualifiedCaptureClosingCustodyTests(unittest.TestCase):
    def setUp(self):
        self.owner = SimpleNamespace(
            _asset=SimpleNamespace(component_revision=object())
        )
        self.prepared = SimpleNamespace(qualified_library_inputs=self.owner)
        self.lifecycle = SimpleNamespace(prepared=self.prepared)
        self.reader = mock.Mock()
        self.adapter = object.__new__(FilesystemStandardQualificationAdapter)
        self.adapter.lifecycle = self.lifecycle
        self.adapter._original_qualified_library_inputs = self.owner
        self.adapter._qualified_library_archive_reader = self.reader
        self.adapter._original_qualified_library_archive_reader = self.reader
        self.data = object()
        self.project = self.enterContext(
            mock.patch.object(
                runtime, "qualified_library_runtime_data", return_value=self.data
            )
        )

    def refuse_mutation(self, callback):
        def mutate(*args):
            callback()
            return self.data

        self.project.side_effect = mutate
        with self.assertRaises(FilesystemQualificationError) as caught:
            self.adapter._qualified_capture_data()
        self.assertEqual(caught.exception.code, "qualification.qualified_owner_changed")
        self.assertEqual(self.project.call_count, 1)
        self.reader.assert_not_called()

    def test_reader_replacement_during_provider_projection_refuses(self):
        self.refuse_mutation(
            lambda: setattr(
                self.adapter, "_qualified_library_archive_reader", mock.Mock()
            )
        )

    def test_lifecycle_replacement_with_same_prepared_object_refuses(self):
        self.refuse_mutation(
            lambda: setattr(
                self.adapter, "lifecycle", SimpleNamespace(prepared=self.prepared)
            )
        )

    def test_prepared_replacement_with_same_original_owner_refuses(self):
        self.refuse_mutation(
            lambda: setattr(
                self.lifecycle,
                "prepared",
                SimpleNamespace(qualified_library_inputs=self.owner),
            )
        )

    def test_original_reader_slot_replacement_also_refuses(self):
        self.refuse_mutation(
            lambda: setattr(
                self.adapter, "_original_qualified_library_archive_reader", mock.Mock()
            )
        )

    def test_original_owner_slot_replacement_also_refuses(self):
        self.refuse_mutation(
            lambda: setattr(
                self.adapter, "_original_qualified_library_inputs", object()
            )
        )

    def test_foreign_guard_error_identity_is_preserved(self):
        original = RuntimeError("original held provider expired")
        self.project.side_effect = original
        with self.assertRaises(RuntimeError) as caught:
            self.adapter._qualified_capture_data()
        self.assertIs(caught.exception, original)

    def test_absent_owner_preserves_legacy_no_projection(self):
        self.adapter._original_qualified_library_inputs = None
        self.prepared.qualified_library_inputs = None
        self.assertIsNone(self.adapter._qualified_capture_data())
        self.project.assert_not_called()
