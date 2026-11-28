"""Real acknowledged restoration under fresh raw and canonical descriptors.

Original forest admission still genuinely refuses. Unmanaged original native and
metadata dependencies plus real normal control finalization provide interrupted
inputs. The recovery owner itself requires actual fresh roles and explicit ack.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import os
import stat
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_forest_control_projection as fixtures
from literate_ai.adapters import exclusive_entry
from literate_ai.adapters import retained_layout_forest_observation as observation
from literate_ai.adapters import retained_layout_forest_recovery as recovery
from literate_ai.adapters import retained_layout_recovery_roles as role_owners
from literate_ai.adapters.exclusive_entry import layout_entry_node
from literate_ai.adapters.retained_layout_journal import LayoutJournalBudget
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.contracts.identity import canonical_identity


@unittest.skipUnless(os.name == "posix", "actual acknowledged forest restoration")
class ForestRecoveryTests(unittest.TestCase):
    git = fixtures.ForestControlProjectionTests.git
    init_git = fixtures.ForestControlProjectionTests.init_git
    prepare = fixtures.ForestControlProjectionTests.prepare
    persist_guarded_root = fixtures.ForestControlProjectionTests.persist_guarded_root
    reopen = fixtures.ForestControlProjectionTests.reopen
    acquired = fixtures.ForestControlProjectionTests.acquired
    observing = fixtures.ForestControlProjectionTests.observing
    retain = fixtures.ForestControlProjectionTests.retain
    run_unmanaged = fixtures.ForestControlProjectionTests.run_unmanaged

    @classmethod
    def setUpClass(cls):
        fixtures.ForestControlProjectionTests.setUpClass.__func__(cls)

    def pool(self, plan):
        # Declared before the original journal is created and persisted. Fresh
        # recovery never changes the immutable producer policy.
        return fixtures.ForestControlProjectionTests.pool(
            self, plan, budget=self.journal_budget
        )

    def setUp(self):
        fixtures.ForestControlProjectionTests.setUp(self)
        # A separate explicit finite fresh-effects policy, declared before the
        # observer exists. Original preparation policy remains untouched.
        self.fresh_budget = replace(
            self.fresh_budget,
            maximum_files=65536,
            maximum_entries=4000000,
            maximum_total_bytes=2 * 1024**3,
        )
        self.fresh_metadata_limit = 16 * 1024**3
        self.journal_budget = LayoutJournalBudget(256, 1024**2, 16 * 1024**2, 32)
        self.quarantine = self.state / "data-quarantine"
        self.quarantine.mkdir(mode=0o700)

    def test_actual_acknowledged_inverse_restores_data_and_preserves_controls(
        self,
    ):
        carried = self.project / "carried-data"
        carried.mkdir()
        (carried / "payload.bin").write_bytes(b"cross-carrier native payload\0\r\n")
        os.link(carried / "payload.bin", self.project / "peer.bin")
        (self.project / "literal-link").symlink_to("carried-data/payload.bin")
        (self.project / "empty-kept").mkdir()
        self.retain()
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            original = value.program.span.roots[0]
            controls = {t.path for t in self.targets}
            plan = recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertTrue(plan.actions)
            self.assertFalse(plan.committed)
            before_journal = tuple(value.journal._events)
            with self.assertRaisesRegex(ValueError, "acknowledgement"):
                recovery.apply_forest_data_recovery(
                    owner,
                    current,
                    plan,
                    acknowledged_recovery_identity=canonical_identity({"wrong": True}),
                    allow_host_execution=True,
                )
            self.assertEqual(tuple(value.journal._events), before_journal)
            with self.assertRaisesRegex(ValueError, "creating forest recovery plan"):
                with mock.patch.object(
                    os, "fstat", side_effect=AssertionError("borrowed FD")
                ):
                    recovery.apply_forest_data_recovery(
                        owner,
                        current,
                        copy.copy(plan),
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
            actual_append = value.journal.append
            actual_move = recovery.move_layout_entry_exclusive
            entered = []

            def append(kind, raw):
                if (
                    kind == "forest-data-recovery-entry-intent"
                    and "read" not in entered
                ):
                    entered.append("read")
                    effect = next(iter(recovery._LIVE))
                    with mock.patch.object(
                        os, "fstat", side_effect=AssertionError("borrowed reentrant FD")
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "reentrant recovery workspace"
                        ):
                            effect._verify(object())
                        with self.assertRaisesRegex(
                            ValueError, "reentrant recovery event"
                        ):
                            effect._emit("intent")
                return actual_append(kind, raw)

            def move(*args, **kwargs):
                if "move" not in entered:
                    entered.append("move")
                    effect = next(iter(recovery._LIVE))
                    action = recovery._DISPATCH[effect][2]
                    before = tuple(value.journal._events)
                    with mock.patch.object(
                        os, "fstat", side_effect=AssertionError("borrowed reentrant FD")
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "reentrant recovery action"
                        ):
                            recovery._dispatch(effect, "move", action)
                        with self.assertRaisesRegex(
                            ValueError, "registered recovery substep"
                        ):
                            effect._move(action)
                        with self.assertRaisesRegex(
                            ValueError, "registered recovery event"
                        ):
                            effect._append(object())
                        coupons = recovery._PROGRESS[effect][2]
                        with self.assertRaisesRegex(
                            ValueError, "registered recovery event"
                        ):
                            effect._verify(None)
                        self.assertEqual(recovery._PROGRESS[effect][2], coupons)
                    self.assertEqual(tuple(value.journal._events), before)
                return actual_move(*args, **kwargs)

            with (
                mock.patch.object(value.journal, "append", append),
                mock.patch.object(recovery, "move_layout_entry_exclusive", move),
            ):
                result = recovery.apply_forest_data_recovery(
                    owner,
                    current,
                    plan,
                    acknowledged_recovery_identity=plan.identity,
                    allow_host_execution=True,
                )
            self.assertEqual(entered, ["read", "move"])
            self.assertTrue(result["data_verified"])
            self.assertFalse(result["controls_released"])
            self.assertFalse(result["internal_recovery_complete"])
            for name, blob, _executable in original.payloads:
                path = original.root / name
                if path in controls:
                    continue
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(), blob.digest, name
                )
            before = dict(original.native)
            after = dict(result["span"].roots[0].native)
            self.assertEqual(set(after), set(before))
            for name, target in original.links:
                self.assertEqual(os.readlink(original.root / name), target)
            for name, node in before.items():
                if original.root / name in controls:
                    continue
                self.assertEqual(
                    after[name].directory_identity
                    if stat.S_ISDIR(node.mode)
                    else after[name].after_rename(),
                    node.directory_identity
                    if stat.S_ISDIR(node.mode)
                    else replace(
                        node, link_target=dict(original.links).get(name)
                    ).after_rename(),
                    name,
                )
            self.assertEqual(self.retired.read_bytes(), self.retired_content)
            self.assertEqual(layout_entry_node(self.retired), self.retired_node)
            self.assertEqual(self.normalized.read_bytes(), b"\0")
            self.assertTrue(self.retired_source.is_file())
            self.assertEqual(len(tuple(self.quarantine.iterdir())), 3)
            current.require_current()
            self.assertNotIn(plan, recovery._PREPARED)
            self.assertFalse(recovery._LIVE)
            self.assertFalse(recovery._PROGRESS)
            self.assertFalse(recovery._RECEIPTS)
            self.assertFalse(recovery._READING)
            self.assertFalse(recovery._WRITES)
            self.assertFalse(recovery._DISPATCH)
            self.assertFalse(recovery._SCHEDULE)
            self.assertFalse(recovery._OBSERVED)

    def test_incompatible_named_source_facts_refuse_before_recovery_intent(self):
        self.retain()
        source = self.project / "retained/app.py"
        before = layout_entry_node(source)
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            value.reader.file(source, maximum_bytes=before.size)
            prior = tuple(value.journal._events)
            with self.assertRaisesRegex(ValueError, "reader facts.*receipt-transfer"):
                recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertEqual(tuple(value.journal._events), prior)
            self.assertEqual(layout_entry_node(source), before)
            self.assertTrue(value.ledger.cache[source].content)
        self.assertEqual(tuple(self.quarantine.iterdir()), ())

    def test_complete_journal_preflight_keeps_original_policy_and_all_nodes(self):
        self.journal_budget = LayoutJournalBudget(128, 1024**2, 8 * 1024**2, 32)
        self.retain()
        source = self.project / "retained/app.py"
        before = layout_entry_node(source)
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            prior = tuple(value.journal._events)
            with self.assertRaisesRegex(ValueError, "complete recovery journal"):
                recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertEqual(tuple(value.journal._events), prior)
            self.assertEqual(value.journal._budget, self.journal_budget)
        self.assertEqual(layout_entry_node(source), before)
        self.assertEqual(tuple(self.quarantine.iterdir()), ())

    def test_same_observer_retry_checks_current_journal_before_source_access(self):
        self.retain()
        source = self.project / "retained/app.py"
        before = layout_entry_node(source)

        class Stopped(Exception):
            pass

        with self.acquired() as (owner, current):
            value = observation._record(owner)
            plan = recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            with mock.patch.object(recovery._Effect, "_move", side_effect=Stopped):
                with self.assertRaises(Stopped):
                    recovery.apply_forest_data_recovery(
                        owner,
                        current,
                        plan,
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
            self.assertFalse(
                any(
                    e["kind"].startswith("forest-data-recovery-")
                    for e in value.saved.events
                )
            )
            self.assertEqual(
                value.journal.events[-1]["kind"], "forest-data-recovery-intent"
            )
            with mock.patch.object(
                recovery,
                "observe_current_native_forest",
                side_effect=AssertionError("source observation before retry guard"),
            ):
                with self.assertRaisesRegex(ValueError, "fresh recovery-prefix replay"):
                    recovery.plan_forest_data_recovery(owner, current, self.quarantine)
        self.assertEqual(layout_entry_node(source), before)
        self.assertEqual(tuple(self.quarantine.iterdir()), ())

    def test_revoked_roles_at_final_native_precheck_refuse_before_rename(self):
        self.retain()
        hit = []
        real_stat = os.stat
        native_code = exclusive_entry.move_layout_entry_exclusive.__code__
        with self.assertRaisesRegex(
            ValueError, "actual creating canonical recovery role"
        ):
            with self.acquired() as (owner, current):
                plan = recovery.plan_forest_data_recovery(
                    owner, current, self.quarantine
                )
                action = plan.actions[0]
                source = plan.span.roots[action.source_area].root / action.source
                before = layout_entry_node(source)

                def stat_at(path, *args, **kwargs):
                    value = real_stat(path, *args, **kwargs)
                    frame = inspect.currentframe().f_back
                    if (
                        frame.f_code is native_code
                        and path == source.name
                        and kwargs.get("dir_fd") is not None
                        and kwargs.get("follow_symlinks") is False
                    ):
                        hit.append(True)
                        role_owners._CREATED_ROLES.pop(current)
                    return value

                with (
                    mock.patch.object(os, "stat", stat_at),
                    mock.patch.object(
                        exclusive_entry,
                        "_native_rename",
                        side_effect=AssertionError("rename after revoked roles"),
                    ),
                ):
                    recovery.apply_forest_data_recovery(
                        owner,
                        current,
                        plan,
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
        self.assertEqual(hit, [True], "actual last primitive precheck was not reached")
        self.assertEqual(layout_entry_node(source), before)
        self.assertEqual(tuple(self.quarantine.iterdir()), ())
        self.assertFalse(recovery._LIVE)
        self.assertFalse(recovery._READING)

    def test_journal_callback_cannot_change_source_after_payload_validation(self):
        self.retain()
        foreign = self.project / "retained/foreign-source.txt"
        hit = []
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            plan = recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            actual_append = value.journal.append

            def append(kind, raw):
                result = actual_append(kind, raw)
                if kind == "forest-data-recovery-entry-intent" and not hit:
                    hit.append(True)
                    foreign.write_bytes(b"preserve concurrent source\n")
                return result

            with (
                mock.patch.object(value.journal, "append", append),
                mock.patch.object(
                    exclusive_entry,
                    "_native_rename",
                    side_effect=AssertionError("rename after foreign source"),
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError, "runtime native|runtime directory"
                ):
                    recovery.apply_forest_data_recovery(
                        owner,
                        current,
                        plan,
                        acknowledged_recovery_identity=plan.identity,
                        allow_host_execution=True,
                    )
        self.assertEqual(hit, [True])
        self.assertEqual(foreign.read_bytes(), b"preserve concurrent source\n")
        self.assertEqual(tuple(self.quarantine.iterdir()), ())

    def test_directory_alias_ancestry_refuses_before_any_recovery_intent(self):
        payload = self.project / "observer-dir/payload.bin"
        payload.parent.mkdir()
        payload.write_bytes(b"original directory carrier\n")
        self.retain()
        canonical = self.project / "retained/observer-dir"
        alias = self.project / "RETAINED/OBSERVER-DIR"
        if not alias.is_dir():
            self.skipTest("native directory case alias is unavailable")
        self.assertEqual(alias.stat().st_ino, canonical.stat().st_ino)
        before = layout_entry_node(canonical / "payload.bin")
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            _lineage(alias)
            prior = tuple(value.journal._events)
            # Keep the predecessor lexical comparison to prove the independent
            # actual native ancestry check, rather than the portable spelling guard.
            with mock.patch.object(
                recovery,
                "_portable_beneath",
                lambda path, parent: path == parent or path.is_relative_to(parent),
            ):
                with self.assertRaisesRegex(ValueError, "reader directory ancestry"):
                    recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertEqual(tuple(value.journal._events), prior)
        self.assertEqual(layout_entry_node(canonical / "payload.bin"), before)
        self.assertEqual(tuple(self.quarantine.iterdir()), ())

    def test_last_planning_callback_cannot_extend_acknowledged_journal_prefix(self):
        self.retain()
        hit = []
        plan_code = recovery.plan_forest_data_recovery.__code__
        with self.acquired() as (owner, current):
            value = observation._record(owner)
            actual = current.require_current

            def closing():
                actual()
                if inspect.currentframe().f_back.f_code is plan_code:
                    hit.append(True)
                    value.journal.append(
                        "forest-data-recovery-intent", b'{"fixture":"late callback"}'
                    )

            with mock.patch.object(current, "require_current", closing):
                with self.assertRaisesRegex(
                    ValueError, "planning journal prefix changed"
                ):
                    recovery.plan_forest_data_recovery(owner, current, self.quarantine)
            self.assertEqual(
                hit, [True], "actual final planning callback was not reached"
            )
            self.assertEqual(
                value.journal.events[-1]["data"], {"fixture": "late callback"}
            )
        self.assertEqual(tuple(self.quarantine.iterdir()), ())
