"""Apply upstream-only changes, clean merges, and explicitly reviewed resolutions.

All input bytes are rechecked. File writes and the upstream baseline checkpoint
roll back together if prospective-project validation fails. Local overlays and
unselected overlapping conflicts remain untouched.
"""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from literate_ai._filesystem import path_is_link_or_reparse
from literate_ai.contracts import (
    ProjectUpdateClassification,
    ProjectUpdateFile,
    ProjectUpdatePlan,
)
from literate_ai.contracts.project_updates import update_adopts_additions

from .native_profile_git import (
    NativeProfileGitBoundaryError,
    require_native_profile_git_boundary,
)
from .project_updates import (
    ProjectUpdateError,
    _identity,
    _project_path,
    _read_contract,
    _template_placement,
    _upstream_template,
)

APPLY_RESULT_SCHEMA = "literate-ai/project-update-apply@1"

MECHANICAL = (
    ProjectUpdateClassification.UPSTREAM_ONLY,
    ProjectUpdateClassification.MERGEABLE,
)
OPT_IN = (ProjectUpdateClassification.UPSTREAM_ADDED,)


def _selected_update_paths(plan, *, adopt_added, resolutions):
    adopting = update_adopts_additions(plan.files, explicit=adopt_added)
    selected = MECHANICAL + OPT_IN if adopting else MECHANICAL
    return {
        item.path
        for item in plan.files
        if item.compatibility is None
        and (item.classification in selected or item.path in resolutions)
    }


def _require_native_update_git_boundary(root, paths):
    try:
        require_native_profile_git_boundary(root, paths)
    except NativeProfileGitBoundaryError as exc:
        raise ProjectUpdateError("project.native_update_nested_git", str(exc)) from exc


@dataclass(frozen=True, slots=True)
class AppliedProjectUpdate:
    """What an apply actually wrote, and what it deliberately left alone."""

    applied: tuple[str, ...]
    adopted: tuple[str, ...]
    refused: dict[str, tuple[str, ...]]
    adopted_because: str | None = None
    merged: tuple[str, ...] = ()
    resolutions: tuple[dict, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema": APPLY_RESULT_SCHEMA,
            "applied": list(self.applied),
            "merged": list(self.merged),
            "resolutions": list(self.resolutions),
            "adopted": list(self.adopted),
            "refused": {
                key: list(value) for key, value in sorted(self.refused.items())
            },
            "authority_review_required": bool(self.applied or self.adopted),
        }
        if self.adopted_because:
            value["adopted_because"] = self.adopted_because
        # A refusal the operator can lift should say so; silence reads as a verdict.
        if self.refused.get(ProjectUpdateClassification.UPSTREAM_ADDED.value):
            value["hint"] = "re-run with --adopt-added to take the added files"
        if self.refused.get("dependency-incompatible"):
            value["hint"] = (
                "Review incompatible skill dependencies and explicitly update the "
                "pinned parent catalog before re-planning those additions."
            )
        return value


def _write_exact(target: Path, content: bytes, *, _observation=None, _mode=None):
    """Replace a file atomically; a crash must not leave a half-written file."""

    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".litai-update-")
    prepared = None
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            if _observation is not None and _mode is not None:
                os.fchmod(stream.fileno(), _mode)
            if _observation is not None:
                prepared = os.fstat(stream.fileno())
            os.fsync(stream.fileno())
            if _observation is not None:
                from .retained_cargo_tree_v2 import _node

                if _node(os.fstat(stream.fileno())) != _node(prepared):
                    raise ProjectUpdateError(
                        "project.update_local_changed",
                        "private update payload changed during fsync",
                    )
        if _observation is None:
            os.replace(temporary, target)
        else:
            from .retained_layout_control_publication import _pinned_directory

            with _pinned_directory(target.parent) as (descriptor, guard):
                guard()
                _observation.before_replace(target, Path(temporary), prepared)
                os.replace(
                    Path(temporary).name,
                    target.name,
                    src_dir_fd=descriptor,
                    dst_dir_fd=descriptor,
                )
                descriptor_file = os.open(
                    target.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor
                )
                try:
                    published = os.fstat(descriptor_file)
                finally:
                    os.close(descriptor_file)
                attrs = (
                    "st_dev",
                    "st_ino",
                    "st_mode",
                    "st_size",
                    "st_mtime_ns",
                    "st_nlink",
                    "st_uid",
                    "st_gid",
                )
                if any(
                    getattr(prepared, name) != getattr(published, name)
                    for name in attrs
                ):
                    raise ProjectUpdateError(
                        "project.update_local_changed", "published update node changed"
                    )
                guard()
                return (
                    published.st_dev,
                    published.st_ino,
                    published.st_mode,
                    published.st_size,
                    published.st_mtime_ns,
                    published.st_ctime_ns,
                )
        return None
    except BaseException:
        if _observation is None:
            Path(temporary).unlink(missing_ok=True)
        elif prepared is not None:
            from .retained_cargo_tree_v2 import _node

            try:
                if _node(Path(temporary).lstat()) == _node(prepared):
                    Path(temporary).unlink()
            except FileNotFoundError:
                pass
        raise


