"""Real verified forest data handoff and canonical control effects.

Original source execution remains an unmanaged dependency under genuine normal
roles. No canonical forest SourcePhase or acquired partition is manufactured.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_generations as fixture
from literate_ai.adapters import retained_layout_disposition_compact as compact
from literate_ai.adapters import retained_layout_disposition_recording as recording
from literate_ai.adapters import retained_layout_forest_disposition as disposition
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_forest_span import _require_current


@unittest.skipUnless(os.name == "posix", "real forest canonical descriptor handoff")
class ForestDispositionTests(unittest.TestCase):
    git = fixture.ForestGenerationTests.git
    init_git = fixture.ForestGenerationTests.init_git
    prepare = fixture.ForestGenerationTests.prepare
    persist_guarded_root = fixture.ForestGenerationTests.persist_guarded_root
    reopen = fixture.ForestGenerationTests.reopen
    acquired = fixture.ForestGenerationTests.acquired
    observing = fixture.ForestGenerationTests.observing
    pool = fixture.ForestGenerationTests.pool
    restore = fixture.ForestGenerationTests.restore
    retain = fixture.ForestGenerationTests.retain
    run_unmanaged = fixture.ForestGenerationTests.run_unmanaged
    fresh_generations = fixture.ForestGenerationTests.fresh_generations
    setUp = fixture.ForestGenerationTests.setUp

    @classmethod
    def setUpClass(cls):
        fixture.ForestGenerationTests.setUpClass.__func__(cls)

    def test_actual_verified_data_handoff_retires_pending_and_preserves_forest(self):
        self.restore()
        retained = self.retired.stat().st_ino, self.retired.read_bytes()
        retirement = self.state / "forest-disposition"
        retirement.mkdir(mode=0o700)
        with self.fresh_generations() as (owner, current, recovered):
            plan = disposition.plan_forest_control_disposition(
                owner, current, self.quarantine, retirement
            )
            # Recording preparation shares the original non-reentrant scratch
            # workspace. Borrowing it alone grants no native verification read.
            original_coupon = disposition._COUPONS[plan]
            original_marker_reads = disposition._MARKER_READS[plan]
            scheduled_actions = sum(
                entry is not None and kind.endswith("-intent")
                for kind, entry in disposition._schedule(plan)
            )
            self.assertEqual(original_marker_reads[0], 2 * scheduled_actions)
            with disposition._workspace(plan):
                self.assertEqual(disposition._COUPONS[plan], original_coupon)
                with self.assertRaisesRegex(ValueError, "reentrant"):
                    with disposition._reading(plan):
                        self.fail("nested workspace obtained native read rights")
            self.assertEqual(disposition._COUPONS[plan], original_coupon)
            with disposition._reading(plan) as policy:
                self.assertIs(policy, original_coupon[0])
                with self.assertRaisesRegex(ValueError, "reentrant"):
                    with disposition._workspace(plan):
                        self.fail("native read allowed nested recording workspace")
                with self.assertRaisesRegex(ValueError, "reentrant"):
                    with disposition._marker_reading(plan):
                        self.fail("full verifier borrowed marker read allowance")
            self.assertEqual(disposition._MARKER_READS[plan], original_marker_reads)
            self.assertEqual(
                disposition._COUPONS[plan],
                (original_coupon[0], original_coupon[1] - 1),
            )
            self.assertEqual(
                tuple(r.root for r in plan.span.roots[:-1]),
                tuple(r.root for r in plan.data.span.roots),
            )
            value = observation._record(owner)
            history = tuple(value.journal._events)
            for ack, allow in ((None, True), (plan.identity, False)):
                with self.assertRaisesRegex(ValueError, "acknowledgement"):
                    disposition.apply_forest_control_disposition(
                        owner,
                        current,
                        plan,
                        acknowledged_recovery_identity=ack,
                        allow_host_execution=allow,
                    )
            with mock.patch.object(
                os, "fstat", side_effect=AssertionError("copied receipt borrowed FD")
            ):
                with self.assertRaisesRegex(ValueError, "creating"):
                    disposition.apply_forest_control_disposition(
                        owner,
                        current,
                        copy.copy(plan),
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
            self.assertEqual(tuple(value.journal._events), history)
            actual_read = disposition._require_current
            revoked = []

            def late_revoke(span, **kwargs):
                actual_read(span, **kwargs)
                current._active = False
                revoked.append(True)

            try:
                with mock.patch.object(disposition, "_require_current", late_revoke):
                    with self.assertRaisesRegex(ValueError, "context ended|lifetime"):
                        disposition._require_plan(owner, current, plan)
            finally:
                current._active = True
                self.assertEqual(revoked, [True])
            before = {
                e.target.path: (e.node.inode, e.content, e.original_content)
                for e in plan.entries
                if e.target.advisory
            }
            actual_dispatch, actual_read = (
                disposition._dispatch,
                disposition._require_current,
            )
            effects, direct, reentrant, nested, backend_reentrant = [], [], [], [], []
            actual_payload = value.journal.store_payload
            actual_marker = disposition.read_owned_marker
            marker_reads = []

            def marker(path, *, maximum_bytes):
                self.assertIs(type(maximum_bytes), int)
                self.assertLessEqual(
                    maximum_bytes, value.ledger.budget.maximum_file_bytes
                )
                with self.assertRaisesRegex(ValueError, "reentrant"):
                    with disposition._reading(plan):
                        self.fail("marker observation acquired full verifier policy")
                marker_reads.append((path, maximum_bytes))
                return actual_marker(path, maximum_bytes=maximum_bytes)

            def dispatch(effect, kind, entry, ordinal=None):
                if not effects:
                    effects.append(effect)
                    advisory, native = disposition.controls._actions(plan.entries)
                    with mock.patch.object(
                        os,
                        "fstat",
                        side_effect=AssertionError("direct native method borrowed FD"),
                    ):
                        if advisory:
                            with self.assertRaisesRegex(ValueError, "dispatch"):
                                effect.normalize(advisory[0])
                            direct.append("normalize")
                        if native:
                            with self.assertRaisesRegex(ValueError, "dispatch"):
                                effect.retire(native[0], 0)
                            direct.append("retire")
                return actual_dispatch(effect, kind, entry, ordinal)

            def read(span, **kwargs):
                if effects and not reentrant:
                    reentrant.append(True)
                    with mock.patch.object(
                        os,
                        "fstat",
                        side_effect=AssertionError("recursive verifier borrowed FD"),
                    ):
                        with self.assertRaisesRegex(ValueError, "reentrant"):
                            effects[0].verify()
                return actual_read(span, **kwargs)

            def payload(content):
                if (
                    effects
                    and content.startswith(compact.STEP_MAGIC)
                    and not backend_reentrant
                ):
                    effect = effects[0]
                    kind, raw = disposition._RECORDING[effect]
                    roster = tuple(value.journal._known.items())
                    with self.assertRaisesRegex(ValueError, "recording dispatch"):
                        recording.record(effect, kind, json.loads(raw))
                    self.assertEqual(tuple(value.journal._known.items()), roster)
                    backend_reentrant.append(True)
                if effects and not nested:
                    effect = effects[0]
                    kind, entry = disposition._DISPATCH[effect]
                    nested.append(kind)
                    with mock.patch.object(
                        os,
                        "fstat",
                        side_effect=AssertionError("nested method borrowed FD"),
                    ):
                        with self.assertRaisesRegex(ValueError, "reentrant"):
                            if kind == "normalize":
                                effect.normalize(entry)
                            else:
                                effect.retire(
                                    entry, disposition._native(effect.plan).index(entry)
                                )
                return actual_payload(content)

            before_apply_reads = disposition._COUPONS[plan][1]
            with (
                mock.patch.object(disposition, "_dispatch", dispatch),
                mock.patch.object(disposition, "_require_current", read),
                mock.patch.object(value.journal, "store_payload", payload),
                mock.patch.object(disposition, "read_owned_marker", marker),
            ):
                result = disposition.apply_forest_control_disposition(
                    owner,
                    current,
                    plan,
                    acknowledged_recovery_identity=plan.identity,
                    allow_host_execution=True,
                )
            self.assertEqual(direct, ["normalize", "retire"])
            self.assertEqual(reentrant, [True])
            self.assertEqual(nested, ["normalize"])
            self.assertEqual(backend_reentrant, [True])
            self.assertEqual(len(marker_reads), original_marker_reads[0])
            self.assertEqual(disposition._MARKER_READS[plan][0], 0)
            # Observe the actual complete native dispatch, including its opening
            # factory/plan checks and release/completion boundary verifications.
            # A new full native read must renew this pre-effect reservation bound.
            self.assertEqual(
                before_apply_reads - disposition._COUPONS[plan][1],
                8 + 6 * scheduled_actions,
            )
            self.assertTrue(result["internal_recovery_complete"])
            self.assertTrue(result["controls_released"])
            self.assertFalse(result["feature_complete"])
            self.assertFalse(result["qualified"])
            self.assertFalse(layout_pending_control_path(self.project).exists())
            _require_current(result["span"])
            with self.assertRaises(ValueError):
                current.require_current()
            for raw in recovered:
                raw.verify_all()
            for path, (inode, content, original) in before.items():
                self.assertEqual(path.stat().st_ino, inode)
                self.assertEqual(
                    path.read_bytes(),
                    b"\0"
                    if original.startswith(disposition.controls._PREFIX)
                    else content,
                )
            from literate_ai.adapters.retained_layout_disposition_read import (
                control_events,
            )

            physical = value.journal.events
            self.assertEqual(
                [e["kind"] for e in physical[len(history) :]],
                [
                    "recovery-control-batch-intent",
                    "recovery-control-batch-decision",
                    "recovery-control-batch-observed",
                ],
            )
            events = control_events(value.pool)
            moves = [
                e for e in events if e["kind"] == "recovery-control-retirement-intent"
            ]
            decision = next(
                e for e in events if e["kind"] == "recovery-control-release-decision"
            )
            self.assertEqual(
                moves[-1]["data"]["source"],
                str(layout_pending_control_path(self.project)),
            )
            self.assertLess(decision["sequence"], moves[-1]["sequence"])
        self.assertEqual(
            (self.retired.stat().st_ino, self.retired.read_bytes()), retained
        )

    def test_last_manifest_publication_callback_cannot_replace_recording_fields(self):
        self.assert_manifest_callback_refuses()

    def test_last_manifest_publication_callback_cannot_revoke_original_roles(self):
        self.assert_manifest_callback_refuses(revoke_role=True)

    def assert_manifest_callback_refuses(self, *, revoke_role=False):
        self.restore()
        retirement = self.state / "recording-field-disposition"
        retirement.mkdir(mode=0o700)
        with self.fresh_generations() as (owner, current, _recovered):
            plan = disposition.plan_forest_control_disposition(
                owner, current, self.quarantine, retirement
            )
            value = observation._record(owner)
            before = tuple(value.journal._events)
            actual = value.journal.store_payload
            record = recording._PLANS[plan]
            epoch = record.manifest.epoch
            reached = []

            def replace_manifest(content):
                result = actual(content)
                if content is record.manifest.raw and not reached:
                    if revoke_role:
                        current._active = False
                    else:
                        object.__setattr__(
                            record.manifest, "epoch", "sha256:" + "9" * 64
                        )
                    reached.append(True)
                return result

            try:
                with mock.patch.object(
                    value.journal, "store_payload", replace_manifest
                ):
                    with self.assertRaisesRegex(
                        ValueError, "recording manifest|canonical role lifetime"
                    ):
                        disposition.apply_forest_control_disposition(
                            owner,
                            current,
                            plan,
                            acknowledged_recovery_identity=plan.identity,
                            allow_host_execution=True,
                        )
            finally:
                current._active = True
                object.__setattr__(record.manifest, "epoch", epoch)
            self.assertEqual(reached, [True])
            self.assertEqual(tuple(value.journal._events), before)
            self.assertEqual(tuple(retirement.iterdir()), ())
            self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_last_native_callback_cannot_replace_successor_budget(self):
        self.restore()
        retirement = self.state / "forest-disposition"
        retirement.mkdir(mode=0o700)
        reached = []
        actual_read = disposition._require_current

        def replace_successor(span, **kwargs):
            result = actual_read(span, **kwargs)
            caller = sys._getframe(1)
            if (
                not reached
                and caller.f_code is disposition._ForestState._advance.__code__
            ):
                successor = caller.f_locals["span"]
                object.__setattr__(successor, "budget", replace(successor.budget))
                reached.append(True)
            return result

        try:
            with self.assertRaisesRegex(ValueError, "successor"):
                with self.fresh_generations() as (owner, current, _recovered):
                    plan = disposition.plan_forest_control_disposition(
                        owner, current, self.quarantine, retirement
                    )
                    with mock.patch.object(
                        disposition, "_require_current", replace_successor
                    ):
                        disposition.apply_forest_control_disposition(
                            owner,
                            current,
                            plan,
                            acknowledged_recovery_identity=plan.identity,
                            allow_host_execution=True,
                        )
        finally:
            self.assertEqual(reached, [True])

    def test_observed_case_alias_refuses_before_disposition_intent(self):
        self.restore()
        retirement = self.state / "forest-disposition"
        retirement.mkdir(mode=0o700)
        with self.fresh_generations() as (owner, current, recovered):
            candidates = [
                record
                for raw in recovered
                for record in raw._plan.markers
                if record.target.advisory
                and record.content.startswith(disposition.controls._PREFIX)
            ]
            chosen = None
            for record in candidates:
                alias = record.named.with_name(record.named.name.swapcase())
                if (
                    alias != record.named
                    and alias.exists()
                    and alias.samefile(record.named)
                ):
                    chosen = record, alias
                    break
            if chosen is None:
                self.skipTest("filesystem has no actual control case alias")
            record, alias = chosen
            value = observation._record(owner)
            value.reader.file(alias, maximum_bytes=256)
            before = tuple(value.journal._events)
            native = record.named.stat().st_ino, record.named.read_bytes()
            try:
                with self.assertRaisesRegex(ValueError, "alias"):
                    disposition.plan_forest_control_disposition(
                        owner, current, self.quarantine, retirement
                    )
            finally:
                self.assertEqual(tuple(value.journal._events), before)
                self.assertEqual(
                    (record.named.stat().st_ino, record.named.read_bytes()), native
                )
                self.assertEqual(tuple(retirement.iterdir()), ())
