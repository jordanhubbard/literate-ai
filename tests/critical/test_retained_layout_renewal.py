"""Genuine readmission after an actual committed nonroot layout transaction."""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

import tests.critical.test_retained_layout_finalization as fixtures
from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters.component_lock_application import (
    current_component_lock_identity,
)
from literate_ai.adapters.retained_harness_receipts import (
    RetainedHarnessReceiptError,
    _implementation_root,
    _load_retained_documents,
    _require_qualified_parity,
)
from literate_ai.adapters.retained_layout import RETAINED_LAYOUT_PATH
from literate_ai.projects import load_project


@unittest.skipUnless(os.name == "posix", "Actual POSIX layout transaction")
class RetainedLayoutRenewalTests(unittest.TestCase):
    plan = fixtures.RetainedLayoutFinalizationTests.plan
    pool = fixtures.RetainedLayoutFinalizationTests.pool
    phase = fixtures.RetainedLayoutFinalizationTests.phase

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutFinalizationTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutFinalizationTests.setUp(self)

    def relocate(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.phase(plan, pool) as phase:
                phase.move_source()
                phase.publish_metadata(self.metadata)
                phase.finalize_controls(self.retired)
        self.assertFalse(self.source.exists())
        self.source = self.destination
        return plan

    def renewal(self):
        return readmission.plan_retained_harness_readmission(self.project)

    def apply(self, plan):
        return readmission.apply_retained_harness_readmission(
            self.project,
            expected_plan_identity=plan["plan_identity"],
            acknowledge=True,
            timeout_seconds=1800,
            execution_worker=None,
            worker_catalog_identity=None,
        )

    def evidence(self):
        return {
            name: (self.project / name).read_bytes()
            for name in (
                readmission.INVENTORY,
                readmission.BASELINE,
                readmission.PARITY,
                readmission.HARNESS_WRAPPER_FILENAME,
                readmission.LIFT_SHIFT,
                RETAINED_LAYOUT_PATH,
            )
        }

    def test_actual_move_then_genuine_readmission_renews_selected_current_lock(self):
        self.relocate()
        before = self.evidence()
        plan = self.renewal()
        self.assertEqual(plan["implementation"], "retained")
        self.assertTrue(plan["changes_required"])
        self.assertEqual(self.evidence(), before)
        result = self.apply(plan)
        self.assertTrue(result["applied"])
        for name in (readmission.BASELINE, readmission.PARITY):
            report = json.loads((self.project / name).read_bytes())
            self.assertEqual(report["state"], "passed")
            self.assertTrue(report["phases"])
            self.assertEqual(report["layout_readmission"], plan["layout_readmission"])
            self.assertTrue(all(p["exit_code"] == 0 for p in report["phases"]))
        current_component_lock_identity(self.project / plan["wrapper_component"])
        prior = self.project / result["prior_evidence_history"]
        for name in (readmission.LIFT_SHIFT, RETAINED_LAYOUT_PATH):
            self.assertEqual((prior / name).read_bytes(), before[name])
            self.assertEqual((self.project / name).read_bytes(), before[name])
        self.assertFalse(self.renewal()["changes_required"])

    def test_old_passed_evidence_does_not_admit_new_structural_location(self):
        # Earn real qualification at the old coordinate before moving. A skipped
        # initialization baseline would test the wrong refusal boundary.
        self.apply(self.renewal())
        project = load_project(self.project)
        original_documents = _load_retained_documents(project)
        _require_qualified_parity(original_documents)
        self.assertEqual(_implementation_root(project, original_documents), self.source)
        self.relocate()
        documents = _load_retained_documents(load_project(self.project))
        with self.assertRaises(RetainedHarnessReceiptError):
            _require_qualified_parity(documents)
            _implementation_root(load_project(self.project), documents)

    def test_pending_transaction_refuses_before_inventory_or_execution(self):
        self.relocate()
        pending = self.project / "litai/layout.pending"
        pending.parent.mkdir(exist_ok=True)
        pending.write_bytes(b"unfinished relocation\n")
        with mock.patch.object(readmission, "inspect_harness") as inspect:
            with self.assertRaisesRegex(
                readmission.RetainedHarnessReadmissionError, "layout_pending"
            ):
                self.renewal()
            inspect.assert_not_called()

    def test_changed_declaration_refuses_old_acknowledgement_before_execution(self):
        self.relocate()
        plan = self.renewal()
        path = self.project / RETAINED_LAYOUT_PATH
        path.write_bytes(path.read_bytes() + b"\n")
        with mock.patch.object(readmission, "_baseline_report") as execute:
            with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                self.apply(plan)
            execute.assert_not_called()

    def test_layout_change_during_real_parity_preserves_foreign_input_and_old_reports(
        self,
    ):
        self.relocate()
        plan = self.renewal()
        before = self.evidence()
        parity = readmission._parity_report
        path = self.project / RETAINED_LAYOUT_PATH

        def changed(*args, **kwargs):
            report = parity(*args, **kwargs)
            path.write_bytes(before[RETAINED_LAYOUT_PATH] + b"\n")
            return report

        with mock.patch.object(readmission, "_parity_report", side_effect=changed):
            with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                self.apply(plan)
        after = self.evidence()
        for name, content in before.items():
            if name != RETAINED_LAYOUT_PATH:
                self.assertEqual(after[name], content)
        self.assertEqual(path.read_bytes(), before[RETAINED_LAYOUT_PATH] + b"\n")

    def test_pending_after_first_publication_restores_only_written_evidence(self):
        self.relocate()
        plan = self.renewal()
        before = self.evidence()
        store = readmission.FilesystemConversionAuthorityStore
        publish = store._atomic_write
        pending = self.project / "litai/layout.pending"
        changed = False

        def inserted(path, content):
            nonlocal changed
            result = publish(path, content)
            if path == self.project / readmission.BASELINE and not changed:
                changed = True
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign pending\n")
            return result

        with mock.patch.object(store, "_atomic_write", side_effect=inserted):
            with self.assertRaisesRegex(
                readmission.RetainedHarnessReadmissionError, "layout_pending"
            ):
                self.apply(plan)
        self.assertTrue(changed)
        self.assertEqual(self.evidence(), before)
        self.assertEqual(pending.read_bytes(), b"foreign pending\n")

    def test_final_layout_read_refuses_late_pending_insertion(self):
        self.relocate()
        plan = self.renewal()
        declaration = (self.project / RETAINED_LAYOUT_PATH).read_bytes()
        pending = self.project / "litai/layout.pending"
        identity = readmission._identity
        inserted = False

        def changed(value):
            nonlocal inserted
            result = identity(value)
            if value == declaration and not inserted:
                inserted = True
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign pending at final layout read\n")
            return result

        with mock.patch.object(readmission, "_identity", side_effect=changed):
            with self.assertRaisesRegex(
                readmission.RetainedHarnessReadmissionError, "layout_pending"
            ):
                readmission._require_layout_current(self.project, plan)
        self.assertTrue(inserted)
        self.assertEqual(
            pending.read_bytes(), b"foreign pending at final layout read\n"
        )

    def test_final_history_pending_refuses_success_and_preserves_marker(
        self,
    ):
        self.relocate()
        plan = self.renewal()
        before = self.evidence()
        pending = self.project / "litai/layout.pending"
        inspect = readmission.inspect_harness
        identity = readmission._identity
        source_observations = 0
        in_layout_check = False
        layout_check = readmission._require_layout_current
        inserted = False

        def checked(*args, **kwargs):
            nonlocal in_layout_check
            in_layout_check = True
            try:
                return layout_check(*args, **kwargs)
            finally:
                in_layout_check = False

        def inspected(*args, **kwargs):
            nonlocal source_observations
            result = inspect(*args, **kwargs)
            source_observations += 1
            return result

        def changed(value):
            nonlocal inserted
            result = identity(value)
            if (
                source_observations >= 2
                and not in_layout_check
                and value == before[readmission.LIFT_SHIFT]
                and not inserted
            ):
                inserted = True
                pending.parent.mkdir(exist_ok=True)
                pending.write_bytes(b"foreign pending at final history read\n")
            return result

        with (
            mock.patch.object(readmission, "inspect_harness", side_effect=inspected),
            mock.patch.object(
                readmission, "_require_layout_current", side_effect=checked
            ),
            mock.patch.object(readmission, "_identity", side_effect=changed),
        ):
            with self.assertRaisesRegex(
                readmission.RetainedHarnessReadmissionError, "layout_pending"
            ):
                self.apply(plan)
        self.assertTrue(inserted)
        self.assertEqual(self.evidence(), before)
        self.assertEqual(
            pending.read_bytes(), b"foreign pending at final history read\n"
        )

    def test_failed_real_baseline_does_not_publish_layout_admission(self):
        self.relocate()
        (self.source / "Makefile").write_bytes(b"build:\n\t@exit 1\ntest:\n\t@exit 1\n")
        plan = self.renewal()
        before = self.evidence()
        with self.assertRaises((ValueError, RuntimeError)):
            self.apply(plan)
        self.assertEqual(self.evidence(), before)
        self.assertNotIn(b'"layout_readmission"', before[readmission.BASELINE])
