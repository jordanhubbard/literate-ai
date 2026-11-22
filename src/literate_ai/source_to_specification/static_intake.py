"""Signed permission for exact, local-only static source analysis."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar

from literate_ai.contracts import ContentIdentity
from literate_ai.contracts.paths import (
    canonical_relative_posix_path,
    canonical_relative_posix_paths,
)

from .attestation import (
    LocalSourceAttestation,
    _canonical_bytes,
    _key_id,
    _require_strong_key,
    verify_source_attestation,
)
from .contracts import canonical_digest
from .errors import SourceToSpecificationError
from .inventory import (
    _GENERIC_SYMBOL,
    SourceInventory,
    SourceInventoryEntry,
    _classify,
    _signals,
    inventory_source,
)

PURPOSE = "local-static-intake"
MAXIMUM_REVIEW_BYTES = 64 * 1024
MAXIMUM_SOURCE_BYTES = 2 * 1024 * 1024
_PRIVATE_KEY = re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")


def _invalid(message: str) -> SourceToSpecificationError:
    return SourceToSpecificationError("intake_review.invalid", message)


def _identity(value: str) -> str:
    try:
        if not isinstance(value, str):
            raise ValueError("identity must be text")
        return ContentIdentity.parse_uri(value).uri
    except (TypeError, ValueError) as error:
        raise _invalid(
            "review identity must be a canonical content identity"
        ) from error


def _text(value: str, maximum: int, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise _invalid(f"{label} must be bounded nonempty text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise _invalid(f"{label} must be valid UTF-8 text") from error


def _fields(value: Any, expected: set[str], schema: str | None = None) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise _invalid("review document fields are invalid")
    if schema is not None and value["schema"] != schema:
        raise _invalid("review document schema is invalid")


@dataclass(frozen=True, slots=True)
class StaticIntakeFile:
    """Metadata only; never original source or a credential match."""

    path: str
    content_identity: str
    byte_count: int
    language: str
    original_classification: str
    reason: str

    def __post_init__(self) -> None:
        _text(self.path, 4096, "review source path")
        try:
            canonical_relative_posix_path(self.path, label="static intake source")
        except (TypeError, ValueError) as error:
            raise _invalid(
                "review path must be a canonical relative source path"
            ) from error
        _identity(self.content_identity)
        if (
            type(self.byte_count) is not int
            or not 0 <= self.byte_count <= MAXIMUM_SOURCE_BYTES
        ):
            raise _invalid("review source size is invalid")
        if not isinstance(self.language, str) or self.language not in {
            "javascript",
            "typescript",
        }:
            raise _invalid("review supports JavaScript and TypeScript source only")
        if not isinstance(
            self.original_classification, str
        ) or self.original_classification not in {"source", "sensitive"}:
            raise _invalid("review cannot admit this source class")
        _text(self.reason, 512, "file review reason")

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, value: Any) -> StaticIntakeFile:
        _fields(value, set(cls.__dataclass_fields__))
        return cls(**value)


def _files(value: tuple[StaticIntakeFile, ...]) -> None:
    if (
        not isinstance(value, tuple)
        or not 1 <= len(value) <= 32
        or any(not isinstance(item, StaticIntakeFile) for item in value)
    ):
        raise _invalid("review requires one to 32 typed source files")
    paths = tuple(item.path for item in value)
    if paths != tuple(sorted(set(paths))):
        raise _invalid("review source paths must be sorted and unique")
    try:
        canonical_relative_posix_paths(paths, label="static intake source")
    except (TypeError, ValueError) as error:
        raise _invalid("review source paths collide") from error


@dataclass(frozen=True, slots=True)
class StaticIntakePlan:
    schema: ClassVar[str] = "literate-ai/source-static-intake-plan@1"
    source_snapshot_id: str
    origin_attestation_id: str
    files: tuple[StaticIntakeFile, ...]

    def __post_init__(self) -> None:
        _identity(self.source_snapshot_id)
        _identity(self.origin_attestation_id)
        _files(self.files)

    def payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "purpose": PURPOSE,
            "source_snapshot_id": self.source_snapshot_id,
            "origin_attestation_id": self.origin_attestation_id,
            "files": [item.to_dict() for item in self.files],
        }

    @property
    def identity(self) -> str:
        return canonical_digest(self.payload())

    def to_dict(self) -> dict[str, Any]:
        value = {**self.payload(), "identity": self.identity}
        if len(_canonical_bytes(value)) > MAXIMUM_REVIEW_BYTES:
            raise _invalid("static intake plan exceeds its metadata budget")
        return value

    @classmethod
    def from_dict(cls, value: Any) -> StaticIntakePlan:
        _fields(
            value,
            {
                "schema",
                "purpose",
                "source_snapshot_id",
                "origin_attestation_id",
                "files",
                "identity",
            },
            cls.schema,
        )
        if value["purpose"] != PURPOSE or not isinstance(value["files"], list):
            raise _invalid("static intake plan purpose or file set is invalid")
        plan = cls(
            value["source_snapshot_id"],
            value["origin_attestation_id"],
            tuple(StaticIntakeFile.from_dict(item) for item in value["files"]),
        )
        if value["identity"] != plan.identity:
            raise _invalid("static intake plan identity is invalid")
        return plan


@dataclass(frozen=True, slots=True)
class StaticIntakeReview:
    schema: ClassVar[str] = "literate-ai/source-static-intake-review@1"
    source_snapshot_id: str
    origin_attestation_id: str
    plan_identity: str
    files: tuple[StaticIntakeFile, ...]
    actor: str
    authority: str
    reason: str
    key_id: str
    signature: str

    def __post_init__(self) -> None:
        for value in (
            self.source_snapshot_id,
            self.origin_attestation_id,
            self.plan_identity,
            self.key_id,
        ):
            _identity(value)
        _files(self.files)
        _text(self.actor, 256, "review actor")
        _text(self.reason, 2048, "review reason")
        if not isinstance(self.authority, str) or self.authority not in {
            "human",
            "authorized-policy",
        }:
            raise _invalid("review authority must be explicit")
        if not isinstance(self.signature, str) or not re.fullmatch(
            r"hmac-sha256:[0-9a-f]{64}", self.signature
        ):
            raise _invalid("review signature is invalid")
        plan = StaticIntakePlan(
            self.source_snapshot_id, self.origin_attestation_id, self.files
        )
        if plan.identity != self.plan_identity:
            raise _invalid("review does not bind its exact source plan")

    def payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "purpose": PURPOSE,
            "algorithm": "hmac-sha256",
            "source_snapshot_id": self.source_snapshot_id,
            "origin_attestation_id": self.origin_attestation_id,
            "plan_identity": self.plan_identity,
            "files": [item.to_dict() for item in self.files],
            "actor": self.actor,
            "authority": self.authority,
            "reason": self.reason,
            "key_id": self.key_id,
        }

    def to_dict(self) -> dict[str, Any]:
        value = {**self.payload(), "signature": self.signature}
        if len(_canonical_bytes(value)) > MAXIMUM_REVIEW_BYTES:
            raise _invalid("review exceeds its metadata budget")
        return value

    @property
    def identity(self) -> str:
        return canonical_digest(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> StaticIntakeReview:
        _fields(
            value,
            {
                "schema",
                "purpose",
                "algorithm",
                "source_snapshot_id",
                "origin_attestation_id",
                "plan_identity",
                "files",
                "actor",
                "authority",
                "reason",
                "key_id",
                "signature",
            },
            cls.schema,
        )
        if (
            value["purpose"] != PURPOSE
            or value["algorithm"] != "hmac-sha256"
            or not isinstance(value["files"], list)
        ):
            raise _invalid("review purpose, algorithm or file set is invalid")
        result = cls(
            **{
                name: value[name]
                for name in cls.__dataclass_fields__
                if name != "schema" and name != "files"
            },
            files=tuple(StaticIntakeFile.from_dict(item) for item in value["files"]),
        )
        result.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class StaticIntakeValidation:
    """Private qualification binding; this record is not a signature attestation."""

    schema: ClassVar[str] = "literate-ai/source-static-intake-validation@1"
    source_snapshot_id: str
    promotion_reference_id: str
    review_identity: str
    qualification_result_id: str
    trust_key_id: str

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if name != "schema":
                _identity(getattr(self, name))

    def to_dict(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "purpose": PURPOSE,
            **{
                name: getattr(self, name)
                for name in self.__dataclass_fields__
                if name != "schema"
            },
        }

    @property
    def identity(self) -> str:
        return canonical_digest(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> StaticIntakeValidation:
        _fields(
            value,
            {
                "schema",
                "purpose",
                "source_snapshot_id",
                "promotion_reference_id",
                "review_identity",
                "qualification_result_id",
                "trust_key_id",
            },
            cls.schema,
        )
        if value["purpose"] != PURPOSE:
            raise _invalid("static intake validation purpose is invalid")
        return cls(
            **{
                name: value[name]
                for name in cls.__dataclass_fields__
                if name != "schema"
            }
        )


def sign_static_intake_review(
    plan: StaticIntakePlan, *, actor: str, authority: str, reason: str, key: bytes
) -> StaticIntakeReview:
    _require_strong_key(key)
    fields = dict(
        source_snapshot_id=plan.source_snapshot_id,
        origin_attestation_id=plan.origin_attestation_id,
        plan_identity=plan.identity,
        files=plan.files,
        actor=actor,
        authority=authority,
        reason=reason,
        key_id=_key_id(key),
    )
    unsigned = StaticIntakeReview(**fields, signature="hmac-sha256:" + "0" * 64)
    signature = (
        "hmac-sha256:"
        + hmac.new(
            key, _canonical_bytes(unsigned.payload()), hashlib.sha256
        ).hexdigest()
    )
    result = StaticIntakeReview(**fields, signature=signature)
    result.to_dict()
    return result


def verify_static_intake_signature(
    review: StaticIntakeReview, *, key: bytes, allow_authorized_policy: bool = False
) -> None:
    if (
        not isinstance(review, StaticIntakeReview)
        or type(allow_authorized_policy) is not bool
    ):
        raise _invalid(
            "signature verification requires a typed review and explicit policy"
        )
    _require_strong_key(key)
    if review.authority == "authorized-policy" and not allow_authorized_policy:
        raise SourceToSpecificationError(
            "intake_review.policy_not_authorized",
            "policy intake review requires separate caller opt-in",
        )
    if review.key_id != _key_id(key):
        raise SourceToSpecificationError(
            "intake_review.trust_mismatch", "intake review uses another trust key"
        )
    expected = (
        "hmac-sha256:"
        + hmac.new(key, _canonical_bytes(review.payload()), hashlib.sha256).hexdigest()
    )
    if not hmac.compare_digest(review.signature, expected):
        raise SourceToSpecificationError(
            "intake_review.signature_invalid", "intake review signature is invalid"
        )


def create_static_intake_plan(
    source: str | Path,
    *,
    inventory: SourceInventory,
    attestation: LocalSourceAttestation,
    paths: tuple[str, ...],
    key: bytes,
) -> StaticIntakePlan:
    """Observe exact eligible source without changing inventory or running code."""
    verify_source_attestation(
        attestation, expected_source_snapshot_id=inventory.identity, key=key
    )
    files = _reviewed_static_files(source, inventory=inventory, paths=paths)
    return StaticIntakePlan(inventory.identity, attestation.identity, files)


def _reviewed_static_files(
    source: str | Path, *, inventory: SourceInventory, paths: tuple[str, ...]
) -> tuple[StaticIntakeFile, ...]:
    from .promotion_materialization import _read_regular_file, _require_direct_directory

    if (
        not isinstance(paths, tuple)
        or not 1 <= len(paths) <= 32
        or not all(isinstance(name, str) for name in paths)
        or paths != tuple(sorted(set(paths)))
    ):
        raise _invalid(
            "review paths must be a sorted explicit unique set of one to 32 files"
        )
    configured = Path(source).absolute()
    root = _require_direct_directory(
        configured if configured.is_dir() else configured.parent,
        label="static intake source",
    )
    entries = {entry.path: entry for entry in inventory.entries}
    selected = []
    for name in paths:
        _text(name, 4096, "review source path")
        try:
            relative = canonical_relative_posix_path(name, label="static intake source")
        except (TypeError, ValueError) as error:
            raise _invalid("review path is invalid") from error
        entry = entries.get(name)
        if entry is None or entry.language not in {"javascript", "typescript"}:
            raise _invalid("review path is absent or has an unsupported language")
        content = _read_regular_file(
            root, PurePosixPath(relative), max_bytes=MAXIMUM_SOURCE_BYTES
        )
        if (
            len(content) != entry.size
            or "sha256:" + hashlib.sha256(content).hexdigest() != entry.content_digest
        ):
            raise SourceToSpecificationError(
                "intake_review.source_drift",
                "review source differs from the original inventory",
            )
        if _PRIVATE_KEY.search(content):
            raise _invalid("private key material remains ineligible for review")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise _invalid("review source must be valid UTF-8 text") from error
        classification, language, _ = _classify(
            name, content, entry.size, _reviewed_credential_content=True
        )
        if classification.value != "source":
            raise _invalid("review cannot admit a hard-excluded source class")
        selected.append(
            StaticIntakeFile(
                name,
                entry.content_digest,
                entry.size,
                language,
                entry.classification.value,
                "Explicit review of exact source for local static analysis only",
            )
        )
    _require_direct_directory(root, label="static intake source")
    if inventory_source(source).identity != inventory.identity:
        raise SourceToSpecificationError(
            "intake_review.source_drift", "source changed during static intake planning"
        )
    return tuple(selected)


def verify_static_intake_source_binding(
    review: StaticIntakeReview, source: str | Path, *, inventory: SourceInventory
) -> None:
    """Recheck the unchanged source and hard exclusions during qualification."""
    if review.source_snapshot_id != inventory.identity:
        raise SourceToSpecificationError(
            "intake_review.source_mismatch", "review names another source snapshot"
        )
    files = _reviewed_static_files(
        source, inventory=inventory, paths=tuple(item.path for item in review.files)
    )
    if files != review.files:
        raise SourceToSpecificationError(
            "intake_review.source_mismatch",
            "review does not bind the current exact eligible files",
        )


def verify_static_intake_review(
    review: StaticIntakeReview,
    source: str | Path,
    *,
    inventory: SourceInventory,
    attestation: LocalSourceAttestation,
    key: bytes,
    allow_authorized_policy: bool = False,
) -> StaticIntakePlan:
    verify_static_intake_signature(
        review, key=key, allow_authorized_policy=allow_authorized_policy
    )
    plan = create_static_intake_plan(
        source,
        inventory=inventory,
        attestation=attestation,
        paths=tuple(item.path for item in review.files),
        key=key,
    )
    if plan.identity != review.plan_identity or plan.files != review.files:
        raise SourceToSpecificationError(
            "intake_review.source_mismatch",
            "intake review does not bind the current source and origin",
        )
    return plan


def reviewed_static_entries(
    review: StaticIntakeReview,
    source: str | Path,
    *,
    inventory: SourceInventory,
    attestation: LocalSourceAttestation,
    key: bytes,
    allow_authorized_policy: bool = False,
) -> dict[str, SourceInventoryEntry]:
    """Return lexical views only; never construct an inventory from these entries."""
    from .promotion_materialization import _read_regular_file, _require_direct_directory

    verify_static_intake_review(
        review,
        source,
        inventory=inventory,
        attestation=attestation,
        key=key,
        allow_authorized_policy=allow_authorized_policy,
    )
    configured = Path(source).absolute()
    root = _require_direct_directory(
        configured if configured.is_dir() else configured.parent,
        label="static intake source",
    )
    original = {entry.path: entry for entry in inventory.entries}
    result = {}
    for file in review.files:
        entry = original[file.path]
        content = _read_regular_file(
            root, PurePosixPath(file.path), max_bytes=MAXIMUM_SOURCE_BYTES
        )
        if (
            len(content) != file.byte_count
            or "sha256:" + hashlib.sha256(content).hexdigest() != file.content_identity
        ):
            raise SourceToSpecificationError(
                "intake_review.source_drift",
                "source changed before reviewed static analysis",
            )
        text = content.decode("utf-8")
        result[file.path] = replace(
            entry,
            symbols=tuple(sorted(set(_GENERIC_SYMBOL.findall(text)))),
            flavor_signals=_signals(file.path, text, file.language),
        )
    verify_static_intake_review(
        review,
        source,
        inventory=inventory,
        attestation=attestation,
        key=key,
        allow_authorized_policy=allow_authorized_policy,
    )
    return result


def read_static_intake_document(
    path: str | Path, *, maximum_bytes: int = MAXIMUM_REVIEW_BYTES
) -> dict[str, Any]:
    """Read bounded direct metadata and reject duplicate JSON object fields."""
    from .promotion_materialization import _read_regular_file, _require_direct_directory

    selected = Path(path).absolute()
    if type(maximum_bytes) is not int or not 0 < maximum_bytes <= 16 * 1024 * 1024:
        raise _invalid("static intake metadata read budget is invalid")
    root = _require_direct_directory(selected.parent, label="static intake metadata")
    content = _read_regular_file(
        root, PurePosixPath(selected.name), max_bytes=maximum_bytes
    )
    _require_direct_directory(root, label="static intake metadata")

    return _parse_static_intake_json(content)


def _parse_static_intake_json(
    content: bytes, *, unwrap_cli: bool = True
) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, value in items:
            if name in result:
                raise _invalid("review metadata contains duplicate JSON fields")
            result[name] = value
        return result

    def constant(_value: str) -> None:
        raise _invalid("review metadata contains a non-finite JSON constant")

    try:
        value = json.loads(
            content.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise _invalid("review metadata must be bounded UTF-8 JSON") from error
    if (
        unwrap_cli
        and isinstance(value, dict)
        and value.get("schema") == "literate-ai/cli-result@1"
    ):
        _fields(value, {"schema", "command", "ok", "result"})
        if value["ok"] is not True or not isinstance(value["command"], str):
            raise _invalid("review metadata CLI envelope is invalid")
        value = value["result"]
    if not isinstance(value, dict):
        raise _invalid("review metadata must be one JSON object")
    return value


def require_static_intake_source(source: str | Path) -> Path:
    """Check configured source ancestors before performing its inventory."""
    from .promotion_materialization import _require_direct_directory

    selected = Path(source).absolute()
    if selected.is_symlink():
        raise _invalid("static intake source cannot be a symbolic link")
    _require_direct_directory(
        selected if selected.is_dir() else selected.parent, label="static intake source"
    )
    return selected


def read_static_intake_key(path: str | Path) -> bytes:
    """Read the caller's existing trust key without exposing or retaining it."""
    from .promotion_materialization import _read_regular_file, _require_direct_directory

    selected = Path(path).absolute()
    root = _require_direct_directory(selected.parent, label="static intake trust key")
    key = _read_regular_file(
        root, PurePosixPath(selected.name), max_bytes=MAXIMUM_REVIEW_BYTES
    )
    _require_direct_directory(root, label="static intake trust key")
    _require_strong_key(key)
    return key


