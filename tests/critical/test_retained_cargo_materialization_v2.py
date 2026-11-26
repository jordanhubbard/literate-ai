"""Actual native archive verification before owned v2 scratch publication."""

import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_scratch_v2 as scratch_owner
from literate_ai.adapters.retained_cargo_files_v2 import read_retained_cargo_files_v2
from literate_ai.adapters.retained_cargo_import_v2 import RetainedCargoCurrentInputsV2
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    materialize_initial_retained_cargo_scratch_v2,
)
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


@unittest.skipUnless(
    os.name != "nt" and shutil.which("git") and shutil.which("make"),
    "requires native POSIX adoption and Git",
)
class RetainedCargoVerifiedScratchMaterializationTests(unittest.TestCase):
    def setUp(self):
        base = Path(
            self.enterContext(tempfile.TemporaryDirectory(prefix="cv-"))
        ).resolve()
        self.reviewed, self.provider = self.enterContext(
            scratch_review_fixture(base, include_provider=True)
        )
        self.workspace = (
            self.reviewed.project.root / self.reviewed.plan.common.workspace_root
        )
        # The receiving review and expected identity are independent inputs to
        # the real verifier; the archive reader supplies only producer bytes.
        self.current = RetainedCargoCurrentInputsV2(
            self.reviewed,
            replace(
                self.provider.inputs,
                importer_project_id=self.reviewed.project.definition.project_id,
                reviewed_binding_identity=self.reviewed.binding.identity,
            ),
        )

    def run_materializer(self, **changes):
        arguments = {
            **self.provider.calls,
            "read_current": lambda: self.current,
            **changes,
        }
        return materialize_initial_retained_cargo_scratch_v2(
            read_retained_cargo_files_v2(
                self.reviewed, manifest_state="after", package_state="absent"
            ),
            **arguments,
        )

    def assert_no_roots(self):
        for item in self.reviewed.plan.scratch_roots:
            self.assertFalse(os.path.lexists(self.workspace / item.path))

    def test_verified_archive_publishes_native_exports_with_live_custody(self):
        with self.run_materializer() as materialized:
            self.assertEqual(materialized.plan, self.reviewed.plan)
            self.assertEqual(
                len(materialized.packages),
                len(self.reviewed.binding.common.destinations),
            )
            for _, destination in self.reviewed.binding.common.destinations:
                root = self.reviewed.project.root / destination
                self.assertEqual(
                    (root / "source/src/lib.rs").read_bytes(), b"pub fn run() {}\n"
                )
            self.assertEqual(list((self.workspace / "cargo-output").iterdir()), [])
            materialized.require_unchanged()
        self.assertEqual(len(self.provider.reads), 1)
        self.assertEqual(self.provider.reads[0][0], "reviewed-store")
        with self.assertRaisesRegex(ValueError, "operation-ended"):
            materialized.require_unchanged()

    def test_corrupt_or_over_limit_archive_cannot_publish_any_root(self):
        for changes in (
            {"read_archive": lambda *args: self.provider.archive[:-1]},
            {"max_archive_bytes": len(self.provider.archive) - 1},
        ):
            with self.subTest(changes=tuple(changes)):
                with self.assertRaises(ValueError):
                    with self.run_materializer(**changes):
                        self.fail("unverified archive published")
                self.assert_no_roots()

    def test_closing_check_rejects_changed_native_package_without_removal(self):
        _, destination = self.reviewed.binding.common.destinations[0]
        source = self.reviewed.project.root / destination / "source/src/lib.rs"
        with self.assertRaises(ValueError):
            with self.run_materializer():
                original = source.read_bytes()
                changed = original.replace(b"run", b"bad")
                self.assertNotEqual(original, changed)
                self.assertEqual(len(original), len(changed))
                source.write_bytes(changed)
        self.assertEqual(source.read_bytes(), changed)

    def test_closing_check_rejects_authored_manifest_drift_without_restoration(self):
        manifest = self.workspace / "Cargo.lock"
        with self.assertRaises(ValueError):
            with self.run_materializer():
                self.assertEqual(manifest.read_bytes(), b"lock")
                manifest.write_bytes(b"LOCK")
        self.assertEqual(manifest.read_bytes(), b"LOCK")

    def test_provider_revocation_between_verification_and_publication_refuses(self):
        reads = 0

        def read_current():
            nonlocal reads
            reads += 1
            if reads > 1:
                return replace(
                    self.current,
                    current=replace(
                        self.current.current, configured_store_id="another-store"
                    ),
                )
            return self.current

        with self.assertRaisesRegex(ValueError, "importer-authority-mismatch"):
            with self.run_materializer(read_current=read_current):
                self.fail("revoked provider published")
        self.assertGreaterEqual(reads, 2)
        self.assertEqual(len(self.provider.reads), 1)
        self.assert_no_roots()

    def test_post_publication_revocation_stops_next_root_without_cleanup(self):
        publisher = scratch_owner.publish_directory_between_owned_parents_exclusive
        published = []

        def publish(source, destination, **kwargs):
            publisher(source, destination, **kwargs)
            published.append(destination)
            self.current = replace(
                self.current,
                current=replace(
                    self.current.current, configured_store_id="revoked-store"
                ),
            )

        with patch.object(
            scratch_owner,
            "publish_directory_between_owned_parents_exclusive",
            side_effect=publish,
        ):
            with self.assertRaisesRegex(ValueError, "importer-authority-mismatch"):
                with self.run_materializer():
                    self.fail("provider revocation did not stop publication")
        self.assertEqual(published, [self.workspace / "cargo-output"])
        self.assertEqual(list(published[0].iterdir()), [])
        self.assertFalse(os.path.lexists(self.workspace / "pkgs"))

    def test_revocation_after_source_capture_prevents_first_publication(self):
        capture = scratch_owner.capture_retained_cargo_tree_v2
        captures = 0

        def capture_then_revoke(*args, **kwargs):
            nonlocal captures
            value = capture(*args, **kwargs)
            captures += 1
            self.current = replace(
                self.current,
                current=replace(
                    self.current.current, configured_store_id="revoked-store"
                ),
            )
            return value

        with patch.object(
            scratch_owner,
            "capture_retained_cargo_tree_v2",
            side_effect=capture_then_revoke,
        ):
            with self.assertRaisesRegex(ValueError, "importer-authority-mismatch"):
                with self.run_materializer():
                    self.fail("revoked provider reached first publication")
        self.assertEqual(captures, 1)
        self.assertEqual(len(self.provider.reads), 1)
        self.assert_no_roots()
