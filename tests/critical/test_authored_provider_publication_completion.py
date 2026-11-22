"""Actual publication bytes/closure with explicit provider admission fixtures.

These controls qualify no model generation, provider semantic replay or consumer
admission. The existing fixture injects those boundaries explicitly.
"""

import copy
import pickle
import shutil
import unittest
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_products as products
from literate_ai.adapters.authored_publication_files import AuthoredPublicationFiles
from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.projects import PinnedInputClosure
from tests.critical import test_authored_retained_cargo_products as fixtures


class AuthoredProviderPublicationCompletionTests(unittest.TestCase):
    def fixture(self):
        return fixtures.AuthoredRetainedCargoProductsTests("runTest").fixture()

    def open(self, fixture, binding, payload):
        return products._open_authored_retained_cargo_products_session(
            fixture.current,
            binding,
            configured_store_id="reviewed-artifacts",
            archive_payload=payload,
        )

    def test_original_publication_survives_close_without_callback_or_saved_grant(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            with self.open(fixture, binding, payload) as session:
                session.products.require_unchanged()
                session.publication.require_original_files()
            with self.assertRaisesRegex(ValueError, "owner-expired"):
                session.products.require_unchanged()
            trap = AssertionError(
                "publication completion invoked a command or expired owner"
            )
            with (
                patch.object(
                    AuthoredPublicationFiles, "require_current", side_effect=trap
                ),
                patch.object(AuthoredPublicationFiles, "read", side_effect=trap),
                patch.object(
                    CurrentAuthoredQualificationPlan,
                    "require_unchanged",
                    side_effect=trap,
                ),
                patch.object(
                    products.CurrentAuthoredRetainedCargoProducts,
                    "require_unchanged",
                    side_effect=trap,
                ),
                patch("subprocess.run", side_effect=trap),
                patch("subprocess.Popen", side_effect=trap),
            ):
                session.publication.require_original_files()
            for value in (session, session.publication):
                for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                    with self.subTest(
                        operation=operation.__name__, value=type(value).__name__
                    ):
                        with self.assertRaises(TypeError):
                            operation(value)

    def test_after_close_changed_original_metadata_refuses_and_preserves_bytes(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            path = fixture.base(binding.provider_reference.attempt) / "reference.json"
            with self.open(fixture, binding, payload) as session:
                original = path.read_bytes()
            changed = original + b" "
            path.write_bytes(changed)
            with self.assertRaises(ValueError):
                session.publication.require_original_files()
            self.assertEqual(path.read_bytes(), changed)

    def test_after_close_retired_provider_path_cannot_reappear(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            with self.open(fixture, binding, payload) as session:
                pass
            path = fixture.paths[0]
            path.mkdir()
            try:
                with self.assertRaisesRegex(ValueError, "run_resources_not_retired"):
                    session.publication.require_original_files()
                self.assertTrue(path.is_dir())
            finally:
                path.rmdir()

    def test_same_bytes_in_replaced_publication_directory_refuse(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            path = fixture.base(binding.provider_reference.attempt)
            with self.open(fixture, binding, payload) as session:
                original = (path / "reference.json").read_bytes()
            moved = path.with_name(path.name + "-original")
            path.rename(moved)
            shutil.copytree(moved, path)
            with self.assertRaisesRegex(ValueError, "publication-directory-changed"):
                session.publication.require_original_files()
            self.assertEqual((path / "reference.json").read_bytes(), original)
            self.assertEqual((moved / "reference.json").read_bytes(), original)

    def test_late_original_capture_mutation_cannot_mint_session(self):
        with self.fixture() as (fixture, binding, payload, _projected, _reopened):
            path = fixture.base(binding.provider_reference.attempt) / "reference.json"
            original = path.read_bytes()
            changed = original + b" "
            real_pin = PinnedInputClosure.pin
            observed = []

            def pin(owner, actual, **kwargs):
                result = real_pin(owner, actual, **kwargs)
                if (
                    actual == path
                    and kwargs.get("expected_content") == original
                    and not observed
                ):
                    observed.append(actual)
                    path.write_bytes(changed)
                return result

            with patch.object(PinnedInputClosure, "pin", new=pin):
                with self.assertRaises(ValueError):
                    with self.open(fixture, binding, payload):
                        self.fail("late metadata mutation yielded a usable session")
            self.assertEqual(observed, [path])
            self.assertEqual(path.read_bytes(), changed)
