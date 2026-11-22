"""Genuine canonical root-out lifecycle, exact admission and pre-effect refusal."""

from __future__ import annotations

import copy
import os
import stat
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_source_forest as fixture
from literate_ai.adapters import retained_layout_forest_operation as operation
from literate_ai.adapters import retained_layout_source_admission as admission
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
)


@unittest.skipUnless(os.name == "posix", "actual canonical forest operation")
class ForestOperationTests(unittest.TestCase):
    git = fixture.OriginalSourceForestTests.git
    init_git = fixture.OriginalSourceForestTests.init_git
    prepare = fixture.OriginalSourceForestTests.prepare
    pool = fixture.OriginalSourceForestTests.pool

    @classmethod
    def setUpClass(cls):
        fixture.OriginalSourceForestTests.setUpClass.__func__(cls)

    def setUp(self):
        fixture.OriginalSourceForestTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=262144)
        self.metadata_limit = 8 * 1024**3
        self.metadata = self.state / "canonical-metadata"
        self.retirement = self.state / "canonical-retirement"
        self.metadata.mkdir(mode=0o700)
        self.retirement.mkdir(mode=0o700)
        self.journal_budget = LayoutJournalBudget(192, 1024**2, 16 * 1024**2, 32)
        self.init_git(commit=True)

    def propose(self, owner, pool):
        return operation.plan_prepared_forest_operation(
            owner, pool, self.metadata, self.retirement
        )

    def execute(self, owner, pool, proposal):
        return operation.execute_prepared_forest_operation(
            owner,
            pool,
            proposal,
            acknowledged_operation_identity=proposal.identity,
            allow_host_execution=True,
        )

    def test_actual_canonical_root_out_operation_closes_all_original_owners(self):
        path = self.project / "app.py"
        before = (
            path.stat().st_ino,
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
        )
        project_inode, git_inode = (
            self.project.stat().st_ino,
            (self.project / ".git").stat().st_ino,
        )
        with self.prepare() as owner:
            original = preparation._state(owner)
            with self.pool(owner.plan, budget=self.journal_budget) as (pool, journal):
                proposal = self.propose(owner, pool)
                result = self.execute(owner, pool, proposal)
                self.assertEqual(result["state"], "committed-unqualified")
                self.assertTrue(result["internal_transition_complete"])
                self.assertFalse(result["qualified"])
                self.assertFalse(result["feature_complete"])
                self.assertIs(preparation._state(owner).reader, original.reader)
                intent = next(
                    e["data"]
                    for e in journal.events
                    if e["kind"] == "forest-source-intent"
                )
                digest = intent["acquired_partition_payload_digest"]
                self.assertIsInstance(digest, str)
                self.assertTrue(journal.read_payload(digest))
                owner.require_current()
                self.assertNotIn(owner, operation._ADMITTED)
                with self.assertRaisesRegex(ValueError, "creating"):
                    self.execute(owner, pool, proposal)
            owner.require_current()
        self.assertFalse(original.reader._active)
        moved = self.destination / "app.py"
        self.assertEqual(
            (
                moved.stat().st_ino,
                moved.read_bytes(),
                stat.S_IMODE(moved.stat().st_mode),
            ),
            before,
        )
        self.assertFalse(path.exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())
        self.assertEqual(self.project.stat().st_ino, project_inode)
        self.assertEqual((self.project / ".git").stat().st_ino, git_inode)

    def test_copied_or_unacknowledged_operation_refuses_before_borrowed_fds(self):
        class Impostor:
            def __eq__(self, _other):
                raise AssertionError("caller identity equality callback")

            def __str__(self):
                raise AssertionError("caller path conversion callback")

            def require_current(self):
                raise AssertionError("caller pool method callback")

        with self.prepare() as owner:
            with self.pool(owner.plan, budget=self.journal_budget) as (pool, journal):
                proposal = self.propose(owner, pool)
                events = tuple(journal._events)
                with mock.patch.object(
                    os, "fstat", side_effect=AssertionError("borrowed native FD")
                ):
                    for ack, allow in (
                        (None, True),
                        (Impostor(), True),
                        (proposal.identity, False),
                    ):
                        with self.subTest(ack=type(ack).__name__, allow=allow):
                            with self.assertRaisesRegex(ValueError, "acknowledgement"):
                                operation.execute_prepared_forest_operation(
                                    owner,
                                    pool,
                                    proposal,
                                    acknowledged_operation_identity=ack,
                                    allow_host_execution=allow,
                                )
                    with self.assertRaisesRegex(ValueError, "creating"):
                        self.execute(owner, pool, copy.copy(proposal))
                    for foreign in (Impostor(), copy.copy(pool)):
                        with self.assertRaises(TypeError):
                            operation.plan_prepared_forest_operation(
                                owner, foreign, self.metadata, self.retirement
                            )
                    with self.assertRaisesRegex(ValueError, "plain absolute"):
                        operation.plan_prepared_forest_operation(
                            owner, pool, Impostor(), self.retirement
                        )
                self.assertEqual(tuple(journal._events), events)
        self.assertTrue((self.project / "app.py").exists())
        self.assertFalse(self.destination.exists())

    def test_small_original_journal_refuses_before_native_source_effects(self):
        path = self.project / "app.py"
        before = path.stat().st_ino, path.read_bytes()
        with self.assertRaisesRegex(ValueError, "immutable journal policy"):
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    proposal = self.propose(owner, pool)
                    try:
                        self.execute(owner, pool, proposal)
                    finally:
                        self.assertFalse(proposal.parking.exists())
        self.assertEqual((path.stat().st_ino, path.read_bytes()), before)
        self.assertFalse(self.destination.exists())
        self.assertFalse(tuple(self.metadata.iterdir()))
        self.assertFalse(tuple(self.retirement.iterdir()))

    def test_effect_root_replaced_after_actual_acquisition_cannot_rebaseline(self):
        original_bind = admission._bind_phase
        reached = []
        kept = self.state / "retained-original-metadata"
        original_inode = self.metadata.stat().st_ino
        path = self.project / "app.py"
        before = path.stat().st_ino, path.read_bytes()

        def bind(owner, phase):
            original_bind(owner, phase)
            self.metadata.rename(kept)
            self.metadata.mkdir(mode=0o700)
            reached.append(True)

        with self.assertRaises(ValueError) as caught:
            with self.prepare() as owner:
                with self.pool(owner.plan, budget=self.journal_budget) as (
                    pool,
                    _journal,
                ):
                    proposal = self.propose(owner, pool)
                    with mock.patch.object(admission, "_bind_phase", bind):
                        self.execute(owner, pool, proposal)
        errors, pending, seen = [], [caught.exception], set()
        while pending:
            error = pending.pop()
            if error is None or id(error) in seen:
                continue
            seen.add(id(error))
            errors.append(str(error))
            pending.extend((error.__cause__, error.__context__))
        self.assertTrue(
            any(
                "original role ancestry changed" in message
                or "original acknowledged snapshot" in message
                for message in errors
            ),
            errors,
        )
        self.assertEqual(reached, [True])
        self.assertEqual(kept.stat().st_ino, original_inode)
        self.assertNotEqual(self.metadata.stat().st_ino, original_inode)
        self.assertFalse(tuple(kept.iterdir()))
        self.assertFalse(tuple(self.metadata.iterdir()))
        self.assertEqual((path.stat().st_ino, path.read_bytes()), before)
        self.assertFalse(self.destination.exists())
