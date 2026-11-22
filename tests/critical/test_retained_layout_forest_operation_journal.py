"""Genuine foreign journal admission cannot persist original source state."""

from __future__ import annotations

import os
import unittest

import tests.critical.test_retained_layout_forest_operation as fixture
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_journal import retained_layout_journal
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual canonical forest journal admission")
class ForestOperationJournalTests(unittest.TestCase):
    git = fixture.ForestOperationTests.git
    init_git = fixture.ForestOperationTests.init_git
    prepare = fixture.ForestOperationTests.prepare
    pool = fixture.ForestOperationTests.pool
    setUp = fixture.ForestOperationTests.setUp
    propose = fixture.ForestOperationTests.propose
    execute = fixture.ForestOperationTests.execute

    @classmethod
    def setUpClass(cls):
        fixture.ForestOperationTests.setUpClass.__func__(cls)

    def test_actual_wrong_journal_refuses_before_original_state_persistence(self):
        wrong_root, wrong_stages = (
            self.state / "wrong-journal",
            self.state / "wrong-stages",
        )
        wrong_stages.mkdir(mode=0o700)
        # A failed creating read scope revokes its preparation. Let that failure
        # leave the real owner scopes; never try to reuse the revoked preparation.
        with self.assertRaisesRegex(ValueError, "journal is not bound"):
            with self.prepare() as owner:
                with self.pool(owner.plan, budget=self.journal_budget) as (
                    pool,
                    journal,
                ):
                    proposal = self.propose(owner, pool)
                    original_events = tuple(journal._events)
                    original_names = set(journal._known)
                    wrong_binding = {
                        **owner.plan.binding,
                        "source_phase_identity": canonical_identity(
                            {"foreign": True}
                        ).uri,
                    }
                    with retained_layout_journal(
                        wrong_root,
                        canonical_binding=canonical_json_bytes(wrong_binding),
                        budget=self.journal_budget,
                    ) as foreign_journal:
                        with staged_layout_controls(
                            wrong_stages, foreign_journal
                        ) as foreign:
                            events = tuple(foreign_journal._events)
                            names = set(foreign_journal._known)
                            payloads = set(foreign_journal._payloads)
                            try:
                                with self.assertRaisesRegex(
                                    ValueError, "acknowledgement"
                                ):
                                    self.execute(owner, foreign, proposal)
                                self.propose(owner, foreign)
                            finally:
                                self.assertEqual(tuple(foreign_journal._events), events)
                                self.assertEqual(set(foreign_journal._known), names)
                                self.assertEqual(
                                    set(foreign_journal._payloads), payloads
                                )
                                self.assertEqual(
                                    tuple(journal._events), original_events
                                )
                                self.assertEqual(set(journal._known), original_names)
        self.assertTrue((self.project / "app.py").exists())
        self.assertFalse(self.destination.exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())
