"""A new process renews after the original Component directory is archived.

Normal preparation, native journal custody and rollback are real. Initialization
lineage remains the fixture seam; this is not installed/platform qualification.
"""

from __future__ import annotations

import os
import unittest

from literate_ai.adapters import project_layout_framework_finalization as finalization
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_framework_producer_renewal as initialized
from tests.critical import test_project_layout_fresh_producer as support
from tests.support.fixtures_test_component_lock_planning import _flavor_variant


@unittest.skipUnless(
    os.name == "posix", "POSIX source archive; Windows remains required"
)
class FreshProducerAfterCloseTests(unittest.TestCase):
    def test_new_process_renews_after_source_native_namespace_is_archived(self):
        helper = initialized.FrameworkProducerRenewalTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, public, endpoint, original = helper.fixture(alternate=False)
        source = project.root / endpoint.source_root
        inodes = {
            path: (project.root / path).stat().st_ino
            for path in endpoint.coordination_paths
        }
        with ProjectConfigurationStore.layout_lock(project.root):
            self.assertTrue(
                finalization.finalize_framework_components(
                    project.root, public["plan_identity"]
                )["components_finalized"]
            )
        self.assertFalse(source.exists())
        # This local policy is authored only AFTER original source closure.
        # Its root is outside every directory created by the migration journal.
        alternate = project.root / "local-flavor-fixture/lang-python-alternate"
        _flavor_variant(
            project.root / "flavors/lang-python",
            alternate,
            name="lang-python-alternate",
            value="python",
        )
        authored = {
            path: path.read_bytes() for path in alternate.rglob("*") if path.is_file()
        }
        journey = support.FreshProducerTests("runTest")
        result = journey.child(
            project,
            public,
            endpoint,
            flavors=("+flavor://literate-ai/lang-python-alternate",),
            roots=("flavors", "local-flavor-fixture"),
        )
        self.assertTrue(result["current"])
        self.assertTrue(result["writes"])
        self.assertFalse(source.exists())
        with ProjectConfigurationStore.layout_lock(project.root):
            report = finalization.finalize_framework_components(
                project.root, public["plan_identity"]
            )
        self.assertTrue(report["components_finalized"])
        self.assertTrue(report["normal_producers"][0]["current"])
        journey.recover(project, public, original)
        for path, inode in inodes.items():
            self.assertEqual((project.root / path).stat().st_ino, inode)
        for path, payload in authored.items():
            self.assertEqual(path.read_bytes(), payload)
