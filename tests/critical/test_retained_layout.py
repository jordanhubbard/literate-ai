"""Legacy retained layout identity and physical path custody."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.harness_inventory import legacy_shim_authority
from literate_ai.adapters.retained_layout import (
    LEGACY_WRAPPER_COMPONENT,
    RETAINED_LAYOUT_SCHEMA,
    RetainedLayoutDeclaration,
    RetainedLayoutError,
    RetainedLayoutSelection,
    read_retained_layout_declaration,
    resolve_legacy_implementation,
    resolve_legacy_layout,
    resolve_structural_layout,
)
from literate_ai.contracts import (
    ProjectInitializationBaseline,
    ProjectInitializationBaselineFile,
    canonical_identity,
    canonical_json_bytes,
)


class RetainedLayoutTests(unittest.TestCase):
    def test_initial_selection_keeps_default_and_refuses_portable_overlap(self) -> None:
        self.assertEqual(
            RetainedLayoutSelection.from_values(
                "components/legacy-project-wrapper",
                "components/legacy-project-wrapper/implementation",
            ).implementation_directory,
            "components/legacy-project-wrapper/implementation",
        )
        for implementation in (
            "components",
            "COMPONENTS",
            "components/SCHEDULER-WRAPPER",
            "components/SCHEDULER-WRAPPER/implementation",
            "COMPONENTS/scheduler-wrapper/implementation",
            "../scheduler",
        ):
            with self.subTest(implementation=implementation):
                with self.assertRaises(RetainedLayoutError):
                    RetainedLayoutSelection.from_values(
                        "components/scheduler-wrapper", implementation
                    )

    def test_shim_authority_uses_selected_wrapper_component(self) -> None:
        inventory = {"commands": {}, "stages": []}
        baseline = {"phases": []}
        selected = legacy_shim_authority(
            inventory, baseline, wrapper_component="components/scheduler-wrapper"
        )
        self.assertIn("components/scheduler-wrapper/component.md", selected)
        self.assertNotIn("components/legacy-project-wrapper/component.md", selected)
        for invalid in ("components", "components/wrapper/child", "../wrapper"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                legacy_shim_authority(inventory, baseline, wrapper_component=invalid)

    def _declared_project(self, root: Path, document: dict) -> None:
        wrapper = root / document["wrapper_component"]
        wrapper.mkdir(parents=True)
        component = legacy_shim_authority(
            {"commands": {}, "stages": []}, {"phases": []}
        )["components/legacy-project-wrapper/component.md"]
        (wrapper / "component.md").write_text(component, encoding="utf-8")
        (root / ".literate").mkdir(exist_ok=True)
        (root / ".literate/retained-layout.json").write_bytes(
            canonical_json_bytes(document) + b"\n"
        )

    def test_structural_resolution_checks_wrapper_role_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scheduler").mkdir()
            document = {
                "schema": RETAINED_LAYOUT_SCHEMA,
                "wrapper_component": "components/scheduler-wrapper",
                "implementation_directory": "scheduler",
                "framework_owned_paths": [],
                "lineage": {"kind": "initial"},
            }
            self._declared_project(root, document)
            lift_shift = {
                "implementation_directory": "scheduler",
                "wrapper_component": "components/scheduler-wrapper",
                "layout_identity": RetainedLayoutDeclaration.from_dict(
                    document
                ).identity,
            }
            layout = resolve_structural_layout(root, lift_shift)
            self.assertEqual(layout.implementation_root, root / "scheduler")
            self.assertEqual(layout.wrapper_root, root / "components/scheduler-wrapper")
            with self.assertRaises(RetainedLayoutError):
                resolve_structural_layout(
                    root, {**lift_shift, "layout_identity": "bad"}
                )
            (layout.wrapper_root / "component.md").write_text(
                (layout.wrapper_root / "component.md")
                .read_text(encoding="utf-8")
                .replace("  - adoption-shim\n", ""),
                encoding="utf-8",
            )
            with self.assertRaises(RetainedLayoutError):
                resolve_structural_layout(root, lift_shift)

    def test_root_layout_requires_current_framework_file_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous_identity = canonical_identity({"previous_layout": "scheduler"}).uri
            document = {
                "schema": RETAINED_LAYOUT_SCHEMA,
                "wrapper_component": "components/scheduler-wrapper",
                "implementation_directory": ".",
                "framework_owned_paths": [
                    ".literate/initialization-baseline.json",
                    ".literate/retained-layout.json",
                    "components/scheduler-wrapper/component.md",
                    "docs/framework.md",
                    "literate.project.json",
                ],
                "lineage": {
                    "kind": "relocation",
                    "previous_layout_identity": previous_identity,
                },
            }
            self._declared_project(root, document)
            lift_shift = {
                "implementation_directory": ".",
                "wrapper_component": "components/scheduler-wrapper",
                "layout_identity": RetainedLayoutDeclaration.from_dict(
                    document
                ).identity,
                "previous_layout_identity": previous_identity,
            }
            with self.assertRaises(RetainedLayoutError):
                resolve_structural_layout(root, lift_shift)
            framework = root / "docs/framework.md"
            framework.parent.mkdir()
            framework.write_text("framework\n", encoding="utf-8")
            baseline = ProjectInitializationBaseline(
                origin_identity=canonical_identity({"origin": "test"}),
                template_protocol="literate-ai/project-template@1",
                files=(
                    ProjectInitializationBaselineFile(
                        path="docs/framework.md",
                        size=len(framework.read_bytes()),
                        identity=canonical_identity({"framework": "test"}),
                    ),
                ),
            )
            (root / ".literate/initialization-baseline.json").write_bytes(
                canonical_json_bytes(baseline.to_dict()) + b"\n"
            )
            (root / "literate.project.json").write_text("{}\n", encoding="utf-8")
            self.assertEqual(
                resolve_structural_layout(root, lift_shift).implementation_root, root
            )
            with self.assertRaises(RetainedLayoutError):
                resolve_structural_layout(
                    root, {**lift_shift, "previous_layout_identity": "bad"}
                )
            (root / ".literate/new-framework-file.json").write_text(
                "{}\n", encoding="utf-8"
            )
            with self.assertRaises(RetainedLayoutError):
                resolve_structural_layout(root, lift_shift)

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
                ".literate/initialization-baseline.json",
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
                ".literate/initialization-baseline.json",
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
                "source",
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
        coordinate = "components/legacy-project-wrapper/implementation"
        for redirected in ("ancestor", "final"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                try:
                    if redirected == "ancestor":
                        (root / "real/legacy-project-wrapper/implementation").mkdir(
                            parents=True
                        )
                        (root / "components").symlink_to(
                            root / "real", target_is_directory=True
                        )
                    else:
                        (root / "real/implementation").mkdir(parents=True)
                        wrapper = root / LEGACY_WRAPPER_COMPONENT
                        wrapper.mkdir(parents=True)
                        (wrapper / "implementation").symlink_to(
                            root / "real/implementation", target_is_directory=True
                        )
                except (OSError, NotImplementedError) as exc:
                    self.skipTest(f"symlinks unavailable: {exc}")
                with (
                    self.subTest(redirected=redirected),
                    self.assertRaises(RetainedLayoutError),
                ):
                    resolve_legacy_implementation(
                        root, {"implementation_directory": coordinate}
                    )
