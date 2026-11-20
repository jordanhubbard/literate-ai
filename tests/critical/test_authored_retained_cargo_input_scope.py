"""Complete native input observations with real original consumer scratch.

No provider replay, native command, source retirement or admission occurs here.
Saved observations cannot replace a future execution owner's fresh capture.
"""

import unittest
from contextlib import contextmanager
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_input_scope as authored
from literate_ai.adapters import retained_cargo_input_scope_core as core
from literate_ai.adapters import retained_cargo_input_scope_v2 as source
from literate_ai.adapters.authored_retained_cargo_scratch import (
    reserve_authored_retained_cargo_scratch,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    authored_retained_cargo_wrapper_context,
)
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_authored_retained_cargo_scratch as scratches


class AuthoredRetainedCargoInputScopeTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        helper = scratches.AuthoredRetainedCargoScratchTests("runTest")
        with helper.fixture() as reviewed:
            home = reviewed.project.root.parent / "cargo-home"
            home.mkdir()
            (home / "unconventional-input").write_bytes(b"capture whole Cargo home")
            with authored_retained_cargo_wrapper_context(reviewed) as context:
                with reserve_authored_retained_cargo_scratch(context) as scratch:
                    yield scratch, {"CARGO_HOME": str(home)}

    def capture(self, scratch, environment, **changes):
        return authored.capture_authored_retained_cargo_input_scope(
            scratch.context.workspace,
            policy=scratch.context.reviewed.policy,
            environment=environment,
            scratch=scratch,
            **changes,
        )

    def test_entire_cargo_home_is_captured_and_unknown_addition_refuses(self):
        with self.fixture() as (scratch, environment):
            scope = self.capture(scratch, environment)
            self.assertIs(type(scope), authored.AuthoredRetainedCargoInputScope)
            self.assertIs(scope._scratch, scratch)
            self.assertEqual(
                {name for name, _ in scope.roots}, {"workspace", "cargo-home"}
            )
            home = dict(scope.roots)["cargo-home"]
            tree = dict(scope.owners.trees)["cargo-home"]
            self.assertIn("unconventional-input", {row[0] for row in tree.files})
            added = home / "late-input"
            added.write_bytes(b"must remain visible")
            with self.assertRaises(ValueError):
                scope.require_unchanged(environment=environment)
            self.assertEqual(added.read_bytes(), b"must remain visible")

    def test_full_environment_is_bound_and_cannot_gain_a_variable(self):
        with self.fixture() as (scratch, environment):
            scope = self.capture(scratch, environment)
            scope.require_unchanged(environment=environment)
            environment["UNREVIEWED_INPUT"] = "changed"
            with self.assertRaisesRegex(ValueError, "input-environment-changed"):
                scope.require_unchanged(environment=environment)

    def test_original_environment_mutation_during_capture_refuses_on_close(self):
        with self.fixture() as (scratch, environment):
            capture = authored._capture_consumer_input_scope

            def changed(*args, **kwargs):
                self.assertIsNot(kwargs["environment"], environment)
                result = capture(*args, **kwargs)
                environment["UNREVIEWED_INPUT"] = "late original mapping mutation"
                return result

            with patch.object(
                authored, "_capture_consumer_input_scope", side_effect=changed
            ):
                with self.assertRaisesRegex(ValueError, "input-environment-changed"):
                    self.capture(scratch, environment)

    def test_cross_origin_and_missing_scratch_refuse_before_private_capture(self):
        with self.fixture() as (scratch, environment):
            args = dict(policy=scratch.context.reviewed.policy, environment=environment)
            with patch.object(source, "_capture_consumer_input_scope") as legacy:
                with self.assertRaisesRegex(TypeError, "v2-live-scratch-required"):
                    source.capture_retained_cargo_input_scope_v2(
                        scratch.context.workspace, scratch=scratch, **args
                    )
                legacy.assert_not_called()
            with patch.object(authored, "_capture_consumer_input_scope") as current:
                for value in (None, object()):
                    with (
                        self.subTest(value=value),
                        self.assertRaisesRegex(
                            TypeError, "authored-live-scratch-required"
                        ),
                    ):
                        authored.capture_authored_retained_cargo_input_scope(
                            scratch.context.workspace, scratch=value, **args
                        )
                current.assert_not_called()

    def test_external_root_cannot_overlap_owned_workspace_output(self):
        with self.fixture() as (scratch, environment):
            environment["CARGO_HOME"] = str(scratch.context.workspace / "cargo-output")
            with patch.object(core, "capture_retained_cargo_input_owners_v2") as owners:
                with self.assertRaisesRegex(ValueError, "input-scratch-overlap"):
                    self.capture(scratch, environment)
                owners.assert_not_called()

    def test_source_scope_keeps_exact_identity_shape_and_five_slots(self):
        with self.fixture() as (scratch, environment):
            scope = source.capture_retained_cargo_input_scope_v2(
                scratch.context.workspace,
                policy=scratch.context.reviewed.policy,
                environment=environment,
            )
            expected = canonical_identity(
                {
                    "schema": "literate-ai/retained-cargo-input-scope@2",
                    "policy": scope.policy.identity.uri,
                    "environment": scope.environment_identity.uri,
                    "owners": scope.owners.identity.uri,
                    "roots": [
                        {"scope": name, "path": str(path)} for name, path in scope.roots
                    ],
                }
            )
            self.assertEqual(scope.identity, expected)
            self.assertEqual(len(type(scope).__slots__), 5)
            self.assertFalse(hasattr(scope, "__dict__"))

    def test_ended_original_scratch_cannot_supply_saved_exclusions(self):
        with self.fixture() as (scratch, environment):
            scope = self.capture(scratch, environment)
            scope.require_unchanged(environment=environment)
        with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
            scope.require_unchanged(environment=environment)
