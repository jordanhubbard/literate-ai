"""Real optional installed-monorepo observation and refusal controls.

Actual per-component retained harness receipts and authored consumer files are
used; authored provider admission is an explicit fixture. No native execution,
model generation, final admission, reopening or release is qualified.
"""

import copy
import os
import pickle
import time
import unittest
from unittest.mock import patch

from literate_ai.adapters import (
    authored_retained_cargo_monorepo_observation as monorepo,
)
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.support.fixtures_authored_monorepo_completion import (
    authored_monorepo_completion_fixture,
    cleanup_monorepo_completion_template,
    initialize_monorepo_completion_template,
)


class AuthoredMonorepoCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()
        cls.addClassCleanup(cleanup_monorepo_completion_template)
        initialize_monorepo_completion_template()

    def capture(self, inputs, environment):
        return monorepo._capture_authored_monorepo_files(
            inputs, environment=environment
        )

    def test_actual_installed_check_refreshes_after_close_and_raw_never_runs_commands(
        self,
    ):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            env,
            close,
            checked,
            state,
        ):
            deadline = time.monotonic() + 900
            observation = self.capture(inputs, env)
            self.assertTrue(observation.present)
            self.assertEqual(observation.original, checked)
            self.assertTrue(observation.files.references)
            self.assertFalse(
                (
                    inputs.materialized.scratch.context.workspace
                    / checked["source_root"]
                ).exists()
            )
            close()
            self.assertTrue(state["closed"])
            with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
                inputs.current_identity(environment=env)
            observation.refresh_current(deadline=deadline)
            for action in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.assertRaises(TypeError):
                    action(observation)
            with (
                patch("subprocess.run", side_effect=AssertionError("raw process")),
                patch("subprocess.Popen", side_effect=AssertionError("raw process")),
                patch.object(
                    type(inputs),
                    "current_identity",
                    side_effect=AssertionError("expired input owner"),
                ),
            ):
                observation.require_original_files()

    def test_absent_optional_gate_never_calls_checker_and_late_gate_refuses(self):
        with authored_monorepo_completion_fixture(self, installed=False) as (
            inputs,
            env,
            close,
            _c,
            _s,
        ):
            with patch.object(
                monorepo,
                "check_installed_monorepo_components",
                side_effect=AssertionError("optional checker"),
            ):
                deadline = time.monotonic() + 900
                observation = self.capture(inputs, env)
                close()
                observation.require_original_files()
                observation.refresh_current(deadline=deadline)
                gate = observation.gate
                gate.parent.mkdir(parents=True)
                gate.write_bytes(b"preserve unexpected installation")
                with self.assertRaisesRegex(ValueError, "gate-changed"):
                    observation.require_original_files()
                self.assertEqual(gate.read_bytes(), b"preserve unexpected installation")

    def test_final_actual_checker_callback_source_mutation_refuses_and_preserves(self):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            env,
            close,
            checked,
            _state,
        ):
            deadline = time.monotonic() + 900
            observation = self.capture(inputs, env)
            source = observation.project.root / checked["source_root"] / "kit/value.py"
            before = source.read_bytes()
            close()
            actual = monorepo.check_installed_monorepo_components

            def changed(root):
                result = actual(root)
                source.write_bytes(before + b"# preserve last checker mutation\n")
                return result

            with patch.object(monorepo, "check_installed_monorepo_components", changed):
                with self.assertRaises(ValueError):
                    observation.refresh_current(deadline=deadline)
            self.assertEqual(
                source.read_bytes(), before + b"# preserve last checker mutation\n"
            )

    def test_closure_reuse_still_charges_uncovered_file_byte_and_entry_allowances(self):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            env,
            close,
            _checked,
            _state,
        ):
            project = inputs.materialized.files.reviewed.project
            component = project.root / monorepo.retained_scaffold_coordinate(
                project.root, "components/legacy-project-wrapper/component.md"
            )
            # This actual catalog closure is reusable local evidence outside
            # already-charged workspace/CARGO_HOME trees. Force each residual
            # allowance boundary independently; no successful admission is faked.
            for counter in ("files_left", "bytes_left", "entries_left", "member_limit"):
                with self.subTest(counter=counter):
                    ledger = monorepo._SupplementalOriginalFiles(
                        inputs, inputs.scope.owners.maximum_metadata_bytes
                    )
                    ledger.cover_selected_closures({component})
                    self.assertIn(component, ledger.covered)
                    self.assertIsNone(ledger._tree_coverage(component))
                    setattr(ledger, counter, 0)
                    with self.assertRaises(ValueError):
                        ledger.observe(component)
            close()

    def test_new_zero_byte_source_fits_zero_payload_residual_with_file_and_entry_space(
        self,
    ):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            _env,
            close,
            _checked,
            _state,
        ):
            path = (
                inputs.materialized.files.reviewed.project.root / "empty-supplement.txt"
            )
            path.write_bytes(b"")
            ledger = monorepo._SupplementalOriginalFiles(
                inputs, inputs.scope.owners.maximum_metadata_bytes
            )
            ledger.bytes_left = 0
            before = ledger.files_left
            self.assertEqual(ledger.observe(path).size, 0)
            self.assertEqual(ledger.bytes_left, 0)
            self.assertEqual(ledger.files_left, before - 1)
            ledger.require_original_files()
            close()

    def test_new_stream_read_uses_current_residual_and_metadata_caps(self):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            _env,
            close,
            _checked,
            _state,
        ):
            root = inputs.materialized.files.reviewed.project.root
            source = root / "bounded-source"
            source.write_bytes(b"1234")
            ledger = monorepo._SupplementalOriginalFiles(
                inputs, inputs.scope.owners.maximum_metadata_bytes
            )
            ledger.observe(source)
            # Directly test the actual guarded stream port with a smaller
            # current residual, including a race that would outrun an old
            # aggregate value. No new successful baseline/admission is issued.
            late = root / "late-source"
            late.write_bytes(b"1234")
            ledger.bytes_left = 3
            with self.assertRaises(ValueError):
                ledger.streamed.pin(late, boundary=root, label="late")
            metadata = root / "oversize-receipt.json"
            with metadata.open("wb") as out:
                out.truncate(16 * 1024**2 + 1)
            ledger.document_paths.add(metadata)
            with self.assertRaisesRegex(ValueError, "document-limit"):
                ledger.observe(metadata)
            self.assertEqual(late.read_bytes(), b"1234")
            self.assertEqual(metadata.stat().st_size, 16 * 1024**2 + 1)
            close()

    def test_actual_late_receipt_growth_is_capped_before_supplemental_stream(self):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            env,
            close,
            _checked,
            _state,
        ):
            receipt = (
                inputs.materialized.files.reviewed.project.framework_root
                / monorepo.INSTALLATION_ROOT
                / "receipts/kit.json"
            )
            original = monorepo.check_installed_monorepo_components
            calls = 0

            def changed(project):
                nonlocal calls
                value = original(project)
                calls += 1
                if calls == 1:
                    with receipt.open("wb") as out:
                        out.truncate(16 * 1024**2 + 1)
                return value

            with patch.object(monorepo, "check_installed_monorepo_components", changed):
                with self.assertRaisesRegex(ValueError, "completion-document-limit"):
                    self.capture(inputs, env)
            self.assertEqual(calls, 1)
            with self.assertRaises(ValueError):
                close()
            self.assertEqual(receipt.stat().st_size, 16 * 1024**2 + 1)

    def test_selected_physical_hardlink_groups_count_once_and_unknown_peer_refuses(
        self,
    ):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            _env,
            close,
            _checked,
            _state,
        ):
            root = inputs.materialized.files.reviewed.project.root
            first, second = root / "linked-source-a", root / "linked-source-b"
            first.write_bytes(b"source")
            os.link(first, second)
            ledger = monorepo._SupplementalOriginalFiles(
                inputs, inputs.scope.owners.maximum_metadata_bytes
            )
            files, payload = ledger.files_left, ledger.bytes_left
            ledger.observe(first)
            ledger.observe(second)
            ledger.require_original_files()
            self.assertEqual(ledger.files_left, files - 1)
            self.assertEqual(ledger.bytes_left, payload - len(b"source"))
            incomplete = monorepo._SupplementalOriginalFiles(
                inputs, inputs.scope.owners.maximum_metadata_bytes
            )
            incomplete.observe(first)
            with self.assertRaisesRegex(ValueError, "unowned-hardlink"):
                incomplete.require_original_files()
            self.assertEqual(first.read_bytes(), b"source")
            self.assertEqual(second.read_bytes(), b"source")
            close()

    def test_additional_json_decode_reserves_metadata_before_parser(self):
        with authored_monorepo_completion_fixture(self) as (
            inputs,
            _env,
            close,
            _checked,
            _state,
        ):
            path = (
                inputs.materialized.files.reviewed.project.framework_root
                / monorepo.INSTALLATION_ROOT
                / "installation.json"
            )
            ledger = monorepo._SupplementalOriginalFiles(
                inputs, inputs.scope.owners.maximum_metadata_bytes
            )
            admitted = ledger.observe(path)
            ledger.metadata_left = admitted.size
            with patch.object(
                monorepo,
                "_parse_document",
                side_effect=AssertionError("decoder must not allocate"),
            ):
                with self.assertRaisesRegex(ValueError, "completion-metadata-limit"):
                    ledger.document(path)
            close()
