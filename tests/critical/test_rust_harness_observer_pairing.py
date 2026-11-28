"""Original native observer pairing through controlled protocol observations.

Real executor/filesystem/input guards run, but native observers and commands are
explicit fixture protocols. These controls grant no native qualification.
"""

import os
import unittest
from contextlib import contextmanager
from unittest import mock

from literate_ai.adapters import rust_library_harness_execution as executor
from literate_ai.adapters.builders.cargo import CargoToolchain
from literate_ai.adapters.builders.rust import RustToolchain
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from tests.critical import test_rust_harness_guard_budget as fixture


@unittest.skipUnless(os.name == "posix", "owned POSIX protocol fixtures")
class RustHarnessObserverPairingTests(unittest.TestCase):
    metadata = fixture.RustHarnessGuardBudgetTests.metadata
    operate = fixture.RustHarnessGuardBudgetTests.operate

    def setUp(self):
        fixture.RustHarnessGuardBudgetTests.setUp(self)
        self.authoring_guard = self.cargo._authority_guard
        self.mode = None
        self.library_callbacks = 0
        self.replacement_calls = []
        self.original_failure = OSError("original admitted observer failure")

    def replace_observer(self, owner_type):
        def replacement(owner, *_args, **_kwargs):
            self.replacement_calls.append(owner)

        owner_type.require_unchanged = replacement

    def library_current(self):
        fixture.RustHarnessGuardBudgetTests.library_current(self)
        self.library_callbacks += 1
        if self.library_callbacks != 1:
            return
        if self.mode == "cargo-function":
            self.replace_observer(CargoToolchain)
        elif self.mode == "rust-function":
            self.replace_observer(RustToolchain)
        elif self.mode == "same-owner-guard":
            object.__setattr__(
                self.rustc, "_authority_guard", self.rust_owner._require_files_unchanged
            )

    def observe(self, kind, owner, environment, timeout_seconds):
        fixture.RustHarnessGuardBudgetTests.observe(
            self, kind, owner, environment, timeout_seconds
        )
        if kind == "cargo" and self.mode == "cargo-changes-rust":
            self.replace_observer(RustToolchain)
        if kind == "cargo" and self.mode == "original-error":
            raise self.original_failure

    def native_protocol(self, argv, **kwargs):
        result = fixture.RustHarnessGuardBudgetTests.native_protocol(
            self, argv, **kwargs
        )
        if self.mode == "command-changes-observer":
            self.replace_observer(RustToolchain)
        return result

    def assert_tool_refusal(self):
        with self.assertRaises(ComponentAcceptanceError) as refused:
            self.operate()
        self.assertEqual(
            refused.exception.code, "component_acceptance.rust_harness_tool_mismatch"
        )
        self.assertEqual(self.replacement_calls, [])

    def test_genuine_rebound_observers_keep_real_protocol_measurements_and_budgets(
        self,
    ):
        self.operate()
        self.assertEqual(len(self.commands), 4)
        self.assertGreaterEqual(len(self.probes), 12)
        self.assertEqual(
            [kind for kind, *_ in self.probes],
            ["cargo", "rust"] * (len(self.probes) // 2),
        )
        self.assertGreaterEqual(self.library_callbacks, 8)
        self.assertEqual(self.replacement_calls, [])

    def test_initial_stale_authoring_guard_cannot_pair_with_current_observer(self):
        original = executor.execute_rust_library_harness

        @contextmanager
        def stale(oracle, **kwargs):
            object.__setattr__(
                kwargs["cargo"], "_authority_guard", self.authoring_guard
            )
            with original(oracle, **kwargs) as value:
                yield value

        with mock.patch.object(executor, "execute_rust_library_harness", stale):
            self.assert_tool_refusal()
        self.assertEqual(self.probes, [])
        self.assertEqual(self.commands, [])

    def test_library_callback_cannot_replace_cargo_function_with_same_owner(self):
        self.mode = "cargo-function"
        self.assert_tool_refusal()
        self.assertEqual(self.probes, [])
        self.assertEqual(self.commands, [])

    def test_library_callback_cannot_replace_rust_function_with_same_owner(self):
        self.mode = "rust-function"
        self.assert_tool_refusal()
        self.assertEqual(self.probes, [])
        self.assertEqual(self.commands, [])

    def test_library_callback_cannot_replace_guard_with_another_same_owner_method(self):
        self.mode = "same-owner-guard"
        self.assert_tool_refusal()
        self.assertEqual(self.probes, [])
        self.assertEqual(self.commands, [])

    def test_cargo_observer_cannot_replace_following_rust_observer(self):
        self.mode = "cargo-changes-rust"
        self.assert_tool_refusal()
        self.assertEqual([kind for kind, *_ in self.probes], ["cargo"])
        self.assertEqual(self.commands, [])

    def test_command_callback_cannot_replace_observer_before_closing_guards(self):
        self.mode = "command-changes-observer"
        self.assert_tool_refusal()
        self.assertEqual(len(self.commands), 1)
        self.assertEqual([kind for kind, *_ in self.probes], ["cargo", "rust"])

    def test_record_callback_cannot_replace_observer_before_returning_record(self):
        original = executor.execute_rust_library_harness
        recorded = []

        @contextmanager
        def recording(oracle, **kwargs):
            original_record = kwargs["record_bytes"]

            def record(content):
                recorded.append(True)
                self.replace_observer(CargoToolchain)
                return original_record(content)

            kwargs["record_bytes"] = record
            with original(oracle, **kwargs) as value:
                yield value

        with mock.patch.object(executor, "execute_rust_library_harness", recording):
            self.assert_tool_refusal()
        self.assertEqual(len(recorded), 1)
        self.assertEqual(len(self.commands), 1)

    def test_observation_record_callback_cannot_mutate_observer_before_first_yield(
        self,
    ):
        original = executor.execute_rust_library_harness
        recorded = []
        yielded = []

        @contextmanager
        def recording(oracle, **kwargs):
            original_record = kwargs["record_bytes"]

            def record(content):
                recorded.append(True)
                # Four successful command stdout/stderr pairs precede the
                # observation's lockfile/manifest/native executable callbacks.
                if len(recorded) == 9:
                    self.replace_observer(RustToolchain)
                return original_record(content)

            kwargs["record_bytes"] = record
            with original(oracle, **kwargs) as value:
                yielded.append(True)
                yield value

        with mock.patch.object(executor, "execute_rust_library_harness", recording):
            self.assert_tool_refusal()
        self.assertEqual(len(recorded), 9)
        self.assertEqual(len(self.commands), 4)
        self.assertEqual(yielded, [])

    def test_original_observer_exception_identity_is_preserved(self):
        self.mode = "original-error"
        with self.assertRaises(OSError) as raised:
            self.operate()
        self.assertIs(raised.exception, self.original_failure)
        self.assertEqual(self.commands, [])
        self.assertEqual(self.replacement_calls, [])

    def test_existing_remaining_operation_deadline_still_refuses_before_command(self):
        self.near_deadline = True
        with self.assertRaises(ComponentAcceptanceError) as refused:
            self.operate()
        self.assertEqual(
            refused.exception.code, "component_acceptance.rust_harness_deadline"
        )
        self.assertEqual(self.commands, [])
        self.assertEqual([kind for kind, *_ in self.probes], ["cargo", "rust"])
