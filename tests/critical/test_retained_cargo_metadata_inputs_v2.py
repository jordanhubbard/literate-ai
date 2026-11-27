"""Metadata membership uses real original v2 materialization/input owners.

The fixture adopts actual Make/Git source and owns real archive/scratch bytes.
Cargo declarations and provider admission are modeled; no Cargo build or native
product qualification is claimed.
"""

import os
import shutil
import unittest
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_metadata_inputs_v2 as projection
from literate_ai.adapters.retained_cargo_execution_inputs_v2 import (
    read_retained_cargo_execution_inputs_v2,
)
from tests.support.fixtures_retained_cargo_receiving_v2 import (
    initialize_retained_cargo_receiving_v2_fixture,
    receive_retained_cargo_fixture,
)


@unittest.skipUnless(
    os.name != "nt" and shutil.which("git") and shutil.which("make"),
    "requires actual adopted POSIX source and native Git/Make",
)
class RetainedCargoMetadataOwnerTests(unittest.TestCase):
    def setUp(self):
        initialize_retained_cargo_receiving_v2_fixture(self)
        materialized = receive_retained_cargo_fixture(self)
        home = self.base / "execution-cargo-home"
        home.mkdir()
        (home / "package").mkdir()
        (home / "package/Cargo.toml").write_bytes(b"captured dependency")
        (home / "alias").symlink_to("package", target_is_directory=True)
        self.alias_manifest = home / "alias/Cargo.toml"
        self.external = self.base / "unowned-metadata"
        self.external.mkdir()
        self.environment = {"CARGO_HOME": str(home), "PATH": os.environ["PATH"]}
        self.inputs = read_retained_cargo_execution_inputs_v2(
            materialized, environment=self.environment
        )
        self.manifest_path = self.scratch.context.workspace / "Cargo.toml"

    def metadata(self, path):
        return {"packages": [{"manifest_path": str(path), "targets": []}]}

    def test_actual_owned_manifest_is_admitted(self):
        before = self.inputs.current_identity(environment=self.environment)
        self.inputs.require_metadata_paths(
            self.metadata(self.manifest_path), environment=self.environment
        )
        self.assertEqual(
            self.inputs.current_identity(environment=self.environment), before
        )

    def test_captured_internal_alias_and_generated_package_are_admitted(self):
        package = self.inputs.materialized.packages[0]
        value = self.metadata(self.alias_manifest)
        value["packages"].append(
            {"manifest_path": str(package.root / package.files[0].path), "targets": []}
        )
        self.inputs.require_metadata_paths(value, environment=self.environment)

    def test_path_and_memory_limits_precede_membership_indexes(self):
        maximum = self.inputs.scope.policy.input_custody.aggregate.maximum_entries * 2
        for count, source, error in (
            (maximum, str(self.manifest_path), "metadata-path-limit"),
            (12000, "/" + "a" * 4095, "metadata-memory-limit"),
        ):
            with self.subTest(bound=error):
                value = self.metadata(self.manifest_path)
                value["packages"][0]["targets"] = [{"src_path": source}] * count
                with (
                    patch.object(
                        projection,
                        "_require_membership",
                        side_effect=AssertionError("unadmitted metadata indexes"),
                    ),
                    self.assertRaisesRegex(ValueError, error),
                ):
                    self.inputs.require_metadata_paths(
                        value, environment=self.environment
                    )

    def test_metadata_mutation_during_membership_is_refused(self):
        value = self.metadata(self.manifest_path)
        membership = projection._require_membership
        calls = []

        def check(*args):
            result = membership(*args)
            value["packages"][0]["manifest_path"] = str(self.alias_manifest)
            calls.append(True)
            return result

        with (
            patch.object(projection, "_require_membership", side_effect=check),
            self.assertRaisesRegex(ValueError, "metadata-changed"),
        ):
            self.inputs.require_metadata_paths(value, environment=self.environment)
        self.assertEqual(calls, [True])

    def test_external_alias_cannot_borrow_an_owned_manifest(self):
        alias = self.external / "Cargo.toml"
        self.assertTrue(self.manifest_path.is_file())
        self.assertFalse(
            any(alias.is_relative_to(root) for _name, root in self.inputs.scope.roots)
        )
        alias.symlink_to(self.manifest_path)
        self.assertTrue(alias.samefile(self.manifest_path))
        before = self.inputs.current_identity(environment=self.environment)
        with self.assertRaisesRegex(ValueError, "uncaptured-package-path"):
            self.inputs.require_metadata_paths(
                self.metadata(alias), environment=self.environment
            )
        self.assertTrue(alias.is_symlink())
        self.assertTrue(alias.samefile(self.manifest_path))
        self.assertEqual(
            self.inputs.current_identity(environment=self.environment), before
        )
