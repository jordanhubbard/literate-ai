"""Explicit original selected/resident maps and exact resource transitions."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path

from literate_ai.adapters import project_initialization as initializer
from literate_ai.adapters.project_scaffold_placement import project_scaffold_placement
from literate_ai.adapters.project_scaffold_references import (
    validate_reference_coordinates,
)
from literate_ai.adapters.project_scaffold_transitions import (
    reviewed_bootstrap_transition,
)


class ProjectScaffoldReferenceMapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.placement = project_scaffold_placement(
            self.root,
            (
                *initializer._TEMPLATE_FILES,
                *initializer._STARTER_TEMPLATE_FILES,
                *initializer._STARTER_DOCS,
            ),
        )

    def test_catalog_authority_is_byte_exact_with_default_and_explicit_maps(self):
        logical = "skills/agent/example/SKILL.md"
        placement = project_scaffold_placement(self.root, (logical,))
        content = b"`docs/` [reference](../../../docs/README.md)\n"
        self.assertEqual(placement.template_content(logical, content), content)
        self.assertEqual(
            placement.template_content(
                logical,
                content,
                coordinate_map={
                    logical: "litai/" + logical,
                    "docs/README.md": "litai/docs/README.md",
                },
            ),
            content,
        )
        with self.assertRaises(ValueError):
            placement.template_content(logical, content, coordinate_map={})

    def test_explicit_map_has_no_implicit_taxonomy_or_starter_selection(self):
        content = (
            b"`skills/agent/` `docs/` `samples/hello-component`\n"
            b"`skills/agent/release-project/SKILL.md`\n"
        )
        rendered = self.placement.template_content(
            "SKILL.md", content, coordinate_map={"SKILL.md": "litai/SKILL.md"}
        )
        self.assertEqual(rendered, content)
        selected = self.placement.template_content(
            "SKILL.md",
            content,
            coordinate_map={
                "SKILL.md": "litai/SKILL.md",
                "skills/agent/": "litai/skills/agent/",
            },
        )
        self.assertIn(b"`litai/skills/agent/`", selected)
        self.assertIn(b"`skills/agent/release-project/SKILL.md`", selected)
        self.assertNotIn(b"litai/docs/", selected)

    def test_moved_doc_links_actual_selected_and_resident_targets(self):
        content = (
            b"[resident](skills/agent/release-project/SKILL.md)\n"
            b"[selected](docs/README.md#guide)\n"
        )
        rendered = self.placement.template_content(
            "SKILL.md",
            content,
            coordinate_map={
                "SKILL.md": "litai/SKILL.md",
                "docs/README.md": "litai/docs/README.md",
            },
        )
        self.assertIn(b"[resident](../skills/agent/release-project/SKILL.md)", rendered)
        self.assertIn(b"[selected](docs/README.md#guide)", rendered)
        self.assertNotIn(b"litai/litai", rendered)

    def test_typed_release_refs_do_not_select_an_unrelated_component(self):
        value = {
            "version_authority": {"path": "literate.project.json"},
            "gate": {
                "argv": ["litai", "test", "samples/hello-component", "--target", "host"]
            },
            "contributions": {
                "roadmap_goal_manifest": "docs/roadmap/release-goals.json"
            },
        }
        coordinates = {
            "literate.release.json": "litai/literate.release.json",
            "docs/roadmap/release-goals.json": "litai/docs/roadmap/release-goals.json",
        }
        rendered = json.loads(
            self.placement.template_content(
                "literate.release.json",
                json.dumps(value).encode(),
                coordinate_map=coordinates,
            )
        )
        self.assertEqual(rendered["version_authority"]["path"], "literate.project.json")
        self.assertEqual(rendered["gate"]["argv"], value["gate"]["argv"])
        self.assertEqual(
            rendered["contributions"]["roadmap_goal_manifest"],
            "litai/docs/roadmap/release-goals.json",
        )

    def test_new_default_rendering_retains_original_known_semantics(self):
        content = (
            b"`skills/agent/` `samples/hello-component`\n[product](../CHANGELOG.md)\n"
        )
        self.assertIn(
            b"`litai/skills/agent/`",
            self.placement.template_content("SKILL.md", content),
        )
        self.assertIn(
            b"`litai/samples/hello-component`",
            self.placement.template_content("SKILL.md", content),
        )
        self.assertEqual(
            self.placement.template_content(
                "docs/README.md", b"[product](../CHANGELOG.md)\n"
            ),
            b"[product](../../CHANGELOG.md)\n",
        )

    def test_explicit_document_binding_and_portable_aliases_are_required(self):
        for coordinates in (
            {},
            {"SKILL.md": "litai/SKILL.md", "skill.md": "other.md"},
            {"SKILL.md": "../outside"},
        ):
            with self.assertRaises(ValueError):
                validate_reference_coordinates(coordinates, document="SKILL.md")

    def test_legacy_whole_region_replaced_once_and_custom_outside_preserved(self):
        old = (
            b"# Original reviewed full framework instructions\nDo old framework work.\n"
        )
        prefix, suffix = b"# Native custom instructions\n", b"Native custom suffix.\n"
        before = prefix + old + suffix
        edit = self.placement.plan_delegate(
            "AGENTS.md",
            before,
            legacy_owned_region=old,
            coordinate_map={"AGENTS.md": "AGENTS.md", "SKILL.md": "SKILL.md"},
        )
        self.assertTrue(edit.content.startswith(prefix))
        self.assertTrue(edit.content.endswith(suffix))
        self.assertNotIn(old, edit.content)
        self.assertIn(b"](SKILL.md)", edit.content)
        self.assertNotIn(b"litai/SKILL.md", edit.content)
        edit.require_current(before)
        with self.assertRaises(ValueError):
            edit.require_current(before + b"concurrent edit")

    def test_changed_ambiguous_or_nonboundary_legacy_region_never_appends(self):
        region = b"original reviewed instructions"
        for current in (
            b"changed instructions",
            region + b"\n" + region,
            b"prefix" + region,
            region + b"suffix",
        ):
            with self.assertRaises(ValueError):
                self.placement.plan_delegate(
                    "AGENTS.md", current, legacy_owned_region=region
                )

    def test_cursor_legacy_full_template_keeps_minimal_native_frontmatter(self):
        old = b"---\nalwaysApply: true\n---\n# Old expanded framework rules\n"
        suffix = b"# Native custom suffix\n"
        edit = self.placement.plan_delegate(
            ".cursor/rules/literate-ai.mdc", old + suffix, legacy_owned_region=old
        )
        self.assertTrue(
            edit.content.startswith(
                b"---\ndescription: Project onboarding\nalwaysApply: true\n---\n"
            )
        )
        self.assertTrue(edit.content.endswith(suffix))
        self.assertNotIn(b"Old expanded", edit.content)

    def test_resident_application_ignore_and_history_are_not_framework_moves(self):
        for logical in (".gitignore", "CHANGELOG.md"):
            current = b"actual product/user bytes\n"
            self.assertEqual(
                self.placement.template_content(
                    logical, current, coordinate_map={logical: logical}
                ),
                current,
            )
        with self.assertRaises(ValueError):
            self.placement.template_content(
                "CHANGELOG.md",
                b"product",
                coordinate_map={"CHANGELOG.md": "litai/CHANGELOG.md"},
            )

    def _bootstrap(self):
        resource = files("literate_ai.project_template").joinpath("scripts")
        before = b"# Exact original reviewed historical bootstrap\n"
        after = resource.joinpath("bootstrap_litai.py").read_bytes()
        helper = resource.joinpath("_bootstrap_processes.py").read_bytes()
        arguments = {
            "original_before_bytes": before,
            "original_after_bytes": after,
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest(),
            "original_helper_bytes": helper,
            "helper_sha256": hashlib.sha256(helper).hexdigest(),
            "coordinate_map": {
                "scripts/bootstrap_litai.py": "litai/scripts/bootstrap_litai.py",
                "scripts/_bootstrap_processes.py": (
                    "litai/scripts/_bootstrap_processes.py"
                ),
            },
        }
        return before, after, arguments

    def test_reviewed_bootstrap_transition_binds_original_bytes_and_helper(self):
        before, after, arguments = self._bootstrap()
        self.assertEqual(reviewed_bootstrap_transition(before, **arguments), after)
        with self.assertRaises(ValueError):
            reviewed_bootstrap_transition(before + b"custom", **arguments)
        with self.assertRaisesRegex(ValueError, "reviewed update transition"):
            self.placement.template_content(
                "scripts/bootstrap_litai.py",
                before,
                coordinate_map=arguments["coordinate_map"],
            )

    def test_bootstrap_wrong_resource_or_separated_helper_refuses(self):
        before, _, arguments = self._bootstrap()
        for changes in (
            {"after_sha256": "0" * 64},
            {"helper_sha256": "0" * 64},
            {
                "coordinate_map": {
                    "scripts/bootstrap_litai.py": "litai/scripts/bootstrap_litai.py",
                    "scripts/_bootstrap_processes.py": (
                        "scripts/_bootstrap_processes.py"
                    ),
                }
            },
        ):
            with self.assertRaises(ValueError):
                reviewed_bootstrap_transition(before, **{**arguments, **changes})
