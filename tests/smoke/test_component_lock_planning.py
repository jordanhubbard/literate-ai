"""Filesystem Component-lock planning adapter tests."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.component_lock_planning import (
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.contracts import CatalogImportsFile
from literate_ai.contracts.catalog_imports import (
    CatalogImport,
    CatalogImportFile,
    CatalogImportSource,
)
from literate_ai.projects import ProjectError

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _component_document() -> str:
    return """---
namespace: examples
version: 1.0.0
display_name: Portable Greeting
profiles:
  - application
  - portable
sample: true
provides:
  - name: sample.portable-app
    version: 1.0.0
requires: []
specification_provider: openspec
specification_roots:
  - specs/spec.md
authoring_inputs:
  - kind: specification-to-source-skill
    uri: skills/implement.json
workflow_definition: workflows/host.json
routing_policy: routing/default.json
flavor_slots:
  - slot_id: language
    axis: implementation.language-ecosystem
    cardinality: exactly-one
    capability_contract: sample.portable-app
  - slot_id: os
    axis: platform.os
    cardinality: exactly-one
    capability_contract: sample.portable-app
entrypoints:
  - name: run
    kind: portable-application
    path: run
acceptance_contracts:
  - acceptance/execution.json
source_dependencies: []
---
A small portable greeting application with deterministic behavior.
"""


def _fixture(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        "---\n"
        "name: fixture-project\n"
        "description: Component-lock planning fixture.\n"
        "---\n"
        "# Fixture project\n",
        encoding="utf-8",
        newline="\n",
    )
    component = root / "greeting"
    for relative, content in {
        "component.md": _component_document(),
        "specs/spec.md": (
            "# Greeting\n\n### Requirement: Deterministic greeting\n\n"
            "The application SHALL print a stable greeting.\n\n"
            "#### Scenario: Run greeting\n\n- **WHEN** the application runs\n"
            "- **THEN** it prints `hello`\n"
        ),
        "acceptance/execution.json": '{"stdout":"hello\\n"}\n',
    }.items():
        path = component / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    for relative, content in {
        "skills/implement.json": '{"skill":"portable"}\n',
        "workflows/host.json": '{"workflow":"host"}\n',
        "routing/default.json": '{"routing":"default"}\n',
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    flavors = root / "flavors"
    for flavor in ("os-macos", "lang-python"):
        shutil.copytree(_REPOSITORY_ROOT / "flavors" / flavor, flavors / flavor)
    for skill in (
        "portable-specification-planning",
        "portable-application-implementation",
        "python-portable-application",
    ):
        shutil.copytree(
            _REPOSITORY_ROOT / "skills" / "specification-to-source" / skill,
            root / "skills" / "specification-to-source" / skill,
        )
    return component, flavors


class ComponentLockPlanningTests(unittest.TestCase):
    def test_selected_flavor_content_resolves_recorded_contained_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            component, flavors = _fixture(root)
            logical = (
                "skills/specification-to-source/python-portable-application/SKILL.md"
            )
            physical = f"litai/{logical}"
            source = root / logical
            original = source.read_bytes()
            identity = "sha256:" + hashlib.sha256(original).hexdigest()
            (root / physical).parent.mkdir(parents=True)
            source.rename(root / physical)
            definition = json.loads(
                (_REPOSITORY_ROOT / "literate.project.json").read_bytes()
            )
            definition.update(
                framework_directory="litai",
                component_roots=["greeting"],
                flavor_roots=["flavors"],
                skill_roots=["skills", "litai/skills"],
            )
            (root / "litai/literate.project.json").write_text(json.dumps(definition))
            CatalogImportsFile(
                (
                    CatalogImport(
                        "skill",
                        "specification-to-source/python-portable-application",
                        CatalogImportSource(
                            "parent",
                            identity,
                            "git:https://example.invalid/parent.git@" + "a" * 40,
                            (),
                        ),
                        (CatalogImportFile(physical, identity),),
                        "2026-01-01T00:00:00Z",
                    ),
                )
            ).save(root / "litai")
            snapshot = FilesystemComponentLockPlanner().snapshot(
                component, flavor_roots=(flavors,)
            )
            selected = next(
                f for f in snapshot._flavors if f.path.parent.name == "lang-python"
            )
            reference = next(
                row
                for row in selected.definition.authoring_inputs
                if row.kind == "specification-to-source-skill"
            )
            self.assertEqual(reference.identity.uri, identity)
            self.assertEqual(
                snapshot.flavor_content(selected.revision.identity, reference), original
            )
            target = root / physical
            target.write_bytes(original + b"\nchanged\n")
            with self.assertRaises(ComponentLockPlanningError) as stale:
                snapshot.flavor_content(selected.revision.identity, reference)
            self.assertEqual(stale.exception.code, "component_lock.stale")
            target.write_bytes(original)
            source.write_bytes(original)
            with self.assertRaises(ProjectError) as shadow:
                snapshot.flavor_content(selected.revision.identity, reference)
            self.assertEqual(shadow.exception.code, "project.skill_placement_conflict")

    def test_authority_directory_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            component, flavors = _fixture(root)
            workflow = root / "workflows"
            actual = root / "actual-workflows"
            workflow.rename(actual)
            try:
                workflow.symlink_to(actual, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symbolic links are unavailable: {exc}")

            with self.assertRaisesRegex(ComponentLockPlanningError, "unsafe directory"):
                FilesystemComponentLockPlanner().plan(
                    component,
                    target_name="macos-host",
                    flavor_selectors=("+macos", "+python"),
                    flavor_roots=(flavors,),
                )


if __name__ == "__main__":
    unittest.main()
