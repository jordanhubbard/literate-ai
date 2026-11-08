"""Retain both qualified trees while transactionally revising their registration."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

from literate_ai._cache_lock import CacheLockError, exclusive_cache_lock
from literate_ai._filesystem import ensure_safe_directory
from literate_ai.adapters.authority import FileAuthorityProjectionStore
from literate_ai.adapters.conversion_authority import (
    NATIVE_PROJECTS_FILE,
    NATIVE_PROJECTS_SCHEMA,
    FilesystemConversionAuthorityStore,
    _current_receipt_identity,
    _native_project_roots,
    evidence_for_conversion_stage,
    require_current_qualified_conversion_authority,
    require_native_project_path,
)
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.adapters.native_child_replacement import (
    NativeChildReplacementError,
    _tree,
)
from literate_ai.adapters.native_project_updates import _read, _replace_metadata
from literate_ai.application.native_child_revision import NativeChildRevisionError
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_child_revision import (
    QualifiedNativeChildRevisionPlan,
    QualifiedNativeChildSnapshot,
)
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
)
from literate_ai.projects import load_project

_JOURNALS = ".literate/native-child-revisions"
_JOURNAL_SCHEMA = "literate-ai/qualified-native-child-revision-journal@1"
_MAXIMUM_JOURNAL_BYTES = 16 * 1024 * 1024


def _refuse(code: str, message: str) -> None:
    raise NativeChildRevisionError(code, message)


def read_revision_plan_document(path: Path) -> object:
    return json.loads(_read(path, maximum_bytes=2 * 1024 * 1024))


def _bytes_identity(content: bytes):
    return ContentIdentity.parse_uri("sha256:" + hashlib.sha256(content).hexdigest())


def _project(root: Path):
    if root.is_symlink():
        _refuse("unsafe_parent", "the parent must be a direct project directory")
    return load_project(root)


def _child_path(project, supplied: Path) -> Path:
    child = supplied if supplied.is_absolute() else project.root / supplied
    require_native_project_path(project, child / "literate.project.json")
    if child.is_symlink() or child.parent != project.root / ".literate/native-projects":
        _refuse("unsafe_child", "revision requires direct native child directories")
    return child


def _tree_identity(child: Path):
    try:
        return canonical_identity(
            {"root_mode": stat.S_IMODE(child.lstat().st_mode), "entries": _tree(child)}
        )
    except NativeChildReplacementError as exc:
        raise NativeChildRevisionError("tree_invalid", str(exc)) from exc


def _snapshot(project, child: Path) -> QualifiedNativeChildSnapshot:
    child = _child_path(project, child)
    tree = _tree_identity(child)
    candidate = load_project(child)
    definition = _read(child / "literate.project.json")
    evidence = evidence_for_conversion_stage(
        candidate, ConversionAuthorityStage.QUALIFIED
    )
    store = FileAuthorityProjectionStore(child)
    coordinates = tuple(sorted(store.coordinates()))
    heads = tuple(
        sorted((store.current(c).identity for c in coordinates), key=lambda v: v.uri)
    )
    receipt = _current_receipt_identity(candidate)
    snapshot = QualifiedNativeChildSnapshot(
        child=child.relative_to(project.root).as_posix(),
        project_id=candidate.definition.project_id,
        definition=canonical_identity(json.loads(definition)),
        receipt=receipt,
        tree=tree,
        coordinates=coordinates,
        authorities=heads,
        evidence=tuple(sorted(evidence, key=lambda value: value.uri)),
    )
    if _tree_identity(child) != tree:
        _refuse("inputs_changed", "a child changed during qualification observation")
    return snapshot


def _registration_content(
    before: bytes, plan: QualifiedNativeChildRevisionPlan
) -> bytes:
    document = json.loads(before)
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "projects"}
        or document["schema"] != NATIVE_PROJECTS_SCHEMA
        or not isinstance(document["projects"], list)
    ):
        _refuse("registry_invalid", "the prior registry is invalid")
    entries = document["projects"]
    if (
        any(
            not isinstance(item, dict)
            or set(item) != {"path", "project_id", "project_definition_identity"}
            or not all(isinstance(value, str) for value in item.values())
            for item in entries
        )
        or len({item["path"] for item in entries}) != len(entries)
        or len({item["project_id"] for item in entries}) != len(entries)
    ):
        _refuse("registry_invalid", "registry entries must be exact and unique")
    previous = {
        "path": plan.previous.child,
        "project_id": plan.previous.project_id,
        "project_definition_identity": plan.previous.definition.uri,
    }
    replacement = {
        "path": plan.replacement.child,
        "project_id": plan.replacement.project_id,
        "project_definition_identity": plan.replacement.definition.uri,
    }
    if entries.count(previous) != 1 or any(
        item != previous
        and (
            item.get("path") == replacement["path"]
            or item.get("project_id") == replacement["project_id"]
        )
        for item in entries
    ):
        _refuse("registry_invalid", "the registry does not match the reviewed revision")
    return (
        canonical_json_bytes(
            {
                "schema": NATIVE_PROJECTS_SCHEMA,
                "projects": sorted(
                    (replacement if item == previous else item for item in entries),
                    key=lambda item: item["path"],
                ),
            }
        )
        + b"\n"
    )


def _renewed(before: bytes, plan: QualifiedNativeChildRevisionPlan):
    prior = ConversionAuthorityState.from_dict(json.loads(before))
    previous = set(plan.previous.evidence)
    expected = tuple(
        sorted(
            (set(prior.evidence_identities) - previous)
            | set(plan.replacement.evidence),
            key=lambda value: value.uri,
        )
    )
    if (
        canonical_json_bytes(prior.to_dict()) + b"\n" != before
        or prior.stage != ConversionAuthorityStage.QUALIFIED
        or prior.identity != plan.parent_authority
        or not previous.issubset(prior.evidence_identities)
        or plan.expected_evidence != expected
    ):
        _refuse(
            "journal_invalid",
            "the exact prior-to-replacement evidence union is required",
        )
    return ConversionAuthorityState(
        project_id=prior.project_id,
        stage=ConversionAuthorityStage.QUALIFIED,
        evidence_identities=expected,
        prior_state_identity=prior.identity,
    )


def _plan(
    parent: Path, child: Path, replacement: Path
) -> QualifiedNativeChildRevisionPlan:
    project = _project(parent)
    child, replacement = _child_path(project, child), _child_path(project, replacement)
    registry = _read(project.root / NATIVE_PROJECTS_FILE)
    definition = _read(project.root / "literate.project.json")
    store = FilesystemConversionAuthorityStore(project.root)
    state = store.load_optional()
    prior = require_current_qualified_conversion_authority(project, state)
    receipt = _current_receipt_identity(project)
    roots = _native_project_roots(project)
    if child not in roots or replacement in roots or child == replacement:
        _refuse(
            "registration_invalid",
            "revise one registered child to an unregistered replacement",
        )
    previous, proposed = _snapshot(project, child), _snapshot(project, replacement)
    if proposed.project_id == project.definition.project_id:
        _refuse("collision", "a child cannot reuse its parent project identifier")
    coordinates = set(proposed.coordinates)
    for root in (project.root, *(r for r in roots if r != child)):
        if coordinates.intersection(FileAuthorityProjectionStore(root).coordinates()):
            _refuse("collision", "replacement coordinates collide with another project")
    plan = QualifiedNativeChildRevisionPlan(
        parent_definition=canonical_identity(json.loads(definition)),
        parent_authority=state.identity,
        parent_receipt=receipt,
        registry=_bytes_identity(registry),
        previous=previous,
        replacement=proposed,
        expected_evidence=tuple(
            sorted(
                (set(prior) - set(previous.evidence)) | set(proposed.evidence),
                key=lambda value: value.uri,
            )
        ),
    )
    _registration_content(registry, plan)
    _renewed(_read(store.path), plan)
    if (
        _read(project.root / NATIVE_PROJECTS_FILE) != registry
        or _read(project.root / "literate.project.json") != definition
        or store.load_optional() != state
        or _snapshot(project, child) != previous
        or _snapshot(project, replacement) != proposed
        or require_current_qualified_conversion_authority(project, state) != prior
        or _current_receipt_identity(project) != receipt
    ):
        _refuse("inputs_changed", "reviewed project inputs changed during planning")
    return plan


def _payload(document, name):
    return base64.b64decode(document[name], validate=True)


def _journal(project, plan, registry, authority):
    base = project.root / _JOURNALS
    require_native_project_path(project, base)
    ensure_safe_directory(base)
    directory = Path(tempfile.mkdtemp(prefix=plan.identity.digest + "-", dir=base))
    path = directory / "journal.json"
    document = {
        "schema": _JOURNAL_SCHEMA,
        "status": "prepared",
        "plan": plan.to_dict(),
        "registry_before": base64.b64encode(registry).decode("ascii"),
        "authority_before": base64.b64encode(authority).decode("ascii"),
        "registry_after": base64.b64encode(
            _registration_content(registry, plan)
        ).decode("ascii"),
        "authority_after": base64.b64encode(
            canonical_json_bytes(_renewed(authority, plan).to_dict()) + b"\n"
        ).decode("ascii"),
    }
    content = canonical_json_bytes(document) + b"\n"
    if len(content) > _MAXIMUM_JOURNAL_BYTES:
        _refuse("journal_limit", "the revision journal exceeds its metadata bound")
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return path, document


def _status(project, path, document, status):
    content = _read(path, maximum_bytes=_MAXIMUM_JOURNAL_BYTES)
    observed = json.loads(content)
    if (
        not isinstance(observed, dict)
        or {key: value for key, value in observed.items() if key != "status"}
        != {key: value for key, value in document.items() if key != "status"}
        or observed.get("status")
        not in {"prepared", "applied", "rolled_back", "recovered"}
    ):
        _refuse("journal_invalid", "the revision journal changed before completion")
    _replace_metadata(
        project,
        path,
        content,
        canonical_json_bytes({**document, "status": status}) + b"\n",
    )


def _restore(project, document):
    store = FilesystemConversionAuthorityStore(project.root)
    paths = (project.root / NATIVE_PROJECTS_FILE, store.path)
    current = tuple(_read(path) for path in paths)
    for index, kind in enumerate(("registry", "authority")):
        if current[index] not in (
            _payload(document, kind + "_before"),
            _payload(document, kind + "_after"),
        ):
            _refuse("recovery_conflict", "metadata changed outside this transaction")
    for index, kind in enumerate(("registry", "authority")):
        _replace_metadata(
            project, paths[index], current[index], _payload(document, kind + "_before")
        )
    state = store.load_optional()
    require_current_qualified_conversion_authority(project, state)
    return state


def _read_journal(project, supplied: Path):
    path = supplied if supplied.is_absolute() else project.root / supplied
    if path.name != "journal.json":
        path = path / "journal.json"
    require_native_project_path(project, path)
    if path.parent.parent != project.root / _JOURNALS:
        _refuse("journal_invalid", "recovery requires an owned revision journal")
    content = _read(path, maximum_bytes=_MAXIMUM_JOURNAL_BYTES)
    document = json.loads(content)
    fields = {
        "schema",
        "status",
        "plan",
        "registry_before",
        "authority_before",
        "registry_after",
        "authority_after",
    }
    if (
        not isinstance(document, dict)
        or set(document) != fields
        or document["schema"] != _JOURNAL_SCHEMA
        or document["status"] not in {"prepared", "applied", "rolled_back", "recovered"}
        or canonical_json_bytes(document) + b"\n" != content
        or (os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077)
    ):
        _refuse("journal_invalid", "the revision journal is changed or unsafe")
    plan = QualifiedNativeChildRevisionPlan.from_dict(document["plan"])
    if not path.parent.name.startswith(plan.identity.digest + "-"):
        _refuse("journal_invalid", "the journal directory does not match its plan")
    registry, authority = (
        _payload(document, "registry_before"),
        _payload(document, "authority_before"),
    )
    renewed = _renewed(authority, plan)
    if (
        _bytes_identity(registry) != plan.registry
        or renewed.project_id != project.definition.project_id
        or _registration_content(registry, plan) != _payload(document, "registry_after")
        or canonical_json_bytes(renewed.to_dict()) + b"\n"
        != _payload(document, "authority_after")
        or canonical_identity(json.loads(_read(project.root / "literate.project.json")))
        != plan.parent_definition
        or _current_receipt_identity(project) != plan.parent_receipt
        or _snapshot(project, project.root / plan.previous.child) != plan.previous
        or _snapshot(project, project.root / plan.replacement.child) != plan.replacement
    ):
        _refuse(
            "recovery_conflict", "reviewed parent or qualified child inputs changed"
        )
    store = FilesystemConversionAuthorityStore(project.root)
    observed_registry, observed_authority = (
        _read(project.root / NATIVE_PROJECTS_FILE),
        _read(store.path),
    )
    if observed_registry not in (
        registry,
        _payload(document, "registry_after"),
    ) or observed_authority not in (authority, _payload(document, "authority_after")):
        _refuse("recovery_conflict", "metadata changed outside this transaction")
    expected = (
        plan.expected_evidence
        if observed_registry == _payload(document, "registry_after")
        else ConversionAuthorityState.from_dict(
            json.loads(authority)
        ).evidence_identities
    )
    if (
        evidence_for_conversion_stage(project, ConversionAuthorityStage.QUALIFIED)
        != expected
    ):
        _refuse("recovery_conflict", "current component qualification changed")
    return path, document


class FilesystemNativeChildRevisionAdapter:
    def plan(
        self, parent: Path, child: Path, replacement: Path
    ) -> QualifiedNativeChildRevisionPlan:
        return _plan(parent, child, replacement)

    def apply(
        self, parent: Path, plan: QualifiedNativeChildRevisionPlan
    ) -> dict[str, object]:
        project = _project(parent)
        store = FilesystemConversionAuthorityStore(project.root)
        registry = project.root / NATIVE_PROJECTS_FILE
        require_native_project_path(project, registry)
        try:
            with (
                project_lifecycle_lock(
                    project.root, operation="native-child.apply-revise"
                ),
                exclusive_cache_lock(registry.with_suffix(".lock")),
                exclusive_cache_lock(store.lock_path),
            ):
                if (
                    _plan(
                        project.root,
                        project.root / plan.previous.child,
                        project.root / plan.replacement.child,
                    )
                    != plan
                ):
                    _refuse("plan_changed", "the reviewed revision plan is stale")
                path, document = _journal(
                    project, plan, _read(registry), _read(store.path)
                )
                try:
                    _replace_metadata(
                        project,
                        registry,
                        _payload(document, "registry_before"),
                        _payload(document, "registry_after"),
                    )
                    _replace_metadata(
                        project,
                        store.path,
                        _payload(document, "authority_before"),
                        _payload(document, "authority_after"),
                    )
                    _read_journal(project, path)
                    state = store.load_optional()
                    require_current_qualified_conversion_authority(project, state)
                    _status(project, path, document, "applied")
                except Exception:
                    _restore(project, document)
                    _status(project, path, document, "rolled_back")
                    raise
                return {
                    "applied": True,
                    "authority_identity": state.identity.uri,
                    "plan_identity": plan.identity.uri,
                    "journal": path.relative_to(project.root).as_posix(),
                }
        except CacheLockError as exc:
            raise NativeChildRevisionError(
                "locked", "native child revision is already locked"
            ) from exc

    def recover(self, parent: Path, journal: Path) -> dict[str, object]:
        project = _project(parent)
        store = FilesystemConversionAuthorityStore(project.root)
        registry = project.root / NATIVE_PROJECTS_FILE
        require_native_project_path(project, registry)
        try:
            with (
                project_lifecycle_lock(
                    project.root, operation="native-child.recover-revise"
                ),
                exclusive_cache_lock(registry.with_suffix(".lock")),
                exclusive_cache_lock(store.lock_path),
            ):
                path, document = _read_journal(project, journal)
                if document["status"] != "prepared":
                    suffix = "after" if document["status"] == "applied" else "before"
                    if _read(registry) != _payload(
                        document, "registry_" + suffix
                    ) or _read(store.path) != _payload(document, "authority_" + suffix):
                        _refuse(
                            "recovery_conflict", "completed journal metadata changed"
                        )
                    return {
                        "recovered": False,
                        "status": document["status"],
                        "journal": path.relative_to(project.root).as_posix(),
                    }
                state = _restore(project, document)
                _status(project, path, document, "recovered")
                return {
                    "recovered": True,
                    "authority_identity": state.identity.uri,
                    "journal": path.relative_to(project.root).as_posix(),
                }
        except CacheLockError as exc:
            raise NativeChildRevisionError(
                "locked", "native child revision recovery is already locked"
            ) from exc
