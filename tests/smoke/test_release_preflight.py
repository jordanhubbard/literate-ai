"""Exercise the real Make entry point with inert gate bodies."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("make"), "requires the native Make entry point")
class ReleasePreflightTests(unittest.TestCase):
    def test_stale_authority_refuses_before_release_gate_runner(self):
        root = Path(__file__).resolve().parents[2]
        for failing in ("driver-review", "runner-review", "documentation-review"):
            with (
                self.subTest(failing=failing),
                tempfile.TemporaryDirectory() as temporary,
            ):
                directory = Path(temporary)
                override = directory / "gates.mk"
                bodies = []
                for gate in ("driver-review", "runner-review", "documentation-review"):
                    marker = str(directory / gate).encode("utf-8").hex()
                    code = (
                        "import pathlib,sys;"
                        f"pathlib.Path(bytes.fromhex('{marker}').decode()).write_text('ran');"
                        f"sys.exit({7 if gate == failing else 0})"
                    )
                    bodies.append(f'{gate}:\n\t$(PYTHON) -c "{code}"\n')
                override.write_text("\n".join(bodies), encoding="utf-8")
                checkpoint = directory / "release-checkpoint.json"
                result = subprocess.run(
                    [
                        shutil.which("make"),
                        "-f",
                        str(root / "Makefile"),
                        "-f",
                        str(override),
                        "release-check",
                        f'PYTHON="{sys.executable}"',
                        f"OBJ_DIR={directory}",
                        f"RELEASE_CHECKPOINT={checkpoint}",
                        "RUNTIME_PREREQUISITE=",
                        "RELEASE_GATES=must-not-run",
                    ],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertTrue((directory / failing).is_file(), result.stderr)
                self.assertFalse(checkpoint.exists())
                self.assertNotIn("run_checkpointed_gates.py", result.stdout)
                if failing == "driver-review":
                    self.assertFalse((directory / "runner-review").exists())
