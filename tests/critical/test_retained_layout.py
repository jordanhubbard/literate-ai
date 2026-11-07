"""Legacy retained layout identity and physical path custody."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.retained_layout import (
    LEGACY_WRAPPER_COMPONENT,
    RETAINED_LAYOUT_SCHEMA,
    RetainedLayoutDeclaration,
    RetainedLayoutError,
    read_retained_layout_declaration,
    resolve_legacy_implementation,
    resolve_legacy_layout,
)
from literate_ai.contracts import canonical_json_bytes


class RetainedLayoutTests(unittest.TestCase):
    def test_direct_declaration_refuses_legacy_qualification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".literate").mkdir()
            (root / "scheduler").mkdir()
            self.assertIsNone(read_retained_layout_declaration(root))
            document = {
                "schema": RETAINED_LAYOUT_SCHEMA,
                "wrapper_component": "components/scheduler-wrapper",
                "implementation_directory": "scheduler",
                "framework_owned_paths": [],
                "lineage": {"kind": "initial"},
            }
            path = root / ".literate/retained-layout.json"
            path.write_bytes(canonical_json_bytes(document) + b"\n")
            self.assertEqual(read_retained_layout_declaration(root).to_dict(), document)
            with self.assertRaises(RetainedLayoutError):
                resolve_legacy_implementation(
                    root, {"implementation_directory": "scheduler"}
                )
            path.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(RetainedLayoutError):
                read_retained_layout_declaration(root)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_declaration_reader_refuses_redirected_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".literate").mkdir()
            target = root / "other.json"
            target.write_text("{}\n", encoding="utf-8")
            try:
                (root / ".literate/retained-layout.json").symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaises(RetainedLayoutError):
                read_retained_layout_declaration(root)

    def test_declared_plain_and_root_layouts_keep_distinct_ownership(self) -> None:
        plain = {
            "schema": RETAINED_LAYOUT_SCHEMA,
            "wrapper_component": "components/scheduler-wrapper",
            "implementation_directory": "scheduler",
            "framework_owned_paths": [],
            "lineage": {"kind": "initial"},
        }
        declared = RetainedLayoutDeclaration.from_dict(plain)
        self.assertEqual(declared.to_dict(), plain)
        root = {
            **plain,
            "implementation_directory": ".",
            "framework_owned_paths": [
                ".literate/retained-layout.json",
                "components/scheduler-wrapper/component.md",
                "literate.project.json",
            ],
            "lineage": {
                "kind": "relocation",
                "previous_layout_identity": declared.identity,
            },
        }
        relocated = RetainedLayoutDeclaration.from_dict(root)
        self.assertEqual(relocated.previous_layout_identity, declared.identity)
        self.assertEqual(relocated.to_dict(), root)
        self.assertNotEqual(relocated.identity, declared.identity)

    def test_declaration_refuses_aliases_and_ambiguous_ownership(self) -> None:
        base = {
            "schema": RETAINED_LAYOUT_SCHEMA,
            "wrapper_component": "components/scheduler-wrapper",
            "implementation_directory": ".",
            "framework_owned_paths": [
                ".literate/retained-layout.json",
                "components/scheduler-wrapper/component.md",
                "literate.project.json",
            ],
            "lineage": {"kind": "initial"},
        }
        variants = (
            {**base, "wrapper_component": "components/CON"},
            {**base, "wrapper_component": "components/scheduler-wrapper/child"},
            {**base, "implementation_directory": "components"},
            {**base, "implementation_directory": "components/scheduler-wrapper"},
            {**base, "framework_owned_paths": base["framework_owned_paths"][:-1]},
            {
                **base,
                "framework_owned_paths": [
                    *base["framework_owned_paths"],
                    "COMPONENTS/SCHEDULER-WRAPPER/component.md",
                ],
            },
            {
                **base,
                "lineage": {
                    "kind": "relocation",
                    "previous_layout_identity": "bad",
                },
            },
        )
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(RetainedLayoutError):
                RetainedLayoutDeclaration.from_dict(variant)

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
            layout = resolve_legacy_layout(
                root, {"implementation_directory": coordinate}
            )
            self.assertEqual(layout.wrapper_component, LEGACY_WRAPPER_COMPONENT)
            self.assertEqual(layout.wrapper_root, implementation.parent)
            self.assertEqual(layout.implementation_root, implementation)

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
