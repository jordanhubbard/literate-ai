"""Context-selection state fixtures, not SDK admission or native qualification."""

import unittest
from contextvars import copy_context
from types import SimpleNamespace

from literate_ai.adapters import node_sdk_host as host
from literate_ai.adapters.node_sdk_project_acceptance import (
    LocalNodeSDKProjectAcceptance,
)


class NodeSDKHostScopeTests(unittest.TestCase):
    def setUp(self):
        self.manual = object()
        self.oracle = object()
        self.ports = SimpleNamespace(
            node_sdk_project_acceptance=self.manual,
            independent_acceptance_oracle=self.oracle,
        )
        self.bound = SimpleNamespace(ports=self.ports)
        # Only selection/retirement is tested. This shell has no snapshot,
        # original invocation, loaded oracle, package or execution authorization.
        self.policy = object.__new__(LocalNodeSDKProjectAcceptance)
        self.policy.ports = self.ports
        self.execution = object()

    def test_only_absence_uses_manual_selection(self):
        self.assertIs(host.current_node_sdk_project_acceptance(self.ports), self.manual)
        token = host._CURRENT.set(object())
        try:
            with self.assertRaisesRegex(
                host.NodeSDKHostConfigurationError, "malformed"
            ):
                host.current_node_sdk_project_acceptance(self.ports)
        finally:
            host._CURRENT.reset(token)

    def test_scope_selects_original_and_copied_retired_context_cannot_fallback(self):
        with host._select_policy(self.bound, self.execution, self.policy):
            self.assertIs(
                host.current_node_sdk_project_acceptance(self.ports), self.policy
            )
            copied = copy_context()
        self.assertIs(host.current_node_sdk_project_acceptance(self.ports), self.manual)
        with self.assertRaisesRegex(host.NodeSDKHostConfigurationError, "ended"):
            copied.run(host.current_node_sdk_project_acceptance, self.ports)
        with self.assertRaises(host.NodeSDKHostConfigurationError):
            copied.run(host.current_node_sdk_project_acceptance, self.ports)

    def test_nested_entry_refuses_without_replacing_outer_selection(self):
        with host._select_policy(self.bound, self.execution, self.policy):
            with self.assertRaisesRegex(host.NodeSDKHostConfigurationError, "nest"):
                with host._select_policy(self.bound, self.execution, self.policy):
                    self.fail("nested scope entered")
            self.assertIs(
                host.current_node_sdk_project_acceptance(self.ports), self.policy
            )

    def test_foreign_ports_retire_original_scope(self):
        with self.assertRaises(host.NodeSDKHostConfigurationError):
            with host._select_policy(self.bound, self.execution, self.policy):
                foreign = SimpleNamespace(node_sdk_project_acceptance=self.manual)
                with self.assertRaises(host.NodeSDKHostConfigurationError):
                    host.current_node_sdk_project_acceptance(foreign)
                with self.assertRaises(host.NodeSDKHostConfigurationError):
                    host.current_node_sdk_project_acceptance(self.ports)

    def test_late_oracle_or_manual_write_does_not_restore_or_reopen_scope(self):
        for field in ("independent_acceptance_oracle", "node_sdk_project_acceptance"):
            with self.subTest(field=field):
                previous = getattr(self.ports, field)
                replacement = object()
                with self.assertRaises(host.NodeSDKHostConfigurationError):
                    with host._select_policy(self.bound, self.execution, self.policy):
                        setattr(self.ports, field, replacement)
                        with self.assertRaises(host.NodeSDKHostConfigurationError):
                            host.current_node_sdk_project_acceptance(self.ports)
                self.assertIs(getattr(self.ports, field), replacement)
                # Explicit fixture reset, not production scope cleanup.
                setattr(self.ports, field, previous)

    def test_exception_cleanup_retires_copy_and_preserves_new_field_values(self):
        replacement = object()
        with self.assertRaisesRegex(RuntimeError, "consumer failed"):
            with host._select_policy(self.bound, self.execution, self.policy):
                copied = copy_context()
                self.ports.node_sdk_project_acceptance = replacement
                raise RuntimeError("consumer failed")
        self.assertIs(self.ports.node_sdk_project_acceptance, replacement)
        with self.assertRaises(host.NodeSDKHostConfigurationError):
            copied.run(host.current_node_sdk_project_acceptance, self.ports)
