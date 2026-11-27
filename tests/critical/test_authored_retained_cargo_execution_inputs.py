"""Fresh complete execution inputs with explicit fixture provider admission.

Actual consumer conversion, package publication, native tools and filesystem
custody are used; no consumer command or genuine provider qualification occurs.
"""

import copy
import os
import pickle
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_execution_inputs as authored
from literate_ai.adapters import retained_cargo_execution_inputs_v2 as source
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_authored_retained_cargo_materialization as receiving
from tests.support.fixtures_retained_cargo_receiving_v2 import (
    initialize_retained_cargo_receiving_v2_fixture,
    receive_retained_cargo_fixture,
)


class AuthoredRetainedCargoExecutionInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        receiving.AuthoredRetainedCargoMaterializationTests.setUpClass()

    @contextmanager
    def fixture(self):
        helper = receiving.AuthoredRetainedCargoMaterializationTests("runTest")
        with helper.fixture() as (files, scratch, current):
            materialized = helper.receive(files, scratch, current)
            base = files.reviewed.project.root.parent
            home = base / "cargo-home"
            home.mkdir()
            (home / "unconventional-input").write_bytes(b"whole-home input")
            configuration = base / ".cargo/config"
            configuration.parent.mkdir()
            configuration.write_bytes(b"[net]\noffline = true\n")
            yield (
                materialized,
                {"CARGO_HOME": str(home), "PATH": os.environ["PATH"]},
                configuration,
            )

    def read(self, materialized, environment):
        return authored.read_authored_retained_cargo_execution_inputs(
            materialized, environment=environment
        )

    def expected_identity(self, owner, schema):
        return canonical_identity(
            {
                "schema": schema,
                "binding": owner.materialized.files.reviewed.binding.identity.uri,
                "scope": owner.scope._captured_identity().uri,
                "configuration": owner._configuration.identity,
                "present": [str(path) for path, state in owner._states if state[2]],
                "absent": [
                    str(path) for path, state in owner._states if state[2] is None
                ],
            }
        )

    def test_fresh_complete_scope_and_ancestor_bytes_bind_original_materialization(
        self,
    ):
        with self.fixture() as (materialized, environment, configuration):
            owner = self.read(materialized, environment)
            self.assertIs(type(owner), authored.AuthoredRetainedCargoExecutionInputs)
            self.assertIs(owner.materialized, materialized)
            self.assertIs(owner.scope._scratch, materialized.scratch)
            identity = owner.current_identity(environment=environment)
            self.assertEqual(
                identity,
                self.expected_identity(
                    owner, "literate-ai/authored-retained-cargo-execution-inputs@1"
                ),
            )
            self.assertEqual(owner.current_identity(environment=environment), identity)
            self.assertIn(configuration, {path for path, _ in owner._states})
            self.assertEqual(
                {name for name, _ in owner.scope.roots}, {"workspace", "cargo-home"}
            )
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with (
                    self.subTest(operation=operation.__name__),
                    self.assertRaises(TypeError),
                ):
                    operation(owner)

    def test_new_unconventional_home_input_refuses_and_is_preserved(self):
        with self.fixture() as (materialized, environment, _configuration):
            owner = self.read(materialized, environment)
            home = dict(owner.scope.roots)["cargo-home"]
            added = home / "late-home-input"
            added.write_bytes(b"preserve")
            with self.assertRaises(ValueError):
                owner.current_identity(environment=environment)
            self.assertEqual(added.read_bytes(), b"preserve")

    def test_ancestor_configuration_mutation_after_final_materialization_refuses(self):
        for present in (True, False):
            with self.subTest(present=present):
                with self.fixture() as (materialized, environment, configuration):
                    if not present:
                        configuration.unlink()
                    owner = self.read(materialized, environment)
                    original = type(materialized).require_unchanged
                    calls = []

                    def check(
                        selected,
                        original=original,
                        calls=calls,
                        materialized=materialized,
                        configuration=configuration,
                    ):
                        result = original(selected)
                        if selected is materialized:
                            calls.append(True)
                            if len(calls) == 2:
                                configuration.write_bytes(b"[net]\noffline = false\n")
                        return result

                    with patch.object(type(materialized), "require_unchanged", check):
                        with self.assertRaises(ValueError):
                            owner.current_identity(environment=environment)
                    self.assertEqual(calls, [True, True])
                    self.assertEqual(
                        configuration.read_bytes(), b"[net]\noffline = false\n"
                    )

    def test_ancestor_configuration_bytes_and_absence_cannot_change(self):
        for present in (True, False):
            with self.subTest(present=present):
                with self.fixture() as (materialized, environment, configuration):
                    if not present:
                        configuration.unlink()
                    owner = self.read(materialized, environment)
                    configuration.write_bytes(b"[net]\noffline = false\n")
                    with self.assertRaises(ValueError):
                        owner.current_identity(environment=environment)
                    self.assertEqual(
                        configuration.read_bytes(), b"[net]\noffline = false\n"
                    )

    def test_metadata_requires_actual_captured_package_manifest_and_target(self):
        with self.fixture() as (materialized, environment, configuration):
            owner = self.read(materialized, environment)
            package = materialized.packages[0].root
            metadata = {
                "packages": [
                    {
                        "manifest_path": str(package / "source/Cargo.toml"),
                        "targets": [{"src_path": str(package / "source/src/lib.rs")}],
                    }
                ]
            }
            owner.require_metadata_paths(metadata, environment=environment)
            metadata["packages"][0]["targets"][0]["src_path"] = str(configuration)
            with self.assertRaisesRegex(ValueError, "uncaptured-package-path"):
                owner.require_metadata_paths(metadata, environment=environment)

    def test_cross_origin_refusal_precedes_any_input_capture(self):
        with self.fixture() as (materialized, environment, _configuration):
            with patch.object(
                source, "capture_retained_cargo_input_scope_v2"
            ) as capture:
                with self.assertRaisesRegex(
                    TypeError, "v2-live-materialization-required"
                ):
                    source.read_retained_cargo_execution_inputs_v2(
                        materialized, environment=environment
                    )
                capture.assert_not_called()
            with patch.object(
                authored, "capture_authored_retained_cargo_input_scope"
            ) as capture:
                with self.assertRaisesRegex(
                    TypeError, "authored-live-materialization-required"
                ):
                    self.read(object(), environment)
                capture.assert_not_called()

    def test_consumer_source_mutation_refuses_and_preserves_exact_changed_bytes(self):
        refused = closing_refused = False
        preserved = expected = None
        try:
            with self.fixture() as (materialized, environment, _configuration):
                owner = self.read(materialized, environment)
                path = materialized.scratch.context.workspace / "app.py"
                expected = path.read_bytes() + b"\n# current input drift\n"
                path.write_bytes(expected)
                try:
                    owner.current_identity(environment=environment)
                except ValueError:
                    refused = True
                preserved = path.read_bytes()
        except ValueError:
            closing_refused = True
        self.assertTrue(refused)
        self.assertTrue(closing_refused)
        self.assertIsNotNone(expected)
        self.assertEqual(preserved, expected)

    def test_saved_owner_cannot_restore_ended_materialization_or_exclusions(self):
        with self.fixture() as (materialized, environment, _configuration):
            owner = self.read(materialized, environment)
            owner.current_identity(environment=environment)
        with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
            owner.current_identity(environment=environment)

    def test_source_input_owner_keeps_exact_legacy_identity_map_and_four_slots(self):
        fixture = unittest.TestCase()
        self.addCleanup(fixture.doCleanups)
        initialize_retained_cargo_receiving_v2_fixture(fixture)
        materialized = receive_retained_cargo_fixture(fixture)
        home = fixture.base / "legacy-input-home"
        home.mkdir()
        environment = {"CARGO_HOME": str(home), "PATH": os.environ["PATH"]}
        owner = source.read_retained_cargo_execution_inputs_v2(
            materialized, environment=environment
        )
        self.assertEqual(
            owner.current_identity(environment=environment),
            self.expected_identity(
                owner, "literate-ai/retained-cargo-execution-inputs@2"
            ),
        )
        self.assertEqual(len(type(owner).__slots__), 4)
        self.assertFalse(hasattr(owner, "__dict__"))
