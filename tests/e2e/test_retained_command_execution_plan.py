"""Executable renewal uses a fresh closed form, preserving saved planning forms."""

from __future__ import annotations

import unittest
from unittest import mock

from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from tests.e2e import test_retained_command_renewal as fixtures


class RetainedCommandExecutionPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RetainedCommandRenewalTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedCommandRenewalTests.setUp(self)

    write_selection = fixtures.RetainedCommandRenewalTests.write_selection
    snapshot = fixtures.RetainedCommandRenewalTests.snapshot

    def plan(self):
        return readmission.plan_retained_command_renewal_execution(
            self.root, command_selection=self.selection_path
        )

    def reopen(self, plan):
        return readmission.reopen_retained_command_renewal_execution_plan(
            self.root,
            canonical_json_bytes(plan),
            reviewed_plan_identity=plan["plan_identity"],
            command_selection=self.selection_path,
        )

    def test_complete_execution_plan_reopens_without_commands_or_mutation(self):
        before = self.snapshot()
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch.object(
                readmission, "_parity_report", side_effect=AssertionError
            ),
        ):
            plan = self.plan()
            self.assertEqual(self.reopen(plan), plan)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(plan["apply_supported"])
        self.assertFalse(plan["command_renewal"]["execution_performed"])
        self.assertEqual(plan["command_renewal"]["compilation_coverage"], "unknown")
        self.assertEqual(
            plan["schema"], "literate-ai/retained-harness-readmission-plan@3"
        )

    def test_planning_only_form_cannot_be_reinterpreted_as_execution(self):
        plan = readmission.plan_retained_harness_readmission(
            self.root, command_selection=self.selection_path
        )
        self.assertFalse(plan["apply_supported"])
        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            self.reopen(plan)

    def test_rehashed_unknown_nested_grant_refuses(self):
        plan = self.plan()
        plan["new_inventory"]["permission"] = {"network": True}
        plan.pop("plan_identity")
        plan["plan_identity"] = canonical_identity(plan).uri
        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            self.reopen(plan)

    def test_changed_command_file_refuses_reviewed_plan(self):
        plan = self.plan()
        self.selection["components"][0]["commands"][0]["command"] = "make build"
        self.write_selection()
        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            self.reopen(plan)

    def test_malformed_and_oversized_saved_forms_refuse_before_current_planning(self):
        plan = self.plan()
        encoded = canonical_json_bytes(plan)
        for content in (
            encoded + b"\n\n",
            b'{"schema":"a","schema":"b"}',
            b" " * (2 * 1024**2 + 1),
        ):
            with self.subTest(size=len(content)):
                with mock.patch.object(
                    readmission,
                    "_current_command_execution_plan",
                    side_effect=AssertionError,
                ):
                    with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                        readmission.reopen_retained_command_renewal_execution_plan(
                            self.root,
                            content,
                            reviewed_plan_identity=plan["plan_identity"],
                            command_selection=self.selection_path,
                        )

    def test_executable_form_is_not_accepted_by_saved_planning_reader(self):
        plan = self.plan()
        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            readmission.reopen_retained_command_renewal_plan(
                self.root,
                canonical_json_bytes(plan),
                reviewed_plan_identity=plan["plan_identity"],
                command_selection=self.selection_path,
            )
