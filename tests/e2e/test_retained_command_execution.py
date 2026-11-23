"""Selected renewal uses the existing acknowledged readmission owner."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from literate_ai.adapters import retained_harness_readmission as readmission
from tests.e2e import test_retained_command_renewal as fixtures
from tests.support.fixtures_test_retained_harness_receipts import _invoke


class RetainedCommandExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RetainedCommandRenewalTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedCommandRenewalTests.setUp(self)

    write_selection = fixtures.RetainedCommandRenewalTests.write_selection

    def plan(self):
        return readmission.plan_retained_command_renewal_execution(
            self.root, command_selection=self.selection_path
        )

    def apply(self, plan, acknowledge=True):
        return readmission.apply_retained_harness_readmission(
            self.root,
            expected_plan_identity=plan["plan_identity"],
            acknowledge=acknowledge,
            command_selection=self.selection_path,
            timeout_seconds=1800,
            execution_worker=None,
            worker_catalog_identity=None,
        )

    def test_public_readonly_selection_plan_does_not_invoke_commands(self):
        before = (self.root / readmission.INVENTORY).read_bytes()
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch(
                "literate_ai.cli.dispatch.maybe_host_self_update",
                side_effect=AssertionError,
            ),
            mock.patch(
                "literate_ai.cli.dispatch.ensure_user_mcp_catalog",
                side_effect=AssertionError,
            ),
            mock.patch(
                "literate_ai.cli.dispatch.PerformanceRecorder",
                side_effect=AssertionError,
            ),
            mock.patch(
                "literate_ai.cli.dispatch.journal_mutagenic_event",
                side_effect=AssertionError,
            ),
        ):
            status, envelope = _invoke(
                "project",
                "retained-harness",
                "readmit",
                "--project",
                str(self.root),
                "--command-selection",
                str(self.selection_path),
            )
        self.assertEqual(status, 0, envelope)
        self.assertEqual(
            envelope["result"]["schema"],
            "literate-ai/retained-harness-readmission-plan@3",
        )
        self.assertEqual((self.root / readmission.INVENTORY).read_bytes(), before)

    def test_explicit_command_renews_inventory_and_preserves_unselected_test(self):
        before = (self.root / readmission.INVENTORY).read_bytes()
        old = json.loads(before)
        plan = self.plan()
        result = self.apply(plan)
        self.assertTrue(result["applied"])
        current = json.loads((self.root / readmission.INVENTORY).read_bytes())
        self.assertEqual(
            current["commands"]["build"]["command"], "make -f Makefile package"
        )
        self.assertEqual(
            [s for s in current["stages"] if s["id"].startswith("test")],
            [s for s in old["stages"] if s["id"].startswith("test")],
        )
        historical = (
            self.root / result["prior_evidence_history"] / readmission.INVENTORY
        )
        self.assertEqual(historical.read_bytes(), before)

    def test_unacknowledged_and_stale_requests_refuse_before_commands(self):
        plan = self.plan()
        with mock.patch.object(
            readmission, "_baseline_report", side_effect=AssertionError
        ):
            with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                self.apply(plan, acknowledge=False)
            self.selection["components"][0]["commands"][0]["command"] = "make build"
            self.write_selection()
            with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                self.apply(plan)

    def test_selection_change_after_baseline_refuses_before_wrapper_execution(self):
        plan = self.plan()
        before = (self.root / readmission.INVENTORY).read_bytes()
        original = readmission._baseline_report

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.selection["components"][0]["commands"][0]["command"] = "make build"
            self.write_selection()
            return result

        with (
            mock.patch.object(readmission, "_baseline_report", side_effect=changed),
            mock.patch.object(
                readmission, "_parity_report", side_effect=AssertionError
            ),
        ):
            with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                self.apply(plan)
        self.assertEqual((self.root / readmission.INVENTORY).read_bytes(), before)

    def test_failed_selected_command_preserves_old_evidence_and_source(self):
        self.selection["components"][0]["commands"][0]["command"] = (
            "make -f Makefile no-such-target"
        )
        self.write_selection()
        plan = self.plan()
        before = {
            name: ((self.root / name).read_bytes(), (self.root / name).stat().st_ino)
            for name in plan["old_documents"]
        }
        source = (self.source / "app.py").read_bytes()
        with self.assertRaises((ValueError, RuntimeError)):
            self.apply(plan)
        self.assertEqual((self.source / "app.py").read_bytes(), source)
        self.assertEqual(
            {
                name: (
                    (self.root / name).read_bytes(),
                    (self.root / name).stat().st_ino,
                )
                for name in before
            },
            before,
        )

    def test_late_selection_change_restores_metadata_and_preserves_selection(
        self,
    ):
        plan = self.plan()
        before = {
            name: ((self.root / name).read_bytes(), (self.root / name).stat().st_ino)
            for name in plan["old_documents"]
        }
        original = readmission.record_project_authority_review

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.selection["components"][0]["commands"][0]["command"] = "make build"
            self.write_selection()
            return result

        with mock.patch.object(
            readmission, "record_project_authority_review", side_effect=changed
        ):
            with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                self.apply(plan)
        self.assertEqual(
            {
                name: (
                    (self.root / name).read_bytes(),
                    (self.root / name).stat().st_ino,
                )
                for name in before
            },
            before,
        )
        self.assertEqual(
            json.loads(self.selection_path.read_bytes())["components"][0]["commands"][
                0
            ]["command"],
            "make build",
        )
