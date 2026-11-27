"""Finite DATA observation release; no original runtime or execution authority."""

import gc
import hashlib
import sys
import unittest
from unittest import mock

from literate_ai.adapters.models.coding_cli import RecipeDocument
from literate_ai.adapters.node_sdk_verifier_runtime import _finite_metadata


class FiniteMetadataReleaseTests(unittest.TestCase):
    def test_default_callable_api_is_preserved(self):
        root = {"items": [1, "two"]}
        guard = _finite_metadata(root)
        self.assertTrue(callable(guard))
        guard()
        root["items"].append(3)
        with self.assertRaises(ValueError):
            guard()

    def test_release_selection_requires_exact_bool(self):
        for invalid in (0, 1, None, "true", object()):
            with (
                self.subTest(kind=type(invalid).__name__),
                self.assertRaises(TypeError),
            ):
                _finite_metadata({}, _with_release=invalid)

    def test_release_is_idempotent_and_refuses_even_restored_state(self):
        root = {"items": [1]}
        guard, release, estimate = _finite_metadata(root, _with_release=True)
        guard()
        self.assertGreater(estimate, 0)
        release()
        release()
        with self.assertRaisesRegex(ValueError, "released"):
            guard()

    def test_estimate_includes_original_mapping_keys(self):
        root = {"source-key": bytes(bytearray(b"original-source"))}
        guard, release, estimate = _finite_metadata(root, _with_release=True)
        self.addCleanup(release)
        self.assertEqual(estimate, len("source-key") + len(b"original-source"))
        guard()

    def test_release_severs_source_with_validation_traceback_retained(self):
        source = bytes(bytearray(b"private observation source"))
        root = {"source": source}
        gc.collect()
        baseline = sys.getrefcount(source)
        guard, release, _estimate = _finite_metadata(root, _with_release=True)
        root["source"] = b"changed"
        retained = None
        try:
            guard()
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.assertIsNotNone(retained.__traceback__)
        self.addCleanup(setattr, retained, "__traceback__", None)
        release()
        self.assertEqual(sys.getrefcount(source), baseline - 1)
        with self.assertRaisesRegex(ValueError, "released"):
            guard()

    def test_supported_source_record_partial_read_failure_releases_through_traceback(
        self,
    ):
        source = bytearray(b"source-bearing original recipe content").decode()
        document = RecipeDocument(
            "fixture.md",
            source,
            "sha256:" + hashlib.sha256(source.encode()).hexdigest(),
        )
        gc.collect()
        baseline = sys.getrefcount(source)
        guard, release, _estimate = _finite_metadata(document, _with_release=True)
        retained = None
        called = []
        with mock.patch.object(
            RecipeDocument, "identity", property(lambda _: called.append(True))
        ):
            try:
                guard()
            except ValueError as error:
                retained = error
        self.assertIsNotNone(retained)
        self.assertIsNotNone(retained.__traceback__)
        self.addCleanup(setattr, retained, "__traceback__", None)
        object.__setattr__(document, "content", "replacement after observation failure")
        release()
        self.assertFalse(called)
        self.assertEqual(sys.getrefcount(source), baseline - 1)

    def test_supported_record_factory_failure_severs_its_partial_field_buffer(self):
        source = bytearray(b"source-bearing recipe before factory failure").decode()
        document = RecipeDocument(
            "fixture.md",
            source,
            "sha256:" + hashlib.sha256(source.encode()).hexdigest(),
        )
        gc.collect()
        baseline = sys.getrefcount(source)
        retained = None
        with mock.patch.object(
            RecipeDocument,
            "identity",
            property(lambda _: self.fail("substituted getter invoked")),
        ):
            try:
                _finite_metadata(document, _with_release=True)
            except ValueError as error:
                retained = error
        self.assertIsNotNone(retained)
        self.assertIsNotNone(retained.__traceback__)
        self.addCleanup(setattr, retained, "__traceback__", None)
        object.__setattr__(
            document, "content", "replacement after construction failure"
        )
        self.assertEqual(sys.getrefcount(source), baseline - 1)

    def test_failed_construction_traceback_severs_partial_snapshots(self):
        source = bytes(bytearray(b"bounded partial observation source"))
        root = [source, object()]
        gc.collect()
        baseline = sys.getrefcount(source)
        retained = None
        try:
            _finite_metadata(root, _with_release=True)
        except TypeError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.addCleanup(setattr, retained, "__traceback__", None)
        root.clear()
        self.assertEqual(sys.getrefcount(source), baseline - 1)
