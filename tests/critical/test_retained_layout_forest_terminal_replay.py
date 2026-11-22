"""Real terminal journal replay with raw descriptors and no recreated barrier."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_forest_disposition as fixture
from literate_ai.adapters import retained_layout_control_roles as role_inputs
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_forest_recovery as recovery
from literate_ai.adapters import retained_layout_forest_terminal_replay as terminal
from literate_ai.adapters import retained_layout_recovery_controls as controls
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_forest_recovery_transcript import (
    decode_recovery_transcript,
)
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual terminal raw descriptor custody")
class ForestTerminalReplayTests(unittest.TestCase):
    git = fixture.ForestDispositionTests.git
    init_git = fixture.ForestDispositionTests.init_git
    prepare = fixture.ForestDispositionTests.prepare
    persist_guarded_root = fixture.ForestDispositionTests.persist_guarded_root
    reopen = fixture.ForestDispositionTests.reopen
    acquired = fixture.ForestDispositionTests.acquired
    observing = fixture.ForestDispositionTests.observing
    pool = fixture.ForestDispositionTests.pool
    restore = fixture.ForestDispositionTests.restore
    retain = fixture.ForestDispositionTests.retain
    run_unmanaged = fixture.ForestDispositionTests.run_unmanaged
    fresh_generations = fixture.ForestDispositionTests.fresh_generations
    setUp = fixture.ForestDispositionTests.setUp
    complete = fixture.ForestDispositionTests.__dict__[
        "test_actual_verified_data_handoff_retires_pending_and_preserves_forest"
    ]

    @classmethod
    def setUpClass(cls):
        fixture.ForestDispositionTests.setUpClass.__func__(cls)

    @contextmanager
    def terminal_raw(self, stage_name="terminal-stages"):
        stages = self.state / stage_name
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
                        yield owner, tuple(recovered)

    def test_real_terminal_replay_preserves_absence_and_all_private_nodes(self):
        self.complete()
        roots = (self.retirement, self.state / "forest-disposition")
        kept = {
            path: (path.stat().st_ino, path.read_bytes())
            for root in roots
            for path in root.iterdir()
        }
        with self.terminal_raw() as (owner, recovered):
            value = observation._record(owner)
            self.assertEqual(len(recovered), 2)
            self.assertTrue(value.frontier.recovery.dispositions[-1].complete)
            events = tuple(value.journal._events)
            publications = tuple(value.pool._entries)
            saved_records = value.frontier.recovery.records
            baseline = decode_recovery_transcript(
                value.program,
                saved_records,
                allowance=value.ledger,
                payloads=frozenset(value.journal._payloads),
            )
            self.assertTrue(baseline.dispositions[-1].complete)
            mutations = (
                (
                    "recovery-control-disposition-intent",
                    lambda d: d.update(qualified=0),
                ),
                (
                    "recovery-control-normalization-observed",
                    lambda d: d["observed_node"].update(links=True),
                ),
                (
                    "recovery-control-normalization-observed",
                    lambda d: d["observed_node"].update(size=2),
                ),
                (
                    "recovery-control-retirement-intent",
                    lambda d: d.update(destination=d["destination"] + "-foreign"),
                ),
                (
                    "recovery-control-release-decision",
                    lambda d: d.update(
                        pending_control=d["pending_control"] + "-foreign"
                    ),
                ),
                (
                    "recovery-control-disposition-observed",
                    lambda d: d.update(qualified=0),
                ),
            )
            for kind, mutate in mutations:
                with self.subTest(record=kind):
                    changed = list(saved_records)
                    i = next(i for i, (k, _body) in enumerate(changed) if k == kind)
                    body = json.loads(changed[i][1])
                    mutate(body)
                    changed[i] = (kind, canonical_json_bytes(body))
                    with self.assertRaises(ValueError):
                        decode_recovery_transcript(
                            value.program,
                            tuple(changed),
                            allowance=value.ledger,
                            payloads=frozenset(value.journal._payloads),
                        )
            with mock.patch.object(
                os, "fstat", side_effect=AssertionError("copied owner borrowed FD")
            ):
                with self.assertRaisesRegex(ValueError, "creating"):
                    terminal.observe_terminal_native_forest(
                        owner, (copy.copy(recovered[0]), *recovered[1:])
                    )
                with self.assertRaisesRegex(ValueError, "canonical"):
                    recovery.plan_forest_data_recovery(
                        owner, recovered, self.quarantine
                    )
            actual_close = role_inputs._ProjectRoles.close_native_inputs
            capability_checks = []
            for mutation in ("inventory", "recovered", "late-result"):
                reached = []

                def change(seed, mutation=mutation, reached=reached):
                    actual_close(seed)
                    if reached or not terminal._TERMINALS:
                        return
                    state = next(iter(terminal._TERMINALS.values()))
                    if not capability_checks:
                        with mock.patch.object(
                            os,
                            "fstat",
                            side_effect=AssertionError(
                                "terminal token borrowed writer FD"
                            ),
                        ):
                            with self.assertRaisesRegex(ValueError, "canonical"):
                                recovery.plan_forest_data_recovery(
                                    owner, state.facts.issuer, self.quarantine
                                )
                        capability_checks.append(True)
                    if mutation == "late-result":
                        frame = sys._getframe(1)
                        while (
                            frame is not None
                            and frame.f_code
                            is not terminal.observe_terminal_native_forest.__code__
                        ):
                            frame = frame.f_back
                        if frame is None or "sealed" not in frame.f_locals:
                            return
                        span = frame.f_locals["result"].span
                        object.__setattr__(span, "budget", replace(span.budget))
                    else:
                        name = "_" + mutation
                        copied = tuple(list(getattr(state.catalog, name)))
                        setattr(state.catalog, name, copied)
                        object.__setattr__(state.facts, mutation, copied)
                    reached.append(mutation)

                try:
                    with mock.patch.object(
                        role_inputs._ProjectRoles, "close_native_inputs", change
                    ):
                        with self.assertRaisesRegex(ValueError, "changed|successor"):
                            terminal.observe_terminal_native_forest(owner, recovered)
                finally:
                    self.assertEqual(reached, [mutation])
                self.assertFalse(terminal._TERMINALS)
            self.assertEqual(capability_checks, [True])
            result = terminal.observe_terminal_native_forest(owner, recovered)
            self.assertFalse(result.issues)
            self.assertTrue(result.journal_complete)
            self.assertEqual(result.position, "disposition-recorded")
            self.assertEqual(tuple(value.journal._events), events)
            self.assertEqual(tuple(value.pool._entries), publications)
            self.assertFalse(terminal._TERMINALS)
            for target in self.targets:
                if not target.advisory:
                    self.assertFalse(target.path.exists())
            all_nodes = {
                (root.root / name): (node.inode, blob.digest)
                for root in result.span.roots
                for name, node in root.native
                for key, blob, _mode in root.payloads
                if key == name
            }
            for path, (inode, _content) in kept.items():
                self.assertEqual(all_nodes[path][0], inode)
        self.assertEqual(
            {
                path: (path.stat().st_ino, path.read_bytes())
                for root in roots
                for path in root.iterdir()
            },
            kept,
        )
        config = self.state / "terminal-process.json"
        config.write_text(
            json.dumps(
                {
                    "state": str(self.state),
                    "binding": json.loads(self.saved_binding),
                    "journal_budget": self.saved_budget.to_dict(),
                    "parking": str(self.parking),
                    "fresh_budget": self.fresh_budget.to_dict(),
                    "fresh_metadata_limit": self.fresh_metadata_limit,
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
            [sys.executable, "-B", "-m", __name__, str(config)],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        report = json.loads(child.stdout)
        self.assertNotEqual(report["pid"], os.getpid())
        self.assertEqual(report["owners"], 2)
        self.assertEqual(report["position"], "disposition-recorded")
        self.assertTrue(report["complete"])
        self.assertFalse(report["issues"])
        self.assertEqual(
            {
                path: (path.stat().st_ino, path.read_bytes())
                for root in roots
                for path in root.iterdir()
            },
            kept,
        )


def _fresh_process(config):
    from literate_ai.adapters import retained_layout_recovery_roles as role_owners
    from literate_ai.adapters._write_reservations import WriteReservationTarget
    from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
    from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

    assert not observation._OWNERS and not role_owners._CREATED_ROLES
    assert not controls._CREATED_RECOVERIES and not terminal._TERMINALS
    data = json.loads(config.read_text())
    harness = ForestTerminalReplayTests()
    harness.state = Path(data["state"])
    harness.saved_binding = canonical_json_bytes(data["binding"])
    harness.saved_budget = LayoutJournalBudget(**data["journal_budget"])
    harness.parking = Path(data["parking"])
    harness.fresh_budget = RetainedCargoInputBudget.from_dict(data["fresh_budget"])
    harness.fresh_metadata_limit = data["fresh_metadata_limit"]
    harness.targets = tuple(
        WriteReservationTarget(
            Path(t["path"]), Path(t["anchor"]), tuple(t["anchor_node"]), t["advisory"]
        )
        for t in data["targets"]
    )
    with harness.terminal_raw("terminal-process-stages") as (owner, recovered):
        value = observation._record(owner)
        before = tuple(value.journal._events)
        publications = tuple(value.pool._entries)
        result = terminal.observe_terminal_native_forest(owner, recovered)
        assert tuple(value.journal._events) == before
        assert tuple(value.pool._entries) == publications
        assert all(t.advisory or not t.path.exists() for t in harness.targets)
        report = {
            "pid": os.getpid(),
            "owners": len(recovered),
            "position": result.position,
            "complete": result.journal_complete,
            "issues": result.issues,
        }
    print(json.dumps(report))


if __name__ == "__main__":
    _fresh_process(Path(sys.argv[1]))
