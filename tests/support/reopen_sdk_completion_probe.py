"""Fresh-process probe for reopening real SDK evidence with acquisition disabled."""

import json
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.native_sdk_completion_binding import read_completion_binding
from literate_ai.adapters.native_sdk_recipes import select_native_sdk_recipes
from literate_ai.contracts import ProjectSourceIntelligencePolicy
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.storage import FileSystemCAS


def main():
    case = json.load(sys.stdin)
    snapshot = FilesystemLockedGenerationAuthorityReader(
        replay_repository_sources=True
    ).read(
        Path(case["component"]),
        target_name="host",
        flavor_selectors=tuple(case["selectors"]),
        flavor_roots=(Path(case["flavors"]),),
    )
    (selection,) = (
        recipe
        for node in snapshot.authority.lock.nodes
        if node.revision.repository_sources
        for recipe in select_native_sdk_recipes(snapshot, node.revision.identity)
    )
    store = FileSystemCAS(Path(case["cas"]), create=False)
    tools = tuple(
        LocalComponentToolBinding(case["tools"][name]).toolchain_identity
        for name in selection.recipe.tools
    )
    with ExitStack() as traps:
        for name in ("put_manifest", "put_bytes", "put_file"):
            traps.enter_context(
                patch.object(FileSystemCAS, name, side_effect=AssertionError(name))
            )
        for name in ("subprocess.Popen", "socket.socket.connect"):
            traps.enter_context(patch(name, side_effect=AssertionError(name)))
        result, _ = read_completion_binding(
            store,
            case["row"],
            selection=selection,
            toolchains=tools,
            intelligence=ProjectSourceIntelligencePolicy.from_dict(
                case["intelligence"]
            ),
            limits=RetainedProjectLimits(10000, 128 * 1024**2, 256 * 1024**2),
            max_manifest_bytes=16 * 1024**2,
            step=lambda: None,
        )
    print(result.identity.uri)


if __name__ == "__main__":
    main()
