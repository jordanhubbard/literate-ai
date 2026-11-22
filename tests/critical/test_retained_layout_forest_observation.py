"""Actual fresh observation and recovered canonical locks, not source recovery.

The original phase remains refused. A separately acknowledged native dependency
runs under real normal canonical locks to retain genuine lease/publication records.
Fresh factories then reacquire those locks; no source phase/partition is fabricated.
"""

from __future__ import annotations

import copy
import inspect
import os
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_original_read as originals
from literate_ai.adapters import retained_layout_forest_control_read as incoming_reads
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_recovery_controls as controls
from literate_ai.adapters import retained_layout_recovery_roles as roles
from literate_ai.adapters.bounded_role_observation import current_role_observation
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_control_roles import (
    acquire_retained_layout_control_roles,
)
from literate_ai.adapters.retained_layout_effect_graph import _SourceEffectGraph
from literate_ai.adapters.retained_layout_forest_native import plan_native_forest
from literate_ai.adapters.retained_layout_forest_span import (
    _ForestSpan,
    _from_namespace,
)
from literate_ai.adapters.retained_layout_git_controls import _presence
from literate_ai.adapters.retained_layout_partition import (
    _lineage,
    capture_retained_layout_partition,
)
from literate_ai.adapters.retained_layout_recovery_data import _decode
from literate_ai.adapters.retained_layout_source_state import _read_original_state
from literate_ai.adapters.retained_layout_transaction import _native_tree


