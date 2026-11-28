"""Original owner propagation and tiny owned-process deadline controls.

The subprocesses are fixed Python sleep fixtures, not generated/native acceptance.
"""

import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from unittest import mock

from literate_ai.adapters._processes import process_tree_termination_wait_seconds
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.lifecycle import standard_local
from literate_ai.adapters.models import coding_cli
from literate_ai.application import native_root_run as run
from literate_ai.application.source_generation_scheduling import (
    schedule_source_generation_executions,
)
from literate_ai.contracts import ComponentChangeSurface, ComponentInvalidationDecision
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from tests.support import fixtures_test_source_generation_scheduling as source_fixture


class NativeRootDeadlinePropagationTests(unittest.TestCase):
    def owner(self, seconds=10, **clocks):
        return run.open_native_root_run(
            NativeRootRunPolicy(seconds, 3),
            project_identity=canonical_identity({"project": "fixed-fixture"}),
            framework_distribution_identity=canonical_identity({"framework": 1}),
            lifecycle_policy_identity=canonical_identity({"policy": 1}),
            require_current=lambda: None,
            **clocks,
        )

    def test_absent_context_preserves_original_cap_and_conveys_no_owner(self):
        cap = 10.25
        self.assertIsNone(run.current_native_root_run())
        self.assertIs(run.native_root_timeout(cap), cap)

    def test_same_owner_nested_context_resets_even_after_failure(self):
        with self.owner() as owner:
            with self.assertRaisesRegex(RuntimeError, "stop"):
                with run.activate_native_root_run(owner):
                    with run.activate_native_root_run(owner):
                        self.assertIs(run.current_native_root_run(), owner)
                        raise RuntimeError("stop")
            self.assertIsNone(run.current_native_root_run())
            self.assertGreater(owner.remaining(), 0)

    def test_context_rejects_other_owner_projection_and_closed_owner(self):
        with self.owner() as first, self.owner() as second:
            with run.activate_native_root_run(first):
                with self.assertRaises(run.NativeRootRunError):
                    with run.activate_native_root_run(second):
                        self.fail("replaced original owner")
                self.assertIs(run.current_native_root_run(), first)
            with self.assertRaises(run.NativeRootRunError):
                with run.activate_native_root_run(first.deadline):
                    self.fail("projection activated")
        with self.assertRaises(run.NativeRootRunError):
            with run.activate_native_root_run(first):
                self.fail("closed owner activated")

    def test_each_wait_intersects_elapsed_original_and_operation_caps(self):
        clock = [1_000_000_000]
        with self.owner(
            10, utc_clock=lambda: clock[0], monotonic_clock=lambda: clock[0]
        ) as owner:
            with run.activate_native_root_run(owner):
                self.assertEqual(run.native_root_timeout(3), 3)
                clock[0] += 8_000_000_000
                self.assertEqual(run.native_root_timeout(60), 2)
                self.assertEqual(run.native_root_timeout(1), 1)
                clock[0] += 2_000_000_000
                with self.assertRaises(run.NativeRootRunError):
                    run.native_root_timeout(60)

    def test_copy_context_propagates_same_owner_without_leaking_to_other_task(self):
        with self.owner() as owner, ThreadPoolExecutor(max_workers=1) as pool:
            with run.activate_native_root_run(owner):
                seen = pool.submit(
                    copy_context().run, run.current_native_root_run
                ).result()
                self.assertIs(seen, owner)
                self.assertIsNone(pool.submit(run.current_native_root_run).result())

    def test_source_generation_pool_receives_original_owner(self):
        fixture = source_fixture._PreparedFixture()
        self.addCleanup(fixture.close)
        execution = fixture.execution
        revisions = tuple(p.component_revision for p in execution.generation_plans)
        invalidation = ComponentInvalidationDecision(
            "fixture",
            execution.root_revision,
            ComponentChangeSurface.LOCAL_AUTHORITY,
            revisions,
            revisions,
            revisions,
        )
        observations = []
        lock = threading.Lock()
        with self.owner() as owner, run.activate_native_root_run(owner):

            def generate(node):
                with lock:
                    observations.append(run.current_native_root_run())
                return source_fixture._output(node)

            outputs = schedule_source_generation_executions(
                execution,
                invalidation=invalidation,
                prepared_nodes=fixture.by_uri,
                runner=generate,
                max_parallelism=2,
            )
        self.assertEqual(len(outputs), len(execution.generation_plans))
        self.assertTrue(observations)
        self.assertTrue(all(observed is owner for observed in observations))

    def test_local_command_actual_wait_uses_remaining_original_bound(self):
        clock = [1_000_000_000]
        completed = subprocess.CompletedProcess(("fixed",), 0, "", "")
        with self.owner(
            10, utc_clock=lambda: clock[0], monotonic_clock=lambda: clock[0]
        ) as owner:
            with (
                run.activate_native_root_run(owner),
                mock.patch.object(
                    standard_local, "run_with_tree_kill", return_value=completed
                ) as process,
            ):
                clock[0] += 7_000_000_000
                standard_local.LocalStandardLifecyclePorts._run_with_environment(
                    None,
                    ("fixed",),
                    cwd=Path.cwd(),
                    environment={},
                    timeout_seconds=60,
                )
                self.assertEqual(process.call_args.kwargs["timeout"], 3)
        with mock.patch.object(
            standard_local, "run_with_tree_kill", return_value=completed
        ) as process:
            standard_local.LocalStandardLifecyclePorts._run_with_environment(
                None,
                ("fixed",),
                cwd=Path.cwd(),
                environment={},
                timeout_seconds=60,
            )
            self.assertEqual(process.call_args.kwargs["timeout"], 60)

    def test_bounded_builder_stops_tiny_owned_process_at_original_expiry(self):
        started = time.monotonic()
        with self.owner(1) as owner, run.activate_native_root_run(owner):
            with self.assertRaises(run.NativeRootRunError):
                run_bounded_process(
                    (sys.executable, "-c", "import time; time.sleep(3)"),
                    cwd=None,
                    environment={},
                    timeout_seconds=10,
                    stdout_limit_bytes=1024,
                    stderr_limit_bytes=1024,
                    error_prefix="fixed_sleep",
                    trace=False,
                )
        self.assertLess(
            time.monotonic() - started,
            2.5 + process_tree_termination_wait_seconds(),
        )

    def test_coding_cli_stops_tiny_owned_process_at_original_expiry(self):
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as temporary:
            with self.owner(1) as owner, run.activate_native_root_run(owner):
                with self.assertRaises(run.NativeRootRunError):
                    coding_cli._run_bounded(
                        (sys.executable, "-c", "import time; time.sleep(3)"),
                        cwd=Path(temporary),
                        environment={},
                        timeout_seconds=10,
                        maximum_stdout_bytes=1024,
                        maximum_stderr_bytes=1024,
                        trace_output=False,
                    )
        self.assertLess(
            time.monotonic() - started,
            2.5 + process_tree_termination_wait_seconds(),
        )

    def test_coding_cli_legacy_short_process_retains_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = coding_cli._run_bounded(
                (sys.executable, "-c", "print('fixed')"),
                cwd=Path(temporary),
                environment={},
                timeout_seconds=5,
                maximum_stdout_bytes=1024,
                maximum_stderr_bytes=1024,
                trace_output=False,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), b"fixed")
