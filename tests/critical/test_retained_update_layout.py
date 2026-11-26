"""Update planning keeps conversion shim authority at the recorded source layout."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.harness_inventory import legacy_shim_authority
from literate_ai.adapters.project_updates import (
    ProjectUpdateError,
    _retained_legacy_shim_authority_paths,
)
from literate_ai.adapters.retained_layout import (
    RETAINED_LAYOUT_SCHEMA,
    RetainedLayoutDeclaration,
)
from literate_ai.contracts import canonical_json_bytes


class RetainedUpdateLayoutTests(unittest.TestCase):
    def _project(self, root: Path, implementation: str) -> None:
        files = (
            ".literate/harness-inventory.json",
            "components/legacy-project-wrapper/component.md",
            "flavors/legacy-project-shim/flavor.md",
            "flavors/legacy-project-shim/openspec/spec.md",
            "workflows/legacy-adoption/workflow.md",
            "routing/legacy-adoption.json",
            "skills/specification-to-source/legacy-project-shim/SKILL.md",
        )
        for relative in files:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("retained\n", encoding="utf-8")
        (root / implementation).mkdir(parents=True)
        (root / ".literate/legacy-lift-shift.json").write_text(
            json.dumps({"implementation_directory": implementation}),
            encoding="utf-8",
        )

    def _contained_project(self, root):
        from tests.support.fixtures_test_repository_initialization_e2e import (
            initialize_root,
        )

        initialize_root(root)
        self._project(root, "components/legacy-project-wrapper/implementation")
        for name in (
            ".literate/harness-inventory.json",
            ".literate/legacy-lift-shift.json",
            "components/legacy-project-wrapper/component.md",
            "flavors/legacy-project-shim/flavor.md",
            "flavors/legacy-project-shim/openspec/spec.md",
            "workflows/legacy-adoption/workflow.md",
            "routing/legacy-adoption.json",
            "skills/specification-to-source/legacy-project-shim/SKILL.md",
        ):
            target = root / "litai" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            (root / name).replace(target)

    def test_contained_catalogs_preserve_shim_without_relocating_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._contained_project(root)
            implementation = root / "components/legacy-project-wrapper/implementation"
            before = implementation.stat()
            wrapper = "litai/components/legacy-project-wrapper/"
            (root / (wrapper + "component.lock.json")).write_bytes(b"lock fixture\n")
            protected = _retained_legacy_shim_authority_paths(
                root, preserve_evidence=True
            )
            self.assertEqual(
                protected,
                frozenset(
                    {
                        wrapper + "component.md",
                        wrapper + "component.lock.json",
                        "litai/flavors/legacy-project-shim/flavor.md",
                        "litai/flavors/legacy-project-shim/openspec/spec.md",
                    }
                ),
            )
            self.assertEqual(implementation.stat(), before)
            self.assertFalse(
                (
                    root / "litai/components/legacy-project-wrapper/implementation"
                ).exists()
            )

    def test_mixed_catalogs_select_current_wrapper_and_keep_source_at_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._contained_project(root)
            manifest = root / "litai/literate.project.json"
            definition = json.loads(manifest.read_bytes())
            definition["component_roots"].insert(0, "components")
            manifest.write_text(json.dumps(definition))
            protected = _retained_legacy_shim_authority_paths(root)
            self.assertIn(
                "litai/components/legacy-project-wrapper/component.md", protected
            )
            self.assertNotIn(
                "components/legacy-project-wrapper/component.md", protected
            )
            self.assertTrue(
                (root / "components/legacy-project-wrapper/implementation").is_dir()
            )
            self.assertFalse(
                (
                    root / "litai/components/legacy-project-wrapper/implementation"
                ).exists()
            )

    def test_missing_current_dependent_does_not_protect_obsolete_shim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._contained_project(root)
            (root / "litai/routing/legacy-adoption.json").unlink()
            self.assertEqual(_retained_legacy_shim_authority_paths(root), frozenset())

    def test_duplicate_declared_shim_flavors_refuse_ambiguous_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._contained_project(root)
            manifest = root / "litai/literate.project.json"
            definition = json.loads(manifest.read_bytes())
            definition["flavor_roots"].append("other-flavors")
            manifest.write_text(json.dumps(definition))
            duplicate = root / "other-flavors/legacy-project-shim/flavor.md"
            duplicate.parent.mkdir(parents=True)
            duplicate.write_bytes(b"ambiguous fixture\n")
            with self.assertRaises(ProjectUpdateError) as captured:
                _retained_legacy_shim_authority_paths(root)
            self.assertEqual(
                captured.exception.code, "project.update_retained_layout_invalid"
            )

    def test_update_preserves_shim_at_historical_coordinate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._project(root, "components/legacy-project-wrapper/implementation")
            protected = _retained_legacy_shim_authority_paths(
                root, preserve_evidence=False
            )
            self.assertEqual(
                protected,
                frozenset(
                    {
                        "components/legacy-project-wrapper/component.md",
                        "flavors/legacy-project-shim/flavor.md",
                        "flavors/legacy-project-shim/openspec/spec.md",
                    }
                ),
            )

    def test_invalid_recorded_source_refuses_update_classification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self._project(root, "components/legacy-project-wrapper/implementation")
            (root / "scheduler").mkdir()
            for changed in ("scheduler", "scheduler/../scheduler"):
                with self.subTest(changed=changed):
                    (root / ".literate/legacy-lift-shift.json").write_text(
                        json.dumps({"implementation_directory": changed}),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ProjectUpdateError) as captured:
                        _retained_legacy_shim_authority_paths(
                            root, preserve_evidence=False
                        )
                    self.assertEqual(
                        captured.exception.code,
                        "project.update_retained_layout_invalid",
                    )

    def test_update_preserves_selected_wrapper_shim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            wrapper = "components/scheduler-wrapper"
            document = {
                "schema": RETAINED_LAYOUT_SCHEMA,
                "wrapper_component": wrapper,
                "implementation_directory": "scheduler",
                "framework_owned_paths": [],
                "lineage": {"kind": "initial"},
            }
            (root / "scheduler").mkdir()
            (root / ".literate").mkdir()
            (root / ".literate/retained-layout.json").write_bytes(
                canonical_json_bytes(document) + b"\n"
            )
            (root / ".literate/legacy-lift-shift.json").write_text(
                json.dumps(
                    {
                        "implementation_directory": "scheduler",
                        "wrapper_component": wrapper,
                        "layout_identity": RetainedLayoutDeclaration.from_dict(
                            document
                        ).identity,
                    }
                ),
                encoding="utf-8",
            )
            (root / ".literate/harness-inventory.json").write_text(
                "{}\n", encoding="utf-8"
            )
            shim = legacy_shim_authority(
                {"commands": {}, "stages": []},
                {"phases": []},
                wrapper_component=wrapper,
            )
            for relative, content in shim.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            for relative in (
                "workflows/legacy-adoption/workflow.md",
                "routing/legacy-adoption.json",
                "skills/specification-to-source/legacy-project-shim/SKILL.md",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("retained\n", encoding="utf-8")
            self.assertEqual(
                _retained_legacy_shim_authority_paths(root, preserve_evidence=False),
                frozenset(
                    {
                        f"{wrapper}/component.md",
                        "flavors/legacy-project-shim/flavor.md",
                        "flavors/legacy-project-shim/openspec/spec.md",
                    }
                ),
            )
            (root / ".literate/legacy-lift-shift.json").write_text(
                json.dumps({"implementation_directory": "scheduler"}),
                encoding="utf-8",
            )
            with self.assertRaises(ProjectUpdateError) as captured:
                _retained_legacy_shim_authority_paths(root, preserve_evidence=False)
            self.assertEqual(
                captured.exception.code, "project.update_retained_layout_invalid"
            )
