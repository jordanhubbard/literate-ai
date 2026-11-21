"""Actual Python observations keep original independent runtime file comparisons."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.builders import BuildError
from literate_ai.adapters.builders import python as python_builder
from tests.smoke.test_python_toolchain import _install_python_alias


class PythonOriginalFilesTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(strict=True)
        with patch(
            "tests.smoke.test_python_toolchain.symlinks_followable", return_value=False
        ):
            self.runtime = _install_python_alias(self.root, "owned-python")
        self.assertFalse(self.runtime.is_symlink())
        self.runtime.chmod(self.runtime.stat().st_mode | 0o200)
        if os.name != "nt":
            base = Path(getattr(sys, "_base_executable", sys.executable)).resolve()
            (self.root / "pyvenv.cfg").write_text(
                f"home = {base.parent}\n", encoding="utf-8"
            )
        # The actual owned interpreter is probed through a distinct launcher.
        # Windows needs list-argv subprocess quoting for the probe's -c script.
        shim = self.root / "invoke.py"
        shim.write_text(
            "import os,subprocess,sys\n"
            f"command = [{str(self.runtime)!r}, *sys.argv[1:]]\n"
            "if os.name == 'nt':\n"
            " sys.exit(subprocess.call(command))\n"
            "os.execv(command[0], command)\n",
            encoding="utf-8",
        )
        self.environment = dict(os.environ)
        self.selected = python_builder.discover_python_toolchain(
            self.environment,
            pinned_command=(sys.executable, str(shim)),
            minimum_version=(3, 0),
        )
        self.assertEqual(self.selected.runtime_executable, str(self.runtime))
        self.assertNotEqual(
            self.selected.launcher_executable, self.selected.runtime_executable
        )
        self.selected.require_unchanged(self.environment)

    def test_original_launcher_and_runtime_files_need_no_probe_or_process(self):
        trap = AssertionError("original file comparison invoked Python")
        with (
            patch.object(python_builder, "_probe_python_command", side_effect=trap),
            patch("subprocess.run", side_effect=trap),
            patch("subprocess.Popen", side_effect=trap),
        ):
            self.selected._require_files_unchanged()

    def test_changed_actual_selected_runtime_refuses_with_unchanged_launcher(self):
        original_launcher = python_builder.executable_file_digest(
            Path(self.selected.launcher_executable)
        )
        changed = self.runtime.read_bytes() + b"preserve foreign runtime bytes"
        self.runtime.write_bytes(changed)
        with self.assertRaises(BuildError) as raised:
            self.selected._require_files_unchanged()
        self.assertEqual(raised.exception.code, "builder.python_toolchain_changed")
        self.assertEqual(self.runtime.read_bytes(), changed)
        self.assertEqual(
            python_builder.executable_file_digest(
                Path(self.selected.launcher_executable)
            ),
            original_launcher,
        )

    def test_original_selected_runtime_absence_refuses_without_recreation(self):
        self.runtime.unlink()
        with self.assertRaises(BuildError) as raised:
            self.selected._require_files_unchanged()
        self.assertEqual(raised.exception.code, "builder.python_toolchain_changed")
        self.assertFalse(self.runtime.exists())

    def test_actual_owned_launcher_drift_refuses_and_preserves_changed_bytes(self):
        selected = python_builder.discover_python_toolchain(
            self.environment,
            pinned_command=(str(self.runtime),),
            minimum_version=(3, 0),
        )
        selected.require_unchanged(self.environment)
        changed = self.runtime.read_bytes() + b"preserve changed launcher"
        self.runtime.write_bytes(changed)
        with self.assertRaises(BuildError) as raised:
            selected._require_files_unchanged()
        self.assertEqual(raised.exception.code, "builder.python_toolchain_changed")
        self.assertEqual(self.runtime.read_bytes(), changed)
