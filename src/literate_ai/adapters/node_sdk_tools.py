"""One environment policy for SDK compiler and packer tool processes."""

from collections.abc import Mapping

from literate_ai.adapters.builders.javascript import controlled_node_environment

SDK_TOOL_ENVIRONMENT_POLICY = "literate-ai/node-sdk-tool-environment@1"


def node_sdk_tool_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Keep launch necessities while denying ambient Node/npm tool controls.

    NODE_V8_COVERAGE, warning redirection and future NODE_* switches must not
    write outside object custody. These are compiler/packer tools, not application
    execution; no application NODE_ENV behavior is inferred or changed here.
    """
    controlled = controlled_node_environment(dict(environment))
    result = {
        name: value
        for name, value in controlled.items()
        if not name.upper().startswith(("NODE_", "NPM_"))
    }
    result["NODE_DISABLE_COMPILE_CACHE"] = "1"
    return result
