"""Actual fresh control FDs; source/metadata recovery remains a separate owner."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import unittest
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

import tests.critical.test_retained_layout_reservations as fixtures
import tests.critical.test_retained_layout_transaction as source_fixtures
from literate_ai._cache_lock import CacheLockError
from literate_ai.adapters import retained_layout_recovery_controls as recovery
from literate_ai.adapters import retained_layout_reservations as original
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock_path
from literate_ai.adapters.repository_orchestration import OrchestrationInventoryError
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "POSIX fresh retained control recovery")
class RetainedLayoutControlRecoveryTests(unittest.TestCase):
    record = fixtures.RetainedLayoutReservationTests.record
    pool = fixtures.RetainedLayoutReservationTests.pool
    probe_mutex = fixtures.RetainedLayoutReservationTests.probe_mutex

    def setUp(self):
        fixtures.RetainedLayoutReservationTests.setUp(self)
        self.mutex = project_lifecycle_lock_path(self.project)
        self.targets = (self.record(self.mutex, advisory=True), self.record())
        self.retired = self.state / "retired"
        self.retired.mkdir(mode=0o700)
        (self.state / "recovery-stages").mkdir(mode=0o700)

    @contextmanager
    def reopen(self, *, budget=None):
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=b"{}",
            budget=LayoutJournalBudget() if budget is None else budget,
            recover=True,
        ) as journal:
            with staged_layout_controls(
                self.state / "recovery-stages", journal
            ) as pool:
                yield pool, journal

    def acquire(self, pool, plan, **overrides):
        return recovery.acquire_layout_recovery_controls(
            pool,
            plan,
            **{
                "acknowledged_recovery_identity": plan.identity,
                "allow_host_execution": True,
                **overrides,
            },
        )

    def retained(self):
        with self.pool() as (pool, _):
            with original.acquire_staged_layout_reservations(
                pool, self.targets
            ) as owned:
                old = owned
                before = {m.target.path: (m.node, m.content) for m in owned._markers}
        return before, old

    def interrupted(self, *, normalize=False, retire=False, postmove=False):
        with self.pool() as (pool, _):
            with self.assertRaisesRegex(OSError, "controlled interruption"):
                with original.acquire_staged_layout_reservations(
                    pool, self.targets
                ) as owned:
                    owned.begin_finalization(self.retired)
                    if normalize:
                        with mock.patch.object(
                            os,
                            "ftruncate",
                            side_effect=OSError("controlled interruption"),
                        ):
                            owned.normalize_advisory(self.mutex)
                    if retire:
                        if postmove:
                            move = original.move_layout_entry_exclusive

                            def interrupted_move(*args, **kwargs):
                                move(*args, **kwargs)
                                raise OSError("controlled interruption")

                            with mock.patch.object(
                                original,
                                "move_layout_entry_exclusive",
                                side_effect=interrupted_move,
                            ):
                                owned.retire_native(self.target)
                        else:
                            owned.retire_native(self.target)
                    raise OSError("controlled interruption")

    def test_readonly_plan_leaves_raw_tokens_and_journal_unchanged(self):
        before, _ = self.retained()
        with self.reopen() as (pool, journal):
            history = journal.events
            with mock.patch.object(
                recovery,
                "_acquire",
                side_effect=AssertionError("readonly plan acquired mutex"),
            ):
                plan = recovery.plan_layout_control_recovery(pool, self.targets)
            self.assertEqual(len(plan.markers), 2)
            self.assertEqual(journal.events, history)
        for path, (node, content) in before.items():
            self.assertEqual(path.stat().st_ino, node[1])
            self.assertEqual(path.read_bytes(), content)

    def test_missing_authority_or_exact_ack_never_acquires_or_records(self):
        self.retained()
        with self.reopen() as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            history = journal.events
            for overrides in (
                {"allow_host_execution": False},
                {"acknowledged_recovery_identity": None},
            ):
                with self.subTest(overrides=overrides):
                    with mock.patch.object(
                        recovery,
                        "_acquire",
                        side_effect=AssertionError("unauthorized acquisition"),
                    ):
                        with self.assertRaises(ValueError):
                            with self.acquire(pool, plan, **overrides):
                                self.fail("unauthorized recovery yielded")
                    self.assertEqual(journal.events, history)

    def test_fresh_actual_mutex_ownership_keeps_tokens_and_expires(self):
        before, old = self.retained()
        with self.reopen() as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            with self.acquire(pool, plan) as owned:
                self.assertTrue(owned.owns(self.mutex))
                self.assertTrue(owned.owns(self.target))
                self.assertEqual(self.probe_mutex(self.mutex).returncode, 23)
                with self.assertRaises(ValueError):
                    old.verify_all()
            self.assertTrue(all(m.descriptor == -1 for m in owned._markers))
            with mock.patch.object(
                os, "fstat", side_effect=AssertionError("expired descriptor touched")
            ):
                with self.assertRaisesRegex(ValueError, "context ended"):
                    owned.owns(self.target)
            self.assertEqual(
                journal.events[-1]["kind"], "control-recovery-acquisition-observed"
            )
        for path, (node, content) in before.items():
            self.assertEqual(path.stat().st_ino, node[1])
            self.assertEqual(path.read_bytes(), content)

    def test_actual_process_death_then_new_journal_and_control_locks(self):
        script = """
