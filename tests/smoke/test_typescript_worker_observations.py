"""TypeScript tool observations remain joined to a worker's selected Node."""

import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from literate_ai.adapters.action_capabilities import CAPABILITY_REQUEST_SCHEMA
from literate_ai.adapters.action_dispatch_wire import (
    ActionDispatchDeadline,
    ActionWireError,
)
from literate_ai.adapters.action_tool_selectors import decode_selector_request
from literate_ai.adapters.remote_standard_toolchains import RemoteStandardToolchains
from literate_ai.adapters.standard_toolchain_observations import (
    MAX_STANDARD_TOOL_ROLES,
    StandardToolObservations,
    capture_standard_tool_observations,
)
from literate_ai.contracts import (
    ToolchainConstraint,
    canonical_identity,
    canonical_json_bytes,
)
from tests.support.fixtures_test_remote_standard_toolchains import snapshot
from tests.support.fixtures_test_standard_toolchain_observations import observation


class TypeScriptWorkerObservationTests(unittest.TestCase):
    def setUp(self):
        self.node = replace(
            observation("node"), version="v22.23.4", version_info=(22, 23, 4)
        )
        self.compiler = replace(
            observation(),
            role="typescript",
            toolchain_identity=canonical_identity("selected captured compiler"),
            command=(
                "/worker/node",
                "--eval",
                "hash-bound bootstrap",
                "--",
                "helper-sha",
                "sdk-sha",
            ),
            version="6.0.3",
            version_info=(6, 0, 3),
            node_identity=self.node.toolchain_identity,
        )

    def inventory(self, *tools):
        return StandardToolObservations(
            "linux", tuple(sorted(tools, key=lambda t: t.role))
        )

    def test_exact_node_join_roundtrips_and_denies_missing_or_substituted_node(self):
        inventory = self.inventory(self.node, self.compiler)
        self.assertEqual(
            StandardToolObservations.from_bytes(inventory.to_bytes()), inventory
        )
        for tools in (
            (self.compiler,),
            (
                self.node,
                replace(self.compiler, node_identity=canonical_identity("other node")),
            ),
        ):
            with (
                self.subTest(tools=tuple(t.role for t in tools)),
                self.assertRaises(ValueError),
            ):
                self.inventory(*tools)
        for changes in ({"node_identity": None}, {"role": "unknown-compiler"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.compiler, **changes)

    def test_capture_records_actual_selected_command_and_node_identity(self):
        def tool(row, **extra):
            return SimpleNamespace(
                identity=row.toolchain_identity.uri,
                command=row.command,
                version=row.version,
                version_info=row.version_info,
                environment=row.environment,
                require_unchanged=Mock(),
                **extra,
            )

        node = tool(self.node)
        compiler = tool(self.compiler, node=node)
        current = Mock()
        captured = capture_standard_tool_observations(
            "linux", {"node": node, "typescript": compiler}, require_current=current
        )
        self.assertEqual(captured, self.inventory(self.node, self.compiler))
        self.assertGreaterEqual(current.call_count, 4)
        self.assertGreaterEqual(compiler.require_unchanged.call_count, 3)

    def test_remote_discovery_requires_bounded_compiler_constraint_and_preserves_node(
        self,
    ):
        remote = RemoteStandardToolchains(
            snapshot(self.node, self.compiler), require_current=lambda: None
        )
        constraint = ToolchainConstraint(
            "typescript", minimum_version=(5, 8), maximum_exclusive_version=(7,)
        )
        selected = remote.discover("typescript", constraint, {})
        self.assertEqual(selected.command, self.compiler.command)
        self.assertEqual(selected.node.identity, self.node.toolchain_identity.uri)
        for bad in (
            None,
            ToolchainConstraint("typescript", minimum_version=(5, 8)),
            ToolchainConstraint("typescript", maximum_exclusive_version=(7,)),
            ToolchainConstraint(
                "typescript", minimum_version=(5, 8), maximum_exclusive_version=(6,)
            ),
        ):
            with self.subTest(constraint=bad), self.assertRaises(ActionWireError):
                remote.discover("typescript", bad, {})

    def test_selector_inventory_bound_includes_new_role_without_widening_tokens(self):
        request = {
            "schema": "literate-ai/worker-tool-selector-request@1",
            "capability": {
                "schema": CAPABILITY_REQUEST_SCHEMA,
                "worker_identity": canonical_identity("worker").uri,
                "nonce": "0" * 32,
                "deadline": ActionDispatchDeadline(
                    datetime.now(UTC) + timedelta(minutes=1)
                ).to_dict(),
            },
            "selectors": [
                {"role": f"role-{i:02}", "command": ["node"]}
                for i in range(MAX_STANDARD_TOOL_ROLES)
            ],
        }
        decoded, _ = decode_selector_request(canonical_json_bytes(request))
        self.assertEqual(len(decoded["selectors"]), MAX_STANDARD_TOOL_ROLES)
        request["selectors"].append({"role": "role-extra", "command": ["node"]})
        with self.assertRaises(ActionWireError):
            decode_selector_request(canonical_json_bytes(request))
        request["selectors"].pop()
        request["selectors"][0]["command"] = ["x" * 4097]
        with self.assertRaises(ActionWireError):
            decode_selector_request(canonical_json_bytes(request))
