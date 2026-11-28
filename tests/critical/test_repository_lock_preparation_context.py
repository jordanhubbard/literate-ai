"""Portable lock content cannot restore an original native preparation context."""

from __future__ import annotations

import shutil
import unittest

from literate_ai.adapters.repository_lock_planning import prepare_repository_lock
from literate_ai.adapters.repository_locks import RepositoryLockStore
from literate_ai.adapters.repository_orchestration import OrchestrationInventoryError
from tests.critical import test_project_layout_repository_locks as journeys
from tests.support.fixtures_test_repository_orchestration import snapshot


class RepositoryLockPreparationContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        journeys.ContainedRepositoryLockTests.setUpClass()
        cls.addClassCleanup(journeys.ContainedRepositoryLockTests.doClassCleanups)

    def test_equal_byte_framework_replacement_cannot_reuse_prepared_authority(self):
        case = journeys.ContainedRepositoryLockTests("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        prepared = case.prepared
        framework = case.root / "litai"
        retained = case.case.base / "original-framework"
        framework.rename(retained)
        shutil.copytree(retained, framework, symlinks=True)
        current = prepare_repository_lock(case.root)
        self.assertEqual(current.lock, prepared.lock)
        self.assertEqual(current.to_plan(), prepared.to_plan())
        store = RepositoryLockStore(case.root)
        before = snapshot(case.case.base)
        with self.assertRaises(OrchestrationInventoryError) as error:
            store.update(prepared)
        self.assertEqual(error.exception.code, "orchestration.inputs_changed")
        self.assertEqual(snapshot(case.case.base), before)
        self.assertFalse(store.writer_path.exists())
