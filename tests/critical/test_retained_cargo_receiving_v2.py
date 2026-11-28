"""Real v2 archive publication in an adopted source owner; no model invocation."""

import copy
import os
import shutil
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_materialization_v2 as receiver
from tests.support.fixtures_retained_cargo_receiving_v2 import (
    initialize_retained_cargo_receiving_v2_fixture,
    receive_retained_cargo_fixture,
)


@unittest.skipUnless(
    os.name != "nt" and shutil.which("git") and shutil.which("make"),
    "requires native POSIX adoption and Git",
)
class RetainedCargoReceivingV2Tests(unittest.TestCase):
    def setUp(self):
        initialize_retained_cargo_receiving_v2_fixture(self)

    def receive(self, **changes):
        return receive_retained_cargo_fixture(self, **changes)

    def test_real_archive_is_published_under_live_original_source_and_expires(self):
        materialized = self.receive()
        # Independent importing-maintainer destinations name ALL graph exports,
        # not only library products. Never derive this expectation from the
        # materializer's observed package count.
        expected = {
            self.reviewed.project.root / destination
            for _, destination in self.reviewed.binding.common.destinations
        }
        self.assertEqual({tree.root for tree in materialized.packages}, expected)
        self.assertEqual(len(materialized.packages), len(expected))
        self.assertEqual(
            len(materialized.capture.exports.libraries),
            len(self.reviewed.binding.common.exports.libraries),
        )
        self.assertEqual(
            materialized.capture.exports, self.reviewed.binding.common.exports
        )
        self.assertTrue(
            all(
                tree.root.is_relative_to(self.context.workspace / "pkgs")
                for tree in materialized.packages
            )
        )
        materialized.require_unchanged()
        with self.assertRaises(TypeError):
            copy.copy(materialized)
        self.scratch_manager.__exit__(None, None, None)
        with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
            materialized.require_unchanged()

    def test_review_cannot_add_foreign_or_omit_graph_export_destinations(self):
        from literate_ai.contracts.identity import canonical_identity

        selected = self.reviewed.binding.common
        for values in (
            selected.destinations[:-1],
            tuple(
                sorted(
                    (
                        *selected.destinations,
                        (canonical_identity("foreign-export"), "foreign/destination"),
                    ),
                    key=lambda row: row[0].uri,
                )
            ),
        ):
            with self.subTest(destinations=len(values)), self.assertRaises(ValueError):
                replace(selected, destinations=values)
        self.assertFalse(
            any(
                (self.reviewed.project.root / value).exists()
                for _, value in selected.destinations
            )
        )

    def test_corrupt_archive_cannot_publish_packages_or_replace_reserved_roots(self):
        from literate_ai.adapters.exclusive_directory import directory_node

        roots = tuple(
            self.context.workspace / item.path
            for item in self.reviewed.plan.scratch_roots
        )
        before = {path: directory_node(path) for path in roots}
        with self.assertRaises(ValueError):
            self.receive(read_archive=lambda *_args: self.provider.archive[:-1])
        self.assertEqual({path: directory_node(path) for path in roots}, before)
        self.assertTrue(all(not any(path.iterdir()) for path in roots))
        for _, destination in self.reviewed.binding.common.destinations:
            self.assertFalse(os.path.lexists(self.reviewed.project.root / destination))

    def test_provider_revocation_cannot_publish_packages(self):
        reads = []

        def current():
            reads.append(True)
            if len(reads) == 1:
                return self.current
            return replace(
                self.current,
                current=replace(
                    self.current.current, configured_store_id="revoked-store"
                ),
            )

        with self.assertRaisesRegex(ValueError, "importer-authority-mismatch"):
            self.receive(read_current=current)
        self.assertGreaterEqual(len(reads), 2)
        for _, destination in self.reviewed.binding.common.destinations:
            self.assertFalse(os.path.lexists(self.reviewed.project.root / destination))

    def test_source_addition_is_never_hidden_by_owned_package_output(self):
        original = receiver.publish_directory_exclusive

        def changed_source(*args, **kwargs):
            original(*args, **kwargs)
            (self.context.workspace / "foreign-source.rs").write_bytes(b"preserve")

        with patch.object(
            receiver, "publish_directory_exclusive", side_effect=changed_source
        ):
            with self.assertRaises(ValueError):
                self.receive()
        self.assertEqual(
            (self.context.workspace / "foreign-source.rs").read_bytes(), b"preserve"
        )
        # End the refused transaction without pretending the changed source is current.
        self.context.workspace.joinpath("foreign-source.rs").unlink()

    def test_later_collision_rolls_back_only_unchanged_owned_package(self):
        original = receiver.publish_directory_exclusive
        count = 0
        destinations = sorted(
            self.reviewed.project.root / value
            for _, value in self.reviewed.binding.common.destinations
        )

        def collision(source, destination, **kwargs):
            nonlocal count
            if destination in destinations:
                count += 1
                if count == 2:
                    destination.mkdir()
                    (destination / "foreign").write_bytes(b"keep")
                    raise FileExistsError("foreign fixture destination")
            return original(source, destination, **kwargs)

        with patch.object(
            receiver, "publish_directory_exclusive", side_effect=collision
        ):
            with self.assertRaises(FileExistsError):
                self.receive()
        self.assertFalse(destinations[0].exists())
        self.assertEqual((destinations[1] / "foreign").read_bytes(), b"keep")
        self.assertTrue(list((self.context.workspace / "pkgs").glob(".rp-*")))
