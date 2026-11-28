"""Reviewed, exact registry coordination for registered native child updates."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai._cache_lock import CacheLockError, exclusive_cache_lock
from literate_ai._filesystem import ensure_safe_directory, stat_is_link_or_reparse
from literate_ai.adapters.conversion_authority import (
    NATIVE_PROJECTS_FILE,
    ConversionAuthorityError,
    _named_file_matches,
    _native_project_roots,
    require_native_project_path,
)
from literate_ai.application.standard_lifecycle_rebind import (
    DistributionObserver,
    OriginObserver,
    PolicyLoader,
    StandardLifecycleRebindError,
    _validated_plan,
    apply_standard_lifecycle_rebind,
    plan_standard_lifecycle_rebind,
)
from literate_ai.contracts import (
    ProjectTestReceiptPolicy,
    StandardProjectLifecycleDriver,
    canonical_identity,
    canonical_json_bytes,
    load_current_standard_lifecycle_policy,
)
from literate_ai.projects import (
    DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES,
    LoadedProject,
    ProjectConfigurationStore,
    ProjectContext,
    ProjectError,
    parse_project_configuration,
    serialize_project_configuration,
)

REGISTERED_REBIND_PLAN_SCHEMA = "literate-ai/registered-child-rebind-plan@1"
CONTAINED_REGISTERED_REBIND_PLAN_SCHEMA = "literate-ai/registered-child-rebind-plan@2"


def _error(code: str, message: str) -> None:
    raise StandardLifecycleRebindError("standard_rebind." + code, message)


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _read(
    path: Path, *, maximum_bytes: int = DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES
) -> bytes:
    named = path.lstat()
    if not stat.S_ISREG(named.st_mode) or stat_is_link_or_reparse(named):
        _error(
            "registered_metadata_invalid",
            "registered metadata must be a direct regular file",
        )
    # Nonblocking open prevents a raced-in FIFO from hanging a reviewed update.
    # NOFOLLOW closes the symlink race where the platform supports it.
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        content = stream.read(maximum_bytes + 1)
        after = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or len(content) > maximum_bytes
            or (before.st_size, before.st_mtime_ns)
            != (after.st_size, after.st_mtime_ns)
            or not _named_file_matches(path, stream.fileno(), before)
        ):
            _error("registered_metadata_changed", "registered project metadata changed")
    return content


@dataclass(frozen=True)
class _RegisteredChild:
    parent: LoadedProject
    child: Path
    registry: bytes
    manifest: bytes
    parent_manifest: bytes
    context: dict[str, str]
    parent_context: ProjectContext
    child_context: ProjectContext

    def require_parent_current(self):
        if ProjectConfigurationStore.context(self.parent.root) != self.parent_context:
            _error("registered_metadata_changed", "original parent framework changed")

    def require_current(self):
        self.require_parent_current()
        if ProjectConfigurationStore.context(self.child) != self.child_context:
            _error("registered_metadata_changed", "original child framework changed")

    def framework_path(self, relative):
        self.require_parent_current()
        return self.parent_context.framework_path(relative)

    @property
    def plan_schema(self):
        return (
            REGISTERED_REBIND_PLAN_SCHEMA
            if self.parent_context.framework_root == self.parent.root
            else CONTAINED_REGISTERED_REBIND_PLAN_SCHEMA
        )


def _capture(parent_path: Path, child_path: Path) -> _RegisteredChild:
    try:
        return _capture_unchecked(parent_path, child_path)
    except StandardLifecycleRebindError:
        raise
    except (ConversionAuthorityError, ProjectError, OSError, ValueError) as exc:
        raise StandardLifecycleRebindError(
            "standard_rebind.registered_metadata_invalid",
            "registered parent or child metadata is stale, unavailable or unsafe",
        ) from exc


def _capture_unchecked(parent_path: Path, child_path: Path) -> _RegisteredChild:
    if parent_path.is_symlink():
        _error("registered_metadata_invalid", "registered parent must not be a symlink")
    parent_snapshot = ProjectConfigurationStore(parent_path).read()
    parent_context = ProjectConfigurationStore.context(parent_snapshot.root)
    if parent_snapshot.directory_binding != parent_context.directory_binding:
        _error("registered_metadata_changed", "parent framework changed during capture")
    parent = LoadedProject(parent_snapshot.root, parent_snapshot.definition)
    # Child and source declarations are always application-relative, including
    # when the caller selected the parent's declared framework coordinate.
    relative = child_path.absolute().relative_to(parent.root)
    child = parent.root / relative
    require_native_project_path(parent, ProjectConfigurationStore.manifest_path(child))
    registry_path = parent_context.framework_path(NATIVE_PROJECTS_FILE)
    registry = _read(registry_path)
    roots = _native_project_roots(parent)
    if ProjectConfigurationStore.context(parent.root) != parent_context:
        _error("registered_metadata_changed", "parent framework changed during capture")
    if _read(registry_path) != registry:
        _error("registered_metadata_changed", "registry changed during observation")
    child_snapshot = ProjectConfigurationStore.discover(child)
    if child_snapshot is None:
        _error("registered_metadata_invalid", "registered child has no direct project")
    child = child_snapshot.root
    if child not in roots:
        _error(
            "child_not_registered", "selected child is not registered by this parent"
        )
    child_context = ProjectConfigurationStore.context(child)
    if child_snapshot.directory_binding != child_context.directory_binding:
        _error("registered_metadata_changed", "child framework changed during capture")
    manifest = _read(child_context.manifest_path)
    parent_manifest = _read(parent_context.manifest_path)
    entry = next(
        item
        for item in json.loads(registry)["projects"]
        if parent.root.joinpath(*Path(item["path"]).parts) == child
    )
    definition_identity = canonical_identity(json.loads(manifest)).uri
    if (
        parent_manifest != parent_snapshot.content
        or manifest != child_snapshot.content
        or definition_identity != entry["project_definition_identity"]
        or parse_project_configuration(manifest).project_id != entry["project_id"]
    ):
        _error(
            "registered_metadata_changed", "parent or child changed during observation"
        )
    context = {
        "parent_project_id": parent.definition.project_id,
        "parent_configuration_identity": _digest(parent_manifest),
        "registry_identity": _digest(registry),
        "child_path": entry["path"],
        "child_configuration_identity": _digest(manifest),
        "child_definition_identity": definition_identity,
    }
    if parent_context.framework_root != parent.root:
        context["native_namespace_observation_identity"] = canonical_identity(
            {
                "parent": [
                    [str(v) for v in row] for row in parent_context.directory_binding
                ],
                "child": [
                    [str(v) for v in row] for row in child_context.directory_binding
                ],
            }
        ).uri
    captured = _RegisteredChild(
        parent,
        child,
        registry,
        manifest,
        parent_manifest,
        context,
        parent_context,
        child_context,
    )
    captured.require_current()
    return captured


def registered_parent_for_child(project: Path) -> Path | None:
    """Identify direct declared membership, never application metadata by name."""
    lexical = project.absolute()
    for candidate in (lexical, *lexical.parents):
        if (
            candidate.parent.name != "native-projects"
            or candidate.parent.parent.name != ".literate"
        ):
            continue
        context = ProjectConfigurationStore.context(candidate.parent.parent.parent)
        if candidate.parent != context.framework_path(".literate/native-projects"):
            continue
        registry = context.framework_path(NATIVE_PROJECTS_FILE)
        try:
            registry.lstat()
        except FileNotFoundError:
            continue
        return context.root
    return None


def plan_registered_standard_rebind(
    parent: Path,
    child: Path,
    *,
    distribution_observer: DistributionObserver,
    origin_observer: OriginObserver,
    policy_loader: PolicyLoader = load_current_standard_lifecycle_policy,
) -> dict[str, object]:
    captured = _capture(parent, child)
    rebind = plan_standard_lifecycle_rebind(
        captured.child,
        distribution_observer=distribution_observer,
        origin_observer=origin_observer,
        policy_loader=policy_loader,
    )
    captured.require_current()
    if _capture(parent, child).context != captured.context:
        _error("registered_metadata_changed", "parent or child changed while planning")
    result: dict[str, object] = {
        "schema": captured.plan_schema,
        "registration": captured.context,
        "rebind": rebind,
    }
    result["identity"] = canonical_identity(result).uri
    return result


def _replace_metadata(
    parent: LoadedProject, path: Path, previous: bytes, content: bytes
) -> None:
    context = parent.context

    def guard():
        if parent.context != context:
            _error(
                "registered_metadata_changed", "framework changed during replacement"
            )
        require_native_project_path(parent, path)

    guard()
    if _read(path) != previous:
        _error("registered_metadata_changed", "metadata changed before replacement")
    if content == previous:
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    descriptor, temporary = tempfile.mkstemp(prefix=".native-update.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.chmod(temporary, mode)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        guard()
        if _read(path) != previous:
            _error("registered_metadata_changed", "metadata changed during replacement")
        os.replace(temporary, path)
        guard()
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply_registered_standard_rebind(
    parent: Path,
    child: Path,
    plan: dict[str, object],
    *,
    authorize_rebind: bool,
    distribution_observer: DistributionObserver,
    origin_observer: OriginObserver,
    policy_loader: PolicyLoader = load_current_standard_lifecycle_policy,
) -> dict[str, object]:
    if authorize_rebind is not True:
        _error("authorization_required", "apply requires --authorize-rebind")
    if (
        set(plan) != {"schema", "registration", "rebind", "identity"}
        or plan.get("schema")
        not in {REGISTERED_REBIND_PLAN_SCHEMA, CONTAINED_REGISTERED_REBIND_PLAN_SCHEMA}
        or canonical_identity({k: v for k, v in plan.items() if k != "identity"}).uri
        != plan.get("identity")
        or not isinstance(plan.get("rebind"), dict)
    ):
        _error("plan_invalid", "registered-child rebind plan is invalid")
    initial = _capture(parent, child)
    if plan["schema"] != initial.plan_schema or initial.context != plan["registration"]:
        _error("registered_metadata_changed", "reviewed parent or child changed")
    registry_path = initial.framework_path(NATIVE_PROJECTS_FILE)
    try:
        with exclusive_cache_lock(registry_path.with_suffix(".lock")):
            initial.require_current()
            captured = _capture(parent, child)
            if captured.context != plan["registration"]:
                _error(
                    "registered_metadata_changed", "reviewed parent or child changed"
                )
            return _apply_locked(
                captured,
                plan,
                distribution_observer=distribution_observer,
                origin_observer=origin_observer,
                policy_loader=policy_loader,
            )
    except CacheLockError as exc:
        raise StandardLifecycleRebindError(
            "standard_rebind.registry_locked",
            "native registry is already being updated",
        ) from exc


def _retain_rebind_metadata(
    captured: _RegisteredChild,
    plan: dict[str, object],
    manifest: bytes,
    registry: bytes,
) -> dict[str, str]:
    """Keep original metadata as history, never as current qualification evidence."""
    document = {
        "schema": "literate-ai/registered-child-rebind-recovery@1",
        "plan": plan,
        "before": {
            "child_manifest_base64": base64.b64encode(captured.manifest).decode(
                "ascii"
            ),
            "registry_base64": base64.b64encode(captured.registry).decode("ascii"),
        },
        "after": {
            "child_manifest_base64": base64.b64encode(manifest).decode("ascii"),
            "registry_base64": base64.b64encode(registry).decode("ascii"),
        },
    }
    identity = canonical_identity(document).uri
    relative = Path(".literate/native-updates") / (
        str(plan["identity"])[7:23] + ".json"
    )
    path = captured.framework_path(relative.as_posix())
    require_native_project_path(captured.parent, path)
    ensure_safe_directory(path.parent)
    content = canonical_json_bytes(document) + b"\n"
    descriptor, temporary = tempfile.mkstemp(prefix=".rebind.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        require_native_project_path(captured.parent, path)
        captured.require_current()
        # Publish the complete record without overwriting prior retained history.
        os.link(temporary, path)
        captured.require_current()
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "path": path.relative_to(captured.parent.root).as_posix(),
        "identity": identity,
    }


def _apply_locked(
    captured: _RegisteredChild,
    plan: dict[str, object],
    *,
    distribution_observer: DistributionObserver,
    origin_observer: OriginObserver,
    policy_loader: PolicyLoader,
) -> dict[str, object]:
    parent = captured.parent
    child = captured.child
    captured.require_current()
    registry_path = captured.framework_path(NATIVE_PROJECTS_FILE)
    manifest_path = captured.child_context.manifest_path
    rebind = _validated_plan(plan["rebind"])
    proposed = replace(
        parse_project_configuration(captured.manifest),
        lifecycle_driver=StandardProjectLifecycleDriver.from_dict(
            rebind["proposed_binding"]
        ),
        test_receipt_policy=ProjectTestReceiptPolicy.from_dict(
            rebind["proposed_receipt_policy"]
        ),
    )
    updated_manifest = (
        serialize_project_configuration(proposed)
        if rebind["change_required"]
        else captured.manifest
    )
    updated_registry: bytes | None = None
    recovery: dict[str, str] | None = None
    try:
        result = apply_standard_lifecycle_rebind(
            child,
            plan["rebind"],
            authorize_rebind=True,
            distribution_observer=distribution_observer,
            origin_observer=origin_observer,
            policy_loader=policy_loader,
        )
        captured.require_current()
        observed_manifest = _read(manifest_path)
        if observed_manifest != updated_manifest:
            _error(
                "registered_metadata_changed",
                "rebound child changed before registration",
            )
        definition = json.loads(updated_manifest)
        # Bind the returned exact child configuration, never arbitrary later edits.
        if _digest(updated_manifest) != result["project_configuration_identity"]:
            _error(
                "registered_metadata_changed",
                "rebound child changed before registration",
            )
        if (
            _read(captured.parent_context.manifest_path) != captured.parent_manifest
            or _read(registry_path) != captured.registry
        ):
            _error("registered_metadata_changed", "parent changed during child update")
        registry = json.loads(captured.registry)
        for entry in registry["projects"]:
            if entry["path"] == captured.context["child_path"]:
                entry["project_definition_identity"] = canonical_identity(
                    definition
                ).uri
        updated_registry = (
            captured.registry
            if registry == json.loads(captured.registry)
            else canonical_json_bytes(registry) + b"\n"
        )
        captured.require_current()
        _replace_metadata(parent, registry_path, captured.registry, updated_registry)
        captured.require_current()
        _native_project_roots(parent)
        if rebind["change_required"]:
            recovery = _retain_rebind_metadata(
                captured, plan, updated_manifest, updated_registry
            )
    except BaseException:
        try:
            captured.require_current()
            current_manifest = _read(manifest_path)
            if current_manifest != captured.manifest:
                canonical_previous = serialize_project_configuration(
                    parse_project_configuration(captured.manifest)
                )
                expected = (
                    canonical_previous
                    if current_manifest == canonical_previous
                    else updated_manifest
                )
                _replace_metadata(parent, manifest_path, expected, captured.manifest)
            current_registry = _read(registry_path)
            if current_registry != captured.registry:
                if updated_registry is None:
                    _error(
                        "registered_metadata_changed",
                        "registry changed before rollback",
                    )
                _replace_metadata(
                    parent, registry_path, updated_registry, captured.registry
                )
        except (OSError, ValueError, ConversionAuthorityError, ProjectError) as exc:
            raise StandardLifecycleRebindError(
                "standard_rebind.registered_rollback_failed",
                "registered-child update failed; concurrent metadata blocked rollback",
            ) from exc
        raise
    result = {
        **result,
        "plan_identity": plan["identity"],
        "registration": {
            "previous_registry_identity": captured.context["registry_identity"],
            "registry_identity": _digest(updated_registry),
            "child_path": captured.context["child_path"],
        },
    }
    if recovery is not None:
        result["recovery"] = recovery
    result.pop("identity", None)
    result["identity"] = canonical_identity(result).uri
    return result
