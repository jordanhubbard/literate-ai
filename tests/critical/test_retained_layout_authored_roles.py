"""Actual canonical authored endpoints in the original source operation."""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
import tests.critical.test_retained_layout_source_finalization as finalization_fixtures
from literate_ai.adapters import retained_layout_source_admission as admission
from literate_ai.adapters import retained_layout_source_authored as authored
from literate_ai.adapters import retained_layout_source_preparation as preparation
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.retained_layout import RETAINED_LAYOUT_PATH
from literate_ai.contracts import ProjectInitializationBaseline


@unittest.skipUnless(os.name == "posix", "actual POSIX source authored roles")
class AuthoredRoleTests(unittest.TestCase):
    prepare = fixtures.SourceAdmissionTests.prepare
    pool = fixtures.SourceAdmissionTests.pool
    inspecting = fixtures.SourceAdmissionTests.inspecting

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=131072)

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def test_selected_lock_and_metadata_have_actual_authored_roles(self):
        lock = ComponentLockStore(self.source.parent).path
        self.assertTrue(lock.is_file())
        baseline = ProjectInitializationBaseline.from_dict(
            json.loads(
                (self.project / ".literate/initialization-baseline.json").read_bytes()
            )
        )
        name = lock.relative_to(self.project).as_posix()
        self.assertIn(name, {item.path for item in baseline.files})
        unknown = self.project / "unclaimed"
        unknown.mkdir()
        (unknown / "component.lock.json").write_bytes(b"unclaimed stale evidence\n")
        (unknown / "component.md").write_bytes(b"unclaimed document\n")
        original_lock = lock.read_bytes()
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with phase.complete_partition(
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            ) as partition:
                roles = dict(partition.roles)
                self.assertEqual(roles[name], "authored")
                self.assertEqual(roles["literate.project.json"], "authored")
                self.assertEqual(roles["unclaimed/component.lock.json"], "unclaimed")
                self.assertEqual(roles["unclaimed/component.md"], "unclaimed")
        self.assertEqual(lock.read_bytes(), original_lock)

    def test_selected_optional_lock_absence_is_not_recreated_from_initializer_history(
        self,
    ):
        lock = ComponentLockStore(self.source.parent).path
        lock.unlink()
        with self.inspecting() as (_owner, phase, _pool, _journal):
            with phase.complete_partition(
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            ) as partition:
                self.assertNotIn(
                    lock.relative_to(self.project).as_posix(), dict(partition.roles)
                )
                self.assertEqual(
                    dict(partition.roles)["literate.project.json"], "authored"
                )
        self.assertFalse(lock.exists())

    def test_actual_authored_owner_survives_metadata_and_closes_as_read_only_terminal(
        self,
    ):
        lock = ComponentLockStore(self.source.parent).path
        lock.unlink()
        with self.prepare() as owner:
            original = preparation._state(owner)
            with self.pool(owner.plan) as (pool, _journal):
                with owner.source_phase(
                    pool,
                    acknowledged_plan_identity=owner.plan.identity,
                    allow_host_execution=True,
                ) as phase:
                    roles = admission._phase_record(phase).authored
                    identity = roles.identity
                    self.assertNotIn(
                        lock.relative_to(self.project).as_posix(), roles.paths
                    )
                    with phase.complete_partition(
                        budget=self.input_budget,
                        maximum_metadata_bytes=self.metadata_limit,
                    ) as partition:
                        self.assertIs(partition._authored, roles)
                        phase.move_source()
                    phase.publish_metadata(self.metadata)
                    roles.require_current()
                    self.assertEqual(roles.identity, identity)
                    self.assertIn(RETAINED_LAYOUT_PATH, roles.paths)
                    self.assertIs(preparation._state(owner).reader, original.reader)
                    result = phase.finalize_controls(self.retired)
                    self.assertEqual(result["state"], "committed-unqualified")
                    self.assertFalse(result["qualified"])
                with self.assertRaises(ValueError):
                    roles.require_current()
                owner.require_current()
            owner.require_current()
        self.assertFalse(lock.exists())
        self.assertTrue((self.destination / "app.py").is_file())

    def test_original_smaller_profile_refuses_finalization_before_control_effects(self):
        from literate_ai.adapters import retained_layout_source_finalization as controls

        # Preserve the original finite policy. The newly funded source graph
        # now exhausts it at finalization preflight, before any control receipt.
        self.input_budget = replace(self.input_budget, maximum_entries=65536)
        lock = ComponentLockStore(self.source.parent).path
        lock.unlink()
        with mock.patch.object(controls, "_preflight_control_receipt") as receipt:
            with self.assertRaisesRegex(
                ValueError, "finalization preflight exceeds original allowance"
            ):
                with self.prepare() as owner:
                    original = preparation._state(owner)
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with phase.complete_partition(
                                budget=self.input_budget,
                                maximum_metadata_bytes=self.metadata_limit,
                            ):
                                phase.move_source()
                            phase.publish_metadata(self.metadata)
                            phase.finalize_controls(self.retired)
            receipt.assert_not_called()
        self.assertEqual(original.ledger.budget.maximum_entries, 65536)
        self.assertTrue(phase._metadata_published)
        self.assertTrue((self.project / "litai/layout.pending").is_file())
        self.assertEqual(list(self.retired.iterdir()), [])
        self.assertFalse(lock.exists())
        self.assertTrue((self.destination / "app.py").is_file())

    def test_committed_control_receipt_refuses_after_original_allowance_is_reserved(
        self,
    ):
        from literate_ai.adapters import retained_layout_source_finalization as controls
        from literate_ai.contracts.identity import canonical_json_bytes

        lock = ComponentLockStore(self.source.parent).path
        lock.unlink()
        original = controls._preflight_control_receipt
        refused = []
        reserved = []

        def receipt(reservations, data):
            # At the real final pending-barrier retirement, reserve from the
            # same original ledger after its durable commit decision. Leave one
            # fewer record than the mandatory 256-record native receipt window.
            # Earlier normalizations retain their ordinary original allowance.
            if not reserved:
                for phase, value in controls._FINALIZATIONS.items():
                    if phase.controls.reservations is reservations:
                        if value.pending != (
                            "retire",
                            self.project / "litai/layout.pending",
                        ):
                            continue
                        self.assertTrue(phase._committed)
                        ledger = value.admission.original.ledger
                        remaining = ledger.budget.maximum_entries - ledger.records
                        self.assertGreater(remaining, 256)
                        ledger.charge_records(remaining - 255, 0)
                        reserved.append(ledger)
            try:
                return original(reservations, data)
            except ValueError:
                for phase, value in controls._FINALIZATIONS.items():
                    if phase.controls.reservations is reservations:
                        ledger = value.admission.original.ledger
                        self.assertIs(ledger, reserved[0])
                        self.assertEqual(ledger.budget.maximum_entries, 131072)
                        self.assertEqual(ledger.metadata, 4 * 1024**3)
                        self.assertEqual(
                            value.pending,
                            ("retire", self.project / "litai/layout.pending"),
                        )
                        self.assertTrue(phase._committed)
                        self.assertLess(len(canonical_json_bytes(data)) + 128, 65536)
                        self.assertLess(
                            ledger.budget.maximum_entries - ledger.records, 256
                        )
                        self.assertGreaterEqual(
                            ledger.metadata - ledger.charged, 4096 * 256
                        )
                        refused.append(True)
                raise

        with mock.patch.object(controls, "_preflight_control_receipt", receipt):
            with self.assertRaises(transaction.LayoutCommitOutcomeError) as caught:
                with self.prepare() as owner:
                    with self.pool(owner.plan) as (pool, _journal):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=owner.plan.identity,
                            allow_host_execution=True,
                        ) as phase:
                            with phase.complete_partition(
                                budget=self.input_budget,
                                maximum_metadata_bytes=self.metadata_limit,
                            ):
                                phase.move_source()
                            phase.publish_metadata(self.metadata)
                            phase.finalize_controls(self.retired)
        self.assertEqual(refused, [True])
        self.assertEqual(len(reserved), 1)
        self.assertIs(caught.exception.committed, True)
        self.assertFalse(lock.exists())
        self.assertTrue((self.destination / "app.py").is_file())

    def test_forged_saved_authored_owner_cannot_borrow_original_operation(self):
        with self.inspecting() as (owner, phase, _pool, _journal):
            roles = admission._phase_record(phase).authored
            before = owner.usage
            forged = object.__new__(type(roles))
            with self.assertRaises(ValueError):
                forged.require_current()
            with self.assertRaises(ValueError):
                authored._Capture(owner)
            self.assertEqual(owner.usage, before)
            roles.require_current()

    def test_changed_authored_input_after_role_discovery_refuses_before_movement(self):
        original = authored._join_partition
        changed = []
        target = self.source.parent / "component.md"

        def change(*arguments, **keywords):
            result = original(*arguments, **keywords)
            target.write_bytes(
                target.read_bytes() + b"\nchanged after actual role discovery\n"
            )
            changed.append(True)
            return result

        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with mock.patch.object(authored, "_join_partition", change):
                            with phase.complete_partition(
                                budget=self.input_budget,
                                maximum_metadata_bytes=self.metadata_limit,
                            ):
                                self.fail("changed authored input admitted")
        self.assertEqual(changed, [True])
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())
        self.assertIn(b"changed after actual role discovery", target.read_bytes())

    def test_late_optional_lock_creation_cannot_become_an_original_observation(self):
        lock = ComponentLockStore(self.source.parent).path
        lock.unlink()
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with phase.complete_partition(
                            budget=self.input_budget,
                            maximum_metadata_bytes=self.metadata_limit,
                        ):
                            lock.write_bytes(b"foreign late lock\n")
                            phase.move_source()
        self.assertEqual(lock.read_bytes(), b"foreign late lock\n")
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())

    def test_missing_unrelated_initializer_file_is_not_waived_as_authored(self):
        target = self.project / "docs/user/getting-started.md"
        self.assertTrue(target.is_file())
        target.unlink()
        with self.assertRaises((ValueError, OSError)):
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with phase.complete_partition(
                            budget=self.input_budget,
                            maximum_metadata_bytes=self.metadata_limit,
                        ):
                            self.fail("missing unrelated initializer file was waived")
        self.assertFalse(target.exists())
        self.assertFalse(self.destination.exists())

    def test_canonical_store_is_not_reconstructed_after_original_discovery(self):
        with self.prepare() as owner:
            with mock.patch.object(
                authored,
                "ComponentLockStore",
                side_effect=AssertionError(
                    "canonical store reconstructed after discovery"
                ),
            ):
                owner.require_current()

    def test_actual_in_project_canonical_store_endpoint_is_the_observed_lock(self):
        cell = self.project / "matrix-cell"
        cell.mkdir(mode=0o700)
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(cell)}):
            lock = ComponentLockStore(self.source.parent).path
            lock.parent.mkdir(parents=True)
            lock.write_bytes(b"stale selected-cell lock evidence\n")
            with self.inspecting() as (owner, phase, _pool, _journal):
                observed = next(item for item in owner.plan.inputs if item.path == lock)
                self.assertEqual(
                    observed.content, b"stale selected-cell lock evidence\n"
                )
                with phase.complete_partition(
                    budget=self.input_budget,
                    maximum_metadata_bytes=self.metadata_limit,
                ) as partition:
                    self.assertEqual(
                        dict(partition.roles)[
                            lock.relative_to(self.project).as_posix()
                        ],
                        "authored",
                    )

    def test_store_selection_is_frozen_after_original_discovery(self):
        with self.prepare() as owner:
            lock = ComponentLockStore(self.source.parent).path
            with mock.patch.dict(
                os.environ, {"LITAI_MATRIX_CELL_ROOT": str(self.root / "external")}
            ):
                owner.require_current()
                self.assertEqual(owner.plan.authored_lock, lock)

    def test_canonical_cell_inside_source_refuses_before_effects(self):
        cell = self.source / "matrix-cell"
        cell.mkdir(mode=0o700)
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(cell)}):
            with self.assertRaises(ValueError):
                with self.prepare():
                    self.fail("canonical storage inside moving source was admitted")
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_absent_canonical_lock_under_actual_source_case_alias_refuses(self):
        alias = self.source.with_name(self.source.name.swapcase())
        if alias == self.source or not alias.is_dir():
            self.skipTest("actual case-insensitive source alias unavailable")
        self.assertEqual(alias.stat().st_ino, self.source.stat().st_ino)
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(alias)}):
            lock = ComponentLockStore(self.source.parent).path
            self.assertFalse(lock.exists())
            with self.assertRaisesRegex(ValueError, "lock storage overlaps"):
                with self.prepare():
                    self.fail("absent lock admitted under actual moving source alias")
        self.assertTrue(self.source.is_dir())
        self.assertFalse(self.destination.exists())

    def test_external_canonical_store_uses_actual_selection_without_legacy_constructor(
        self,
    ):
        cell = self.root / "external-cell"
        cell.mkdir(mode=0o700)
        with mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(cell)}):
            expected = ComponentLockStore(self.source.parent).path
            with mock.patch.object(
                authored, "ComponentLockStore", wraps=ComponentLockStore
            ) as store:
                with self.prepare() as owner:
                    selection = preparation._state(owner).authored.selection
                    self.assertEqual(owner.plan.authored_lock, expected)
                    self.assertEqual(
                        owner.plan.authored_storage, selection.identity.uri
                    )
                    owner.require_current()
                    store.observe_selection.assert_called_once_with(
                        owner, self.source.parent
                    )
                self.assertFalse(store.called)
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_authored_hardlink_to_unknown_role_refuses_without_reclassification(self):
        lock = ComponentLockStore(self.source.parent).path
        unknown = self.project / "unknown-lock-link"
        os.link(lock, unknown)
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with phase.complete_partition(
                            budget=self.input_budget,
                            maximum_metadata_bytes=self.metadata_limit,
                        ):
                            self.fail(
                                "shared unknown hardlink acquired authored ownership"
                            )
        self.assertEqual(lock.stat().st_ino, unknown.stat().st_ino)
        self.assertFalse(self.destination.exists())

    def test_authored_owner_revocation_in_final_native_callback_prevents_movement(self):
        revoked = []
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        with phase.complete_partition(
                            budget=self.input_budget,
                            maximum_metadata_bytes=self.metadata_limit,
                        ):
                            roles = admission._phase_record(phase).authored
                            root = self.project.stat()
                            original = transaction._from_stat

                            def revoke(node):
                                result = original(node)
                                if not revoked and (node.st_dev, node.st_ino) == (
                                    root.st_dev,
                                    root.st_ino,
                                ):
                                    authored._OWNERS.pop(roles)
                                    revoked.append(True)
                                return result

                            with mock.patch.object(transaction, "_from_stat", revoke):
                                phase.move_source()
        self.assertEqual(revoked, [True])
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())

    def test_authored_owner_ending_during_descriptor_teardown_refuses_terminal_success(
        self,
    ):
        revoked = []
        with self.assertRaises(Exception) as caught:
            with self.prepare() as owner:
                with self.pool(owner.plan) as (pool, _journal):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        roles = admission._phase_record(phase).authored
                        with phase.complete_partition(
                            budget=self.input_budget,
                            maximum_metadata_bytes=self.metadata_limit,
                        ):
                            phase.move_source()
                        phase.publish_metadata(self.metadata)
                        phase.finalize_controls(self.retired)

                        def revoke():
                            authored._OWNERS.pop(roles)
                            revoked.append(True)

                        phase._resources.callback(revoke)
        self.assertEqual(revoked, [True])
        self.assertIs(getattr(caught.exception, "committed", None), True)


