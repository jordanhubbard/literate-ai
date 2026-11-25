"""Actual normal producers/source control closure and exact native recovery.

Current distribution lookup/initialization lineage are fixture seams. POSIX
source handle coverage is not installed or Windows release qualification.
"""

from __future__ import annotations

import os
import unittest

from literate_ai.adapters import project_layout_framework_finalization as finalization
from literate_ai.adapters import project_layout_framework_source_closure as closing
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_locks import ComponentLockStoreError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_producer_renewal as support


@unittest.skipUnless(
    os.name == "posix", "POSIX source handle coverage; Windows remains required"
)
class FrameworkSourceFinalizationTests(unittest.TestCase):
    def journey(self, *, renew):
        helper = support.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, endpoint, original = helper.fixture(alternate=renew)
        before = {
            path: (project.root / path).stat().st_ino
            for path in endpoint.coordination_paths
        }
        with ProjectConfigurationStore.layout_lock(project.root):
            prepared = helper.prepare(project, endpoint, alternate=renew)
            if renew:
                self.assertTrue(
                    helper.renew(project, public, endpoint, prepared)["current"]
                )
            result = finalization.finalize_framework_components(
                project.root, public["plan_identity"]
            )
            self.assertTrue(result["components_finalized"])
            self.assertFalse(result["full_containment"])
            self.assertFalse((project.root / endpoint.source_root).exists())
            journal, intent = framework._decode(project.root, public["plan_identity"])
            ((record, archive, archived),) = closing.records(
                project.root, journal, intent
            )
            self.assertTrue(archived)
            for path, inode in before.items():
                self.assertEqual(
                    (archive / path.removeprefix(endpoint.source_root + "/"))
                    .stat()
                    .st_ino,
                    inode,
                )
            self.assertEqual(record["source_root"], endpoint.source_root)
            with self.assertRaises(ComponentLockStoreError):
                endpoint.original_lock_store.update(prepared.result.lock)
            self.assertFalse((project.root / endpoint.source_root).exists())
        # A separate lease and new real preparations establish restart behavior;
        # original source proof/currentness is never restored from stored data.
        with ProjectConfigurationStore.layout_lock(project.root):
            self.assertTrue(
                finalization.finalize_framework_components(
                    project.root, public["plan_identity"]
                )["components_finalized"]
            )
        helper.recover(project, public, original)
        for path, inode in before.items():
            self.assertEqual((project.root / path).stat().st_ino, inode)

    def test_current_original_pair_closes_controls_and_fresh_restart_recovers(self):
        self.journey(renew=False)

    def test_actually_renewed_pair_closes_controls_and_recovers_original_history(self):
        self.journey(renew=True)
