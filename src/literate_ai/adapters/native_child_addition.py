"""Locked publication and guarded recovery of reviewed qualified-child additions."""

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
from literate_ai.adapters.native_project_updates import _read, _replace_metadata
from literate_ai.application.native_child_addition import NativeChildAdditionError
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_child_addition import QualifiedNativeChildAdditionPlan
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
)
from literate_ai.projects import load_project

_JOURNALS = ".literate/native-child-additions"
_JOURNAL_SCHEMA = "literate-ai/qualified-native-child-addition-journal@1"
_MAXIMUM_JOURNAL_BYTES = 16 * 1024 * 1024


def read_addition_plan_document(path: Path) -> object:
    """Read one bounded direct regular plan file for a public transport."""
    return json.loads(_read(path, maximum_bytes=2 * 1024 * 1024))


def _refuse(code: str, message: str) -> None:
    raise NativeChildAdditionError(code, message)


def _identity(content: bytes) -> ContentIdentity:
    return ContentIdentity.parse_uri("sha256:" + hashlib.sha256(content).hexdigest())


def _project(root: Path):
    if root.is_symlink():
        _refuse("unsafe_parent", "the adopted parent must be a direct directory")
    return load_project(root)


def _registration_content(
    before: bytes, plan: QualifiedNativeChildAdditionPlan
) -> bytes:
    entries = json.loads(before)["projects"]
    entry = {
        "path": plan.child,
        "project_id": plan.child_project_id,
        "project_definition_identity": plan.child_definition.uri,
    }
    return (
        canonical_json_bytes(
            {
                "schema": NATIVE_PROJECTS_SCHEMA,
                "projects": sorted([*entries, entry], key=lambda item: item["path"]),
            }
        )
        + b"\n"
    )


def _renewed(before: bytes, plan: QualifiedNativeChildAdditionPlan):
    prior = ConversionAuthorityState.from_dict(json.loads(before))
    if canonical_json_bytes(prior.to_dict()) + b"\n" != before:
        _refuse("journal_invalid", "the prior authority backup is not canonical")
    if (
        prior.stage != ConversionAuthorityStage.QUALIFIED
        or prior.identity != plan.parent_authority
        or plan.expected_evidence
        != tuple(
            sorted(
                set((*prior.evidence_identities, *plan.child_evidence)),
                key=lambda value: value.uri,
            )
        )
    ):
        _refuse(
            "journal_invalid",
            "the prior authority or evidence union does not match the reviewed plan",
        )
    return ConversionAuthorityState(
        project_id=prior.project_id,
        stage=ConversionAuthorityStage.QUALIFIED,
        evidence_identities=plan.expected_evidence,
        prior_state_identity=prior.identity,
    )


def _plan(parent: Path, child: Path) -> QualifiedNativeChildAdditionPlan:
    project = _project(parent)
    child = child if child.is_absolute() else project.root / child
    require_native_project_path(project, child / "literate.project.json")
    if child.is_symlink() or child.parent != project.root / ".literate/native-projects":
        _refuse("unsafe_child", "the child must be a direct native-project directory")
    registry_path = project.root / NATIVE_PROJECTS_FILE
    registry_bytes = _read(registry_path)
    parent_definition = _read(project.root / "literate.project.json")
    store = FilesystemConversionAuthorityStore(project.root)
    state = store.load_optional()
    if state is None:
        _refuse("parent_authority_missing", "the parent has no conversion authority")
    if state.project_id != project.definition.project_id:
        _refuse(
            "parent_identity_invalid", "the parent authority belongs to another project"
        )
    prior_evidence = require_current_qualified_conversion_authority(project, state)
    receipt = _current_receipt_identity(project)
    roots = _native_project_roots(project)
    candidate = load_project(child)
    definition = _read(child / "literate.project.json")
    entries = json.loads(registry_bytes)["projects"]
    if (
        candidate.definition.project_id == project.definition.project_id
        or any(item["project_id"] == project.definition.project_id for item in entries)
        or child in roots
        or any(
            item["project_id"] == candidate.definition.project_id for item in entries
        )
    ):
        _refuse(
            "collision", "the child path or project identifier is already registered"
        )
    coordinates = set()
    for root in (project.root, *roots, child):
        for coordinate in FileAuthorityProjectionStore(root).coordinates():
            if coordinate in coordinates:
                _refuse(
                    "collision", "a component coordinate occurs in multiple projects"
                )
            coordinates.add(coordinate)
    evidence = evidence_for_conversion_stage(
        candidate, ConversionAuthorityStage.QUALIFIED
    )
    authorities = FileAuthorityProjectionStore(child)
    heads = tuple(
        sorted(
            (
                authorities.current(coordinate).identity
                for coordinate in authorities.coordinates()
            ),
            key=lambda value: value.uri,
        )
    )
    result = QualifiedNativeChildAdditionPlan(
        parent_definition=canonical_identity(json.loads(parent_definition)),
        parent_authority=state.identity,
        parent_receipt=receipt,
        registry=_identity(registry_bytes),
        child=child.relative_to(project.root).as_posix(),
        child_project_id=candidate.definition.project_id,
        child_definition=canonical_identity(json.loads(definition)),
        child_authorities=heads,
        child_evidence=tuple(sorted(evidence, key=lambda value: value.uri)),
        expected_evidence=tuple(
            sorted(set((*prior_evidence, *evidence)), key=lambda value: value.uri)
        ),
    )
    if (
        _read(registry_path) != registry_bytes
        or _read(project.root / "literate.project.json") != parent_definition
        or _read(child / "literate.project.json") != definition
        or store.load_optional() != state
    ):
        _refuse("inputs_changed", "project metadata changed during planning")
    return result


