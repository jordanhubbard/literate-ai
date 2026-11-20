"""Exact consumer file observations do not establish package ownership or admission."""

import hashlib
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_files as authored
from literate_ai.adapters import retained_cargo_files_v2 as source
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_authored_retained_cargo_review as declarations
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


class AuthoredRetainedCargoFilesTests(unittest.TestCase):
    @contextmanager
    def fixture(self, *, authored_binding=True):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(
                Path(directory).resolve(strict=True), with_provider=True
            ) as (old, provider):
                helper = declarations.AuthoredRetainedCargoReviewTests("runTest")
                if authored_binding:
                    reference = helper.write_binding(
                        old.project.root, helper.fixture(old)
                    )
                    reviewed = helper.read(old.project.root, reference)
                else:
                    reviewed = old
                contents = (
                    b"workspace",
                    b"lock",
                    b"before",
                    *provider.native_manifests.values(),
                )
                payloads = {
                    hashlib.sha256(value).hexdigest(): value for value in contents
                }
                yield reviewed, payloads

    def write_manifests(self, reviewed, payloads, *, state="after", packages=True):
        workspace = reviewed.project.root / reviewed.plan.common.workspace_root
        for item in reviewed.plan.common.manifests:
            if not packages and item.path not in {"Cargo.toml", "Cargo.lock"}:
                continue
            reference = getattr(item, state)
            if reference is None:
                continue
            path = workspace / item.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payloads[reference.digest])
        return workspace

    def test_present_exact_manifests_are_read_only_and_byte_drift_refuses(self):
        with self.fixture() as (reviewed, payloads):
            workspace = self.write_manifests(reviewed, payloads)
            before = {
                item.path: (workspace / item.path).read_bytes()
                for item in reviewed.plan.common.manifests
            }
            snapshot = authored.read_authored_retained_cargo_files(
                reviewed, manifest_state="after"
            )
            self.assertIs(type(snapshot), authored.AuthoredRetainedCargoFileSnapshot)
            self.assertNotIsInstance(snapshot, source.RetainedCargoFileSnapshotV2)
            snapshot.require_unchanged()
            self.assertEqual(
                before, {name: (workspace / name).read_bytes() for name in before}
            )
            self.assertEqual(snapshot.absent_paths, ())
            (workspace / "Cargo.lock").write_bytes(b"changed literal lock")
            with self.assertRaises(ValueError):
                snapshot.require_unchanged()

    def test_deferred_package_absence_does_not_adopt_later_foreign_package(self):
        with self.fixture() as (reviewed, payloads):
            self.write_manifests(reviewed, payloads, packages=False)
            snapshot = authored.read_authored_retained_cargo_files(
                reviewed, manifest_state="after", package_state="absent"
            )
            snapshot.require_unchanged()
            package = reviewed.plan.graph.common.packages[0]
            manifest = (
                reviewed.project.root
                / reviewed.plan.common.workspace_root
                / package.root
                / "Cargo.toml"
            )
            destination = next(
                reviewed.project.root / path
                for _, path in reviewed.binding.destinations
                if manifest.is_relative_to(reviewed.project.root / path)
            )
            destination.mkdir(parents=True)
            (destination / "foreign").write_bytes(b"not a qualified package")
            # Authored-file observation intentionally defers package custody.
            snapshot.require_authored_unchanged()
            with self.assertRaises(ValueError):
                snapshot.require_unchanged()
            with self.assertRaises(ValueError):
                authored.read_authored_retained_cargo_files(
                    reviewed, manifest_state="after", package_state="provision"
                )
            self.assertEqual(
                (destination / "foreign").read_bytes(), b"not a qualified package"
            )

    def test_provision_observes_reviewed_files_but_does_not_prove_existing_ownership(
        self,
    ):
        with self.fixture() as (reviewed, payloads):
            self.write_manifests(reviewed, payloads)
            snapshot = authored.read_authored_retained_cargo_files(
                reviewed, manifest_state="after", package_state="provision"
            )
            snapshot.require_unchanged()
            self.assertFalse(hasattr(snapshot, "packages"))
            self.assertFalse(hasattr(snapshot, "admission"))
            self.assertEqual(snapshot.manifest_state, "after")
            self.assertEqual(snapshot.package_state, "provision")

    def test_before_state_is_distinct_and_unbounded_or_invalid_states_refuse(self):
        with self.fixture() as (reviewed, payloads):
            self.write_manifests(reviewed, payloads, state="before")
            snapshot = authored.read_authored_retained_cargo_files(
                reviewed, manifest_state="before"
            )
            snapshot.require_unchanged()
            for kwargs in (
                {"manifest_state": "unknown"},
                {"manifest_state": "before", "package_state": "absent"},
                {"manifest_state": "after", "package_state": "unknown"},
                {"manifest_state": "before", "maximum_file_bytes": True},
                {"manifest_state": "before", "maximum_total_bytes": 1024**3 + 1},
            ):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    authored.read_authored_retained_cargo_files(reviewed, **kwargs)

    def test_exact_public_type_gates_refuse_before_shared_observation_reader(self):
        with self.fixture() as (reviewed, _payloads):
            with patch.object(
                source,
                "_read_consumer_file_observations",
                side_effect=AssertionError("source reader entered"),
            ) as entered:
                with self.assertRaisesRegex(ValueError, "v2-reviewed-files-required"):
                    source.read_retained_cargo_files_v2(
                        reviewed, manifest_state="after"
                    )
                entered.assert_not_called()
        with self.fixture(authored_binding=False) as (reviewed, _payloads):
            with patch.object(
                authored,
                "_read_consumer_file_observations",
                side_effect=AssertionError("authored reader entered"),
            ) as entered:
                with self.assertRaisesRegex(
                    ValueError, "authored-reviewed-files-required"
                ):
                    authored.read_authored_retained_cargo_files(
                        reviewed, manifest_state="after"
                    )
                entered.assert_not_called()

    def test_source_snapshot_retains_exact_identity_shape_and_slots(self):
        with self.fixture(authored_binding=False) as (reviewed, payloads):
            self.write_manifests(reviewed, payloads)
            snapshot = source.read_retained_cargo_files_v2(
                reviewed, manifest_state="after"
            )
            expected = canonical_identity(
                {
                    "schema": "literate-ai/retained-cargo-file-snapshot@2",
                    "reviewed": reviewed.identity.uri,
                    "manifest_state": "after",
                    "package_state": "present",
                    "present_files": snapshot._inputs.identity,
                    "absent_paths": [],
                }
            )
            self.assertEqual(snapshot.identity, expected)
            self.assertFalse(hasattr(snapshot, "__dict__"))
            self.assertEqual(
                set(snapshot.__slots__),
                {
                    "reviewed",
                    "manifest_state",
                    "package_state",
                    "absent_paths",
                    "_inputs",
                },
            )
