"""Actual canonical transaction, interrupted retirement, G2 retry and replay."""

import os
from contextlib import ExitStack, contextmanager
from contextvars import copy_context
from functools import wraps
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_forest_operation_committed as fixture
from literate_ai.adapters import retained_layout_disposition_history as history
from literate_ai.adapters import retained_layout_disposition_read as history_read
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_forest_terminal_replay as terminal
from literate_ai.adapters import retained_layout_recovery_controls as controls
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_forest_observation import (
    observed_forest_recovery,
)
from literate_ai.adapters.retained_layout_journal import _LayoutJournalWriter


def _single_decode_per_actual_plan(method):
    @wraps(method)
    def checked(self):
        original_plan = controls.plan_layout_control_recovery
        original_expand = history.expand_history
        original_snapshot = _LayoutJournalWriter._raw_documents_from_snapshot
        active, completed = [], []

        def expand(*args, **kwargs):
            if active and history_read._PLAN.get() is not None:
                active[-1][0] += 1
                active[-1][2] = copy_context()
            return original_expand(*args, **kwargs)

        def snapshot(*args, **kwargs):
            if active and history_read._PLAN.get() is not None:
                active[-1][1] += 1
            return original_snapshot(*args, **kwargs)

        def plan(pool, *args, **kwargs):
            counts = [0, 0, None]
            active.append(counts)
            try:
                result = original_plan(pool, *args, **kwargs)
            finally:
                active.pop()
            if counts[2] is not None:
                self.assertEqual(counts[0], 1)
                self.assertGreaterEqual(counts[1], 3)
                self.assertIsNone(history_read._PLAN.get())
                # A copied execution context cannot retain the ended plan's
                # descriptions or borrow native reads, even while its genuine
                # parent forest observation remains alive.
                with (
                    mock.patch.object(
                        _LayoutJournalWriter,
                        "_raw_documents_from_snapshot",
                        side_effect=AssertionError("ended plan borrowed native IO"),
                    ),
                    mock.patch.object(
                        os,
                        "fstat",
                        side_effect=AssertionError("ended plan borrowed native FD"),
                    ),
                ):
                    with self.assertRaisesRegex(ValueError, "plan lifetime ended"):
                        counts[2].run(history_read.control_history, pool)
                completed.append(tuple(counts[:2]))
            return result

        with (
            mock.patch.object(controls, "plan_layout_control_recovery", plan),
            mock.patch.object(history, "expand_history", expand),
            mock.patch.object(
                _LayoutJournalWriter, "_raw_documents_from_snapshot", snapshot
            ),
        ):
            method(self)
        self.assertGreaterEqual(len(completed), 2)

    return checked


class _Stopped(Exception):
    pass


class CanonicalForestG2RetryTests(fixture.CanonicalCommittedCase):
    @contextmanager
    def terminal_raw(self):
        stages = self.state / "canonical-g2-terminal"
        stages.mkdir(mode=0o700)
        with self.reopen() as journal:
            with staged_layout_controls(stages, journal) as pool:
                with observed_forest_recovery(
                    pool,
                    self.parking.parent,
                    budget=self.fresh_budget,
                    maximum_metadata_bytes=16 * 1024**3,
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
                        for request in observer.discover_supplemental_controls(
                            (original,)
                        ):
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
                        yield observer, tuple(raw)

    @_single_decode_per_actual_plan
    def test_actual_canonical_retirement_retry_preserves_three_generations(self):
        app, index = self.project / "app.py", self.project / ".git/index"
        before = app.stat().st_ino, app.stat().st_mode, app.read_bytes()
        git_before = index.stat().st_ino, index.read_bytes()
        self.recover_committed_data()
        event = disposition.controls._RecoveryDisposition._event
        reached = []

        def stop(effect, kind, data):
            result = event(effect, kind, data)
            if kind == "recovery-control-retirement-observed" and not reached:
                self.assertFalse(Path(data["path"]).exists())
                self.assertEqual(
                    Path(data["destination"]).stat().st_ino,
                    controls._node(data["original_node"]).inode,
                )
                self.assertFalse(effect.decision_attempted)
                self.assertIsNone(effect.decision)
                reached.append(True)
                raise _Stopped("actual predecision native retirement observed")
            return result

        with self.assertRaises(_Stopped):
            with self.committed_disposition() as (observer, roles):
                plan = disposition.plan_forest_control_disposition(
                    observer, roles, self.quarantine, self.disposal
                )
                with mock.patch.object(
                    disposition.controls._RecoveryDisposition, "_event", stop
                ):
                    disposition.apply_forest_control_disposition(
                        observer,
                        roles,
                        plan,
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
        self.assertEqual(reached, [True])
        kept = {
            path: (path.stat().st_ino, path.read_bytes())
            for root in (self.retirement, self.disposal)
            for path in root.iterdir()
        }
        second = self.state / "canonical-g2-disposal"
        second.mkdir(mode=0o700)
        with self.canonical_epoch(
            "canonical-g2-retry", bootstrap=True, missing=True
        ) as (observer, roles, raw):
            self.assertEqual(len(raw), 2)
            self.assertIsNotNone(roles.reservations._incoming)
            plan = disposition.plan_forest_control_disposition(
                observer, roles, self.quarantine, second
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
        with self.terminal_raw() as (observer, raw):
            self.assertEqual(len(raw), 3)
            value = observation._record(observer)
            self.assertEqual(len(value.frontier.recovery.dispositions), 2)
            self.assertFalse(value.frontier.recovery.dispositions[0].complete)
            self.assertTrue(value.frontier.recovery.dispositions[1].complete)
            events, publications = (
                tuple(value.journal._events),
                tuple(value.pool._entries),
            )
            result = terminal.observe_terminal_native_forest(observer, raw)
            self.assertTrue(result.journal_complete)
            self.assertEqual(tuple(value.journal._events), events)
            self.assertEqual(tuple(value.pool._entries), publications)
            for owner in raw:
                for marker in owner._plan.markers:
                    if not marker.target.advisory:
                        self.assertFalse(marker.target.path.exists())
        self.assertEqual(
            {path: (path.stat().st_ino, path.read_bytes()) for path in kept}, kept
        )
        moved = self.destination / "app.py"
        self.assertEqual(
            (moved.stat().st_ino, moved.stat().st_mode, moved.read_bytes()), before
        )
        self.assertEqual((index.stat().st_ino, index.read_bytes()), git_before)
