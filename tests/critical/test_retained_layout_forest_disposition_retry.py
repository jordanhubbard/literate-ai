"""Real interrupted disposition, replacement generation and terminal replay.

Original source execution uses the unmanaged fixture under real normal owners;
this does not claim integrated canonical forest execution or public reentry.
"""

from __future__ import annotations

import json
import os
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_forest_terminal_replay as fixture
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_forest_terminal_replay as terminal
from literate_ai.adapters import retained_layout_recovery_controls as controls
from literate_ai.adapters import retained_layout_recovery_roles as role_owners
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_forest_recovery_transcript import (
    decode_recovery_transcript,
)
from literate_ai.contracts.identity import canonical_json_bytes


class _Stopped(Exception):
    pass


@unittest.skipUnless(os.name == "posix", "actual interrupted native disposition")
class ForestDispositionRetryFixture(unittest.TestCase):
    git = fixture.ForestTerminalReplayTests.git
    init_git = fixture.ForestTerminalReplayTests.init_git
    prepare = fixture.ForestTerminalReplayTests.prepare
    persist_guarded_root = fixture.ForestTerminalReplayTests.persist_guarded_root
    reopen = fixture.ForestTerminalReplayTests.reopen
    acquired = fixture.ForestTerminalReplayTests.acquired
    observing = fixture.ForestTerminalReplayTests.observing
    pool = fixture.ForestTerminalReplayTests.pool
    restore = fixture.ForestTerminalReplayTests.restore
    retain = fixture.ForestTerminalReplayTests.retain
    run_unmanaged = fixture.ForestTerminalReplayTests.run_unmanaged
    fresh_generations = fixture.ForestTerminalReplayTests.fresh_generations
    terminal_raw = fixture.ForestTerminalReplayTests.terminal_raw
    setUp = fixture.ForestTerminalReplayTests.setUp

    @classmethod
    def setUpClass(cls):
        fixture.ForestTerminalReplayTests.setUpClass.__func__(cls)

    @contextmanager
    def active_retry(self, *, expected_missing=True):
        stages = self.state / "attempt-two-stages"
        stages.mkdir(mode=0o700)
        with self.reopen() as journal:
            with staged_layout_controls(stages, journal) as pool:
                with self.observing(pool) as owner:
                    with owner._reads(), ExitStack() as stack:
                        plan = owner.plan_controls(self.targets)
                        original = stack.enter_context(
                            controls.acquire_layout_recovery_controls(
                                pool,
                                plan,
                                acknowledged_recovery_identity=plan.identity,
                                allow_host_execution=True,
                            )
                        )
                        recovered = [original]
                        for request in owner.discover_supplemental_controls(
                            (original,)
                        ):
                            plan = owner.plan_controls(
                                request.targets, reservation_group=request.group
                            )
                            recovered.append(
                                stack.enter_context(
                                    controls.acquire_layout_recovery_controls(
                                        pool,
                                        plan,
                                        acknowledged_recovery_identity=plan.identity,
                                        allow_host_execution=True,
                                    )
                                )
                            )
                        self.assertEqual(len(recovered), 2)
                        plan = owner.plan_roles(tuple(recovered))
                        self.assertEqual(bool(plan.missing), expected_missing)
                        with role_owners.acquire_recovered_layout_roles(
                            pool,
                            tuple(recovered),
                            plan,
                            acknowledged_recovery_identity=plan.identity,
                            allow_host_execution=True,
                        ) as roles:
                            yield owner, roles

    def assert_handoff_mutations_refuse(self, owner):
        value = observation._record(owner)
        records = value.frontier.recovery.records
        rows = [
            (i, json.loads(body))
            for i, (kind, body) in enumerate(records)
            if kind == "control-recovery-public-handoff"
        ]
        left, right = next(
            (a, b)
            for a in rows
            for b in rows
            if a[0] < b[0]
            and a[1]["old_group"] != b[1]["old_group"]
            and a[1]["incoming_nodes"] == b[1]["incoming_nodes"]
        )
        self.assertNotEqual(
            left[1]["old_recovery_identity"], right[1]["old_recovery_identity"]
        )
        variants = (
            ("same-group-repeat", dict(left[1])),
            ("same-identity-new-group", {**left[1], "old_group": "foreign-group"}),
            (
                "same-group-other-identity",
                {
                    **left[1],
                    "old_recovery_identity": right[1]["old_recovery_identity"],
                },
            ),
        )
        for label, body in variants:
            with self.subTest(handoff=label):
                duplicate = (
                    "control-recovery-public-handoff",
                    canonical_json_bytes(body),
                )
                changed = (*records[: left[0] + 1], duplicate, *records[left[0] + 1 :])
                with self.assertRaisesRegex(ValueError, "handoff"):
                    decode_recovery_transcript(
                        value.program,
                        changed,
                        allowance=value.ledger,
                        payloads=frozenset(value.journal._payloads),
                    )

    def run_interruption(self, boundary):
        self.assertIn(boundary, {"pwrite", "normalized", "retired"})
        missing = boundary == "retired"
        self.restore()
        first = self.state / "attempt-one-controls"
        first.mkdir(mode=0o700)
        event = disposition.controls._RecoveryDisposition._event
        pwrite = disposition.controls.os.pwrite
        reached = []
        advisory = []

        def stop_write(descriptor, content, offset):
            before = os.fstat(descriptor)
            original = os.pread(descriptor, before.st_size, 0)
            result = pwrite(descriptor, content, offset)
            if not reached:
                self.assertEqual((content, offset, result), (b"\0", 0, 1))
                self.assertGreater(before.st_size, 1)
                entry = next(
                    e
                    for e in plan.entries
                    if e.node.inode == before.st_ino and e.target.advisory
                )
                self.assertEqual(os.fstat(descriptor).st_size, before.st_size)
                self.assertEqual(
                    os.pread(descriptor, before.st_size, 0), b"\0" + original[1:]
                )
                advisory.append((entry.named, before.st_ino))
                reached.append(True)
                raise _Stopped("actual advisory pwrite before truncate")
            return result

        expected_observation = (
            "recovery-control-retirement-observed"
            if missing
            else "recovery-control-normalization-observed"
        )

        def stop_event(effect, kind, data):
            if kind == expected_observation and not reached:
                path = Path(data["path"])
                if missing:
                    destination = Path(data["destination"])
                    self.assertFalse(path.exists())
                    self.assertEqual(
                        destination.stat().st_ino, data["original_node"]["inode"]
                    )
                else:
                    self.assertEqual(path.read_bytes(), b"\0")
                    self.assertEqual(path.stat().st_size, 1)
                    advisory.append((path, data["original_node"]["inode"]))
                reached.append(True)
                raise _Stopped("actual primitive before durable observation")
            return event(effect, kind, data)

        expected_error = (
            disposition.controls.RecoveryDispositionOutcomeError
            if missing
            else _Stopped
        )
        with self.assertRaises(expected_error) as caught:
            with self.fresh_generations("attempt-one-stages") as (owner, roles, _raw):
                plan = disposition.plan_forest_control_disposition(
                    owner, roles, self.quarantine, first
                )
                patch = (
                    mock.patch.object(disposition.controls.os, "pwrite", stop_write)
                    if boundary == "pwrite"
                    else mock.patch.object(
                        disposition.controls._RecoveryDisposition, "_event", stop_event
                    )
                )
                with patch:
                    disposition.apply_forest_control_disposition(
                        owner,
                        roles,
                        plan,
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
        self.assertEqual(reached, [True])
        if missing:
            self.assertIsInstance(caught.exception.__cause__, _Stopped)
        before = {
            path: (path.stat().st_ino, path.read_bytes())
            for root in (self.retirement, first)
            for path in root.iterdir()
        }
        try:
            second = self.state / "attempt-two-controls"
            second.mkdir(mode=0o700)
            with self.active_retry(expected_missing=missing) as (owner, roles):
                plan = disposition.plan_forest_control_disposition(
                    owner, roles, self.quarantine, second
                )
                result = disposition.apply_forest_control_disposition(
                    owner,
                    roles,
                    plan,
                    acknowledged_recovery_identity=plan.identity,
                    allow_host_execution=True,
                )
                self.assertTrue(result["controls_released"])
                self.assertFalse(result["qualified"])
            with self.terminal_raw("after-retry-stages") as (owner, raw):
                self.assertEqual(len(raw), 3 if missing else 2)
                value = observation._record(owner)
                attempts = value.frontier.recovery.dispositions
                self.assertEqual(len(attempts), 2)
                self.assertFalse(attempts[0].complete)
                self.assertEqual(
                    attempts[0].pending[0],
                    expected_observation.removesuffix("-observed") + "-intent",
                )
                self.assertTrue(attempts[1].complete)
                events, publications = (
                    tuple(value.journal._events),
                    tuple(value.pool._entries),
                )
                result = terminal.observe_terminal_native_forest(owner, raw)
                self.assertTrue(result.journal_complete)
                self.assertEqual(tuple(value.journal._events), events)
                self.assertEqual(tuple(value.pool._entries), publications)
                for recovered in raw:
                    for marker in recovered._plan.markers:
                        if not marker.target.advisory:
                            self.assertFalse(marker.target.path.exists())
        finally:
            self.assertEqual(
                {path: (path.stat().st_ino, path.read_bytes()) for path in before},
                before,
            )
        for path, inode in advisory:
            self.assertEqual((path.stat().st_ino, path.read_bytes()), (inode, b"\0"))


class ForestDispositionRetryTests(ForestDispositionRetryFixture):
    def test_interrupted_retirement_retries_with_real_replacement_generation(self):
        self.restore()
        first = self.state / "attempt-one-controls"
        first.mkdir(mode=0o700)
        event = disposition.controls._RecoveryDisposition._event
        reached = []

        def stop(effect, kind, data):
            result = event(effect, kind, data)
            if kind == "recovery-control-retirement-observed" and not reached:
                reached.append(True)
                raise _Stopped("first actual exclusive native retirement observed")
            return result

        with self.assertRaises(disposition.controls.RecoveryDispositionOutcomeError):
            with self.fresh_generations("attempt-one-stages") as (owner, roles, _raw):
                plan = disposition.plan_forest_control_disposition(
                    owner, roles, self.quarantine, first
                )
                with mock.patch.object(
                    disposition.controls._RecoveryDisposition, "_event", stop
                ):
                    disposition.apply_forest_control_disposition(
                        owner,
                        roles,
                        plan,
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
        self.assertEqual(reached, [True])
        before = {
            path: (path.stat().st_ino, path.read_bytes())
            for root in (self.retirement, first)
            for path in root.iterdir()
        }
        self.assertTrue(tuple(first.iterdir()))
        try:
            second = self.state / "attempt-two-controls"
            second.mkdir(mode=0o700)
            with self.active_retry() as (owner, roles):
                plan = disposition.plan_forest_control_disposition(
                    owner, roles, self.quarantine, second
                )
                result = disposition.apply_forest_control_disposition(
                    owner,
                    roles,
                    plan,
                    acknowledged_recovery_identity=plan.identity,
                    allow_host_execution=True,
                )
                self.assertTrue(result["controls_released"])
                self.assertFalse(result["qualified"])
            with self.terminal_raw("after-retry-stages") as (owner, raw):
                self.assertEqual(len(raw), 3)
                value = observation._record(owner)
                self.assertEqual(len(value.frontier.recovery.dispositions), 2)
                self.assertFalse(value.frontier.recovery.dispositions[0].complete)
                self.assertTrue(value.frontier.recovery.dispositions[1].complete)
                self.assert_handoff_mutations_refuse(owner)
                events = tuple(value.journal._events)
                result = terminal.observe_terminal_native_forest(owner, raw)
                self.assertTrue(result.journal_complete)
                self.assertEqual(tuple(value.journal._events), events)
        finally:
            self.assertEqual(
                {path: (path.stat().st_ino, path.read_bytes()) for path in before},
                before,
            )
