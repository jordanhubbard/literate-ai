"""Actual private executed observations; explicit fixture provider, no admission.

No model generation, release, source retirement or reopened namespace is proved.
"""

import copy
import os
import pickle
import shutil
import unittest
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_execution as authored
from literate_ai.adapters import retained_cargo_execution_core as core
from literate_ai.adapters import retained_cargo_test_execution as preparation
from literate_ai.adapters.dependencies.observation import PortableHostDependencyObserver
from literate_ai.adapters.retained_cargo_execution import RetainedCargoExecutionError
from literate_ai.contracts.retained_cargo_test_protocol import (
    RetainedCargoCustomProtocol,
)
from tests.support.fixtures_authored_retained_cargo_native import (
    authored_native_receiving_fixture,
)

LITAI_TEST_PRIORITY = 10
LITAI_TEST_SERIAL = True


@unittest.skipUnless(
    os.name != "nt" and all(shutil.which(x) for x in ("cargo", "rustc", "make", "git")),
    "requires native POSIX Cargo/Rust and actual retained Make/Git adoption",
)
class AuthoredNativeForwardingTests(unittest.TestCase):
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

    def custom_input(self, materialized):
        reviewed = materialized.files.reviewed
        protocols = [
            t.protocol
            for t in reviewed.inventory.targets
            if isinstance(t.protocol, RetainedCargoCustomProtocol)
        ]
        self.assertEqual(len(protocols), 1)
        self.assertEqual(len(protocols[0].inputs), 1)
        return reviewed.project.root / protocols[0].inputs[0].path

    def test_private_actual_execution_retains_custom_inputs_and_original_deadline(self):
        with authored_native_receiving_fixture(
            self, with_build_output=True, with_custom_input=True
        ) as (materialized, inputs, native, state):
            args = self.arguments(inputs, native)
            with patch.object(authored, "_execute_cargo_consumer_session") as engine:
                with self.assertRaisesRegex(
                    ValueError, "authored-authorization-required"
                ):
                    authored._execute_authored_retained_cargo_consumer_session(
                        materialized, **{**args, "allow_host_execution": False}
                    )
                with self.assertRaisesRegex(TypeError, "authored-live-inputs-required"):
                    authored._execute_authored_retained_cargo_consumer_session(
                        materialized, **{**args, "consumer_inputs": object()}
                    )
                engine.assert_not_called()
            started = core.time.monotonic()
            executed = authored._execute_authored_retained_cargo_consumer_session(
                materialized, **args
            )
            ended = core.time.monotonic()
            self.assertIs(type(executed), core._RetainedCargoExecutedSession)
            completion = executed.native_completion
            self.assertIs(type(completion), core._RetainedCargoNativeCompletion)
            self.assertLessEqual(started + 900, completion.deadline)
            self.assertLessEqual(completion.deadline, ended + 900)
            self.assertTrue(executed.observations)
            self.assertEqual(
                tuple(x.key for x in executed.target_outcomes),
                tuple(x.key for x in materialized.files.reviewed.inventory.targets),
            )
            self.assertEqual(
                executed.consumer_inputs_identity,
                inputs.current_identity(environment=native.environment),
            )
            self.assertEqual(len(completion.tests.custom_inputs), 1)
            path = self.custom_input(materialized)
            before = path.read_bytes()
            state["close_receiving"]()
            self.assertTrue(state["closed"])
            with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
                inputs.current_identity(environment=native.environment)
            for owner in (executed, completion, completion.tests):
                for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                    with self.assertRaises(TypeError):
                        operation(owner)
            completion.refresh_native_dependencies()
            with patch.object(
                preparation.time, "monotonic", return_value=completion.deadline + 1
            ):
                with self.assertRaisesRegex(ValueError, "completion-deadline"):
                    completion.refresh_native_dependencies()
            path.write_bytes(before + b"\n// preserve late custom input\n")
            # Native bytes remain current. This refusal needs the original
            # custom protocol input closure rather than a renewed baseline.
            completion.tests.preparation.require_original_files()
            with patch.object(
                PortableHostDependencyObserver,
                "observe",
                side_effect=AssertionError("raw must not inspect"),
            ):
                with self.assertRaises(ValueError):
                    completion.require_original_files()
            self.assertEqual(
                path.read_bytes(), before + b"\n// preserve late custom input\n"
            )

    def test_final_actual_metadata_drift_returns_no_completion_owner(self):
        with authored_native_receiving_fixture(self, with_custom_input=True) as (
            materialized,
            inputs,
            native,
            state,
        ):
            path = self.custom_input(materialized)
            before = path.read_bytes()
            run = authored.run_bounded_process
            count = 0

            def changed(argv, **kwargs):
                nonlocal count
                result = run(argv, **kwargs)
                if "metadata" in argv:
                    count += 1
                    if count == 2:
                        path.write_bytes(
                            before + b"\n// preserve final metadata drift\n"
                        )
                return result

            with (
                patch.object(authored, "run_bounded_process", changed),
                patch.object(
                    core,
                    "_RetainedCargoNativeCompletion",
                    wraps=core._RetainedCargoNativeCompletion,
                ) as mint,
            ):
                with self.assertRaises(RetainedCargoExecutionError) as failed:
                    authored._execute_authored_retained_cargo_consumer_session(
                        materialized, **self.arguments(inputs, native)
                    )
                mint.assert_not_called()
            self.assertEqual(count, 2)
            self.assertTrue(failed.exception.observations)
            self.assertEqual(
                path.read_bytes(), before + b"\n// preserve final metadata drift\n"
            )
            # Drain the actual closers and assert their independent refusal;
            # never restore or delete the changed consumer bytes.
            with self.assertRaises(ValueError):
                state["close_receiving"]()
            self.assertTrue(state["closed"])
            self.assertEqual(
                path.read_bytes(), before + b"\n// preserve final metadata drift\n"
            )
