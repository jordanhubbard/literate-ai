"""Real native original observations survive closure without reviving custody.

Provider admission is the explicit fixture. No model generation, source
retirement, full admission receipt, reopened namespace or release is qualified.
"""

import copy
import inspect
import os
import pickle
import shutil
import time
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_execution as authored
from literate_ai.adapters import retained_cargo_test_execution as preparation
from literate_ai.adapters.retained_native_dependencies import RetainedNativeDependencies
from tests.support.fixtures_authored_retained_cargo_native import (
    authored_native_receiving_fixture,
)

LITAI_TEST_PRIORITY = 10
LITAI_TEST_SERIAL = True


@unittest.skipUnless(
    os.name != "nt" and all(shutil.which(x) for x in ("cargo", "rustc", "make", "git")),
    "requires native POSIX Cargo/Rust and actual retained Make/Git adoption",
)
class AuthoredNativeCompletionTests(unittest.TestCase):
    @contextmanager
    def executed(self):
        with authored_native_receiving_fixture(self, with_build_output=True) as (
            materialized,
            inputs,
            native,
            state,
        ):
            created = []
            factory = preparation._prepare_retained_native_session

            def capture(**kwargs):
                # Retain the exact original execution deadline, not a fresh900s.
                deadline = inspect.getclosurevars(kwargs["run"]).nonlocals["deadline"]
                observed = factory(**kwargs)
                created.append((observed, deadline))
                return observed

            with patch.object(preparation, "_prepare_retained_native_session", capture):
                result = authored.execute_authored_retained_cargo_consumer(
                    materialized,
                    cargo=native.cargo,
                    rustc=native.rustc,
                    gate_tools={"cargo": native.cargo},
                    environment=native.environment,
                    consumer_inputs=inputs,
                    allow_host_execution=True,
                    read_exclusion_permission=native.read_permission,
                    timeout_seconds=900,
                )
            self.assertEqual(len(created), 1)
            observed, deadline = created[0]
            self.assertIs(type(observed), preparation._PreparedRetainedNativeTests)
            self.assertTrue(observed.native_dependencies)
            self.assertTrue(observed.files.build_outputs.trees)
            self.assertEqual(
                len(result.target_outcomes),
                len(materialized.files.reviewed.inventory.targets),
            )
            self.assertTrue(result.observations)
            state["close_receiving"]()
            self.assertTrue(state["closed"])
            self.assertFalse(state["active"])
            with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
                inputs.current_identity(environment=native.environment)
            with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
                observed.binary_guard()
            yield observed, deadline

    def test_original_native_facts_after_close_keep_the_original_deadline(self):
        with self.executed() as (observed, deadline):
            for owner in (observed, observed.files):
                for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                    with self.subTest(owner=type(owner), operation=operation.__name__):
                        with self.assertRaises(TypeError):
                            operation(owner)
            observed.refresh_native_dependencies(deadline=deadline)
            observed.require_original_files()
            with (
                patch.object(preparation.time, "monotonic", return_value=deadline + 1),
                patch.object(
                    RetainedNativeDependencies,
                    "require_unchanged",
                    side_effect=AssertionError("expired inspection"),
                ) as refresh,
            ):
                with self.assertRaisesRegex(ValueError, "completion-deadline"):
                    observed.refresh_native_dependencies(deadline=deadline)
                refresh.assert_not_called()
            original = RetainedNativeDependencies.require_unchanged
            calls = 0
            with patch.object(
                preparation.time, "monotonic", return_value=time.monotonic()
            ) as clock:

                def expire(candidate):
                    nonlocal calls
                    original(candidate)
                    calls += 1
                    clock.return_value = deadline + 1

                with patch.object(
                    RetainedNativeDependencies, "require_unchanged", expire
                ):
                    with self.assertRaisesRegex(ValueError, "completion-deadline"):
                        observed.refresh_native_dependencies(deadline=deadline)
            self.assertEqual(calls, 1)
            observed.require_original_files()

    def test_inspector_graph_change_refuses_even_when_original_files_stay_current(self):
        with self.executed() as (observed, deadline):
            observed.require_original_files()
            # An explicit negative inspector-port response. Real gates above
            # executed; this refusal never supplies successful native evidence.
            with patch(
                "literate_ai.adapters.retained_native_dependencies.PortableHostDependencyObserver.observe",
                return_value=SimpleNamespace(components=(), edges=()),
            ) as inspect_graph:
                with self.assertRaisesRegex(ValueError, "native.observation-changed"):
                    observed.refresh_native_dependencies(deadline=deadline)
                inspect_graph.assert_called_once()
            observed.require_original_files()

    def test_inspector_late_outdir_mutation_refuses_and_preserves_changed_bytes(self):
        from literate_ai.adapters.dependencies.observation import (
            PortableHostDependencyObserver,
        )

        with self.executed() as (observed, deadline):
            output = observed.files.build_outputs.trees[0][0] / "completion.txt"
            before = output.read_bytes()
            self.assertEqual(before, b"owned build output")
            original = PortableHostDependencyObserver.observe
            calls = 0

            def changed(observer, *args, **kwargs):
                nonlocal calls
                value = original(observer, *args, **kwargs)
                calls += 1
                if calls == 1:
                    output.write_bytes(before + b" preserve late inspector mutation")
                return value

            with patch.object(PortableHostDependencyObserver, "observe", changed):
                with self.assertRaises(ValueError):
                    observed.refresh_native_dependencies(deadline=deadline)
            self.assertEqual(calls, len(observed.native_dependencies))
            self.assertEqual(
                output.read_bytes(), before + b" preserve late inspector mutation"
            )