def _journal(project, plan, registry_before, authority_before):
    base = project.root / _JOURNALS
    require_native_project_path(project, base)
    ensure_safe_directory(base)
    directory = Path(tempfile.mkdtemp(prefix=plan.identity.digest + "-", dir=base))
    path = directory / "journal.json"
    state = _renewed(authority_before, plan)
    document = {
        "schema": _JOURNAL_SCHEMA,
        "status": "prepared",
        "plan": plan.to_dict(),
        "registry_before": base64.b64encode(registry_before).decode("ascii"),
        "authority_before": base64.b64encode(authority_before).decode("ascii"),
        "registry_after": base64.b64encode(
            _registration_content(registry_before, plan)
        ).decode("ascii"),
        "authority_after": base64.b64encode(
            canonical_json_bytes(state.to_dict()) + b"\n"
        ).decode("ascii"),
    }
    content = canonical_json_bytes(document) + b"\n"
    if len(content) > _MAXIMUM_JOURNAL_BYTES:
        _refuse("journal_limit", "the recovery journal exceeds its metadata bound")
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return path, document


def _payload(document, name):
    return base64.b64decode(document[name], validate=True)


def _status(project, path, document, status):
    current = _read(path, maximum_bytes=_MAXIMUM_JOURNAL_BYTES)
    observed = json.loads(current)
    if not isinstance(observed, dict):
        _refuse("journal_invalid", "the addition journal must be an object")
    if {key: value for key, value in observed.items() if key != "status"} != {
        key: value for key, value in document.items() if key != "status"
    } or observed.get("status") not in {
        "prepared",
        "applied",
        "rolled_back",
        "recovered",
    }:
        _refuse(
            "journal_invalid",
            "the addition journal changed before recording its outcome",
        )
    updated = {**document, "status": status}
    _replace_metadata(
        project,
        path,
        current,
        canonical_json_bytes(updated) + b"\n",
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
            _refuse(
                "recovery_conflict",
                "metadata changed outside this reviewed transaction",
            )
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
        _refuse("journal_invalid", "recovery requires an owned addition journal")
    content = _read(path, maximum_bytes=_MAXIMUM_JOURNAL_BYTES)
    document = json.loads(content)
    if not isinstance(document, dict):
        _refuse("journal_invalid", "the addition journal must be an object")
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
        set(document) != fields
        or document["schema"] != _JOURNAL_SCHEMA
        or document["status"] not in {"prepared", "applied", "rolled_back", "recovered"}
        or canonical_json_bytes(document) + b"\n" != content
        or (os.name != "nt" and stat.S_IMODE(path.stat().st_mode) & 0o077)
    ):
        _refuse("journal_invalid", "the addition journal is changed or unsafe")
    plan = QualifiedNativeChildAdditionPlan.from_dict(document["plan"])
    if not path.parent.name.startswith(plan.identity.digest + "-"):
        _refuse("journal_invalid", "the journal directory does not match its plan")
    registry_before = _payload(document, "registry_before")
    authority_before = _payload(document, "authority_before")
    state = _renewed(authority_before, plan)
    if (
        _identity(registry_before) != plan.registry
        or state.project_id != project.definition.project_id
        or _registration_content(registry_before, plan)
        != _payload(document, "registry_after")
        or canonical_json_bytes(state.to_dict()) + b"\n"
        != _payload(document, "authority_after")
        or canonical_identity(json.loads(_read(project.root / "literate.project.json")))
        != plan.parent_definition
        or _current_receipt_identity(project) != plan.parent_receipt
    ):
        _refuse(
            "journal_invalid",
            "the journal or current parent no longer matches the plan",
        )
    store = FilesystemConversionAuthorityStore(project.root)
    registry_current = _read(project.root / NATIVE_PROJECTS_FILE)
    authority_current = _read(store.path)
    if registry_current not in (
        registry_before,
        _payload(document, "registry_after"),
    ) or authority_current not in (
        authority_before,
        _payload(document, "authority_after"),
    ):
        _refuse(
            "recovery_conflict", "metadata changed outside this reviewed transaction"
        )
    expected_current = (
        plan.expected_evidence
        if registry_current == _payload(document, "registry_after")
        else ConversionAuthorityState.from_dict(
            json.loads(authority_before)
        ).evidence_identities
    )
    actual_current = evidence_for_conversion_stage(
        project, ConversionAuthorityStage.QUALIFIED
    )
    child = project.root / plan.child
    require_native_project_path(project, child / "literate.project.json")
    candidate = load_project(child)
    heads = FileAuthorityProjectionStore(child)
    current_heads = tuple(
        sorted(
            (heads.current(coordinate).identity for coordinate in heads.coordinates()),
            key=lambda value: value.uri,
        )
    )
    if (
        tuple(sorted(actual_current, key=lambda value: value.uri)) != expected_current
        or canonical_identity(json.loads(_read(child / "literate.project.json")))
        != plan.child_definition
        or current_heads != plan.child_authorities
        or tuple(
            sorted(
                evidence_for_conversion_stage(
                    candidate, ConversionAuthorityStage.QUALIFIED
                ),
                key=lambda value: value.uri,
            )
        )
        != plan.child_evidence
    ):
        _refuse(
            "recovery_conflict",
            "qualification or child authority changed after publication",
        )
    return path, document


