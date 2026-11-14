"""Real prepared control/partition admission; unfinished effects stay refused."""

from __future__ import annotations

import copy
import os
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

import tests.critical.test_catalog_copy_roles as catalog_fixtures
import tests.critical.test_retained_layout_ownership as fixtures
from literate_ai.adapters import bounded_role_observation as reads
from literate_ai.adapters import framework_update_roles as updates
from literate_ai.adapters import project_initialization
from literate_ai.adapters import repository_refresh as refresh
from literate_ai.adapters import retained_layout_git_controls as git_controls
from literate_ai.adapters import retained_layout_source_admission as admission
from literate_ai.adapters import retained_layout_source_preparation as preparation
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


@unittest.skipUnless(os.name == "posix", "actual POSIX descriptor admission")
class SourceAdmissionTests(unittest.TestCase):
    git = fixtures.RetainedLayoutOwnershipTests.git
    init_git = fixtures.RetainedLayoutOwnershipTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutOwnershipTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutOwnershipTests.setUp(self)
        self.input_budget = RetainedCargoInputBudget(
            4096, 65536, 4 * 1024**2, 128 * 1024**2
        )
        self.metadata_limit = 4 * 1024**3

    def prepare(self):
        return preparation.prepared_retained_layout_source_move(
            self.project,
            "retained",
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
        )

    @contextmanager
    def pool(self, plan, *, budget=None):
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=canonical_json_bytes(plan.binding),
            budget=budget or LayoutJournalBudget(128, 1024**2, 8 * 1024**2, 32),
        ) as journal:
            with staged_layout_controls(self.state / "stages", journal) as pool:
                yield pool, journal

    @contextmanager
    def inspecting(self, *, before_admission=None):
        completed = False
        try:
            with self.prepare() as owner:
                if before_admission is not None:
                    before_admission(owner)
                with self.pool(owner.plan) as (pool, journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        yield owner, phase, pool, journal
                        completed = True
        except ValueError as error:
            if completed and "source phase remains incomplete" in str(error):
                return
            raise
        self.fail("inspection unexpectedly finalized the unfinished source phase")

    def test_actual_controls_reuse_original_reader_and_close_current_inputs(self):
        self.init_git(commit=True)

        def observe_original_absence(owner):
            path = owner.plan.git.targets()[0].path
            with owner._reads():
                self.assertIsNone(
                    refresh._file(path, optional=True, maximum_bytes=256).content
                )
                self.assertIsNone(git_controls._presence(path))

        with self.inspecting(before_admission=observe_original_absence) as (
            owner,
            phase,
            pool,
            _journal,
        ):
            original = preparation._state(owner)
            record = admission._phase_record(phase)
            self.assertIs(record.original, original)
            self.assertIs(record.pool, pool)
            self.assertTrue(record.history)
            self.assertIsNone(reads.current_role_observation())
            before = owner.usage
            owner.require_current()
            self.assertIs(preparation._state(owner).reader, original.reader)
            self.assertGreaterEqual(owner.usage["entries"], before["entries"])
            self.assertFalse(self.destination.exists())
        self.assertFalse(phase._active)
        self.assertFalse(original.reader._active)

    def test_complete_partition_uses_original_allowance_and_preserves_unknowns(self):
        unknown = self.project / "unclaimed-neighbor"
        unknown.write_bytes(b"unclaimed\n")
        with self.inspecting() as (owner, phase, _pool, _journal):
            before = owner.usage
            with phase.complete_partition(
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            ) as partition:
                self.assertEqual(
                    dict(partition.roles)["unclaimed-neighbor"], "unclaimed"
                )
                self.assertEqual(
                    dict(partition.roles)["literate.project.json"], "framework"
                )
                self.assertEqual(
                    dict(partition.roles)["litai/layout.pending"], "control"
                )
                self.assertGreater(owner.usage["files"], before["files"])
                self.assertIs(
                    admission._phase_record(phase).partition_binding[0],
                    partition.census,
                )
                self.assertEqual(partition.census.tree.exclusions, ())
                self.assertIsNone(reads.current_role_observation())
                partition.require_current()
        self.assertEqual(unknown.read_bytes(), b"unclaimed\n")

    def test_new_partition_policy_cannot_restore_spent_allowance(self):
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with self.assertRaisesRegex(ValueError, "original preparation policy"):
                with phase.complete_partition(
                    budget=replace(self.input_budget, maximum_entries=65537),
                    maximum_metadata_bytes=self.metadata_limit,
                ):
                    self.fail("new quota admitted")

    def test_public_and_control_effects_remain_guarded_before_transition_owner(self):
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with self.assertRaisesRegex(ValueError, "actual complete partition"):
                phase.move_source()
            for operation in (
                lambda: phase.publish_metadata(self.metadata),
                lambda: phase.finalize_controls(self.retired),
                lambda: phase.controls.reservations.begin_finalization(self.retired),
            ):
                with self.subTest(operation=operation):
                    with self.assertRaisesRegex(ValueError, "verified transition"):
                        operation()
            self.assertFalse(phase._attempted)
            self.assertFalse(self.destination.exists())

    def test_actual_movement_consumes_partition_and_retains_original_reader(self):
        from literate_ai.adapters import retained_layout_source_movement as movement

        unknown = self.project / "unclaimed-neighbor"
        unknown.write_bytes(b"preserved\n")
        (self.source / "alias-source.txt").write_bytes(b"original hardlink group\n")
        os.link(self.source / "alias-source.txt", self.source / "alias-copy.txt")
        (self.source / "app-link").symlink_to("app.py")
        original_bytes = (self.source / "app.py").read_bytes()
        with self.inspecting() as (owner, phase, _pool, _journal):
            original = preparation._state(owner)
            with owner._reads():
                refresh._file(self.source / "app.py")
                git_controls._presence(self.source)
            before = owner.usage
            with phase.complete_partition(
                budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
            ) as partition:
                with self.assertRaisesRegex(ValueError, "movement partition"):
                    partition._consume()
                result = phase.move_source()
                self.assertEqual(result["state"], "source-moved-metadata-pending")
                self.assertTrue(partition._spent)
                with self.assertRaises(ValueError):
                    partition.require_current()
                owner.require_current()
                self.assertIs(preparation._state(owner).reader, original.reader)
                self.assertGreater(
                    owner.usage["payload_bytes"], before["payload_bytes"]
                )
                with self.assertRaisesRegex(ValueError, "already attempted"):
                    phase.move_source()
            owner.require_current()
            self.assertFalse(self.source.exists())
            self.assertEqual((self.destination / "app.py").read_bytes(), original_bytes)
            self.assertEqual(unknown.read_bytes(), b"preserved\n")
            self.assertTrue(
                (self.destination / "alias-copy.txt").samefile(
                    self.destination / "alias-source.txt"
                )
            )
            self.assertEqual(os.readlink(self.destination / "app-link"), "app.py")
            self.assertIsNone(reads.current_role_observation())
            with self.assertRaisesRegex(ValueError, "verified transition"):
                phase.publish_metadata(self.metadata)
        self.assertNotIn(phase, movement._MOVES)
        self.assertFalse(original.reader._active)
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_foreign_namespace_inserted_during_actual_move_refuses(self):
        move = transaction.move_layout_entry_exclusive
        foreign = self.project / "foreign-during-source-move"

        def insert(source, destination, **kwargs):
            result = move(source, destination, **kwargs)
            if source == self.source:
                foreign.write_bytes(b"foreign\n")
            return result

        with self.assertRaisesRegex(ValueError, "native namespace"):
            with self.inspecting() as (_owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ):
                    with mock.patch.object(
                        transaction, "move_layout_entry_exclusive", insert
                    ):
                        phase.move_source()
        self.assertEqual(foreign.read_bytes(), b"foreign\n")
        self.assertTrue(self.destination.exists())
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_observed_destination_absences_advance_from_actual_source_move(self):
        def observe_destination(owner):
            with owner._reads():
                self.assertIsNone(
                    refresh._file(self.destination / "app.py", optional=True).content
                )
                self.assertIsNone(git_controls._presence(self.destination / "app.py"))

        with self.inspecting(before_admission=observe_destination) as (
            owner,
            phase,
            _pool,
            _journal,
        ):
            with phase.complete_partition(
                budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
            ):
                phase.move_source()
                owner.require_current()
            self.assertTrue((self.destination / "app.py").exists())

    def test_all_mapped_lineage_reservations_precede_actual_movement(self):
        reserve = reads._RoleObservation.reserve_lineage
        with self.inspecting() as (owner, phase, _pool, _journal):
            reader = preparation._state(owner).reader

            def check(actual, path):
                if (
                    actual is reader
                    and path.is_relative_to(self.destination)
                    and path not in reader._lineage_allowances
                ):
                    self.assertFalse(
                        phase._attempted, "fresh lineage debit after movement intent"
                    )
                return reserve(actual, path)

            with phase.complete_partition(
                budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
            ):
                with mock.patch.object(
                    reads._RoleObservation, "reserve_lineage", check
                ):
                    phase.move_source()

    def test_preparation_end_during_last_native_callback_revokes_currentness(self):
        closed, rejected = [], []
        close = transaction._close_tree
        descriptor = None
        try:
            with self.inspecting() as (owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ):
                    phase.move_source()
                descriptor = phase.controls.reservations._markers[0].descriptor

                def end(*args, **kwargs):
                    result = close(*args, **kwargs)
                    if kwargs.get("_admitted_source_phase") is phase and not closed:
                        closed.append(True)
                        preparation._LIVE.pop(owner)
                    return result

                with mock.patch.object(transaction, "_close_tree", end):
                    try:
                        owner.require_current()
                    except ValueError:
                        rejected.append(True)
        except ValueError:
            pass  # Ended preparation also refuses its enclosing cleanup reads.
        self.assertEqual(closed, [True])
        self.assertEqual(rejected, [True])
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def test_activation_teardown_cannot_change_moved_source_before_return(self):
        from literate_ai.adapters import retained_layout_source_movement as movement

        raw, changed = refresh._raw_file, []
        with self.assertRaises(ValueError):
            with self.inspecting() as (owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ):

                    def change(path, **kwargs):
                        result = raw(path, **kwargs)
                        current = movement._MOVES.get(phase)
                        if (
                            current is not None
                            and not current.active
                            and current.expected is not None
                            and not changed
                        ):
                            changed.append(True)
                            target = self.destination / "app.py"
                            target.write_bytes(
                                target.read_bytes() + b"late-payload-close\n"
                            )
                        return result

                    with mock.patch.object(refresh, "_raw_file", change):
                        phase.move_source()
        self.assertEqual(changed, [True])
        self.assertTrue(
            (self.destination / "app.py").read_bytes().endswith(b"late-payload-close\n")
        )

    def test_funded_plan_and_usage_document_cannot_replace_actual_preparation(self):
        with self.prepare() as owner:
            with self.pool(owner.plan) as (pool, _journal):
                with self.assertRaises(ValueError):
                    with transaction.retained_layout_source_phase(
                        replace(owner.plan),
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                        preparation=owner,
                    ):
                        self.fail("copied plan admitted")
                with self.assertRaises(TypeError):
                    with transaction.retained_layout_source_phase(
                        owner.plan,
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                        preparation=owner.usage,
                    ):
                        self.fail("saved usage admitted")
            self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_copied_phase_and_changed_preparation_pointer_cannot_borrow_admission(self):
        with self.inspecting() as (owner, phase, _pool, _journal):
            forged = copy.copy(phase)
            with self.assertRaisesRegex(ValueError, "admission ended or is missing"):
                forged.move_source()
            phase._preparation = None
            try:
                with self.assertRaisesRegex(
                    ValueError, "original admitted source phase"
                ):
                    phase.move_source()
            finally:
                phase._preparation = owner
            owner.require_current()

    def test_actual_journal_documents_debit_original_metadata_records(self):
        with self.inspecting() as (owner, _phase, _pool, journal):
            before = owner.usage
            journal.append("inspection-observed", b'{"items":[1,2,3]}')
            self.assertGreater(owner.usage["entries"], before["entries"])
            self.assertIsNone(reads.current_role_observation())
            owner.require_current()

    def _refuse_aliased_private_resource(self, *, journal_inside):
        alias = self.project.with_name(self.project.name.swapcase())
        if (
            alias == self.project
            or not alias.exists()
            or not alias.samefile(self.project)
        ):
            self.skipTest("actual case-insensitive project alias required")
        inside = alias / "private-resource"
        inside.mkdir(mode=0o700)
        with self.prepare() as owner:
            journal_path = (inside if journal_inside else self.state) / "journal"
            stages_path = (self.state if journal_inside else inside) / "stages"
            stages_path.mkdir(mode=0o700, exist_ok=True)
            with retained_layout_journal(
                journal_path,
                canonical_binding=canonical_json_bytes(owner.plan.binding),
                budget=LayoutJournalBudget(128, 1024**2, 8 * 1024**2, 32),
            ) as journal:
                with staged_layout_controls(stages_path, journal) as pool:
                    with self.assertRaisesRegex(ValueError, "physically overlaps"):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail(
                                "aliased private resource acquired canonical controls"
                            )
                    self.assertFalse((self.project / "litai/layout.pending").exists())
                    self.assertEqual(journal.events, ())

    def test_private_pool_alias_refuses_before_control_acquisition(self):
        self._refuse_aliased_private_resource(journal_inside=False)

    def test_private_journal_alias_refuses_before_control_acquisition(self):
        self._refuse_aliased_private_resource(journal_inside=True)

    def test_journal_file_policy_cannot_exceed_original_read_ceiling(self):
        with self.prepare() as owner:
            with self.pool(owner.plan, budget=LayoutJournalBudget()) as (
                pool,
                _journal,
            ):
                with self.assertRaisesRegex(ValueError, "input file ceiling"):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ):
                        self.fail("enlarged journal file policy admitted")
            self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_created_control_parent_advances_original_absent_input_anchors(self):
        pending = transaction.layout_pending_control_path(self.project)
        neighbor = pending.parent / "unclaimed-optional.json"
        deeper = pending.parent / "still-missing/optional.json"
        unrelated = self.project / "uncreated-directory/optional.json"
        self.assertFalse(pending.parent.exists())

        def original_absences(owner):
            with owner._reads():
                for path in (pending, neighbor, deeper, unrelated):
                    self.assertIsNone(refresh._file(path, optional=True).content)

        with self.inspecting(before_admission=original_absences) as (
            owner,
            phase,
            _pool,
            _journal,
        ):
            state = preparation._state(owner)
            for path in (pending, neighbor, deeper):
                self.assertEqual(state.ledger.ancestry[path][0], pending.parent)
            self.assertEqual(state.ledger.ancestry[unrelated][0], self.project)
            self.assertTrue(admission._phase_record(phase).history)
            owner.require_current()
            self.assertFalse(neighbor.exists())

    def test_phase_revokes_before_resource_teardown_while_reader_survives_cleanup(self):
        observed = []
        with self.inspecting() as (owner, phase, _pool, _journal):
            reader = preparation._state(owner).reader
            descriptor = phase.controls.reservations._markers[0].descriptor

            def boundary():
                os.fstat(descriptor)
                observed.append(
                    (phase._active, phase in admission._PHASES, reader._active)
                )
                with self.assertRaises(ValueError):
                    phase.move_source()

            phase._resources.callback(boundary)
        self.assertEqual(observed, [(False, False, True)])
        self.assertFalse(reader._active)

    def test_admitted_installed_origin_never_uses_legacy_unbounded_git_capture(self):
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with mock.patch.object(
                project_initialization,
                "_git_value",
                side_effect=AssertionError("legacy unbounded origin capture"),
            ):
                with phase.complete_partition(
                    budget=self.input_budget,
                    maximum_metadata_bytes=self.metadata_limit,
                ) as partition:
                    partition.require_current()


