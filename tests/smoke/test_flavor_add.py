"""Adding a Flavor to an existing project does not re-run init."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.flavor_add import FlavorAddError, add_flavor_to_project
from literate_ai.adapters.project_initialization import (
    FilesystemProjectInitializationAdapter,
    initialize_project,
)
from literate_ai.adapters.project_scaffold_placement import ScaffoldLayout
from literate_ai.contracts import RepositoryParentSelection
from literate_ai.contracts.authoring_markdown import (
    parse_authoring_markdown,
    render_authoring_markdown,
)
from literate_ai.projects import ProjectConfigurationStore


class FlavorAddTests(unittest.TestCase):
    def test_macos_project_can_gain_linux(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "project"
            initialize_project(
                target,
                parent_selection=RepositoryParentSelection.root(),
                source_intelligence_provider="none",
                empty=True,
                flavor_selectors=("+javascript", "+macos"),
            )
            (target / "samples" / "hello" / "component.md").parent.mkdir(parents=True)
            (target / "samples" / "hello" / "component.md").write_text(
                "# hello\n", encoding="utf-8"
            )
            (target / "samples" / "hello" / "component.lock.json").write_text(
                "{}\n", encoding="utf-8"
            )
            result = add_flavor_to_project(target, "linux")
            self.assertEqual(result["state"], "completed")
            context = ProjectConfigurationStore.context(target)
            self.assertTrue(
                context.framework_path("flavors/os-linux/flavor.md").is_file()
            )
            manifest = json.loads(context.manifest_path.read_text(encoding="utf-8"))
            self.assertIn(
                "+flavor://literate-ai/os-linux", manifest["default_flavor_selectors"]
            )
            self.assertFalse(
                (target / "samples" / "hello" / "component.lock.json").exists()
            )
            self.assertTrue((target / "samples" / "hello" / "component.md").is_file())

    def test_python_and_go_fail_closed_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "project"
            initialize_project(
                target,
                parent_selection=RepositoryParentSelection.root(),
                source_intelligence_provider="none",
                empty=True,
                flavor_selectors=("+python", "+macos"),
            )
            context = ProjectConfigurationStore.context(target)
            before = context.manifest_path.read_bytes()
            with self.assertRaises(FlavorAddError) as raised:
                add_flavor_to_project(target, "go")
            self.assertEqual(raised.exception.code, "flavor.add_conflict")
            self.assertEqual(before, context.manifest_path.read_bytes())
            self.assertFalse(context.framework_path("flavors/go").exists())

    def project(self, target, *, language="javascript"):
        initialize_project(
            target,
            parent_selection=RepositoryParentSelection.root(),
            source_intelligence_provider="none",
            empty=True,
            flavor_selectors=(f"+{language}", "+macos"),
        )
        context = ProjectConfigurationStore.context(target)
        self.assertEqual(context.framework_root, target / "litai")
        return context

    def mixed(self, target, *, language, duplicate=False):
        context = self.project(target, language=language)
        original = context.framework_path(f"flavors/lang-{language}")
        destination = target / f"flavors/lang-{language}"
        destination.parent.mkdir()
        if duplicate:
            shutil.copytree(original, destination)
        else:
            original.rename(destination)
        store = ProjectConfigurationStore(target)
        snapshot = store.read()
        store.update(
            snapshot,
            replace(
                snapshot.definition,
                flavor_roots=("flavors", "litai/flavors"),
                skill_roots=("skills", "litai/skills"),
            ),
        )
        return context, destination

    def test_contained_files_are_reported_at_actual_paths_and_repeat_is_idempotent(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "project"
            context = self.project(target, language="python")
            before = context.manifest_path.read_bytes()
            result = add_flavor_to_project(target, "elixir", set_default=False)
            self.assertTrue(result["created"])
            self.assertTrue(
                all(name.startswith("litai/") for name in result["created"])
            )
            self.assertTrue(
                all((target / name).is_file() for name in result["created"])
            )
            self.assertFalse((target / "flavors").exists())
            self.assertFalse((target / "skills").exists())
            repeated = add_flavor_to_project(target, "elixir", set_default=False)
            self.assertEqual(repeated["created"], [])
            self.assertEqual(context.manifest_path.read_bytes(), before)

    def test_existing_legacy_project_keeps_root_catalog_and_user_component(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "project"
            FilesystemProjectInitializationAdapter().initialize(
                target,
                parent_selection=RepositoryParentSelection.root(),
                source_intelligence_provider="none",
                empty=True,
                flavor_selectors=("+python", "+macos"),
                _layout=ScaffoldLayout.LEGACY_ROOT_FIXTURE,
            )
            context = ProjectConfigurationStore.context(target)
            self.assertEqual(context.framework_root, target)
            component = target / "component.md"
            component.write_bytes(b"# original user component\n")
            result = add_flavor_to_project(target, "elixir", set_default=False)
            self.assertTrue((target / "flavors/lang-elixir/flavor.md").is_file())
            self.assertTrue(
                (
                    target
                    / "skills/specification-to-source"
                    / "elixir-portable-application/SKILL.md"
                ).is_file()
            )
            self.assertTrue(
                all(not name.startswith("litai/") for name in result["created"])
            )
            self.assertEqual(component.read_bytes(), b"# original user component\n")

    def test_current_nondefault_incoming_flavor_keeps_its_own_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "project"
            context = self.project(target)
            add_flavor_to_project(target, "linux", set_default=False)
            path = context.framework_path("flavors/os-linux/flavor.md")
            document, body = parse_authoring_markdown(
                path.read_bytes(), source=str(path)
            )
            document["conflicts"].append("flavor://literate-ai/lang-javascript")
            path.write_bytes(render_authoring_markdown(document, body))
            before = {
                p.relative_to(target).as_posix(): p.read_bytes()
                for p in target.rglob("*")
                if p.is_file()
            }
            with self.assertRaises(FlavorAddError) as caught:
                add_flavor_to_project(target, "linux")
            self.assertEqual(caught.exception.code, "flavor.add_conflict")
            self.assertEqual(
                {
                    p.relative_to(target).as_posix(): p.read_bytes()
                    for p in target.rglob("*")
                    if p.is_file()
                },
                before,
            )

    def test_current_custom_declared_skill_is_preserved_on_noop_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "project"
            context = self.project(target, language="elixir")
            path = context.framework_path("flavors/lang-elixir/flavor.md")
            original = context.framework_path(
                "skills/specification-to-source/elixir-portable-application/SKILL.md"
            )
            custom = context.framework_path("skills/custom-elixir/SKILL.md")
            custom.parent.mkdir()
            original.rename(custom)
            document, body = parse_authoring_markdown(
                path.read_bytes(), source=str(path)
            )
            reference = next(
                item
                for item in document["authoring_inputs"]
                if item["kind"] == "specification-to-source-skill"
            )
            reference["uri"] = os.path.relpath(custom, path.parent).replace(os.sep, "/")
            path.write_bytes(render_authoring_markdown(document, body))
            before = {
                p.relative_to(target).as_posix(): p.read_bytes()
                for p in target.rglob("*")
                if p.is_file()
            }
            result = add_flavor_to_project(target, "elixir")
            self.assertEqual(result["state"], "unchanged")
            self.assertEqual(result["created"], [])
            self.assertEqual(
                {
                    p.relative_to(target).as_posix(): p.read_bytes()
                    for p in target.rglob("*")
                    if p.is_file()
                },
                before,
            )

    def test_unique_existing_mixed_flavor_keeps_its_original_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory).resolve() / "project"
            context, flavor = self.mixed(target, language="elixir")
            original_skill = context.framework_path(
                "skills/specification-to-source/elixir-portable-application"
            )
            skill = (
                target / "skills/specification-to-source/elixir-portable-application"
            )
            skill.parent.mkdir(parents=True)
            original_skill.rename(skill)
            original = (flavor / "flavor.md").read_bytes()
            result = add_flavor_to_project(target, "elixir")
            self.assertFalse(context.framework_path("flavors/lang-elixir").exists())
            self.assertTrue(
                all(not name.startswith("litai/") for name in result["created"])
            )
            self.assertEqual((flavor / "flavor.md").read_bytes(), original)
            self.assertTrue((skill / "SKILL.md").is_file())

    def test_mixed_current_conflicts_and_duplicate_authority_refuse_without_writes(
        self,
    ):
        for duplicate in (False, True):
            with (
                self.subTest(duplicate=duplicate),
                tempfile.TemporaryDirectory() as directory,
            ):
                target = Path(directory).resolve() / "project"
                _context, flavor = self.mixed(
                    target, language="javascript", duplicate=duplicate
                )
                path = flavor / "flavor.md"
                document, body = parse_authoring_markdown(
                    path.read_bytes(), source=str(path)
                )
                document["conflicts"].append("flavor://literate-ai/os-linux")
                path.write_bytes(render_authoring_markdown(document, body))
                before = {
                    p.relative_to(target).as_posix(): p.read_bytes()
                    for p in target.rglob("*")
                    if p.is_file()
                }
                with self.assertRaises(FlavorAddError) as caught:
                    add_flavor_to_project(target, "linux")
                self.assertEqual(
                    caught.exception.code,
                    "flavor.add_catalog_ambiguous"
                    if duplicate
                    else "flavor.add_conflict",
                )
                self.assertEqual(
                    {
                        p.relative_to(target).as_posix(): p.read_bytes()
                        for p in target.rglob("*")
                        if p.is_file()
                    },
                    before,
                )


if __name__ == "__main__":
    unittest.main()