@unittest.skipUnless(os.name == "posix", "actual fresh canonical recovery locks")
class ForestObservationTests(unittest.TestCase):
    git = originals.ForestOriginalReadTests.git
    init_git = originals.ForestOriginalReadTests.init_git
    prepare = originals.ForestOriginalReadTests.prepare
    pool = originals.ForestOriginalReadTests.pool
    persist_guarded_root = originals.ForestOriginalReadTests.persist_guarded_root
    reopen = originals.ForestOriginalReadTests.reopen
    run_unmanaged = originals.ForestOriginalReadTests.run_unmanaged

    @classmethod
    def setUpClass(cls):
        originals.ForestOriginalReadTests.setUpClass.__func__(cls)

    def setUp(self):
        originals.ForestOriginalReadTests.setUp(self)
        self.fresh_budget = replace(
            self.input_budget,
            maximum_files=8192,
            maximum_entries=524288,
            maximum_total_bytes=256 * 1024**2,
        )
        self.fresh = self.state / "fresh-stages"
        self.fresh.mkdir(mode=0o700)

    def retain(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            saved = _read_original_state(
                journal,
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            )
            old_stages = self.state / "normal-stages"
            old_stages.mkdir(mode=0o700)
            with staged_layout_controls(old_stages, journal) as pool:
                with acquire_retained_layout_control_roles(self.project, pool) as owner:
                    self.targets = owner._seed.targets() + owner.git.targets()
                    tree = capture_retained_layout_partition(
                        self.project,
                        framework_files=tuple(
                            saved.document["namespace"]["census"]["framework_files"]
                        ),
                        budget=self.input_budget,
                        maximum_metadata_bytes=self.metadata_limit,
                    ).tree
                    original_dirs = set(
                        saved.document["namespace"]["census"]["tree"]["directories"]
                    )
                    graph = dict(_decode(saved.document["partition"]["graph"]))
                    graph.pop("schema")
                    graph = _SourceEffectGraph(**graph)
                    graph = replace(
                        graph,
                        fixed_directories=tuple(
                            sorted(
                                set(graph.fixed_directories)
                                | (set(tree.directories) - original_dirs)
                            )
                        ),
                    )
                    span = _ForestSpan(
                        (
                            _from_namespace(
                                tree, _native_tree(tree), _lineage(self.project)
                            ),
                        ),
                        self.input_budget,
                        self.metadata_limit,
                    )
                    program = plan_native_forest(
                        span,
                        graph,
                        self.parking,
                        source_phase_identity=self.saved_phase,
                    )
                    self.expected = self.run_unmanaged(journal, program)
                    owner.require_current()
        self.assertTrue((self.project / "litai/layout.pending").is_file())

    def observing(self, pool):
        return observation.observed_forest_recovery(
            pool,
            self.parking.parent,
            budget=self.fresh_budget,
            maximum_metadata_bytes=self.metadata_limit,
        )

    def test_actual_current_canonical_roles_are_reacquired_under_fresh_observation(
        self,
    ):
        self.retain()
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                with self.assertRaisesRegex(ValueError, "complete multi-carrier"):
                    controls.plan_layout_control_recovery(pool, self.targets)
                with self.observing(pool) as owner:
                    before = observation._record(owner)
                    self.assertIsNone(current_role_observation())
                    proposal = owner.plan_controls(self.targets)
                    with owner._reads():
                        with controls.acquire_layout_recovery_controls(
                            pool,
                            proposal,
                            acknowledged_recovery_identity=proposal.identity,
                            allow_host_execution=True,
                        ) as recovered:
                            recovered.verify_all()
                            role_plan = owner.plan_roles((recovered,))
                            with roles.acquire_recovered_layout_roles(
                                pool,
                                (recovered,),
                                role_plan,
                                acknowledged_recovery_identity=role_plan.identity,
                                allow_host_execution=True,
                            ) as current:
                                current.require_initial_inputs()
                                self.assertIs(
                                    roles._CREATED_ROLES[current][1],
                                    current.reservations,
                                )
                                self.assertTrue(
                                    all(
                                        current.reservations.owns(t.path)
                                        for t in self.targets
                                    )
                                )
                                self.assertIs(
                                    observation._record(owner).ledger, before.ledger
                                )
                                self.assertEqual(before.frontier.span, self.expected)
                    owner.require_current()
                with self.assertRaisesRegex(ValueError, "complete multi-carrier"):
                    controls.plan_layout_control_recovery(pool, self.targets)
        self.assertTrue((self.project / "retained/app.py").is_file())

    def test_actual_incoming_git_controls_advance_only_owned_absent_inputs(self):
        self.retain()
        self.init_git(commit=True)
        commit = self.git("rev-parse", "HEAD").stdout.decode().strip()
        reference = "refs/heads/incoming/deep/branch"
        self.git("symbolic-ref", "HEAD", reference)
        absent_ref = self.project / ".git" / reference
        self.assertFalse(absent_ref.parent.exists())
        unknown = self.project / "retained/foreign.txt"
        unknown.write_bytes(b"preserve unrelated current source\n")
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                with self.observing(pool) as owner:
                    original = observation._record(owner)
                    proposal = owner.plan_controls(self.targets)
                    with owner._reads():
                        with controls.acquire_layout_recovery_controls(
                            pool,
                            proposal,
                            acknowledged_recovery_identity=proposal.identity,
                            allow_host_execution=True,
                        ) as recovered:
                            role_plan = owner.plan_roles((recovered,))
                            self.assertTrue(role_plan.missing)
                            self.assertIn(
                                absent_ref.with_name("branch.lock"),
                                {t.path for t in role_plan.missing},
                            )
                            old_ref = original.ledger.cache[absent_ref]
                            old_anchor = original.ledger.ancestry[absent_ref]
                            self.assertIsNone(old_ref.content)
                            for target in role_plan.missing:
                                original.reader.file(
                                    target.path, optional=True, maximum_bytes=256
                                )
                                self.assertIsNone(_presence(target.path))
                            before = dict(original.ledger.cache)
                            with roles.acquire_recovered_layout_roles(
                                pool,
                                (recovered,),
                                role_plan,
                                acknowledged_recovery_identity=role_plan.identity,
                                allow_host_execution=True,
                            ) as current:
                                current.require_initial_inputs()
                                current.require_current()
                                self.assertIs(observation._record(owner), original)
                                self.assertIs(
                                    original.ledger.cache[absent_ref], old_ref
                                )
                                self.assertEqual(
                                    original.ledger.ancestry[absent_ref][0],
                                    absent_ref.parent,
                                )
                                self.assertNotEqual(
                                    original.ledger.ancestry[absent_ref], old_anchor
                                )
                                changed = {t.path for t in role_plan.missing}
                                for path, item in before.items():
                                    if path not in changed:
                                        self.assertIs(original.ledger.cache[path], item)
                                for target in role_plan.missing:
                                    self.assertTrue(
                                        current.reservations.owns(target.path)
                                    )
                                    self.assertTrue(
                                        original.ledger.cache[target.path].content
                                    )
                                blocked = self.git(
                                    "update-ref", reference, commit, check=False
                                )
                                self.assertNotEqual(blocked.returncode, 0)
                                self.assertIn(b"lock", blocked.stderr)
                                with mock.patch.object(
                                    os,
                                    "fstat",
                                    side_effect=AssertionError("borrowed FD"),
                                ):
                                    for key in (None, object()):
                                        with self.assertRaisesRegex(
                                            ValueError,
                                            "one actual canonical acquisition",
                                        ):
                                            incoming_reads.advance_incoming_control_reads(
                                                current, key
                                            )
                    owner.require_current()
        self.assertFalse(absent_ref.exists())
        self.assertEqual(unknown.read_bytes(), b"preserve unrelated current source\n")

    def _incoming_late_change(self, mode):
        self.retain()
        self.init_git(commit=True)
        self.git("symbolic-ref", "HEAD", "refs/heads/incoming/deep/branch")
        foreign = self.project / ".git/unrelated-observed-input"
        hit = []
        before = None
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                with self.assertRaisesRegex(
                    ValueError,
                    "original fresh forest read lifetime|input native facts|"
                    "source forest requires complete multi-carrier recovery",
                ):
                    with self.observing(pool) as owner:
                        original = observation._record(owner)
                        proposal = owner.plan_controls(self.targets)
                        with owner._reads():
                            original.reader.file(
                                foreign, optional=True, maximum_bytes=256
                            )
                            with controls.acquire_layout_recovery_controls(
                                pool,
                                proposal,
                                acknowledged_recovery_identity=proposal.identity,
                                allow_host_execution=True,
                            ) as recovered:
                                role_plan = owner.plan_roles((recovered,))
                                before = dict(original.ledger.cache)
                                anchors = dict(original.ledger.ancestry)
                                advance = incoming_reads.advance_incoming_control_reads

                                def controlled_transfer(lease, key):
                                    if mode == "parent":
                                        close = incoming_reads._close_reader

                                        def late_close(*args):
                                            close(*args)
                                            observation._POOLS.pop(pool)
                                            hit.append(True)

                                        with mock.patch.object(
                                            incoming_reads,
                                            "_close_reader",
                                            new=late_close,
                                        ):
                                            return advance(lease, key)
                                    incoming = lease.reservations._incoming
                                    close = incoming._close_marker_inputs

                                    def late_input():
                                        close()
                                        if (
                                            inspect.currentframe().f_back.f_code
                                            is advance.__code__
                                        ):
                                            self.assertFalse(hit)
                                            foreign.write_bytes(b"foreign late input\n")
                                            hit.append(True)

                                    with mock.patch.object(
                                        incoming,
                                        "_close_marker_inputs",
                                        new=late_input,
                                    ):
                                        return advance(lease, key)

                                with mock.patch.object(
                                    incoming_reads,
                                    "advance_incoming_control_reads",
                                    new=controlled_transfer,
                                ):
                                    with roles.acquire_recovered_layout_roles(
                                        pool,
                                        (recovered,),
                                        role_plan,
                                        acknowledged_recovery_identity=role_plan.identity,
                                        allow_host_execution=True,
                                    ):
                                        self.fail("late change yielded canonical roles")
                self.assertEqual(hit, [True], "late callback did not execute")
                self.assertIsNotNone(before)
                for path, item in before.items():
                    self.assertIs(original.ledger.cache[path], item)
                    self.assertEqual(original.ledger.ancestry[path], anchors[path])
        if mode == "input":
            self.assertEqual(foreign.read_bytes(), b"foreign late input\n")

    def test_incoming_parent_revoke_at_last_native_close_does_not_install_reads(self):
        self._incoming_late_change("parent")

    def test_incoming_late_foreign_input_is_preserved_without_advancing_reads(self):
        self._incoming_late_change("input")

    def test_copied_owner_and_changed_fresh_policy_refuse_before_native_access(self):
        self.retain()
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                with self.observing(pool) as owner:
                    fake = observation._ForestRecoveryObservation(observation._KEY)
                    with mock.patch.object(
                        os, "fstat", side_effect=AssertionError("borrowed FD")
                    ):
                        with self.assertRaisesRegex(ValueError, "lifetime|observation"):
                            fake.require_current()
                        value = observation._record(owner)
                        original = value.ledger.metadata
                        try:
                            value.ledger.metadata += 1
                            with self.assertRaisesRegex(
                                ValueError, "policy ended/changed"
                            ):
                                owner.require_current()
                        finally:
                            value.ledger.metadata = original
                    owner.require_current()

    def test_journal_policy_and_original_event_order_cannot_change(self):
        self.retain()
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                with self.observing(pool) as owner:
                    original = journal._budget.maximum_storage_bytes
                    events = tuple(journal._events)
                    try:
                        object.__setattr__(
                            journal._budget, "maximum_storage_bytes", original + 1
                        )
                        with mock.patch.object(
                            os, "fstat", side_effect=AssertionError("borrowed FD")
                        ):
                            with self.assertRaisesRegex(
                                ValueError, "policy ended/changed"
                            ):
                                owner.require_current()
                        object.__setattr__(
                            journal._budget, "maximum_storage_bytes", original
                        )
                        journal._events.reverse()
                        with mock.patch.object(
                            os, "fstat", side_effect=AssertionError("borrowed FD")
                        ):
                            with self.assertRaisesRegex(
                                ValueError, "descriptions or read activation"
                            ):
                                owner.require_current()
                    finally:
                        object.__setattr__(
                            journal._budget, "maximum_storage_bytes", original
                        )
                        journal._events[:] = events
                    owner.require_current()

    def test_ended_parent_revokes_retained_descriptor_roles_before_fd_access(self):
        self.retain()
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                parent = self.observing(pool)
                owner = parent.__enter__()
                resources = ExitStack()
                try:
                    proposal = owner.plan_controls(self.targets)
                    with owner._reads():
                        recovered = resources.enter_context(
                            controls.acquire_layout_recovery_controls(
                                pool,
                                proposal,
                                acknowledged_recovery_identity=proposal.identity,
                                allow_host_execution=True,
                            )
                        )
                        role_plan = owner.plan_roles((recovered,))
                        current = resources.enter_context(
                            roles.acquire_recovered_layout_roles(
                                pool,
                                (recovered,),
                                role_plan,
                                acknowledged_recovery_identity=role_plan.identity,
                                allow_host_execution=True,
                            )
                        )
                    descriptors = tuple(m.descriptor for m in recovered._markers)
                    parent.__exit__(None, None, None)
                    parent = None
                    with mock.patch.object(
                        os, "fstat", side_effect=AssertionError("ended FD")
                    ):
                        for check in (
                            owner.require_current,
                            recovered.verify_all,
                            current.require_current,
                        ):
                            with self.assertRaises(ValueError):
                                check()
                finally:
                    try:
                        resources.close()
                    except ValueError:
                        pass
                    if parent is not None:
                        parent.__exit__(None, None, None)
                self.assertNotIn(current, roles._CREATED_ROLES)
                for fd in descriptors:
                    with self.assertRaises(OSError):
                        os.fstat(fd)

    @contextmanager
    def acquired(self):
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                with self.observing(pool) as owner:
                    proposal = owner.plan_controls(self.targets)
                    with owner._reads():
                        with controls.acquire_layout_recovery_controls(
                            pool,
                            proposal,
                            acknowledged_recovery_identity=proposal.identity,
                            allow_host_execution=True,
                        ) as recovered:
                            plan = owner.plan_roles((recovered,))
                            with roles.acquire_recovered_layout_roles(
                                pool,
                                (recovered,),
                                plan,
                                acknowledged_recovery_identity=plan.identity,
                                allow_host_execution=True,
                            ) as current:
                                yield owner, current

    def test_replacement_project_role_cannot_skip_actual_canonical_validation(self):
        self.retain()
        with self.acquired() as (_owner, current):
            seed = current._seed

            class NoProjectValidation:
                def require_roles_current(self):
                    return self

                def require_initial_inputs(self):
                    return self

                def close_native_inputs(self):
                    pass

                def targets(self):
                    return seed.targets()

            try:
                current._seed = NoProjectValidation()
                with self.assertRaisesRegex(
                    ValueError, "creating canonical recovery role"
                ):
                    current.require_current()
                with mock.patch.object(
                    os, "fstat", side_effect=AssertionError("borrowed FD")
                ):
                    with self.assertRaisesRegex(
                        ValueError, "creating canonical recovery role"
                    ):
                        current.require_initial_inputs()
            finally:
                current._seed = seed
            current.require_current()

    def test_last_native_close_cannot_revoke_role_parent_or_store_unchecked(self):
        from literate_ai.adapters import component_lock_observation as stores

        self.retain()
        with self.acquired() as (owner, current):
            close = roles._close_dependency_facts
            for check in (current.require_current, current.require_initial_inputs):
                for table, key in (
                    (roles._CREATED_ROLES, current),
                    (controls._CREATED_RECOVERIES, current.reservations._recovered[0]),
                    (observation._POOLS, current._pool),
                    (stores._BOUND, owner),
                ):
                    original = table[key]
                    native = []
                    hit = []

                    def late_change(
                        pool,
                        roots,
                        *,
                        check=check,
                        table=table,
                        key=key,
                        hit=hit,
                        native=native,
                    ):
                        close(pool, roots)
                        if (
                            inspect.currentframe().f_back.f_code
                            is check.__func__.__code__
                        ):
                            table.pop(key)
                            hit.append(True)
                            patch = mock.patch.object(
                                os,
                                "fstat",
                                side_effect=AssertionError("FD after final revoke"),
                            )
                            patch.start()
                            native.append(patch)

                    try:
                        with (
                            self.subTest(method=check.__name__, table=id(table)),
                            mock.patch.object(
                                roles,
                                "_close_dependency_facts",
                                new=late_change,
                            ),
                        ):
                            with self.assertRaises(ValueError):
                                check()
                            self.assertEqual(hit, [True])
                    finally:
                        for patch in reversed(native):
                            patch.stop()
                        table[key] = original
                        self.assertEqual(
                            hit, [True], "late native callback was not reached"
                        )
            current.require_current()

    def test_copied_recovered_descriptor_owner_has_no_factory_rights(self):
        self.retain()
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                with self.observing(pool) as owner:
                    proposal = owner.plan_controls(self.targets)
                    with owner._reads():
                        with controls.acquire_layout_recovery_controls(
                            pool,
                            proposal,
                            acknowledged_recovery_identity=proposal.identity,
                            allow_host_execution=True,
                        ) as recovered:
                            copied = copy.copy(recovered)
                            with self.assertRaisesRegex(
                                ValueError, "actual creating recovered"
                            ):
                                copied.verify_all()
                            recovered.verify_all()

    def test_case_alias_private_pool_inside_project_is_refused(self):
        self.retain()
        alias = self.project.with_name(self.project.name.swapcase())
        if not alias.exists() or alias.stat().st_ino != self.project.stat().st_ino:
            self.skipTest("native filesystem has no case alias")
        inside = alias / "private-fixture"
        inside.mkdir(mode=0o700)
        with self.reopen() as journal:
            with staged_layout_controls(inside, journal) as pool:
                with self.assertRaisesRegex(ValueError, "physically overlaps"):
                    with self.observing(pool):
                        self.fail("in-project aliased pool admitted")

    def test_current_store_selection_is_genuine_and_expired_with_parent(self):
        self.retain()
        with self.reopen() as journal:
            with staged_layout_controls(self.fresh, journal) as pool:
                with self.observing(pool) as owner:
                    value = observation._record(owner)
                    selection = value.selection
                    with owner._reads():
                        selection.require_current()
                        with self.assertRaises((TypeError, ValueError)):
                            ComponentLockStore.observe_selection(owner, value.root)
                with mock.patch.object(
                    os, "fstat", side_effect=AssertionError("ended FD")
                ):
                    with self.assertRaises(ValueError):
                        selection.close_native()
