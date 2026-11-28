"""Closing callbacks cannot grant a successful original-run lifecycle result.

The lifecycle ports are modeled. These controls do not establish filesystem
cache commit atomicity, persisted receipt rollback or native acceptance.
"""

import unittest
from unittest import mock

from literate_ai.application.native_root_run import (
    NativeRootRunError,
    activate_native_root_run,
)
from tests.critical import test_native_root_scheduler_deadline as scheduling
from tests.support import fixtures_test_standard_project_lifecycle as fixture


class NativeRootCompletionDeadlineTests(unittest.TestCase):
    setUp = scheduling.NativeRootSchedulerDeadlineTests.setUp
    owner = scheduling.NativeRootSchedulerDeadlineTests.owner
    execute = scheduling.NativeRootSchedulerDeadlineTests.execute

    def test_admission_closing_original_owner_prevents_receipt_issuance(self):
        ports = fixture.LifecyclePorts(self.execution, self.names)
        service = fixture._service(ports)
        admit = ports.admit
        with self.owner() as owner, activate_native_root_run(owner):

            def close_after_admission(*args):
                result = admit(*args)
                owner.close()
                return result

            with (
                mock.patch.object(ports, "admit", side_effect=close_after_admission),
                self.assertRaisesRegex(NativeRootRunError, "closed"),
            ):
                self.execute(service)
        self.assertIn(("admit", "project"), ports.events)
        self.assertEqual(ports.issued_receipts, [])

    def test_issuer_closing_original_owner_prevents_successful_return(self):
        ports = fixture.LifecyclePorts(self.execution, self.names)
        service = fixture._service(ports)
        issue = ports.issue
        with self.owner() as owner, activate_native_root_run(owner):

            def close_after_issue(*args):
                result = issue(*args)
                owner.close()
                return result

            with (
                mock.patch.object(ports, "issue", side_effect=close_after_issue),
                self.assertRaisesRegex(NativeRootRunError, "closed"),
            ):
                self.execute(service)
        # This models an issuer that returned a record before closing the owner;
        # the service must refuse success, not pretend that callback never ran.
        self.assertEqual(len(ports.issued_receipts), 1)

    def test_cache_callback_closing_owner_prevents_admission(self):
        ports = fixture.LifecyclePorts(self.execution, self.names)
        service = fixture._service(ports)
        publish = ports.publish
        with self.owner() as owner, activate_native_root_run(owner):

            def close_after_publish(*args):
                result = publish(*args)
                owner.close()
                return result

            with mock.patch.object(ports, "publish", side_effect=close_after_publish):
                result = self.execute(service)
        self.assertFalse(result.successful)
        self.assertTrue(
            any(
                node.failure_evidence is not None
                and node.failure_evidence.code == "native_root_run.closed"
                for node in result.node_results
            )
        )
        self.assertFalse(any(stage == "admit" for stage, _name in ports.events))
        self.assertEqual(ports.issued_receipts, [])
