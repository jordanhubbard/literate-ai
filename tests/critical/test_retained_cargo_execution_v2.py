"""Actual bounded Python commands within real v2 publication and input guards.

Provider qualification, tool measurements, Cargo graph semantics and Cargo
metadata are explicit fixtures. These controls execute no native Cargo commands
and qualify neither test protocols nor receiving/installed admission.
"""

import json
import os
import shutil
import sys
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_execution_v2 as execution
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.retained_cargo_execution import RetainedCargoExecutionError
from tests.critical import test_retained_cargo_metadata_inputs_v2 as metadata_fixture


@unittest.skipUnless(
    os.name != "nt" and shutil.which("git") and shutil.which("make"),
    "requires actual POSIX adoption, native publication and closed input custody",
)
class RetainedCargoCommandExecutionV2Tests(unittest.TestCase):
    _fixture = metadata_fixture.RetainedCargoMetadataInputTests
    setUp = _fixture.setUp
    run_materializer = _fixture.run_materializer
    inputs = _fixture.inputs

    def arguments(self, materialized, *, fail_gate=False, gate_script=None):
        scope, environment, metadata, source = self.inputs(materialized)
        script = (
            "import sys\n"
            "if 'metadata' in sys.argv:\n"
            " print(" + repr(json.dumps(metadata)) + ")\n"
            "else:\n"
            " print('actual bounded gate output')\n"
            " print('actual bounded gate detail', file=sys.stderr)\n"
            " sys.exit(" + ("7" if fail_gate else "0") + ")\n"
        )
        if gate_script is not None:
            script = (
                "import sys\n"
                "if 'metadata' in sys.argv:\n"
                " print(" + repr(json.dumps(metadata)) + ")\n"
                "else:\n"
                + "\n".join(" " + line for line in gate_script.splitlines())
                + "\n"
            )

        def measured(identity, command):
            # Synthetic tool measurement; actual Python processes still use the
            # production bounded runner. No native Cargo identity is asserted.
            return LocalComponentToolBinding.from_observed_toolchain(
                SimpleNamespace(
                    identity=identity.uri,
                    command=command,
                    require_unchanged=lambda: None,
                )
            )

        cargo = measured(
            materialized.plan.common.cargo_identity, (sys.executable, "-c", script)
        )
        rustc = measured(materialized.plan.common.rustc_identity, (sys.executable,))
        return (
            dict(
                cargo=cargo,
                rustc=rustc,
                gate_tools={
                    command.argv[0]: cargo for command in materialized.plan.common.gates
                },
                environment=environment,
                consumer_inputs=scope,
                allow_host_execution=True,
            ),
            source,
        )

    def test_actual_bounded_commands_bracket_exact_reviewed_gates(self):
        with self.run_materializer() as materialized:
            arguments, _source = self.arguments(materialized)
            with patch.object(execution, "verify_cargo_workspace_patches_v2") as graph:
                observations = execution.execute_retained_cargo_commands_v2(
                    materialized, **arguments
                )
            self.assertEqual(
                [value.command.step_id for value in observations],
                [
                    "retained-cargo-metadata",
                    "existing-full-tests",
                    "retained-cargo-metadata",
                ],
            )
            self.assertEqual(graph.call_count, 2)
            for call in graph.call_args_list:
                self.assertIs(call.kwargs["plan"], materialized.plan)
                self.assertEqual(call.kwargs["workspace_manifest"], b"workspace")
                self.assertEqual(call.kwargs["lockfile"], b"lock")
            self.assertTrue(all(value.result.returncode == 0 for value in observations))
            self.assertEqual(
                observations[1].result.stdout, b"actual bounded gate output\n"
            )
            self.assertEqual(
                observations[1].result.stderr, b"actual bounded gate detail\n"
            )
            self.assertIn("--locked", observations[0].argv)
            self.assertIn("--offline", observations[0].argv)
            self.assertEqual(list((self.workspace / "cargo-output").iterdir()), [])

    def test_no_process_without_authorization_or_current_measured_tools(self):
        with self.run_materializer() as materialized:
            arguments, _source = self.arguments(materialized)
            with patch.object(
                execution,
                "run_bounded_process",
                side_effect=AssertionError("not admitted"),
            ) as process:
                for changes in (
                    {"allow_host_execution": False},
                    {"gate_tools": {}},
                    {"timeout_seconds": float("inf")},
                    {"timeout_seconds": 10801},
                    {"cargo": arguments["rustc"]},
                ):
                    with (
                        self.subTest(changes=tuple(changes)),
                        self.assertRaises(ValueError),
                    ):
                        execution.execute_retained_cargo_commands_v2(
                            materialized, **{**arguments, **changes}
                        )
                process.assert_not_called()

    def test_graph_refusal_after_actual_metadata_stops_before_gate(self):
        with self.run_materializer() as materialized:
            arguments, _source = self.arguments(materialized)
            with patch.object(
                execution,
                "verify_cargo_workspace_patches_v2",
                side_effect=ValueError("explicit graph fixture refusal"),
            ):
                with self.assertRaises(RetainedCargoExecutionError) as failure:
                    execution.execute_retained_cargo_commands_v2(
                        materialized, **arguments
                    )
            self.assertEqual(len(failure.exception.observations), 1)
            self.assertEqual(failure.exception.observations[0].result.returncode, 0)
            self.assertIn(
                "explicit graph fixture refusal", str(failure.exception.__cause__)
            )

    def test_actual_nonzero_gate_retains_outputs_and_stops_final_metadata(self):
        with self.run_materializer() as materialized:
            arguments, _source = self.arguments(materialized, fail_gate=True)
            with patch.object(execution, "verify_cargo_workspace_patches_v2"):
                with self.assertRaises(RetainedCargoExecutionError) as failure:
                    execution.execute_retained_cargo_commands_v2(
                        materialized, **arguments
                    )
            observations = failure.exception.observations
            self.assertEqual(len(observations), 2)
            self.assertEqual(observations[-1].result.returncode, 7)
            self.assertEqual(
                observations[-1].result.stdout, b"actual bounded gate output\n"
            )
            self.assertEqual(
                observations[-1].result.stderr, b"actual bounded gate detail\n"
            )

    def test_actual_input_mutation_after_real_gate_refuses_and_preserves_bytes(self):
        with self.run_materializer() as materialized:
            arguments, source = self.arguments(materialized)
            original = source.read_bytes()
            changed = original.replace(b"dependency", b"DEPENDENCY")
            self.assertEqual(len(original), len(changed))
            actual_run = execution.run_bounded_process
            calls = []

            def run(*args, **kwargs):
                result = actual_run(*args, **kwargs)
                calls.append(result.returncode)
                if len(calls) == 2:
                    source.write_bytes(changed)
                return result

            with (
                patch.object(execution, "verify_cargo_workspace_patches_v2"),
                patch.object(execution, "run_bounded_process", side_effect=run),
            ):
                with self.assertRaises(RetainedCargoExecutionError) as failure:
                    execution.execute_retained_cargo_commands_v2(
                        materialized, **arguments
                    )
            self.assertEqual(calls, [0, 0])
            self.assertEqual(len(failure.exception.observations), 2)
            self.assertEqual(source.read_bytes(), changed)
            self.assertIn("custody-changed", str(failure.exception.__cause__))

    def test_real_elapsed_deadline_prevents_the_first_process(self):
        with self.run_materializer() as materialized:
            arguments, _source = self.arguments(materialized)
            with patch.object(
                execution,
                "run_bounded_process",
                side_effect=AssertionError("past deadline"),
            ) as process:
                with self.assertRaises(RetainedCargoExecutionError) as failure:
                    execution.execute_retained_cargo_commands_v2(
                        materialized, **arguments, timeout_seconds=1e-12
                    )
                process.assert_not_called()
            self.assertEqual(failure.exception.observations, ())
            self.assertIn("deadline-exceeded", str(failure.exception.__cause__))

    def test_successful_parent_cannot_leave_a_runnable_owned_descendant(self):
        with self.run_materializer() as materialized:
            marker = self.workspace / "cargo-output/owned-child.json"
            nonce = uuid.uuid4().hex
            child = (
                "import json,os,sys,time\n"
                "with open(sys.argv[1], 'x') as f:\n"
                " json.dump({'pid':os.getpid(),'nonce':sys.argv[2]}, f)\n"
                "time.sleep(5)\n"
            )
            parent = (
                "import subprocess,time,pathlib,json\n"
                "subprocess.Popen([sys.executable,'-c',"
                + repr(child)
                + ","
                + repr(str(marker))
                + ","
                + repr(nonce)
                + "], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "deadline=time.monotonic()+2\n"
                "while True:\n"
                " try:\n"
                "  row=json.loads(pathlib.Path("
                + repr(str(marker))
                + ").read_text())\n"
                "  if row['nonce']==" + repr(nonce) + ": break\n"
                " except (FileNotFoundError,ValueError): pass\n"
                " if time.monotonic()>deadline:\n"
                "  raise RuntimeError('child did not start')\n"
                " time.sleep(0.01)\n"
            )
            arguments, _source = self.arguments(materialized, gate_script=parent)
            actual_run = execution.run_bounded_process
            observed = []

            def run(*args, **kwargs):
                result = actual_run(*args, **kwargs)
                if "metadata" not in args[0][3:]:
                    # Observe immediately after the real parent's successful
                    # return, before expensive closing guards could conceal a
                    # leaked child's own finite five-second lease expiry.
                    raw = json.loads(marker.read_text())
                    self.assertEqual(raw["nonce"], nonce)
                    ps = actual_run(
                        ("/bin/ps", "-p", str(raw["pid"]), "-o", "pid=,stat=,command="),
                        cwd=self.workspace,
                        environment={"PATH": "/usr/bin:/bin"},
                        timeout_seconds=3,
                        stdout_limit_bytes=16384,
                        stderr_limit_bytes=4096,
                        error_prefix="fixture.child-observation",
                        terminate_descendants=True,
                    )
                    self.assertIn(ps.returncode, (0, 1))
                    self.assertEqual(ps.stderr, b"")
                    words = ps.stdout.decode().strip().split(None, 2)
                    live = (
                        len(words) == 3
                        and nonce in words[2]
                        and not words[1].startswith("Z")
                    )
                    observed.append((result.returncode, live))
                return result

            with (
                patch.object(execution, "verify_cargo_workspace_patches_v2"),
                patch.object(execution, "run_bounded_process", side_effect=run),
            ):
                observations = execution.execute_retained_cargo_commands_v2(
                    materialized, **arguments
                )
            self.assertEqual(observed, [(0, False)])
            self.assertEqual(len(observations), 3)
            # The real original process group is terminated by the canonical
            # owner. A zombie is terminated, not a kernel-reaping claim. The
            # child's own finite lease also bounds a failing regression test.
