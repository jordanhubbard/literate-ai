"""Canonical SDK authority selection; no generated lifecycle qualification."""

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.generation_preparation import (
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.standard_project import (
    StandardCommandProjectionError,
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts.authoring_markdown import (
    parse_authoring_markdown,
    render_authoring_markdown,
)
from literate_ai.contracts.node_sdk import NodeSDKExportDeclaration
from tests.smoke.test_standard_command_projection import _locked_snapshot, _observation

ROOT = Path(__file__).resolve().parents[2]


def canonical_snapshot(root, *, build_system=None, package=True, application=False):
    def configure(component, _flavors):
        path = component / "component.md"
        value, body = parse_authoring_markdown(path.read_bytes(), source=str(path))
        value["authoring_inputs"] = [
            {
                "kind": "specification-to-source-skill",
                "uri": (
                    "skills/specification-to-source/"
                    "portable-specification-planning/SKILL.md"
                ),
            }
        ]
        value["library_imports"] = (
            []
            if application
            else [
                {
                    "language": "typescript",
                    "package": "sample",
                    "capability": "sample.portable-app",
                    "module": "sample",
                    "symbols": ["add"],
                    "node_sdk_exports": [
                        NodeSDKExportDeclaration("sample", "index").to_dict()
                    ],
                }
            ]
        )
        path.write_bytes(render_authoring_markdown(value, body))

    return _locked_snapshot(
        root,
        language="typescript-library",
        no_entrypoint=not application,
        package_node_sdk=package,
        generation_ready=True,
        build_system=build_system,
        before_lock=configure,
    )


class NodeSDKFlavorAuthorityTests(unittest.TestCase):
    def test_application_or_competing_build_is_denied_before_tool_discovery(self):
        def forbidden_discovery(*_args):
            raise AssertionError("unsupported profile cannot discover tools")

        for options in ({"application": True}, {"build_system": "make"}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as raw:
                _, snapshot, execution = canonical_snapshot(Path(raw), **options)
                with self.assertRaises(StandardCommandProjectionError) as denied:
                    project_locked_standard_toolchain_closure(
                        snapshot,
                        execution,
                        host_platform="macos",
                        toolchain_discoverer=forbidden_discovery,
                    )
                self.assertEqual(
                    denied.exception.code,
                    "standard_command.node_sdk_profile_unsupported",
                )

    def test_complete_canonical_authority_matches_shipped_template(self):
        relatives = (
            Path("flavors/lang-typescript-library"),
            Path("flavors/package-node-sdk"),
            Path("skills/specification-to-source/typescript-node-sdk"),
        )
        for relative in relatives:
            files = tuple(
                sorted(
                    p.relative_to(ROOT)
                    for p in (ROOT / relative).rglob("*")
                    if p.is_file()
                )
            )
            template = ROOT / "src/literate_ai/project_template"
            shipped = tuple(
                sorted(
                    p.relative_to(template)
                    for p in (template / relative).rglob("*")
                    if p.is_file()
                )
            )
            self.assertEqual(files, shipped)
            for path in files:
                with self.subTest(path=path):
                    self.assertEqual(
                        (ROOT / path).read_bytes(), (template / path).read_bytes()
                    )
        for name in ("lang-typescript-library", "package-node-sdk"):
            bom = json.loads(
                (ROOT / "flavors" / name / "host-toolchain.cdx.json").read_bytes()
            )
            self.assertEqual(bom["metadata"]["component"]["name"], name)

    @unittest.skipUnless(
        os.environ.get("LITERATE_TYPESCRIPT_SDK")
        and shutil.which("node")
        and os.name == "posix",
        "requires explicitly selected compiler and Node/npm",
    )
    def test_actual_canonical_lock_recipe_profile_and_runtime_target(self):
        with tempfile.TemporaryDirectory() as raw:
            _, snapshot, execution = canonical_snapshot(Path(raw))
            projection = LockedComponentNodePreparationAdapter().project(
                snapshot, execution.generation_plans[0]
            )
            recipe = projection.recipe
            self.assertTrue(recipe.library_import_surface.node_sdk_exports)
            selected = [
                s for s in recipe.resolved_skills if s.skill_id == "typescript-node-sdk"
            ]
            self.assertEqual(len(selected), 1)
            content = (
                ROOT / "skills/specification-to-source/typescript-node-sdk/SKILL.md"
            ).read_bytes()
            self.assertEqual(
                selected[0].content_identity.digest, hashlib.sha256(content).hexdigest()
            )
            self.assertEqual(str(selected[0].manifest.version), "1.0.0")
            self.assertIsNone(recipe.required_entrypoint)
            language = next(f for f in recipe.flavors if f.value == "typescript")
            self.assertIn("lang-typescript-library", language.coordinate_uri)
            self.assertEqual(
                {f.value for f in recipe.flavors if f.axis == "packaging"},
                {"node-sdk"},
            )
            environment = dict(os.environ)
            environment["LITAI_TYPESCRIPT_SDK"] = os.environ["LITERATE_TYPESCRIPT_SDK"]
            closure = project_locked_standard_toolchain_closure(
                snapshot,
                execution,
                environment=environment,
                host_platform="macos",
                dependency_observer=_observation,
            )
            target = closure.node_sdk_targets[0]
            target.require_contract(closure.contracts[0])
            self.assertEqual(target.profile.legal_files, ("LICENSE",))
            self.assertEqual(target.profile.source_root, "src")
            self.assertEqual(target.typescript.version_constraint, ">=5.8,<7")
            self.assertEqual(target.npm.version_constraint, ">=9,<13")
