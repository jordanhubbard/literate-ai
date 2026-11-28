"""Actual canonical plain-to-root execution and complete terminal teardown."""

import os
import unittest
from dataclasses import replace

import tests.critical.test_retained_layout_source_forest as fixture
from literate_ai.adapters import retained_layout_forest_operation as operation
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget


@unittest.skipUnless(os.name == "posix", "actual canonical root placement")
class CanonicalForestIntoRootTests(unittest.TestCase):
    git = fixture.OriginalMixedDestinationTests.git
    init_git = fixture.OriginalMixedDestinationTests.init_git
    pool = fixture.OriginalMixedDestinationTests.pool
    prepare_to = fixture.OriginalMixedDestinationTests.prepare_to

    @classmethod
    def setUpClass(cls):
        fixture.OriginalMixedDestinationTests.setUpClass.__func__(cls)

    def setUp(self):
        fixture.OriginalMixedDestinationTests.setUp(self)

    def test_actual_plain_to_root_preserves_source_and_repository_native_custody(self):
        self.input_budget = replace(self.input_budget, maximum_entries=262144)
        self.metadata_limit = 8 * 1024**3
        self.init_git(commit=True)
        app = self.source / "app.py"
        before = app.stat().st_ino, app.read_bytes(), app.stat().st_mode
        source_inode = self.source.stat().st_ino
        project_inode = self.project.stat().st_ino
        git_inode = (self.project / ".git").stat().st_ino
        metadata = self.state / "canonical-root-metadata"
        retirement = self.state / "canonical-root-retirement"
        metadata.mkdir(mode=0o700)
        retirement.mkdir(mode=0o700)
        with self.prepare_to(".") as owner:
            with self.pool(
                owner.plan, budget=LayoutJournalBudget(256, 1024**2, 16 * 1024**2, 32)
            ) as (pool, _journal):
                proposal = operation.plan_prepared_forest_operation(
                    owner, pool, metadata, retirement
                )
                result = operation.execute_prepared_forest_operation(
                    owner,
                    pool,
                    proposal,
                    acknowledged_operation_identity=proposal.identity,
                    allow_host_execution=True,
                )
                self.assertTrue(result["internal_transition_complete"])
                self.assertFalse(result["qualified"])
                owner.require_current()
        target = self.project / "app.py"
        self.assertEqual(
            (target.stat().st_ino, target.read_bytes(), target.stat().st_mode), before
        )
        self.assertFalse(self.source.exists())
        self.assertEqual(self.project.stat().st_ino, project_inode)
        self.assertEqual((self.project / ".git").stat().st_ino, git_inode)
        self.assertTrue(
            any(
                path.is_dir() and path.stat().st_ino == source_inode
                for path in proposal.parking.rglob("*")
            )
        )
        self.assertFalse(layout_pending_control_path(self.project).exists())
