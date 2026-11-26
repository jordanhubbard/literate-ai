"""Early precheck guard composition with a controlled executor-entry observer.

Backend file/command/export pins are real; framework stages/source registration
are modeled. The observer invokes the actual supplied library callback, then
stops before any native command or successful outcome. No qualification claim.
"""

import os
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import native_candidate_verification as verifier
from literate_ai.adapters.lifecycle.standard_local import (
    LocalComponentToolBinding,
    LocalStandardLifecycleError,
)
from literate_ai.application import native_root_continuation as application
from literate_ai.contracts.identity import canonical_identity
from tests.critical import test_native_root_binding as fixture


class _TraceStop(Exception):
    """Controlled executor entry, never a successful native observation."""


@unittest.skipUnless(os.name == "posix", "owned POSIX protocol fixture setup")
class NativeRootPrecheckGuardTests(unittest.TestCase):
    setUp = fixture.NativeRootBindingTests.setUp
    observe = fixture.NativeRootBindingTests.observe
    metadata = fixture.NativeRootBindingTests.metadata
    library_current = fixture.NativeRootBindingTests.library_current
    native_protocol = fixture.NativeRootBindingTests.native_protocol
    opened = fixture.NativeRootBindingTests.opened
    modeled_registered_candidate = (
        fixture.NativeRootBindingTests.modeled_registered_candidate
    )

    def drive(self, action):
        with self.modeled_registered_candidate() as (output, plan, stage, _tree):
            with self.opened() as (scope, _run), ExitStack() as retained:
                controller = SimpleNamespace(
                    scope=scope, prepared_candidate=self.node, contexts=retained
                )

                @contextmanager
                def controlled_observer(_oracle, **kwargs):
                    action(kwargs["require_library_current"], kwargs, scope, stage)
                    raise _TraceStop("controlled executor entry complete")
                    yield  # pragma: no cover - deliberately no native outcome

                token = application._ACTIVE.set(controller)
                try:
                    with (
                        mock.patch.object(
                            verifier,
                            "_observe_rust_library_harness_outcome",
                            controlled_observer,
                        ),
                        mock.patch.object(
                            LocalComponentToolBinding,
                            "require_unchanged",
                            side_effect=AssertionError(
                                "precheck invoked ambient/default-budget native guard"
                            ),
                        ) as ambient,
                    ):
                        try:
                            verifier._NativeCandidateVerifier(
                                self.prepared, self.ports
                            ).verify_native_root(
                                plan,
                                output,
                                stage.acceptance_evidence,
                                stage.source_generation,
                                controller,
                            )
                        finally:
                            ambient.assert_not_called()
                finally:
                    application._ACTIVE.reset(token)

    def test_actual_callback_has_two_fresh_scope_scans_and_no_ambient_probe(self):
        observed = []

        def action(current, _kwargs, scope, _stage):
            with mock.patch.object(
                scope, "require_current", wraps=scope.require_current
            ) as full:
                for expected in (2, 4, 6):
                    current()
                    observed.append(full.call_count)
                    self.assertEqual(full.call_count, expected)

        with self.assertRaises(_TraceStop):
            self.drive(action)
        self.assertEqual(observed, [2, 4, 6])

    def assert_later_callback_refuses(self, mutate):
        phases = []

        def action(current, kwargs, scope, stage):
            current()
            phases.append("fresh callback")
            mutate(kwargs, scope, stage)
            phases.append("changed custody")
            current()
            self.fail("later callback accepted changed custody")

        with self.assertRaises((ValueError, LocalStandardLifecycleError)):
            self.drive(action)
        self.assertEqual(phases, ["fresh callback", "changed custody"])

    def test_later_callback_rechecks_actual_command_bytes(self):
        def mutate(kwargs, _scope, _stage):
            with Path(kwargs["cargo"].executable).open("ab") as stream:
                stream.write(b"\nchanged original command\n")

        self.assert_later_callback_refuses(mutate)

    def test_later_callback_rechecks_same_oracle_identity(self):
        def mutate(_kwargs, _scope, _stage):
            object.__setattr__(self.fixture.oracle, "component", "changed-component")

        self.assert_later_callback_refuses(mutate)

    def test_later_callback_rechecks_actual_source_generation_binding(self):
        def mutate(_kwargs, _scope, stage):
            object.__setattr__(
                stage.source_generation,
                "prompt_identity",
                canonical_identity({"changed-source-generation": True}),
            )

        self.assert_later_callback_refuses(mutate)

    def test_later_callback_rechecks_actual_export_bytes(self):
        def mutate(kwargs, _scope, _stage):
            with (kwargs["export"] / "Cargo.toml").open("ab") as stream:
                stream.write(b"\n# changed retained export\n")

        self.assert_later_callback_refuses(mutate)

    def test_later_callback_rechecks_original_tool_binding_object(self):
        def mutate(kwargs, _scope, _stage):
            cargo = kwargs["cargo"]
            self.ports.tool_bindings[cargo.authority_identity.uri] = replace(cargo)

        self.assert_later_callback_refuses(mutate)
