"""Original typed root data survives audit; no native acceptance is asserted."""

import os
import unittest
from types import SimpleNamespace

from literate_ai.application.native_root_continuation import NativeRootController
from tests.critical import test_native_root_binding as fixture
from tests.support import fixtures_test_standard_project_lifecycle as model


class _StopAfterRoot(Exception):
    pass


@unittest.skipUnless(os.name == "posix", "original binding fixture")
class NativeRootRootRetentionTests(unittest.TestCase):
    setUp = fixture.NativeRootBindingTests.setUp
    observe = fixture.NativeRootBindingTests.observe
    metadata = fixture.NativeRootBindingTests.metadata
    library_current = fixture.NativeRootBindingTests.library_current
    native_protocol = fixture.NativeRootBindingTests.native_protocol
    opened = fixture.NativeRootBindingTests.opened

    def test_actual_root_record_precedes_lifecycle_without_reauthoring(self):
        names = {self.lock.root_revision.uri: "qualified-fixture"}
        ports = model.ContractEvidenceLifecyclePorts(
            self.execution, names, library_exports=True
        )
        ports.artifact_target_identity = self.lock.target_profile_identity
        result = model._service(ports).execute(
            self.execution,
            component_lock=self.lock,
            invalidation=model._decision(
                self.execution, names, "qualified-fixture", ("qualified-fixture",)
            ),
            prepared_nodes={self.lock.root_revision.uri: self.node},
            max_parallelism=1,
        )
        root = result.root_integration
        self.assertIsNotNone(root)
        original = root.to_dict()
        with self.opened() as (scope, _owner):
            retained = []

            def remember(record):
                if type(record) is dict and record == result.identity_document():
                    raise _StopAfterRoot
                retained.append(record)
                return scope.retain_record(record)

            # Only the audit data-retention boundary is under test. Stop before
            # audit/ledger validation instead of inventing an accepted native run.
            controller = SimpleNamespace(
                sequence=SimpleNamespace(ledger=lambda: None),
                _retain_node=lambda _node: None,
                scope=SimpleNamespace(retain_record=remember),
            )
            with self.assertRaises(_StopAfterRoot):
                NativeRootController._audit_result(controller, result)
        self.assertEqual(retained, [root])
        self.assertIs(retained[0], root)
        self.assertEqual(root.to_dict(), original)
