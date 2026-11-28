"""Actual declared taxonomy ownership, references and preserved content pins."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path, PurePosixPath
from unittest.mock import patch

from literate_ai.application.agent_skill_catalog import (
    AgentSkillCatalog,
    AgentSkillCatalogError,
)
from literate_ai.projects import (
    ProjectError,
    load_project,
    project_skill_catalog,
    serialize_project_configuration,
)
from tests.support.fixtures_test_project_configuration import _definition


def skill(name, body):
    return f"---\nname: {name}\ndescription: Fixture skill.\n---\n{body}\n".encode()


class ContainedDeclaredSkillCatalogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.files = {
            "litai/SKILL.md": skill(
                "root", "Read `litai/skills/agent/child/SKILL.md`."
            ),
            "litai/skills/agent/child/SKILL.md": skill(
                "child", "Follow `skills/agent/other/SKILL.md`."
            ),
            "litai/skills/agent/child/script.py": b"print('owned fixture')\n",
            "litai/skills/agent/other/SKILL.md": skill("other", "Use local inputs."),
        }
        for name, content in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.definition = replace(
            _definition(),
            framework_directory="litai",
            agent_skill="litai/SKILL.md",
            skill_roots=("litai/skills",),
        )
        self.configure()

    def configure(self):
        (self.root / "litai/literate.project.json").write_bytes(
            serialize_project_configuration(self.definition)
        )

    def test_actual_location_alias_keeps_identity_ancestry_and_all_resource_ownership(
        self,
    ):
        catalog = project_skill_catalog(load_project(self.root))
        child = catalog.by_name("child")
        self.assertEqual(
            child.logical_manifest, PurePosixPath("skills/agent/child/SKILL.md")
        )
        self.assertEqual(
            child.manifest_path, self.root / "litai/skills/agent/child/SKILL.md"
        )
        self.assertEqual(child.ancestors, ("root",))
        self.assertEqual(
            child.identity,
            "sha256:"
            + hashlib.sha256(
                self.files["litai/skills/agent/child/SKILL.md"]
            ).hexdigest(),
        )
        self.assertIs(catalog.owner_for("litai/skills/agent/child/script.py"), child)
        self.assertEqual(catalog.unresolved_references(), ())
        for name, content in self.files.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        self.assertFalse((self.root / "litai/.literate/imports.json").exists())

    def test_ambient_same_bytes_cannot_shadow_declared_contained_authority(self):
        path = self.root / "skills/agent/other/SKILL.md"
        path.parent.mkdir(parents=True)
        original = self.files["litai/skills/agent/other/SKILL.md"]
        path.write_bytes(original)
        with self.assertRaises(ProjectError) as raised:
            project_skill_catalog(load_project(self.root))
        self.assertEqual(raised.exception.code, "project.skill_placement_conflict")
        self.assertEqual(path.read_bytes(), original)

    def test_shadow_alias_is_refused_without_opening_its_target(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "skills").symlink_to(outside, target_is_directory=True)
        original_open = Path.open
        calls = []

        def guarded(path, *args, **kwargs):
            if path.is_relative_to(outside) or path.is_relative_to(
                self.root / "skills"
            ):
                calls.append(path)
                raise AssertionError("shadow target opened")
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", guarded), self.assertRaises(ProjectError):
            project_skill_catalog(load_project(self.root))
        self.assertEqual(calls, [])

    def test_other_explicit_catalog_root_keeps_its_actual_coordinates(self):
        path = self.root / "custom-skills/extra/SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_bytes(skill("extra", "Keep the independently declared location."))
        self.definition = replace(
            self.definition, skill_roots=("litai/skills", "custom-skills")
        )
        self.configure()
        catalog = project_skill_catalog(load_project(self.root))
        self.assertEqual(catalog.by_name("extra").manifest_path, path)
        self.assertEqual(
            catalog.by_name("extra").logical_manifest,
            PurePosixPath("custom-skills/extra/SKILL.md"),
        )

    def test_location_alias_must_select_an_actually_declared_root(self):
        with self.assertRaises(AgentSkillCatalogError) as raised:
            AgentSkillCatalog.discover(
                self.root,
                catalog_roots=(self.root / "litai/skills",),
                reference_root_coordinates={"skills": "litai/unrelated"},
            )
        self.assertEqual(raised.exception.code, "agent_skill.path_conflict")

    def test_contained_root_skill_and_unmoved_declared_catalog_keep_logical_join(self):
        (self.root / "litai/skills").rename(self.root / "skills")
        root = self.root / "litai/SKILL.md"
        root.write_bytes(
            skill("root", "Read `litai/SKILL.md` and `skills/agent/child/SKILL.md`.")
        )
        self.definition = replace(self.definition, skill_roots=("skills",))
        self.configure()
        catalog = project_skill_catalog(load_project(self.root))
        self.assertEqual(
            catalog.by_name("root").logical_manifest, PurePosixPath("SKILL.md")
        )
        self.assertEqual(catalog.by_name("root").manifest_path, root)
        self.assertEqual(catalog.by_name("child").ancestors, ("root",))
        self.assertEqual(catalog.unresolved_references(), ())
        # Alias authority comes from the actual declared agent coordinate. It
        # does not admit a competing old-root file, even when bytes match.
        (self.root / "SKILL.md").write_bytes(root.read_bytes())
        with self.assertRaises(ProjectError) as caught:
            project_skill_catalog(load_project(self.root))
        self.assertEqual(caught.exception.code, "project.skill_placement_conflict")
