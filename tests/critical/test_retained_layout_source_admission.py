"""Real prepared control/partition admission; unfinished effects stay refused."""

from __future__ import annotations

import copy
import errno
import json
import os
import stat
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

import tests.critical.test_catalog_copy_roles as catalog_fixtures
import tests.critical.test_catalog_source_lease as git_fixtures
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
                    dict(partition.roles)["literate.project.json"], "authored"
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
            with self.assertRaisesRegex(ValueError, "actual moved source"):
                phase.publish_metadata(self.metadata)
            for operation in (
                lambda: phase.finalize_controls(self.retired),
                lambda: phase.controls.reservations.begin_finalization(self.retired),
            ):
                with self.subTest(operation=operation):
                    with self.assertRaisesRegex(ValueError, "verified transition"):
                        operation()
            self.assertFalse(phase._attempted)
            self.assertFalse(self.destination.exists())

    def test_actual_graph_is_bound_to_partition_and_durable_move_intent(self):
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        with self.inspecting() as (_owner, phase, _pool, journal):
            with phase.complete_partition(
                budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
            ) as partition:
                graph = partition._effect_graph
                self.assertEqual(
                    graph.require_single_rename(),
                    (self.source.relative_to(self.project).as_posix(), "retained"),
                )
                phase.move_source()
                event = next(
                    e for e in journal.events if e["kind"] == "source-move-intent"
                )
                self.assertEqual(
                    event["data"]["source_effect_graph_identity"], graph.identity.uri
                )
                event = next(
                    e
                    for e in journal.events
                    if e["kind"] == "source-partition-observed"
                )
                recorded = json.loads(
                    journal.read_payload(event["data"]["partition_payload_digest"])
                )
                self.assertEqual(
                    recorded["source_effect_graph"]["carriers"],
                    [list(graph.carriers[0])],
                )

    def _changed_graph_refuses_effect(self, mutate):
        from dataclasses import replace

        with self.assertRaisesRegex(
            ValueError, "partition required|effect graph changed"
        ):
            with self.inspecting() as (_owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ) as partition:
                    graph = partition._effect_graph
                    if mutate:
                        object.__setattr__(graph, "carriers", ())
                    else:
                        partition._effect_graph = replace(graph)
                    with mock.patch.object(
                        transaction, "move_layout_entry_exclusive"
                    ) as effect:
                        try:
                            phase.move_source()
                        finally:
                            effect.assert_not_called()
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_replaced_graph_refuses_before_effect(self):
        self._changed_graph_refuses_effect(mutate=False)

    def test_mutated_graph_refuses_before_effect(self):
        self._changed_graph_refuses_effect(mutate=True)

    def test_actual_movement_consumes_partition_and_retains_original_reader(self):
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
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
                phase.finalize_controls(self.retired)
        self.assertNotIn(phase, movement._MOVES)
        self.assertFalse(original.reader._active)
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_actual_metadata_publication_retains_originals_and_same_read_owner(self):
        from literate_ai.adapters import retained_layout_source_metadata as metadata

        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        with self.inspecting() as (owner, phase, _pool, _journal):
            original = preparation._state(owner)
            inputs = owner.plan.inputs
            with phase.complete_partition(
                budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
            ):
                phase.move_source()
            result = phase.publish_metadata(self.metadata)
            self.assertEqual(result["state"], "metadata-published-finalization-pending")
            self.assertTrue(phase._metadata_published)
            self.assertIs(phase.plan.inputs, inputs)
            self.assertIs(preparation._state(owner).reader, original.reader)
            owner.require_current()
            for name, content in phase.plan.prospective:
                self.assertEqual((self.project / name).read_bytes(), content)
            state = metadata._METADATA[phase]
            self.assertTrue(state.published)
            for _path, before, backup, _current in state.receipts:
                if before.content is not None:
                    self.assertEqual(backup.path.read_bytes(), before.content)
            with self.assertRaisesRegex(ValueError, "verified transition"):
                phase.controls.reservations.begin_finalization(self.retired)
            self.assertIsNone(reads.current_role_observation())
        self.assertNotIn(phase, metadata._METADATA)
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_original_entry_policy_refuses_before_source_move(self):
        from literate_ai.adapters.retained_layout_source_state import (
            _read_original_state,
        )

        self.assertEqual(self.input_budget.maximum_entries, 65536)
        before = (self.source / "app.py").read_bytes()
        source_inode = self.source.stat().st_ino
        source_error, controls, descriptors = [], [], []
        with self.assertRaises(ValueError) as failed:
            with self.prepare() as owner:
                original = preparation._state(owner)
                binding = canonical_json_bytes(owner.plan.binding)
                phase_identity = owner.plan.identity.uri
                with self.pool(owner.plan) as (pool, journal):
                    journal_budget = journal._budget
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        controls.extend(phase.controls.reservations._markers)
                        descriptors.extend(marker.descriptor for marker in controls)
                        with phase.complete_partition(
                            budget=self.input_budget,
                            maximum_metadata_bytes=self.metadata_limit,
                        ):
                            with mock.patch.object(
                                transaction,
                                "move_layout_entry_exclusive",
                                side_effect=AssertionError(
                                    "source effect before capacity admission"
                                ),
                            ):
                                try:
                                    phase.move_source()
                                except ValueError as error:
                                    source_error.append(error)
                                    raise
        self.assertEqual(len(source_error), 1)
        self.assertIn("shared catalog input allowance exhausted", str(source_error[0]))
        chain, current = [], failed.exception
        while current is not None and current not in chain:
            chain.append(current)
            current = current.__cause__ or current.__context__
        self.assertIn(
            source_error[0], chain, "cleanup masked the primary capacity failure"
        )
        self.assertEqual(original.ledger.budget.maximum_entries, 65536)
        self.assertGreater(original.ledger.records, 65536)
        self.assertLess(original.ledger.charged, self.metadata_limit)
        self.assertEqual(self.source.stat().st_ino, source_inode)
        self.assertEqual((self.source / "app.py").read_bytes(), before)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.metadata.iterdir()), [])
        self.assertEqual(list(self.retired.iterdir()), [])
        self.assertTrue(controls)
        self.assertTrue(all(marker.target.path.is_file() for marker in controls))
        self.assertTrue(all(marker.descriptor == -1 for marker in controls))
        for descriptor in descriptors:
            with self.assertRaises(OSError) as closed:
                os.fstat(descriptor)
            self.assertEqual(closed.exception.errno, errno.EBADF)
        self.assertTrue((self.project / "litai/layout.pending").is_file())
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=binding,
            budget=journal_budget,
            recover=True,
        ) as journal:
            events = journal.events
            self.assertEqual(
                sum(e["kind"] == "source-original-state-durable" for e in events), 1
            )
            self.assertNotIn("source-move-intent", [e["kind"] for e in events])
            saved = _read_original_state(
                journal,
                phase_identity,
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            )
            self.assertEqual(saved.document["source_phase_identity"], phase_identity)

    def test_changed_retained_metadata_backup_refuses_without_erasure(self):
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        changed = []
        with self.assertRaises(ValueError):
            with self.inspecting() as (owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ):
                    phase.move_source()
                phase.publish_metadata(self.metadata)
                backup = self.metadata / "old-0"
                backup.write_bytes(backup.read_bytes() + b"foreign-backup-edit\n")
                changed.append(backup)
                owner.require_current()
        self.assertEqual(len(changed), 1)
        self.assertTrue(changed[0].read_bytes().endswith(b"foreign-backup-edit\n"))
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_foreign_namespace_during_metadata_rename_is_retained_and_refused(self):
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        move, changed = transaction.move_layout_entry_exclusive, []
        foreign = self.project / "foreign-during-metadata"

        def insert(source, destination, **kwargs):
            result = move(source, destination, **kwargs)
            if destination.parent == self.metadata and not changed:
                foreign.write_bytes(b"foreign\n")
                changed.append(True)
            return result

        with self.assertRaises(ValueError):
            with self.inspecting() as (_owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ):
                    phase.move_source()
                with mock.patch.object(
                    transaction, "move_layout_entry_exclusive", insert
                ):
                    phase.publish_metadata(self.metadata)
        self.assertEqual(changed, [True])
        self.assertEqual(foreign.read_bytes(), b"foreign\n")
        self.assertFalse(phase._metadata_published)
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_wrong_stage_permission_template_refuses_before_stage_creation(self):
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        stage, changed = transaction._MetadataArea.stage, []

        def wrong(area, name, content, old_node):
            if not changed and old_node is not None:
                changed.append(True)
                old_node = replace(old_node, mode=old_node.mode ^ 0o111)
            return stage(area, name, content, old_node)

        with self.assertRaises(ValueError):
            with self.inspecting() as (_owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ):
                    phase.move_source()
                with mock.patch.object(transaction._MetadataArea, "stage", wrong):
                    phase.publish_metadata(self.metadata)
        self.assertEqual(changed, [True])
        self.assertFalse((self.metadata / "new-0").exists())

    def test_observed_record_headroom_is_required_before_public_metadata_rename(self):
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        absence, consumed = transaction._absence, []
        with self.assertRaises(ValueError):
            with self.inspecting() as (owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ):
                    phase.move_source()
                name = transaction.HARNESS_WRAPPER_FILENAME
                original = (self.project / name).read_bytes()
                reader = preparation._state(owner).reader

                def consume(path, *args, **kwargs):
                    result = absence(path, *args, **kwargs)
                    if path == self.metadata / "old-0" and not consumed:
                        ledger = preparation._state(owner).ledger
                        left = ledger.budget.maximum_entries - ledger.records
                        payload = b"[" + b",".join([b"0"] * (left - 2)) + b"]"
                        reader.json_value(
                            payload, str(self.project / "additional-observation")
                        )
                        consumed.append(True)
                    return result

                with mock.patch.object(transaction, "_absence", consume):
                    phase.publish_metadata(self.metadata)
        self.assertEqual(consumed, [True])
        self.assertFalse((self.metadata / "old-0").exists())
        self.assertEqual((self.project / name).read_bytes(), original)
        self.assertTrue((self.metadata / "new-0").exists())
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_private_membership_change_during_last_native_file_close_refuses(self):
        from literate_ai.adapters import retained_layout_source_metadata as metadata

        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        real_stat, changed, rejected, armed = os.stat, [], [], []
        close = metadata._close_metadata_native
        foreign = self.metadata / "foreign-last-native"
        try:
            with self.inspecting() as (owner, phase, _pool, _journal):
                with phase.complete_partition(
                    budget=self.input_budget, maximum_metadata_bytes=self.metadata_limit
                ):
                    phase.move_source()
                phase.publish_metadata(self.metadata)
                state = metadata._METADATA[phase]
                last_name = state.known[-1][0]

                def change(path, *args, **kwargs):
                    result = real_stat(path, *args, **kwargs)
                    if (
                        path == last_name
                        and kwargs.get("dir_fd") == state.descriptor
                        and armed
                        and not changed
                    ):
                        changed.append(True)
                        foreign.write_bytes(b"foreign\n")
                    return result

                def mark(record):
                    armed.append(True)
                    try:
                        return close(record)
                    finally:
                        armed.clear()

                with mock.patch.object(metadata, "_close_metadata_native", mark):
                    with mock.patch.object(metadata.os, "stat", change):
                        try:
                            owner.require_current()
                        except ValueError:
                            rejected.append(True)
        except ValueError:
            pass
        self.assertEqual(changed, [True])
        self.assertEqual(rejected, [True])
        self.assertEqual(foreign.read_bytes(), b"foreign\n")

    def test_foreign_namespace_inserted_during_actual_move_refuses(self):
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
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
        self.input_budget = replace(self.input_budget, maximum_entries=131072)

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
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
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
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
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
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
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
        class StopInspection(Exception):
            pass

        alias = self.project.with_name(self.project.name.swapcase())
        if (
            alias == self.project
            or not alias.exists()
            or not alias.samefile(self.project)
        ):
            self.skipTest("actual case-insensitive project alias required")
        inside = alias / "private-resource"
        inside.mkdir(mode=0o700)
        journal_path = (inside if journal_inside else self.state) / "journal"
        stages_path = (self.state if journal_inside else inside) / "stages"
        # An existing empty pool must still reach the native ancestry guard.
        # The journal binds the plan, so its later in-project creation instead
        # invalidates the original namespace before private admission begins.
        stages_path.mkdir(mode=0o700, exist_ok=True)
        rejected = False
        try:
            with self.prepare() as owner:
                with retained_layout_journal(
                    journal_path,
                    canonical_binding=canonical_json_bytes(owner.plan.binding),
                    budget=LayoutJournalBudget(128, 1024**2, 8 * 1024**2, 32),
                ) as journal:
                    with staged_layout_controls(stages_path, journal) as pool:
                        before = sorted(self.project.rglob("*"))
                        expected = (
                            r"^retained\.cargo\.v2-input-custody-changed$"
                            if journal_inside
                            else "physically overlaps"
                        )
                        with mock.patch.object(
                            transaction,
                            "acquire_retained_layout_control_roles",
                            side_effect=AssertionError("canonical acquisition reached"),
                        ):
                            with self.assertRaisesRegex(ValueError, expected):
                                with owner.source_phase(
                                    pool,
                                    acknowledged_plan_identity=owner.plan.identity,
                                    allow_host_execution=True,
                                ):
                                    self.fail("aliased private resource admitted")
                        self.assertEqual(sorted(self.project.rglob("*")), before)
                        self.assertFalse(
                            (self.project / "litai/layout.pending").exists()
                        )
                        self.assertEqual(journal.events, ())
                        os.fstat(journal._descriptor)
                        os.fstat(pool._descriptor)
                        rejected = True
                        if journal_inside:
                            self.assertNotIn(owner, preparation._LIVE)
                            raise StopInspection()
                        owner.require_current()
        except StopInspection:
            pass
        self.assertTrue(rejected)
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

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

        # Fund the complete namespace and post-move observations before the
        # catalog producer starts; the live ledger never gains allowance.
        self.copy_budget = replace(self.copy_budget, maximum_entries=131072)
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

        self.copy_budget = replace(self.copy_budget, maximum_entries=131072)
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

        # Isolated workers add real ancestor and reservation observations.
        # Declare the complete positive profile before the first producer;
        # an active operation never receives a larger allowance.
        self.copy_metadata = 8 * 1024**3
        self.copy_budget = replace(self.copy_budget, maximum_entries=131072)
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
                                    self.assertEqual(
                                        original.ledger.budget, self.copy_budget
                                    )
                                    self.assertEqual(
                                        original.ledger.metadata, self.copy_metadata
                                    )
                                    self.assertLessEqual(
                                        owner.usage["entries"],
                                        self.copy_budget.maximum_entries,
                                    )
                                    self.assertLessEqual(
                                        owner.usage["metadata_bytes"],
                                        self.copy_metadata,
                                    )
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

    def test_actual_framework_catalog_metadata_preserves_immutable_witnesses(self):
        class StopInspection(Exception):
            pass

        self.copy_metadata = 8 * 1024**3
        # This positive profile includes the real framework/catalog roster,
        # source handoff and metadata receipts. Declare its complete entry
        # allowance before the first producer; the separate low-budget refusal
        # retains its original 69,632-entry policy.
        self.copy_budget = replace(self.copy_budget, maximum_entries=196608)
        self.update_budget, self.update_sequence = self.copy_budget, 0
        try:
            with self.updated(adopt_added=True) as update:
                with self.copying(framework_update=update) as catalog:
                    catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                    cache = tuple(update._cache.items())
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
                                phase.publish_metadata(self.metadata)
                                owner.require_current()
                                self.assertEqual(tuple(update._cache.items()), cache)
                                self.assertIs(
                                    preparation._state(owner).reader, original.reader
                                )
                                self.assertTrue(phase._metadata_published)
                                raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.metadata / "old-0").exists())

    def test_original_combined_allowance_refuses_before_metadata_writes(self):
        class InspectionComplete(Exception):
            pass

        self.copy_budget = replace(self.copy_budget, maximum_entries=69632)
        self.copy_metadata = 8 * 1024**3
        self.update_budget, self.update_sequence = self.copy_budget, 0
        with (
            self.assertRaises(InspectionComplete),
            self.updated(adopt_added=True) as update,
        ):
            with self.copying(framework_update=update) as catalog:
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                usage = preparation._predecessor_usage(update, catalog)
                self.assertEqual(usage.budget.maximum_entries, 69632)
                names = sorted(self.project.rglob("*"))
                source = (
                    self.source.stat().st_ino,
                    (self.source / "app.py").read_bytes(),
                )
                before = {
                    self.project / name: (
                        (self.project / name).read_bytes()
                        if (self.project / name).exists()
                        else None
                    )
                    for name in (
                        transaction.RETAINED_LAYOUT_PATH,
                        transaction._LIFT,
                        transaction.HARNESS_WRAPPER_FILENAME,
                    )
                }
                with (
                    mock.patch.object(
                        transaction,
                        "move_layout_entry_exclusive",
                        side_effect=AssertionError("source effect during preparation"),
                    ) as effect,
                    self.assertRaisesRegex(
                        ValueError,
                        "shared catalog input allowance exhausted|"
                        "decoded canonical metadata exceeds the shared allowance",
                    ),
                ):
                    with preparation.prepared_retained_layout_source_move(
                        self.project,
                        "retained",
                        budget=self.copy_budget,
                        maximum_metadata_bytes=self.copy_metadata,
                        framework_update=update,
                        catalog_copy=catalog,
                    ):
                        self.fail("unfunded combined role discovery admitted")
                effect.assert_not_called()
                self.assertEqual(sorted(self.project.rglob("*")), names)
                self.assertEqual(
                    (self.source.stat().st_ino, (self.source / "app.py").read_bytes()),
                    source,
                )
                self.assertFalse(self.destination.exists())
                self.assertFalse((self.project / "litai/layout.pending").exists())
                self.assertEqual(list(self.metadata.iterdir()), [])
                self.assertEqual(list(self.retired.iterdir()), [])
                for path, content in before.items():
                    self.assertEqual(
                        path.read_bytes() if path.exists() else None, content
                    )
                self.assertEqual(preparation._predecessor_usage(update, catalog), usage)
                update.require_current()
                catalog.require_current()
                # This refusal does not claim a consuming source transaction.
                raise InspectionComplete()

    def test_metadata_preflight_refuses_after_original_allowance_is_reserved(self):
        # Fund this actual metadata boundary before either producer starts,
        # then reserve records through the same original ledger.
        limit = 131072
        self.copy_budget = replace(self.copy_budget, maximum_entries=limit)
        self.copy_metadata = 8 * 1024**3
        self.update_budget, self.update_sequence = self.copy_budget, 0
        moved = False
        with self.assertRaisesRegex(
            ValueError,
            "metadata preflight exceeds original allowance",
        ):
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
                                    original = preparation._state(owner)
                                    before = {
                                        name: next(
                                            item.content
                                            for item in owner.plan.inputs
                                            if item.path == self.project / name
                                        )
                                        for name, _ in owner.plan.prospective
                                    }
                                    with mock.patch.object(
                                        transaction,
                                        "move_layout_entry_exclusive",
                                        wraps=transaction.move_layout_entry_exclusive,
                                    ) as effect:
                                        phase.move_source()
                                    moved = True
                                ledger = original.ledger
                                remaining = (
                                    ledger.budget.maximum_entries - ledger.records
                                )
                                self.assertGreater(remaining, 512)
                                ledger.charge_records(remaining - 512, 0)
                                phase.publish_metadata(self.metadata)
        self.assertEqual(list(self.metadata.iterdir()), [])
        self.assertFalse(phase._metadata_published)
        self.assertEqual(original.ledger.budget.maximum_entries, limit)
        self.assertEqual(effect.call_count, int(moved))
        self.assertEqual((self.source / "app.py").is_file(), not moved)
        self.assertEqual(self.destination.exists(), moved)
        for name, content in before.items():
            path = self.project / name
            self.assertEqual(path.read_bytes() if path.exists() else None, content)
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def _check_original_catalog_scope_refuses_metadata(self, *, source_scope):
        class StopInspection(Exception):
            pass

        self.copy_metadata = 8 * 1024**3
        self.copy_budget = replace(self.copy_budget, maximum_entries=131072)
        refused = []
        protected = self.item / "empty" if source_scope else None
        if source_scope:
            protected.chmod(0o700)
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
                            if not source_scope:
                                record = admission._phase_record(
                                    phase
                                ).catalog_lifetime[0]
                                candidates = [
                                    state.root / name
                                    for state in record["seal"].private
                                    for name, node in state.nodes.items()
                                    if stat.S_ISDIR(node.mode)
                                    and stat.S_IMODE(node.mode) == 0o700
                                    and not any(
                                        other != name
                                        and (not name or other.startswith(name + "/"))
                                        for other in state.nodes
                                    )
                                ]
                                self.assertTrue(candidates)
                                protected = sorted(candidates)[0]
                            self.assertEqual(list(protected.iterdir()), [])
                            try:
                                phase.publish_metadata(protected)
                            except ValueError:
                                refused.append(True)
                            raise StopInspection()
        except StopInspection:
            pass
        self.assertEqual(refused, [True])
        self.assertEqual(list(protected.iterdir()), [])
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_consumed_catalog_private_container_refuses_metadata_before_writes(self):
        self._check_original_catalog_scope_refuses_metadata(source_scope=False)

    def test_original_catalog_source_refuses_metadata_before_writes(self):
        self._check_original_catalog_scope_refuses_metadata(source_scope=True)