@unittest.skipUnless(os.name == "posix", "actual catalog/source descriptor ownership")
class SourceAdmissionCatalogTests(unittest.TestCase):
    git = catalog_fixtures.CatalogCopyRoleTests.git
    init_git = catalog_fixtures.CatalogCopyRoleTests.init_git
    copying = catalog_fixtures.CatalogCopyRoleTests.copying
    pool = SourceAdmissionTests.pool
    updated = catalog_fixtures.CatalogCopyRoleTests.updated

    @classmethod
    def setUpClass(cls):
        catalog_fixtures.CatalogCopyRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        catalog_fixtures.CatalogCopyRoleTests.setUp(self)

    def test_admitted_currentness_revalidates_external_catalog_inputs(self):
        class StopInspection(Exception):
            pass

        rejected = []
        try:
            with self.copying() as catalog:
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                with preparation.prepared_retained_layout_source_move(
                    self.project,
                    "retained",
                    budget=self.copy_budget,
                    maximum_metadata_bytes=self.copy_metadata,
                    catalog_copy=catalog,
                ) as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ):
                            original = self.item / "flavor.md"
                            original.write_bytes(original.read_bytes() + b"changed\n")
                            try:
                                owner.require_current()
                            except ValueError:
                                rejected.append(True)
                            raise StopInspection()
        except StopInspection:
            pass
        self.assertEqual(rejected, [True])
        self.assertTrue((self.item / "flavor.md").read_bytes().endswith(b"changed\n"))

    def test_actual_catalog_is_consumed_once_but_its_inputs_stay_observed(self):
        class StopInspection(Exception):
            pass

        try:
            with self.copying() as catalog:
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                with preparation.prepared_retained_layout_source_move(
                    self.project,
                    "retained",
                    budget=self.copy_budget,
                    maximum_metadata_bytes=self.copy_metadata,
                    catalog_copy=catalog,
                ) as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with phase.complete_partition(
                                budget=self.copy_budget,
                                maximum_metadata_bytes=self.copy_metadata,
                                catalog_copy=catalog,
                            ) as partition:
                                phase.move_source()
                                self.assertTrue(partition._spent)
                                with self.assertRaises(ValueError):
                                    catalog.require_current()
                                owner.require_current()
                                original = self.item / "flavor.md"
                                original.write_bytes(
                                    original.read_bytes() + b"changed-after-spend\n"
                                )
                                with self.assertRaises(ValueError):
                                    owner.require_current()
                                raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue(self.destination.exists())

    def test_last_absence_scan_cannot_change_consumed_catalog_input(self):
        class StopInspection(Exception):
            pass

        changed, rejected = [], []
        absence = transaction._absence

        def change(path, *args, **kwargs):
            result = absence(path, *args, **kwargs)
            if path == self.source and not changed:
                changed.append(True)
                source = self.item / "flavor.md"
                source.write_bytes(source.read_bytes() + b"late-after-native\n")
            return result

        try:
            with self.copying() as catalog:
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                with preparation.prepared_retained_layout_source_move(
                    self.project,
                    "retained",
                    budget=self.copy_budget,
                    maximum_metadata_bytes=self.copy_metadata,
                    catalog_copy=catalog,
                ) as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with phase.complete_partition(
                                budget=self.copy_budget,
                                maximum_metadata_bytes=self.copy_metadata,
                                catalog_copy=catalog,
                            ):
                                phase.move_source()
                                with mock.patch.object(transaction, "_absence", change):
                                    try:
                                        owner.require_current()
                                    except ValueError:
                                        rejected.append(True)
                                raise StopInspection()
        except StopInspection:
            pass
        self.assertEqual(changed, [True])
        self.assertEqual(rejected, [True])

    def test_actual_framework_and_catalog_consumption_keep_original_read_owner(self):
        class StopInspection(Exception):
            pass

        self.update_budget, self.update_sequence = self.copy_budget, 0
        try:
            with self.updated(adopt_added=True) as update:
                with self.copying(framework_update=update) as catalog:
                    catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                    with preparation.prepared_retained_layout_source_move(
                        self.project,
                        "retained",
                        budget=self.copy_budget,
                        maximum_metadata_bytes=self.copy_metadata,
                        framework_update=update,
                        catalog_copy=catalog,
                    ) as owner:
                        original = preparation._state(owner)
                        with self.pool(owner.plan) as (pool, _journal):
                            with owner.source_phase(
                                pool,
                                acknowledged_plan_identity=owner.plan.identity,
                                allow_host_execution=True,
                            ) as phase:
                                with phase.complete_partition(
                                    budget=self.copy_budget,
                                    maximum_metadata_bytes=self.copy_metadata,
                                    framework_update=update,
                                    catalog_copy=catalog,
                                ):
                                    phase.move_source()
                                    owner.require_current()
                                    self.assertTrue(update._spent)
                                    with self.assertRaises(
                                        updates.FrameworkUpdateRoleError
                                    ):
                                        update.require_current()
                                    self.assertIs(
                                        preparation._state(owner).reader,
                                        original.reader,
                                    )
                                    raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
