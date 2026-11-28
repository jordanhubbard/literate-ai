"""Real structural source renewal before relocated admission is earned."""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_renewal as fixtures
from literate_ai.adapters import retained_evidence_migration as migration
from literate_ai.adapters import retained_scope_refresh as refresh
from literate_ai.adapters.project_initialization import (
    ProjectInitializationError,
    record_project_authority_review,
)
from literate_ai.adapters.retained_harness_receipts import (
    RetainedHarnessReceiptError,
    run_retained_harness_receipt,
)
from literate_ai.adapters.retained_layout_renewal import observe_retained_layout_renewal
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore, ProjectError, load_project


@unittest.skipUnless(os.name == "posix", "actual POSIX layout transaction")
class RetainedLayoutStructuralConsumerTests(unittest.TestCase):
    plan = fixtures.RetainedLayoutRenewalTests.plan
    pool = fixtures.RetainedLayoutRenewalTests.pool
    phase = fixtures.RetainedLayoutRenewalTests.phase
    relocate = fixtures.RetainedLayoutRenewalTests.relocate
    renewal = fixtures.RetainedLayoutRenewalTests.renewal
    apply = fixtures.RetainedLayoutRenewalTests.apply
    evidence = fixtures.RetainedLayoutRenewalTests.evidence

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutRenewalTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutRenewalTests.setUp(self)

    def refresh(self, plan):
        return refresh.apply_retained_scope_refresh(
            self.project, expected_plan_identity=plan["plan_identity"], acknowledge=True
        )

    def test_actual_unqualified_move_refresh_then_genuine_readmission_and_receipt(self):
        self.relocate()
        (self.source / "new.py").write_bytes(b"print('new source')\n")
        before = self.evidence()
        plan = refresh.plan_retained_scope_refresh(self.project)
        self.assertEqual(plan["implementation"], "retained")
        self.assertIn("new.py", plan["added"])
        self.assertFalse(plan["execution_performed"])
        self.assertTrue(plan["requalification_required"])
        self.assertEqual(self.evidence(), before)
        result = self.refresh(plan)
        self.assertTrue(result["applied"])
        for name, content in before.items():
            if name != refresh.INVENTORY:
                self.assertEqual((self.project / name).read_bytes(), content)
        with self.assertRaises(RetainedHarnessReceiptError):
            run_retained_harness_receipt(
                load_project(self.project),
                candidate_path=self.root / "unqualified.json",
                evidence_path=self.root / "unqualified-evidence.json",
                worker_id="local",
                timeout_seconds=60,
            )
        self.apply(self.renewal())
        receipt = run_retained_harness_receipt(
            load_project(self.project),
            candidate_path=self.root / "fresh.json",
            evidence_path=self.root / "fresh-evidence.json",
            worker_id="local",
            timeout_seconds=60,
        )
        self.assertEqual(receipt["tests"], 2)

    def test_pending_layout_refuses_before_source_capture(self):
        self.relocate()
        before = self.evidence()
        pending = self.project / "litai/layout.pending"
        pending.parent.mkdir(exist_ok=True)
        pending.write_bytes(b"foreign pending\n")
        with mock.patch.object(refresh, "capture_retained_source_scope") as capture:
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                refresh.plan_retained_scope_refresh(self.project)
            capture.assert_not_called()
        self.assertEqual(self.evidence(), before)

    def test_changed_layout_refuses_old_acknowledgement(self):
        self.relocate()
        (self.source / "new.py").write_bytes(b"new\n")
        plan = refresh.plan_retained_scope_refresh(self.project)
        path = self.project / ".literate/retained-layout.json"
        path.write_bytes(path.read_bytes() + b"\n")
        before = self.evidence()
        with self.assertRaises(ValueError):
            self.refresh(plan)
        self.assertEqual(self.evidence(), before)

    def test_pending_after_inventory_publication_restores_only_written_evidence(self):
        self.relocate()
        (self.source / "new.py").write_bytes(b"new\n")
        plan = refresh.plan_retained_scope_refresh(self.project)
        before = self.evidence()
        pending = self.project / "litai/layout.pending"
        store = refresh.FilesystemConversionAuthorityStore
        publish = store._atomic_write
        inserted = False

        def changed(path, content):
            nonlocal inserted
            result = publish(path, content)
            if path == self.project / refresh.INVENTORY and not inserted:
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign late pending\n")
                inserted = True
            return result

        with mock.patch.object(store, "_atomic_write", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                self.refresh(plan)
        self.assertTrue(inserted)
        self.assertEqual(self.evidence(), before)
        self.assertEqual(pending.read_bytes(), b"foreign late pending\n")

    def test_structural_observation_has_no_admission_and_expires_on_input_change(self):
        self.relocate()
        observed = observe_retained_layout_renewal(self.project)
        self.assertEqual(observed.layout.implementation_root, self.source)
        observed.require_current()
        lift = self.project / ".literate/legacy-lift-shift.json"
        value = json.loads(lift.read_bytes())
        value["state"] = "failed"
        lift.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            observed.require_current()

    def test_migration_backfills_current_unqualified_source_without_new_admission(self):
        self.relocate()
        (self.source / "new.py").write_bytes(b"new source\n")
        path = self.project / refresh.INVENTORY
        value = json.loads(path.read_bytes())
        value.pop("source_scope")
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        before = self.evidence()
        result = migration.migrate_retained_evidence(self.project)
        self.assertIn(refresh.INVENTORY, result.migrated)
        current = json.loads(path.read_bytes())
        self.assertIn("new.py", current["source_scope"]["paths"])
        for name, content in before.items():
            if name != refresh.INVENTORY:
                self.assertEqual((self.project / name).read_bytes(), content)
        with self.assertRaises(RetainedHarnessReceiptError):
            run_retained_harness_receipt(
                load_project(self.project),
                candidate_path=self.root / "migration.json",
                evidence_path=self.root / "migration-evidence.json",
                worker_id="local",
                timeout_seconds=60,
            )

    def test_pending_migration_preserves_all_historical_bytes(self):
        self.relocate()
        parity = self.project / ".literate/legacy-wrapper-parity.json"
        value = json.loads(parity.read_bytes())
        value["schema"] = migration.LEGACY_WRAPPER_PARITY_SCHEMA_V1
        parity.write_bytes(canonical_json_bytes(value) + b"\n")
        path = self.project / refresh.INVENTORY
        value = json.loads(path.read_bytes())
        value.pop("source_scope")
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        pending = self.project / "litai/layout.pending"
        pending.parent.mkdir(exist_ok=True)
        pending.write_bytes(b"foreign migration barrier\n")
        before = self.evidence()
        result = migration.migrate_retained_evidence(self.project)
        self.assertEqual(result.migrated, ())
        self.assertEqual(self.evidence(), before)

    def test_layout_changed_during_backfill_refuses_inventory_publication(self):
        self.relocate()
        path = self.project / refresh.INVENTORY
        value = json.loads(path.read_bytes())
        value.pop("source_scope")
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        before_inventory = path.read_bytes()
        declaration = self.project / ".literate/retained-layout.json"
        before_declaration = declaration.read_bytes()
        capture = migration.backfill_harness_inventory_source_scope

        def changed(*args, **kwargs):
            result = capture(*args, **kwargs)
            declaration.write_bytes(before_declaration + b"\n")
            return result

        with mock.patch.object(
            migration, "backfill_harness_inventory_source_scope", side_effect=changed
        ):
            with self.assertRaises(ValueError):
                migration.migrate_retained_evidence(self.project)
        self.assertEqual(path.read_bytes(), before_inventory)
        self.assertEqual(declaration.read_bytes(), before_declaration + b"\n")

    def _missing_scope(self):
        self.relocate()
        path = self.project / refresh.INVENTORY
        value = json.loads(path.read_bytes())
        value.pop("source_scope")
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        return path

    def test_migration_preserves_inventory_changed_after_original_parse(self):
        path = self._missing_scope()
        read = migration._json_input
        foreign = None

        def changed(current):
            nonlocal foreign
            result = read(current)
            if current == path:
                foreign = canonical_json_bytes({**result[1], "foreign": "preserve"})
                path.write_bytes(foreign)
            return result

        with mock.patch.object(migration, "_json_input", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "evidence changed"):
                migration.migrate_retained_evidence(self.project)
        self.assertIsNotNone(foreign)
        self.assertEqual(path.read_bytes(), foreign)

    def test_pending_during_last_inventory_native_compare_refuses_publication(self):
        path = self._missing_scope()
        before = path.read_bytes()
        pending = self.project / "litai/layout.pending"
        signature = migration._signature
        inserted = False

        def changed(current):
            nonlocal inserted
            result = signature(current)
            if current == path and not inserted:
                inserted = True
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign final barrier\n")
            return result

        with mock.patch.object(migration, "_signature", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                migration.migrate_retained_evidence(self.project)
        self.assertTrue(inserted)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(pending.read_bytes(), b"foreign final barrier\n")

    def test_schema_only_migration_refuses_pending_after_transform(self):
        self.relocate()
        path = self.project / ".literate/legacy-wrapper-parity.json"
        value = json.loads(path.read_bytes())
        value["schema"] = migration.LEGACY_WRAPPER_PARITY_SCHEMA_V1
        before = canonical_json_bytes(value) + b"\n"
        path.write_bytes(before)
        pending = self.project / "litai/layout.pending"
        transform = migration.migrate_legacy_wrapper_parity_document

        def changed(document):
            result = transform(document)
            pending.parent.mkdir(exist_ok=True)
            pending.write_bytes(b"foreign schema barrier\n")
            return result

        with mock.patch.object(
            migration, "migrate_legacy_wrapper_parity_document", side_effect=changed
        ):
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                migration.migrate_retained_evidence(self.project)
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue(pending.exists())

    def test_source_change_during_final_layout_read_refuses_refresh_success(self):
        self.relocate()
        (self.source / "new.py").write_bytes(b"new\n")
        plan = refresh.plan_retained_scope_refresh(self.project)
        before = self.evidence()
        real_members = refresh._members
        real_observe = refresh.observe_retained_layout_renewal
        real_publish = refresh.FilesystemConversionAuthorityStore._atomic_write
        published = armed = changed = False

        def publish(path, content):
            nonlocal published
            result = real_publish(path, content)
            if path == self.project / refresh.INVENTORY:
                published = True
            return result

        def members(*args, **kwargs):
            nonlocal armed
            result = real_members(*args, **kwargs)
            if published:
                armed = True
            return result

        def observe(*args, **kwargs):
            nonlocal changed
            result = real_observe(*args, **kwargs)
            if armed and not changed:
                changed = True
                path = self.source / "app.py"
                path.write_bytes(path.read_bytes() + b"\n# foreign edit\n")
            return result

        with (
            mock.patch.object(
                refresh.FilesystemConversionAuthorityStore,
                "_atomic_write",
                side_effect=publish,
            ),
            mock.patch.object(refresh, "_members", side_effect=members),
            mock.patch.object(
                refresh, "observe_retained_layout_renewal", side_effect=observe
            ),
        ):
            with self.assertRaisesRegex(ValueError, "source changed"):
                self.refresh(plan)
        self.assertTrue(changed)
        self.assertEqual(self.evidence(), before)
        self.assertTrue(
            (self.source / "app.py").read_bytes().endswith(b"# foreign edit\n")
        )

    def test_schema_only_migration_without_layout_or_lift_remains_supported(self):
        project = self.root / "schema-only"
        metadata = project / ".literate"
        metadata.mkdir(parents=True)
        parity = metadata / "legacy-wrapper-parity.json"
        parity.write_bytes(
            canonical_json_bytes(
                {
                    "schema": migration.LEGACY_WRAPPER_PARITY_SCHEMA_V1,
                    "state": "passed",
                    "historical": "preserved",
                }
            )
        )
        result = migration.migrate_retained_evidence(project)
        self.assertEqual(result.migrated, (".literate/legacy-wrapper-parity.json",))
        current = json.loads(parity.read_bytes())
        self.assertEqual(current["schema"], migration.HARNESS_PARITY_SCHEMA)
        self.assertEqual(current["historical"], "preserved")

    def test_migration_pending_inside_actual_review_read_preserves_marker(self):
        self._missing_scope()
        (self.source / "new.py").write_bytes(b"new source\n")
        adapter = refresh.FilesystemProjectValidationAdapter
        real_review = adapter.documentation_review
        pending = self.project / "litai/layout.pending"
        before = review_path = None

        def review(instance, *args, **kwargs):
            nonlocal before, review_path
            result = real_review(instance, *args, **kwargs)
            if before is None:
                review_path = self.project / result["document"]
                before = review_path.read_bytes()
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign nested review barrier\n")
            return result

        with mock.patch.object(adapter, "documentation_review", review):
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                migration.migrate_retained_evidence(self.project)
        self.assertIsNotNone(before)
        self.assertEqual(review_path.read_bytes(), before)
        self.assertTrue(pending.exists())

    def test_migration_pending_inside_actual_policy_read_preserves_manifest(self):
        self._missing_scope()
        (self.source / "new.py").write_bytes(b"new source\n")
        manifest = self.project / "literate.project.json"
        before = manifest.read_bytes()
        pending = self.project / "litai/layout.pending"
        real_update = ProjectConfigurationStore.update
        real_read = ProjectConfigurationStore._read_manifest
        armed = inserted = False

        def update(store, *args, **kwargs):
            nonlocal armed
            armed = True
            return real_update(store, *args, **kwargs)

        def read(store, path):
            nonlocal inserted
            result = real_read(store, path)
            if armed and not inserted:
                inserted = True
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign nested policy barrier\n")
            return result

        with (
            mock.patch.object(ProjectConfigurationStore, "update", update),
            mock.patch.object(ProjectConfigurationStore, "_read_manifest", read),
        ):
            with self.assertRaisesRegex(ValueError, "pending relocation"):
                migration.migrate_retained_evidence(self.project)
        self.assertTrue(inserted)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertTrue(pending.exists())

    def test_policy_publication_guard_preserves_intervening_manifest_edit(self):
        store = ProjectConfigurationStore(self.project)
        original = store.read()
        foreign = original.content + b"\n"

        def changed():
            store.path.write_bytes(foreign)

        with self.assertRaisesRegex(ProjectError, "changed during publication"):
            store.update(
                original,
                replace(original.definition, project_id="new-identity"),
                require_current=changed,
            )
        self.assertEqual(store.path.read_bytes(), foreign)

    def test_review_publication_guard_preserves_intervening_review_edit(self):
        store = ProjectConfigurationStore(self.project)
        original = store.read()
        store.update(original, replace(original.definition, project_id="new-identity"))
        review = refresh.FilesystemProjectValidationAdapter().documentation_review(
            self.project
        )
        path = self.project / review["document"]
        foreign = path.read_bytes() + b"\nForeign review text.\n"

        def changed():
            path.write_bytes(foreign)

        with self.assertRaisesRegex(
            ProjectInitializationError, "could not be recorded"
        ):
            record_project_authority_review(self.project, require_current=changed)
        self.assertEqual(path.read_bytes(), foreign)