@unittest.skipUnless(os.name == "posix", "actual canonical Git acquisition ownership")
class SourceAdmissionGitCatalogTests(unittest.TestCase):
    git = git_fixtures.CatalogSourceLeaseTests.git
    init_git = git_fixtures.CatalogSourceLeaseTests.init_git
    commit_source = git_fixtures.CatalogSourceLeaseTests.commit_source
    copying = git_fixtures.CatalogSourceLeaseTests.copying
    pool = SourceAdmissionTests.pool

    @classmethod
    def setUpClass(cls):
        git_fixtures.CatalogSourceLeaseTests.setUpClass.__func__(cls)

    def setUp(self):
        git_fixtures.CatalogSourceLeaseTests.setUp(self)
        self.copy_metadata = 8 * 1024**3
        self.copy_budget = replace(self.copy_budget, maximum_entries=131072)

    def _check_canonical_scope_refuses_metadata(self, *, sibling):
        class StopInspection(Exception):
            pass

        refused = []
        try:
            with self.copying() as catalog:
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                clone = catalog.plan.source_root
                protected = (
                    clone.parent / "metadata"
                    if sibling
                    else clone / ".git/objects/info"
                )
                if not sibling:
                    self.assertEqual(list(protected.iterdir()), [])
                    protected.chmod(0o700)
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
                            if sibling:
                                protected.mkdir(mode=0o700)
                            try:
                                phase.publish_metadata(protected)
                            except ValueError:
                                refused.append(True)
                            self.assertEqual(refused, [True])
                            self.assertEqual(list(protected.iterdir()), [])
                            raise StopInspection()
        except StopInspection:
            pass
        self.assertTrue((self.project / "litai/layout.pending").exists())

    def test_whole_canonical_acquisition_refuses_metadata_before_writes(self):
        self._check_canonical_scope_refuses_metadata(sibling=False)

    def test_canonical_cleanup_parent_refuses_metadata_before_writes(self):
        self._check_canonical_scope_refuses_metadata(sibling=True)

    def test_metadata_outside_acquisition_survives_actual_clone_cleanup(self):
        class StopInspection(Exception):
            pass

        try:
            with self.copying() as catalog:
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                clone = catalog.plan.source_root
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
                            original = (
                                self.project / transaction.HARNESS_WRAPPER_FILENAME
                            ).read_bytes()
                            phase.publish_metadata(self.metadata)
                            owner.require_current()
                            self.assertEqual(
                                (self.metadata / "old-0").read_bytes(), original
                            )
                            raise StopInspection()
        except StopInspection:
            pass
        self.assertFalse(clone.exists())
        self.assertEqual((self.metadata / "old-0").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
