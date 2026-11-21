"""Actual Cargo launcher bytes, pure comparison and unchanged public probing.

Tools are copied into owned temporary files before intentional mutations.
No provider, generated native consumer or SDK qualification is claimed.
"""

import shutil
import stat
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.builders import cargo
from literate_ai.adapters.builders.python import BuildError, executable_file_digest


@unittest.skipUnless(shutil.which("cargo"), "requires an installed Cargo launcher")
class CargoOriginalFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = cargo.discover_cargo_toolchain()

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.path = self.root / Path(self.original.command[0]).name
        shutil.copy2(self.original.command[0], self.path)
        self.path.chmod(stat.S_IMODE(self.path.stat().st_mode) | stat.S_IWUSR)
        self.tool = replace(
            self.original,
            command=(str(self.path), *self.original.command[1:]),
            launcher_executable=str(self.path),
            launcher_digest=executable_file_digest(self.path),
        )

    def test_original_file_comparison_never_probes_but_public_validation_does(self):
        with patch.object(cargo, "_probe_cargo", side_effect=AssertionError("probe")):
            self.assertEqual(self.tool._require_files_unchanged(), self.path)
        with patch.object(cargo, "_probe_cargo", wraps=cargo._probe_cargo) as probe:
            self.tool.require_unchanged()
            probe.assert_called_once()

    def test_owned_launcher_drift_refuses_before_any_probe_and_preserves_bytes(self):
        with self.path.open("ab") as stream:
            stream.write(b" preserve changed owned Cargo launcher")
        after = self.path.read_bytes()
        with patch.object(cargo, "_probe_cargo", side_effect=AssertionError("probe")):
            for check in (
                self.tool._require_files_unchanged,
                self.tool.require_unchanged,
            ):
                with self.assertRaises(BuildError) as failed:
                    check()
                self.assertEqual(
                    failed.exception.code, "builder.cargo_toolchain_changed"
                )
        self.assertEqual(self.path.read_bytes(), after)

    def test_changed_launcher_selection_refuses_before_any_probe(self):
        other = self.root / ("other-" + self.path.name)
        shutil.copy2(self.path, other)
        candidate = replace(self.tool, command=(str(other), *self.tool.command[1:]))
        with patch.object(cargo, "_probe_cargo", side_effect=AssertionError("probe")):
            with self.assertRaises(BuildError) as failed:
                candidate._require_files_unchanged()
            self.assertEqual(failed.exception.code, "builder.cargo_toolchain_changed")

    def test_real_probe_late_launcher_mutation_still_refuses_and_preserves_bytes(self):
        original = cargo._probe_cargo
        marker = b" preserve changed launcher after actual probe"

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            with self.path.open("ab") as stream:
                stream.write(marker)
            return result

        with patch.object(cargo, "_probe_cargo", changed):
            with self.assertRaises(BuildError) as failed:
                self.tool.require_unchanged()
            self.assertEqual(failed.exception.code, "builder.cargo_toolchain_changed")
        self.assertTrue(self.path.read_bytes().endswith(marker))
