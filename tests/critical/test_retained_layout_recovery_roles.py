"""Actual canonical recovery roles and staged native controls, no data recovery."""

from __future__ import annotations

import os
import shutil
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_reservations as lease_fixtures
import tests.critical.test_retained_layout_transaction as source_fixtures
from literate_ai.adapters import retained_layout_recovery_roles as roles
from literate_ai.adapters._write_reservations import WriteReservationTarget
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock_path
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_control_roles import (
    acquire_retained_layout_control_roles,
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.adapters.retained_layout_recovery_controls import (
    acquire_layout_recovery_controls,
    plan_layout_control_recovery,
)
from literate_ai.adapters.retained_layout_reservations import (
    acquire_staged_layout_reservations,
)
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "POSIX canonical recovery role composition")
class RetainedLayoutRecoveryRoleTests(unittest.TestCase):
    plan = source_fixtures.RetainedLayoutTransactionTests.plan
    pool = source_fixtures.RetainedLayoutTransactionTests.pool
    phase = source_fixtures.RetainedLayoutTransactionTests.phase
    git = source_fixtures.RetainedLayoutTransactionTests.git
    init_git = source_fixtures.RetainedLayoutTransactionTests.init_git
    probe_mutex = lease_fixtures.RetainedLayoutReservationTests.probe_mutex

    @classmethod
    def setUpClass(cls):
        source_fixtures.RetainedLayoutTransactionTests.setUpClass.__func__(cls)

    def setUp(self):
        source_fixtures.RetainedLayoutTransactionTests.setUp(self)
        self.metadata, self.retired = self.state / "metadata", self.state / "retired"
        self.metadata.mkdir(mode=0o700)
        self.retired.mkdir(mode=0o700)
        (self.state / "recovery-stages").mkdir(mode=0o700)

    def retained(self, *, finalized=False):
        self.original = self.plan()
        with self.pool(self.original) as (pool, _):
            if finalized:
                with self.phase(self.original, pool) as phase:
                    self.targets = tuple(
                        m.target for m in phase.controls.reservations._markers
                    )
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
            else:
                with acquire_retained_layout_control_roles(self.project, pool) as lease:
                    self.targets = tuple(m.target for m in lease.reservations._markers)

    @contextmanager
    def reopened(self):
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=canonical_json_bytes(self.original.binding),
            budget=LayoutJournalBudget(),
            recover=True,
        ) as journal:
            with staged_layout_controls(
                self.state / "recovery-stages", journal
            ) as pool:
                proposal = plan_layout_control_recovery(pool, self.targets)
                with acquire_layout_recovery_controls(
                    pool,
                    proposal,
                    acknowledged_recovery_identity=proposal.identity,
                    allow_host_execution=True,
                ) as raw:
                    yield pool, journal, (raw,)

    def proposal(self, pool, raw):
        return roles.plan_recovered_layout_roles(self.project, pool, raw)

    def acquire(self, pool, raw, plan, **overrides):
        return roles.acquire_recovered_layout_roles(
            pool,
            raw,
            plan,
            **{
                "acknowledged_recovery_identity": plan.identity,
                "allow_host_execution": True,
                **overrides,
            },
        )

    def test_actual_project_roles_reuse_original_mutexes_without_new_markers(self):
        self.retained()
        before = {target.path: target.path.read_bytes() for target in self.targets}
        with self.reopened() as (pool, journal, raw):
            history = journal.events
            plan = self.proposal(pool, raw)
            self.assertEqual(plan.missing, ())
            self.assertEqual(journal.events, history)
            with self.acquire(pool, raw, plan) as lease:
                lease.require_initial_inputs()
                self.assertEqual(lease.fixed_anchors, (self.project,))
                self.assertEqual(lease.protected_admin_entries, ())
                self.assertEqual(
                    self.probe_mutex(
                        project_lifecycle_lock_path(self.project)
                    ).returncode,
                    23,
                )
                self.assertEqual(len(lease.reservations._inventory), len(self.targets))
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_actual_git_roles_block_native_index_writer_under_fresh_descriptors(self):
        self.init_git()
        self.retained()
        with self.reopened() as (pool, _, raw):
            plan = self.proposal(pool, raw)
            self.assertIsNotNone(plan.git.files)
            with self.acquire(pool, raw, plan) as lease:
                self.assertIn(self.project / ".git", lease.protected_admin_entries)
                self.assertNotEqual(self.git("add", ".", check=False).returncode, 0)
                lease.require_current()

    def test_retired_pending_gets_new_known_node_without_relabeling_old_private_fd(
        self,
    ):
        self.retained(finalized=True)
        pending = layout_pending_control_path(self.project)
        old = next(self.retired.iterdir())
        old_node, old_bytes = old.stat(), old.read_bytes()
        with self.reopened() as (pool, journal, raw):
            plan = self.proposal(pool, raw)
            self.assertEqual(tuple(t.path for t in plan.missing), (pending,))
            with self.acquire(pool, raw, plan) as lease:
                self.assertTrue(lease.reservations.owns(pending))
                self.assertFalse(raw[0].owns(pending))
                self.assertTrue(raw[0].owns(old))
                self.assertNotEqual(pending.stat().st_ino, old_node.st_ino)
                incoming = lease.reservations._incoming
                self.assertTrue(incoming._markers[0].created)
                self.assertIn(
                    "control-recovery-public-handoff",
                    [e["kind"] for e in journal.events],
                )
            self.assertTrue(all(m.descriptor == -1 for m in incoming._markers))
            raw[0].verify_all()
        self.assertEqual(old.read_bytes(), old_bytes)
        self.assertEqual(old.stat().st_ino, old_node.st_ino)
        self.assertTrue(pending.exists())
        self.assertTrue(self.destination.is_dir())

    def test_git_handoff_uses_current_index_and_reacquires_native_names(
        self,
    ):
        self.init_git()
        self.retained(finalized=True)
        self.assertEqual(self.git("add", "retained", check=False).returncode, 0)
        index = (self.project / ".git/index").read_bytes()
        before = {path: path.read_bytes() for path in self.retired.iterdir()}
        with self.reopened() as (pool, _, raw):
            plan = self.proposal(pool, raw)
            self.assertEqual(plan.git.files.index.content, index)
            with self.acquire(pool, raw, plan) as lease:
                self.assertTrue(
                    lease.reservations.owns(self.project / ".git/index.lock")
                )
                self.assertNotEqual(self.git("add", ".", check=False).returncode, 0)
                lease.require_current()
        self.assertEqual((self.project / ".git/index").read_bytes(), index)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_foreign_pending_occupant_refuses_without_publication(self):
        self.retained(finalized=True)
        pending = layout_pending_control_path(self.project)
        pending.write_bytes(b"foreign pending owner")
        inode = pending.stat().st_ino
        with self.reopened() as (pool, journal, raw):
            history = journal.events
            with self.assertRaises(ValueError):
                self.proposal(pool, raw)
            self.assertEqual(journal.events, history)
        self.assertEqual(pending.read_bytes(), b"foreign pending owner")
        self.assertEqual(pending.stat().st_ino, inode)

    def test_foreign_git_control_refuses_without_publication(self):
        self.init_git()
        self.retained(finalized=True)
        foreign = self.project / ".git/HEAD.lock"
        foreign.write_bytes(b"independent Git writer")
        with self.reopened() as (pool, journal, raw):
            history = journal.events
            with self.assertRaises(ValueError):
                self.proposal(pool, raw)
            self.assertEqual(journal.events, history)
        self.assertEqual(foreign.read_bytes(), b"independent Git writer")

    def test_missing_ack_or_execution_cannot_publish_absent_control(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, journal, raw):
            plan = self.proposal(pool, raw)
            history = journal.events
            for overrides in (
                {"allow_host_execution": False},
                {"acknowledged_recovery_identity": None},
            ):
                with self.subTest(overrides=overrides):
                    with self.assertRaises(ValueError):
                        with self.acquire(pool, raw, plan, **overrides):
                            self.fail("unauthorized canonical publication")
            self.assertEqual(journal.events, history)
            self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_forged_missing_targets_do_not_override_current_canonical_roles(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, journal, raw):
            plan = self.proposal(pool, raw)
            forged = replace(plan, missing=())
            history = journal.events
            with self.assertRaisesRegex(ValueError, "exact fresh"):
                with self.acquire(pool, raw, forged):
                    self.fail("forged role target map accepted")
            self.assertEqual(journal.events, history)
            self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_project_manifest_same_byte_replacement_invalidates_acknowledgement(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, _, raw):
            plan = self.proposal(pool, raw)
            manifest = self.project / "literate.project.json"
            displaced = self.state / "actual-manifest"
            manifest.rename(displaced)
            manifest.write_bytes(displaced.read_bytes())
            with self.assertRaisesRegex(ValueError, "exact fresh"):
                with self.acquire(pool, raw, plan):
                    self.fail("changed manifest inode accepted")
        self.assertEqual(manifest.read_bytes(), displaced.read_bytes())

    def test_journal_advance_invalidates_canonical_proposal(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, journal, raw):
            plan = self.proposal(pool, raw)
            journal.append("unrelated-current-observation", b"{}")
            history = journal.events
            with self.assertRaisesRegex(ValueError, "exact fresh"):
                with self.acquire(pool, raw, plan):
                    self.fail("stale canonical journal snapshot accepted")
            self.assertEqual(journal.events, history)

    def test_native_git_input_change_invalidates_canonical_proposal(self):
        self.init_git()
        self.retained(finalized=True)
        with self.reopened() as (pool, _, raw):
            plan = self.proposal(pool, raw)
            config = self.project / ".git/config"
            config.write_bytes(config.read_bytes() + b"\n[review]\n value = changed\n")
            with self.assertRaisesRegex(ValueError, "exact fresh"):
                with self.acquire(pool, raw, plan):
                    self.fail("stale Git configuration accepted")
        self.assertIn(b"changed", config.read_bytes())

    def test_post_intent_manifest_drift_refuses_before_absent_marker_creation(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, journal, raw):
            plan = self.proposal(pool, raw)
            append = journal.append

            def replaced(kind, content):
                result = append(kind, content)
                if kind == "recovery-canonical-roles-intent":
                    manifest = self.project / "literate.project.json"
                    saved = self.state / "manifest-before-intent-drift"
                    manifest.rename(saved)
                    manifest.write_bytes(saved.read_bytes())
                return result

            with mock.patch.object(journal, "append", side_effect=replaced):
                with self.assertRaises(ValueError):
                    with self.acquire(pool, raw, plan):
                        self.fail("canonical publication crossed manifest drift")
            self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_late_journal_insertion_never_yields_canonical_roles(self):
        self.retained(finalized=True)
        entered = False
        foreign = self.state / "journal/foreign"
        with self.assertRaises(ValueError):
            with self.reopened() as (pool, journal, raw):
                plan = self.proposal(pool, raw)
                append = journal.append

                def inserted(kind, content):
                    result = append(kind, content)
                    if kind == "recovery-canonical-roles-observed":
                        foreign.write_bytes(b"late foreign record")
                    return result

                with mock.patch.object(journal, "append", side_effect=inserted):
                    with self.acquire(pool, raw, plan):
                        entered = True
        self.assertFalse(entered)
        self.assertEqual(foreign.read_bytes(), b"late foreign record")
        self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_cached_role_and_catalog_expire_before_any_native_fd_lookup(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, _, raw):
            plan = self.proposal(pool, raw)
            with self.acquire(pool, raw, plan) as lease:
                catalog = lease.reservations
            with mock.patch.object(
                os, "fstat", side_effect=AssertionError("expired FD read")
            ):
                with self.assertRaisesRegex(ValueError, "role context ended"):
                    lease.require_current()
                with self.assertRaisesRegex(ValueError, "descriptor context ended"):
                    catalog.owns(layout_pending_control_path(self.project))

    def test_supplemental_generation_reopens_and_proves_current_public_ownership(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, journal, raw):
            plan = self.proposal(pool, raw)
            with self.acquire(pool, raw, plan) as lease:
                supplemental = tuple(
                    m.target for m in lease.reservations._incoming._markers
                )
                group = [
                    e["data"]["group"]
                    for e in journal.events
                    if e["kind"] == "reservation-set-acquired"
                ][-1]
        with self.reopened() as (pool, _, original):
            proposal = plan_layout_control_recovery(
                pool, supplemental, reservation_group=group
            )
            with acquire_layout_recovery_controls(
                pool,
                proposal,
                acknowledged_recovery_identity=proposal.identity,
                allow_host_execution=True,
            ) as extra:
                recovered = (*original, extra)
                plan = self.proposal(pool, recovered)
                self.assertEqual(plan.missing, ())
                with self.acquire(pool, recovered, plan) as lease:
                    pending = layout_pending_control_path(self.project)
                    self.assertFalse(original[0].owns(pending))
                    self.assertTrue(extra.owns(pending))
                    self.assertTrue(lease.reservations.owns(pending))
                    self.assertEqual(
                        len(lease.reservations._inventory),
                        len(self.targets) + len(supplemental),
                    )

    def test_recorded_advisory_label_cannot_satisfy_actual_native_pending_role(self):
        self.retained(finalized=True)
        pending = layout_pending_control_path(self.project)
        anchor = self.targets[0].anchor_node
        wrong = WriteReservationTarget(pending, self.project, anchor, advisory=True)
        with self.assertRaisesRegex(OSError, "controlled incomplete"):
            with self.reopened() as (pool, journal, _):
                with acquire_staged_layout_reservations(pool, (wrong,)):
                    group = [
                        e["data"]["group"]
                        for e in journal.events
                        if e["kind"] == "reservation-set-acquired"
                    ][-1]
                    raise OSError("controlled incomplete role generation")
        entered = False
        with self.assertRaisesRegex(ValueError, "canonical.*role|role.*descriptor"):
            with self.reopened() as (pool, _, original):
                candidate = plan_layout_control_recovery(
                    pool, (wrong,), reservation_group=group
                )
                with acquire_layout_recovery_controls(
                    pool,
                    candidate,
                    acknowledged_recovery_identity=candidate.identity,
                    allow_host_execution=True,
                ) as other:
                    raw = (*original, other)
                    plan = self.proposal(pool, raw)
                    with self.acquire(pool, raw, plan):
                        entered = True
        self.assertFalse(entered)
        self.assertTrue(pending.exists())

    def test_duplicate_raw_owner_never_mints_a_second_canonical_claim(self):
        self.retained()
        with self.reopened() as (pool, journal, raw):
            history = journal.events
            with self.assertRaisesRegex(ValueError, "actual same-producer"):
                roles.plan_recovered_layout_roles(self.project, pool, (raw[0], raw[0]))
            self.assertEqual(journal.events, history)
            raw[0].verify_all()

    def test_actual_other_project_cannot_borrow_original_project_controls(self):
        self.retained()
        other = self.root / "independent-project"
        shutil.copytree(self.project, other, symlinks=True)
        with self.reopened() as (pool, journal, raw):
            history = journal.events
            with self.assertRaisesRegex(ValueError, "actual project controls"):
                roles.plan_recovered_layout_roles(other, pool, raw)
            self.assertEqual(journal.events, history)

    def test_saved_handoff_dictionary_cannot_replace_actual_staged_owner(self):
        self.retained(finalized=True)
        with self.reopened() as (_, _, raw):
            with self.assertRaisesRegex(ValueError, "actual same-producer"):
                raw[0].relinquish_public_observations({"claimed": "new-control"})
            raw[0].verify_all()
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_actual_git_branch_change_uses_current_reference_writer_role(self):
        self.init_git()
        self.retained(finalized=True)
        self.git("symbolic-ref", "HEAD", "refs/heads/recovered")
        with self.reopened() as (pool, _, raw):
            plan = self.proposal(pool, raw)
            current = self.project / ".git/refs/heads/recovered.lock"
            self.assertIn(current, {target.path for target in plan.missing})
            with self.acquire(pool, raw, plan) as lease:
                self.assertTrue(lease.reservations.owns(current))
                self.assertEqual(
                    lease.git.files.references[-1].name, "refs/heads/recovered"
                )

    def test_mutation_of_old_control_during_new_set_publication_never_yields(self):
        self.retained(finalized=True)
        entered = False
        mutex = project_lifecycle_lock_path(self.project)
        with self.assertRaises(ValueError):
            with self.reopened() as (pool, journal, raw):
                plan = self.proposal(pool, raw)
                append = journal.append

                def changed(kind, content):
                    result = append(kind, content)
                    if kind == "reservation-set-acquired":
                        mutex.write_bytes(b"foreign original control mutation")
                    return result

                with mock.patch.object(journal, "append", side_effect=changed):
                    with self.acquire(pool, raw, plan):
                        entered = True
        self.assertFalse(entered)
        self.assertEqual(mutex.read_bytes(), b"foreign original control mutation")
        self.assertTrue(layout_pending_control_path(self.project).exists())
        self.assertTrue(all(m.descriptor == -1 for m in raw[0]._markers))

    def test_exact_canonical_grant_expires_before_any_incoming_fd_close(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, _, raw):
            plan = self.proposal(pool, raw)
            with self.acquire(pool, raw, plan) as lease:
                incoming = lease.reservations._incoming
                fds = [m.descriptor for m in incoming._markers]
                close = os.close
                observed = []

                def closing(fd):
                    close(fd)
                    if fd in fds:
                        observed.append(fd)
                        self.assertFalse(lease._active)
                        self.assertFalse(lease.reservations._active)

                patch = mock.patch.object(os, "close", side_effect=closing)
                patch.start()
                self.addCleanup(patch.stop)
            patch.stop()
            self.assertEqual(observed, list(reversed(fds)))
            raw[0].verify_all()

    def test_fork_does_not_inherit_canonical_role_rights_or_unlock_parent_mutex(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, _, raw):
            plan = self.proposal(pool, raw)
            with self.acquire(pool, raw, plan) as lease:
                child = os.fork()
                if child == 0:
                    try:
                        try:
                            lease.require_current()
                        except ValueError:
                            os._exit(0)
                        os._exit(2)
                    except BaseException:
                        os._exit(3)
                _, status = os.waitpid(child, 0)
                self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                lease.require_current()
                self.assertEqual(
                    self.probe_mutex(
                        project_lifecycle_lock_path(self.project)
                    ).returncode,
                    23,
                )

    def _late_initial_read_replacement(self, *, git_head):
        self.init_git()
        self.retained(finalized=True)
        path = self.project / (".git/HEAD" if git_head else "literate.project.json")
        saved = self.state / "actual-late-input"
        armed, changed, entered = False, False, False
        error = None
        try:
            with self.reopened() as (pool, journal, raw):
                plan = self.proposal(pool, raw)
                original_read = type(plan.seed).require_initial_inputs
                append = journal.append

                def appended(kind, content):
                    nonlocal armed
                    result = append(kind, content)
                    if kind == "recovery-canonical-roles-observed":
                        armed = True
                    return result

                def read_then_replace(seed):
                    nonlocal changed
                    result = original_read(seed)
                    if armed and not changed:
                        changed = True
                        path.rename(saved)
                        path.write_bytes(saved.read_bytes())
                    return result

                with (
                    mock.patch.object(journal, "append", side_effect=appended),
                    mock.patch.object(
                        type(plan.seed), "require_initial_inputs", read_then_replace
                    ),
                ):
                    with self.acquire(pool, raw, plan):
                        entered = True
        except ValueError as caught:
            error = caught
        self.assertTrue(changed, "last actual seed read was not reached")
        self.assertFalse(
            entered, "canonical role yield crossed actual input replacement"
        )
        self.assertIsNotNone(error)
        self.assertEqual(path.read_bytes(), saved.read_bytes())
        self.assertNotEqual(path.stat().st_ino, saved.stat().st_ino)
        self.assertTrue(layout_pending_control_path(self.project).exists())

    def test_final_initial_project_read_rejects_same_byte_manifest_replacement(self):
        self._late_initial_read_replacement(git_head=False)

    def test_final_initial_project_read_rejects_same_byte_git_head_replacement(self):
        self._late_initial_read_replacement(git_head=True)

    def test_actual_proposal_and_generic_catalog_cannot_construct_canonical_grant(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, journal, raw):
            plan = self.proposal(pool, raw)
            catalog = roles._RecoveryReservations(pool, raw)
            history = journal.events
            with self.assertRaisesRegex(ValueError, "factory|coverage"):
                lease = roles._RecoveryRoleLease(plan, catalog)
                lease.require_initial_inputs()
            self.assertFalse(layout_pending_control_path(self.project).exists())
            self.assertEqual(journal.events, history)

    def test_actual_factory_key_cannot_validate_missing_canonical_descriptor(self):
        self.retained(finalized=True)
        with self.reopened() as (pool, journal, raw):
            plan = self.proposal(pool, raw)
            catalog = roles._RecoveryReservations(pool, raw)
            history = journal.events
            # The actual retained descriptor catalogue still lacks the current
            # public pending marker. Check that coverage independently of the
            # earlier factory-lifetime refusal for a key-constructed lease.
            targets = tuple(dict.fromkeys(plan.seed.targets() + plan.git.targets()))
            with self.assertRaisesRegex(ValueError, "coverage"):
                catalog._require_coverage(targets, complete=True)
            lease = roles._RecoveryRoleLease(
                plan, catalog, _factory_key=roles._LEASE_KEY
            )
            with mock.patch.object(
                os, "fstat", side_effect=AssertionError("uncreated role borrowed FD")
            ):
                with self.assertRaisesRegex(
                    ValueError, "actual creating canonical recovery role"
                ):
                    lease.require_initial_inputs()
            self.assertFalse(layout_pending_control_path(self.project).exists())
            self.assertEqual(journal.events, history)

    def test_public_git_reassignment_cannot_waive_acknowledged_native_inputs(self):
        self.init_git()
        self.retained(finalized=True)
        with self.assertRaises(ValueError):
            with self.reopened() as (pool, _, raw):
                plan = self.proposal(pool, raw)
                with self.acquire(pool, raw, plan) as lease:
                    head = self.project / ".git/HEAD"
                    saved = self.state / "actual-original-head"
                    head.rename(saved)
                    head.write_bytes(saved.read_bytes())
                    # Real observed non-Git directory; no substitute native facts
                    # or private field edits. The acknowledged root still has Git.
                    lease.git = roles.observe_layout_git_controls(self.state)
                    with self.assertRaisesRegex(ValueError, "binding|Git"):
                        lease.require_current()
                    # Restore only the public reference. The foreign HEAD remains
                    # and context exit must refuse the actual changed native input.
                    lease.git = plan.git
        self.assertEqual(head.read_bytes(), saved.read_bytes())
        self.assertNotEqual(head.stat().st_ino, saved.stat().st_ino)

    def test_mid_validation_public_git_reassignment_cannot_waive_native_close(self):
        self.init_git()
        self.retained(finalized=True)
        changed = False
        with self.assertRaises(ValueError):
            with self.reopened() as (pool, _, raw):
                plan = self.proposal(pool, raw)
                with self.acquire(pool, raw, plan) as lease:
                    read = type(plan.seed).require_roles_current
                    calls = 0
                    head, saved = (
                        self.project / ".git/HEAD",
                        self.state / "actual-mid-head",
                    )

                    def read_then_reassign(seed):
                        nonlocal calls, changed
                        result = read(seed)
                        calls += 1
                        if calls == 2:
                            changed = True
                            head.rename(saved)
                            head.write_bytes(saved.read_bytes())
                            lease.git = roles.observe_layout_git_controls(self.state)
                        return result

                    with mock.patch.object(
                        type(plan.seed), "require_roles_current", read_then_reassign
                    ):
                        with self.assertRaisesRegex(ValueError, "binding|Git"):
                            lease.require_current()
                    lease.git = plan.git
        self.assertTrue(changed)
        self.assertEqual(head.read_bytes(), saved.read_bytes())
        self.assertNotEqual(head.stat().st_ino, saved.stat().st_ino)
