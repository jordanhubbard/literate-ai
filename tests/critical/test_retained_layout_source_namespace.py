"""Actual original namespace and canonical descriptor publication projection."""

from __future__ import annotations

import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
from literate_ai.adapters import retained_layout_source_namespace as namespace
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters import retained_layout_transaction as transaction


@unittest.skipUnless(os.name == "posix", "actual POSIX original namespace owner")
class SourceNamespaceTests(unittest.TestCase):
    prepare = fixtures.SourceAdmissionTests.prepare
    pool = fixtures.SourceAdmissionTests.pool
    inspecting = fixtures.SourceAdmissionTests.inspecting

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        # Declare the complete finite positive profile before preparation.
        self.input_budget = replace(self.input_budget, maximum_entries=131072)

    def test_complete_original_namespace_is_bound_before_acknowledgement(self):
        foreign = self.project / "unclaimed"
        foreign.write_bytes(b"original user neighbor\n")
        before = sorted(self.project.rglob("*"))
        with self.prepare() as owner:
            original = preparation._state(owner)
            value = namespace._require_registration(owner, original)
            self.assertEqual(owner.plan.project_namespace, value.identity.uri)
            self.assertEqual(
                owner.plan.document["plan"]["project_namespace"], value.identity.uri
            )
            self.assertEqual(value.census.tree.root, self.project)
            self.assertIn("unclaimed", {n for n, _, _ in value.census.tree.files})
            self.assertTrue(any(c is value.census for c in original.ledger.censuses))
            owner.require_current()
        self.assertEqual(sorted(self.project.rglob("*")), before)
        self.assertEqual(foreign.read_bytes(), b"original user neighbor\n")

    def test_late_git_read_cannot_adopt_a_new_project_neighbor(self):
        observe = transaction.observe_layout_git_controls
        foreign = self.project / "late-neighbor"
        changed = []

        def change(*args, **kwargs):
            result = observe(*args, **kwargs)
            if not changed:
                foreign.write_bytes(b"concurrent user file\n")
                changed.append(True)
            return result

        with self.assertRaises(ValueError):
            with mock.patch.object(transaction, "observe_layout_git_controls", change):
                with self.prepare():
                    self.fail("late project membership became an acknowledged baseline")
        self.assertEqual(changed, [True])
        self.assertEqual(foreign.read_bytes(), b"concurrent user file\n")
        self.assertFalse(self.destination.exists())

    def test_same_byte_neighbor_replacement_revokes_original_preparation(self):
        foreign = self.project / "original-neighbor"
        foreign.write_bytes(b"same bytes\n")
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                staged = self.state / "replacement"
                staged.write_bytes(foreign.read_bytes())
                os.replace(staged, foreign)
                owner.require_current()
        self.assertEqual(foreign.read_bytes(), b"same bytes\n")
        self.assertFalse(self.destination.exists())

    def test_unknown_entry_before_admission_refuses_before_control_creation(self):
        foreign = self.project / "late-neighbor"
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                foreign.write_bytes(b"concurrent input\n")
                with self.pool(owner.plan) as (pool, _journal):
                    with mock.patch.object(
                        pool,
                        "stage_marker",
                        side_effect=AssertionError(
                            "control before original namespace closure"
                        ),
                    ):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail("changed complete namespace admitted")
        self.assertEqual(foreign.read_bytes(), b"concurrent input\n")
        self.assertFalse((self.project / "litai/layout.pending").exists())
        self.assertFalse(self.destination.exists())

    def test_original_namespace_projects_only_actual_control_publications(self):
        from literate_ai.adapters.retained_layout_control_publication import (
            _publication_history,
        )

        with self.inspecting() as (owner, phase, pool, _journal):
            value = namespace._require_registration(owner, preparation._state(owner))
            self.assertIsNotNone(value.controlled)
            self.assertIs(value.controls, phase.controls)
            self.assertIs(value.publications, _publication_history(pool))
            self.assertEqual(value.identity.uri, owner.plan.project_namespace)
            original = {n for n, _ in value.native}
            controlled = {n for n, _ in value.controlled_native}
            actual = {
                r.path.relative_to(self.project).as_posix()
                for r in value.publications
                if r.path.is_relative_to(self.project)
            }
            self.assertEqual(controlled - original, actual)
            self.assertNotIn("litai/layout.pending", original)
            self.assertIn("litai/layout.pending", controlled)
            owner.require_current()

    def test_publication_callback_cannot_add_a_fresh_namespace_baseline(self):
        foreign = self.project / "concurrent-input"
        changed = []
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, journal):
                    append = journal.append

                    def change(kind, data):
                        result = append(kind, data)
                        if kind == "control-publication-observed" and not changed:
                            foreign.write_bytes(b"preserve foreign input\n")
                            changed.append(True)
                        return result

                    with (
                        mock.patch.object(journal, "append", change),
                        mock.patch.object(
                            transaction, "move_layout_entry_exclusive"
                        ) as move,
                    ):
                        try:
                            with owner.source_phase(
                                pool,
                                acknowledged_plan_identity=owner.plan.identity,
                                allow_host_execution=True,
                            ):
                                self.fail(
                                    "foreign file adopted after control publication"
                                )
                        finally:
                            move.assert_not_called()
        self.assertEqual(changed, [True])
        self.assertEqual(foreign.read_bytes(), b"preserve foreign input\n")
        self.assertTrue((self.source / "app.py").is_file())

    def test_changed_namespace_plan_binding_refuses_before_native_inventory(self):
        with self.assertRaisesRegex(ValueError, "acknowledged namespace plan"):
            with self.prepare() as owner:
                object.__setattr__(
                    owner.plan, "project_namespace", "sha256:" + "0" * 64
                )
                with mock.patch.object(
                    transaction,
                    "_inventory",
                    side_effect=AssertionError(
                        "inventory before namespace authentication"
                    ),
                ):
                    owner.require_current()

    def test_replaced_namespace_record_refuses_before_native_inventory(self):
        with self.assertRaisesRegex(ValueError, "namespace record changed"):
            with self.prepare() as owner:
                selected = namespace._PREPARATIONS[owner]
                namespace._OWNERS[selected] = replace(namespace._OWNERS[selected])
                with mock.patch.object(
                    transaction,
                    "_inventory",
                    side_effect=AssertionError(
                        "inventory before namespace authentication"
                    ),
                ):
                    owner.require_current()

    def test_forged_string_comparison_cannot_replace_namespace_binding(self):
        class Forged(str):
            def __ne__(self, other):
                return False

        with self.assertRaisesRegex(ValueError, "acknowledged namespace plan"):
            with self.prepare() as owner:
                object.__setattr__(owner.plan, "project_namespace", Forged("forged"))
                with mock.patch.object(
                    transaction,
                    "_inventory",
                    side_effect=AssertionError(
                        "inventory before namespace authentication"
                    ),
                ):
                    owner.require_current()

    def test_replaced_nested_roster_refuses_before_reserializing_or_inventory(self):
        with self.assertRaisesRegex(ValueError, "namespace facts changed"):
            with self.prepare() as owner:
                selected = namespace._PREPARATIONS[owner]
                value = namespace._OWNERS[selected]
                object.__setattr__(value.census.tree, "files", ())
                with (
                    mock.patch.object(
                        namespace,
                        "_seal",
                        side_effect=AssertionError(
                            "serialization before reference authentication"
                        ),
                    ),
                    mock.patch.object(
                        transaction,
                        "_inventory",
                        side_effect=AssertionError(
                            "inventory before reference authentication"
                        ),
                    ),
                ):
                    owner.require_current()

    def test_ended_namespace_binding_cannot_reopen_or_reselect(self):
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                selected = namespace._PREPARATIONS[owner]
                namespace._PREPARATIONS.pop(owner)
                with owner._reads():
                    namespace.observe_project_namespace(owner)
        self.assertNotIn(selected, namespace._OWNERS)
        with self.assertRaises(ValueError):
            _ = selected.identity

    def test_original_namespace_survives_genuine_transaction_and_terminal(self):
        with self.prepare() as owner:
            identity = owner.plan.project_namespace
            with self.pool(owner.plan) as (pool, _journal):
                with owner.source_phase(
                    pool,
                    acknowledged_plan_identity=owner.plan.identity,
                    allow_host_execution=True,
                ) as phase:
                    with phase.complete_partition(
                        budget=self.input_budget,
                        maximum_metadata_bytes=self.metadata_limit,
                    ) as partition:
                        self.assertEqual(partition.census.tree.root, self.project)
                        phase.move_source()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
                owner.require_current()
            owner.require_current()
            self.assertEqual(owner.plan.project_namespace, identity)
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse(self.source.exists())

    def test_original_census_cannot_be_resealed_after_acknowledgement(self):
        class StopInspection(Exception):
            pass

        foreign = self.project / "late-foreign-file"
        try:
            with self.prepare() as owner:
                with owner._reads():
                    selected = namespace._PREPARATIONS[owner]
                    before = namespace._OWNERS[selected]
                    foreign.write_bytes(b"preserve concurrent file\n")
                    fresh = before.ledger.capture(self.project)
                    native = before.ledger.native[-1]
                    with self.assertRaisesRegex(
                        ValueError, "immutable original namespace"
                    ):
                        namespace._advance(
                            selected, before, census=fresh, native=native
                        )
                    self.assertIs(namespace._OWNERS[selected], before)
                    self.assertEqual(owner.plan.project_namespace, before.identity.uri)
                    raise StopInspection()
        except StopInspection:
            pass
        self.assertEqual(foreign.read_bytes(), b"preserve concurrent file\n")
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_last_native_callback_cannot_replace_a_nested_namespace_witness(self):
        class StopInspection(Exception):
            pass

        changed = []
        try:
            with self.prepare() as owner:
                selected = namespace._PREPARATIONS[owner]
                value = namespace._OWNERS[selected]
                close = transaction._close_tree

                def change(*args, **kwargs):
                    result = close(*args, **kwargs)
                    if kwargs.get("_namespace_preparation") is owner and not changed:
                        object.__setattr__(value.census.tree, "files", ())
                        changed.append(True)
                    return result

                with mock.patch.object(transaction, "_close_tree", change):
                    with self.assertRaisesRegex(ValueError, "namespace facts changed"):
                        selected.close_native()
                raise StopInspection()
        except StopInspection:
            pass
        self.assertEqual(changed, [True])
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())
