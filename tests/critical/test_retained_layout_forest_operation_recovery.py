"""Fresh inverse recovery of actual canonical source effects and partition bytes."""

from __future__ import annotations

import os
import unittest
from contextlib import ExitStack, contextmanager, nullcontext
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_operation as fixture
import tests.critical.test_retained_layout_source_forest as originals
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters import retained_layout_forest_generations as generations
from literate_ai.adapters import retained_layout_forest_native as native
from literate_ai.adapters import retained_layout_forest_recovery as recovery
from literate_ai.adapters import retained_layout_recovery_controls as controls
from literate_ai.adapters import retained_layout_recovery_roles as role_owners
from literate_ai.adapters import retained_layout_source_admission as admission
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_forest_observation import (
    observed_forest_recovery,
)
from literate_ai.contracts.identity import canonical_json_bytes


class _Stopped(Exception):
    pass


@unittest.skipUnless(os.name == "posix", "actual canonical forest recovery")
class CanonicalForestRecoveryCase(unittest.TestCase):
    git = fixture.ForestOperationTests.git
    init_git = fixture.ForestOperationTests.init_git
    prepare = fixture.ForestOperationTests.prepare
    pool = fixture.ForestOperationTests.pool
    propose = fixture.ForestOperationTests.propose
    execute = fixture.ForestOperationTests.execute
    reopen = originals.OriginalSourceForestTests.reopen

    @classmethod
    def setUpClass(cls):
        fixture.ForestOperationTests.setUpClass.__func__(cls)

    def setUp(self):
        fixture.ForestOperationTests.setUp(self)
        self.journal_budget = replace(self.journal_budget, maximum_events=256)
        self.fresh_budget = replace(
            self.input_budget,
            maximum_files=65536,
            maximum_entries=4000000,
            maximum_total_bytes=2 * 1024**3,
        )

    def run_original(self, *, interrupt=False):
        event = native._NativeForest._event
        captured, stopped = [], []

        def observe(effect, kind, data):
            result = event(effect, kind, data)
            if not captured:
                # Read the actual creating canonical lease. These target
                # descriptions cannot reopen its FDs or grant later rights.
                record = admission._JOURNALS[effect.journal]
                self.targets = (
                    record.controls._seed.targets() + record.controls.git.targets()
                )
                captured.append(True)
            if interrupt and kind == "forest-entry-observed" and not stopped:
                stopped.append(True)
                raise _Stopped("actual original canonical source effect observed")
            return result

        expected = self.assertRaises(_Stopped) if interrupt else nullcontext()
        with expected:
            with self.prepare() as owner:
                self.original_reader = preparation._state(owner).reader
                with self.pool(owner.plan, budget=self.journal_budget) as (
                    pool,
                    journal,
                ):
                    self.saved_binding = canonical_json_bytes(owner.plan.binding)
                    self.saved_budget = journal._budget
                    self.saved_phase = owner.plan.identity.uri
                    proposal = self.propose(owner, pool)
                    self.parking = proposal.parking
                    with mock.patch.object(native._NativeForest, "_event", observe):
                        result = self.execute(owner, pool, proposal)
                    self.assertTrue(result["internal_transition_complete"])
                    self.assertFalse(result["qualified"])
        self.assertEqual(captured, [True])
        self.assertEqual(stopped, [True] if interrupt else [])
        self.assertFalse(self.original_reader._active)
        with self.reopen() as journal:
            intent = next(
                e["data"] for e in journal.events if e["kind"] == "forest-source-intent"
            )
            digest = intent["acquired_partition_payload_digest"]
            self.assertIsInstance(digest, str)
            self.assertTrue(journal.read_payload(digest))

    @contextmanager
    def canonical_epoch(
        self, stage, *, bootstrap=False, missing=False, metadata_limit=16 * 1024**3
    ):
        stages = self.state / stage
        stages.mkdir(mode=0o700)
        with self.reopen() as journal:
            with staged_layout_controls(stages, journal) as pool:
                with observed_forest_recovery(
                    pool,
                    self.parking.parent,
                    budget=self.fresh_budget,
                    maximum_metadata_bytes=metadata_limit,
                ) as observer:
                    with observer._reads(), ExitStack() as stack:
                        proposal = observer.plan_controls(self.targets)
                        original = stack.enter_context(
                            controls.acquire_layout_recovery_controls(
                                pool,
                                proposal,
                                acknowledged_recovery_identity=proposal.identity,
                                allow_host_execution=True,
                            )
                        )
                        raw = [original]
                        canary = (
                            mock.patch.object(
                                generations,
                                "observe_layout_git_controls",
                                side_effect=AssertionError(
                                    "Git read before replacement FDs"
                                ),
                            )
                            if bootstrap
                            else nullcontext()
                        )
                        with canary:
                            requests = observer.discover_supplemental_controls(
                                (original,)
                            )
                        if bootstrap:
                            self.assertTrue(requests)
                            self.assertTrue(
                                all(r.current_git_observed is False for r in requests)
                            )
                        for request in requests:
                            proposal = observer.plan_controls(
                                request.targets, reservation_group=request.group
                            )
                            raw.append(
                                stack.enter_context(
                                    controls.acquire_layout_recovery_controls(
                                        pool,
                                        proposal,
                                        acknowledged_recovery_identity=proposal.identity,
                                        allow_host_execution=True,
                                    )
                                )
                            )
                        proposal = observer.plan_roles(tuple(raw))
                        self.assertEqual(bool(proposal.missing), missing)
                        with role_owners.acquire_recovered_layout_roles(
                            pool,
                            tuple(raw),
                            proposal,
                            acknowledged_recovery_identity=proposal.identity,
                            allow_host_execution=True,
                        ) as roles:
                            yield observer, roles, tuple(raw)


class CanonicalForestInverseTests(CanonicalForestRecoveryCase):
    def test_actual_canonical_interruption_restores_original_partition_and_git(self):
        app, index = self.project / "app.py", self.project / ".git/index"
        before = app.stat().st_ino, app.read_bytes()
        git_before = index.stat().st_ino, index.read_bytes()
        self.run_original(interrupt=True)
        quarantine = self.state / "canonical-quarantine"
        quarantine.mkdir(mode=0o700)
        with self.canonical_epoch("inverse-stages") as (observer, roles, _raw):
            plan = recovery.plan_forest_data_recovery(observer, roles, quarantine)
            self.assertFalse(plan.committed)
            self.assertTrue(plan.actions)
            result = recovery.apply_forest_data_recovery(
                observer,
                roles,
                plan,
                acknowledged_recovery_identity=plan.identity,
                allow_host_execution=True,
            )
            self.assertTrue(result["data_verified"])
            self.assertFalse(result["qualified"])
        disposal = self.state / "canonical-disposal"
        disposal.mkdir(mode=0o700)
        with self.canonical_epoch("disposal-stages") as (observer, roles, _raw):
            plan = disposition.plan_forest_control_disposition(
                observer, roles, quarantine, disposal
            )
            result = disposition.apply_forest_control_disposition(
                observer,
                roles,
                plan,
                acknowledged_recovery_identity=plan.identity,
                allow_host_execution=True,
            )
            self.assertTrue(result["controls_released"])
            self.assertFalse(result["qualified"])
        self.assertEqual((app.stat().st_ino, app.read_bytes()), before)
        self.assertEqual((index.stat().st_ino, index.read_bytes()), git_before)
        self.assertFalse(self.destination.exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())
