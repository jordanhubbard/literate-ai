"""Generic import verification admits only the artifact and interpreter libraries."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.standard_project import (
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts import ComponentCommandPhase
from tests.smoke.test_standard_command_projection import (
    _locked_snapshot,
    _observation,
    _tool,
)


def _library(root):
    _, snapshot, execution = _locked_snapshot(
        root, language="python", no_entrypoint=True
    )
    closure = project_locked_standard_toolchain_closure(
        snapshot,
        execution,
        host_platform="macos",
        toolchain_discoverer=lambda name, _constraint, _environment: _tool(name),
        dependency_observer=_observation,
    )
    contract = closure.contracts[0]
    capability = contract.library_import_surface.capabilities[0]
    export = root / "artifact" / contract.artifact_export.export_id
    source = export / "source"
    module = source.joinpath(*capability.module.split(".")).with_suffix(".py")
    module.parent.mkdir(parents=True)
    for parent in module.parents:
        if parent == source:
            break
        (parent / "__init__.py").touch()
    replacements = {
        "{tool}": sys.executable,
        "{export_path}": str(export),
        "{artifact_root}": str(export.parent),
    }
    argv = [
        replacements.get(value, value)
        for value in contract.command(ComponentCommandPhase.EXECUTE).argv
    ]
    return module, capability, argv


class GenericPythonImportIsolationTests(unittest.TestCase):
    def test_ambient_dependency_cannot_satisfy_an_artifact_import(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module, capability, argv = _library(root)
            ambient = root / "ambient"
            ambient.mkdir()
            (ambient / "ambient_only_fixture.py").write_text("VALUE = 7\n")
            module.write_text(
                "from ambient_only_fixture import VALUE\n"
                + capability.symbols[0]
                + " = VALUE\n"
            )
            result = subprocess.run(
                argv,
                cwd=ambient,
                env={**os.environ, "PYTHONPATH": str(ambient)},
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("ambient_only_fixture", result.stderr)

    def test_standard_library_and_exact_artifact_symbols_remain_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            module, capability, argv = _library(Path(temporary))
            module.write_text(
                "from fractions import Fraction\n"
                + capability.symbols[0]
                + " = Fraction(7, 1)\n"
            )
            result = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["capabilities"], [capability.capability]
            )
            module.write_text("other_symbol = 7\n")
            missing = subprocess.run(argv, capture_output=True, text=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn(capability.symbols[0], missing.stderr)

    def test_ambient_startup_and_standard_library_shadows_are_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            module, capability, argv = _library(root)
            module.write_text(capability.symbols[0] + " = 7\n")
            ambient = root / "ambient"
            ambient.mkdir()
            marker = root / "startup-ran"
            (ambient / "sitecustomize.py").write_text(
                "from pathlib import Path\nPath("
                + repr(str(marker))
                + ").write_text('unexpected startup')\n"
            )
            (ambient / "json.py").write_text(
                "raise RuntimeError('ambient standard-library shadow')\n"
            )
            result = subprocess.run(
                argv,
                cwd=ambient,
                env={**os.environ, "PYTHONPATH": str(ambient)},
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())
            self.assertEqual(
                json.loads(result.stdout)["capabilities"], [capability.capability]
            )