def apply_project_update(
    plan: ProjectUpdatePlan,
    root: Path,
    *,
    adopt_added: bool = False,
    validator: Callable[[Path], object] | None = None,
    resolutions: dict | None = None,
    native_lock: Path | None = None,
    _role_observation=None,
) -> AppliedProjectUpdate:
    """Write one rollback-safe subset and optionally validate the complete result."""

    if not isinstance(plan, ProjectUpdatePlan):
        raise ProjectUpdateError(
            "project.update_plan_invalid", "apply requires a typed update plan"
        )
    root = Path(root).resolve()
    from literate_ai.adapters.project_initialization import INITIALIZATION_BASELINE_FILE
    from literate_ai.contracts import ProjectInitializationBaseline
    from literate_ai.projects import ProjectConfigurationStore

    context = ProjectConfigurationStore.context(root)
    root = context.root
    profile = "generated"
    if context.framework_root != root:
        baseline = _read_contract(
            root, INITIALIZATION_BASELINE_FILE, ProjectInitializationBaseline
        )
        if baseline.identity != plan.baseline_identity:
            raise ProjectUpdateError(
                "project.update_base_changed",
                "initialization baseline changed; re-plan",
            )
        profile = baseline.profile
    if _role_observation is not None:
        from .framework_update_roles import _FrameworkUpdateRoles

        if type(_role_observation) is not _FrameworkUpdateRoles:
            raise TypeError("actual framework update observation required")
        _role_observation._before_apply(plan, root)
    from .update_merge import UpdateBases, resolution_content

    resolutions = resolutions or {}
    bases = (
        UpdateBases(root) if _role_observation is None else _role_observation.bases()
    )
    if (
        plan.update_bases_identity is not None
        and _identity(bases.original or b"") != plan.update_bases_identity
    ):
        raise ProjectUpdateError(
            "project.update_base_changed", "update baseline changed; re-plan"
        )
    if set(resolutions) - {item.path for item in plan.files}:
        raise ProjectUpdateError(
            "project.update_resolution_invalid", "unknown resolution path"
        )
    write_content: dict[str, bytes | None] = {}
    merged: list[str] = []
    # The opt-in on upstream-added exists to guard judgment: adopting a capability a
    # project never had is a decision. A project that has not diverged from its
    # baseline has no such decision to make -- there is nothing local to protect and
    # nothing to reconcile -- so refusing there only obstructs the operator. Divergence
    # means the project changed a framework-owned file: local-only or conflict.
    selected = _selected_update_paths(
        plan, adopt_added=adopt_added, resolutions=resolutions
    )

    baseline_paths = {
        item.path for item in plan.files if item.baseline_identity is not None
    }
    placement = None
    if context.framework_root != root and profile != "native":
        from literate_ai.projects import ProjectError, load_project

        try:
            project = (
                load_project(root)
                if _role_observation is None
                else _role_observation.project(root)
            )
        except ProjectError as error:
            raise ProjectUpdateError(error.code, str(error)) from error
        if project is None or project.definition.identity != plan.project_identity:
            raise ProjectUpdateError(
                "project.update_project_changed",
                "project definition changed after planning; re-plan before applying",
            )
        placement = _template_placement(project, profile=profile)
    upstream_content = _upstream_template(
        baseline_paths,
        profile=profile,
        observation=_role_observation,
        **({"placement": placement} if placement is not None else {}),
    )
    applied: list[str] = []
    adopted: list[str] = []
    refused: dict[str, list[str]] = {}
    snapshots: dict[str, tuple[bytes | None, int | None]] = {}
    created_directories: set[Path] = set()
    selected_items: list[ProjectUpdateFile] = []

    for item in plan.files:
        if item.compatibility is not None:
            if item.path in resolutions:
                raise ProjectUpdateError(*item.compatibility)
            reason = (
                "layout-pending"
                if item.compatibility[0] == "project.update_layout_pending"
                else "dependency-incompatible"
            )
            refused.setdefault(reason, []).append(item.path)
            continue
        if item.path not in selected:
            if item.classification in (
                ProjectUpdateClassification.CONFLICT,
                ProjectUpdateClassification.LOCAL_ONLY,
                *OPT_IN,
            ):
                refused.setdefault(item.classification.value, []).append(item.path)
            continue

        content = upstream_content.get(item.path)
        removing = item.upstream_identity is None
        if removing:
            if (
                content is not None
                or item.baseline_identity is None
                or item.local_identity != item.baseline_identity
            ):
                raise ProjectUpdateError(
                    "project.update_removal_unsafe",
                    f"upstream removal for {item.path} is not baseline-identical",
                )
        elif content is None or _identity(content) != item.upstream_identity:
            raise ProjectUpdateError(
                "project.update_upstream_changed",
                f"upstream content for {item.path} changed after planning; re-plan "
                "before applying",
            )
        target = _project_path(root, item.path)
        if path_is_link_or_reparse(target):
            raise ProjectUpdateError(
                "project.update_path_unsafe",
                f"{item.path} is a link and cannot be replaced",
            )
        observed_content = (
            (target.read_bytes() if target.is_file() else None)
            if _role_observation is None
            else _role_observation.read(item.path, optional=True)
        )
        observed = None if observed_content is None else _identity(observed_content)
        if observed != item.local_identity:
            raise ProjectUpdateError(
                "project.update_local_changed",
                f"{item.path} changed after planning; re-plan before applying",
            )

        write_content[item.path] = resolution_content(
            item, observed_content, content, resolutions, _observation=_role_observation
        )
        if (
            item.classification is ProjectUpdateClassification.MERGEABLE
            or resolutions.get(item.path, {}).get("decision") == "merge"
        ):
            merged.append(item.path)
        snapshots[item.path] = (
            observed_content,
            stat.S_IMODE(target.stat().st_mode) if target.is_file() else None,
        )
        selected_items.append(item)

    from .project_update_compatibility import require_selected_skill_closure

    if _role_observation is not None:
        _role_observation.before_writes(selected_items)
    if _role_observation is None:
        require_selected_skill_closure(root, write_content)
    else:
        require_selected_skill_closure(
            root, write_content, _observation=_role_observation
        )
    from literate_ai.application.roadmap_dependencies import RoadmapDependencyError

    from .roadmap_dependencies import require_project_roadmap_acyclic

    try:
        if _role_observation is None:
            require_project_roadmap_acyclic(root, write_content)
        else:
            require_project_roadmap_acyclic(
                root, write_content, _observation=_role_observation
            )
    except RoadmapDependencyError as exc:
        raise ProjectUpdateError(exc.code, exc.message) from exc
    native = profile == "native"
    lock_paths = () if native_lock is None else (native_lock,)
    native_paths = (*write_content, bases.checkpoint, *lock_paths)

    def checkpoint_guard(path):
        _require_native_update_git_boundary(root, (path,))

    checkpoint_before_write = checkpoint_guard if native else None
    if native:
        _require_native_update_git_boundary(root, native_paths)
    written: list[str] = []
    receipts = {}
    advanced = []
    checkpoint = None
    checkpoint_receipt = None
    try:
        for item in selected_items:
            target = _project_path(root, item.path)
            content = write_content[item.path]
            if native:
                _require_native_update_git_boundary(root, (target, *lock_paths))
            if content is None:
                if _role_observation is not None:
                    _role_observation.retire(target)
                else:
                    target.unlink(missing_ok=True)
                receipts[item.path] = None
            else:
                parent = target.parent
                while parent != root and not parent.exists():
                    created_directories.add(parent)
                    parent = parent.parent
                assert content is not None
                receipts[item.path] = (
                    _write_exact(target, content)
                    if _role_observation is None
                    else _write_exact(
                        target,
                        content,
                        _observation=_role_observation,
                        _mode=snapshots[item.path][1],
                    )
                )
            if _role_observation is not None:
                _role_observation.after_publication(
                    target, content, receipts[item.path]
                )
            written.append(item.path)
            mode = snapshots[item.path][1]
            if (
                content is not None
                and os.name != "nt"
                and mode is not None
                and _role_observation is None
            ):
                if native:
                    _require_native_update_git_boundary(root, (target,))
                os.chmod(target, mode)
            if item.classification is ProjectUpdateClassification.UPSTREAM_ADDED:
                adopted.append(item.path)
            else:
                applied.append(item.path)
        for item in plan.files:
            if item in selected_items or item.classification in (
                ProjectUpdateClassification.UNCHANGED,
                ProjectUpdateClassification.ALREADY_CURRENT,
            ):
                content = upstream_content.get(item.path)
                if content is not None or item in selected_items:
                    bases.advance("framework", item.path, content)
                    advanced.append(item)
        if native:
            _require_native_update_git_boundary(root, native_paths)
        if _role_observation is None:
            bases.write(before_write=checkpoint_before_write)
        else:
            checkpoint = bases.write(
                _observation=_role_observation, before_write=checkpoint_before_write
            )
            checkpoint_receipt = bases.published_node
        if validator is not None:
            validator(root)
        if native:
            _require_native_update_git_boundary(root, native_paths)
    except BaseException as error:
        if _role_observation is not None:
            from .framework_update_roles import FrameworkUpdateRoleError

            if not isinstance(error, Exception):
                error.add_note(
                    "update did not complete; observed state retained; "
                    "handoff unavailable"
                )
                raise
            raise FrameworkUpdateRoleError(
                "update did not complete; observed state retained; handoff unavailable"
            ) from error
        try:
            rollback_checkpoint = not native or bases.checkpoint_needs_rollback()
            if native:
                rollback_paths = (
                    (*written, bases.checkpoint) if rollback_checkpoint else written
                )
                _require_native_update_git_boundary(root, rollback_paths)
            if rollback_checkpoint:
                bases.rollback(
                    before_write=checkpoint_before_write, require_intended=native
                )
            for path in reversed(written):
                target = _project_path(root, path)
                if native:
                    _require_native_update_git_boundary(root, (target,))
                previous, mode = snapshots[path]
                if previous is None:
                    target.unlink(missing_ok=True)
                else:
                    _write_exact(target, previous)
                    if os.name != "nt" and mode is not None:
                        if native:
                            _require_native_update_git_boundary(root, (target,))
                        os.chmod(target, mode)
            for directory in sorted(
                created_directories,
                key=lambda item: len(item.parts),
                reverse=True,
            ):
                if native:
                    _require_native_update_git_boundary(root, (directory,))
                try:
                    directory.rmdir()
                except OSError:
                    pass
        except BaseException as rollback_error:
            raise ProjectUpdateError(
                "project.update_rollback_failed",
                "project update failed and exact rollback could not be completed",
            ) from rollback_error
        raise

    result = AppliedProjectUpdate(
        tuple(sorted(applied)),
        tuple(sorted(adopted)),
        {key: tuple(sorted(value)) for key, value in refused.items()},
        merged=tuple(sorted(merged)),
        resolutions=tuple(
            {**resolutions[path], "applied": True} for path in sorted(resolutions)
        ),
        adopted_because=(
            None
            if not adopted
            else "requested"
            if adopt_added
            else "the project has not diverged from its baseline"
        ),
    )
    if _role_observation is not None:
        from .framework_update_roles import FrameworkUpdateRoleError

        try:
            _role_observation._complete(
                plan,
                result,
                advanced,
                upstream_content,
                write_content,
                receipts,
                checkpoint,
                checkpoint_receipt,
            )
        except Exception as error:
            raise FrameworkUpdateRoleError(
                "update applied, handoff unavailable: " + str(error)
            ) from error
    return result


__all__ = [
    "APPLY_RESULT_SCHEMA",
    "MECHANICAL",
    "OPT_IN",
    "AppliedProjectUpdate",
    "apply_project_update",
]
