"""Actual fresh canonical roles observing separately acknowledged native prefixes.

The original canonical source forest admission still refuses. Native dependency
interruptions retain actual journals/endpoints under genuine normal locks; no
successful source phase, restored partition or recovery effect is fabricated.
"""

from __future__ import annotations

import copy
import inspect
import os
import unittest
from unittest import mock

import tests.critical.test_retained_layout_forest_observation as fixtures
from literate_ai.adapters import retained_layout_forest_current as current_native
from literate_ai.adapters import retained_layout_forest_native as native
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_recovery_roles as roles


class _Stopped(RuntimeError):
    pass


@unittest.skipUnless(os.name == "posix", "actual fresh native forest endpoints")
class ForestCurrentTests(unittest.TestCase):
    git = fixtures.ForestObservationTests.git
    init_git = fixtures.ForestObservationTests.init_git
    prepare = fixtures.ForestObservationTests.prepare
    pool = fixtures.ForestObservationTests.pool
    persist_guarded_root = fixtures.ForestObservationTests.persist_guarded_root
    reopen = fixtures.ForestObservationTests.reopen
    retain = fixtures.ForestObservationTests.retain
    observing = fixtures.ForestObservationTests.observing
    acquired = fixtures.ForestObservationTests.acquired

    @classmethod
    def setUpClass(cls):
        fixtures.ForestObservationTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.ForestObservationTests.setUp(self)
        self.cut = None

    def _closing_code(self):
        return next(
            item
            for item in current_native.observe_current_native_forest.__code__.co_consts
            if inspect.iscode(item) and item.co_name == "close_dependencies"
        )

    def run_unmanaged(self, journal, program):
        if self.cut is None:
            return fixtures.ForestObservationTests.run_unmanaged(self, journal, program)
        event, recorded = self.cut
        original = native._NativeForest._event
        hit = []

        def stop(owner, kind, data):
            if kind == event and not recorded:
                hit.append(True)
                raise _Stopped("actual native effect before its journal observation")
            original(owner, kind, data)
            if kind == event:
                hit.append(True)
                raise _Stopped("actual durable native prefix")

        with mock.patch.object(native._NativeForest, "_event", new=stop):
            with self.assertRaises(_Stopped):
                fixtures.ForestObservationTests.run_unmanaged(self, journal, program)
        self.assertEqual(hit, [True], "actual native prefix stop was not reached")
        return None

    def test_complete_native_span_is_observed_under_real_current_roles(self):
        self.retain()
        with self.acquired() as (owner, current):
            original = observation._record(owner)
            before = original.ledger.bytes, original.ledger.records
            result = current_native.observe_current_native_forest(owner, current)
            self.assertEqual(result.span, self.expected)
            self.assertEqual(result.position, "recorded")
            self.assertTrue(result.journal_complete)
            self.assertFalse(result.issues)
            self.assertIs(observation._record(owner), original)
            self.assertGreater(original.ledger.bytes, before[0])
            self.assertGreater(original.ledger.records, before[1])
            with mock.patch.object(
                os, "fstat", side_effect=AssertionError("borrowed FD")
            ):
                with self.assertRaisesRegex(ValueError, "creating canonical recovery"):
                    current_native.observe_current_native_forest(
                        owner, copy.copy(current)
                    )
                copied = copy.copy(current)

                class UnregisteredSeed:
                    @property
                    def root(self):
                        raise AssertionError("unregistered seed dereferenced")

                copied._seed = UnregisteredSeed()
                with self.assertRaisesRegex(ValueError, "creating canonical recovery"):
                    current_native.observe_current_native_forest(owner, copied)
                fake = observation._ForestRecoveryObservation(observation._KEY)
                with self.assertRaisesRegex(ValueError, "observation|lifetime"):
                    current_native.observe_current_native_forest(fake, current)

    def test_real_pending_prefixes_preserve_ambiguity_and_derive_exact_native_moves(
        self,
    ):
        cases = (
            ("forest-parking-intent", True, "pending-before"),
            ("forest-parking-observed", False, "unresolved"),
            ("forest-directory-intent", True, "pending-before"),
            ("forest-directory-observed", False, "unresolved"),
            ("forest-directory-observed", True, "recorded"),
            ("forest-entry-intent", True, "pending-before"),
            ("forest-entry-observed", False, "pending-after"),
            ("forest-mode-intent", True, "pending-before"),
            ("forest-mode-observed", False, "pending-after"),
        )
        for index, (kind, recorded, expected) in enumerate(cases):
            with self.subTest(kind=kind, recorded=recorded):
                if index:
                    self.setUp()
                self.project.chmod(0o750)
                self.cut = kind, recorded
                self.retain()
                private_before = (
                    self.parking.stat().st_ino if self.parking.exists() else None
                )
                with self.acquired() as (owner, current):
                    result = current_native.observe_current_native_forest(
                        owner, current
                    )
                    self.assertEqual(result.position, expected)
                    self.assertFalse(result.journal_complete)
                    self.assertEqual(bool(result.issues), expected == "unresolved")
                    if expected == "unresolved":
                        self.assertIsNone(result.span)
                    else:
                        self.assertIsNotNone(result.span)
                    if kind == "forest-directory-observed" and recorded:
                        self.assertTrue(result.refreshed_directories)
                if private_before is not None:
                    self.assertEqual(self.parking.stat().st_ino, private_before)

    def test_preliminary_pending_probe_never_follows_a_redirected_parent(self):
        self.cut = "forest-entry-intent", True
        self.retain()
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            step = native._native_event_schedule(value.program)[
                value.frontier.consumed - 1
            ][0]
            _operation, action = native._native_steps(value.program)[step]
            target = (
                value.frontier.span.roots[action.destination_area].root
                / action.destination
            )
            retained = self.parking.with_name("kept-native-parking")
            self.parking.rename(retained)
            outside = self.state / "foreign-outside"
            outside.mkdir()
            foreign = outside / target.name
            foreign.write_bytes(b"foreign endpoint\n")
            self.parking.symlink_to(outside, target_is_directory=True)
            lstat = os.lstat

            def no_redirected_leaf(path, *args, **kwargs):
                if path == target or path == str(target):
                    raise AssertionError("followed a redirected endpoint parent")
                return lstat(path, *args, **kwargs)

            with mock.patch.object(os, "lstat", new=no_redirected_leaf):
                with self.assertRaisesRegex(ValueError, "redirected|ancestor"):
                    current_native.observe_current_native_forest(owner, current)
            self.assertEqual(foreign.read_bytes(), b"foreign endpoint\n")
            self.assertTrue(self.parking.is_symlink())
            self.assertTrue(retained.is_dir())

    def test_late_canonical_callback_cannot_change_earlier_source_payload_unchecked(
        self,
    ):
        self.retain()
        payload = self.project / "retained/app.py"
        hit = []
        with self.acquired() as (owner, current):
            close = current.require_current
            closing_code = self._closing_code()

            def late():
                close()
                if inspect.currentframe().f_back.f_code is closing_code:
                    self.assertFalse(hit)
                    payload.write_bytes(b"foreign current source bytes\\n")
                    hit.append(True)

            with mock.patch.object(current, "require_current", new=late):
                with self.assertRaisesRegex(ValueError, "runtime native|runtime root"):
                    current_native.observe_current_native_forest(owner, current)
            self.assertEqual(hit, [True])
        self.assertEqual(payload.read_bytes(), b"foreign current source bytes\\n")

    def test_late_role_or_parent_revocation_refuses_before_more_borrowed_fd_access(
        self,
    ):
        self.retain()
        for kind in ("role", "parent"):
            with self.subTest(kind=kind):
                # Each genuine fresh operation has its own explicit allowance;
                # failed observations never refund or reset an old reader.
                with self.acquired() as (owner, current):
                    table, key = (
                        (roles._CREATED_ROLES, current)
                        if kind == "role"
                        else (observation._POOLS, current._pool)
                    )
                    original, hit, patches = table[key], [], []
                    close = current.require_current
                    closing_code = self._closing_code()

                    def late(
                        *,
                        close=close,
                        closing_code=closing_code,
                        hit=hit,
                        table=table,
                        key=key,
                        patches=patches,
                    ):
                        close()
                        if inspect.currentframe().f_back.f_code is closing_code:
                            self.assertFalse(hit)
                            table.pop(key)
                            hit.append(True)
                            patch = mock.patch.object(
                                os,
                                "fstat",
                                side_effect=AssertionError("FD after revoke"),
                            )
                            patch.start()
                            patches.append(patch)

                    try:
                        with mock.patch.object(current, "require_current", new=late):
                            with self.assertRaises(ValueError):
                                current_native.observe_current_native_forest(
                                    owner, current
                                )
                    finally:
                        for patch in reversed(patches):
                            patch.stop()
                        table[key] = original
                        self.assertEqual(hit, [True], "late callback did not execute")

    def test_shared_allowance_refuses_before_current_native_descriptor_access(self):
        self.retain()
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
                    os, "open", side_effect=AssertionError("unfunded native open")
                ):
                    entered.append(True)
                    current_native.observe_current_native_forest(owner, current)
        self.assertEqual(entered, [True], "fixture failed before actual observer entry")
