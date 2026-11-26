"""Roadmap work-item CLI adapter."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    require_safe_directory,
    stat_is_link_or_reparse,
)
from literate_ai.adapters.native_profile_git import (
    NativeProfileGitBoundaryError,
    require_native_profile_git_boundary,
)
from literate_ai.adapters.roadmap_dependencies import require_project_roadmap_acyclic
from literate_ai.application.roadmap_dependencies import RoadmapDependencyError
from literate_ai.application.roadmap_work import (
    RoadmapWorkError,
    RoadmapWorkRecord,
    close_work,
    record_work,
)
from literate_ai.projects import ProjectConfigurationStore, ProjectContext, ProjectError

from .errors import CliFailure

_WORK_QUEUE = "docs/roadmap/active-work.md"


def _require_queue_scope(context: ProjectContext, path: Path) -> None:
    if ProjectConfigurationStore.context(context.root) != context:
        raise RoadmapWorkError("roadmap_work.queue_changed", "project layout changed")
    try:
        require_safe_directory(path.parent, allow_missing=True)
    except (OSError, UnsafeFilesystemPathError) as exc:
        raise RoadmapWorkError(
            "roadmap_work.queue_unsafe", "contained work queue has unsafe ancestors"
        ) from exc
    try:
        require_native_profile_git_boundary(context.root, (path,))
    except NativeProfileGitBoundaryError as exc:
        raise RoadmapWorkError("roadmap_work.queue_nested_git", str(exc)) from exc


def _queue_file_stamp(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _read_contained_queue(context: ProjectContext, path: Path):
    _require_queue_scope(context, path)
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise RoadmapWorkError(
            "roadmap_work.queue_missing", "no existing contained work queue was found"
        ) from exc
    if (
        stat_is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
    ):
        raise RoadmapWorkError(
            "roadmap_work.queue_unsafe",
            "contained work queue must be a direct regular file",
        )
    parent = path.parent.lstat()
    stamp = _queue_file_stamp(before)
    reader = ProjectConfigurationStore(
        context.root, maximum_bytes=max(before.st_size, 1)
    )
    try:
        content = reader._read_manifest(path)
    except ProjectError as exc:
        raise RoadmapWorkError(
            "roadmap_work.queue_changed", "work queue changed while opening or reading"
        ) from exc
    _require_queue_scope(context, path)
    if (
        len(content) != before.st_size
        or _queue_file_stamp(path.lstat()) != stamp
        or not os.path.samestat(path.parent.lstat(), parent)
    ):
        raise RoadmapWorkError(
            "roadmap_work.queue_changed", "work queue changed while reading"
        )
    return content, stamp, (parent.st_dev, parent.st_ino, parent.st_mode)


def _write_contained_queue(context: ProjectContext, path: Path, observed, updated: str):
    def require_current():
        if _read_contained_queue(context, path) != observed:
            raise RoadmapWorkError(
                "roadmap_work.queue_changed", "work queue changed before writing"
            )

    require_current()
    payload = updated.encode("utf-8")
    descriptor, name = tempfile.mkstemp(
        dir=path.parent, prefix=".active-work-", suffix=".tmp"
    )
    staging = Path(name)
    stage = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            if os.name != "nt":
                os.fchmod(stream.fileno(), stat.S_IMODE(observed[1][2]))
        staged_content, stage_stamp, parent = _read_contained_queue(context, staging)
        if (
            staged_content != payload
            or stage_stamp[:2] != (stage.st_dev, stage.st_ino)
            or parent != observed[2]
        ):
            raise RoadmapWorkError(
                "roadmap_work.queue_changed", "work queue staging changed"
            )
        require_current()
        current_stage = staging.lstat()
        if (
            stat_is_link_or_reparse(current_stage)
            or _queue_file_stamp(current_stage) != stage_stamp
        ):
            raise RoadmapWorkError(
                "roadmap_work.queue_changed", "work queue staging changed"
            )
        os.replace(staging, path)
    except BaseException:
        try:
            _require_queue_scope(context, path)
            if os.path.samestat(stage, staging.lstat()):
                staging.unlink()
        except (OSError, ProjectError, RoadmapWorkError):
            pass
        raise


def work_from_args(args: Any) -> tuple[dict[str, object], int]:
    project = ProjectConfigurationStore.discover(Path(args.project))
    if project is None:
        raise CliFailure("project.not_found", "no Literate AI project was found")
    context = ProjectContext(
        project.root, project.manifest_path.parent, project.directory_binding
    )
    path = context.framework_path(_WORK_QUEUE)
    contained = context.framework_root != context.root
    try:
        if contained:
            observed = _read_contained_queue(context, path)
            content = observed[0].decode("utf-8")
        else:
            content = path.read_text(encoding="utf-8")
        if args.work_command == "record":
            updated = record_work(
                content,
                RoadmapWorkRecord(
                    args.work_id,
                    args.title,
                    args.priority,
                    args.owner,
                    args.direction,
                    args.conclusion,
                    tuple(args.depends_on),
                    tuple(args.implementation),
                    tuple(args.evidence),
                    tuple(getattr(args, "completion_prerequisite", ())),
                ),
            )
        else:
            updated = close_work(content, args.work_id)
        if not contained:
            require_project_roadmap_acyclic(
                project.root, {_WORK_QUEUE: updated.encode("utf-8")}
            )
        if updated != content:
            if contained:
                _write_contained_queue(context, path, observed, updated)
            else:
                if ProjectConfigurationStore.context(context.root) != context:
                    raise RoadmapWorkError(
                        "roadmap_work.queue_changed",
                        "project layout changed before writing",
                    )
                staging = path.with_name(f".{path.name}.{os.getpid()}.tmp")
                staging.write_text(updated, encoding="utf-8", newline="\n")
                os.replace(staging, path)
    except (
        OSError,
        UnicodeError,
        ProjectError,
        RoadmapWorkError,
        RoadmapDependencyError,
    ) as exc:
        raise CliFailure(
            getattr(exc, "code", "roadmap_work.write_failed"),
            getattr(exc, "message", str(exc)),
        ) from exc
    return {
        "schema": "literate-ai/roadmap-work-result@1",
        "operation": args.work_command,
        "work_id": args.work_id,
        "path": path.relative_to(project.root).as_posix(),
        "changed": updated != content,
    }, 0


__all__ = ["work_from_args"]
