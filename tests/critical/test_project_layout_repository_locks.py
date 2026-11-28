"""Original contained initialization and repository lock consumers share a context."""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.repository_lock_planning import prepare_repository_lock
from literate_ai.adapters.repository_locks import RepositoryLockStore
from literate_ai.adapters.repository_orchestration import OrchestrationInventoryError
from tests.e2e import test_cli_repository_locks as journeys
from tests.support.fixtures_test_repository_orchestration import snapshot


class ContainedRepositoryLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        journeys.RepositoryLockCliTests.setUpClass()
        cls.addClassCleanup(journeys.RepositoryLockCliTests.doClassCleanups)

    def setUp(self):
        self.case = journeys.RepositoryLockCliTests("runTest")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.root_with_components()
        self.root = self.case.root
        self.prepared = prepare_repository_lock(self.root)

    def refused(self, store, suffix):
        before = snapshot(self.case.base)
        with self.assertRaises(OrchestrationInventoryError) as error:
            store.read()
        self.assertEqual(error.exception.code, "orchestration." + suffix)
        self.assertEqual(snapshot(self.case.base), before)

    def test_original_cli_lock_plan_and_check_preserve_application_metadata(self):
        private = self.root / ".literate"
        private.mkdir()
        for name in ("private.txt", "repository.lock.json", ".repository-lock.write"):
            (private / name).write_bytes(b"unrelated application metadata fixture")
        before = snapshot(private)
        inodes = {p.name: p.stat().st_ino for p in private.iterdir()}
        code, report = self.case.invoke("lock")
        self.assertEqual(code, 0, report)
        check = report["result"]["lock"]
        self.assertEqual(check["schema"], "literate-ai/repository-lock-check@2")
        self.assertEqual(check["path"], "litai/.literate/repository.lock.json")
        self.assertTrue((self.root / check["path"]).is_file())
        self.case.validator.validate(check)
        for changed in (
            dict(check, schema="literate-ai/repository-lock-check@1"),
            dict(check, path=".literate/repository.lock.json"),
        ):
            self.assertTrue(list(self.case.validator.iter_errors(changed)))
        for selected in (self.root, self.root / "litai"):
            code, checked = self.case.invoke("lock", "--check", root=selected)
            self.assertEqual(code, 0, checked)
            self.assertEqual(checked["result"]["lock"], check)
            code, plan = self.case.invoke("plan", root=selected)
            self.assertEqual(code, 0, plan)
        self.assertEqual(snapshot(private), before)
        self.assertEqual({p.name: p.stat().st_ino for p in private.iterdir()}, inodes)
        store = RepositoryLockStore(self.root / "litai")
        self.assertEqual(store.root, self.root)
        self.assertEqual(store.path, self.root / check["path"])
        self.assertFalse(store.writer_path.exists())

    def test_application_metadata_alias_is_not_opened(self):
        target = self.case.base / "private-metadata"
        target.mkdir()
        (target / "private").write_bytes(b"private fixture")
        private = self.root / ".literate"
        private.symlink_to(target, target_is_directory=True)
        original = Path.open

        def guard(path, *args, **kwargs):
            if path == private or path.is_relative_to(private):
                raise AssertionError("application metadata alias was opened")
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", guard):
            code, report = self.case.invoke("lock")
        self.assertEqual(code, 0, report)
        self.assertTrue(private.is_symlink())
        self.assertEqual((target / "private").read_bytes(), b"private fixture")
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["private"])

    def test_layout_switch_refuses_original_store_before_lock_reads(self):
        store = RepositoryLockStore(self.root)
        manifest = self.root / "litai/literate.project.json"
        manifest.rename(manifest.with_suffix(".retained"))
        self.refused(store, "lock_path_changed")

    def test_equal_byte_framework_replacement_refuses_original_store(self):
        store = RepositoryLockStore(self.root)
        original = self.case.base / "original-framework"
        (self.root / "litai").rename(original)
        shutil.copytree(original, self.root / "litai", symlinks=True)
        self.refused(store, "lock_path_changed")

    def test_new_dual_authority_refuses_original_store(self):
        store = RepositoryLockStore(self.root)
        (self.root / "literate.project.json").write_bytes(
            (self.root / "litai/literate.project.json").read_bytes()
        )
        self.refused(store, "lock_path_unsafe")
