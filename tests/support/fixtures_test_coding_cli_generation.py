"""Shared test fixtures extracted from test_coding_cli_generation."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import sysconfig
from pathlib import Path

import literate_ai.adapters.models.coding_cli as coding_cli_adapter
from literate_ai.adapters.dependencies import build_cyclonedx_bom
from literate_ai.adapters.models import (
    GenerationRecipe,
    RecipeDocument,
    RecipeFlavor,
    RecipeSkill,
)
from literate_ai.contracts import (
    CYCLONEDX_SOURCE_SBOM_PATH,
    ContentIdentity,
    ContentReference,
    CycloneDxLifecycle,
    CycloneDxManagedComponent,
    CycloneDxManagedGraph,
    ManagedComponentKind,
    SkillReference,
    canonical_identity,
    component_bom_ref,
)
from literate_ai.generated_tests import (
    GENERATED_TEST_SUITE_PATH,
    GENERATED_TEST_SUITE_SCHEMA,
)

TEST_COMPONENT_LOCK_IDENTITY = ContentIdentity.parse_uri("sha256:" + "c" * 64)


def configure_python_cli_alias(root: Path, name: str, environment: dict[str, str]):
    """Give a pinned Python transport its own isolated native CLI startup path."""
    if os.name != "posix":
        return
    tools = root / "python-cli-tools"
    tools.mkdir(exist_ok=True)
    (tools / name).symlink_to(Path(sys.executable).resolve(strict=True))
    # Relocatable Python builds cannot discover their stdlib from an arbitrary
    # argv[0]. These fixture-owned paths keep the real executable pin and the
    # provider's logical argv[0], without changing the installation or PYTHONHOME.
    paths = (sysconfig.get_path("stdlib"), sysconfig.get_config_var("DESTSHARED"))
    (tools / f"{name}._pth").write_text(
        "".join(f"{Path(path).resolve(strict=True)}\n" for path in paths),
        encoding="utf-8",
    )
    environment["PATH"] = str(tools) + os.pathsep + environment.get("PATH", "")


def generation_skill(
    skill_id: str = "specification-planning",
    *,
    stages: tuple[str, ...] = ("plan",),
    dependencies: tuple[RecipeSkill | SkillReference, ...] = (),
    instructions: str = "Plan the exact specified behavior.",
) -> RecipeSkill:
    content = json.dumps(
        {
            "schema": "urn:literate-ai:schema:v1:specification-to-source-skill",
            "skill_id": skill_id,
            "version": "1.0.0",
            "title": skill_id.replace("-", " ").title(),
            "stages": list(stages),
            "dependencies": [
                (item.ref if isinstance(item, RecipeSkill) else item).to_dict()
                for item in dependencies
            ],
            "instructions": instructions,
            "limitations": ["Do not invent behavior."],
            "trust": "fixture-reviewed",
        },
        sort_keys=True,
    ).encode()
    identity = f"sha256:{hashlib.sha256(content).hexdigest()}"
    reference = ContentReference(
        "specification-to-source-skill",
        f"skills/{skill_id}.json",
        ContentIdentity.parse_uri(identity),
    )
    return RecipeSkill.from_reference(reference, content, source="test fixture")


def flavor(value: str, *, models=(), skills=()) -> RecipeFlavor:
    revision = canonical_identity({"fixture_flavor": value}).uri
    specification_set = canonical_identity({"fixture_flavor_spec": value}).uri
    return RecipeFlavor(
        f"implementation-{value}",
        "implementation.language-ecosystem",
        value,
        (RecipeDocument.create(f"{value}/spec.md", f"Generate {value}.\n"),),
        tuple(models),
        skills=tuple(skills),
        revision_identity=revision,
        specification_set_identity=specification_set,
    )


def recipe(selected: RecipeFlavor) -> GenerationRecipe:
    suffix = "py" if selected.value == "python" else "cpp"
    root_identity = ContentIdentity.parse_uri("sha256:" + "a" * 64)
    root_ref = component_bom_ref(root_identity)
    managed_graph = CycloneDxManagedGraph(
        root_ref,
        (
            CycloneDxManagedComponent(
                root_ref,
                ManagedComponentKind.ROOT,
                root_identity,
                "urn:literate-ai:component:test/hello",
                "1.0.0",
                (),
            ),
        ),
        (),
        ContentIdentity.parse_uri("sha256:" + "c" * 64),
    )
    return GenerationRecipe(
        "hello-recipe",
        "hello",
        (RecipeDocument.create("openspec/spec.md", "Say hello.\n"),),
        TEST_COMPONENT_LOCK_IDENTITY,
        (selected,),
        f"source/main.{suffix}",
        (("codex", "base-codex-model"),),
        (generation_skill(),),
        managed_sbom_graph=managed_graph,
    )


def generated_test_suite(
    value: GenerationRecipe, *, first_arguments: list[object] | None = None
) -> str:
    arguments = first_arguments or [{"value": 7}]
    return json.dumps(
        {
            "schema": GENERATED_TEST_SUITE_SCHEMA,
            "recipe_identity": value.identity,
            "generation_mode": "major-rebuild",
            "cases": [
                {
                    "case_id": "ordinary-example",
                    "category": "example",
                    "specification_refs": ["openspec/spec.md"],
                    "arguments": arguments,
                    "expected_result": {"value": 14},
                },
                {
                    "case_id": "empty-boundary",
                    "category": "boundary",
                    "specification_refs": ["openspec/spec.md"],
                    "arguments": [],
                    "expected_result": {"value": 0},
                },
                {
                    "case_id": "repeat-invariant",
                    "category": "invariant",
                    "specification_refs": ["openspec/spec.md"],
                    "arguments": [{"value": 19}],
                    "expected_result": {"value": 38},
                },
            ],
        },
        sort_keys=True,
    )


def write_generated_test_suite(workspace: Path, value: GenerationRecipe) -> None:
    path = workspace / GENERATED_TEST_SUITE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generated_test_suite(value), encoding="utf-8")
    assert value.managed_sbom_graph is not None
    authority_components, authority_edges = coding_cli_adapter._recipe_authority_sbom(
        value
    )
    sbom, _binding = build_cyclonedx_bom(
        lifecycle=CycloneDxLifecycle.SOURCE,
        managed_graph=value.managed_sbom_graph,
        additional_components=authority_components,
        additional_edges=authority_edges,
    )
    sbom_path = workspace / CYCLONEDX_SOURCE_SBOM_PATH
    sbom_path.parent.mkdir(parents=True, exist_ok=True)
    sbom_path.write_bytes(sbom)