@unittest.skipUnless(
    os.name == "posix", "actual canonical/update/catalog authored join"
)
class CombinedAuthoredRoleTests(unittest.TestCase):
    git = finalization_fixtures.CombinedSourceFinalizationTests.git
    init_git = finalization_fixtures.CombinedSourceFinalizationTests.init_git
    commit_source = finalization_fixtures.CombinedSourceFinalizationTests.commit_source
    copying = finalization_fixtures.CombinedSourceFinalizationTests.copying
    pool = finalization_fixtures.CombinedSourceFinalizationTests.pool
    updated = finalization_fixtures.CombinedSourceFinalizationTests.updated

    @classmethod
    def setUpClass(cls):
        finalization_fixtures.CombinedSourceFinalizationTests.setUpClass.__func__(cls)

    def setUp(self):
        finalization_fixtures.CombinedSourceFinalizationTests.setUp(self)
        self.copy_budget = replace(self.copy_budget, maximum_entries=262144)

    def test_real_original_authored_update_and_catalog_owners_complete_together(self):
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
                            roles = admission._phase_record(phase).authored
                            with phase.complete_partition(
                                budget=self.copy_budget,
                                maximum_metadata_bytes=self.copy_metadata,
                                framework_update=update,
                                catalog_copy=catalog,
                            ) as partition:
                                self.assertEqual(
                                    dict(partition.roles)["literate.project.json"],
                                    "authored",
                                )
                                self.assertIn(
                                    "imported", dict(partition.roles).values()
                                )
                                phase.move_source()
                            phase.publish_metadata(self.metadata)
                            roles.require_current()
                            phase.finalize_controls(self.retired)
                        owner.require_current()
                    self.assertIs(preparation._state(owner).reader, original.reader)
                    owner.require_current()
        self.assertTrue((self.destination / "app.py").is_file())
