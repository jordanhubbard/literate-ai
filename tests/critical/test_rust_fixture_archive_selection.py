"""Fixture routing refuses links without opening external cache targets."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.support.fixtures_rust_library_harness import _archive_search_roots


class RustFixtureArchiveSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_explicit_root_never_discovers_or_resolves_ambient_cache(self):
        with (
            mock.patch.dict(os.environ, {"LITAI_TEST_RUST_ARCHIVES": str(self.root)}),
            mock.patch.object(
                Path, "home", side_effect=AssertionError("ambient cache")
            ),
            mock.patch.object(
                Path, "resolve", side_effect=AssertionError("link resolution")
            ),
        ):
            self.assertEqual(_archive_search_roots(), (self.root,))

    def test_explicit_relative_root_refuses_without_fallback(self):
        with (
            mock.patch.dict(os.environ, {"LITAI_TEST_RUST_ARCHIVES": "relative"}),
            mock.patch.object(Path, "home", side_effect=AssertionError("fallback")),
            self.assertRaises(ValueError),
        ):
            _archive_search_roots()

    @unittest.skipUnless(os.name == "posix", "POSIX symlink fixture")
    def test_ambient_registry_link_refuses_before_target_directory_open(self):
        cargo = self.root / ".cargo"
        cargo.mkdir()
        (cargo / "registry").symlink_to("/unprobed-external-fixture-target")
        environment = {
            k: v for k, v in os.environ.items() if k != "LITAI_TEST_RUST_ARCHIVES"
        }
        with (
            mock.patch.dict(os.environ, environment, clear=True),
            mock.patch.object(Path, "home", return_value=self.root),
            mock.patch.object(
                Path, "glob", side_effect=AssertionError("opened target")
            ),
            self.assertRaises(unittest.SkipTest),
        ):
            _archive_search_roots()

    @unittest.skipUnless(os.name == "posix", "POSIX symlink fixture")
    def test_explicit_symlink_root_is_configuration_error_without_target_probe(self):
        alias = self.root / "archives"
        alias.symlink_to("/unprobed-external-fixture-target")
        with (
            mock.patch.dict(os.environ, {"LITAI_TEST_RUST_ARCHIVES": str(alias)}),
            mock.patch.object(
                Path, "resolve", side_effect=AssertionError("opened target")
            ),
            self.assertRaises(ValueError),
        ):
            _archive_search_roots()