import os, signal, sys
from pathlib import Path
from literate_ai.adapters._write_reservations import WriteReservationTarget
from literate_ai.adapters.exclusive_entry import layout_entry_node
from literate_ai.adapters import retained_layout_journal as j
from literate_ai.adapters import retained_layout_control_publication as p
from literate_ai.adapters import retained_layout_reservations as r
project, state, mutex = map(Path, sys.argv[1:])
node=layout_entry_node(project)
anchor=(node.device,node.inode,node.mode)
targets=(
 WriteReservationTarget(mutex,project,anchor,advisory=True),
 WriteReservationTarget(project/'index.lock',project,anchor),
)
with j.retained_layout_journal(
 state/'journal',canonical_binding=b'{}',budget=j.LayoutJournalBudget()
) as journal:
 with p.staged_layout_controls(state/'stages',journal) as pool:
  with r.acquire_staged_layout_reservations(pool,targets):
   print('actual-owner-ready',flush=True)
   os.kill(os.getpid(),signal.SIGKILL)
"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(self.project),
                str(self.state),
                str(self.mutex),
            ],
            capture_output=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, -signal.SIGKILL, result.stderr)
        self.assertIn(b"actual-owner-ready", result.stdout)
        before = {t.path: t.path.read_bytes() for t in self.targets}
        with self.reopen() as (pool, _):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            with self.acquire(pool, plan) as owned:
                owned.verify_all()
                self.assertEqual(self.probe_mutex(self.mutex).returncode, 23)
        self.assertEqual({t.path: t.path.read_bytes() for t in self.targets}, before)

    def test_live_old_advisory_owner_prevents_recovery_takeover(self):
        with self.pool() as (pool, _):
            with original.acquire_staged_layout_reservations(pool, self.targets) as old:
                with staged_layout_controls(
                    self.state / "recovery-stages", pool._journal
                ) as fresh:
                    plan = recovery.plan_layout_control_recovery(fresh, self.targets)
                    with self.assertRaises(CacheLockError):
                        with self.acquire(fresh, plan):
                            self.fail("active OS mutex was bypassed")
                old.verify_all()
                self.assertEqual(self.probe_mutex(self.mutex).returncode, 23)

    def test_same_byte_foreign_replacement_refuses_stale_proposal(self):
        self.retained()
        with self.reopen() as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            displaced = self.state / "actual-token"
            self.target.rename(displaced)
            self.target.write_bytes(displaced.read_bytes())
            history = journal.events
            with self.assertRaises(ValueError):
                with self.acquire(pool, plan):
                    self.fail("foreign replacement adopted")
            self.assertEqual(journal.events, history)
        self.assertEqual(self.target.read_bytes(), displaced.read_bytes())
        self.assertNotEqual(self.target.stat().st_ino, displaced.stat().st_ino)

    def test_forged_plan_cannot_change_observed_payload_or_target_set(self):
        self.retained()
        with self.reopen() as (pool, _):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            forged = replace(
                plan,
                markers=(
                    replace(plan.markers[0], content=b"forged"),
                    *plan.markers[1:],
                ),
            )
            with self.assertRaisesRegex(ValueError, "exact fresh"):
                with self.acquire(pool, forged):
                    self.fail("forged native facts adopted")
            with self.assertRaisesRegex(ValueError, "complete actual target"):
                recovery.plan_layout_control_recovery(pool, self.targets[:1])

    def test_post_intent_foreign_replacement_is_retained_without_yield(self):
        self.retained()
        displaced = self.state / "actual-token"
        with self.reopen() as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            append = journal.append

            def replaced(kind, content):
                result = append(kind, content)
                if kind == "control-recovery-acquisition-intent":
                    self.target.rename(displaced)
                    self.target.write_bytes(displaced.read_bytes())
                return result

            with mock.patch.object(journal, "append", side_effect=replaced):
                with self.assertRaises(ValueError):
                    with self.acquire(pool, plan):
                        self.fail("post-intent replacement adopted")
        self.assertEqual(self.target.read_bytes(), displaced.read_bytes())

    def test_partial_normalization_is_locked_as_actual_bytes_without_rewriting(self):
        self.interrupted(normalize=True)
        partial = self.mutex.read_bytes()
        self.assertTrue(partial.startswith(b"\0"))
        self.assertGreater(len(partial), 1)
        with self.reopen() as (pool, _):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            with self.acquire(pool, plan) as owned:
                self.assertTrue(owned.owns(self.mutex))
                self.assertEqual(self.probe_mutex(self.mutex).returncode, 23)
        self.assertEqual(self.mutex.read_bytes(), partial)

    def test_normalization_without_intent_or_unknown_bytes_are_preserved(self):
        self.retained()
        self.mutex.write_bytes(b"\0unknown")
        with self.reopen() as (pool, _):
            with self.assertRaisesRegex(ValueError, "retained marker changed"):
                recovery.plan_layout_control_recovery(pool, self.targets)
        self.assertEqual(self.mutex.read_bytes(), b"\0unknown")

    def test_normalization_intent_does_not_authorize_arbitrary_current_bytes(self):
        self.interrupted(normalize=True)
        self.mutex.write_bytes(b"foreign bytes")
        with self.reopen() as (pool, _):
            with self.assertRaisesRegex(ValueError, "unknown normalization bytes"):
                recovery.plan_layout_control_recovery(pool, self.targets)
        self.assertEqual(self.mutex.read_bytes(), b"foreign bytes")

    def test_actual_move_without_observation_reopens_private_fd_not_public_role(self):
        self.interrupted(retire=True, postmove=True)
        private = next(self.retired.iterdir())
        token = private.read_bytes()
        with self.reopen() as (pool, _):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            with self.acquire(pool, plan) as owned:
                self.assertTrue(owned.owns(private))
                self.assertFalse(owned.owns(self.target))
                self.assertTrue(owned.owns(self.mutex))
        self.assertFalse(self.target.exists())
        self.assertEqual(private.read_bytes(), token)

    def test_foreign_reused_public_name_is_described_and_never_owned(self):
        self.interrupted(retire=True)
        self.target.write_bytes(b"new independent owner")
        foreign = self.target.stat().st_ino
        with self.reopen() as (pool, _):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            with self.acquire(pool, plan) as owned:
                self.assertFalse(owned.owns(self.target))
                self.assertTrue(owned.owns(next(self.retired.iterdir())))
        self.assertEqual(self.target.stat().st_ino, foreign)
        self.assertEqual(self.target.read_bytes(), b"new independent owner")

    def test_private_foreign_insertion_preserved_and_refused(self):
        self.interrupted(retire=True)
        foreign = self.retired / "foreign"
        foreign.write_bytes(b"untouched")
        with self.reopen() as (pool, _):
            with self.assertRaisesRegex(ValueError, "namespace"):
                recovery.plan_layout_control_recovery(pool, self.targets)
        self.assertEqual(foreign.read_bytes(), b"untouched")

    def test_same_byte_retired_marker_replacement_refuses(self):
        self.interrupted(retire=True)
        private = next(self.retired.iterdir())
        displaced = self.state / "actual-retired"
        private.rename(displaced)
        private.write_bytes(displaced.read_bytes())
        with self.reopen() as (pool, _):
            with self.assertRaisesRegex(ValueError, "retired marker was replaced"):
                recovery.plan_layout_control_recovery(pool, self.targets)
        self.assertEqual(private.read_bytes(), displaced.read_bytes())

    def test_late_private_insertion_refuses_before_yield_and_retires_all_fds(self):
        self.interrupted(retire=True)
        with self.reopen() as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            append = journal.append
            foreign = self.retired / "foreign"

            def inserted(kind, content):
                result = append(kind, content)
                if kind == "control-recovery-acquisition-observed":
                    foreign.write_bytes(b"preserve")
                return result

            observed = []
            close = os.close

            def closing(fd):
                observed.append(fd)
                close(fd)

            with mock.patch.object(journal, "append", side_effect=inserted):
                with mock.patch.object(recovery.os, "close", side_effect=closing):
                    with self.assertRaisesRegex(ValueError, "namespace"):
                        with self.acquire(pool, plan):
                            self.fail("yielded across private insertion")
            self.assertGreater(len(observed), 2)
        self.assertEqual(foreign.read_bytes(), b"preserve")

    def test_inherited_cleanup_cannot_unlock_parent_recovered_mutex(self):
        self.retained()
        with self.reopen() as (pool, _):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            with self.acquire(pool, plan) as owned:
                child = os.fork()
                if child == 0:
                    try:
                        try:
                            owned.owns(self.mutex)
                        except ValueError:
                            owned._release()
                            os._exit(0)
                        os._exit(2)
                    except BaseException:
                        os._exit(3)
                _, status = os.waitpid(child, 0)
                self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                owned.verify_all()
                self.assertEqual(self.probe_mutex(self.mutex).returncode, 23)

    def test_real_close_then_error_still_attempts_every_marker_once(self):
        self.retained()
        with self.reopen() as (pool, _):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            with self.assertRaises(OrchestrationInventoryError):
                with self.acquire(pool, plan) as owned:
                    fds = [m.descriptor for m in owned._markers]
                    attempts = []
                    close = os.close

                    def interrupted(fd):
                        close(fd)
                        if fd in fds:
                            attempts.append(fd)
                            if fd == fds[-1]:
                                raise OSError("controlled close after native effect")

                    # Keep this patch through manager teardown, including all
                    # remaining real closes; retire it via the test cleanup.
                    patch = mock.patch.object(os, "close", side_effect=interrupted)
                    patch.start()
                    self.addCleanup(patch.stop)
            patch.stop()
            self.assertEqual(attempts, list(reversed(fds)))
            self.assertTrue(all(m.descriptor == -1 for m in owned._markers))

    def test_empty_retirement_parent_replacement_after_intent_refuses(self):
        self.interrupted()
        displaced = self.state / "actual-retirement-root"
        with self.reopen() as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            append = journal.append

            def replaced(kind, content):
                result = append(kind, content)
                if kind == "control-recovery-acquisition-intent":
                    self.retired.rename(displaced)
                    self.retired.mkdir(mode=0o700)
                return result

            with mock.patch.object(journal, "append", side_effect=replaced):
                with self.assertRaisesRegex(ValueError, "ancestry|retirement"):
                    with self.acquire(pool, plan):
                        self.fail("empty retirement root replacement passed")
        self.assertTrue(displaced.is_dir())
        self.assertTrue(self.retired.is_dir())
        self.assertNotEqual(displaced.stat().st_ino, self.retired.stat().st_ino)

    def test_projected_portable_marker_alias_after_intent_refuses_before_yield(self):
        # This host folds ASCII and expanding Unicode spellings to the same
        # native inode. Project an extra directory name; do not claim a native
        # distinct-alias insertion. Real tokens and native FDs stay unchanged.
        self.retained()
        original_bytes = self.mutex.read_bytes()
        parent = self.mutex.parent.stat()
        scandir = os.scandir
        injected = False

        @contextmanager
        def projected(path):
            with scandir(path) as entries:
                info = os.fstat(path) if isinstance(path, int) else os.stat(path)
                names = list(entries)
                if injected and (info.st_dev, info.st_ino) == (
                    parent.st_dev,
                    parent.st_ino,
                ):
                    names.append(SimpleNamespace(name=self.mutex.name.upper()))
                yield iter(names)

        with self.reopen() as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            append = journal.append

            def inserted(kind, content):
                nonlocal injected
                result = append(kind, content)
                if kind == "control-recovery-acquisition-intent":
                    injected = True
                return result

            with mock.patch.object(journal, "append", side_effect=inserted):
                with mock.patch.object(os, "scandir", side_effect=projected):
                    with self.assertRaisesRegex(ValueError, "alias"):
                        with self.acquire(pool, plan):
                            self.fail("projected alias crossed recovery intent")
        self.assertEqual(self.mutex.read_bytes(), original_bytes)

    def test_descriptor_setup_failure_closes_the_actual_unregistered_fd(self):
        self.retained()
        with self.reopen() as (pool, _):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            actual_open = os.open
            opened = []

            def opening(path, *args, **kwargs):
                fd = actual_open(path, *args, **kwargs)
                if path in (self.mutex.name, self.target.name):
                    opened.append(fd)
                return fd

            with mock.patch.object(os, "open", side_effect=opening):
                with mock.patch.object(
                    recovery,
                    "_OwnedMarker",
                    side_effect=RuntimeError("controlled setup"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "controlled setup"):
                        with self.acquire(pool, plan):
                            self.fail("failed marker setup yielded")
            self.assertEqual(len(opened), 1)
            with self.assertRaises(OSError):
                os.fstat(opened[0])

    def test_journal_advance_invalidates_prior_ack_before_private_intent(self):
        self.retained()
        with self.reopen() as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            journal.append("unrelated-observation", b"{}")
            history = journal.events
            with self.assertRaisesRegex(ValueError, "exact fresh"):
                with self.acquire(pool, plan):
                    self.fail("stale journal proposal yielded")
            self.assertEqual(journal.events, history)

    def test_finite_event_budget_refuses_before_intent_or_mutex_acquisition(self):
        budget = LayoutJournalBudget(maximum_events=14)
        with self.pool(budget=budget) as (pool, _):
            with original.acquire_staged_layout_reservations(pool, self.targets):
                pass
        with self.reopen(budget=budget) as (pool, journal):
            plan = recovery.plan_layout_control_recovery(pool, self.targets)
            history = journal.events
            self.assertEqual(len(history), 13)
            with mock.patch.object(
                recovery, "_acquire", side_effect=AssertionError("budget bypass")
            ):
                with self.assertRaisesRegex(ValueError, "budget"):
                    with self.acquire(pool, plan):
                        self.fail("exhausted budget yielded")
            self.assertEqual(journal.events, history)

    def _late_dependency_change(self, kind):
        self.retained()
        entered = False
        armed, closes, closing, injected = False, 0, False, False
        captured = []
        constructor = recovery._RecoveredControlSet

        def constructing(*args):
            owned = constructor(*args)
            captured.append(owned)
            return owned

        with self.assertRaises(ValueError):
            with self.reopen() as (pool, journal):
                if kind == "known":
                    token = pool.stage_marker(b"known immutable private stage")
                    foreign = pool.root / pool._entries[token].name
                elif kind == "journal":
                    foreign = self.state / "journal/foreign"
                else:
                    foreign = pool.root / "foreign"
                plan = recovery.plan_layout_control_recovery(pool, self.targets)
                append = journal.append
                close_inputs = recovery._close_inputs
                native = recovery.layout_entry_node

                def appended(event, content):
                    nonlocal armed
                    result = append(event, content)
                    if event == "control-recovery-acquisition-observed":
                        armed = True
                    return result

                def closing_inputs(proposal):
                    nonlocal closes, closing
                    if armed:
                        closes += 1
                    closing = armed and closes == 2
                    try:
                        return close_inputs(proposal)
                    finally:
                        closing = False

                def observed(path):
                    nonlocal injected
                    result = native(path)
                    if closing and path == plan.markers[-1].named and not injected:
                        injected = True
                        foreign.write_bytes(b"retain late dependency mutation")
                    return result

                with (
                    mock.patch.object(journal, "append", side_effect=appended),
                    mock.patch.object(
                        recovery, "_close_inputs", side_effect=closing_inputs
                    ),
                    mock.patch.object(
                        recovery, "layout_entry_node", side_effect=observed
                    ),
                    mock.patch.object(
                        recovery, "_RecoveredControlSet", side_effect=constructing
                    ),
                ):
                    with self.acquire(pool, plan):
                        entered = True
        self.assertTrue(injected, "late native observation was not reached")
        self.assertFalse(entered, "verified lease crossed an actual dependency change")
        self.assertEqual(foreign.read_bytes(), b"retain late dependency mutation")
        self.assertEqual(len(captured), 1)
        self.assertTrue(all(marker.descriptor == -1 for marker in captured[0]._markers))

    def test_last_marker_read_cannot_cross_actual_foreign_journal_insertion(self):
        self._late_dependency_change("journal")

    def test_last_marker_read_cannot_cross_actual_foreign_pool_insertion(self):
        self._late_dependency_change("pool")

    def test_last_marker_read_cannot_cross_actual_known_stage_mutation(self):
        self._late_dependency_change("known")


@unittest.skipUnless(os.name == "posix", "POSIX actual transaction composition")
class RetainedLayoutTransactionControlRecoveryTests(unittest.TestCase):
    plan = source_fixtures.RetainedLayoutTransactionTests.plan
    pool = source_fixtures.RetainedLayoutTransactionTests.pool
    phase = source_fixtures.RetainedLayoutTransactionTests.phase

    @classmethod
    def setUpClass(cls):
        source_fixtures.RetainedLayoutTransactionTests.setUpClass.__func__(cls)

    def setUp(self):
        source_fixtures.RetainedLayoutTransactionTests.setUp(self)
        self.metadata = self.state / "metadata"
        self.retired = self.state / "retired"
        self.metadata.mkdir(mode=0o700)
        self.retired.mkdir(mode=0o700)
        (self.state / "recovery-stages").mkdir(mode=0o700)

    @contextmanager
    def reopened(self, plan, targets):
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=canonical_json_bytes(plan.binding),
            budget=LayoutJournalBudget(),
            recover=True,
        ) as journal:
            with staged_layout_controls(
                self.state / "recovery-stages", journal
            ) as pool:
                proposal = recovery.plan_layout_control_recovery(pool, targets)
                with recovery.acquire_layout_recovery_controls(
                    pool,
                    proposal,
                    acknowledged_recovery_identity=proposal.identity,
                    allow_host_execution=True,
                ) as owned:
                    yield owned

    def test_completed_actual_source_metadata_finalizer_reopens_unqualified_controls(
        self,
    ):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.phase(plan, pool) as phase:
                targets = tuple(m.target for m in phase.controls.reservations._markers)
                phase.move_source()
                phase.publish_metadata(self.metadata)
                phase.finalize_controls(self.retired)
        metadata = {path: path.read_bytes() for path in self.metadata.iterdir()}
        with self.reopened(plan, targets) as owned:
            self.assertTrue(owned.owns(project_lifecycle_lock_path(self.project)))
            self.assertFalse(owned.owns(layout_pending_control_path(self.project)))
            self.assertTrue(owned.owns(next(self.retired.iterdir())))
            owned.verify_all()
        self.assertEqual(
            {path: path.read_bytes() for path in self.metadata.iterdir()}, metadata
        )
        self.assertTrue(self.destination.is_dir())
        self.assertFalse(self.source.exists())

    def test_actual_interrupted_metadata_keeps_pending_and_is_not_data_recovery(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def interrupted(kind, content):
                result = append(kind, content)
                if kind == "metadata-quarantine-observed":
                    raise OSError("controlled metadata quarantine interruption")
                return result

            with self.assertRaisesRegex(OSError, "controlled metadata"):
                with self.phase(plan, pool) as phase:
                    targets = tuple(
                        m.target for m in phase.controls.reservations._markers
                    )
                    phase.move_source()
                    with mock.patch.object(journal, "append", side_effect=interrupted):
                        phase.publish_metadata(self.metadata)
        before = {
            m.target.path: m.target.path.read_bytes()
            for m in phase.controls.reservations._markers
        }
        with self.reopened(plan, targets) as owned:
            self.assertTrue(owned.owns(layout_pending_control_path(self.project)))
            owned.verify_all()
        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertTrue(self.destination.is_dir())
        self.assertFalse(self.source.exists())
        self.assertTrue(list(self.metadata.iterdir()))
