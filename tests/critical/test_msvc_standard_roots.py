"""Real file/PE-format controls; these do not qualify a native Windows host."""

import tempfile
import unittest
from pathlib import Path

from literate_ai.bootstrap.windows_msvc import (
    WindowsMsvcDiscoveryError,
    discover_native_msvc_compiler,
)


class MsvcStandardRootTests(unittest.TestCase):
    def compiler(self, root, version, edition, machine=0xAA64):
        vc = root / "Microsoft Visual Studio" / version / edition / "VC"
        metadata = vc / "Auxiliary/Build/Microsoft.VCToolsVersion.default.txt"
        metadata.parent.mkdir(parents=True)
        metadata.write_text("14.50.00000\n", encoding="ascii")
        compiler = vc / "Tools/MSVC/14.50.00000/bin/Hostarm64/arm64/cl.exe"
        compiler.parent.mkdir(parents=True)
        image = bytearray(88)
        image[:2] = b"MZ"
        image[60:64] = (64).to_bytes(4, "little")
        image[64:68] = b"PE\0\0"
        image[68:70] = machine.to_bytes(2, "little")
        compiler.write_bytes(image)
        return compiler

    def test_vs2026_standard_root_observes_native_image_and_refuses_foreign(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            compiler = self.compiler(root, "18", "Enterprise")
            environment = {"ProgramFiles": str(root)}
            self.assertEqual(
                discover_native_msvc_compiler("arm64", environment), compiler
            )
            original = compiler.read_bytes()
            foreign = bytearray(original)
            foreign[68:70] = (0x8664).to_bytes(2, "little")
            compiler.write_bytes(foreign)
            with self.assertRaisesRegex(WindowsMsvcDiscoveryError, "not native"):
                discover_native_msvc_compiler("arm64", environment)
            self.assertEqual(compiler.read_bytes(), foreign)

    def test_existing_2022_selection_keeps_priority_over_new_standard_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            legacy = self.compiler(root, "2022", "BuildTools")
            recent = self.compiler(root, "18", "Enterprise")
            original = legacy.read_bytes(), recent.read_bytes()
            self.assertEqual(
                discover_native_msvc_compiler("arm64", {"ProgramFiles": str(root)}),
                legacy,
            )
            self.assertEqual((legacy.read_bytes(), recent.read_bytes()), original)
