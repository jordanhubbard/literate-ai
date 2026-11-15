"""Actual bounded discovery lifetime; phase/effect admission is not enabled."""

from __future__ import annotations

import os
import threading
import unittest
from contextvars import copy_context
from dataclasses import replace
from unittest import mock

import tests.critical.test_catalog_copy_roles as predecessor_fixtures
import tests.critical.test_retained_layout_transaction as fixtures
from literate_ai.adapters import bounded_role_observation as reads
from literate_ai.adapters import repository_refresh as refresh
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(os.name == "posix", "actual canonical POSIX input observations")
class SourcePreparationTests(unittest.TestCase):
    git = fixtures.RetainedLayoutTransactionTests.git
    init_git = fixtures.RetainedLayoutTransactionTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutTransactionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutTransactionTests.setUp(self)
        self.input_budget = RetainedCargoInputBudget(
            4096, 65536, 4 * 1024**2, 128 * 1024**2
        )

    def prepare(self, **kwargs):
        return preparation.prepared_retained_layout_source_move(
            self.project,
            "retained",
            budget=kwargs.pop("budget", self.input_budget),
            maximum_metadata_bytes=4 * 1024**3,
            **kwargs,
        )

    def test_actual_discovery_is_read_only_and_retains_one_ledger(self):
        before = sorted(self.project.rglob("*"))
        with self.prepare() as owner:
            state = preparation._state(owner)
            self.assertIsNone(reads.current_role_observation())
            self.assertEqual(owner.plan.tree.root, self.source)
            self.assertGreater(owner.usage["files"], owner.plan.tree.file_count)
            self.assertGreaterEqual(
                owner.usage["payload_bytes"], owner.plan.tree.payload_bytes
            )
            identity = owner.identity
            owner.require_current()
            self.assertEqual(owner.identity, identity)
            self.assertIs(preparation._state(owner).ledger, state.ledger)
            self.assertIs(preparation._state(owner).reader, state.reader)
        self.assertEqual(sorted(self.project.rglob("*")), before)
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_metadata_exhaustion_refuses_before_source_capture(self):
        budget = RetainedCargoInputBudget(2, 32768, 4 * 1024**2, 8 * 1024**2)
        with mock.patch.object(
            preparation._Observation,
            "capture",
            side_effect=AssertionError("source capture before input admission"),
        ):
            with self.assertRaises(ValueError):
                with self.prepare(budget=budget):
                    self.fail("unfunded discovery returned")
        self.assertIsNone(reads.current_role_observation())
        self.assertFalse(self.destination.exists())

    def test_tree_capture_uses_remaining_input_budget(self):
        with self.prepare() as owner:
            self.assertLess(
                owner.plan.tree.budget.maximum_files, self.input_budget.maximum_files
            )
            self.assertLess(
                owner.plan.tree.budget.maximum_total_bytes,
                self.input_budget.maximum_total_bytes,
            )
            self.assertEqual(owner.plan.tree.exclusions, ())

    def test_original_physical_input_survives_sequential_read_activations(self):
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                manifest = self.project / "literate.project.json"
                other = self.state / "same-bytes.json"
                other.write_bytes(manifest.read_bytes())
                os.replace(other, manifest)
                owner.require_current()
        with self.assertRaises(ValueError):
            _ = owner.plan
        self.assertTrue((self.project / "literate.project.json").is_file())
        self.assertFalse(self.destination.exists())

    def test_ended_or_constructed_handle_cannot_reopen_preparation(self):
        with self.prepare() as owner:
            saved = owner.identity
        with self.assertRaises(ValueError):
            owner.require_current()
        forged = object.__new__(preparation._SourcePreparation)
        with self.assertRaises(ValueError):
            forged.require_current()
        self.assertIsNotNone(saved)

    def test_copied_activation_cannot_be_replayed_while_operation_stays_live(self):
        with self.prepare() as owner:
            with owner._reads():
                copied = copy_context()
            with self.assertRaisesRegex(ValueError, "activation ended"):
                copied.run(refresh._file, self.project / "literate.project.json")
            owner.require_current()
            self.assertIsNone(reads.current_role_observation())

    def test_read_owner_cannot_do_io_between_activations(self):
        with self.prepare() as owner:
            state = preparation._state(owner)
            with self.assertRaisesRegex(ValueError, "active canonical read scope"):
                state.reader.file(
                    self.project / "literate.project.json", maximum_bytes=1024**2
                )
            owner.require_current()

    def test_foreign_scope_does_not_restart_or_borrow_preparation_budget(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            with self.prepare() as owner:
                with reads.bounded_role_observation(
                    budget=self.input_budget, maximum_metadata_bytes=4 * 1024**3
                ):
                    owner.require_current()
        with self.assertRaises(ValueError):
            _ = owner.usage

    def test_cross_thread_handle_cannot_borrow_original_owner(self):
        with self.prepare() as owner:
            errors = []

            def use():
                try:
                    owner.require_current()
                except ValueError as error:
                    errors.append(str(error))

            thread = threading.Thread(target=use)
            thread.start()
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertIn("foreign", errors[0])
            owner.require_current()

    def test_actual_git_revalidation_keeps_cumulative_input_usage(self):
        self.init_git(commit=True)
        with self.prepare() as owner:
            before = owner.usage
            owner.require_current()
            after = owner.usage
            self.assertGreater(after["payload_bytes"], before["payload_bytes"])
            self.assertGreater(after["entries"], before["entries"])
            self.assertEqual(after["files"], before["files"])

    def test_funded_plan_is_refused_by_unjoined_legacy_effect_entry(self):
        with self.prepare() as owner:
            for plan in (owner.plan, replace(owner.plan)):
                with self.assertRaisesRegex(ValueError, "acknowledgement"):
                    with transaction.retained_layout_source_phase(
                        plan,
                        object(),
                        acknowledged_plan_identity=plan.identity,
                        allow_host_execution=True,
                    ):
                        self.fail("unjoined preparation granted effects")
            self.assertFalse(self.destination.exists())

    def test_unactivated_ledger_cannot_select_funded_planner_path(self):
        ledger = preparation._Observation(
            self.input_budget, 4 * 1024**3, (self.project,)
        )
        with self.assertRaisesRegex(TypeError, "active source preparation ledger"):
            transaction.plan_retained_layout_source_move(
                self.project, "retained", budget=self.input_budget, _observation=ledger
            )

    def test_original_input_and_buffer_policy_cannot_change_between_activations(self):
        for field in ("budget", "metadata", "reserve"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "read policy changed"):
                    with self.prepare() as owner:
                        ledger = preparation._state(owner).ledger
                        if field == "budget":
                            ledger.budget = replace(
                                ledger.budget,
                                maximum_entries=ledger.budget.maximum_entries + 1,
                            )
                        else:
                            setattr(ledger, field, getattr(ledger, field) + 1)
                        owner.require_current()

    def test_equal_matching_policy_keeps_existing_shared_ledger_contract(self):
        ledger = preparation._Observation(
            self.input_budget, 4 * 1024**3, (self.project,)
        )
        with reads.bounded_role_observation(
            budget=replace(self.input_budget),
            maximum_metadata_bytes=4 * 1024**3,
            _ledger=ledger,
        ):
            self.assertIsNotNone(
                refresh._file(self.project / "literate.project.json").content
            )

    def test_source_operation_ending_during_payload_close_revokes_result(self):
        context = self.prepare()
        owner = context.__enter__()
        raw = refresh._raw_file
        closed = []

        def end(path, **kwargs):
            result = raw(path, **kwargs)
            if not closed:
                closed.append(True)
                context.__exit__(RuntimeError, RuntimeError("interrupted"), None)
            return result

        try:
            with self.assertRaises(ValueError):
                with mock.patch.object(refresh, "_raw_file", end):
                    owner.require_current()
            self.assertEqual(closed, [True])
            with self.assertRaises(ValueError):
                _ = owner.plan
        finally:
            context.__exit__(RuntimeError, RuntimeError("cleanup"), None)
        self.assertFalse(self.destination.exists())

    def test_late_metadata_payload_callback_cannot_change_source_before_return(self):
        context = self.prepare()
        owner = context.__enter__()
        raw = refresh._raw_file
        require = preparation._require_prepared
        armed, changed = [], []

        def arm(*args, **kwargs):
            result = require(*args, **kwargs)
            armed.append(True)
            return result

        def change(path, **kwargs):
            result = raw(path, **kwargs)
            if armed and not changed:
                changed.append(True)
                source = self.source / "app.py"
                source.write_bytes(source.read_bytes() + b"\n# late change\n")
            return result

        try:
            with self.assertRaisesRegex(ValueError, "source native"):
                with mock.patch.object(preparation, "_require_prepared", arm):
                    with mock.patch.object(refresh, "_raw_file", change):
                        owner.require_current()
            self.assertEqual(changed, [True])
        finally:
            context.__exit__(RuntimeError, RuntimeError("cleanup"), None)
        self.assertTrue(
            (self.source / "app.py").read_bytes().endswith(b"late change\n")
        )

    def test_late_metadata_callback_cannot_insert_pending_control(self):
        context = self.prepare()
        owner = context.__enter__()
        raw = refresh._raw_file
        require = preparation._require_prepared
        armed, changed = [], []
        pending = transaction.layout_pending_control_path(self.project)

        def arm(*args, **kwargs):
            result = require(*args, **kwargs)
            armed.append(True)
            return result

        def change(path, **kwargs):
            result = raw(path, **kwargs)
            if armed and not changed:
                changed.append(True)
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign pending control\n")
            return result

        try:
            with self.assertRaisesRegex(ValueError, "pending"):
                with mock.patch.object(preparation, "_require_prepared", arm):
                    with mock.patch.object(refresh, "_raw_file", change):
                        owner.require_current()
            self.assertEqual(changed, [True])
        finally:
            context.__exit__(RuntimeError, RuntimeError("cleanup"), None)
        self.assertEqual(pending.read_bytes(), b"foreign pending control\n")

    def test_final_namespace_scan_cannot_change_previously_closed_metadata(self):
        context = self.prepare()
        owner = context.__enter__()
        absence = preparation._absence
        changed = []
        manifest = self.project / "literate.project.json"

        def change(*args, **kwargs):
            result = absence(*args, **kwargs)
            if not changed:
                changed.append(True)
                manifest.write_bytes(manifest.read_bytes() + b"\n")
            return result

        try:
            with self.assertRaises(ValueError):
                with mock.patch.object(preparation, "_absence", change):
                    owner.require_current()
            self.assertEqual(changed, [True])
        finally:
            context.__exit__(RuntimeError, RuntimeError("cleanup"), None)
        self.assertTrue(manifest.read_bytes().endswith(b"\n\n"))

    def test_destination_parent_membership_closes_after_source_namespace(self):
        context = self.prepare()
        owner = context.__enter__()
        close = preparation._close_original_native
        inventory = transaction._inventory
        armed, changed = [], []
        foreign = self.project / "new-destination-neighbor"

        def arm(*args, **kwargs):
            armed.append(True)
            return close(*args, **kwargs)

        def change(*args, **kwargs):
            result = inventory(*args, **kwargs)
            if armed and not changed:
                changed.append(True)
                foreign.mkdir()
            return result

        try:
            with self.assertRaises(ValueError):
                with mock.patch.object(preparation, "_close_original_native", arm):
                    with mock.patch.object(transaction, "_inventory", change):
                        owner.require_current()
            self.assertEqual(changed, [True])
        finally:
            context.__exit__(RuntimeError, RuntimeError("cleanup"), None)
        self.assertTrue(foreign.is_dir())
        self.assertFalse(self.destination.exists())


@unittest.skipUnless(os.name == "posix", "genuine native predecessor handoffs")
class SourcePreparationPredecessorTests(unittest.TestCase):
    git = predecessor_fixtures.CatalogCopyRoleTests.git
    init_git = predecessor_fixtures.CatalogCopyRoleTests.init_git
    updated = predecessor_fixtures.CatalogCopyRoleTests.updated
    copying = predecessor_fixtures.CatalogCopyRoleTests.copying
    pool = predecessor_fixtures.CatalogCopyRoleTests.pool
    phase = predecessor_fixtures.CatalogCopyRoleTests.phase

    @classmethod
    def setUpClass(cls):
        predecessor_fixtures.CatalogCopyRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        predecessor_fixtures.CatalogCopyRoleTests.setUp(self)
        self.update_budget = self.copy_budget
        self.update_sequence = 0

    def prepare(self, **kwargs):
        return preparation.prepared_retained_layout_source_move(
            self.project,
            "retained",
            budget=self.copy_budget,
            maximum_metadata_bytes=kwargs.pop(
                "maximum_metadata_bytes", self.copy_metadata
            ),
            **kwargs,
        )

    def test_actual_framework_usage_and_original_policy_precede_discovery(self):
        # Declare the complete positive policy before the original producer;
        # the successor never enlarges an already-live predecessor allowance.
        with self.updated(
            adopt_added=True, maximum_metadata_bytes=4 * 1024**3
        ) as update:
            usage = preparation._predecessor_usage(update, None)
            with self.assertRaisesRegex(ValueError, "enlarge original predecessor"):
                with self.prepare(
                    framework_update=update, maximum_metadata_bytes=8 * 1024**3
                ):
                    self.fail("enlarged metadata policy admitted")
            with self.prepare(
                framework_update=update, maximum_metadata_bytes=4 * 1024**3
            ) as owner:
                state = preparation._state(owner)
                self.assertEqual(state.predecessor, usage)
                self.assertIsNot(state.ledger.cache, update._cache)
                self.assertGreater(owner.usage["files"], usage.files)
                self.assertEqual(owner.plan.framework_update, update.identity.uri)

    def test_original_two_gib_policy_refuses_complete_namespace_without_effects(self):
        with self.updated(adopt_added=True) as update:
            before = sorted(self.project.rglob("*"))
            usage = preparation._predecessor_usage(update, None)
            self.assertEqual(usage.metadata, 2 * 1024**3)
            with self.assertRaisesRegex(
                ValueError, "shared catalog input allowance exhausted"
            ):
                with self.prepare(
                    framework_update=update, maximum_metadata_bytes=2 * 1024**3
                ):
                    self.fail("unfunded original project namespace admitted")
            self.assertEqual(sorted(self.project.rglob("*")), before)
            self.assertTrue((self.source / "app.py").is_file())
            self.assertFalse(self.destination.exists())
            self.assertFalse((self.project / "litai/layout.pending").exists())
            self.assertEqual(preparation._predecessor_usage(update, None), usage)
            update.require_current()

    def test_actual_catalog_usage_is_imported_without_old_control_cache(self):
        with self.copying() as catalog:
            catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
            usage = preparation._predecessor_usage(None, catalog)
            with self.prepare(catalog_copy=catalog) as owner:
                state = preparation._state(owner)
                self.assertEqual(state.predecessor, usage)
                self.assertIsNot(
                    state.ledger.cache,
                    predecessor_fixtures.copies._record(catalog, ready=True)[
                        "seal"
                    ].ledger.cache,
                )
                self.assertGreater(owner.usage["files"], usage.files)
                self.assertEqual(owner.plan.catalog_copy, catalog.identity.uri)
                owner.require_current()
        with self.assertRaises(TypeError):
            with self.prepare(catalog_copy=catalog):
                self.fail("ended catalog supplied a preparation")

    def test_actual_joined_framework_and_catalog_usage_is_debited_once(self):
        with self.updated(adopt_added=True) as update:
            with self.copying(framework_update=update) as catalog:
                catalog.apply(acknowledged_plan_identity=catalog.plan.identity)
                combined = preparation._predecessor_usage(update, catalog)
                debit = preparation._debit_predecessor
                initial = []
                ledgers = []

                def observe(ledger, usage):
                    # Observe the actual import boundary. Canonical authored
                    # discovery reserves metadata before invoking the planner.
                    self.assertEqual(
                        (ledger.files, ledger.records, len(ledger.cache)), (0, 0, 0)
                    )
                    debit(ledger, usage)
                    initial.append((ledger.files, ledger.records, len(ledger.cache)))
                    ledgers.append(ledger)

                with mock.patch.object(preparation, "_debit_predecessor", observe):
                    with self.prepare(
                        framework_update=update, catalog_copy=catalog
                    ) as owner:
                        self.assertEqual(
                            initial, [(combined.files, combined.entries, 0)]
                        )
                        self.assertEqual(
                            preparation._state(owner).predecessor, combined
                        )
                        self.assertEqual(len(ledgers), 1)
                        self.assertIs(preparation._state(owner).ledger, ledgers[0])
                        self.assertIsNone(reads.current_role_observation())
                # Finish the genuine consuming flow before either enclosing
                # producer ends; the read-only preparation does not spend them.
                plan = transaction.plan_retained_layout_source_move(
                    self.project,
                    "retained",
                    budget=self.budget,
                    framework_update=update,
                    catalog_copy=catalog,
                )
                with self.pool(plan) as (pool, _journal):
                    with self.phase(plan, pool) as phase:
                        with phase.complete_partition(
                            budget=self.copy_budget,
                            maximum_metadata_bytes=self.copy_metadata,
                            framework_update=update,
                            catalog_copy=catalog,
                        ):
                            phase.move_source()
                        phase.publish_metadata(self.metadata)
                        phase.finalize_controls(self.retired)

    def test_saved_producer_labels_cannot_debit_or_admit_preparation(self):
        with self.assertRaises(TypeError):
            with self.prepare(catalog_copy={"state": "ready"}):
                self.fail("saved labels admitted")


if __name__ == "__main__":
    unittest.main()
