"""Source protocol/custody controls; these do NOT claim installed/native success."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai import test_checkpointing as checkpoint
from literate_ai.application.pinned_test_dispatch import (
    MemoryTestedTagStore,
    PinDispatchService,
    pin_from_framework_tcb,
    pin_plan_identity,
)
from literate_ai.contracts import canonical_identity
from literate_ai.projects import PinnedInputClosureError
from scripts import installed_native_root_inputs as inputs
from scripts import qualify_release_files as qualification
from scripts import wheel_smoke as wheel
from tests.critical import test_pinned_test_dispatch as dispatch_fixtures


class InstalledNativeRootInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repository = self.root / "repo"
        self.archives = self.root / "archives"
        (self.repository / "tests/support").mkdir(parents=True)
        (self.repository / "scripts").mkdir()
        self.archives.mkdir()
        (self.repository / "skills/source-to-specification").mkdir(parents=True)
        (self.repository / "skills/source-to-specification/SKILL.md").write_text(
            "owned authoring asset\n"
        )
        # Protocol fixture only: the real run reads the repository's maintained
        # canonical upstream inventory and verifies actual upstream size/hash.
        crates = {}
        for number in range(11):
            content = f"owned protocol input {number}".encode()
            name = f"fixture-{number}"
            crates[name] = (len(content), hashlib.sha256(content).hexdigest())
            (self.archives / (name + ".crate")).write_bytes(content)
        (self.repository / "tests/support/fixtures_rust_harness_vendor.py").write_text(
            "CRATES = " + repr(crates) + "\n"
        )
        for name in (
            "scripts/installed_native_root_inputs.py",
            "tests/support/installed_public_qualified_native_journey.py",
        ):
            (self.repository / name).write_text("# inert protocol fixture\n")

    def test_real_input_closure_refuses_changed_original_archive(self):
        data, pins = inputs.capture_inputs(self.repository, self.archives)
        self.assertEqual(len(data["archives"]), 11)
        self.assertEqual(data["modes"], ["consumer", "late-first"])
        pins.require_unchanged()
        (self.archives / "fixture-3.crate").write_bytes(b"changed original")
        with self.assertRaises(PinnedInputClosureError):
            pins.require_unchanged()

    def test_real_input_closure_refuses_changed_test_subject(self):
        _data, pins = inputs.capture_inputs(self.repository, self.archives)
        (
            self.repository
            / "tests/support/installed_public_qualified_native_journey.py"
        ).write_text("# different executed test subject\n")
        with self.assertRaises(PinnedInputClosureError):
            pins.require_unchanged()

    def test_missing_or_wrong_archive_never_becomes_optional_unqualified_result(self):
        archive = self.archives / "fixture-4.crate"
        original = archive.read_bytes()
        for mutation in (
            lambda: archive.unlink(),
            lambda: archive.write_bytes(b"wrong"),
        ):
            archive.write_bytes(original)
            mutation()
            with self.assertRaises((ValueError, PinnedInputClosureError)):
                inputs.capture_inputs(self.repository, self.archives)

    def test_stage_uses_only_original_bytes_without_framework_source(self):
        record, pins = inputs.capture_inputs(self.repository, self.archives)
        destination, staged = inputs.stage_inputs(
            self.repository,
            self.archives,
            self.root / "snapshot",
            inputs=record,
            pins=pins,
        )
        observed, original_staged = inputs.capture_inputs(
            destination, destination / "archives"
        )
        self.assertEqual(observed, record)
        self.assertFalse((destination / "src").exists())
        staged.require_unchanged()
        original_staged.require_unchanged()
        (destination / "tests/support/added.py").write_text("# foreign member\n")
        with self.assertRaises(ValueError):
            staged.require_unchanged()

    def test_original_added_member_refuses_before_stage_publication(self):
        record, pins = inputs.capture_inputs(self.repository, self.archives)
        (self.repository / "tests/support/added.py").write_text(
            "# added after capture\n"
        )
        with self.assertRaises(ValueError):
            inputs.stage_inputs(
                self.repository,
                self.archives,
                self.root / "snapshot",
                inputs=record,
                pins=pins,
            )
        self.assertFalse((self.root / "snapshot").exists())

    @unittest.skipUnless(os.name == "posix", "native POSIX alias control")
    def test_symlink_ancestor_refuses_without_opening_target(self):
        alias = self.root / "unopened-alias"
        alias.symlink_to(self.root / "does-not-exist", target_is_directory=True)
        with self.assertRaises(ValueError):
            inputs.real_directory(alias / "archives")


class InstalledNativeRequiredGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.environment = mock.patch.dict(
            os.environ,
            {"OBJ_DIR": "", "LITAI_EVIDENCE_RUN": "", "LITAI_EVIDENCE_PARENT": ""},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def _attempt(self, *, required=(), code=0):
        gates = ("wheel-check", "final")
        pin = pin_from_framework_tcb(
            canonical_identity({"actual-protocol-test": 1}), pipeline=gates
        )
        receipts = MemoryTestedTagStore()
        receipts.record(
            pin.identity,
            pin_plan_identity(pin),
            dispatch_fixtures._receipt(pin.identity),
        )
        calls = []
        result = checkpoint.run_gates(
            suite="required-native",
            gates=gates,
            state_path=self.root / "checkpoint.json",
            project_root=self.root,
            gate_pins={gate: pin for gate in gates},
            dispatch=PinDispatchService(receipts=receipts),
            required_gates=required,
            runner=lambda gate: calls.append(gate) or code,
        )
        return result, calls

    def test_explicit_required_wheel_gate_runs_despite_existing_tested_dispatch(self):
        code, calls = self._attempt(required=("wheel-check",))
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["wheel-check"])

    def test_required_failure_remains_failure_despite_existing_tested_dispatch(self):
        code, calls = self._attempt(required=("wheel-check",), code=17)
        self.assertEqual(code, 17)
        self.assertEqual(calls, ["wheel-check"])

    def test_absent_selection_preserves_existing_tested_skip(self):
        code, calls = self._attempt()
        self.assertEqual(code, 0)
        self.assertEqual(calls, [])

    def test_required_gate_must_belong_to_selected_plan_before_runner(self):
        for required in (("not-a-selected-gate",), ("wheel-check", "wheel-check")):
            runner = mock.Mock()
            with self.assertRaises(ValueError):
                checkpoint.run_gates(
                    suite="required-native",
                    gates=("wheel-check",),
                    state_path=self.root / "checkpoint.json",
                    project_root=self.root,
                    runner=runner,
                    required_gates=required,
                )
            runner.assert_not_called()
            self.assertFalse((self.root / "checkpoint.json").exists())

    def test_required_wheel_runs_again_despite_earlier_repair_checkpoint(self):
        gates = ("wheel-check", "final")
        pin = pin_from_framework_tcb(canonical_identity({"repair": 1}), pipeline=gates)
        options = dict(
            suite="required-native",
            gates=gates,
            state_path=self.root / "checkpoint.json",
            project_root=self.root,
            gate_pins={gate: pin for gate in gates},
        )
        self.assertEqual(
            checkpoint.run_gates(
                **options, runner=lambda gate: 7 if gate == "final" else 0
            ),
            7,
        )
        calls = []
        self.assertEqual(
            checkpoint.run_gates(
                **options,
                required_gates=("wheel-check",),
                runner=lambda gate: calls.append(gate) or 0,
            ),
            2,
        )
        self.assertEqual(calls, ["wheel-check", "final"])

    def test_selected_wheel_cell_without_explicit_archives_refuses_before_effects(self):
        with (
            mock.patch.object(
                wheel.sys,
                "argv",
                ["wheel_smoke.py", "--require-native-root-qualification"],
            ),
            mock.patch.object(wheel, "run") as run,
        ):
            with self.assertRaises(RuntimeError):
                wheel._main()
            run.assert_not_called()

    def test_selected_release_artifact_cell_cannot_silently_omit_archives(self):
        with (
            mock.patch.object(
                qualification.sys,
                "argv",
                ["qualify_release_files.py", "--require-native-root-qualification"],
            ),
            mock.patch.object(qualification.subprocess, "run") as run,
        ):
            with self.assertRaises(RuntimeError):
                qualification.main(["--require-native-root-qualification"])
            run.assert_not_called()


class InstalledNativeWheelReportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.wheel = self.root / "candidate.whl"
        self.wheel.write_bytes(b"protocol wheel bytes; not installable qualification")
        self.inputs = {
            "identity": "inputs",
            "test_python_identity": "tests",
            "test_python_members": 7,
        }
        self.pins = mock.Mock()
        self.attempt = 0

    def _report(self, mode):
        return {
            "schema": "literate-ai/installed-native-qualified-public-journey@1",
            "qualified": True,
            "skipped": 0,
            "mode": mode,
            "framework_distribution": "F",
            "wheel_identity": wheel.file_identity(self.wheel),
            "build_origin": {"repository_url": "origin", "git_revision": "revision"},
            "fixture_input_identity": "inputs",
            "test_python_identity": "tests",
            "test_python_members": 7,
            "synthetic_framework_observers": False,
            "actual_clean_runs": 2,
            "source_requests": 3 if mode == "consumer" else 4,
            "histories": [
                {"attempts": [1] if mode == "consumer" else [1, 2]} for _ in range(2)
            ],
            "calls": [{"exit": 0}],
            "consumer": (
                {
                    "receipt_committed": True,
                    "generated_nodes": 1,
                    "provider_closed_history_reopens": 2,
                }
                if mode == "consumer"
                else None
            ),
        }

    def _invoke(self, change=None):
        self.attempt += 1
        cwd = self.root / f"attempt-{self.attempt}"
        cwd.mkdir()

        def run(arguments, **options):
            mode = arguments[-1]
            report = self._report(mode)
            if change is not None:
                change(mode, report)
            options["stdout_sink"].write(json.dumps(report).encode())
            self.assertEqual(
                options["timeout_seconds"], inputs.MODE_TRANSPORT_SECONDS[mode]
            )
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

        with (
            mock.patch.object(
                wheel.runpy,
                "run_path",
                return_value={
                    "stage_inputs": lambda *_arguments, **_options: (cwd, self.pins),
                    "MODE_TRANSPORT_SECONDS": inputs.MODE_TRANSPORT_SECONDS,
                },
            ),
            mock.patch.object(wheel, "run_bounded_process", side_effect=run),
            mock.patch.object(wheel, "_runtime_record_scope"),
        ):
            return wheel.qualify_installed_native_root_journeys(
                self.root,
                self.root / "python",
                cwd,
                wheel=self.wheel,
                distribution="F",
                origin="origin",
                revision="revision",
                archive_directory=self.root,
                inputs=self.inputs,
                input_pins=self.pins,
            )

    def test_both_distinct_cells_required_and_bookended(self):
        result = self._invoke()
        self.assertEqual(list(result), ["consumer", "late-first"])
        self.assertGreaterEqual(self.pins.require_unchanged.call_count, 4)

    def test_optional_false_or_foreign_wheel_or_synthetic_observer_refuses(self):
        for field, value in (
            ("qualified", False),
            ("wheel_identity", "foreign"),
            ("framework_distribution", "source-F"),
            ("synthetic_framework_observers", True),
            ("fixture_input_identity", "changed-tests"),
        ):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                self._invoke(
                    lambda _mode, report, field=field, value=value: report.__setitem__(
                        field, value
                    )
                )

    def test_late_cell_cannot_reuse_positive_one_attempt_proof(self):
        def wrong(mode, report):
            if mode == "late-first":
                report["histories"] = [{"attempts": [1]}, {"attempts": [1]}]

        with self.assertRaises(RuntimeError):
            self._invoke(wrong)
