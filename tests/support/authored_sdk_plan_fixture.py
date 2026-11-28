"""SDK-backed library and private oracle for the authored CLI planning fixture."""

import hashlib
import json

from literate_ai.adapters.component_acceptance import load_versioned_library_acceptance
from literate_ai.application.library_artifacts import project_library_import_surface
from literate_ai.contracts.authored_qualification_profiles import (
    AuthoredQualificationOracleSelection,
    AuthoredQualificationProfile,
)
from literate_ai.contracts.authoring_markdown import (
    parse_authoring_markdown,
    render_authoring_markdown,
)


def configure_library(recipe):
    path = recipe.component_document
    definition, body = parse_authoring_markdown(path.read_bytes(), source=str(path))
    definition["kind"] = "library"
    definition["entrypoints"] = []
    definition["provides"] = [
        {
            "name": "greeting.value",
            "version": "1.0.0",
            "interface": {"uri": "interface.md", "pin": None},
        }
    ]
    definition["authoring_inputs"][0]["uri"] = (
        "skills/specification-to-source/portable-application-implementation/SKILL.md"
    )
    (recipe.component / "interface.md").write_text(
        "# Greeting\n\nThe library SHALL expose greeting.value.\n"
    )
    path.write_bytes(render_authoring_markdown(definition, body))


def write_private_oracle(root, snapshot):
    (node,) = snapshot.authority.lock.nodes
    coordinate = node.revision.coordinate
    (interface,) = node.interface_bindings
    surface = project_library_import_surface(
        coordinate.name,
        "python",
        ((interface.capability, interface.interface_identity),),
        declarations=node.revision.definition.library_imports,
    )
    directory = root / "litai/verification/acceptance" / coordinate.namespace
    directory.mkdir(parents=True)
    harness = b"raise AssertionError('planning executed private harness')\n"
    (directory / "harness.py").write_bytes(harness)
    path = directory / (coordinate.name + ".json")
    path.write_text(
        json.dumps(
            {
                "schema": "literate-ai/library-acceptance-oracle@1",
                "component": coordinate.name,
                "specification_set_identity": (
                    node.revision.specification_set_identity.uri
                ),
                "public_interface_identities": sorted(
                    item.identity.uri for item in node.revision.public_interfaces
                ),
                "import_surface_identity": surface.identity.uri,
                "language": "python",
                "harness": "harness.py",
                "harness_identity": "sha256:" + hashlib.sha256(harness).hexdigest(),
                "cases": [
                    {
                        "case_id": "value",
                        "capability": interface.capability,
                        "arguments": [1],
                        "expected_result": "private-sdk-plan-answer",
                    }
                ],
            }
        )
    )
    oracle = load_versioned_library_acceptance(path, coordinate.name)
    profile = AuthoredQualificationProfile(
        "authored-graph@1",
        (AuthoredQualificationOracleSelection(coordinate, oracle.identity),),
    )
    (root / "litai/qualification.json").write_text(json.dumps(profile.to_dict()))
