"""One content-pinned Standard profile decoder for preparation and execution.

Callers own selection/axis policy and translate errors for their operation. Reading
a declaration grants neither tool selection nor source/build execution permission.
"""

import json

from literate_ai.contracts import (
    StandardArtifactLayout,
    StandardLanguageBuildStrategy,
    StandardLanguageCommandProfile,
    StandardLanguageRuntimeStrategy,
    parse_standard_command_profile,
)


def is_node_sdk_language_profile(profile):
    return (
        type(profile) is StandardLanguageCommandProfile
        and profile.target == "typescript"
        and profile.build_strategy is StandardLanguageBuildStrategy.TYPESCRIPT_TREE
        and profile.runtime_strategy is StandardLanguageRuntimeStrategy.JAVASCRIPT
        and profile.artifact_layout is StandardArtifactLayout.TREE
    )


def read_standard_profile_contribution(snapshot, flavor, contribution):
    content = snapshot.flavor_content(flavor.identity, contribution.content)
    return parse_standard_command_profile(
        json.loads(content.decode("utf-8")),
        path=(
            f"Flavor {flavor.definition.coordinate.uri} contribution "
            f"{contribution.contribution_id}"
        ),
    )
