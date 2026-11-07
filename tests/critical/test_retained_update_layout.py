"""Update planning keeps conversion shim authority at the recorded source layout."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.project_updates import (
    ProjectUpdateError,
    _retained_legacy_shim_authority_paths,
)


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

    def test_update_preserves_shim_at_historical_coordinate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._project(root, "components/legacy-project-wrapper/implementation")
            protected = _retained_legacy_shim_authority_paths(root)
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
            root = Path(directory)
            self._project(root, "components/legacy-project-wrapper/implementation")
            (root / "scheduler").mkdir()
            for changed in ("scheduler", "scheduler/../scheduler"):
                with self.subTest(changed=changed):
                    (root / ".literate/legacy-lift-shift.json").write_text(
                        json.dumps({"implementation_directory": changed}),
                        encoding="utf-8",
                    )
                    with self.assertRaises(ProjectUpdateError) as captured:
                        _retained_legacy_shim_authority_paths(root)
                    self.assertEqual(
                        captured.exception.code,
                        "project.update_retained_layout_invalid",
                    )
