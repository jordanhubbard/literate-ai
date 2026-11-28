from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path

from literate_ai.application.agent_skill_catalog import (
    AgentSkillCatalog,
    AgentSkillCatalogError,
)
from literate_ai.projects import read_only_project_configuration_parses


def _skill(name: str, body: str = "# Skill\n\nDo the bounded work.") -> bytes:
    return (f"---\nname: {name}\ndescription: Bounded skill.\n---\n{body}\n").encode()


class AgentSkillCatalogTests(unittest.TestCase):
    def test_stale_typed_dependency_and_unresolved_reference_fail_closed(self) -> None:
        stale = (
            "---\nname: dependent\nskill_id: dependent\nversion: 1.0.0\n"
            "dependencies:\n  - skill_id: base\n    version: 1.0.0\n"
            '    identity:\n      algorithm: sha256\n      digest: "'
            + "0" * 64
            + '"\n---\n# Dependent\n'
        ).encode()
        with self.assertRaises(AgentSkillCatalogError) as caught:
            AgentSkillCatalog.from_documents(
                {
                    "skills/base/SKILL.md": _skill("base").replace(
                        b"description: Bounded skill.\n",
                        b"description: Bounded skill.\n"
                        b"skill_id: base\nversion: 1.0.0\n",
                    ),
                    "skills/dependent/SKILL.md": stale,
                }
            )
        self.assertEqual(caught.exception.code, "agent_skill.dependency_identity_stale")

        with self.assertRaises(AgentSkillCatalogError) as missing:
            AgentSkillCatalog.from_documents(
                {"SKILL.md": _skill("root", "Follow `skills/agent/missing/SKILL.md`.")},
                validate_references=True,
            )
        self.assertEqual(missing.exception.code, "agent_skill.reference_missing")

    def test_recorded_placement_keeps_held_child_under_its_logical_parent(self):
        original = "skills/agent/SKILL.md"
        placed = "litai/skills/agent/SKILL.md"
        held = "skills/agent/checkout/SKILL.md"
        documents = {
            placed: _skill("agent"),
            held: _skill("checkout", "Follow `../SKILL.md`."),
            "SKILL.md": _skill("root", f"Follow `{placed}`."),
        }
        catalog = AgentSkillCatalog.from_documents(
            documents,
            reference_coordinates={original: placed},
            validate_references=True,
        )
        self.assertEqual(catalog.by_name("checkout").ancestors, ("root", "agent"))
        self.assertEqual(catalog.by_name("agent").logical_manifest.as_posix(), original)
        self.assertEqual(catalog.owner_for(placed).name, "agent")
        with self.assertRaises(AgentSkillCatalogError) as alias:
            AgentSkillCatalog.from_documents(
                {**documents, original: documents[placed]},
                reference_coordinates={original: placed},
            )
        self.assertEqual(alias.exception.code, "agent_skill.path_conflict")

    def test_repository_and_shipped_template_are_closed_catalogs(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        framework = AgentSkillCatalog.discover(
            repository,
            catalog_roots=(repository / "skills",),
            root_manifests=(repository / "SKILL.md",),
            validate_references=True,
        )
        template = repository / "src/literate_ai/project_template"
        initialized = AgentSkillCatalog.discover(
            template,
            catalog_roots=(template / "skills",),
            root_manifests=(template / "SKILL.md",),
            validate_references=True,
        )
        self.assertGreater(len(framework.skills), len(initialized.skills))

        # A joined parse lifetime must never substitute a previous catalog or
        # its filesystem observations for this call's current manifest bytes.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            manifest = root / "skills/base/SKILL.md"
            manifest.parent.mkdir(parents=True)
            original = _skill("base")
            manifest.write_bytes(original)

            def discover(**kwargs):
                return AgentSkillCatalog.discover(
                    root, catalog_roots=(root / "skills",), **kwargs
                )

            with read_only_project_configuration_parses(isolated=True):
                first = discover()
                repeated = discover()
                self.assertEqual(first.skills, repeated.skills)
                first.skills = ()
                self.assertEqual(discover().skills, repeated.skills)
                manifest.write_bytes(original.replace(b"name: base", b"name: next"))
                changed = discover()
                self.assertEqual(changed.skills[0].name, "next")
                self.assertNotEqual(
                    changed.skills[0].identity, repeated.skills[0].identity
                )
                duplicate = root / "skills/other/SKILL.md"
                duplicate.parent.mkdir()
                duplicate.write_bytes(manifest.read_bytes())
                with self.assertRaises(AgentSkillCatalogError) as caught:
                    discover()
                self.assertEqual(caught.exception.code, "agent_skill.name_ambiguous")
                duplicate.unlink()
                manifest.write_bytes(
                    _skill("base", "Follow `skills/missing/SKILL.md`.")
                )
                discover()
                with self.assertRaises(AgentSkillCatalogError) as references:
                    discover(validate_references=True)
                self.assertEqual(
                    references.exception.code, "agent_skill.reference_missing"
                )
                manifest.write_bytes(original)
                self.assertEqual(discover().skills, repeated.skills)
                # Copied caller contexts can share this read-only parse frame.
                # Concurrent catalogs still own their names and byte identities.
                with ThreadPoolExecutor(max_workers=8) as pool:
                    futures = [
                        pool.submit(
                            copy_context().run,
                            AgentSkillCatalog.from_documents,
                            {f"skills/entry-{i}/SKILL.md": _skill(f"entry-{i}")},
                        )
                        for i in range(160)
                    ]
                    self.assertEqual(
                        [future.result().skills[0].name for future in futures],
                        [f"entry-{i}" for i in range(160)],
                    )
            manifest.write_bytes(_skill("outside"))
            self.assertEqual(discover().skills[0].name, "outside")


if __name__ == "__main__":
    unittest.main()
