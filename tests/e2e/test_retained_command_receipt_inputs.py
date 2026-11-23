"""Preserve an ordinary retained receipt without inferring genuine test coverage."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from literate_ai.adapters import retained_harness_readmission as readmission
from tests.e2e import test_retained_command_renewal as fixtures
from tests.support.fixtures_test_retained_harness_receipts import _invoke


class RetainedCommandReceiptInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RetainedCommandRenewalTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedCommandRenewalTests.setUp(self)
        # The existing harness fixture prints its test summary. This exercises
        # real receipt-owner plumbing, not genuine test or native qualification;
        # the separate native fixture preserves two actual original unit tests.
        candidate = self.base / "prior-candidate.json"
        for operation in ("run-retained", "update"):
            status, envelope = _invoke(
                "project",
                "test-receipt",
                operation,
                str(candidate),
                "--project",
                str(self.root),
            )
            self.assertEqual(status, 0, envelope)
        manifest = json.loads((self.root / "literate.project.json").read_bytes())
        self.receipt_name = manifest["test_receipt"]
        self.receipt = self.root / self.receipt_name
        self.original = self.receipt.read_bytes()

    write_selection = fixtures.RetainedCommandRenewalTests.write_selection

    def plan(self):
        return readmission.plan_retained_command_renewal_execution(
            self.root, command_selection=self.selection_path
        )

    def apply(self, plan):
        return readmission.apply_retained_harness_readmission(
            self.root,
            expected_plan_identity=plan["plan_identity"],
            acknowledge=True,
            command_selection=self.selection_path,
            timeout_seconds=1800,
            execution_worker=None,
            worker_catalog_identity=None,
        )

    def test_prior_receipt_is_bound_and_archived_without_rewriting_it(self):
        plan = self.plan()
        self.assertIn(self.receipt_name, plan["old_documents"])
        result = self.apply(plan)
        self.assertEqual(self.receipt.read_bytes(), self.original)
        status, envelope = _invoke(
            "project", "test-receipt", "require-current", "--project", str(self.root)
        )
        self.assertNotEqual(status, 0, envelope)
        self.assertIn("stale", envelope["error"]["code"])
        self.assertEqual(
            (
                self.root / result["prior_evidence_history"] / self.receipt_name
            ).read_bytes(),
            self.original,
        )

    def test_changed_prior_receipt_refuses_before_any_command(self):
        plan = self.plan()
        self.receipt.write_bytes(self.original + b"\n")
        with mock.patch.object(
            readmission, "_baseline_report", side_effect=AssertionError
        ):
            with self.assertRaises((ValueError, RuntimeError)):
                self.apply(plan)

    def test_receipt_appearing_after_review_refuses_before_commands(self):
        self.receipt.unlink()
        plan = self.plan()
        self.assertEqual(plan["prior_test_receipt"]["state"], "missing")
        self.receipt.write_bytes(self.original)
        with mock.patch.object(
            readmission, "_baseline_report", side_effect=AssertionError
        ):
            with self.assertRaises((ValueError, RuntimeError)):
                self.apply(plan)
        self.assertEqual(self.receipt.read_bytes(), self.original)
