"""Original typed configuration; injected graph construction, no native execution."""

import copy
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import node_sdk_host as host
from literate_ai.adapters import node_sdk_verifier_authority as membership
from literate_ai.adapters import node_sdk_verifier_authorization as authorization
from literate_ai.adapters import node_sdk_verifier_runtime as runtime
from literate_ai.contracts import canonical_identity
from tests.smoke import test_node_library_acceptance as oracle_fixture
from tests.smoke.test_node_sdk_cross_language import with_provider


class TypedHostConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        _, self.snapshot, self.execution = with_provider(Path(temporary.name))
        oracle_control = oracle_fixture.NodeLibraryOracleTests()
        oracle_control.setUp()
        self.addCleanup(oracle_control.doCleanups)
        self.oracle = oracle_control.load()
        self.calls = []

    def owner(self):
        self.calls.append("owner")

    def acknowledge(self):
        ack = authorization.acknowledge_node_sdk_verifier_execution(
            snapshot=self.snapshot,
            execution=self.execution,
            actor="isolated typed host control",
            reason="original binding qualification",
            authorization_lifetime=timedelta(minutes=10),
            authorization_deadline=datetime.now(UTC) + timedelta(minutes=20),
            acknowledge_identity_only_inputs=True,
        )
        self.addCleanup(membership._retire_acknowledgement, ack)
        return ack

    def configuration(self, **changes):
        args = dict(
            snapshot=self.snapshot,
            expected_execution=self.execution,
            provider_oracles={"provider": self.oracle},
            root_oracle=self.oracle,
            require_current=self.owner,
            environment={},
        )
        args.update(changes)
        return host.LocalNodeSDKHostConfiguration(**args)

    def injected_binding(self, configuration, *, owner=None, closure=None):
        # Keep actual configuration/core and original binding registration, but
        # replace expensive graph validation explicitly. Native tests own that.
        ports = object.__new__(host.LocalStandardLifecyclePorts)
        ports._node_sdk_host_binding = None
        if closure is None:
            closure = SimpleNamespace(require_unchanged=lambda: None)

        def construct(bound, actual_configuration, actual_ports, closure):
            self.assertIs(actual_configuration, configuration)
            bound.configuration, bound.ports, bound.closure = (
                actual_configuration,
                actual_ports,
                closure,
            )
            bound.consumer, bound.target = object(), object()
            bound._require_inputs = configuration._require_bytes
            bound._inspection_binding = runtime.create_runtime_inspection_binding(bound)
            bound.require_current = self.owner if owner is None else owner

        with mock.patch.object(host._BoundAdmission, "__init__", construct):
            result = configuration.bind(ports, closure)
        return result, ports

    def test_mutual_exclusion_precedes_all_user_mapping_or_owner_callbacks(self):
        class Mapping:
            def keys(_self):
                raise AssertionError("configuration mapping read before mode selection")

        for changes in (
            {},
            {"authorize_verifier": self.owner, "verifier_acknowledgement": object()},
        ):
            with self.subTest(changes=tuple(changes)):
                with self.assertRaisesRegex(TypeError, "exactly one"):
                    self.configuration(provider_oracles=Mapping(), **changes)
        self.assertFalse(self.calls)

    def test_manual_identity_remains_version_one_without_owner_invocation(self):
        cfg = self.configuration(authorize_verifier=self.owner)
        expected = canonical_identity(
            {
                "schema": "literate-ai/local-node-sdk-host-configuration@1",
                "authority": self.snapshot.authority.identity.uri,
                "execution": self.execution.identity.uri,
                "root_oracle": self.oracle.identity.uri,
                "providers": [["provider", self.oracle.identity.uri]],
            }
        )
        self.assertEqual(cfg._identity, expected)
        self.assertFalse(self.calls)

    def test_typed_identity_is_separate_and_construction_grants_nothing(self):
        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack)
        self.assertIs(cfg.verifier_acknowledgement, ack)
        self.assertIsNone(cfg.authorize_verifier)
        self.assertIsNone(membership._values(membership._state(ack))[3])
        self.assertEqual(
            cfg._verifier_intent, authorization._verifier_intent_identity(ack)
        )
        self.assertNotEqual(
            cfg._identity, self.configuration(authorize_verifier=self.owner)._identity
        )
        self.assertFalse(self.calls)

    def test_foreign_acknowledgement_refuses_before_owner(self):
        with self.assertRaises(TypeError):
            self.configuration(verifier_acknowledgement=object())
        self.assertFalse(self.calls)

    def test_equal_foreign_snapshot_is_not_original_authority(self):
        ack = self.acknowledge()
        with self.assertRaisesRegex(ValueError, "original authority"):
            self.configuration(
                verifier_acknowledgement=ack, snapshot=copy.copy(self.snapshot)
            )
        self.assertFalse(self.calls)

    def test_cleared_intent_cannot_downgrade_to_manual(self):
        cfg = self.configuration(verifier_acknowledgement=self.acknowledge())
        cfg.verifier_acknowledgement = None
        with self.assertRaisesRegex(ValueError, "intent changed"):
            cfg._require_bytes()
        self.assertFalse(self.calls)

    def test_original_binding_consumes_intent_before_first_owner_callback(self):
        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack)

        def owner():
            state = membership._state(ack)
            bound = membership._values(state)[3]
            self.assertIs(bound[0](), cfg)
            self.assertIs(bound[1](), cfg._binding)
            self.calls.append("consumed owner")

        self.injected_binding(cfg, owner=owner)
        self.assertEqual(self.calls, ["consumed owner"])
        self.assertIsNone(cfg._binding_attempt)
        cfg._require_bytes()

    def test_failed_original_binding_permanently_poisons_intent(self):
        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack)
        with self.assertRaises(TypeError):
            cfg.bind(object(), object())
        with self.assertRaisesRegex(ValueError, "poisoned"):
            membership._state(ack)
        self.assertIsNone(cfg._binding_attempt)
        self.assertFalse(self.calls)

    def test_owner_failure_after_consumption_is_not_replayed(self):
        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack)
        primary = RuntimeError("original owner unavailable")

        def owner():
            self.calls.append("failed owner")
            raise primary

        with self.assertRaises(RuntimeError) as caught:
            self.injected_binding(cfg, owner=owner)
        self.assertIs(caught.exception, primary)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            cfg.bind(object(), object())
        self.assertEqual(self.calls, ["failed owner"])

    def test_second_binding_cannot_reuse_consumed_intent(self):
        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack)
        self.injected_binding(cfg)
        with self.assertRaisesRegex(ValueError, "already bound"):
            cfg.bind(object(), object())
        with self.assertRaisesRegex(ValueError, "poisoned"):
            cfg._require_bytes()
        self.assertEqual(self.calls, ["owner"])

    def test_swallowed_reentry_cannot_publish_outer_binding(self):
        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack)

        def owner():
            with self.assertRaisesRegex(ValueError, "reenter"):
                cfg.bind(object(), object())
            self.calls.append("swallowed reentry")

        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.injected_binding(cfg, owner=owner)
        self.assertEqual(self.calls, ["swallowed reentry"])
        self.assertIsNone(cfg._binding_attempt)

    def test_original_dependency_guard_runs_only_after_binding_consumes_intent(self):
        from literate_ai.adapters.standard_project import (
            ProjectedStandardToolchainClosure,
        )

        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack)
        closure = object.__new__(ProjectedStandardToolchainClosure)
        primary = RuntimeError("original dependency validation stopped")

        def dependency_guard():
            bound = membership._values(membership._state(ack))[3]
            self.assertIs(bound[0](), cfg)
            self.assertIs(bound[1](), cfg._binding)
            self.calls.append("consumed dependency guard")
            raise primary

        # Original closure type and method, stopped at its original first guard.
        # Graph construction is injected; this is an ordering control, not native.
        object.__setattr__(closure, "node_sdk_targets", ())
        object.__setattr__(closure, "rust_harness_compilers", None)
        object.__setattr__(closure, "execution_plan", None)
        object.__setattr__(closure, "dependency_guard", dependency_guard)
        with self.assertRaises(RuntimeError) as caught:
            self.injected_binding(cfg, closure=closure)
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.calls, ["consumed dependency guard"])
        with self.assertRaisesRegex(ValueError, "poisoned"):
            membership._state(ack)

    def _substituted_configuration_helper(self, name, *, bind=False):
        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack) if bind else None
        with mock.patch.object(authorization, name) as substitute:
            with self.assertRaisesRegex(ValueError, "fixed SDK verifier"):
                if bind:
                    self.injected_binding(cfg)
                else:
                    self.configuration(verifier_acknowledgement=ack)
            substitute.assert_not_called()
        self.assertFalse(self.calls)

    def test_substituted_intent_identity_is_not_invoked(self):
        self._substituted_configuration_helper("_verifier_intent_identity")

    def test_substituted_host_intent_check_is_not_invoked(self):
        self._substituted_configuration_helper("_require_host_verifier_intent")

    def test_substituted_binding_helper_is_not_invoked(self):
        self._substituted_configuration_helper("_bind_host_verifier_intent", bind=True)

    def test_host_callback_substitution_withholds_binding_without_foreign_call(self):
        ack = self.acknowledge()
        cfg = self.configuration(verifier_acknowledgement=ack)
        substitute = mock.Mock()
        patcher = mock.patch.object(
            authorization, "_require_host_verifier_operation", substitute
        )

        def owner():
            patcher.start()
            self.calls.append("substituted operation helper")

        try:
            with self.assertRaisesRegex(ValueError, "fixed SDK verifier"):
                self.injected_binding(cfg, owner=owner)
        finally:
            patcher.stop()
        substitute.assert_not_called()
        self.assertEqual(self.calls, ["substituted operation helper"])
        with self.assertRaisesRegex(ValueError, "poisoned"):
            membership._state(ack)
