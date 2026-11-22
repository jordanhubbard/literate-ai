"""Real descriptor discovery/reentry after old private and new public ownership.

Original effects remain explicitly unmanaged dependencies under actual normal
roles; fresh observation and descriptor factories are independently real.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import tests.critical.test_retained_layout_forest_recovery as original_fixture
import tests.critical.test_retained_layout_forest_recovery_retry as fixture
from literate_ai.adapters import retained_layout_control_roles as normal_roles
from literate_ai.adapters import retained_layout_forest_current as current_native
from literate_ai.adapters import retained_layout_forest_generations as generations
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_recovery_controls as controls
from literate_ai.adapters import retained_layout_recovery_roles as roles
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)


@unittest.skipUnless(os.name == "posix", "actual supplemental native descriptors")
class ForestGenerationTests(unittest.TestCase):
    git = fixture.ForestRecoveryRetryTests.git
    init_git = fixture.ForestRecoveryRetryTests.init_git
    prepare = fixture.ForestRecoveryRetryTests.prepare
    persist_guarded_root = fixture.ForestRecoveryRetryTests.persist_guarded_root
    reopen = fixture.ForestRecoveryRetryTests.reopen
    acquired = fixture.ForestRecoveryRetryTests.acquired
    observing = fixture.ForestRecoveryRetryTests.observing
    pool = fixture.ForestRecoveryRetryTests.pool
    restore = fixture.ForestRecoveryRetryTests.restore
    retain = original_fixture.ForestRecoveryTests.retain
    run_unmanaged = original_fixture.ForestRecoveryTests.run_unmanaged
    setUp = fixture.ForestRecoveryRetryTests.setUp

    @classmethod
    def setUpClass(cls):
        fixture.ForestRecoveryRetryTests.setUpClass.__func__(cls)

    @contextmanager
    def fresh_generations(self, stage_name="generation-stages"):
        stages = self.state / stage_name
        stages.mkdir(mode=0o700)
        with self.reopen() as journal:
            with staged_layout_controls(stages, journal) as pool:
                with self.observing(pool) as owner:
                    proposal = owner.plan_controls(self.targets)
                    with owner._reads():
                        with controls.acquire_layout_recovery_controls(
                            pool,
                            proposal,
                            acknowledged_recovery_identity=proposal.identity,
                            allow_host_execution=True,
                        ) as original:
                            requests = owner.discover_supplemental_controls((original,))
                            self.assertEqual(len(requests), 1)
                            with ExitStack() as stack:
                                recovered = [original]
                                for request in requests:
                                    fresh = owner.plan_controls(
                                        request.targets, reservation_group=request.group
                                    )
                                    recovered.append(
                                        stack.enter_context(
                                            controls.acquire_layout_recovery_controls(
                                                pool,
                                                fresh,
                                                acknowledged_recovery_identity=fresh.identity,
                                                allow_host_execution=True,
                                            )
                                        )
                                    )
                                recovered = tuple(recovered)
                                plan = owner.plan_roles(recovered)
                                self.assertFalse(plan.missing)
                                with roles.acquire_recovered_layout_roles(
                                    pool,
                                    recovered,
                                    plan,
                                    acknowledged_recovery_identity=plan.identity,
                                    allow_host_execution=True,
                                ) as current:
                                    yield owner, current, recovered

    def test_actual_existing_public_generation_reenters_without_recreating_controls(
        self,
    ):
        self.restore()
        kept = self.retired.stat().st_ino, self.retired.read_bytes()
        public = self.retired_source.stat().st_ino, self.retired_source.read_bytes()
        with self.fresh_generations() as (owner, current, recovered):
            self.assertEqual(len(recovered), 2)
            value = observation._record(owner)
            before = tuple(value.journal._events)
            result = current_native.observe_current_native_forest(owner, current)
            self.assertFalse(result.issues)
            self.assertTrue(result.journal_complete)
            roots = {root.root: root for root in result.span.roots}
            self.assertEqual(
                dict(roots[self.retirement].native)[self.retired.name].inode, kept[0]
            )
            name = self.retired_source.relative_to(self.project).as_posix()
            self.assertEqual(dict(roots[self.project].native)[name].inode, public[0])
            self.assertNotEqual(kept[0], public[0])
            self.assertEqual(tuple(value.journal._events), before)
        self.assertEqual((self.retired.stat().st_ino, self.retired.read_bytes()), kept)
        self.assertEqual(
            (self.retired_source.stat().st_ino, self.retired_source.read_bytes()),
            public,
        )
        config = self.state / "generation-process.json"
        config.write_text(
            json.dumps(
                {
                    "state": str(self.state),
                    "binding": json.loads(self.saved_binding),
                    "journal_budget": self.saved_budget.to_dict(),
                    "parking": str(self.parking),
                    "budget": self.fresh_budget.to_dict(),
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
        self.assertTrue(report["complete"])
        self.assertFalse(report["issues"])
        self.assertEqual((self.retired.stat().st_ino, self.retired.read_bytes()), kept)
        self.assertEqual(
            (self.retired_source.stat().st_ino, self.retired_source.read_bytes()),
            public,
        )

    def test_late_callbacks_cannot_change_requests_or_catalog(self):
        self.restore()
        reached = []
        native_close = normal_roles._ProjectRoles.close_native_inputs
        native_targets = normal_roles._ProjectRoles.targets

        def change(caller):
            request = caller.f_locals["requests"][0]
            catalog = caller.f_locals["catalog"]
            if mutation == "group":
                object.__setattr__(request, "group", request.group + "-changed")
            elif mutation == "tuple-copy":
                object.__setattr__(request, "targets", tuple(list(request.targets)))
            elif mutation == "target-copy":
                object.__setattr__(request, "targets", (replace(request.targets[0]),))
            elif mutation == "target-field":
                target = request.targets[0]
                object.__setattr__(
                    target, "anchor_node", tuple(list(target.anchor_node))
                )
            elif mutation in ("inactive", "final-accessor"):
                catalog._active = False
            elif mutation == "receiver":
                catalog._receiver += 1
            reached.append(mutation)

        def change_request(seed):
            native_close(seed)
            caller = sys._getframe(1)
            if caller.f_code is generations.discover_supplemental_controls.__code__:
                change(caller)

        def change_final_accessor(seed):
            result = native_targets(seed)
            caller = sys._getframe(1)
            if (
                caller.f_code is generations.discover_supplemental_controls.__code__
                and "requests" in caller.f_locals
            ):
                change(caller)
            return result

        stages = self.state / "generation-stages"
        stages.mkdir(mode=0o700)
        try:
            with self.reopen() as journal:
                with staged_layout_controls(stages, journal) as pool:
                    with self.observing(pool) as owner:
                        proposal = owner.plan_controls(self.targets)
                        with owner._reads():
                            with controls.acquire_layout_recovery_controls(
                                pool,
                                proposal,
                                acknowledged_recovery_identity=proposal.identity,
                                allow_host_execution=True,
                            ) as original:
                                for mutation in (
                                    "group",
                                    "tuple-copy",
                                    "target-copy",
                                    "target-field",
                                    "inactive",
                                    "receiver",
                                    "final-accessor",
                                ):
                                    with self.subTest(mutation=mutation):
                                        method, callback = (
                                            ("targets", change_final_accessor)
                                            if mutation == "final-accessor"
                                            else ("close_native_inputs", change_request)
                                        )
                                        with patch.object(
                                            normal_roles._ProjectRoles, method, callback
                                        ):
                                            with self.assertRaisesRegex(
                                                ValueError, "changed"
                                            ):
                                                owner.discover_supplemental_controls(
                                                    (original,)
                                                )
        finally:
            self.assertEqual(
                reached,
                [
                    "group",
                    "tuple-copy",
                    "target-copy",
                    "target-field",
                    "inactive",
                    "receiver",
                    "final-accessor",
                ],
            )


def _fresh_process(config):
    """Reconstruct test inputs only; actual owners come from fresh factories."""
    from literate_ai.adapters._write_reservations import WriteReservationTarget
    from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
    from literate_ai.contracts.identity import canonical_json_bytes
    from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

    assert not observation._OWNERS and not roles._CREATED_ROLES
    data = json.loads(config.read_text())
    harness = ForestGenerationTests()
    harness.state = Path(data["state"])
    harness.saved_binding = canonical_json_bytes(data["binding"])
    harness.saved_budget = LayoutJournalBudget(**data["journal_budget"])
    harness.parking = Path(data["parking"])
    harness.fresh_budget = RetainedCargoInputBudget.from_dict(data["budget"])
    harness.fresh_metadata_limit = data["fresh_metadata_limit"]
    harness.targets = tuple(
        WriteReservationTarget(
            Path(t["path"]), Path(t["anchor"]), tuple(t["anchor_node"]), t["advisory"]
        )
        for t in data["targets"]
    )
    with harness.fresh_generations("process-generation-stages") as (
        owner,
        current,
        recovered,
    ):
        value = observation._record(owner)
        before = tuple(value.journal._events)
        result = current_native.observe_current_native_forest(owner, current)
        assert tuple(value.journal._events) == before
        print(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "owners": len(recovered),
                    "complete": result.journal_complete,
                    "issues": result.issues,
                }
            )
        )


if __name__ == "__main__":
    _fresh_process(Path(sys.argv[1]))
