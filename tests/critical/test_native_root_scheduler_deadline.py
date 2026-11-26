"""Modeled lifecycle capacity waits consume the original finite run lifetime."""

import unittest
from types import SimpleNamespace
from unittest import mock

from literate_ai.application import standard_project_lifecycle as lifecycle
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    activate_native_root_run,
    open_native_root_run,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from tests.support import fixtures_test_standard_project_lifecycle as fixture


class NativeRootSchedulerDeadlineTests(unittest.TestCase):
    def setUp(self):
        model = fixture.StandardProjectLifecycleTests()
        model.setUp()
        self.lock, self.execution = model.lock, model.execution
        self.nodes, self.names = model.nodes, model.names

    def owner(self, seconds=60, **clocks):
        return open_native_root_run(
            NativeRootRunPolicy(seconds, 3),
            project_identity=canonical_identity({"project": "scheduler-fixture"}),
            framework_distribution_identity=canonical_identity({"framework": 1}),
            lifecycle_policy_identity=canonical_identity({"policy": 1}),
            require_current=lambda: None,
            **clocks,
        )

    def execute(self, service):
        return service.execute(
            self.execution,
            component_lock=self.lock,
            invalidation=fixture._decision(
                self.execution, self.names, "money", tuple(self.names.values())
            ),
            prepared_nodes=self.nodes,
            max_parallelism=1,
        )

    def assert_capacity_expires(self, *, link):
        clock = [1_000_000_000]
        retries = []

        def occupied(*_args):
            retries.append(True)
            if len(retries) > 4:
                # Keep the original broken scheduler finite. That path returns
                # a failed modeled node instead of the required owner expiry.
                raise AssertionError("capacity retried beyond original deadline")
            clock[0] += 250_000_000
            return None

        ports = fixture.ContractEvidenceLifecyclePorts(self.execution, self.names)
        service = fixture._service(ports)
        operation = mock.Mock(side_effect=AssertionError("occupied operation ran"))
        if link:
            service.component_linker = SimpleNamespace(
                try_reserve_link=occupied, link=operation
            )
        else:
            ports.try_reserve_build = occupied
            ports.build = operation
        with self.owner(
            1, utc_clock=lambda: clock[0], monotonic_clock=lambda: clock[0]
        ) as owner:
            with activate_native_root_run(owner):
                with self.assertRaisesRegex(NativeRootRunError, "expired"):
                    self.execute(service)
        self.assertEqual(len(retries), 4)
        operation.assert_not_called()
        self.assertFalse(any(stage == "admit" for stage, _name in ports.events))

    def test_occupied_build_slot_expires_without_a_new_action_deadline(self):
        self.assert_capacity_expires(link=False)

    def test_occupied_link_slot_expires_without_a_new_action_deadline(self):
        self.assert_capacity_expires(link=True)

    def test_native_future_waits_are_bounded_and_absent_owner_keeps_old_behavior(self):
        for selected in (False, True):
            with self.subTest(selected=selected):
                ports = fixture.LifecyclePorts(self.execution, self.names)
                service = fixture._service(ports)
                with mock.patch.object(lifecycle, "wait", wraps=lifecycle.wait) as wait:
                    if selected:
                        with self.owner() as owner, activate_native_root_run(owner):
                            result = self.execute(service)
                    else:
                        result = self.execute(service)
                self.assertTrue(result.successful)
                self.assertTrue(wait.call_args_list)
                timeouts = [call.kwargs["timeout"] for call in wait.call_args_list]
                if selected:
                    self.assertTrue(all(0 < limit <= 0.05 for limit in timeouts))
                else:
                    self.assertEqual(set(timeouts), {None})
