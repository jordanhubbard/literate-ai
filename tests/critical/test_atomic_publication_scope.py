"""A copied or rejected publication context cannot fall through to a writer."""

from __future__ import annotations

import os
import unittest
from contextvars import copy_context
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

from literate_ai import _atomic_publication as publication


class AtomicPublicationScopeTests(unittest.TestCase):
    def setUp(self):
        self.path = Path("metadata.json")
        self.writer = mock.Mock()

    def publish(self, **kwargs):
        return publication.publish_atomic_file_if_scoped(self.path, b"{}\n", **kwargs)

    def test_without_scope_ordinary_writer_is_selected(self):
        self.assertFalse(self.publish())
        self.writer.publish.assert_not_called()

    def test_original_payload_and_currentness_callback_reach_the_bound_writer(self):
        current = mock.Mock()
        with publication.atomic_publication_scope(self.writer):
            self.assertTrue(self.publish(require_current=current, preserve_mode=True))
        self.writer.publish.assert_called_once_with(
            self.path, b"{}\n", require_current=current, preserve_mode=True
        )
        self.assertFalse(self.publish())

    def test_writer_refusal_propagates_and_closes_the_scope(self):
        self.writer.publish.side_effect = ValueError("foreign node")
        with self.assertRaisesRegex(ValueError, "foreign node"):
            with publication.atomic_publication_scope(self.writer):
                self.publish()
        self.assertFalse(self.publish())
        self.writer.publish.assert_called_once()

    def test_copied_context_cannot_reactivate_a_closed_scope(self):
        with publication.atomic_publication_scope(self.writer):
            copied = copy_context()
        with self.assertRaises(publication.AtomicPublicationScopeError):
            copied.run(self.publish)
        self.writer.publish.assert_not_called()

    def test_process_mismatch_refuses_without_a_fallback(self):
        original_pid = os.getpid()
        with publication.atomic_publication_scope(self.writer):
            with mock.patch.object(
                publication.os, "getpid", return_value=original_pid + 1
            ):
                with self.assertRaises(publication.AtomicPublicationScopeError):
                    self.publish()
        self.writer.publish.assert_not_called()

    def test_nested_scope_refuses_without_replacing_original_receiver(self):
        other = mock.Mock()
        with publication.atomic_publication_scope(self.writer):
            with self.assertRaises(publication.AtomicPublicationScopeError):
                with publication.atomic_publication_scope(other):
                    self.fail("nested writer acquired the original scope")
            self.assertTrue(self.publish())
        self.writer.publish.assert_called_once()
        other.publish.assert_not_called()

    def test_invalid_scoped_input_refuses_before_the_receiver(self):
        with publication.atomic_publication_scope(self.writer):
            with self.assertRaises(TypeError):
                publication.publish_atomic_file_if_scoped(self.path, bytearray(b"{}"))
        self.writer.publish.assert_not_called()

    def test_scope_uses_original_bound_publisher_after_class_slot_changes(self):
        original, foreign = [], []

        class Writer:
            def publish(self, *args, **kwargs):
                original.append((args, kwargs))

        writer = Writer()
        with publication.atomic_publication_scope(writer):
            with mock.patch.object(
                Writer, "publish", lambda *_a, **_k: foreign.append(True)
            ):
                self.assertTrue(self.publish())
        self.assertEqual(len(original), 1)
        self.assertEqual(foreign, [])

    def test_receiver_and_bound_delegate_cannot_be_reassigned_in_live_scope(self):
        with publication.atomic_publication_scope(self.writer):
            scope = publication._ACTIVE.get()
            for name, value in (
                ("writer", mock.Mock()),
                ("publisher", mock.Mock()),
                ("pid", 0),
            ):
                with self.assertRaises(FrozenInstanceError):
                    setattr(scope, name, value)
            self.assertTrue(self.publish())
        self.writer.publish.assert_called_once()

    def test_original_reader_delegate_cannot_expand_after_scope_entry(self):
        class Writer:
            def publish(self, *args, **kwargs):
                pass

            def permits_project_read(self, root):
                return False

        writer = Writer()
        with publication.atomic_publication_scope(writer):
            with mock.patch.object(Writer, "permits_project_read", lambda *_a: True):
                self.assertFalse(
                    publication.scoped_writer_permits_project_read(Path("."))
                )
