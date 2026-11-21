"""Actual native authored receiving execution with fixture provider admission.

Real consumer files, Cargo/Rust, gates, target protocols and explicit native
custody run here. Provider generation/replay and consumer retirement/admission
remain separate requirements; these tests do not qualify a model or release.
"""

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_execution as authored
from literate_ai.adapters import retained_cargo_execution_v2 as source
from literate_ai.adapters.retained_cargo_execution import RetainedCargoExecutionError
from literate_ai.contracts.retained_cargo_test_protocol import (
    RetainedCargoCustomProtocol,
    RetainedCargoExcludedProtocol,
    RetainedCargoLibtestProtocol,
)
from tests.support.fixtures_authored_retained_cargo_native import (
    authored_native_receiving_fixture,
)

LITAI_TEST_PRIORITY = 10
# The checkpointed runner isolates this heavy native group on small CI hosts.
LITAI_TEST_SERIAL = True


@unittest.skipUnless(
    os.name != "nt" and all(shutil.which(x) for x in ("cargo", "rustc", "make", "git")),
    "requires native POSIX Cargo/Rust and actual retained Make/Git adoption",
)
class AuthoredRetainedCargoNativeExecutionTests(unittest.TestCase):
    def arguments(self, inputs, native):
        return dict(
            cargo=native.cargo,
            rustc=native.rustc,
            gate_tools={"cargo": native.cargo},
            environment=native.environment,
            consumer_inputs=inputs,
            allow_host_execution=True,
            read_exclusion_permission=native.read_permission,
            timeout_seconds=900,
        )

    def test_actual_complete_gates_and_protocols_use_original_authored_owner(self):
        with authored_native_receiving_fixture(self) as (
            materialized,
            inputs,
            native,
            state,
        ):
            args = self.arguments(inputs, native)
            with patch.object(source, "_execute_cargo_consumer") as old:
                with self.assertRaisesRegex(TypeError, "v2-live-inputs-required"):
                    source.execute_retained_cargo_consumer_v2(materialized, **args)
                old.assert_not_called()
            with patch.object(authored, "_execute_cargo_consumer") as engine:
                with self.assertRaisesRegex(
                    ValueError, "authored-authorization-required"
                ):
                    authored.execute_authored_retained_cargo_consumer(
                        materialized, **{**args, "allow_host_execution": False}
                    )
                with self.assertRaisesRegex(TypeError, "authored-live-inputs-required"):
                    authored.execute_authored_retained_cargo_consumer(
                        materialized, **{**args, "consumer_inputs": object()}
                    )
                engine.assert_not_called()
            result = authored.execute_authored_retained_cargo_consumer(
                materialized, **args
            )
            self.assertIs(type(result), authored.AuthoredRetainedCargoExecution)
            reviewed = materialized.files.reviewed
            self.assertIsNotNone(reviewed.policy.native_custody)
            self.assertEqual(
                tuple(item.key for item in result.target_outcomes),
                tuple(item.key for item in reviewed.inventory.targets),
            )
            self.assertTrue(
                {gate.step_id for gate in reviewed.plan.common.gates}
                <= {row.command.step_id for row in result.observations}
            )
            self.assertEqual(
                result.consumer_inputs_identity,
                inputs.current_identity(environment=native.environment),
            )
            outcomes = {item.key: item for item in result.target_outcomes}
            for target in reviewed.inventory.targets:
                outcome = outcomes[target.key]
                if isinstance(target.protocol, RetainedCargoLibtestProtocol):
                    self.assertEqual(outcome.kind, "libtest")
                    self.assertEqual(outcome.passed_cases, target.protocol.must_run)
                    self.assertEqual(outcome.ignored_cases, target.protocol.ignored)
                elif isinstance(target.protocol, RetainedCargoCustomProtocol):
                    self.assertEqual(outcome.kind, "custom-harness")
                    self.assertEqual(outcome.passed_cases, ())
                    self.assertEqual(len(outcome.command_observation_identities), 1)
                else:
                    self.assertIsInstance(
                        target.protocol, RetainedCargoExcludedProtocol
                    )
                    self.assertEqual(outcome.kind, "excluded")
                    self.assertEqual(outcome.passed_cases, ())
                    self.assertEqual(outcome.command_observation_identities, ())
            self.assertTrue(state["active"])
        self.assertTrue(state["closed"])
        with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
            inputs.current_identity(environment=native.environment)

    def test_late_actual_cargo_home_mutation_refuses_and_preserves_input(self):
        with authored_native_receiving_fixture(self) as (
            materialized,
            inputs,
            native,
            _state,
        ):
            run = authored.run_bounded_process
            addition = Path(native.environment["CARGO_HOME"]) / "late-native-input"
            calls = 0

            def changed(*args, **kwargs):
                nonlocal calls
                result = run(*args, **kwargs)
                calls += 1
                if calls == 1:
                    addition.write_bytes(b"preserve late actual consumer input")
                return result

            with patch.object(authored, "run_bounded_process", changed):
                with self.assertRaises(RetainedCargoExecutionError):
                    authored.execute_authored_retained_cargo_consumer(
                        materialized, **self.arguments(inputs, native)
                    )
            self.assertEqual(calls, 1)
            self.assertEqual(
                addition.read_bytes(), b"preserve late actual consumer input"
            )

    def test_independent_exclusion_permission_is_reopened_before_any_command(self):
        with authored_native_receiving_fixture(self) as (
            materialized,
            inputs,
            native,
            _state,
        ):
            native.permission_path.write_bytes(b"independent permission revoked")
            with patch.object(authored, "run_bounded_process") as process:
                with self.assertRaises(RetainedCargoExecutionError):
                    authored.execute_authored_retained_cargo_consumer(
                        materialized, **self.arguments(inputs, native)
                    )
                process.assert_not_called()
            self.assertEqual(
                native.permission_path.read_bytes(), b"independent permission revoked"
            )
