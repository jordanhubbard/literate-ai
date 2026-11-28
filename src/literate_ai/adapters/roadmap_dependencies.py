"""Read prospective roadmap authority before any supported write commits it."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from literate_ai.application.roadmap_dependencies import (
    RoadmapDependencyError,
    validate_roadmap_dependencies,
)
from literate_ai.application.roadmap_paths import RoadmapPaths

_UNSELECTED = object()


def require_project_roadmap_acyclic(
    root: Path,
    proposed: Mapping[str, bytes | None] | None = None,
    *,
    additional_queue: str | None = None,
    _observation=None,
    framework_directory: str | None | object = _UNSELECTED,
) -> None:
    """Validate an in-memory overlay, without creating or modifying any file."""
    from literate_ai.projects import ProjectConfigurationStore

    proposed = proposed or {}
    if framework_directory is _UNSELECTED:
        context = ProjectConfigurationStore.context(root)
        relative = context.framework_root.relative_to(context.root).as_posix()
        framework_directory = None if relative == "." else relative
    namespace = RoadmapPaths.for_framework(framework_directory)
    policy_coordinate = namespace.release_policy
    conventional_queue = namespace.queue

    def read(relative: str) -> bytes | None:
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise RoadmapDependencyError(
                "roadmap.dependency_path_invalid", f"unsafe roadmap path: {relative}"
            )
        if relative in proposed:
            return proposed[relative]
        if _observation is not None:
            return _observation.read(relative, optional=True)
        path = root / relative
        return path.read_bytes() if path.exists() else None

    try:
        policy_bytes = read(policy_coordinate)
        manifest_path = None
        if policy_bytes is not None:
            policy = (
                json.loads(policy_bytes)
                if _observation is None
                else _observation.json_value(policy_bytes, policy_coordinate)
            )
            manifest_path = policy.get("contributions", {}).get("roadmap_goal_manifest")
        manifest = None
        queue = conventional_queue
        if manifest_path is not None:
            raw = read(manifest_path)
            if raw is None:
                raise ValueError(f"missing release goal manifest: {manifest_path}")
            manifest = (
                json.loads(raw)
                if _observation is None
                else _observation.json_value(raw, manifest_path)
            )
            queue = manifest["roadmap"]
        raw_queue = read(queue)
        if raw_queue is None:
            if manifest is not None:
                raise ValueError(f"missing roadmap: {queue}")
        else:
            validate_roadmap_dependencies(raw_queue.decode("utf-8"), manifest)
        # The work CLI's conventional queue can coexist with a custom release queue.
        if queue != conventional_queue:
            conventional = read(conventional_queue)
            if conventional is not None:
                validate_roadmap_dependencies(conventional.decode("utf-8"))
        if additional_queue is not None and additional_queue not in {
            queue,
            conventional_queue,
        }:
            additional = read(additional_queue)
            if additional is not None:
                validate_roadmap_dependencies(additional.decode("utf-8"))
    except RoadmapDependencyError:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise RoadmapDependencyError(
            "roadmap.dependency_authority_invalid", f"cannot validate roadmap: {exc}"
        ) from exc
