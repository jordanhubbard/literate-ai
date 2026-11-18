"""Rebuild orchestration controls; no SDK admission or execution qualification."""

import unittest
from copy import copy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from literate_ai.adapters.action_admission import CommandActionWorkerPool
from literate_ai.adapters.node_sdk_host import LocalNodeSDKHostConfiguration
from literate_ai.adapters.standard_rebuild import FilesystemStandardRebuildError
from literate_ai.contracts.model_scopes import RETAINED_SOURCE_PROVIDER
from tests.support import fixtures_test_standard_action_indexing as factory_fixture


class NodeSDKRebuildTests(unittest.TestCase):
    def setUp(self):
        self.fixture = factory_fixture.StandardActionIndexingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        # This exact-type shell tests only assembler routing. The original SDK
        # configuration integrity/binding and live grants are qualified elsewhere.
        self.host = object.__new__(LocalNodeSDKHostConfiguration)
        self.host.snapshot = self.fixture.snapshot
        self.host.expected_execution = self.fixture.execution
        self.host.root_oracle = object()
        self.integrity = self.enterContext(
            patch.object(LocalNodeSDKHostConfiguration, "_require_bytes")
        )
        self.runner = Mock(wraps=self.fixture.source_generation.runner)
        self.fixture.source_generation.runner = self.runner
        self.load_actions = self.enterContext(
            patch(
                "literate_ai.adapters.standard_rebuild.load_action_execution",
                return_value=None,
            )
        )

    def refuse(self, code, **changes):
        with self.assertRaises(FilesystemStandardRebuildError) as raised:
            self.fixture.assemble(node_sdk_host=self.host, **changes)
        self.assertEqual(raised.exception.code, code)
        self.runner.assert_not_called()

    def test_untyped_host_refuses(self):
        with self.assertRaises(TypeError):
            self.fixture.assemble(node_sdk_host=object())
        self.runner.assert_not_called()

    def test_foreign_original_snapshot_refuses_even_with_equal_lock(self):
        self.host.snapshot = copy(self.fixture.snapshot)
        self.refuse("standard_rebuild.node_sdk_authority_mismatch")

    def test_actual_plan_must_match_host_execution(self):
        self.host.expected_execution = SimpleNamespace(identity=object())
        self.refuse("standard_rebuild.node_sdk_authority_mismatch")

    def test_post_planning_snapshot_replacement_refuses(self):
        def change_on_recheck():
            if self.integrity.call_count == 2:
                self.host.snapshot = copy(self.fixture.snapshot)

        self.integrity.side_effect = change_on_recheck
        self.refuse("standard_rebuild.node_sdk_authority_mismatch")

    def test_retained_or_competing_native_owner_refuses(self):
        for changes in (
            {"retained_source": object()},
            {"accepted_source_provider_id": RETAINED_SOURCE_PROVIDER},
            {
                "prepared": replace(
                    self.fixture.rebuild.prepared,
                    locked_authority_snapshot=self.fixture.snapshot,
                    native_sdk_inputs=object(),
                )
            },
        ):
            with self.subTest(fields=tuple(changes)):
                self.refuse(
                    "standard_rebuild.node_sdk_execution_unsupported", **changes
                )

    def test_explicit_action_workers_refuse(self):
        self.refuse(
            "standard_rebuild.node_sdk_execution_unsupported",
            action_workers=object.__new__(CommandActionWorkerPool),
            action_source_cas=self.fixture.admission.fixture.controller_cas,
        )

    def test_configured_action_workers_refuse_before_admission(self):
        configured = Mock()
        self.load_actions.return_value = configured
        self.refuse("standard_rebuild.node_sdk_execution_unsupported")
        configured.admit.assert_not_called()

    def test_foreign_root_oracle_refuses(self):
        self.refuse(
            "standard_rebuild.node_sdk_oracle_mismatch",
            independent_acceptance_oracle=object(),
        )

    def test_original_host_reaches_existing_runtime_assembler_unchanged(self):
        class ReachedRuntime(Exception):
            pass

        with patch(
            "literate_ai.adapters.standard_rebuild.assemble_filesystem_standard_project_runtime",
            side_effect=ReachedRuntime,
        ) as assemble:
            with self.assertRaises(ReachedRuntime):
                self.fixture.assemble(node_sdk_host=self.host)
        self.assertIs(assemble.call_args.kwargs["node_sdk_host"], self.host)
        self.assertEqual(self.integrity.call_count, 2)
        self.runner.assert_called_once()
