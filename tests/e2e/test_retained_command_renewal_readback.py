"""Saved renewal plans must match reviewed intent and freshly observed inputs."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from tests.e2e import test_retained_command_renewal as fixtures


class RetainedCommandRenewalReadbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RetainedCommandRenewalTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedCommandRenewalTests.setUp(self)

    write_selection = fixtures.RetainedCommandRenewalTests.write_selection
    plan = fixtures.RetainedCommandRenewalTests.plan
    snapshot = fixtures.RetainedCommandRenewalTests.snapshot

    def reopen(self, content, reviewed_identity):
        return readmission.reopen_retained_command_renewal_plan(
            self.root,
            content,
            reviewed_plan_identity=reviewed_identity,
            command_selection=self.selection_path,
        )

    @staticmethod
    def encode_rehashed(plan):
        plan.pop("plan_identity")
        plan["plan_identity"] = canonical_identity(plan).uri
        return canonical_json_bytes(plan), plan["plan_identity"]

    def test_complete_current_plan_reopens_without_mutation_or_execution(self):
        plan = self.plan()
        before = self.snapshot()
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch.object(
                readmission, "_parity_report", side_effect=AssertionError
            ),
        ):
            self.assertEqual(
                self.reopen(canonical_json_bytes(plan), plan["plan_identity"]), plan
            )
            self.assertEqual(
                self.reopen(canonical_json_bytes(plan) + b"\n", plan["plan_identity"]),
                plan,
            )
        self.assertEqual(self.snapshot(), before)

    def test_source_changed_after_review_refuses(self):
        plan = self.plan()
        (self.source / "app.py").write_text("print('changed after review')\n")
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.reopen(canonical_json_bytes(plan), plan["plan_identity"])
        self.assertEqual(caught.exception.code, "retained_harness.plan_stale")

    def test_selection_changed_after_review_refuses(self):
        plan = self.plan()
        self.selection["components"][0]["commands"][0]["command"] = "make test"
        self.write_selection()
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.reopen(canonical_json_bytes(plan), plan["plan_identity"])
        self.assertEqual(caught.exception.code, "retained_harness.plan_stale")

    def test_rehashed_unknown_nested_authority_refuses(self):
        plan = self.plan()
        plan["new_inventory"]["extra_authority"] = {"execute": True}
        content, identity = self.encode_rehashed(plan)
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.reopen(content, identity)
        self.assertEqual(caught.exception.code, "retained_harness.plan_stale")

    def test_rehashed_apply_grant_refuses(self):
        plan = self.plan()
        plan["apply_supported"] = True
        content, identity = self.encode_rehashed(plan)
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.reopen(content, identity)
        self.assertEqual(caught.exception.code, "retained_harness.plan_invalid")

    def test_review_identity_mismatch_refuses(self):
        plan = self.plan()
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.reopen(canonical_json_bytes(plan), "sha256:" + "0" * 64)
        self.assertEqual(caught.exception.code, "retained_harness.plan_stale")

    def test_noncanonical_duplicate_and_oversized_inputs_refuse_before_observation(
        self,
    ):
        plan = self.plan()
        canonical = canonical_json_bytes(plan)
        inputs = [
            json.dumps(plan, indent=2).encode(),
            canonical + b"\n\n",
            b'{"schema":"one","schema":"two"}',
            b" " * (2 * 1024**2 + 1),
        ]
        for content in inputs:
            with self.subTest(content_size=len(content)):
                with mock.patch.object(
                    readmission,
                    "plan_retained_harness_readmission",
                    side_effect=AssertionError("malformed plan reached source"),
                ):
                    with self.assertRaises(
                        readmission.RetainedHarnessReadmissionError
                    ) as caught:
                        self.reopen(content, plan["plan_identity"])
                self.assertEqual(caught.exception.code, "retained_harness.plan_invalid")

    def test_saved_v1_plan_keeps_its_meaning_and_cannot_be_read_as_renewal(self):
        plan = readmission.plan_retained_harness_readmission(self.root)
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.reopen(canonical_json_bytes(plan), plan["plan_identity"])
        self.assertEqual(caught.exception.code, "retained_harness.plan_invalid")

    def test_tampering_without_renewing_identity_refuses(self):
        plan = self.plan()
        reviewed = plan["plan_identity"]
        plan["command_renewal"]["selected_phases"] = ["test"]
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.reopen(canonical_json_bytes(plan), reviewed)
        self.assertEqual(caught.exception.code, "retained_harness.plan_invalid")

    def test_producer_refuses_a_plan_that_cannot_fit_the_saved_input_limit(self):
        path = self.root / readmission.INVENTORY
        inventory = json.loads(path.read_bytes())
        stage = next(s for s in inventory["stages"] if s["id"] == "test")
        stage["command"] = "printf '" + "x" * (2 * 1024**2) + "'"
        inventory["commands"]["test"]["command"] = stage["command"]
        path.write_text(json.dumps(inventory), encoding="utf-8")
        before = self.snapshot()
        with self.assertRaises(readmission.RetainedHarnessReadmissionError) as caught:
            self.plan()
        self.assertEqual(caught.exception.code, "retained_harness.plan_too_large")
        self.assertEqual(self.snapshot(), before)
