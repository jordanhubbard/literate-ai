"""Finite layout/delegate planning + real initializer routing; no project jobs."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from literate_ai.adapters import project_initialization as initializer
from literate_ai.adapters import project_scaffold_placement as scaffold
from literate_ai.contracts import (
    ProjectDefinition,
    RepositoryParentSelection,
    RepositoryPolicy,
)

_FILES = (
    "SKILL.md",
    "AGENTS.md",
    "CLAUDE.md",
    "agents/openai.yaml",
    ".cursor/rules/literate-ai.mdc",
    ".gitignore",
    "CHANGELOG.md",
    "docs/README.md",
    "docs/roadmap/active-work.md",
    "docs/roadmap/release-goals.json",
    "literate.release.json",
    "samples/hello-component/component.md",
    "skills/example/SKILL.md",
)


def _definition():
    return ProjectDefinition(
        project_id="scaffold-test",
        version="1.0.0",
        profile="canonical",
        agent_skill="SKILL.md",
        component_roots=("components", "samples"),
        flavor_roots=("flavors",),
        skill_roots=("skills",),
        workflow_roots=("workflows",),
        routing_roots=("routing",),
        mcp_roots=("mcps",),
        documentation_roots=("docs",),
        source_intelligence=initializer._source_intelligence_policy("none"),
        test_receipt="verification/current.json",
        source_cache=initializer._default_source_cache(),
        repository_policy=RepositoryPolicy(),
    )


class ProjectScaffoldPlacementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "application"
        self.root.mkdir()
        self.placement = scaffold.project_scaffold_placement(self.root, _FILES)

    def test_finite_roles_keep_application_root_and_framework_root_distinct(self):
        self.assertEqual(self.placement.context.root, self.root)
        self.assertEqual(self.placement.context.framework_root, self.root / "litai")
        self.assertEqual(
            self.placement.framework_coordinate("SKILL.md"), "litai/SKILL.md"
        )
        self.assertEqual(
            self.placement.entry("CHANGELOG.md").coordinate, "CHANGELOG.md"
        )
        self.assertEqual(self.placement.entry("AGENTS.md").role, "root-delegate")
        with self.assertRaisesRegex(ValueError, "not framework authority"):
            self.placement.framework_coordinate("CHANGELOG.md")
        with self.assertRaisesRegex(ValueError, "no ownership"):
            self.placement.framework_coordinate("components/app/implementation/main.rs")

    def test_definition_projects_only_declared_framework_fields_and_state(self):
        original = _definition()
        placed = self.placement.project_definition(original)
        self.assertEqual(placed.framework_directory, "litai")
        self.assertEqual(placed.agent_skill, "litai/SKILL.md")
        self.assertEqual(placed.component_roots, ("litai/components", "litai/samples"))
        self.assertEqual(placed.documentation_roots, ("litai/docs",))
        self.assertEqual(placed.test_receipt, "litai/verification/current.json")
        self.assertEqual(placed.log_dir, "litai/logs")
        self.assertEqual(
            placed.repository_policy.work_queue, "litai/docs/roadmap/active-work.md"
        )
        self.assertEqual(
            placed.repository_policy.release_engineer_source,
            "README.md#release-engineers",
        )
        operator_before, project_before = original.source_cache.targets
        operator_after, project_after = placed.source_cache.targets
        self.assertIs(operator_after, operator_before)
        self.assertEqual(
            project_before.root_reference, "generated/committed-source-cache"
        )
        self.assertEqual(
            project_after.root_reference, "litai/generated/committed-source-cache"
        )
        self.assertEqual(original.framework_directory, None)

    def test_explicit_internal_root_modes_never_inferred_from_parent_selection(self):
        original = _definition()
        for mode in (
            scaffold.ScaffoldLayout.FRAMEWORK_ROOT_AUTHORING,
            scaffold.ScaffoldLayout.LEGACY_ROOT_FIXTURE,
        ):
            projection = scaffold.project_scaffold_placement(
                self.root, _FILES, layout=mode
            )
            self.assertEqual(projection.context.framework_root, self.root)
            self.assertIs(projection.project_definition(original), original)
            self.assertEqual(
                projection.template_content("SKILL.md", b"original root bytes"),
                b"original root bytes",
            )
        with self.assertRaises(TypeError):
            scaffold.project_scaffold_placement(self.root, _FILES, layout="root")

    def test_unknown_application_path_and_portable_aliases_cannot_gain_framework_role(
        self,
    ):
        for extra in (
            ("source/main.rs",),
            ("skills/Example/SKILL.md",),
            ("docs/NUL",),
            ("../escape",),
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                scaffold.project_scaffold_placement(self.root, (*_FILES, *extra))

    def test_existing_destination_and_root_authority_refuse_without_writes(self):
        for name in ("litai", "literate.project.json"):
            target = self.root / name
            target.write_bytes(b"existing application bytes")
            with (
                self.subTest(name=name),
                self.assertRaises(scaffold.ScaffoldPlacementError),
            ):
                self.placement.preflight_new_destination()
            self.assertEqual(target.read_bytes(), b"existing application bytes")
            target.unlink()
        self.assertEqual(list(self.root.iterdir()), [])

    @unittest.skipUnless(os.name == "posix", "POSIX no-follow preflight control")
    def test_redirected_litai_destination_is_refused_without_target_probe(self):
        target = self.root / "litai"
        target.symlink_to(self.root.parent / "never-probed", target_is_directory=True)
        with patch.object(
            Path, "resolve", side_effect=AssertionError("must not resolve target")
        ):
            with self.assertRaisesRegex(ValueError, "existing litai"):
                self.placement.preflight_new_destination()

    def test_root_delegate_inventory_is_exact_and_minimal(self):
        for name in scaffold._ROOT_DELEGATES:
            edit = self.placement.plan_delegate(name, None)
            self.assertEqual(edit.coordinate, name)
            self.assertIn(b"litai/SKILL.md", edit.content)
            self.assertNotIn(b"specification", edit.content)
            self.assertLess(len(edit.content), 512)
        with self.assertRaises(scaffold.ScaffoldPlacementError):
            self.placement.plan_delegate("README.md", None)

    def test_custom_markdown_and_cursor_bytes_stay_outside_owned_regions(self):
        for name in ("AGENTS.md", "CLAUDE.md", ".cursor/rules/literate-ai.mdc"):
            custom = b"# Native project rules\nKeep the original instructions.\n"
            edit = self.placement.plan_delegate(name, custom)
            self.assertTrue(edit.content.startswith(custom))
            current = b"new custom preface\n" + edit.content + b"custom suffix\n"
            renewed = self.placement.plan_delegate(
                name, current, expected_region=edit.owned_region
            )
            self.assertTrue(
                renewed.content.startswith(b"new custom preface\n" + custom)
            )
            self.assertTrue(renewed.content.endswith(b"custom suffix\n"))

    def test_stale_plan_and_changed_owned_region_cannot_overwrite_custom_text(self):
        edit = self.placement.plan_delegate("AGENTS.md", b"custom\n")
        with self.assertRaisesRegex(ValueError, "changed after"):
            edit.require_current(b"later custom edit\n")
        tampered = edit.content.replace(
            b"Read and follow", b"changed owned instruction"
        )
        with self.assertRaisesRegex(ValueError, "differs from its original"):
            self.placement.plan_delegate(
                "AGENTS.md", tampered, expected_region=edit.owned_region
            )

    def test_yaml_custom_interface_and_ambiguous_markers_are_preserved_by_refusal(self):
        custom = b'interface:\n  default_prompt: "original native project"\n'
        with self.assertRaisesRegex(ValueError, "custom YAML interface"):
            self.placement.plan_delegate("agents/openai.yaml", custom)
        for text in (
            (scaffold._END + "\n" + scaffold._BEGIN).encode(),
            (scaffold._BEGIN + "\n" + scaffold._BEGIN).encode(),
        ):
            with self.assertRaises(ValueError):
                self.placement.plan_delegate("AGENTS.md", text)
        self.assertEqual(
            custom, b'interface:\n  default_prompt: "original native project"\n'
        )

    def test_ignore_rules_are_owned_under_litai_application_ignore_untouched(self):
        current = {
            ".gitignore": b"native-output/\n",
            "CHANGELOG.md": b"custom product history\n",
        }
        rows = self.placement.project_templates(
            {".gitignore": b"old template", "CHANGELOG.md": b"new seed"},
            application_files=current,
        )
        self.assertEqual(rows[0][0].coordinate, "litai/.gitignore")
        self.assertNotIn(".gitignore", [row.coordinate for row, _ in rows])
        self.assertEqual(rows[1][1], current["CHANGELOG.md"])
        self.assertEqual(current[".gitignore"], b"native-output/\n")

    def test_typed_release_and_ledger_references_move_but_product_changelog_does_not(
        self,
    ):
        value = {
            "version_authority": {"path": "literate.project.json"},
            "gate": {
                "argv": ["litai", "test", "samples/hello-component", "--target", "host"]
            },
            "changelog": {"path": "CHANGELOG.md"},
            "contributions": {
                "roadmap_goal_manifest": "docs/roadmap/release-goals.json"
            },
        }
        projected = json.loads(
            self.placement.template_content(
                "literate.release.json", json.dumps(value).encode()
            )
        )
        self.assertEqual(
            projected["version_authority"]["path"], "litai/literate.project.json"
        )
        self.assertEqual(projected["gate"]["argv"][2], "litai/samples/hello-component")
        self.assertEqual(
            projected["contributions"]["roadmap_goal_manifest"],
            "litai/docs/roadmap/release-goals.json",
        )
        self.assertEqual(projected["changelog"], value["changelog"])
        ledger = json.loads(
            self.placement.template_content(
                "docs/roadmap/release-goals.json",
                b'{"roadmap":"docs/roadmap/active-work.md","releases":{}}',
            )
        )
        self.assertEqual(ledger["roadmap"], "litai/docs/roadmap/active-work.md")

    def test_markdown_cross_boundary_links_are_typed_not_arbitrary_command_rewrites(
        self,
    ):
        content = (
            b"[Product history](../CHANGELOG.md#old)\n"
            b"`cargo --manifest-path Cargo.toml`\n"
            b"```\n[example](../CHANGELOG.md)\n```\n"
        )
        projected = self.placement.template_content("docs/README.md", content)
        self.assertIn(b"[Product history](../../CHANGELOG.md#old)", projected)
        self.assertIn(b"`cargo --manifest-path Cargo.toml`", projected)
        self.assertIn(b"[example](../CHANGELOG.md)", projected)

    def test_actual_initializer_passes_original_app_root_and_live_placement(self):
        origin = Mock(side_effect=AssertionError("origin must not be touched"))
        adapter = initializer.FilesystemProjectInitializationAdapter(
            initialization_origin_provider=origin
        )
        original = RuntimeError("original compiler seam")
        with patch.object(
            adapter, "_initialize_project_scaffold", side_effect=original
        ) as compile_project:
            with self.assertRaises(RuntimeError) as caught:
                adapter.initialize(
                    self.root,
                    parent_selection=RepositoryParentSelection.root(),
                    empty=True,
                )
        self.assertIs(caught.exception, original)
        self.assertEqual(compile_project.call_args.args, (self.root,))
        placement = compile_project.call_args.kwargs["_placement"]
        self.assertEqual(placement.context.root, self.root)
        self.assertEqual(placement.context.framework_root, self.root / "litai")
        origin.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_explicit_legacy_fixture_mode_keeps_original_owner_and_errors(self):
        original = RuntimeError("stop original owner before any writer")
        origin = Mock(side_effect=original)
        adapter = initializer.FilesystemProjectInitializationAdapter(
            initialization_origin_provider=origin
        )
        with self.assertRaises(RuntimeError) as caught:
            adapter.initialize(
                self.root,
                empty=True,
                parent_selection=RepositoryParentSelection.root(),
                _layout=scaffold.ScaffoldLayout.LEGACY_ROOT_FIXTURE,
            )
        self.assertIs(caught.exception, original)
        origin.assert_called_once()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_real_pinned_catalog_resources_keep_exact_original_content(self):
        placement = scaffold.project_scaffold_placement(
            self.root,
            (*initializer._TEMPLATE_FILES, *initializer._STARTER_TEMPLATE_FILES),
        )
        resources = {
            **initializer._TEMPLATE_FILES,
            **initializer._STARTER_TEMPLATE_FILES,
        }
        for logical, resource in resources.items():
            if logical.split("/", 1)[0] not in {
                "components",
                "samples",
                "flavors",
                "skills",
                "workflows",
                "routing",
                "mcps",
            }:
                continue
            original = initializer._template_text(resource).encode()
            with self.subTest(logical=logical):
                self.assertEqual(
                    placement.template_content(logical, original), original
                )
