"""Native exact metadata publication in the existing unfinished live owner."""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_transaction as source_fixtures
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "POSIX transaction metadata phase")
class RetainedLayoutMetadataTests(unittest.TestCase):
    plan = source_fixtures.RetainedLayoutTransactionTests.plan
    pool = source_fixtures.RetainedLayoutTransactionTests.pool
    phase = source_fixtures.RetainedLayoutTransactionTests.phase

    @classmethod
    def setUpClass(cls):
        source_fixtures.RetainedLayoutTransactionTests.setUpClass.__func__(cls)

    def setUp(self):
        source_fixtures.RetainedLayoutTransactionTests.setUp(self)
        self.metadata = self.state / "metadata"
        self.metadata.mkdir(mode=0o700)

    def test_actual_metadata_publication_keeps_old_nodes_and_requires_finalization(
        self,
    ):
        plan = self.plan()
        before = {item.path: item for item in plan.inputs}
        old_inodes = {
            name: (self.project / name).stat().st_ino
            for name in (transaction.HARNESS_WRAPPER_FILENAME, transaction._LIFT)
        }
        with self.pool(plan) as (pool, journal):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    result = phase.publish_metadata(self.metadata)
                    self.assertEqual(
                        result,
                        {
                            "state": "metadata-published-finalization-pending",
                            "relocation_complete": False,
                            "qualified": False,
                        },
                    )
                    phase._require_moved()
                    with self.assertRaisesRegex(ValueError, "already attempted"):
                        phase.publish_metadata(self.metadata)
            self.assertEqual(journal.events[-1]["kind"], "layout-metadata-observed")
            for index, name in enumerate(
                (transaction.HARNESS_WRAPPER_FILENAME, transaction._LIFT)
            ):
                backup = self.metadata / f"old-{index}"
                self.assertEqual(backup.stat().st_ino, old_inodes[name])
                self.assertEqual(
                    backup.read_bytes(), before[self.project / name].content
                )
        for name, content in plan.prospective:
            self.assertEqual((self.project / name).read_bytes(), content)
        current = transaction.resolve_structural_layout(
            self.project, json.loads((self.project / transaction._LIFT).read_bytes())
        )
        self.assertEqual(current.implementation_root, self.destination)
        self.assertFalse(self.source.exists())
        unaffected = set(before) - {self.project / name for name, _ in plan.prospective}
        for path in unaffected:
            self.assertEqual(
                path.read_bytes() if path.exists() else None, before[path].content
            )

    def test_metadata_cannot_start_without_actual_source_effect(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "completed source phase"):
                with self.phase(plan, pool) as phase:
                    phase.publish_metadata(self.metadata)
        self.assertTrue(self.source.exists())
        self.assertEqual(list(self.metadata.iterdir()), [])

    def test_foreign_metadata_root_is_preserved_without_public_metadata_effects(self):
        plan = self.plan()
        foreign = self.metadata / "foreign"
        foreign.write_bytes(b"foreign private bytes")
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "not empty"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
        self.assertEqual(foreign.read_bytes(), b"foreign private bytes")
        self.assertEqual(
            json.loads((self.project / transaction._LIFT).read_bytes())["state"],
            "passed",
        )

    def test_source_directory_cannot_become_metadata_stage_area(self):
        self.source.chmod(0o700)
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "overlaps source"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.destination)

    def test_changed_authored_bytes_are_not_quarantined(self):
        plan = self.plan()
        wrapper = self.project / transaction.HARNESS_WRAPPER_FILENAME
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "authored metadata changed"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    wrapper.write_bytes(b"foreign wrapper bytes\n")
                    phase.publish_metadata(self.metadata)
        self.assertEqual(wrapper.read_bytes(), b"foreign wrapper bytes\n")
        self.assertEqual(list(self.metadata.iterdir()), [])

    def test_replaced_live_plan_cannot_publish_new_unacknowledged_bytes(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(
                ValueError, "acknowledged transaction plan changed"
            ):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.plan = replace(
                        plan,
                        prospective=(
                            (transaction.HARNESS_WRAPPER_FILENAME, b"foreign"),
                            *plan.prospective[1:],
                        ),
                    )
                    phase.publish_metadata(self.metadata)
        self.assertEqual(list(self.metadata.iterdir()), [])

    def test_interrupted_old_file_quarantine_keeps_original_node_and_source(self):
        plan = self.plan()
        original = (self.project / transaction.HARNESS_WRAPPER_FILENAME).read_bytes()
        move = transaction.move_layout_entry_exclusive

        def interrupted(source, destination, **kwargs):
            move(source, destination, **kwargs)
            if destination == self.metadata / "old-0":
                raise OSError("controlled interruption after quarantine")

        with self.pool(plan) as (pool, journal):
            with self.assertRaisesRegex(OSError, "after quarantine"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    with mock.patch.object(
                        transaction,
                        "move_layout_entry_exclusive",
                        side_effect=interrupted,
                    ):
                        phase.publish_metadata(self.metadata)
            self.assertEqual(journal.events[-1]["kind"], "metadata-quarantine-intent")
        self.assertEqual((self.metadata / "old-0").read_bytes(), original)
        self.assertFalse((self.project / transaction.HARNESS_WRAPPER_FILENAME).exists())
        self.assertTrue(self.destination.exists())

    def test_foreign_repopulation_after_quarantine_is_never_replaced(self):
        plan = self.plan()
        wrapper = self.project / transaction.HARNESS_WRAPPER_FILENAME
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "metadata-quarantine-observed":
                    wrapper.write_bytes(b"foreign replacement")
                return result

            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.publish_metadata(self.metadata)
        self.assertEqual(wrapper.read_bytes(), b"foreign replacement")
        self.assertTrue((self.metadata / "old-0").is_file())

    def test_foreign_private_insertion_during_publication_remains_intact(self):
        plan = self.plan()
        foreign = self.metadata / "foreign"
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "metadata-publication-observed":
                    foreign.write_bytes(b"foreign insertion")
                return result

            with self.assertRaisesRegex(ValueError, "private metadata namespace"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.publish_metadata(self.metadata)
        self.assertEqual(foreign.read_bytes(), b"foreign insertion")

    def test_changed_moved_source_during_metadata_intent_refuses_before_quarantine(
        self,
    ):
        plan = self.plan()
        original = (self.project / transaction.HARNESS_WRAPPER_FILENAME).read_bytes()
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed(kind, content):
                result = append(kind, content)
                if kind == "metadata-quarantine-intent":
                    (self.destination / "app.py").write_bytes(
                        b"changed after source move"
                    )
                return result

            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    with mock.patch.object(journal, "append", side_effect=changed):
                        phase.publish_metadata(self.metadata)
        self.assertEqual(
            (self.project / transaction.HARNESS_WRAPPER_FILENAME).read_bytes(), original
        )
        self.assertFalse((self.metadata / "old-0").exists())

    def test_metadata_modes_are_preserved_without_qualification(self):
        wrapper = self.project / transaction.HARNESS_WRAPPER_FILENAME
        wrapper.chmod(0o640)
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
        self.assertEqual(wrapper.stat().st_mode & 0o777, 0o640)
        self.assertEqual((self.metadata / "old-0").stat().st_mode & 0o777, 0o640)
        self.assertEqual(
            json.loads((self.project / transaction._LIFT).read_bytes())["state"],
            "requalification-required",
        )

    def test_metadata_state_may_use_actual_private_framework_state_inside_project(self):
        private = self.project / "litai/state/metadata"
        private.mkdir(parents=True, mode=0o700)
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(private)
        self.assertTrue((private / "old-0").is_file())
        self.assertEqual(
            (self.project / transaction.RETAINED_LAYOUT_PATH).read_bytes(),
            dict(plan.prospective)[transaction.RETAINED_LAYOUT_PATH],
        )

    def test_actual_journal_budget_refuses_before_metadata_staging_or_quarantine(self):
        plan = self.plan()
        budget = replace(LayoutJournalBudget(), maximum_events=24)
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=canonical_json_bytes(plan.binding),
            budget=budget,
        ) as journal:
            with staged_layout_controls(self.state / "stages", journal) as pool:
                with self.assertRaisesRegex(ValueError, "remaining journal budget"):
                    with self.phase(plan, pool) as phase:
                        phase.move_source()
                        phase.publish_metadata(self.metadata)
                self.assertFalse(
                    any(item["kind"].startswith("metadata-") for item in journal.events)
                )
        self.assertEqual(list(self.metadata.iterdir()), [])
        self.assertTrue((self.project / transaction.HARNESS_WRAPPER_FILENAME).exists())

    def test_closed_live_owner_cannot_publish_further_metadata(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
            with self.assertRaisesRegex(ValueError, "context ended"):
                phase.publish_metadata(self.metadata)

    def test_existing_layout_declaration_is_quarantined_by_original_identity(self):
        declaration = transaction.RetainedLayoutDeclaration(
            "components/legacy-project-wrapper",
            "components/legacy-project-wrapper/implementation",
            (),
            None,
        )
        path = self.project / transaction.RETAINED_LAYOUT_PATH
        old_bytes = canonical_json_bytes(declaration.to_dict()) + b"\n"
        path.write_bytes(old_bytes)
        old_inode = path.stat().st_ino
        lift_path = self.project / transaction._LIFT
        lift = json.loads(lift_path.read_bytes())
        lift.update(
            wrapper_component=declaration.wrapper_component,
            layout_identity=declaration.identity,
            previous_layout_identity=None,
        )
        lift_path.write_bytes(canonical_json_bytes(lift) + b"\n")
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
        self.assertEqual((self.metadata / "old-2").stat().st_ino, old_inode)
        self.assertEqual((self.metadata / "old-2").read_bytes(), old_bytes)
        self.assertNotEqual(path.stat().st_ino, old_inode)
        self.assertEqual(
            json.loads(path.read_bytes())["lineage"]["previous_layout_identity"],
            declaration.identity,
        )

    def test_control_pool_cannot_be_reused_as_metadata_producer(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "another actual producer"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(pool.root)
        self.assertEqual(
            json.loads((self.project / transaction._LIFT).read_bytes())["state"],
            "passed",
        )

    def test_live_plan_replacement_cannot_redirect_source_before_metadata(self):
        plan = self.plan()
        other = transaction.plan_retained_layout_source_move(
            self.project, "different-source-target", budget=self.budget
        )
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(
                ValueError, "acknowledged transaction plan changed"
            ):
                with self.phase(plan, pool) as phase:
                    phase.plan = other
                    phase.move_source()
        self.assertTrue(self.source.exists())
        self.assertFalse(other.destination.exists())

    def test_same_byte_foreign_publication_inode_is_never_adopted(self):
        plan = self.plan()
        wrapper = self.project / transaction.HARNESS_WRAPPER_FILENAME
        displaced = self.state / "actual-published-stage"
        original_node = transaction.layout_entry_node
        injected = False
        with self.pool(plan) as (pool, _):
            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    phase.move_source()

                    def changed(path):
                        nonlocal injected
                        node = original_node(path)
                        area = phase._metadata_area
                        if (
                            not injected
                            and path == wrapper
                            and area is not None
                            and "new-0" in area.known
                            and node.inode == area.known["new-0"][0].inode
                        ):
                            injected = True
                            content = wrapper.read_bytes()
                            wrapper.rename(displaced)
                            wrapper.write_bytes(content)
                        return node

                    with mock.patch.object(
                        transaction, "layout_entry_node", side_effect=changed
                    ):
                        phase.publish_metadata(self.metadata)
                    self.fail(
                        "metadata returned success across a foreign same-byte inode"
                    )
        self.assertTrue(injected)
        self.assertEqual(wrapper.read_bytes(), displaced.read_bytes())
        self.assertNotEqual(wrapper.stat().st_ino, displaced.stat().st_ino)

    def test_quarantine_hole_never_adopts_a_foreign_optional_read(self):
        plan = self.plan()
        wrapper = self.project / transaction.HARNESS_WRAPPER_FILENAME
        original_file = transaction._file
        injected = False
        with self.pool(plan) as (pool, journal):
            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    phase.move_source()

                    def changed(path, **kwargs):
                        nonlocal injected
                        area = phase._metadata_area
                        if (
                            not injected
                            and path == wrapper
                            and kwargs.get("optional")
                            and area is not None
                            and "old-0" in area.known
                            and not wrapper.exists()
                        ):
                            injected = True
                            wrapper.write_bytes(b"foreign quarantine hole occupant")
                        return original_file(path, **kwargs)

                    with mock.patch.object(transaction, "_file", side_effect=changed):
                        phase.publish_metadata(self.metadata)
            self.assertTrue(injected)
            current = next(
                item for item in phase._current_inputs if item.path == wrapper
            )
            self.assertIsNone(current.signature)
            self.assertFalse(
                any(
                    item["kind"] == "metadata-publication-intent"
                    for item in journal.events
                )
            )
        self.assertEqual(wrapper.read_bytes(), b"foreign quarantine hole occupant")

    def test_cached_metadata_writer_rejects_context_end_before_using_closed_fds(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "remains incomplete"):
                with self.phase(plan, pool) as phase:
                    phase.move_source()
                    phase.publish_metadata(self.metadata)
                    area = phase._metadata_area
            with self.assertRaisesRegex(ValueError, "context ended"):
                area.require_current()
