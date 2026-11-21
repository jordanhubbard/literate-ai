"""Real native same-consumer reopen, gates and protocols; provider is a fixture.

Separate-process CLI, genuine generation and positive admission remain unqualified.
"""

import json
import os
import shutil
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_execution as execution
from literate_ai.adapters import authored_retained_cargo_reopened_output as outputs
from literate_ai.adapters import retained_cargo_execution_core as core
from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    read_authored_retained_cargo_execution_inputs,
)
from literate_ai.adapters.authored_retained_cargo_reopen_owner import (
    _reserve_authored_reopened_namespace,
)
from literate_ai.adapters.authored_retained_cargo_reopened_materialization import (
    _reopen_authored_retained_cargo_packages,
)
from literate_ai.adapters.retained_cargo_execution import RetainedCargoExecutionError
from literate_ai.contracts.repositories import RepositoryBuildEnvironment
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
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
class AuthoredReopenedNativeExecutionTests(unittest.TestCase):
    def arguments(self, inputs, native, registry):
        return dict(
            cargo=native.cargo,
            rustc=native.rustc,
            gate_tools={"cargo": native.cargo},
            environment=native.environment,
            consumer_inputs=inputs,
            allow_host_execution=True,
            read_exclusion_permission=native.read_permission,
            registry_sources=registry,
            timeout_seconds=900,
        )

    def test_both_modes_use_fresh_same_consumer_children_and_original_completion(
        self,
    ):
        with authored_native_receiving_fixture(self, with_build_output=True) as (
            initial,
            _inputs,
            native,
            state,
        ):
            workspace = initial.scratch.context.workspace
            parent = (
                workspace / initial.files.reviewed.plan.graph.common.output_directory
            )
            old = parent / "old-executable-marker"
            old.write_bytes(b"old executable must never be selected")
            old.chmod(0o755)
            state["close_receiving"]()
            children = []
            for retain in (False, True):
                with state["reopen_receiving"]() as (current, wrapper):
                    with _reserve_authored_reopened_namespace(
                        current,
                        wrapper,
                        old_output_budget=RetainedCargoOutputBudget(
                            512 * 1024**2, 4 * 1024**3
                        ),
                    ) as namespace:
                        materialized = _reopen_authored_retained_cargo_packages(
                            current,
                            namespace,
                            new_output_budget=RetainedCargoOutputBudget(
                                512 * 1024**2, 4 * 1024**3
                            ),
                        )
                        child = namespace.cargo_output
                        children.append(child)
                        observed = read_authored_retained_cargo_execution_inputs(
                            materialized, environment=native.environment
                        )
                        registry = {}
                        args = self.arguments(observed, native, registry)
                        invoke = (
                            execution._execute_authored_retained_cargo_consumer_session
                            if retain
                            else execution.execute_authored_retained_cargo_consumer
                        )
                        result = invoke(materialized, **args)
                        self.assertEqual(
                            len(result.target_outcomes),
                            len(current.reviewed.inventory.targets),
                        )
                        self.assertEqual(
                            result.consumer_inputs_identity,
                            observed.current_identity(environment=native.environment),
                        )
                        for row in result.observations:
                            if row.command.step_id == "retained-cargo-metadata":
                                document = json.loads(row.result.stdout)
                                self.assertEqual(
                                    document["target_directory"], str(child)
                                )
                                self.assertEqual(
                                    document.get("build_directory", str(child)),
                                    str(child),
                                )
                                self.assertEqual(
                                    dict(
                                        (item.name, item.value)
                                        for item in row.command.environment
                                    )["CARGO_TARGET_DIR"],
                                    str(child),
                                )
                            if row.command.step_id.startswith(
                                "retained-test-"
                            ) and row.command.argv[0] not in {"cargo", "rustc"}:
                                self.assertTrue(
                                    row.command.argv[0].startswith(str(child) + os.sep)
                                )
                        self.assertEqual(
                            old.read_bytes(), b"old executable must never be selected"
                        )
                        if retain:
                            completion = result.output_completion
                            self.assertIs(completion.namespace, namespace)
                            self.assertIs(completion.registry_sources, registry)
                            self.assertIs(
                                completion.read_exclusion_permission,
                                args["read_exclusion_permission"],
                            )
                            self.assertEqual(
                                completion.deadline, result.native_completion.deadline
                            )
                            completion.refresh_permissions()
                if retain:
                    completion.require_original_files()
                    result.native_completion.require_original_files()
                    result.tool_completion.require_original_files()
                    registry["late-registry"] = "registry+https://invalid.example/index"
                    with self.assertRaisesRegex(
                        ValueError, "original-registry-changed"
                    ):
                        completion.require_original_files()
                    del registry["late-registry"]
                    native.environment["LITAI_LATE_ENVIRONMENT"] = "changed"
                    with self.assertRaisesRegex(
                        ValueError, "original-environment-changed"
                    ):
                        completion.require_original_files()
                    del native.environment["LITAI_LATE_ENVIRONMENT"]
                    extra = child / "late-unselected-output"
                    extra.write_bytes(b"preserve post-close unselected output drift")
                    with self.assertRaisesRegex(ValueError, "original-tree-changed"):
                        completion.require_original_files()
                    self.assertEqual(
                        extra.read_bytes(),
                        b"preserve post-close unselected output drift",
                    )
            self.assertNotEqual(*children)
            self.assertEqual(native.environment["CARGO_TARGET_DIR"], str(parent))

    def test_final_live_callback_cannot_change_output_after_full_capture(self):
        with authored_native_receiving_fixture(self) as (
            initial,
            _inputs,
            native,
            state,
        ):
            state["close_receiving"]()
            with state["reopen_receiving"]() as (current, wrapper):
                with _reserve_authored_reopened_namespace(
                    current,
                    wrapper,
                    old_output_budget=RetainedCargoOutputBudget(
                        512 * 1024**2, 4 * 1024**3
                    ),
                ) as namespace:
                    materialized = _reopen_authored_retained_cargo_packages(
                        current,
                        namespace,
                        new_output_budget=RetainedCargoOutputBudget(
                            512 * 1024**2, 4 * 1024**3
                        ),
                    )
                    observed = read_authored_retained_cargo_execution_inputs(
                        materialized, environment=native.environment
                    )
                    capture = core._capture_reopened_output_completion
                    changed = namespace.cargo_output / "late-completion-callback"
                    armed = [False]

                    def mark(*args, **kwargs):
                        result = capture(*args, **kwargs)
                        armed[0] = True
                        return result

                    # The last full guard invokes the ORIGINAL permission reader.
                    reader = native.read_permission

                    def permission(identity):
                        result = reader(identity)
                        if armed[0]:
                            changed.write_bytes(
                                b"preserve final permission callback drift"
                            )
                        return result

                    with patch.object(
                        core, "_capture_reopened_output_completion", side_effect=mark
                    ):
                        args = self.arguments(observed, native, {})
                        args["read_exclusion_permission"] = permission
                        with self.assertRaises(RetainedCargoExecutionError):
                            execution._execute_authored_retained_cargo_consumer_session(
                                materialized, **args
                            )
                    self.assertTrue(armed[0])
                    self.assertEqual(
                        changed.read_bytes(),
                        b"preserve final permission callback drift",
                    )

    def test_reviewed_output_pins_refuse_before_any_consumer_process(self):
        with authored_native_receiving_fixture(self) as (
            initial,
            _inputs,
            native,
            state,
        ):
            parent = (
                initial.scratch.context.workspace
                / initial.files.reviewed.plan.graph.common.output_directory
            )
            state["close_receiving"]()
            with state["reopen_receiving"]() as (current, wrapper):
                with _reserve_authored_reopened_namespace(
                    current,
                    wrapper,
                    old_output_budget=RetainedCargoOutputBudget(
                        512 * 1024**2, 4 * 1024**3
                    ),
                ) as namespace:
                    materialized = _reopen_authored_retained_cargo_packages(
                        current,
                        namespace,
                        new_output_budget=RetainedCargoOutputBudget(
                            512 * 1024**2, 4 * 1024**3
                        ),
                    )
                    observed = read_authored_retained_cargo_execution_inputs(
                        materialized, environment=native.environment
                    )
                    # Actual tool binding remains measured, but its concrete
                    # reviewed environment pin cannot become logical-container intent.
                    pinned = replace(
                        native.cargo, environment=(("CARGO_TARGET_DIR", str(parent)),)
                    )
                    args = self.arguments(observed, native, {})
                    args["cargo"] = pinned
                    with patch.object(
                        execution,
                        "run_bounded_process",
                        side_effect=AssertionError("consumer process launched"),
                    ) as run:
                        with self.assertRaisesRegex(
                            ValueError, "reviewed-output-pin-refused"
                        ):
                            execution._execute_authored_retained_cargo_consumer_session(
                                materialized, **args
                            )
                        run.assert_not_called()
                    command = current.reviewed.plan.common.gates[0]
                    for pinned_command in (
                        replace(
                            command,
                            environment=(
                                RepositoryBuildEnvironment(
                                    "CARGO_TARGET_DIR", str(parent)
                                ),
                            ),
                        ),
                        replace(
                            command, argv=(*command.argv, "--target-dir", str(parent))
                        ),
                        replace(
                            command, argv=(*command.argv, "--target-dir=" + str(parent))
                        ),
                    ):
                        with self.subTest(command=pinned_command):
                            with self.assertRaisesRegex(
                                ValueError, "reviewed-output-pin-refused"
                            ):
                                outputs._require_reopened_command_pins(
                                    pinned_command,
                                    native.cargo,
                                    output=namespace.cargo_output,
                                    project_root=current.reviewed.project.root,
                                )
                    self.assertFalse(any(namespace.cargo_output.iterdir()))
                    namespace.require_original_files()

    def test_actual_nested_cargo_config_is_checked_but_unrelated_config_is_not(self):
        import json

        from tests.support.fixtures_retained_cargo_native_v2 import (
            NativeReceivingFixture,
        )

        actual_setup = NativeReceivingFixture.setUp
        for nested_pin in (False, True):
            with self.subTest(nested_pin=nested_pin):

                def setup(candidate, nested_pin=nested_pin):
                    actual_setup(candidate)
                    project = candidate.base / "converted"
                    implementation = json.loads(
                        (project / ".literate/legacy-lift-shift.json").read_bytes()
                    )["implementation_directory"]
                    workspace = project / implementation
                    # This is ordinary source, never Cargo configuration.
                    (workspace / "config").write_bytes(
                        b"ordinary non-TOML source content !@#"
                    )
                    gate = replace(
                        candidate.plan.gates[0],
                        working_directory=implementation + "/app",
                    )
                    candidate.plan = replace(candidate.plan, gates=(gate,))
                    candidate.inputs = replace(candidate.inputs, current_gates=(gate,))
                    if nested_pin:
                        config = workspace / "app/.cargo/config.toml"
                        config.parent.mkdir()
                        config.write_text(
                            '[build]\nbuild-dir = "'
                            + (workspace / "cargo-output").as_posix()
                            + '"\n'
                        )

                with patch.object(NativeReceivingFixture, "setUp", new=setup):
                    with authored_native_receiving_fixture(self) as (
                        initial,
                        _inputs,
                        native,
                        state,
                    ):
                        state["close_receiving"]()
                        with state["reopen_receiving"]() as (current, wrapper):
                            with _reserve_authored_reopened_namespace(
                                current,
                                wrapper,
                                old_output_budget=RetainedCargoOutputBudget(
                                    512 * 1024**2, 4 * 1024**3
                                ),
                            ) as namespace:
                                materialized = _reopen_authored_retained_cargo_packages(
                                    current,
                                    namespace,
                                    new_output_budget=RetainedCargoOutputBudget(
                                        512 * 1024**2, 4 * 1024**3
                                    ),
                                )
                                observed = (
                                    read_authored_retained_cargo_execution_inputs(
                                        materialized, environment=native.environment
                                    )
                                )
                                if nested_pin:
                                    with patch.object(
                                        execution,
                                        "run_bounded_process",
                                        side_effect=AssertionError(
                                            "consumer process launched"
                                        ),
                                    ) as run:
                                        with self.assertRaisesRegex(
                                            ValueError,
                                            "configuration-output-pin-refused",
                                        ):
                                            execution._execute_authored_retained_cargo_consumer_session(
                                                materialized,
                                                **self.arguments(observed, native, {}),
                                            )
                                        run.assert_not_called()
                                else:
                                    outputs._require_reopened_configuration(
                                        observed, output=namespace.cargo_output
                                    )
                                self.assertFalse(any(namespace.cargo_output.iterdir()))
