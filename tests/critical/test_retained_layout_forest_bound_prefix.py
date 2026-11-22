"""Actual bound source intent before interrupted native dependency execution.

Normal canonical roles are real; original canonical forest admission still
refuses. Native interruption is at actual durable journal/effect boundaries.
No successful forest SourcePhase or acquired partition is manufactured.
"""

from __future__ import annotations

import hashlib
import os
import unittest
from unittest import mock

import tests.critical.test_retained_layout_forest_metadata_replay as metadata_fixture
import tests.critical.test_retained_layout_forest_recovery as recovery_fixture
from literate_ai.adapters import retained_layout_forest_current as current_native
from literate_ai.adapters import retained_layout_forest_effects as effects
from literate_ai.adapters import retained_layout_forest_native as native
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_forest_recovery as recovery
from literate_ai.adapters.exclusive_entry import layout_entry_node
from literate_ai.adapters.repository_refresh_reservations import _custody_wire
from literate_ai.adapters.retained_layout_partition import _lineage


class _Stopped(Exception):
    pass


@unittest.skipUnless(os.name == "posix", "actual bound native prefix")
class ForestBoundPrefixTests(unittest.TestCase):
    git = recovery_fixture.ForestRecoveryTests.git
    init_git = recovery_fixture.ForestRecoveryTests.init_git
    prepare = recovery_fixture.ForestRecoveryTests.prepare
    persist_guarded_root = recovery_fixture.ForestRecoveryTests.persist_guarded_root
    reopen = recovery_fixture.ForestRecoveryTests.reopen
    acquired = recovery_fixture.ForestRecoveryTests.acquired
    observing = recovery_fixture.ForestRecoveryTests.observing
    pool = recovery_fixture.ForestRecoveryTests.pool
    run_unmanaged = metadata_fixture.ForestMetadataReplayTests.run_unmanaged

    @classmethod
    def setUpClass(cls):
        recovery_fixture.ForestRecoveryTests.setUpClass.__func__(cls)

    def setUp(self):
        recovery_fixture.ForestRecoveryTests.setUp(self)
        self.cut = "forest-entry-observed", True

    def retain(self):
        real_event = native._NativeForest._event
        hit = []
        kind, recorded = self.cut

        def event(owner, name, data):
            if name == kind and not recorded:
                hit.append(name)
                raise _Stopped("actual native effect before observation")
            result = real_event(owner, name, data)
            if name == kind:
                hit.append(name)
                raise _Stopped("actual recorded native prefix")
            return result

        with mock.patch.object(native._NativeForest, "_event", event):
            with self.assertRaises(_Stopped):
                metadata_fixture.ForestMetadataReplayTests.retain(self)
        self.assertEqual(hit, [kind], "actual native prefix was not reached")
        self.assertEqual(tuple(self.metadata.iterdir()), ())
        self.assertEqual(tuple(self.retirement.iterdir()), ())

    def test_partial_native_retains_real_bound_future_private_roots(self):
        self.retain()
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            self.assertTrue(
                any(e["kind"] == "forest-source-intent" for e in value.saved.events)
            )
            self.assertFalse(value.frontier.complete)
            result = current_native.observe_current_native_forest(owner, current)
            self.assertIsNotNone(result.metadata)
            self.assertFalse(result.metadata.started)
            roots = {r.root for r in result.span.roots}
            self.assertIn(self.metadata, roots)
            self.assertIn(self.retirement, roots)
            self.assertIn(self.parking, roots)
            self.assertEqual(result.position, "recorded")

    def test_future_metadata_root_cannot_be_reused_as_recovery_quarantine(self):
        self.retain()
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "overlaps|participant"):
                recovery.plan_forest_data_recovery(owner, current, self.metadata)
        self.assertEqual(tuple(self.metadata.iterdir()), ())

    def test_bound_future_roots_preserve_parking_before_classification(self):
        self.cut = "forest-parking-intent", True
        self.retain()
        self.assertFalse(self.parking.exists())
        with self.acquired() as (owner, current):
            result = current_native.observe_current_native_forest(owner, current)
            self.assertIsNotNone(result.metadata)
            self.assertFalse(result.metadata.started)
            self.assertEqual(result.position, "pending-before")
            self.assertNotIn(self.parking, {r.root for r in result.span.roots})
        self.assertFalse(self.parking.exists())

    def test_replaced_future_retirement_root_refuses_and_preserves_both_roots(self):
        self.retain()
        original = self.retirement.with_name("kept-future-retirement")
        self.retirement.rename(original)
        self.retirement.mkdir(mode=0o700)
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "original observed ancestry"):
                current_native.observe_current_native_forest(owner, current)
        self.assertEqual(tuple(original.iterdir()), ())
        self.assertEqual(tuple(self.retirement.iterdir()), ())

    def test_foreign_future_metadata_entry_stays_unresolved_and_intact(self):
        self.retain()
        foreign = self.metadata / "new-0"
        foreign.write_bytes(b"unknown prospective-looking entry\n")
        before = layout_entry_node(foreign)
        with self.acquired() as (owner, current):
            with self.assertRaisesRegex(ValueError, "runtime native|runtime root"):
                current_native.observe_current_native_forest(owner, current)
        self.assertEqual(layout_entry_node(foreign), before)
        self.assertEqual(foreign.read_bytes(), b"unknown prospective-looking entry\n")

    def test_aliasing_bound_private_descriptions_refuse_before_current_source_access(
        self,
    ):
        actual = effects._Effects.document.fget

        def aliasing(value):
            document = actual(value)
            document["retirement"] = document["metadata"]
            return document

        with mock.patch.object(effects._Effects, "document", property(aliasing)):
            self.retain()
        with self.acquired() as (owner, current):
            with mock.patch.object(
                current_native,
                "_EndpointReads",
                side_effect=AssertionError("source access before bound validation"),
            ):
                with self.assertRaisesRegex(ValueError, "overlaps"):
                    current_native.observe_current_native_forest(owner, current)

    def test_actual_bound_pending_native_effect_restores_original_data(self):
        self.cut = "forest-entry-observed", False
        self.retain()
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            result = current_native.observe_current_native_forest(owner, current)
            self.assertEqual(result.position, "pending-after")
            self.assertFalse(result.metadata.started)
            plan = recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertTrue(plan.actions)
            restored = recovery.apply_forest_data_recovery(
                owner,
                current,
                plan,
                acknowledged_recovery_identity=plan.identity,
                allow_host_execution=True,
            )
            self.assertTrue(restored["data_verified"])
            original = value.program.span.roots[0]
            for name, blob, _executable in original.payloads:
                self.assertEqual(
                    hashlib.sha256((self.project / name).read_bytes()).hexdigest(),
                    blob.digest,
                    name,
                )
            self.assertEqual(
                set(dict(restored["span"].roots[0].native)), set(dict(original.native))
            )
            self.assertEqual(tuple(self.metadata.iterdir()), ())
            self.assertEqual(tuple(self.retirement.iterdir()), ())
            self.assertTrue((self.project / "litai/layout.pending").is_file())

    def test_future_metadata_root_cannot_be_the_fresh_control_producer(self):
        self.retain()
        self.fresh = self.metadata
        with self.acquired() as (owner, current):
            with mock.patch.object(
                current_native,
                "_EndpointReads",
                side_effect=AssertionError("source access before producer separation"),
            ):
                with self.assertRaisesRegex(
                    ValueError, "overlaps an actual participant"
                ):
                    current_native.observe_current_native_forest(owner, current)
        self.assertTrue((self.project / "litai/layout.pending").is_file())

    def test_future_metadata_cannot_alias_the_actual_journal_producer(self):
        actual = effects._Effects.document.fget

        def journal_root(value):
            document = actual(value)
            root = self.state / "journal"
            document["metadata"] = [
                str(root),
                _custody_wire(layout_entry_node(root)),
                _custody_wire(_lineage(root)),
            ]
            return document

        with mock.patch.object(effects._Effects, "document", property(journal_root)):
            self.retain()
        with self.acquired() as (owner, current):
            with mock.patch.object(
                current_native,
                "_EndpointReads",
                side_effect=AssertionError("source access before journal separation"),
            ):
                with self.assertRaisesRegex(
                    ValueError, "overlaps an actual participant"
                ):
                    current_native.observe_current_native_forest(owner, current)

    def test_late_parking_creation_cannot_be_reinterpreted_as_quarantine(self):
        self.cut = "forest-parking-intent", True
        self.retain()
        actual = recovery.observe_current_native_forest
        hit = []

        def after_observation(*args):
            result = actual(*args)
            self.parking.mkdir(mode=0o700)
            hit.append(layout_entry_node(self.parking))
            return result

        with self.acquired() as (owner, current):
            value = observation._record(owner)
            prior = tuple(value.journal._events)
            with mock.patch.object(
                recovery, "observe_current_native_forest", after_observation
            ):
                with self.assertRaisesRegex(ValueError, "overlaps original parking"):
                    recovery.plan_forest_data_recovery(owner, current, self.parking)
            self.assertEqual(tuple(value.journal._events), prior)
        self.assertEqual(
            len(hit), 1, "actual completed current observation was not reached"
        )
        self.assertEqual(layout_entry_node(self.parking), hit[0])
        self.assertEqual(tuple(self.parking.iterdir()), ())

    def test_completed_native_still_closes_unused_future_retirement(self):
        self.cut = "forest-native-complete", True
        self.retain()
        kept = self.retirement.with_name("kept-complete-retirement")
        self.retirement.rename(kept)
        self.retirement.mkdir(mode=0o700)
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            self.assertTrue(value.frontier.complete)
            with self.assertRaisesRegex(ValueError, "original observed ancestry"):
                current_native.observe_current_native_forest(owner, current)
        self.assertEqual(tuple(kept.iterdir()), ())
        self.assertEqual(tuple(self.retirement.iterdir()), ())