class FilesystemNativeChildAdditionAdapter:
    def plan(self, parent: Path, child: Path) -> QualifiedNativeChildAdditionPlan:
        return _plan(parent, child)

    def apply(
        self, parent: Path, plan: QualifiedNativeChildAdditionPlan
    ) -> dict[str, object]:
        project = _project(parent)
        store = FilesystemConversionAuthorityStore(project.root)
        registry = project.root / NATIVE_PROJECTS_FILE
        require_native_project_path(project, registry)
        try:
            with exclusive_cache_lock(registry.with_suffix(".lock")):
                with exclusive_cache_lock(store.lock_path):
                    if _plan(project.root, project.root / plan.child) != plan:
                        _refuse("plan_changed", "the reviewed addition plan is stale")
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
            raise NativeChildAdditionError(
                "locked", "native child publication is already locked"
            ) from exc

    def recover(self, parent: Path, journal: Path) -> dict[str, object]:
        project = _project(parent)
        store = FilesystemConversionAuthorityStore(project.root)
        registry = project.root / NATIVE_PROJECTS_FILE
        require_native_project_path(project, registry)
        try:
            with exclusive_cache_lock(registry.with_suffix(".lock")):
                with exclusive_cache_lock(store.lock_path):
                    path, document = _read_journal(project, journal)
                    if document["status"] != "prepared":
                        suffix = (
                            "after" if document["status"] == "applied" else "before"
                        )
                        if _read(registry) != _payload(
                            document, "registry_" + suffix
                        ) or _read(store.path) != _payload(
                            document, "authority_" + suffix
                        ):
                            _refuse(
                                "recovery_conflict",
                                "completed journal metadata changed",
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
            raise NativeChildAdditionError(
                "locked", "native child recovery is already locked"
            ) from exc
