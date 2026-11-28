"""Fresh journal/role factories observe actual original and recovery effects.

Original forest execution remains an explicitly unmanaged dependency under real
normal canonical roles. These tests manufacture no SourcePhase or partition.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_forest_bound_prefix as fixture
from literate_ai.adapters import retained_layout_forest_current as current_native
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_forest_recovery as recovery
from literate_ai.adapters import (
    retained_layout_forest_recovery_current as recovered_current,
)
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes


class _Stopped(Exception):
    pass


@unittest.skipUnless(os.name == "posix", "actual fresh native recovery replay")
class ForestRecoveryRetryTests(unittest.TestCase):
    git = fixture.ForestBoundPrefixTests.git
    init_git = fixture.ForestBoundPrefixTests.init_git
    prepare = fixture.ForestBoundPrefixTests.prepare
    persist_guarded_root = fixture.ForestBoundPrefixTests.persist_guarded_root
    reopen = fixture.ForestBoundPrefixTests.reopen
    acquired = fixture.ForestBoundPrefixTests.acquired
    observing = fixture.ForestBoundPrefixTests.observing
    pool = fixture.ForestBoundPrefixTests.pool
    run_unmanaged = fixture.ForestBoundPrefixTests.run_unmanaged
    retain = fixture.ForestBoundPrefixTests.retain
    setUp = fixture.ForestBoundPrefixTests.setUp

    @classmethod
    def setUpClass(cls):
        fixture.ForestBoundPrefixTests.setUpClass.__func__(cls)

    def restore(self, boundary=None):
        self.retain()
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            self.original = value.program.span.roots[0]
            plan = recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            actual_append = value.journal.append
            actual_emit = recovery._Effect._emit
            reached = []

            def append(kind, raw):
                result = actual_append(kind, raw)
                if kind == boundary:
                    reached.append(kind)
                    raise _Stopped("actual durable recovery record")
                return result

            def emit(effect, kind):
                if boundary == "native-before-observed" and kind == "observed":
                    reached.append(boundary)
                    raise _Stopped("actual native inverse before observation")
                return actual_emit(effect, kind)

            with (
                mock.patch.object(value.journal, "append", append),
                mock.patch.object(recovery._Effect, "_emit", emit),
            ):
                if boundary is None:
                    result = recovery.apply_forest_data_recovery(
                        owner,
                        current,
                        plan,
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
                    self.assertTrue(result["data_verified"])
                else:
                    with self.assertRaises(_Stopped):
                        recovery.apply_forest_data_recovery(
                            owner,
                            current,
                            plan,
                            acknowledged_recovery_identity=plan.identity,
                            allow_host_execution=True,
                        )
                    self.assertEqual(reached, [boundary])
        self.assertFalse(recovery._LIVE)

    def check_fresh(self, position, complete):
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            self.assertIsNotNone(value.frontier.recovery)
            result = current_native.observe_current_native_forest(owner, current)
            self.assertFalse(result.issues)
            self.assertEqual(result.position, position)
            self.assertEqual(result.journal_complete, complete)
            self.assertIn(self.quarantine, {r.root for r in result.span.roots})
            # The new plan uses this actual fresh observer and existing complete
            # quarantine; observation alone still grants no acknowledged effect.
            events = tuple(value.journal._events)
            proposal = recovery.plan_forest_data_recovery(
                owner, current, self.quarantine
            )
            self.assertIsNotNone(proposal.resume)
            self.assertEqual(proposal.private_root, self.quarantine)
            with self.assertRaisesRegex(ValueError, "acknowledgement"):
                recovery.apply_forest_data_recovery(
                    owner,
                    current,
                    proposal,
                    acknowledged_recovery_identity=canonical_identity({"wrong": True}),
                    allow_host_execution=True,
                )
            self.assertEqual(tuple(value.journal._events), events)

    def test_actual_completed_inverse_reopens_under_new_real_roles(self):
        self.restore()
        self.check_fresh("recovery-recorded", True)

    def test_original_pending_after_witness_survives_inverse_and_fresh_reopen(self):
        self.cut = "forest-entry-observed", False
        self.restore()
        self.check_fresh("recovery-recorded", True)

    def test_actual_recovery_intent_before_native_effect_reopens(self):
        self.restore("forest-data-recovery-entry-intent")
        self.check_fresh("recovery-pending-before", False)

    def test_actual_recovery_effect_before_observation_reopens(self):
        self.restore("native-before-observed")
        self.check_fresh("recovery-pending-after", False)

    def test_actual_observed_recovery_prefix_before_completion_reopens(self):
        self.restore("forest-data-recovery-entry-observed")
        self.check_fresh("recovery-recorded", False)

    def test_original_native_continuation_after_recovery_refuses(self):
        self.restore()
        with self.reopen() as journal:
            prior = next(
                e for e in journal.events if e["kind"] == "forest-entry-observed"
            )
            journal.append(prior["kind"], canonical_json_bytes(prior["data"]))
        stages = self.state / "continuation-stages"
        stages.mkdir(mode=0o700)
        with self.reopen() as journal:
            with staged_layout_controls(stages, journal) as pool:
                with self.assertRaisesRegex(ValueError, "recovery suffix"):
                    with self.observing(pool):
                        self.fail("original continuation admitted")

    def test_access_teardown_cannot_change_derived_recovery_view_unchecked(self):
        self.restore()
        captured, hit = [], []
        actual_check = recovered_current._require_current
        actual_access = current_native._directory_access

        def check(span, **kwargs):
            result = actual_check(span, **kwargs)
            captured.append(span)
            return result

        @contextmanager
        def access(root):
            with actual_access(root) as value:
                yield value
            if root == self.project and captured:
                self.assertFalse(hit)
                object.__setattr__(captured[0].roots[0], "payloads", ())
                hit.append(True)

        with self.acquired() as (owner, current):
            with (
                mock.patch.object(recovered_current, "_require_current", check),
                mock.patch.object(current_native, "_directory_access", access),
            ):
                try:
                    with self.assertRaisesRegex(
                        ValueError, "derived recovery view changed"
                    ):
                        current_native.observe_current_native_forest(owner, current)
                finally:
                    self.assertEqual(
                        hit, [True], "actual source access teardown was not reached"
                    )

    def test_original_pending_witness_cannot_change_consumed_prefix(self):
        actual = recovery._intent_document

        def corrupt(plan):
            document = actual(plan)
            document["original_frontier"] = {
                **document["original_frontier"],
                "native_consumed": plan.original_frontier["native_consumed"] - 1,
            }
            return document

        with mock.patch.object(recovery, "_intent_document", corrupt):
            self.restore()
        with self.acquired() as (owner, current):
            with mock.patch.object(
                current_native,
                "_EndpointReads",
                side_effect=AssertionError("source access before witness validation"),
            ):
                with self.assertRaisesRegex(ValueError, "exact original interrupted"):
                    current_native.observe_current_native_forest(owner, current)

    def test_recovery_header_cannot_add_an_unexecuted_inverse_action(self):
        actual = recovery._intent_document

        def corrupt(plan):
            document = actual(plan)
            document["actions"] = [*document["actions"], document["actions"][0]]
            return document

        with mock.patch.object(recovery, "_intent_document", corrupt):
            self.restore()
        with self.assertRaisesRegex(ValueError, "exact complete data observation"):
            with self.acquired():
                self.fail("unexecuted inverse action admitted")

    def test_foreign_source_payload_after_recovery_is_preserved_and_refused(self):
        self.restore()
        payload = self.project / "app.py"
        payload.write_bytes(b"foreign source after recovery\n")
        before = payload.read_bytes()
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "runtime native|runtime root"):
                current_native.observe_current_native_forest(owner, current)
        self.assertEqual(payload.read_bytes(), before)

    def test_unknown_quarantine_entry_after_recovery_is_preserved_and_refused(self):
        self.restore()
        foreign = self.quarantine / "unknown"
        foreign.write_bytes(b"never a recovery baseline\n")
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "runtime native|runtime root"):
                current_native.observe_current_native_forest(owner, current)
        self.assertEqual(foreign.read_bytes(), b"never a recovery baseline\n")

    def test_fresh_replay_funds_view_before_current_source_access(self):
        self.restore()
        entered = []
        with self.assertRaisesRegex(ValueError, "allowance"):
            with self.acquired() as (owner, current):
                ledger = observation._record(owner).ledger
                headroom = min(
                    ledger.budget.maximum_entries - ledger.records,
                    (ledger.metadata - ledger.charged) // 4096,
                )
                ledger.charge_records(headroom)
                ledger.require_capacity()
                with mock.patch.object(
                    current_native,
                    "_EndpointReads",
                    side_effect=AssertionError("unfunded current source access"),
                ):
                    entered.append(True)
                    current_native.observe_current_native_forest(owner, current)
        self.assertEqual(entered, [True], "fresh observer was not reached")

    def test_completed_recovery_replays_in_an_independent_os_process(self):
        self.restore()
        config = self.state / "fresh-process.json"
        config.write_text(
            json.dumps(
                {
                    "binding": json.loads(self.saved_binding),
                    "journal": str(self.state / "journal"),
                    "journal_budget": self.saved_budget.to_dict(),
                    "stages": str(self.state / "process-stages"),
                    "parking_parent": str(self.parking.parent),
                    "fresh_budget": self.fresh_budget.to_dict(),
                    "metadata_limit": self.fresh_metadata_limit,
                    "targets": [
                        {
                            "path": str(t.path),
                            "anchor": str(t.anchor),
                            "anchor_node": t.anchor_node,
                            "advisory": t.advisory,
                        }
                        for t in self.targets
                    ],
                }
            )
        )
        child = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "tests.critical.test_retained_layout_forest_recovery_retry",
                str(config),
            ],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        report = json.loads(child.stdout)
        self.assertNotEqual(report["pid"], os.getpid())
        self.assertEqual(report["position"], "recovery-recorded")
        self.assertTrue(report["complete"])
        self.assertFalse(report["issues"])


def _fresh_process(config):
    """Only descriptive arguments cross processes; real factories reacquire rights."""
    from literate_ai.adapters import retained_layout_recovery_controls as raw_controls
    from literate_ai.adapters import retained_layout_recovery_roles as role_owners
    from literate_ai.adapters._write_reservations import WriteReservationTarget
    from literate_ai.adapters.retained_layout_journal import (
        LayoutJournalBudget,
        retained_layout_journal,
    )
    from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

    assert not observation._OWNERS and not role_owners._CREATED_ROLES
    data = json.loads(config.read_text())
    stages = Path(data["stages"])
    stages.mkdir(mode=0o700)
    targets = tuple(
        WriteReservationTarget(
            Path(t["path"]),
            Path(t["anchor"]),
            tuple(t["anchor_node"]),
            t["advisory"],
        )
        for t in data["targets"]
    )
    with retained_layout_journal(
        Path(data["journal"]),
        canonical_binding=canonical_json_bytes(data["binding"]),
        budget=LayoutJournalBudget(**data["journal_budget"]),
        recover=True,
    ) as journal:
        with staged_layout_controls(stages, journal) as pool:
            with observation.observed_forest_recovery(
                pool,
                Path(data["parking_parent"]),
                budget=RetainedCargoInputBudget.from_dict(data["fresh_budget"]),
                maximum_metadata_bytes=data["metadata_limit"],
            ) as owner:
                raw_plan = owner.plan_controls(targets)
                with owner._reads():
                    with raw_controls.acquire_layout_recovery_controls(
                        pool,
                        raw_plan,
                        acknowledged_recovery_identity=raw_plan.identity,
                        allow_host_execution=True,
                    ) as raw:
                        role_plan = owner.plan_roles((raw,))
                        with role_owners.acquire_recovered_layout_roles(
                            pool,
                            (raw,),
                            role_plan,
                            acknowledged_recovery_identity=role_plan.identity,
                            allow_host_execution=True,
                        ) as current:
                            if data.get("resume") is True:
                                proposal = recovery.plan_forest_data_recovery(
                                    owner, current, Path(data["private_root"])
                                )
                                actual_emit = recovery._Effect._emit

                                def emit(effect, kind):
                                    if (
                                        data.get("crash_after_effect") is True
                                        and kind == "observed"
                                    ):
                                        # This child exits only after the real
                                        # exclusive inverse and fsync, before its
                                        # durable observation. The OS closes FDs.
                                        os._exit(73)
                                    return actual_emit(effect, kind)

                                with mock.patch.object(recovery._Effect, "_emit", emit):
                                    result = recovery.apply_forest_data_recovery(
                                        owner,
                                        current,
                                        proposal,
                                        acknowledged_recovery_identity=proposal.identity,
                                        allow_host_execution=True,
                                    )
                                report = {
                                    "pid": os.getpid(),
                                    "position": "recovery-applied",
                                    "complete": result["data_verified"],
                                    "issues": [],
                                    "controls_released": result["controls_released"],
                                    "actions": len(proposal.actions),
                                }
                            else:
                                result = current_native.observe_current_native_forest(
                                    owner, current
                                )
                                report = {
                                    "pid": os.getpid(),
                                    "position": result.position,
                                    "complete": result.journal_complete,
                                    "issues": result.issues,
                                }
                            print(json.dumps(report))


if __name__ == "__main__":
    _fresh_process(Path(sys.argv[1]))
