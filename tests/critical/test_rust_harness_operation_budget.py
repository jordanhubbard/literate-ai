"""Expired verifier work refuses without poisoning a longer original run.

The executor and real filesystem guards run with controlled command protocols.
These tests do not execute Cargo/Rust or establish native qualification.
"""

import os
import unittest
from contextlib import contextmanager
from unittest import mock

from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from tests.critical import test_rust_harness_outcome as outcomes


@unittest.skipUnless(os.name == "posix", "owned POSIX protocol fixture")
class RustHarnessOperationBudgetTests(unittest.TestCase):
    setUp = outcomes.RustHarnessOutcomeTests.setUp
    observe = outcomes.RustHarnessOutcomeTests.observe
    metadata = outcomes.RustHarnessOutcomeTests.metadata
    library_current = outcomes.RustHarnessOutcomeTests.library_current
    native_protocol = outcomes.RustHarnessOutcomeTests.native_protocol
    binding = outcomes.RustHarnessOutcomeTests.binding
    operate = outcomes.RustHarnessOutcomeTests.operate

    def test_expiry_during_fresh_input_guards_preserves_original_root_budget(self):
        original_open = outcomes.open_native_root_run
        current_library = self.library_current
        original_remaining = []

        def elapsed_library_check():
            current_library()
            # The original operation is 180 seconds; its fresh guards consume
            # that budget before the first version probe can be dispatched.
            self.clock = 181.0

        self.library_current = elapsed_library_check

        @contextmanager
        def longer_original_run(_policy, **kwargs):
            with original_open(NativeRootRunPolicy(600, 3), **kwargs) as run:
                try:
                    yield run
                except ComponentAcceptanceError:
                    # Observe before normal context cleanup closes this owner.
                    run.require_current()
                    original_remaining.append(run.remaining())
                    raise

        with (
            mock.patch.object(outcomes, "open_native_root_run", longer_original_run),
            self.assertRaises(ComponentAcceptanceError) as caught,
        ):
            self.operate(lambda *_: self.fail("expired operation yielded acceptance"))
        self.assertEqual(
            caught.exception.code, "component_acceptance.rust_harness_deadline"
        )
        self.assertEqual(original_remaining, [419.0])
        self.assertEqual(self.probes, [])
        self.assertEqual(self.commands, [])
