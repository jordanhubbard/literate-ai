"""Actual installed-monorepo observations without fabricated execution inputs.

Harness/provider admission remain the maintained explicit fixtures. No consumer
native execution, positive admission or genuine model qualification is inferred.
"""

import time
import unittest

from literate_ai.adapters.authored_retained_cargo_provisioning_monorepo import (
    _capture_provisioning_monorepo,
)
from literate_ai.adapters.authored_retained_cargo_provisioning_source import (
    _capture_authored_provisioning_source,
)
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.support.fixtures_authored_monorepo_completion import (
    authored_monorepo_completion_fixture,
    cleanup_monorepo_completion_template,
    initialize_monorepo_completion_template,
)


class AuthoredProvisioningMonorepoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()
        initialize_monorepo_completion_template()
        cls.addClassCleanup(cleanup_monorepo_completion_template)

    def capture(self, inputs):
        materialized = inputs.materialized
        source = _capture_authored_provisioning_source(
            materialized.current,
            materialized.scratch.context,
            old_output_budget=RetainedCargoOutputBudget(16 * 1024**2, 64 * 1024**2),
        )
        return source, _capture_provisioning_monorepo(source)

    def test_actual_source_counts_and_selected_monorepo_survive_receiving_close(self):
        deadline = time.monotonic() + 900
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            _env,
            close,
            _monorepo,
            _state,
        ):
            source, observed = self.capture(inputs)
            self.assertTrue(observed.present)
            self.assertEqual(
                source.source_counts,
                dict(
                    files=source.source.file_count,
                    entries=source.source.entry_count,
                    bytes=source.source.payload_bytes,
                ),
            )
            self.assertIs(
                observed.files.aggregate,
                source.current.reviewed.policy.input_custody.aggregate,
            )
            self.assertEqual(observed.files.configuration_files, set())
            self.assertLessEqual(
                observed.files.bytes_left + source.source_counts["bytes"],
                observed.files.aggregate.maximum_total_bytes,
            )
            close()
            observed.refresh_current(deadline=deadline)
            observed.require_original_files()
            source.require_original_files()

    def test_installed_selected_receipt_mutation_after_close_refuses(self):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            _env,
            close,
            _monorepo,
            _state,
        ):
            _source, observed = self.capture(inputs)
            paths = sorted(
                path
                for path in observed.files.references
                if path.parent.name == "receipts"
            )
            self.assertTrue(paths)
            path = paths[0]
            before = path.read_bytes()
            close()
            path.write_bytes(before + b" ")
            with self.assertRaises(ValueError):
                observed.require_original_files()
            self.assertEqual(path.read_bytes(), before + b" ")

    def test_absent_gate_remains_absent_and_passive_objects_refuse(self):
        with authored_monorepo_completion_fixture(self, installed=False) as (
            inputs,
            _env,
            close,
            _monorepo,
            _state,
        ):
            source, observed = self.capture(inputs)
            self.assertFalse(observed.present)
            close()
            observed.require_original_files()
            observed.gate.parent.mkdir(parents=True, exist_ok=True)
            observed.gate.write_bytes(b"preserve late gate")
            with self.assertRaisesRegex(ValueError, "completion-gate-changed"):
                observed.require_original_files()
            for fake in (source.source, {}, None):
                with self.assertRaises(TypeError):
                    _capture_provisioning_monorepo(fake)