def write_new_static_intake_review(
    path: str | Path, review: StaticIntakeReview
) -> None:
    """Use the existing immutable-projection publisher for one new review file."""
    value = _write_new_static_intake_metadata(path, review.to_dict())
    if StaticIntakeReview.from_dict(value) != review:
        raise SourceToSpecificationError(
            "intake_review.output_changed",
            "published review changed before closing validation",
        )


def write_new_static_intake_validation(
    path: str | Path, validation: StaticIntakeValidation
) -> None:
    """Persist one exact measured validation without replacing another record."""
    value = _write_new_static_intake_metadata(path, validation.to_dict())
    if StaticIntakeValidation.from_dict(value) != validation:
        raise SourceToSpecificationError(
            "intake_review.output_changed",
            "published validation changed before closing verification",
        )


def _write_new_static_intake_metadata(
    path: str | Path, value: dict[str, Any]
) -> dict[str, Any]:
    from literate_ai.adapters.authority import (
        AuthorityProjectionStoreError,
        FileAuthorityProjectionStore,
    )

    from .promotion_materialization import _require_direct_directory

    selected = Path(path).absolute()
    _require_direct_directory(selected.parent, label="static intake review output")
    serialized = _canonical_bytes(value) + b"\n"
    if len(serialized) > MAXIMUM_REVIEW_BYTES:
        raise _invalid("review output exceeds its metadata budget")
    try:
        FileAuthorityProjectionStore._atomic_write(selected, serialized, exclusive=True)
    except (OSError, AuthorityProjectionStoreError) as error:
        raise SourceToSpecificationError(
            "intake_review.output_conflict",
            "review output must be a new regular file in a direct directory",
        ) from error
    _require_direct_directory(selected.parent, label="static intake review output")
    return read_static_intake_document(selected)
