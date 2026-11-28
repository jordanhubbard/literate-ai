"""Actual complete current metadata observation under a smaller fresh allowance.

Reuse the existing original native metadata fixture and its complete projection
assertions. This proves resource behavior only, never canonical effect authority.
"""

import os
import unittest

from tests.critical import test_retained_layout_forest_metadata_replay as fixtures


@unittest.skipUnless(os.name == "posix", "actual original metadata/native journal")
class CurrentForestAllowanceTests(unittest.TestCase):
    git = fixtures.ForestMetadataReplayTests.git
    init_git = fixtures.ForestMetadataReplayTests.init_git
    prepare = fixtures.ForestMetadataReplayTests.prepare
    pool = fixtures.ForestMetadataReplayTests.pool
    persist_guarded_root = fixtures.ForestMetadataReplayTests.persist_guarded_root
    reopen = fixtures.ForestMetadataReplayTests.reopen
    retain = fixtures.ForestMetadataReplayTests.retain
    acquired = fixtures.ForestMetadataReplayTests.acquired
    observing = fixtures.ForestMetadataReplayTests.observing
    run_unmanaged = fixtures.ForestMetadataReplayTests.run_unmanaged
    setUp = fixtures.ForestMetadataReplayTests.setUp

    @classmethod
    def setUpClass(cls):
        fixtures.ForestMetadataReplayTests.setUpClass.__func__(cls)

    def test_exact_known_view_fits_original_smaller_fresh_allowance(self):
        self.fresh_metadata_limit = 8 * 1024**3 - 128 * 1024**2
        fixtures.ForestMetadataReplayTests.test_actual_complete_metadata_projects_original_and_prospective_nodes(
            self
        )
