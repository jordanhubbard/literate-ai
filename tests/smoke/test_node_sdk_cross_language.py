"""Actual filesystem lock/recipe SDK imports remain static, untrusted DATA."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.generation_preparation import (
    LockedComponentNodePreparationAdapter,
)
from literate_ai.application.generation_preparation import GenerationPreparationError
from literate_ai.contracts.authoring_markdown import (
    parse_authoring_markdown,
    render_authoring_markdown,
)
from literate_ai.contracts.node_sdk import CommonJSModuleDeclaration
from tests.smoke.test_node_sdk_flavors import canonical_snapshot

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_LEGAL_TEXT = (
    "Fixture-only packaging text. No distribution license is granted.\n"
)


def with_provider(root, *, declared=True, build_system=None, corrupt_profile=False):
    def configure(component, flavors):
        source = component / "component.md"
        value, body = parse_authoring_markdown(source.read_bytes(), source=str(source))
        value["requires"] = [
            {
                "requirement_id": "counter-" + kind,
                "capability": "counter.add",
                "version_range": ">=1,<2",
                "dependency_kind": kind,
                "optional": False,
                "constraints": [],
            }
            for kind in ("generation", "build")
        ]
        (component / "legal").mkdir()
        (component / "legal/LICENSE").write_text(FIXTURE_LEGAL_TEXT)
        value["assets"] = [
            {
                "asset_id": "sdk-license",
                "source": "legal/LICENSE",
                "path": "LICENSE",
                "role": "node-sdk-legal",
                "media_type": "text/plain",
            }
        ]
        source.write_bytes(render_authoring_markdown(value, body))
        (component / "specs/spec.md").write_text(
            "# Addition SDK\n\n### Requirement: Exact integer addition\n\n"
            "The SDK SHALL expose add(a,b), returning the sum of its integer inputs "
            "through its declared sealed counter provider.\n\n"
            "#### Scenario: Forward addition\n\n- **WHEN** add(1,2) is called\n"
            "- **THEN** it returns 3\n\n"
            "### Requirement: Fixture-only legal input\n\n"
            "The fixture root LICENSE SHALL contain exactly:\n\n```text\n"
            + FIXTURE_LEGAL_TEXT
            + "```\n\n#### Scenario: Package fixture text\n\n"
            "- **WHEN** this isolated fixture is packed\n"
            "- **THEN** its LICENSE retains those exact bytes\n"
        )
        (component / "interfaces/library.md").write_text(
            "# Addition SDK interface\n\nThe public add(a,b) function returns "
            "the exact sum of two integers through its sealed provider.\n"
        )
        provider = component / "counter"
        (provider / "interfaces").mkdir(parents=True)
        (provider / "specs").mkdir()
        (provider / "acceptance").mkdir()
        child = dict(value)
        child["authoring_inputs"] = [
            *value["authoring_inputs"],
            {
                "kind": "specification-to-source-skill",
                "uri": (
                    "skills/specification-to-source/"
                    "portable-application-implementation/SKILL.md"
                ),
            },
        ]
        child.update(
            display_name="Sealed counter provider",
            assets=[],
            requires=[],
            provides=[
                {
                    "name": "counter.add",
                    "version": "1.0.0",
                    "interface": {"uri": "interfaces/public.md"},
                }
            ],
            flavor_slots=[s for s in value["flavor_slots"] if s["axis"] != "packaging"],
            library_imports=[
                {
                    "language": "javascript",
                    "package": "counter",
                    "capability": "counter.add",
                    "module": "counter/api",
                    "symbols": ["add"],
                    **(
                        {
                            "node_module": CommonJSModuleDeclaration(
                                "counter/api",
                                "source/counter/api.js",
                                "source/counter/api.d.ts",
                            ).to_dict()
                        }
                        if declared
                        else {}
                    ),
                }
            ],
        )
        (provider / "component.md").write_bytes(
            render_authoring_markdown(
                child,
                "# Counter\nPrivate provider detail stays outside consumer context.",
            )
        )
        (provider / "specs/spec.md").write_text(
            "# Counter\n\n### Requirement: Private implementation\n\n"
            "The provider SHALL retain PRIVATE_PROVIDER_IMPLEMENTATION.\n\n"
            "#### Scenario: Private behavior\n\n- **WHEN** executing privately\n"
            "- **THEN** it returns an exact sum\n"
        )
        (provider / "interfaces/public.md").write_text(
            "# Addition\n\nThe add function returns the exact sum "
            "of its two integers.\n"
        )
        (provider / "acceptance/execution.json").write_text(
            '{"private":"PRIVATE_PROVIDER_ORACLE"}\n'
        )
        shutil.copytree(ROOT / "flavors/lang-javascript", flavors / "lang-javascript")
        shutil.copytree(
            ROOT
            / "skills/specification-to-source/javascript-portable-json-application",
            root
            / "skills/specification-to-source/javascript-portable-json-application",
        )
        if corrupt_profile:
            path = flavors / "package-node-sdk/standard-command-profile.json"
            data = json.loads(path.read_text())
            data["pack_policy"] = "online"
            path.write_text(json.dumps(data))

    return canonical_snapshot(
        root,
        build_system=build_system,
        before_lock=configure,
        additional_flavor_selectors=(
            "component://examples/counter::-flavor://literate-ai/lang-typescript-library",
            "component://examples/counter::+flavor://literate-ai/lang-javascript",
        ),
    )


class NodeSDKCrossLanguageTests(unittest.TestCase):
    def test_invalid_pinned_sdk_profile_is_refused(self):
        with tempfile.TemporaryDirectory() as raw:
            _, snapshot, execution = with_provider(Path(raw), corrupt_profile=True)
            plan = next(
                p
                for p in execution.generation_plans
                if p.component_revision == execution.root_revision
            )
            with self.assertRaises(GenerationPreparationError) as denied:
                LockedComponentNodePreparationAdapter().project(snapshot, plan)
            self.assertEqual(denied.exception.code, "generate.node_sdk_profile_invalid")

    def test_real_canonical_recipe_preserves_exact_public_provider_surface(self):
        with tempfile.TemporaryDirectory() as raw:
            _, snapshot, execution = with_provider(Path(raw))
            plan = next(
                p
                for p in execution.generation_plans
                if p.component_revision == execution.root_revision
            )
            projection = LockedComponentNodePreparationAdapter().project(snapshot, plan)
            recipe = projection.recipe
            self.assertEqual(len(recipe.library_dependencies), 1)
            dependency = recipe.library_dependencies[0]
            self.assertEqual(dependency.import_surface.language, "javascript")
            self.assertEqual(
                dependency.import_surface.declarations[0].runtime,
                "source/counter/api.js",
            )
            self.assertEqual(
                dependency.interface_identity,
                plan.direct_generation_edges[0].public_interface_identity,
            )
            self.assertEqual(recipe.node_sdk_providers, ())
            self.assertNotIn("PRIVATE_PROVIDER_IMPLEMENTATION", repr(recipe))
            self.assertNotIn("PRIVATE_PROVIDER_ORACLE", repr(recipe))

    def test_undeclared_javascript_or_competing_build_remains_refused(self):
        for options in ({"declared": False}, {"build_system": "make"}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as raw:
                _, snapshot, execution = with_provider(Path(raw), **options)
                plan = next(
                    p
                    for p in execution.generation_plans
                    if p.component_revision == execution.root_revision
                )
                with self.assertRaises(GenerationPreparationError) as denied:
                    LockedComponentNodePreparationAdapter().project(snapshot, plan)
                self.assertEqual(
                    denied.exception.code, "generate.library_cross_language_unsupported"
                )
