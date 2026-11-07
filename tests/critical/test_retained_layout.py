"""Legacy retained layout identity and physical path custody."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.retained_layout import (
    RetainedLayoutError,
    resolve_legacy_implementation,
)


class RetainedLayoutTests(unittest.TestCase):
    def test_preserves_legacy_coordinate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinate = "components/legacy-project-wrapper/implementation"
            implementation = root.joinpath(*coordinate.split("/"))
            implementation.mkdir(parents=True)
            spelling, resolved = resolve_legacy_implementation(
                root,
                {"implementation_directory": coordinate},
            )
            self.assertEqual(spelling, coordinate)
            self.assertEqual(resolved, implementation)

    def test_rejects_cross_host_aliases_and_root_without_declaration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source").mkdir()
            for coordinate in (
                ".",
                "source/../source",
                "source//",
                "C:/source",
                "source\\file",
                "CON",
            ):
                with (
                    self.subTest(coordinate=coordinate),
                    self.assertRaises(RetainedLayoutError),
                ):
                    resolve_legacy_implementation(
                        root, {"implementation_directory": coordinate}
                    )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_rejects_redirected_ancestor_and_final_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real" / "implementation").mkdir(parents=True)
            try:
                (root / "alias").symlink_to(root / "real", target_is_directory=True)
                (root / "final").symlink_to(
                    root / "real" / "implementation", target_is_directory=True
                )
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            for coordinate in ("alias/implementation", "final"):
                with (
                    self.subTest(coordinate=coordinate),
                    self.assertRaises(RetainedLayoutError),
                ):
                    resolve_legacy_implementation(
                        root, {"implementation_directory": coordinate}
                    )
