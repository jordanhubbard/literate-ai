"""Known original receipt bytes belong to refined renewal's shared budget.

The fixture uses the source-development parent and real original unittest
harness. It supplies no installed distribution or release qualification.
"""

from __future__ import annotations

import json
import os
import shutil
import unittest
from dataclasses import replace
from unittest import mock

from literate_ai.adapters import monorepo_components as components
from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters.monorepo_adoption import MonorepoAdoptionError
from literate_ai.adapters.project_initialization import record_project_authority_review
from literate_ai.contracts.projects import ProjectScaleLimits
from literate_ai.projects import ProjectConfigurationStore
from tests.e2e import test_refined_command_readmission as fixtures
from tests.support.fixtures_test_retained_harness_receipts import _invoke


@unittest.skipUnless(
    os.name == "posix" and shutil.which("make") and shutil.which("cc"),
    "native POSIX Make/C compiler prerequisites are required",
)
class RefinedCommandBudgetTests(unittest.TestCase):
    write_selection = fixtures.RefinedCommandReadmissionTests.write_selection
    snapshot = fixtures.RefinedCommandReadmissionTests.snapshot
    plan = fixtures.RefinedCommandReadmissionTests.plan

    @classmethod
    def setUpClass(cls):
        fixtures.RefinedCommandReadmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RefinedCommandReadmissionTests.setUp(self)

    def test_real_prior_receipt_counts_before_any_renewal_harness(self):
        total_limit = 2 * 1024**2
        store = ProjectConfigurationStore(self.root)
        original = store.read()
        store.update(
            original,
            replace(
                original.definition,
                scale_limits=ProjectScaleLimits(
                    pinned_input_files=2048,
                    pinned_input_total_bytes=total_limit,
                    catalog_files=2048,
                    catalog_entries=4096,
                    catalog_total_bytes=total_limit,
                ),
            ),
        )
        record_project_authority_review(self.root)
        candidate = self.base / "original-receipt.json"
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
        status, envelope = _invoke(
            "project", "test-receipt", "require-current", "--project", str(self.root)
        )
        self.assertEqual(status, 0, envelope)
        manifest = json.loads((self.root / "literate.project.json").read_bytes())
        receipt_name = manifest["test_receipt"]
        receipt = (self.root / receipt_name).read_bytes()
        self.assertGreater(len(receipt), 2)

        initial = self.plan()
        self.assertIn(receipt_name, initial["old_documents"])
        old_metadata_bytes = sum(
            (self.root / name).stat().st_size
            for name in initial["old_documents"]
            if name != receipt_name
        )
        fitting_metadata_bytes = total_limit - len(receipt) // 2
        padding_size = fitting_metadata_bytes - old_metadata_bytes
        self.assertGreater(padding_size, 0, "fixture metadata already fills the budget")
        wrapper = self.root / readmission.HARNESS_WRAPPER_FILENAME
        wrapper_bytes = wrapper.read_bytes()
        # The canonical receipt consumer accepts the wrapper as exact arbitrary
        # bytes; Make permits comments. Do not change any canonical JSON report
        # or invent execution observations merely to enlarge this valid input.
        self.assertGreaterEqual(padding_size, 3)
        comment = b"#" + b"x" * (padding_size - 2) + b"\n"
        padded = wrapper_bytes + comment
        self.assertLess(len(padded), total_limit)
        self.assertTrue(padded.startswith(wrapper_bytes))
        self.assertEqual(len(padded) - len(wrapper_bytes), padding_size)
        wrapper.write_bytes(padded)
        self.assertLess(fitting_metadata_bytes, total_limit)
        self.assertGreater(fitting_metadata_bytes + len(receipt), total_limit)
        # The genuine previous receipt may become stale, but the modified
        # wrapper must remain consumable through the ordinary public reader.
        status, envelope = _invoke(
            "project", "test-receipt", "require-current", "--project", str(self.root)
        )
        self.assertNotEqual(status, 0, envelope)
        self.assertIn("stale", envelope["error"]["code"])

        before = self.snapshot()
        with (
            mock.patch.object(
                readmission, "_baseline_report", side_effect=AssertionError
            ),
            mock.patch.object(
                readmission, "_parity_report", side_effect=AssertionError
            ),
            mock.patch.object(
                components, "run_component_retained_harness", side_effect=AssertionError
            ),
        ):
            with self.assertRaises(
                (readmission.RetainedHarnessReadmissionError, MonorepoAdoptionError)
            ) as refused:
                self.plan()
        self.assertIn(
            refused.exception.code,
            {
                "retained_harness.publication_limit",
                "monorepo.input_limit",
                "monorepo.input_too_large",
            },
        )
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.root / receipt_name).read_bytes(), receipt)
