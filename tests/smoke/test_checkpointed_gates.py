"""Tests for the fail-fast, repair-resumable release gate runner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.run_checkpointed_gates import run_gates


class CheckpointedGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name) / "release.json"
        self.gates = ("fast", "expensive", "final")
        self.evidence_environment = mock.patch.dict(
            os.environ,
            {
                "OBJ_DIR": "",
                "LITAI_EVIDENCE_RUN": "",
                "LITAI_EVIDENCE_PARENT": "",
            },
            clear=False,
        )
        self.evidence_environment.start()
        self.addCleanup(self.evidence_environment.stop)

    def test_repaired_success_requires_a_clean_release_evidence_rerun(self) -> None:
        first_calls: list[str] = []

        def fail_expensive(gate: str) -> int:
            first_calls.append(gate)
            return 7 if gate == "expensive" else 0

        self.assertEqual(
            run_gates(
                suite="release",
                gates=self.gates,
                state_path=self.state,
                runner=fail_expensive,
            ),
            7,
        )
        self.assertEqual(first_calls, ["fast", "expensive"])
        recorded = json.loads(self.state.read_text(encoding="utf-8"))
        completed = [
            step for payload in recorded["pins"].values() for step in payload["ok"]
        ]
        self.assertEqual(completed, ["fast"])

        resumed_calls: list[str] = []
        self.assertEqual(
            run_gates(
                suite="release",
                gates=self.gates,
                state_path=self.state,
                runner=lambda gate: resumed_calls.append(gate) or 0,
            ),
            2,
        )
        self.assertEqual(resumed_calls, ["expensive", "final"])
        self.assertFalse(self.state.exists())

        release_calls: list[str] = []
        self.assertEqual(
            run_gates(
                suite="release",
                gates=self.gates,
                state_path=self.state,
                runner=lambda gate: release_calls.append(gate) or 0,
            ),
            0,
        )
        self.assertEqual(release_calls, list(self.gates))

    def test_changed_gate_plan_does_not_reuse_an_incompatible_checkpoint(self) -> None:
        run_gates(
            suite="release",
            gates=self.gates,
            state_path=self.state,
            runner=lambda gate: 9 if gate == "expensive" else 0,
        )
        changed = ("new-fast", *self.gates)
        calls: list[str] = []
        run_gates(
            suite="release",
            gates=changed,
            state_path=self.state,
            runner=lambda gate: calls.append(gate) or (9 if gate == "expensive" else 0),
        )
        self.assertEqual(calls, ["new-fast", "fast", "expensive"])

    def test_unmanaged_native_inputs_are_retested_after_a_failed_attempt(self):
        root = Path(self.temporary.name).resolve()
        native = root / "native_test.py"
        dependency = root / "input.txt"
        native.write_text(
            "from pathlib import Path\n"
            "assert Path('input.txt').read_text() == 'correct'\n"
        )
        dependency.write_text("correct")
        fail_final = True

        def execute(gate):
            if gate == "native-test":
                return subprocess.run(
                    (sys.executable, str(native)),
                    cwd=root,
                    capture_output=True,
                    timeout=30,
                ).returncode
            return 7 if fail_final else 0

        def attempt():
            return run_gates(
                suite="native-fixture",
                gates=("native-test", "final"),
                state_path=self.state,
                runner=execute,
                project_root=root,
            )

        self.assertEqual(attempt(), 7)
        dependency.write_text("broken")
        fail_final = False
        self.assertEqual(attempt(), 1)
        dependency.write_text("correct")
        self.assertEqual(attempt(), 0)

    @unittest.skipUnless(shutil.which("make"), "Make is unavailable")
    def test_make_preview_modes_never_create_success_evidence_or_clear_progress(self):
        root = Path(self.temporary.name).resolve()
        script = (
            Path(__file__).resolve().parents[2] / "scripts/run_checkpointed_gates.py"
        )
        (root / "Makefile").write_text(
            ".PHONY: all marker fail\nall:\n"
            f'\t+"{sys.executable}" "{script}" --state checkpoint.json '
            '--make "$(MAKE)" marker fail\n'
            f'marker:\n\t"{sys.executable}" -c '
            "\"from pathlib import Path; Path('executed').write_text('yes')\"\n"
            f'fail:\n\t"{sys.executable}" -c "raise SystemExit(7)"\n'
        )
        environment = {
            **os.environ,
            "MAKEFLAGS": "",
            "MFLAGS": "",
            "MAKEOVERRIDES": "",
            "GNUMAKEFLAGS": "",
            "OBJ_DIR": str(root / "objects"),
        }
        for flag in ("-n", "-q", "-t"):
            with self.subTest(flag=flag):
                progress = root / "checkpoint.json"
                progress.write_bytes(b"retained incomplete run\n")
                result = subprocess.run(
                    ("make", flag, "all"),
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertIn(result.returncode, (0, 1), result.stderr)
                self.assertEqual(progress.read_bytes(), b"retained incomplete run\n")
                self.assertFalse((root / "executed").exists())
                self.assertFalse((root / "objects").exists())
        progress.unlink()
        result = subprocess.run(
            ("make", "all"),
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((root / "executed").is_file(), result.stdout + result.stderr)
        self.assertTrue(progress.is_file())


if __name__ == "__main__":
    unittest.main()
