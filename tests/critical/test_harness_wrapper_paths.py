"""Real Make wrapper/direct parity over literal retained filesystem paths."""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.harness_inventory import (
    HARNESS_WRAPPER_FILENAME,
    execute_harness_baseline,
    execute_harness_wrapper_parity,
    render_harness_wrapper,
)


@unittest.skipUnless(shutil.which("make"), "native Make required")
class HarnessWrapperPathTests(unittest.TestCase):
    def fixture(self, root, directory, nested="."):
        legacy = root / directory
        cwd = legacy if nested == "." else legacy / nested
        cwd.mkdir(parents=True)
        (cwd / "marker.txt").write_text("original literal bytes")
        (cwd / "probe.py").write_text(
            "from pathlib import Path\n"
            "assert Path('marker.txt').read_text() == 'original literal bytes'\n"
            "print('original command executed')\n"
        )
        command = (
            subprocess.list2cmdline([sys.executable, "probe.py"])
            if os.name == "nt"
            else shlex.join([sys.executable, "probe.py"])
        )
        entry = {
            "command": command,
            "cwd": nested,
            "evidence": "probe.py" if nested == "." else nested + "/probe.py",
        }
        inventory = {"commands": {"build": entry}, "findings": []}
        wrapper = root / HARNESS_WRAPPER_FILENAME
        wrapper.write_text(
            render_harness_wrapper(
                inventory, legacy_directory=directory, legacy_root=legacy
            )
        )
        return legacy, inventory, wrapper

    def assert_make_build(self, root, wrapper):
        completed = subprocess.run(
            ["make", "-f", str(wrapper), "build"],
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(b"original command executed", completed.stdout)

    def test_default_retained_directory_keeps_spaces_and_hash_literal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            _legacy, _inventory, wrapper = self.fixture(root, "retained # data")
            self.assert_make_build(root, wrapper)

    def test_nested_retained_directory_is_one_literal_command_argument(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            _legacy, _inventory, wrapper = self.fixture(
                root, "retained data", "nested ' $HOME"
            )
            self.assert_make_build(root, wrapper)

    def test_actual_parity_override_preserves_original_path_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / "root ' $HOME `touch pwned` ; data"
            root.mkdir()
            legacy, inventory, _wrapper = self.fixture(root, "original")
            baseline = execute_harness_baseline(
                inventory, legacy_root=legacy, timeout_seconds=30
            )
            self.assertEqual(baseline["state"], "passed")
            report = execute_harness_wrapper_parity(
                inventory,
                baseline,
                project_root=root,
                legacy_root=legacy,
                timeout_seconds=30,
            )
            self.assertEqual(report["state"], "passed")
            self.assertEqual(report["phase_count"], 1)
            self.assertTrue(report["phases"][0]["parity"])
            self.assertFalse((root / "pwned").exists())
            self.assertFalse((legacy / "pwned").exists())
