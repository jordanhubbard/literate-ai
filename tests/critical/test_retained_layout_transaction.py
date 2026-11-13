"""Real source effects under joined controls, never full relocation acceptance."""

from __future__ import annotations

import json
import os
import shutil
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_control_roles as fixtures
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(os.name == "posix", "POSIX transaction source phase")
class RetainedLayoutTransactionTests(unittest.TestCase):
    git = fixtures.RetainedLayoutControlRoleTests.git
    init_git = fixtures.RetainedLayoutControlRoleTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutControlRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutControlRoleTests.setUp(self)
        self.budget = RetainedCargoInputBudget(128, 256, 1024**2, 16 * 1024**2)
        self.source = self.project / "components/legacy-project-wrapper/implementation"
        self.destination = self.project / "retained"

    def plan(self):
        return transaction.plan_retained_layout_source_move(
            self.project, "retained", budget=self.budget
        )

    @contextmanager
    def pool(self, plan, *, binding=None):
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=canonical_json_bytes(
                plan.binding if binding is None else binding
            ),
            budget=LayoutJournalBudget(),
        ) as journal:
            with staged_layout_controls(self.state / "stages", journal) as pool:
                yield pool, journal

    def phase(self, plan, pool, **overrides):
        arguments = {
            "acknowledged_plan_identity": plan.identity,
            "allow_host_execution": True,
            **overrides,
        }
        return transaction.retained_layout_source_phase(plan, pool, **arguments)

    def test_plan_binds_actual_wrapper_initialization_and_prospective_metadata(self):
        before = sorted(
            str(path.relative_to(self.project)) for path in self.project.rglob("*")
        )
        plan = self.plan()
        self.assertEqual(plan.tree.exclusions, ())
        self.assertEqual(
            plan.layout.wrapper_component, "components/legacy-project-wrapper"
        )
        self.assertEqual(
            before,
            sorted(
                str(path.relative_to(self.project)) for path in self.project.rglob("*")
            ),
        )
        prospective = dict(plan.prospective)
        self.assertEqual(
            json.loads(prospective[transaction._LIFT])["state"],
            "requalification-required",
        )
        self.assertIn(b"LITAI_LEGACY := retained\n", prospective["litai.harness.mk"])
        self.assertFalse(self.destination.exists())

    def test_actual_move_keeps_modes_aliases_hardlinks_and_reports_metadata_pending(
        self,
    ):
        (self.source / "data").mkdir()
        payload = self.source / "data/tool"
        payload.write_bytes(b"original executable bytes\n")
        payload.chmod(0o755)
        os.link(payload, self.source / "second-name")
        (self.source / "alias").symlink_to("data/tool")
        (self.source / "directory-alias").symlink_to("data", target_is_directory=True)
        inode, root_inode = payload.stat().st_ino, self.source.stat().st_ino
        plan = self.plan()
        old_metadata = {item.path: item.content for item in plan.inputs}
        with self.pool(plan) as (pool, journal):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    result = phase.move_source()
                    self.assertEqual(result["state"], "source-moved-metadata-pending")
                    self.assertFalse(result["relocation_complete"])
            self.assertEqual(journal.events[-1]["kind"], "source-move-observed")
            intent = next(
                item["data"]
                for item in journal.events
                if item["kind"] == "source-move-intent"
            )
            self.assertEqual(len(intent["metadata"]), 3)
            self.assertEqual(
                journal.read_payload(intent["prepared_plan_digest"]),
                canonical_json_bytes(plan.document),
            )
            for item in intent["metadata"]:
                self.assertEqual(
                    journal.read_payload(item["prospective"]),
                    dict(plan.prospective)[item["path"]],
                )
            with self.assertRaisesRegex(ValueError, "ended"):
                phase.move_source()
        self.assertFalse(self.source.exists())
        self.assertEqual(self.destination.stat().st_ino, root_inode)
        self.assertEqual((self.destination / "data/tool").stat().st_ino, inode)
        self.assertEqual((self.destination / "second-name").stat().st_ino, inode)
        self.assertEqual((self.destination / "data/tool").stat().st_mode & 0o777, 0o755)
        self.assertEqual(os.readlink(self.destination / "alias"), "data/tool")
        self.assertEqual(os.readlink(self.destination / "directory-alias"), "data")
        for path, content in old_metadata.items():
            self.assertEqual(path.read_bytes() if path.exists() else None, content)
        self.assertTrue((self.project / ".literate/conversion-authority.lock").exists())

    def test_missing_ack_or_execution_permission_refuses_before_publication(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            for overrides in (
                {"acknowledged_plan_identity": None},
                {"allow_host_execution": False},
            ):
                with self.subTest(overrides=overrides):
                    with self.assertRaisesRegex(ValueError, "acknowledgement"):
                        with self.phase(plan, pool, **overrides):
                            self.fail("unauthorized source phase entered")
            self.assertEqual(journal.events, ())
        self.assertTrue(self.source.exists())

    def test_journal_binding_cannot_authorize_another_source_plan(self):
        plan = self.plan()
        with self.pool(plan, binding={}) as (pool, journal):
            with self.assertRaisesRegex(ValueError, "journal is not bound"):
                with self.phase(plan, pool):
                    self.fail("unbound journal gained source authority")
            self.assertEqual(journal.events, ())

    def test_changed_source_refuses_before_public_controls(self):
        plan = self.plan()
        (self.source / "app.py").write_bytes(b"changed source\n")
        with self.pool(plan) as (pool, journal):
            with self.assertRaises(ValueError):
                with self.phase(plan, pool):
                    self.fail("stale source phase accepted")
            self.assertEqual(journal.events, ())
        self.assertFalse(self.destination.exists())

    def test_changed_authored_wrapper_refuses_before_public_controls(self):
        plan = self.plan()
        wrapper = self.project / "litai.harness.mk"
        wrapper.write_bytes(wrapper.read_bytes() + b"# concurrent change\n")
        with self.pool(plan) as (pool, journal):
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                with self.phase(plan, pool):
                    self.fail("changed actual wrapper accepted")
            self.assertEqual(journal.events, ())

    def test_foreign_destination_is_preserved(self):
        plan = self.plan()
        self.destination.mkdir()
        foreign = self.destination / "foreign"
        foreign.write_bytes(b"foreign bytes")
        with self.pool(plan) as (pool, journal):
            with self.assertRaisesRegex(ValueError, "destination exists"):
                with self.phase(plan, pool):
                    self.fail("foreign destination accepted")
            self.assertEqual(journal.events, ())
        self.assertEqual(foreign.read_bytes(), b"foreign bytes")
        self.assertTrue(self.source.exists())

    def test_change_after_durable_intent_refuses_before_source_effect(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "source-move-intent":
                    (self.source / "app.py").write_bytes(b"late source bytes\n")
                return result

            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.move_source()
            self.assertEqual(journal.events[-1]["kind"], "source-move-intent")
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())

    def test_posteffect_failure_retains_moved_source_and_old_metadata(self):
        plan = self.plan()
        move = transaction.move_layout_entry_exclusive

        def interrupted(*args, **kwargs):
            move(*args, **kwargs)
            raise OSError("controlled interruption after actual native move")

        with self.pool(plan) as (pool, journal):
            with self.assertRaisesRegex(OSError, "controlled interruption"):
                with self.phase(plan, pool) as phase:
                    with mock.patch.object(
                        transaction,
                        "move_layout_entry_exclusive",
                        side_effect=interrupted,
                    ):
                        phase.move_source()
            self.assertEqual(journal.events[-1]["kind"], "source-move-intent")
        self.assertFalse(self.source.exists())
        self.assertEqual(
            (self.destination / "app.py").read_bytes(), b"print('retained')\n"
        )
        self.assertEqual(
            json.loads((self.project / transaction._LIFT).read_bytes())["state"],
            "passed",
        )

    def test_changed_moved_namespace_during_observation_refuses_and_keeps_foreign(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "source-move-observed":
                    (self.destination / "foreign").write_bytes(b"late foreign")
                return result

            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.move_source()
        self.assertEqual((self.destination / "foreign").read_bytes(), b"late foreign")

    def test_cross_boundary_hardlink_refuses_without_source_effect(self):
        os.link(self.source / "app.py", self.root / "outside")
        with self.assertRaisesRegex(ValueError, "hardlink"):
            self.plan()
        self.assertFalse(self.destination.exists())

    def test_root_cells_remain_required_and_public_success_is_unavailable(self):
        with self.assertRaisesRegex(ValueError, "mixed-partition"):
            transaction.plan_retained_layout_source_move(
                self.project, ".", budget=self.budget
            )

    def test_actual_git_index_writer_is_excluded_and_index_bytes_are_retained(self):
        self.init_git()
        self.git("add", self.source.relative_to(self.project).as_posix())
        index = self.project / ".git/index"
        before = index.read_bytes()
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    contender = self.git("add", ".", check=False)
                    self.assertNotEqual(contender.returncode, 0)
                    self.assertIn(b"index.lock", contender.stderr)
                    phase.move_source()
        self.assertEqual(index.read_bytes(), before)

    def test_late_root_ctime_change_is_not_accepted_as_rename_ctime(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "source-move-observed":
                    os.chmod(self.destination, self.destination.stat().st_mode)
                return result

            with self.assertRaisesRegex(ValueError, "native facts"):
                with self.phase(plan, pool) as phase:
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.move_source()
        self.assertTrue(self.destination.exists())

    def test_inherited_source_phase_cannot_move_while_parent_remains_live(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    child = os.fork()
                    if child == 0:
                        try:
                            phase.move_source()
                        except ValueError:
                            os._exit(0)
                        except BaseException:
                            os._exit(2)
                        os._exit(1)
                    _, status = os.waitpid(child, 0)
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                    self.assertTrue(self.source.exists())
                    phase.move_source()

    def test_private_stage_namespace_inside_source_refuses_before_controls(self):
        state = self.source / "state"
        state.mkdir(mode=0o700)
        stages = state / "stages"
        stages.mkdir(mode=0o700)
        plan = self.plan()
        with retained_layout_journal(
            state / "journal",
            canonical_binding=canonical_json_bytes(plan.binding),
            budget=LayoutJournalBudget(),
        ) as journal:
            with staged_layout_controls(stages, journal) as pool:
                with self.assertRaisesRegex(ValueError, "overlap retained source"):
                    with self.phase(plan, pool):
                        self.fail("private state would move with retained source")
                self.assertEqual(journal.events, ())

    def test_replaced_plan_cannot_select_destination_outside_actual_project(self):
        plan = replace(
            self.plan(),
            destination=self.root / "outside-project",
            destination_lineage=transaction._lineage(self.root),
            destination_parent=transaction.layout_entry_node(self.root),
        )
        with self.pool(plan) as (pool, journal):
            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    self.fail("replaced plan moved source outside actual project")
            self.assertEqual(journal.events, ())
        self.assertTrue(self.source.exists())

    def test_replaced_plan_cannot_claim_unrelated_source_as_selected_layout(self):
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        (unrelated / "original").write_bytes(b"unrelated source")
        tree = transaction.capture_retained_cargo_tree_v2(unrelated, budget=self.budget)
        plan = replace(
            self.plan(),
            tree=tree,
            native=transaction._native_tree(tree),
            source_node=transaction.layout_entry_node(unrelated),
            source_parent=transaction.layout_entry_node(self.root),
        )
        with self.pool(plan) as (pool, journal):
            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    self.fail("replaced plan moved unrelated source")
            self.assertEqual(journal.events, ())
        self.assertEqual((unrelated / "original").read_bytes(), b"unrelated source")

    def test_replaced_plan_cannot_supply_arbitrary_prospective_authority(self):
        plan = self.plan()
        plan = replace(
            plan,
            prospective=(
                (transaction.RETAINED_LAYOUT_PATH, b"arbitrary"),
                *plan.prospective[1:],
            ),
        )
        with self.pool(plan) as (pool, journal):
            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    self.fail("replaced plan bound arbitrary prospective metadata")
            self.assertEqual(journal.events, ())
        self.assertTrue(self.source.exists())

    def test_prior_logical_layout_identity_is_portable_across_physical_copies(self):
        original = dict(self.plan().prospective)[transaction.RETAINED_LAYOUT_PATH]
        copied = self.root / "copied-project"
        shutil.copytree(self.project, copied, symlinks=True)
        plan = transaction.plan_retained_layout_source_move(
            copied, "retained", budget=self.budget
        )
        other = dict(plan.prospective)[transaction.RETAINED_LAYOUT_PATH]
        self.assertEqual(json.loads(original)["lineage"], json.loads(other)["lineage"])

    def test_case_aliased_private_stage_is_refused_by_actual_directory_identity(self):
        stages = self.source / "private-stages"
        stages.mkdir(mode=0o700)
        alias = self.source.with_name(self.source.name.upper()) / stages.name
        if not alias.exists() or not os.path.samefile(alias, stages):
            self.skipTest("actual case-insensitive filesystem required")
        plan = self.plan()
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=canonical_json_bytes(plan.binding),
            budget=LayoutJournalBudget(),
        ) as journal:
            with staged_layout_controls(alias, journal) as pool:
                self.assertFalse(pool.root.is_relative_to(plan.tree.root))
                with self.assertRaisesRegex(ValueError, "overlap retained source"):
                    with self.phase(plan, pool):
                        self.fail(
                            "physical private stage alias gained source-phase authority"
                        )
                self.assertEqual(journal.events, ())

    def test_changed_original_destination_ancestry_refuses_after_observation(self):
        outer = self.project / "outer"
        (outer / "inner").mkdir(parents=True)
        plan = transaction.plan_retained_layout_source_move(
            self.project, "outer/inner/retained", budget=self.budget
        )
        displaced = self.project / "original-outer"
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "source-move-observed":
                    outer.rename(displaced)
                    outer.mkdir()
                    (displaced / "inner").rename(outer / "inner")
                return result

            with self.assertRaisesRegex(ValueError, "ancestry"):
                with self.phase(plan, pool) as phase:
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.move_source()
                    self.fail("changed destination ancestry returned pending success")
        self.assertTrue((plan.destination / "app.py").is_file())
        self.assertTrue(displaced.is_dir())

    def test_case_aliased_git_administration_never_receives_source(self):
        self.init_git()
        alias = self.project / ".GIT"
        if not alias.is_dir() or not os.path.samefile(alias, self.project / ".git"):
            self.skipTest("actual case-insensitive filesystem required")
        with self.assertRaises(ValueError):
            plan = transaction.plan_retained_layout_source_move(
                self.project, ".GIT/retained", budget=self.budget
            )
            with self.pool(plan) as (pool, _):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    self.fail(
                        "source moved into case-aliased actual Git administration"
                    )
        self.assertTrue(self.source.exists())
        self.assertFalse((alias / "retained").exists())

    def test_case_aliased_source_descendant_refuses_during_plan(self):
        (self.source / "nested").mkdir()
        alias = self.source.with_name(self.source.name.upper()) / "nested"
        if not alias.is_dir() or not os.path.samefile(alias, self.source / "nested"):
            self.skipTest("actual case-insensitive filesystem required")
        coordinate = (alias / "retained").relative_to(self.project).as_posix()
        with self.assertRaisesRegex(ValueError, "source|overlap"):
            transaction.plan_retained_layout_source_move(
                self.project, coordinate, budget=self.budget
            )
