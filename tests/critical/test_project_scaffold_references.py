"""Finite original-template references and stdlib bootstrap source controls."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_initialization as initializer
from literate_ai.adapters.project_scaffold_placement import project_scaffold_placement
from literate_ai.adapters.project_updates import _upstream_template
from literate_ai.project_template import scripts
from literate_ai.projects import (
    configured_catalog_path,
    serialize_project_configuration,
)
from tests.support.fixtures_test_project_configuration import _definition


class ProjectScaffoldReferencesTests(unittest.TestCase):
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

    def test_real_central_skill_literals_use_application_cwd_and_links_are_relative(
        self,
    ):
        original = initializer._template_text(
            initializer._TEMPLATE_FILES["SKILL.md"]
        ).encode()
        rendered = self.placement.template_content("SKILL.md", original)
        self.assertIn(b"`litai/skills/agent/SKILL.md`", rendered)
        self.assertIn(b"`litai/skills/agent/release-project/SKILL.md`", rendered)
        self.assertIn(b"](docs/user/bootstrap.md)", rendered)
        self.assertNotIn(b"](litai/docs/user/bootstrap.md)", rendered)
        self.assertIn(b"`PROJECT.md`", rendered)

    def test_known_commands_paths_map_without_rewriting_unknown_argv_or_relative_inputs(
        self,
    ):
        content = (
            b"python3 scripts/bootstrap_litai.py --wheel path/to/product.whl\n"
            b"py -3 scripts\\bootstrap_litai.py --litai .\\local\\litai.exe\n"
            b"`litai test samples/hello-component --target host`\n"
            b'uri: "../../skills/agent/package-artifacts/SKILL.md"\n'
            b"cargo --manifest-path Cargo.toml\ncustom scripts/product.py\n"
        )
        rendered = self.placement.template_content("docs/README.md", content)
        self.assertIn(
            b"python3 litai/scripts/bootstrap_litai.py --wheel path/to/product.whl",
            rendered,
        )
        self.assertIn(
            b"py -3 litai\\scripts\\bootstrap_litai.py --litai .\\local\\litai.exe",
            rendered,
        )
        self.assertIn(
            b"litai test litai/samples/hello-component --target host", rendered
        )
        self.assertIn(b'uri: "../../skills/agent/package-artifacts/SKILL.md"', rendered)
        self.assertIn(
            b"cargo --manifest-path Cargo.toml\ncustom scripts/product.py", rendered
        )

    def test_original_catalog_bytes_use_declared_contained_input_locations(self):
        logical = "samples/hello-component/component.md"
        original = initializer._template_text(
            initializer._STARTER_TEMPLATE_FILES[logical]
        ).encode()
        self.assertEqual(self.placement.template_content(logical, original), original)
        definition = replace(
            _definition(),
            framework_directory="litai",
            agent_skill="litai/SKILL.md",
            component_roots=("litai/components", "litai/samples"),
            skill_roots=("litai/skills",),
            workflow_roots=("litai/workflows",),
            routing_roots=("litai/routing",),
            flavor_roots=("litai/flavors",),
        )
        (self.root / "litai").mkdir()
        (self.root / "litai/literate.project.json").write_bytes(
            serialize_project_configuration(definition)
        )
        for logical, kind in (
            (
                "skills/specification-to-source/portable-application-implementation/SKILL.md",
                "specification-to-source-skill",
            ),
            ("workflows/production/staging/dev/workflow.md", "workflow"),
            ("routing/production/staging/dev/routing.json", "routing-policy"),
        ):
            target = self.root / "litai" / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = initializer._template_text(
                initializer._TEMPLATE_FILES[logical]
            ).encode()
            target.write_bytes(payload)
            selected = configured_catalog_path(self.root, self.root, logical, kind=kind)
            self.assertEqual(selected, target)
            self.assertEqual(selected.read_bytes(), payload)

    def test_update_renderer_uses_explicit_placement_not_optional_baseline_shape(self):
        baseline = {"litai/samples/hello-component/component.md"}
        projected = _upstream_template(baseline, placement=self.placement)
        self.assertIn("litai/SKILL.md", projected)
        self.assertIn("litai/samples/hello-component/component.md", projected)
        self.assertNotIn("SKILL.md", projected)
        legacy = _upstream_template(baseline)
        self.assertIn("SKILL.md", legacy)
        self.assertNotIn("litai/SKILL.md", legacy)

    def test_portable_alias_preflight_preserves_original_without_child_probe(self):
        for alias in ("LitAI", "LITERATE.PROJECT.JSON"):
            entry = self.root / alias
            entry.write_bytes(b"original application bytes")
            with patch.object(
                Path, "resolve", side_effect=AssertionError("no resolve")
            ):
                with self.assertRaisesRegex(ValueError, "portable alias"):
                    self.placement.preflight_new_destination()
            self.assertEqual(entry.read_bytes(), b"original application bytes")
            entry.unlink()

    @unittest.skipUnless(os.name == "posix", "modeled POSIX alias refusal")
    def test_alias_symlink_target_is_never_inspected(self):
        (self.root / "LitAI").symlink_to(
            self.root / "unopened-target", target_is_directory=True
        )
        with patch.object(
            Path, "resolve", side_effect=AssertionError("no target resolve")
        ):
            with self.assertRaisesRegex(ValueError, "portable alias"):
                self.placement.preflight_new_destination()

    @staticmethod
    def _bootstrap():
        path = Path(next(iter(scripts.__path__))) / "bootstrap_litai.py"
        spec = importlib.util.spec_from_file_location("_fixture_bootstrap", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _manifest(self, path, framework=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        value = {
            "lifecycle_driver": {
                "binding": "standard",
                "framework_distribution_identity": {
                    "algorithm": "sha256",
                    "digest": "a" * 64,
                },
            }
        }
        if framework is not None:
            value["framework_directory"] = framework
        path.write_text(json.dumps(value))

    def test_bootstrap_frame_and_app_select_same_original_app(
        self,
    ):
        manifest = self.root / "litai/literate.project.json"
        self._manifest(manifest, "litai")
        bootstrap = self._bootstrap()
        output = json.dumps(
            {
                "ok": True,
                "result": {
                    "ok": True,
                    "project": {
                        "derived_identities": {"driver_identity_matches": True}
                    },
                },
            }
        )
        for selected in (self.root, self.root / "litai"):
            with patch.object(
                bootstrap,
                "_run_version_probe",
                return_value=subprocess.CompletedProcess([], 0, output, ""),
            ) as probe:
                self.assertTrue(bootstrap.check(selected, "original-litai")["ok"])
                self.assertEqual(probe.call_args.kwargs["cwd"], self.root)
                command = probe.call_args.args[0]
                self.assertEqual(
                    command[command.index("--project") + 1], str(self.root)
                )

    def test_bootstrap_dual_authority_refuses_before_any_process(self):
        self._manifest(self.root / "litai/literate.project.json", "litai")
        self._manifest(self.root / "literate.project.json")
        bootstrap = self._bootstrap()
        with patch.object(bootstrap, "_run_version_probe") as probe:
            self.assertEqual(
                bootstrap.check(self.root, "litai")["state"], "project-invalid"
            )
            probe.assert_not_called()

    def test_bootstrap_legacy_root_keeps_original_root_and_pin(self):
        self._manifest(self.root / "literate.project.json")
        bootstrap = self._bootstrap()
        app, manifest, definition = bootstrap._declared_project(self.root)
        self.assertEqual(app, self.root)
        self.assertEqual(manifest, self.root / "literate.project.json")
        self.assertEqual(
            definition["lifecycle_driver"]["framework_distribution_identity"]["digest"],
            "a" * 64,
        )
