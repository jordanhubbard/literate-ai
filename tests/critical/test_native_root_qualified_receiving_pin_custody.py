"""Real bounded file-pin closure controls; project loader is a protocol model."""

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_root_qualified_receiving as receiving
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity
from literate_ai.projects import PinnedInputClosure
from tests.critical import test_native_root_qualified_receiving_public as public_fixture


class ConfiguredReceivingPinCustodyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        content = b'{"project":"modeled loader; real pinned bytes"}'
        manifest = self.root / "literate.project.json"
        manifest.write_bytes(content)
        self.path = self.root / "receivers.json"
        self.path.write_text(json.dumps(public_fixture.configuration()))
        definition = SimpleNamespace(identity=canonical_identity("fixture-definition"))
        self.project = SimpleNamespace(root=self.root, definition=definition)
        current = SimpleNamespace(
            root=self.root,
            definition=definition,
            manifest_path=manifest,
            content=content,
        )
        store = self.enterContext(
            mock.patch.object(receiving, "ProjectConfigurationStore")
        )
        store.return_value.read.return_value = current
        self.operation = self.enterContext(
            receiving.configured_qualified_library_receivers(self.project, self.path)
        )
        self.pins = self.operation._original_pins

    def test_replacement_before_first_refresh_refuses_without_foreign_guard(self):
        foreign = mock.Mock()
        self.operation._pins = foreign
        try:
            with self.assertRaisesRegex(ValueError, "receiving_pin_custody_changed"):
                self.operation._configuration_guard()
            foreign.require_unchanged.assert_not_called()
        finally:
            self.operation._pins = self.pins

    def test_callback_replacement_during_original_file_read_refuses_on_close(self):
        original_read = PinnedInputClosure._read
        foreign = mock.Mock()

        def changed(pins, *args, **kwargs):
            result = original_read(pins, *args, **kwargs)
            self.operation._pins = foreign
            return result

        try:
            with mock.patch.object(
                PinnedInputClosure, "_read", autospec=True, side_effect=changed
            ):
                with self.assertRaisesRegex(
                    ValueError, "receiving_pin_custody_changed"
                ):
                    self.operation._configuration_guard()
            foreign.require_unchanged.assert_not_called()
        finally:
            self.operation._pins = self.pins

    def test_cleared_original_entries_refuse_before_guard_can_become_noop(self):
        original = tuple(self.pins._entries.items())
        self.pins._entries.clear()
        try:
            with self.assertRaisesRegex(ValueError, "receiving_pin_closure_changed"):
                self.operation._configuration_guard()
        finally:
            self.pins._entries.update(original)

    def test_same_portable_identity_cannot_replace_original_file_coordinate(self):
        original = dict(self.pins._entries)
        key, row = next(iter(original.items()))
        replacement = replace(row, path=self.root / "foreign.json")
        self.pins._entries[key] = replacement
        try:
            self.assertEqual(self.pins.identity, self.operation._original_pins_identity)
            with self.assertRaisesRegex(ValueError, "receiving_pin_closure_changed"):
                self.operation._configuration_guard()
        finally:
            self.pins._entries.clear()
            self.pins._entries.update(original)

    def test_guard_method_replacement_refuses_without_invoking_foreign(self):
        foreign = mock.Mock()
        self.pins.require_unchanged = foreign
        try:
            with self.assertRaisesRegex(ValueError, "receiving_pin_custody_changed"):
                self.operation._configuration_guard()
            foreign.assert_not_called()
        finally:
            del self.pins.require_unchanged

    def test_original_guard_error_keeps_exact_identity(self):
        original = RuntimeError("original file owner refused")
        with mock.patch.object(PinnedInputClosure, "_read", side_effect=original):
            with self.assertRaises(RuntimeError) as caught:
                self.operation._configuration_guard()
        self.assertIs(caught.exception, original)

    def test_only_trusted_selection_extension_advances_identity_then_stays_fresh(self):
        source = self.root / "selection.json"
        content = b'{"strict":"asset content"}'
        source.write_bytes(content)
        asset = SimpleNamespace(
            blob=BlobRef(
                hashlib.sha256(content).hexdigest(),
                len(content),
                media_type="application/json",
            )
        )
        previous = self.operation._original_pins_identity
        self.assertEqual(self.operation._pin_selection(source, asset), content)
        self.assertNotEqual(self.operation._original_pins_identity, previous)
        self.assertEqual(self.pins.file_count, 3)
        self.operation._configuration_guard()
        source.write_bytes(b"changed")
        try:
            with self.assertRaises(ValueError):
                self.operation._configuration_guard()
        finally:
            source.write_bytes(content)

    def test_pin_method_substitution_cannot_capture_new_selection(self):
        foreign = mock.Mock()
        self.pins.pin = foreign
        try:
            with self.assertRaisesRegex(ValueError, "receiving_pin_custody_changed"):
                self.operation._pin_selection(self.root / "never-read", object())
            foreign.assert_not_called()
        finally:
            del self.pins.pin
