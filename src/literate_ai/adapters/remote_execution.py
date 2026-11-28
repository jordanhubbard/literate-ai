"""Worker-side execution of one exact, already-selected lifecycle request."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tarfile
import tempfile
import time
import uuid
import zipfile
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    ensure_safe_directory,
    path_is_link_or_reparse,
    require_safe_directory,
)
from literate_ai.adapters._processes import run_with_tree_kill
from literate_ai.adapters.directory_artifacts import (
    directory_export_bytes,
    require_library_package,
    require_transported_library_package,
)
from literate_ai.adapters.project_runtime import (
    ContainedProjectRuntime,
    allocate_project_runtime,
    close_project_runtime,
    require_project_runtime,
    require_runtime_candidate,
)
from literate_ai.adapters.user_paths import prepare_user_directory, resolve_host_paths
from literate_ai.adapters.worker_capabilities import probe_worker_capabilities
from literate_ai.cache_directories import (
    CacheDirectories,
    bind_cache_directories,
    resolve_cache_directories,
)
from literate_ai.contracts import (
    MAX_REMOTE_CONTROL_SUMMARY_BYTES,
    MAX_REMOTE_EVIDENCE_MANIFEST_BYTES,
    ContentIdentity,
    ContentReference,
    DispatchResultStatus,
    ExecutionDispatchRequest,
    ExecutionDispatchResult,
    ExecutionSourceMaterialization,
    ExecutionWorker,
    ExecutionWorkerKind,
    HashAlgorithm,
    LifecycleDispatchAction,
    ObservedExecutionEnvironment,
    RemoteEvidenceFile,
    RemoteFailureDiagnostic,
    RemoteLifecycleEvidenceManifest,
    canonical_identity,
    canonical_json_bytes,
    coordinator_evidence_import_identity,
)
from literate_ai.contracts.library_products import (
    LibraryArtifactProduct,
    library_worker_manifest,
)
from literate_ai.diagnostics import inherited_verbose_environment, trace_subprocess
from literate_ai.projects import ProjectConfigurationStore, load_project
from literate_ai.remote_source_guard import (
    SourceGuardError,
    extract_accepted_source_cache_archive,
    extract_source_archive_with_manifest,
    source_tree_identity,
    verify_materialized_source,
)

from .artifact_exports import ArtifactEntrypointCommand, ArtifactExportError
from .evidence_archive import write_evidence_archive
from .evidence_files import EvidenceFileLimit, copy_evidence_files
from .evidence_staging import EvidenceStagingError, evidence_staging
from .remote_cleanup import (
    INTENT_PATH,
    acknowledge_cleanup,
    capture_cleanup_intent,
    hold_cleanup_root,
    write_cleanup_ticket,
)

_CAS_SCHEME = "litai-worker-cas"
_EVIDENCE_URI = "staged:remote-evidence.tar.gz"
_MAX_EVIDENCE_FILES = 50_000
_MAX_EVIDENCE_BYTES = 8 * 1024 * 1024 * 1024
_SECRET = re.compile(
    r"(?i)(authorization|cookie|credential|password|secret|token)"
    r"([\"'\s:=]+)([^\s,\"']+)"
)
_WINDOWS_PATH = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:\\[^\r\n\t\"']+")
_POSIX_PATH = re.compile(r"(?<![A-Za-z0-9_.-])/(?:[^/\s\"']+/)+[^/\s\"']*")


class RemoteExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True, slots=True)
class RemoteLifecycleCustody:
    """Exact short-root directory custody for one worker lifecycle attempt."""

    attempt_root: Path
    cache_directories: CacheDirectories
    runtime_root: Path
    candidate_receipt: Path
    project_runtime: ContainedProjectRuntime | None = field(
        default=None, repr=False, compare=False
    )
    _runtime_identity: ContentIdentity | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.project_runtime is not None:
            project = load_project(self.cache_directories.project_root)
            require_project_runtime(self.project_runtime, project)
            require_runtime_candidate(
                self.project_runtime, project, self.candidate_receipt
            )
            if (
                self.runtime_root != self.project_runtime.path
                or self.cache_directories.obj_dir != self.project_runtime.object_root
            ):
                raise ValueError(
                    "worker paths differ from original live runtime custody"
                )
            object.__setattr__(self, "_runtime_identity", self.project_runtime.identity)
        root = self.attempt_root.resolve(strict=True)
        paths = (
            self.cache_directories.build_dir,
            self.cache_directories.obj_dir,
            self.runtime_root,
            self.candidate_receipt,
        )
        if any(not Path(path).resolve().is_relative_to(root) for path in paths):
            raise ValueError(
                "worker lifecycle custody must remain below its attempt root"
            )

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(
            {
                "schema": "literate-ai/remote-lifecycle-directory-custody@1",
                "attempt_root": str(self.attempt_root),
                "cache_directory_custody_identity": (
                    self.cache_directories.identity.uri
                ),
                "runtime_root": str(self.runtime_root),
                "candidate_receipt": str(self.candidate_receipt),
                **(
                    {"project_runtime_custody_identity": self._runtime_identity.uri}
                    if self._runtime_identity is not None
                    else {}
                ),
            }
        )


class _RemoteRuntimeLifetime(ExitStack):
    """Actual caller lifetime through evidence; never transport/deserialized data."""

    def __init__(self):
        super().__init__()
        self.cleanup_safe = True

    def retire(self, owner, keep):
        try:
            if close_project_runtime(owner, keep=keep) is False:
                self.cleanup_safe = False
        except BaseException:
            self.cleanup_safe = False
            raise


def _default_remote_custody(root, attempt_root, lifetime, *, keep):
    context = ProjectConfigurationStore.context(root)
    require_safe_directory(context.framework_root / "_build", allow_missing=True)
    directories = resolve_cache_directories(root, environment={})
    if context.framework_root == root:
        return RemoteLifecycleCustody(
            attempt_root,
            directories,
            attempt_root / "lifecycle-runtime",
            attempt_root / "candidate-receipt.json",
        )
    owner = allocate_project_runtime(load_project(root), nested=True)
    lifetime.callback(lifetime.retire, owner, keep)
    return RemoteLifecycleCustody(
        attempt_root,
        bind_cache_directories(
            root, build_dir=directories.build_dir, obj_dir=owner.object_root
        ),
        owner.path,
        owner.candidate_receipt,
        owner,
    )


class RemoteLifecycleRebuilder(Protocol):
    """CLI-independent port for one worker-local Standard lifecycle rebuild."""

    def __call__(
        self,
        *,
        component_path: str,
        project_root: Path,
        custody: RemoteLifecycleCustody,
        flavor_selectors: tuple[str, ...],
        target_profile: str,
        model_selector: str | None,
        accepted_source_only: bool,
        accepted_source_provider_id: str | None,
        accepted_source_provider_identity: ContentIdentity | None,
        jobs: int,
        source_cache_entry_identities: tuple[ContentIdentity, ...] = (),
    ) -> dict[str, object]: ...


def _evidence_budget(deadline_monotonic):
    if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
        raise RemoteExecutionError(
            "execution.remote_evidence_timeout", "Evidence verification budget expired"
        )


def _file_identity(
    path: Path, *, expected_size=None, deadline_monotonic=None
) -> ContentIdentity:
    _evidence_budget(deadline_monotonic)
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while True:
            _evidence_budget(deadline_monotonic)
            limit = (
                1024 * 1024
                if expected_size is None
                else min(1024 * 1024, expected_size - count + 1)
            )
            chunk = stream.read(limit)
            if not chunk:
                break
            count += len(chunk)
            if expected_size is not None and count > expected_size:
                raise RemoteExecutionError(
                    "execution.remote_evidence_file_mismatch",
                    "Imported blob size changed",
                )
            digest.update(chunk)
    if expected_size is not None and count != expected_size:
        raise RemoteExecutionError(
            "execution.remote_evidence_file_mismatch", "Imported blob size changed"
        )
    return ContentIdentity(HashAlgorithm.SHA256, digest.hexdigest())


def _directory_identity(path: Path) -> ContentIdentity:
    entries: list[dict[str, object]] = []
    for item in sorted(
        path.rglob("*"), key=lambda candidate: candidate.relative_to(path).as_posix()
    ):
        if item.is_symlink() or (not item.is_file() and not item.is_dir()):
            raise RemoteExecutionError(
                "execution.remote_artifact_invalid",
                "accepted artifact contains an unsupported entry",
            )
        if item.is_file():
            entries.append(
                {
                    "path": item.relative_to(path).as_posix(),
                    "identity": _file_identity(item).uri,
                    "executable": bool(item.stat().st_mode & 0o111),
                }
            )
    return canonical_identity(
        {"schema": "literate-ai/worker-artifact-directory@1", "entries": entries}
    )


def _artifact_identity(path: Path) -> ContentIdentity:
    return _file_identity(path) if path.is_file() else _directory_identity(path)


def _artifact_reference(
    identity: ContentIdentity, execution_identity: ContentIdentity | None = None
) -> ContentReference:
    locator = identity.uri
    if execution_identity is not None:
        locator = f"{locator}/execution/{execution_identity.uri}"
    return ContentReference("artifact-export", f"{_CAS_SCHEME}:{locator}", identity)


def _cas_entry(
    root: Path,
    identity: ContentIdentity,
    execution_identity: ContentIdentity | None = None,
) -> Path:
    base = root / "artifacts" / identity.digest[:2] / identity.digest
    return base if execution_identity is None else base / execution_identity.digest


def _execution_manifest_identity(
    artifact_identity: ContentIdentity,
    argv: tuple[str, ...],
    environment: dict[str, str],
    toolchain_identities: tuple[ContentIdentity, ...],
    entrypoints: tuple[ArtifactEntrypointCommand, ...],
    *,
    artifact_path: Path,
) -> ContentIdentity:
    """Bind dispatch commands without binding a worker-private CAS pathname."""

    original = str(artifact_path)

    def portable(value: str) -> str:
        return value.replace(original, "{artifact}")

    command: dict[str, object] = {
        "argv": [portable(item) for item in argv],
        "environment": {
            name: portable(value) for name, value in sorted(environment.items())
        },
        "toolchain_identities": [item.to_dict() for item in toolchain_identities],
    }
    if entrypoints:
        command["entrypoints"] = [
            {
                "schema": item.to_dict()["schema"],
                "name": item.name,
                "kind": item.kind,
                "deployment_unit": item.deployment_unit,
                "argv": [portable(argument) for argument in item.argv],
                "environment": {
                    name: portable(value)
                    for name, value in sorted(item.environment.items())
                },
            }
            for item in entrypoints
        ]
        command["default_entrypoint"] = entrypoints[0].name
    return canonical_identity(
        {
            "schema": "literate-ai/worker-artifact-execution@1",
            "artifact_identity": artifact_identity.to_dict(),
            "command": command,
        }
    )


def _redact_diagnostic(value: object, *, limit: int = 8192) -> str:
    """Apply the explicit remote diagnostic redaction policy before transport."""

    text = str(value).replace("\x00", "")
    text = _SECRET.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text
    )
    text = _WINDOWS_PATH.sub("<private-path>", text)
    text = _POSIX_PATH.sub("<private-path>", text)
    return text[:limit] or "remote lifecycle failed without a public diagnostic"


def _failure_diagnostic(exc: Exception) -> RemoteFailureDiagnostic:
    cause = exc.__cause__
    stdout = getattr(exc, "stdout", None)
    stderr = getattr(exc, "stderr", None)
    if cause is not None:
        stdout = stdout or getattr(cause, "stdout", None)
        stderr = stderr or getattr(cause, "stderr", None)
    return RemoteFailureDiagnostic(
        code=_redact_diagnostic(
            getattr(exc, "code", "execution.remote_lifecycle_failed"), limit=256
        ),
        message=_redact_diagnostic(getattr(exc, "message", exc)),
        nested_code=(
            None
            if cause is None
            else _redact_diagnostic(
                getattr(cause, "code", type(cause).__name__), limit=256
            )
        ),
        nested_message=(
            None
            if cause is None
            else _redact_diagnostic(getattr(cause, "message", cause))
        ),
        stdout="" if stdout is None else _redact_diagnostic(stdout, limit=65536),
        stderr="" if stderr is None else _redact_diagnostic(stderr, limit=65536),
    )


def remote_control_summary(result: ExecutionDispatchResult) -> str:
    """Project one bounded redacted status summary into the SSH control channel."""

    selected = (
        result.stdout if result.status is DispatchResultStatus.PASSED else result.stderr
    )
    if not selected:
        return ""
    return _redact_diagnostic(selected, limit=MAX_REMOTE_CONTROL_SUMMARY_BYTES)


def _portable_result(value: object) -> object:
    """Project lifecycle output without worker-private paths or credential material."""

    if isinstance(value, dict):
        projected: dict[str, object] = {}
        for key, item in value.items():
            if key in {"artifact", "candidate_receipt", "runtime_root"}:
                continue
            projected[str(key)] = _portable_result(item)
        return projected
    if isinstance(value, list):
        return [_portable_result(item) for item in value]
    if isinstance(value, tuple):
        return [_portable_result(item) for item in value]
    if isinstance(value, str):
        return _redact_diagnostic(value, limit=65536)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RemoteExecutionError(
                "execution.remote_result_noncanonical",
                "worker lifecycle output contains a non-finite floating-point value",
            )
        decimal = Decimal(str(value))
        return {
            "encoding": "decimal-v1",
            "value": "0" if decimal.is_zero() else format(decimal.normalize(), "f"),
        }
    if isinstance(value, (bool, int)) or value is None:
        return value
    return _redact_diagnostic(value)


def _stage_identities(value: object) -> tuple[ContentIdentity, ...]:
    identities: set[ContentIdentity] = set()

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for nested in item.values():
                visit(nested)
        elif isinstance(item, (list, tuple)):
            for nested in item:
                visit(nested)
        elif isinstance(item, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", item):
            identities.add(ContentIdentity.parse_uri(item))

    visit(value)
    return tuple(sorted(identities, key=lambda item: item.uri))


def _evidence_kind(relative: str) -> str:
    first = relative.split("/", 1)[0]
    if first in {"source", "object", "binary", "package", "test", "receipt", "log"}:
        return first
    if first == "artifact":
        return "artifact"
    if first == "diagnostic":
        return "diagnostic"
    return "manifest"


def _copy_evidence_tree(
    source: Path,
    destination: Path,
    prefix: str,
    *,
    files: list[RemoteEvidenceFile],
    totals: list[int],
    _output_owner=None,
) -> None:
    try:
        copied = copy_evidence_files(
            source,
            destination,
            prefix,
            maximum_files=_MAX_EVIDENCE_FILES - len(files),
            maximum_bytes=_MAX_EVIDENCE_BYTES - totals[0],
            _output_owner=_output_owner,
        )
    except EvidenceFileLimit as exc:
        raise RemoteExecutionError(
            "execution.remote_evidence_too_large", str(exc)
        ) from exc
    except (ValueError, OSError, RuntimeError) as exc:
        raise RemoteExecutionError(
            "execution.remote_evidence_entry_invalid", str(exc)
        ) from exc
    for row in copied:
        files.append(
            RemoteEvidenceFile(
                row.relative,
                _evidence_kind(row.relative),
                row.size,
                ContentIdentity(HashAlgorithm.SHA256, row.digest),
                row.executable,
            )
        )
        totals[0] += row.size


def _write_deterministic_tar_gz(
    source: Path, destination: Path, *, expected=None, _source_owner=None
) -> ContentIdentity:
    return ContentIdentity(
        HashAlgorithm.SHA256,
        write_evidence_archive(
            source,
            destination,
            maximum_files=_MAX_EVIDENCE_FILES + 1,
            maximum_bytes=_MAX_EVIDENCE_BYTES + MAX_REMOTE_EVIDENCE_MANIFEST_BYTES,
            expected=expected,
            _source_owner=_source_owner,
        ),
    )


def _staged_evidence_file(row, kind):
    return RemoteEvidenceFile(
        row.relative,
        kind,
        row.size,
        ContentIdentity(HashAlgorithm.SHA256, row.digest),
        row.executable,
    )


def _write_remote_evidence(
    *,
    worker: ExecutionWorker,
    request: ExecutionDispatchRequest,
    materialization: ExecutionSourceMaterialization,
    result: ExecutionDispatchResult,
    lifecycle_result: dict[str, object] | None,
    failure: RemoteFailureDiagnostic | None,
    custody: RemoteLifecycleCustody | None,
    artifact: Path | None,
    output: Path,
    cleanup_token: str,
    cleanup_roots: tuple[object, ...],
    cleanup_ticket: Path,
) -> tuple[RemoteLifecycleEvidenceManifest, ContentReference, dict]:
    if custody is not None and custody.project_runtime is not None:
        project = load_project(custody.cache_directories.project_root)
        require_project_runtime(custody.project_runtime, project)
        staging_parent = custody.project_runtime.candidate_receipt.parent
    else:
        staging_parent = Path(resolve_host_paths().temporary_root)
        prepare_user_directory(staging_parent, staging_parent)
    files: list[RemoteEvidenceFile] = []
    totals = [0]
    with evidence_staging(staging_parent, prefix=".e-") as stage:
        staging = stage.path
        portable_result = _portable_result(lifecycle_result or {})
        row = stage.write(
            "manifest/lifecycle-result.json", canonical_json_bytes(portable_result)
        )
        files.append(_staged_evidence_file(row, "manifest"))
        if failure is not None:
            row = stage.write(
                "diagnostic/failure.json", canonical_json_bytes(failure.to_dict())
            )
            files.append(_staged_evidence_file(row, "diagnostic"))
        for name, value in (("stdout", result.stdout), ("stderr", result.stderr)):
            if not value:
                continue
            row = stage.write(
                f"log/{name}.txt",
                _redact_diagnostic(value, limit=65536).encode("utf-8"),
            )
            files.append(_staged_evidence_file(row, "log"))
        if custody is not None:
            _copy_evidence_tree(
                custody.candidate_receipt,
                staging,
                "receipt",
                files=files,
                totals=totals,
                _output_owner=stage,
            )
            _copy_evidence_tree(
                custody.runtime_root,
                staging,
                "source/runtime",
                files=files,
                totals=totals,
                _output_owner=stage,
            )
            _copy_evidence_tree(
                custody.cache_directories.obj_dir,
                staging,
                "object/cache",
                files=files,
                totals=totals,
                _output_owner=stage,
            )
            _copy_evidence_tree(
                custody.cache_directories.build_dir,
                staging,
                "source/cache",
                files=files,
                totals=totals,
                _output_owner=stage,
            )
        if artifact is not None:
            _copy_evidence_tree(
                artifact,
                staging,
                "artifact",
                files=files,
                totals=totals,
                _output_owner=stage,
            )
        if result.library_product is not None:
            if artifact is None:
                raise RemoteExecutionError(
                    "execution.remote_library_invalid", "library package is missing"
                )
            require_library_package(result.library_product, artifact)
            row = stage.write("package/library.zip", directory_export_bytes(artifact))
            totals[0] += row.size
            if len(files) >= _MAX_EVIDENCE_FILES or totals[0] > _MAX_EVIDENCE_BYTES:
                raise RemoteExecutionError(
                    "execution.remote_evidence_too_large",
                    "sealed library package exceeds evidence custody limits",
                )
            files.append(_staged_evidence_file(row, "package"))
        try:
            cleanup_intent = capture_cleanup_intent(
                cleanup_roots,
                request_identity=request.identity,
                cleanup_token=cleanup_token,
                ticket=cleanup_ticket,
            )
        except (ValueError, OSError, RuntimeError) as exc:
            raise RemoteExecutionError(
                "execution.remote_cleanup_custody_invalid",
                "producer native cleanup capture refused; workspaces retained: "
                + _redact_diagnostic(exc),
            ) from exc
        cleanup_bytes = canonical_json_bytes(cleanup_intent)
        row = stage.write(INTENT_PATH, cleanup_bytes)
        totals[0] += len(cleanup_bytes)
        if len(files) >= _MAX_EVIDENCE_FILES or totals[0] > _MAX_EVIDENCE_BYTES:
            raise RemoteExecutionError(
                "execution.remote_evidence_too_large",
                "native cleanup intent exceeds evidence custody limits",
            )
        files.append(_staged_evidence_file(row, "manifest"))
        files.sort(key=lambda item: item.path)
        manifest = RemoteLifecycleEvidenceManifest(
            request.identity,
            request.authority_identity,
            worker.identity,
            materialization.identity,
            request.source_identity,
            request.specification_identity,
            request.flavor_identity,
            request.toolchain_identity,
            request.source_index_identity,
            request.model_scope_identity,
            request.action.value,
            result.status.value,
            result.evidence_identity,
            canonical_identity(result.observed_environment.to_dict()),
            (
                None
                if artifact is None or result.artifact_reference is None
                else result.artifact_reference.identity
            ),
            None if artifact is None else artifact.is_dir(),
            _stage_identities(lifecycle_result or {}),
            tuple(files),
            failure,
            cleanup_token,
            library_product=result.library_product,
        )
        manifest_bytes = canonical_json_bytes(manifest.to_dict())
        stage.write("remote-evidence-manifest.json", manifest_bytes)
        expected = {
            row.path: (row.size, row.identity.digest, row.executable) for row in files
        }
        expected["remote-evidence-manifest.json"] = (
            len(manifest_bytes),
            hashlib.sha256(manifest_bytes).hexdigest(),
            False,
        )
        stage.seal()
        bundle_identity = _write_deterministic_tar_gz(
            staging, output, expected=expected, _source_owner=stage
        )
        return (
            manifest,
            ContentReference(
                "remote-lifecycle-evidence", _EVIDENCE_URI, bundle_identity
            ),
            cleanup_intent,
        )


def _persist_library_artifact(
    artifact: Path,
    product: LibraryArtifactProduct,
    cas_root: Path,
    toolchain_identities: tuple[ContentIdentity, ...],
) -> ContentReference:
    """Retain the exact sealed package under a non-executable CAS locator.

    This is package custody, not import authorization. Dispatch/evidence transport
    must separately bind this product before presenting it to a consumer.
    """

    temporary: Path | None = None
    try:
        require_library_package(product, artifact)
        identity = _artifact_identity(artifact)
        value = library_worker_manifest(identity, product, toolchain_identities)
        manifest_identity = canonical_identity(value)
        destination = _cas_entry(cas_root, identity, manifest_identity)
        reference = ContentReference(
            "artifact-export",
            f"{_CAS_SCHEME}:{identity.uri}/library/{manifest_identity.uri}",
            identity,
        )
        ensure_safe_directory(destination.parent)
        if not destination.exists():
            temporary = Path(tempfile.mkdtemp(prefix=".lib-", dir=destination.parent))
            copied = temporary / "payload"
            shutil.copytree(artifact, copied)
            require_library_package(product, copied)
            if _artifact_identity(copied) != identity:
                raise ValueError("worker library copy changed during retention")
            (temporary / "library.json").write_bytes(canonical_json_bytes(value))
            try:
                os.replace(temporary, destination)
                temporary = None
            except OSError:
                # A concurrent publisher may have won. Never replace or remove its
                # custody; the common resolver below must validate the winner.
                if not destination.exists():
                    raise
        _resolve_library_artifact(reference, cas_root)
        return reference
    except (OSError, ValueError, UnsafeFilesystemPathError) as exc:
        raise RemoteExecutionError(
            "execution.remote_library_invalid", str(exc)
        ) from exc
    finally:
        if temporary is not None:
            shutil.rmtree(temporary, ignore_errors=True)


def _resolve_library_artifact(
    reference: ContentReference, cas_root: Path
) -> tuple[Path, dict[str, Any]]:
    try:
        parsed = urlsplit(reference.uri)
        prefix = f"{reference.identity.uri}/library/"
        if (
            reference.kind != "artifact-export"
            or parsed.scheme != _CAS_SCHEME
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith(prefix)
        ):
            raise ValueError("worker library locator is invalid")
        manifest_identity = ContentIdentity.parse_uri(parsed.path.removeprefix(prefix))
        entry = _cas_entry(cas_root, reference.identity, manifest_identity)
        require_safe_directory(entry)
        manifest = entry / "library.json"
        if path_is_link_or_reparse(manifest) or not manifest.is_file():
            raise ValueError("worker library manifest must be a regular file")
        value = json.loads(manifest.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {
            "schema",
            "artifact_identity",
            "library_artifact",
            "toolchain_identities",
        }:
            raise ValueError("worker library manifest fields are invalid")
        product = LibraryArtifactProduct.from_dict(value["library_artifact"])
        if not isinstance(value["toolchain_identities"], list):
            raise ValueError("worker library toolchain identities must be an array")
        toolchains = tuple(
            ContentIdentity.from_dict(item) for item in value["toolchain_identities"]
        )
        expected = library_worker_manifest(reference.identity, product, toolchains)
        if canonical_identity(value) != manifest_identity or value != expected:
            raise ValueError("worker library manifest changed after acceptance")
        payload = entry / "payload"
        require_library_package(product, payload)
        if _artifact_identity(payload) != reference.identity:
            raise ValueError("worker library payload differs from its CAS identity")
        return payload, value
    except (OSError, ValueError, TypeError, UnsafeFilesystemPathError) as exc:
        raise RemoteExecutionError(
            "execution.remote_library_invalid", str(exc)
        ) from exc


def _persist_artifact(
    artifact: Path,
    execution_command: dict[str, Any],
    cas_root: Path,
    toolchain_identities: tuple[ContentIdentity, ...],
    execution_entrypoints: tuple[dict[str, Any], ...] = (),
) -> ContentReference:
    try:
        source = Path(artifact).resolve(strict=True)
    except OSError as exc:
        raise RemoteExecutionError(
            "execution.remote_artifact_missing", "accepted artifact is unavailable"
        ) from exc
    if source.is_symlink() or not (source.is_file() or source.is_dir()):
        raise RemoteExecutionError(
            "execution.remote_artifact_invalid",
            "accepted artifact must be a regular file or directory",
        )
    identity = _artifact_identity(source)
    argv = tuple(str(item) for item in execution_command.get("argv") or ())
    if not argv:
        raise RemoteExecutionError(
            "execution.remote_command_missing",
            "accepted artifact has no execution command",
        )
    environment = {
        str(name): str(value)
        for name, value in (execution_command.get("environment") or {}).items()
    }
    try:
        entrypoints = tuple(
            ArtifactEntrypointCommand.from_dict(item) for item in execution_entrypoints
        )
    except ArtifactExportError as exc:
        raise RemoteExecutionError(exc.code, exc.message) from exc
    if entrypoints:
        names = tuple(item.name for item in entrypoints)
        if len(entrypoints) < 2 or len(set(names)) != len(names):
            raise RemoteExecutionError(
                "execution.remote_artifact_manifest_invalid",
                "entrypoint command extension requires unique multiple commands",
            )
        default = entrypoints[0]
        if default.argv != argv or default.environment != environment:
            raise RemoteExecutionError(
                "execution.remote_artifact_manifest_invalid",
                "default entrypoint differs from the top-level command",
            )
    execution_identity = _execution_manifest_identity(
        identity,
        argv,
        environment,
        toolchain_identities,
        entrypoints,
        artifact_path=source,
    )
    destination = _cas_entry(cas_root, identity, execution_identity)
    payload = destination / "payload"
    manifest = destination / "execution.json"
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(
            tempfile.mkdtemp(prefix=f".{identity.digest}.", dir=destination.parent)
        )
        try:
            staged = temporary / "payload"
            if source.is_dir():
                shutil.copytree(source, staged)
            else:
                shutil.copy2(source, staged)
            original = str(source)
            stored_argv = tuple(
                str(payload)
                if item == original
                else item.replace(original, str(payload))
                for item in argv
            )
            stored_environment = {
                str(name): str(value).replace(original, str(payload))
                for name, value in environment.items()
            }
            stored_entrypoints = tuple(
                ArtifactEntrypointCommand(
                    item.name,
                    item.kind,
                    item.deployment_unit,
                    tuple(
                        str(payload)
                        if argument == original
                        else argument.replace(original, str(payload))
                        for argument in item.argv
                    ),
                    {
                        name: value.replace(original, str(payload))
                        for name, value in item.environment.items()
                    },
                )
                for item in entrypoints
            )
            manifest_value: dict[str, Any] = {
                "argv": list(stored_argv),
                "environment": stored_environment,
                "toolchain_identities": [
                    item.to_dict() for item in toolchain_identities
                ],
                "execution_identity": execution_identity.to_dict(),
            }
            if stored_entrypoints:
                default = stored_entrypoints[0]
                if (
                    default.argv != stored_argv
                    or default.environment != stored_environment
                ):
                    raise RemoteExecutionError(
                        "execution.remote_artifact_manifest_invalid",
                        "default entrypoint differs from the top-level command",
                    )
                manifest_value["entrypoints"] = [
                    item.to_dict() for item in stored_entrypoints
                ]
                manifest_value["default_entrypoint"] = default.name
            (temporary / "execution.json").write_text(
                json.dumps(
                    manifest_value,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, destination)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
    if (
        not payload.exists()
        or not manifest.is_file()
        or _artifact_identity(payload) != identity
    ):
        raise RemoteExecutionError(
            "execution.remote_artifact_corrupt",
            "worker artifact CAS entry does not match its identity",
        )
    reference = _artifact_reference(identity, execution_identity)
    _resolve_artifact(reference, cas_root)
    return reference


def _resolve_artifact(
    reference: ContentReference, cas_root: Path
) -> tuple[Path, dict[str, Any]]:
    parsed = urlsplit(reference.uri)
    if parsed.path.startswith(f"{reference.identity.uri}/library/"):
        return _resolve_library_artifact(reference, cas_root)
    execution_identity: ContentIdentity | None = None
    legacy_locator = parsed.path == reference.identity.uri
    prefix = f"{reference.identity.uri}/execution/"
    if parsed.scheme == _CAS_SCHEME and parsed.path.startswith(prefix):
        try:
            execution_identity = ContentIdentity.parse_uri(
                parsed.path.removeprefix(prefix)
            )
        except ValueError as exc:
            raise RemoteExecutionError(
                "execution.remote_artifact_reference_invalid",
                "worker-CAS execution locator is invalid",
            ) from exc
    elif parsed.scheme != _CAS_SCHEME or not legacy_locator:
        raise RemoteExecutionError(
            "execution.remote_artifact_reference_invalid",
            "run requires a worker-CAS artifact reference",
        )
    entry = _cas_entry(cas_root, reference.identity, execution_identity)
    payload = entry / "payload"
    manifest = entry / "execution.json"
    try:
        if _artifact_identity(payload) != reference.identity:
            raise RemoteExecutionError(
                "execution.remote_artifact_corrupt",
                "worker artifact CAS payload does not match its identity",
            )
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except RemoteExecutionError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RemoteExecutionError(
            "execution.remote_artifact_unavailable",
            "worker artifact CAS entry is unavailable",
        ) from exc
    required = {"argv", "environment", "toolchain_identities"}
    keys = set(value) if isinstance(value, dict) else set()
    extras = keys - required
    allowed_extras = (
        set(),
        {"execution_identity"},
        {"entrypoints", "default_entrypoint"},
        {"entrypoints", "default_entrypoint", "execution_identity"},
    )
    if (
        not isinstance(value, dict)
        or not required.issubset(keys)
        or extras not in allowed_extras
        or not isinstance(value["argv"], list)
        or not value["argv"]
        or any(not isinstance(item, str) or not item for item in value["argv"])
        or not isinstance(value["environment"], dict)
        or any(
            not isinstance(name, str) or not isinstance(item, str)
            for name, item in value["environment"].items()
        )
        or not isinstance(value["toolchain_identities"], list)
    ):
        raise RemoteExecutionError(
            "execution.remote_artifact_manifest_invalid",
            "worker artifact execution manifest is invalid",
        )
    parsed_entrypoints: tuple[ArtifactEntrypointCommand, ...] = ()
    if "entrypoints" in value:
        try:
            parsed_entrypoints = tuple(
                ArtifactEntrypointCommand.from_dict(item)
                for item in value["entrypoints"]
            )
            names = tuple(item.name for item in parsed_entrypoints)
            if (
                len(parsed_entrypoints) < 2
                or len(parsed_entrypoints) > 256
                or len(set(names)) != len(names)
                or value["default_entrypoint"] not in names
            ):
                raise ValueError
            default = next(
                item
                for item in parsed_entrypoints
                if item.name == value["default_entrypoint"]
            )
            if (
                list(default.argv) != value["argv"]
                or default.environment != value["environment"]
            ):
                raise ValueError
        except (
            ArtifactExportError,
            KeyError,
            StopIteration,
            TypeError,
            ValueError,
        ) as exc:
            raise RemoteExecutionError(
                "execution.remote_artifact_manifest_invalid",
                "worker artifact entrypoint commands are invalid",
            ) from exc
    if execution_identity is not None:
        try:
            recorded_execution_identity = ContentIdentity.from_dict(
                value["execution_identity"]
            )
            toolchain_identities = tuple(
                ContentIdentity.from_dict(item)
                for item in value["toolchain_identities"]
            )
            observed_execution_identity = _execution_manifest_identity(
                reference.identity,
                tuple(value["argv"]),
                dict(value["environment"]),
                toolchain_identities,
                parsed_entrypoints,
                artifact_path=payload,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RemoteExecutionError(
                "execution.remote_artifact_manifest_invalid",
                "worker artifact execution identity is invalid",
            ) from exc
        if (
            recorded_execution_identity != execution_identity
            or observed_execution_identity != execution_identity
        ):
            raise RemoteExecutionError(
                "execution.remote_artifact_manifest_changed",
                "worker artifact execution manifest changed after acceptance",
            )
    elif "execution_identity" in value:
        raise RemoteExecutionError(
            "execution.remote_artifact_reference_invalid",
            "legacy worker-CAS locator cannot address an execution-bound manifest",
        )
    return payload, value


def _observed_environment(
    worker: ExecutionWorker, toolchains: tuple[ContentIdentity, ...]
) -> ObservedExecutionEnvironment:
    local = ExecutionWorker(
        "local-probe",
        ExecutionWorkerKind.LOCAL,
        requirements=worker.requirements,
    )
    observed = probe_worker_capabilities(local)
    nvidia = tuple(device for device in observed.gpus if device.vendor == "nvidia")
    first = nvidia[0] if nvidia else None
    capabilities = tuple(
        sorted({capability for device in nvidia for capability in device.capabilities})
    )
    return ObservedExecutionEnvironment(
        observed.os_family,
        observed.os_version,
        observed.cpu_architecture,
        observed.logical_cpu_cores,
        observed.memory_mib,
        None if first is None else first.vendor,
        None if first is None else first.model,
        len(nvidia),
        None
        if first is None
        else min(device.memory_mib or 0 for device in nvidia) or None,
        capabilities,
        tuple(sorted(toolchains, key=lambda item: item.uri)),
    )


def execute_remote_request(
    worker: ExecutionWorker,
    request: ExecutionDispatchRequest,
    materialization: ExecutionSourceMaterialization,
    *,
    project_root: Path,
    cas_root: Path,
    rebuild: RemoteLifecycleRebuilder,
    accepted_source_entries: tuple[dict[str, Any], ...] | None = None,
    custody: RemoteLifecycleCustody | None = None,
    retain_lifecycle_custody: bool = False,
    _runtime_lifetime: _RemoteRuntimeLifetime | None = None,
) -> ExecutionDispatchResult:
    """Execute after transport extraction, retaining only immutable worker artifacts."""

    if not worker.is_remote:
        raise RemoteExecutionError(
            "execution.remote_worker_kind_invalid", "receiver requires an SSH worker"
        )
    if (
        request.worker_identity != worker.identity
        or request.target_profile != worker.target_profile
    ):
        raise RemoteExecutionError(
            "execution.remote_request_mismatch",
            "request does not bind the selected SSH worker",
        )
    if materialization.request_identity != request.identity:
        raise RemoteExecutionError(
            "execution.remote_materialization_mismatch",
            "source materialization binds a different request",
        )
    root = Path(project_root).resolve(strict=True)
    current_source_identity = (
        source_tree_identity(root)
        if accepted_source_entries is None
        else verify_materialized_source(root, accepted_source_entries)
    )
    if current_source_identity != materialization.source_tree_identity.uri:
        raise RemoteExecutionError(
            "execution.remote_source_mismatch",
            "materialized project tree does not match transport authority",
        )
    artifact_reference: ContentReference | None = None
    library_product: LibraryArtifactProduct | None = None
    stdout = ""
    stderr = ""
    exit_status = 0
    coverage_gaps: dict[str, object] | None = None
    observed_toolchains: tuple[ContentIdentity, ...]
    if request.action in {LifecycleDispatchAction.BUILD, LifecycleDispatchAction.TEST}:
        own_lifetime = _runtime_lifetime is None
        lifetime = _RemoteRuntimeLifetime() if own_lifetime else _runtime_lifetime
        if type(lifetime) is not _RemoteRuntimeLifetime:
            raise TypeError("original receiver runtime lifetime required")
        try:
            lifecycle_custody = custody or _default_remote_custody(
                root,
                root.parent,
                lifetime,
                keep=retain_lifecycle_custody,
            )
            result = rebuild(
                component_path=request.component_path,
                project_root=root,
                custody=lifecycle_custody,
                flavor_selectors=request.flavor_selectors,
                target_profile=request.target_profile,
                model_selector=request.model_selector,
                accepted_source_only=request.accepted_source_only,
                jobs=request.jobs,
                accepted_source_provider_id=request.accepted_source_provider_id,
                accepted_source_provider_identity=(
                    request.accepted_source_provider_identity
                ),
                **(
                    {
                        "source_cache_entry_identities": (
                            request.source_cache_entry_identities
                        )
                    }
                    if request.source_cache_entry_identities
                    else {}
                ),
            )
            try:
                observed_toolchains = tuple(
                    ContentIdentity.parse_uri(str(item))
                    for item in result["observed_toolchain_identities"]
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise RemoteExecutionError(
                    "execution.remote_toolchain_observation_missing",
                    "accepted lifecycle omitted its observed toolchain closure",
                ) from exc
            if not observed_toolchains:
                raise RemoteExecutionError(
                    "execution.remote_toolchain_observation_missing",
                    "accepted lifecycle reported an empty toolchain closure",
                )
            try:
                if "library_artifact" in result:
                    try:
                        library_product = LibraryArtifactProduct.from_dict(
                            result["library_artifact"]
                        )
                        if (
                            result.get("passed") is not True
                            or result.get("execution_command")
                            or result.get("execution_entrypoints")
                        ):
                            raise ValueError(
                                "library must be accepted without an execution command"
                            )
                    except (TypeError, ValueError) as exc:
                        raise RemoteExecutionError(
                            "execution.remote_library_invalid", str(exc)
                        ) from exc
                    artifact_reference = _persist_library_artifact(
                        Path(str(result["artifact"])),
                        library_product,
                        cas_root,
                        observed_toolchains,
                    )
                else:
                    artifact_reference = _persist_artifact(
                        Path(str(result["artifact"])),
                        dict(result["execution_command"]),
                        cas_root,
                        observed_toolchains,
                        tuple(
                            dict(item)
                            for item in result.get("execution_entrypoints", [])
                        ),
                    )
            finally:
                runtime = result.get("runtime_root")
                if runtime:
                    from literate_ai.adapters.coverage_gaps import (
                        scan_runtime_coverage_gaps,
                    )

                    report = scan_runtime_coverage_gaps(
                        root, request.component_path, runtime
                    )
                    if report is not None:
                        coverage_gaps = report.to_dict()
                    if (
                        not retain_lifecycle_custody
                        and lifecycle_custody.project_runtime is None
                    ):
                        shutil.rmtree(str(runtime), ignore_errors=True)
        finally:
            if own_lifetime:
                lifetime.close()

    else:
        if request.artifact_reference is None:
            raise RemoteExecutionError(
                "execution.remote_artifact_reference_missing",
                "run request requires an exact worker artifact reference",
            )
        payload, command = _resolve_artifact(request.artifact_reference, cas_root)
        if "library_artifact" in command:
            raise RemoteExecutionError(
                "execution.remote_library_not_executable",
                "library artifacts have no process entrypoint; "
                "consume the exact import surface",
            )
        try:
            observed_toolchains = tuple(
                ContentIdentity.from_dict(item)
                for item in command["toolchain_identities"]
            )
        except (TypeError, ValueError) as exc:
            raise RemoteExecutionError(
                "execution.remote_artifact_manifest_invalid",
                "worker artifact toolchain evidence is invalid",
            ) from exc
        if not observed_toolchains:
            raise RemoteExecutionError(
                "execution.remote_artifact_manifest_invalid",
                "worker artifact toolchain evidence is empty",
            )
        selected_command = None
        if "entrypoints" in command:
            selected_name = request.entrypoint or command["default_entrypoint"]
            selected_command = next(
                (
                    item
                    for item in command["entrypoints"]
                    if item["name"] == selected_name
                ),
                None,
            )
            if selected_command is None:
                available = ", ".join(item["name"] for item in command["entrypoints"])
                raise RemoteExecutionError(
                    "execution.remote_entrypoint_unknown",
                    f"unknown entrypoint {selected_name!r}; available entrypoints: "
                    f"{available}",
                )
        elif request.entrypoint is not None:
            raise RemoteExecutionError(
                "execution.remote_entrypoint_unsupported",
                "worker artifact is single-entrypoint and has no named selector",
            )
        selected_argv = (
            command["argv"] if selected_command is None else selected_command["argv"]
        )
        selected_environment = (
            command["environment"]
            if selected_command is None
            else selected_command["environment"]
        )
        argv = [*selected_argv, *request.arguments]
        environment = inherited_verbose_environment(
            {**os.environ, **selected_environment}
        )
        command_cwd = payload if "entrypoints" in command else payload.parent
        trace_subprocess(argv, cwd=command_cwd, environment=environment)
        completed = run_with_tree_kill(
            argv,
            cwd=command_cwd,
            env=environment,
            text=True,
            timeout=request.timeout_seconds,
        )
        exit_status = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
        artifact_reference = request.artifact_reference
    status = (
        DispatchResultStatus.PASSED if exit_status == 0 else DispatchResultStatus.FAILED
    )
    observation = _observed_environment(worker, observed_toolchains)
    evidence = canonical_identity(
        {
            "schema": "literate-ai/ssh-execution-evidence@1",
            "request_identity": request.identity.uri,
            "materialization_identity": materialization.identity.uri,
            "artifact_reference": None
            if artifact_reference is None
            else artifact_reference.to_dict(),
            "observed_environment": observation.to_dict(),
            "exit_status": exit_status,
        }
    )
    return ExecutionDispatchResult(
        request.identity,
        worker.identity,
        materialization.identity.uri,
        status,
        observation,
        exit_status,
        artifact_reference,
        evidence,
        stdout,
        stderr,
        coverage_gaps=coverage_gaps,
        library_product=library_product,
    )


def materialize_and_execute(
    worker: ExecutionWorker,
    request: ExecutionDispatchRequest,
    materialization: ExecutionSourceMaterialization,
    *,
    archive: Path,
    workspace: Path,
    cas_root: Path,
    rebuild: RemoteLifecycleRebuilder,
    accepted_source_cache_archive: Path | None = None,
    evidence_output: Path | None = None,
    cleanup_ticket: Path | None = None,
) -> ExecutionDispatchResult:
    if (evidence_output is None) != (cleanup_ticket is None):
        raise RemoteExecutionError(
            "execution.remote_evidence_custody_invalid",
            "evidence output and cleanup ticket must appear together",
        )
    if materialization.archive_reference is None:
        raise RemoteExecutionError(
            "execution.remote_archive_required",
            "this receiver invocation requires staged archive materialization",
        )
    if _file_identity(archive) != materialization.archive_reference.identity:
        raise RemoteExecutionError(
            "execution.remote_archive_mismatch",
            "staged archive bytes do not match transport authority",
        )
    if (accepted_source_cache_archive is None) != (
        materialization.accepted_source_cache_reference is None
    ):
        raise RemoteExecutionError(
            "execution.remote_accepted_source_cache_mismatch",
            "staged accepted-source-cache archive does not match transport authority",
        )
    if (
        accepted_source_cache_archive is not None
        and materialization.accepted_source_cache_reference is not None
        and _file_identity(accepted_source_cache_archive)
        != materialization.accepted_source_cache_reference.identity
    ):
        raise RemoteExecutionError(
            "execution.remote_accepted_source_cache_mismatch",
            "staged accepted-source-cache bytes do not match transport authority",
        )
    destination = Path(workspace).resolve()
    if destination.exists() or destination.is_symlink():
        raise RemoteExecutionError(
            "execution.remote_workspace_exists",
            "remote execution workspace must not already exist",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    _identity, accepted_source_entries = extract_source_archive_with_manifest(
        archive, destination, materialization.source_tree_identity.uri
    )
    deferred_cleanup = evidence_output is not None
    runtime_lifetime = _RemoteRuntimeLifetime()
    workspace_node = destination.lstat()
    short_attempt: Path | None = None
    lifecycle_result: dict[str, object] | None = None
    lifecycle_custody: RemoteLifecycleCustody | None = None
    artifact: Path | None = None
    cleanup_token = uuid.uuid4().hex
    cleanup_roots = []

    def recording_rebuild(**values: Any) -> dict[str, object]:
        nonlocal lifecycle_result, artifact, lifecycle_custody
        lifecycle_custody = values["custody"]
        lifecycle_result = rebuild(**values)
        candidate = lifecycle_result.get("artifact")
        artifact = None if candidate is None else Path(str(candidate))
        return lifecycle_result

    try:
        if deferred_cleanup:
            cleanup_roots.append(
                runtime_lifetime.enter_context(
                    hold_cleanup_root(destination, workspace_node)
                )
            )
        project_root = destination / "literate-ai"
        if accepted_source_cache_archive is not None:
            short_attempt = Path(
                tempfile.mkdtemp(prefix=f"litai-s-{cleanup_token[:8]}-")
            ).resolve(strict=True)
            if deferred_cleanup:
                cleanup_roots.append(
                    runtime_lifetime.enter_context(
                        hold_cleanup_root(short_attempt, short_attempt.lstat())
                    )
                )
            lifecycle_custody = RemoteLifecycleCustody(
                short_attempt,
                bind_cache_directories(
                    project_root,
                    build_dir=short_attempt / "build",
                    obj_dir=short_attempt / "objects",
                ),
                short_attempt / "runtime",
                short_attempt / "candidate-receipt.json",
            )
            _restore_accepted_source_cache(
                lifecycle_custody.cache_directories.build_dir,
                accepted_source_cache_archive,
            )
        else:
            lifecycle_custody = None  # Allocate only after exact source verification.
        try:
            result = execute_remote_request(
                worker,
                request,
                materialization,
                project_root=project_root,
                cas_root=cas_root,
                rebuild=recording_rebuild,
                accepted_source_entries=accepted_source_entries,
                custody=lifecycle_custody,
                retain_lifecycle_custody=deferred_cleanup,
                _runtime_lifetime=runtime_lifetime,
            )
            failure = None
        except Exception as exc:
            if not deferred_cleanup:
                raise
            failure = _failure_diagnostic(exc)
            observed = _observed_environment(worker, (request.toolchain_identity,))
            evidence = canonical_identity(
                {
                    "schema": "literate-ai/ssh-execution-failure-evidence@1",
                    "request_identity": request.identity.uri,
                    "worker_identity": worker.identity.uri,
                    "materialization_identity": materialization.identity.uri,
                    "diagnostic_identity": failure.identity.uri,
                }
            )
            result = ExecutionDispatchResult(
                request.identity,
                worker.identity,
                materialization.identity.uri,
                DispatchResultStatus.FAILED,
                observed,
                1,
                None,
                evidence,
                "",
                failure.message,
                failure.identity.uri,
            )
        if (
            deferred_cleanup
            and failure is None
            and result.status is not DispatchResultStatus.PASSED
        ):
            failure = RemoteFailureDiagnostic(
                code="execution.remote_process_failed",
                message=(
                    f"worker {request.action.value} exited "
                    f"with status {result.exit_status}"
                ),
                stdout=(
                    _redact_diagnostic(result.stdout, limit=65536)
                    if result.stdout
                    else ""
                ),
                stderr=(
                    _redact_diagnostic(result.stderr, limit=65536)
                    if result.stderr
                    else ""
                ),
            )
            result = replace(result, diagnostic_digest=failure.identity.uri)
        if evidence_output is None or cleanup_ticket is None:
            return result
        try:
            manifest, reference, cleanup_intent = _write_remote_evidence(
                worker=worker,
                request=request,
                materialization=materialization,
                result=result,
                lifecycle_result=lifecycle_result,
                failure=failure,
                custody=lifecycle_custody,
                artifact=artifact,
                output=Path(evidence_output),
                cleanup_token=cleanup_token,
                cleanup_roots=tuple(cleanup_roots),
                cleanup_ticket=Path(cleanup_ticket),
            )
        except (EvidenceStagingError, OSError) as exc:
            raise RemoteExecutionError(
                "execution.remote_evidence_staging_changed",
                "original evidence staging refused; retained state: "
                + _redact_diagnostic(exc),
            ) from exc
        write_cleanup_ticket(
            Path(cleanup_ticket), manifest, reference.identity, cleanup_intent
        )
        return replace(
            result,
            evidence_manifest=manifest,
            evidence_reference=reference,
        )
    finally:
        runtime_lifetime.close()
        if not deferred_cleanup and runtime_lifetime.cleanup_safe:
            if short_attempt is not None:
                shutil.rmtree(short_attempt, ignore_errors=True)
            require_safe_directory(destination)
            current_node = destination.lstat()
            if (current_node.st_dev, current_node.st_ino, current_node.st_mode) != (
                workspace_node.st_dev,
                workspace_node.st_ino,
                workspace_node.st_mode,
            ):
                raise RemoteExecutionError(
                    "execution.remote_workspace_changed", "foreign workspace preserved"
                )
            shutil.rmtree(destination, ignore_errors=True)


def import_remote_evidence_bundle(
    bundle: Path,
    manifest: RemoteLifecycleEvidenceManifest,
    *,
    expected_bundle_identity: ContentIdentity,
    store_root: Path,
) -> tuple[ContentIdentity, tuple[ContentIdentity, ...]]:
    """Verify transported bytes, then deterministically import coordinator custody."""

    source = Path(bundle)
    if _file_identity(source) != expected_bundle_identity:
        raise RemoteExecutionError(
            "execution.remote_evidence_bundle_mismatch",
            "transported evidence bundle does not match its declared identity",
        )
    root = Path(store_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="litai-evidence-import-"))
    try:
        transported_modes: dict[str, bool] = {}
        with tarfile.open(source, mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) > _MAX_EVIDENCE_FILES + 1:
                raise RemoteExecutionError(
                    "execution.remote_evidence_too_large",
                    "remote evidence bundle contains too many entries",
                )
            total = 0
            for member in members:
                parts = Path(member.name).parts
                if (
                    not member.isfile()
                    or member.name.startswith("/")
                    or "\\" in member.name
                    or not parts
                    or any(part in {"", ".", ".."} for part in parts)
                    or member.name in transported_modes
                ):
                    raise RemoteExecutionError(
                        "execution.remote_evidence_bundle_invalid",
                        "remote evidence bundle contains an unsafe entry",
                    )
                transported_modes[member.name] = bool(member.mode & 0o111)
                total += member.size
                if total > _MAX_EVIDENCE_BYTES:
                    raise RemoteExecutionError(
                        "execution.remote_evidence_too_large",
                        "remote evidence bundle exceeds the eight GiB custody limit",
                    )
                stream = archive.extractfile(member)
                if stream is None:
                    raise RemoteExecutionError(
                        "execution.remote_evidence_bundle_invalid",
                        "remote evidence bundle entry is unreadable",
                    )
                target = temporary.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as output:
                    shutil.copyfileobj(stream, output, length=1024 * 1024)
                if member.mode & 0o111:
                    target.chmod(target.stat().st_mode | 0o111)
        manifest_path = temporary / "remote-evidence-manifest.json"
        try:
            transported_manifest = RemoteLifecycleEvidenceManifest.from_dict(
                json.loads(manifest_path.read_text(encoding="utf-8"))
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise RemoteExecutionError(
                "execution.remote_evidence_manifest_invalid",
                "transported remote evidence manifest is unavailable or invalid",
            ) from exc
        if transported_manifest != manifest:
            raise RemoteExecutionError(
                "execution.remote_evidence_manifest_mismatch",
                "transported manifest differs from the signed result manifest",
            )
        imported: list[ContentIdentity] = []
        expected_paths = {"remote-evidence-manifest.json"}
        for item in manifest.files:
            expected_paths.add(item.path)
            candidate = temporary.joinpath(*item.path.split("/"))
            if (
                not candidate.is_file()
                or candidate.is_symlink()
                or candidate.stat().st_size != item.size
                or _file_identity(candidate) != item.identity
                or transported_modes.get(item.path) != item.executable
            ):
                raise RemoteExecutionError(
                    "execution.remote_evidence_file_mismatch",
                    f"transported evidence file {item.path!r} failed verification",
                )
            blob = (
                root
                / "blobs"
                / "sha256"
                / item.identity.digest[:2]
                / item.identity.digest
            )
            if not blob.exists():
                blob.parent.mkdir(parents=True, exist_ok=True)
                staged = blob.with_name(blob.name + f".{uuid.uuid4().hex}.partial")
                shutil.copyfile(candidate, staged)
                if item.executable:
                    staged.chmod(staged.stat().st_mode | 0o111)
                os.replace(staged, blob)
            if _file_identity(blob) != item.identity:
                raise RemoteExecutionError(
                    "execution.remote_evidence_cas_corrupt",
                    "coordinator evidence CAS contains conflicting bytes",
                )
            imported.append(item.identity)
        if manifest.action in {"build", "test"} and manifest.outcome == "passed":
            artifact_files = tuple(
                item for item in manifest.files if item.path.startswith("artifact/")
            )
            if manifest.artifact_identity is None or not artifact_files:
                raise RemoteExecutionError(
                    "execution.remote_evidence_artifact_missing",
                    "passing remote lifecycle evidence omitted its accepted artifact",
                )
            if manifest.artifact_is_directory:
                observed_artifact_identity = canonical_identity(
                    {
                        "schema": "literate-ai/worker-artifact-directory@1",
                        "entries": [
                            {
                                "path": item.path.removeprefix("artifact/"),
                                "identity": item.identity.uri,
                                "executable": item.executable,
                            }
                            for item in artifact_files
                        ],
                    }
                )
            elif len(artifact_files) == 1:
                observed_artifact_identity = artifact_files[0].identity
            else:
                raise RemoteExecutionError(
                    "execution.remote_evidence_artifact_invalid",
                    "single-file remote artifact has ambiguous transported custody",
                )
            if observed_artifact_identity != manifest.artifact_identity:
                raise RemoteExecutionError(
                    "execution.remote_evidence_artifact_mismatch",
                    "transported artifact bytes do not match the accepted artifact",
                )
            if manifest.library_product is not None:
                try:
                    require_transported_library_package(
                        manifest.library_product,
                        temporary / "package" / "library.zip",
                        temporary / "artifact",
                        executable_by_path={
                            item.path.removeprefix("artifact/"): item.executable
                            for item in artifact_files
                        },
                    )
                except (OSError, ValueError, zipfile.BadZipFile) as exc:
                    raise RemoteExecutionError(
                        "execution.remote_library_invalid", str(exc)
                    ) from exc
        actual_paths = {
            item.relative_to(temporary).as_posix()
            for item in temporary.rglob("*")
            if item.is_file()
        }
        if actual_paths != expected_paths:
            raise RemoteExecutionError(
                "execution.remote_evidence_bundle_unlisted",
                "remote evidence bundle contains missing or undeclared files",
            )
        manifest_destination = (
            root / "manifests" / "sha256" / f"{manifest.identity.digest}.json"
        )
        manifest_destination.parent.mkdir(parents=True, exist_ok=True)
        canonical_manifest = canonical_json_bytes(manifest.to_dict())
        if not manifest_destination.exists():
            staged_manifest = manifest_destination.with_name(
                manifest_destination.name + f".{uuid.uuid4().hex}.partial"
            )
            staged_manifest.write_bytes(canonical_manifest)
            os.replace(staged_manifest, manifest_destination)
        elif manifest_destination.read_bytes() != canonical_manifest:
            raise RemoteExecutionError(
                "execution.remote_evidence_manifest_collision",
                "coordinator evidence manifest CAS contains conflicting bytes",
            )
        imported_identities = tuple(sorted(set(imported), key=lambda item: item.uri))
        store_identity = coordinator_evidence_import_identity(
            manifest_identity=manifest.identity,
            bundle_identity=expected_bundle_identity,
            file_identities=imported_identities,
        )
        return store_identity, imported_identities
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def verify_imported_remote_evidence_store(
    store_root: Path,
    *,
    manifest_identity: ContentIdentity,
    bundle_identity: ContentIdentity,
    deadline_monotonic: float | None = None,
) -> tuple[
    RemoteLifecycleEvidenceManifest, ContentIdentity, tuple[ContentIdentity, ...]
]:
    """Recheck one current imported manifest and its blobs without importing again."""
    _evidence_budget(deadline_monotonic)
    root = Path(store_root).absolute()
    try:
        require_safe_directory(root)
        marker = root / "manifests" / "sha256" / f"{manifest_identity.digest}.json"
        require_safe_directory(marker.parent)
        if (
            marker.is_symlink()
            or not marker.is_file()
            or marker.stat().st_size > MAX_REMOTE_EVIDENCE_MANIFEST_BYTES
        ):
            raise ValueError
        with marker.open("rb") as stream:
            raw = stream.read(MAX_REMOTE_EVIDENCE_MANIFEST_BYTES + 1)
        if (
            len(raw) > MAX_REMOTE_EVIDENCE_MANIFEST_BYTES
            or hashlib.sha256(raw).hexdigest() != manifest_identity.digest
        ):
            raise ValueError
        manifest = RemoteLifecycleEvidenceManifest.from_dict(json.loads(raw))
        if (
            canonical_json_bytes(manifest.to_dict()) != raw
            or manifest.identity != manifest_identity
        ):
            raise ValueError
        if len(manifest.files) > _MAX_EVIDENCE_FILES:
            raise ValueError
        total = 0
        for item in manifest.files:
            _evidence_budget(deadline_monotonic)
            total += item.size
            if total > _MAX_EVIDENCE_BYTES:
                raise ValueError
            blob = (
                root
                / "blobs"
                / "sha256"
                / item.identity.digest[:2]
                / item.identity.digest
            )
            require_safe_directory(blob.parent)
            if (
                blob.is_symlink()
                or not blob.is_file()
                or blob.stat().st_size != item.size
                or _file_identity(
                    blob, expected_size=item.size, deadline_monotonic=deadline_monotonic
                )
                != item.identity
            ):
                raise ValueError
    except RemoteExecutionError:
        raise
    except (OSError, ValueError, UnsafeFilesystemPathError) as exc:
        raise RemoteExecutionError(
            "execution.remote_evidence_store_invalid",
            "Current imported evidence manifest or blobs are unavailable or changed",
        ) from exc
    _evidence_budget(deadline_monotonic)
    identities = tuple(
        sorted({item.identity for item in manifest.files}, key=lambda item: item.uri)
    )
    return (
        manifest,
        coordinator_evidence_import_identity(
            manifest_identity=manifest.identity,
            bundle_identity=bundle_identity,
            file_identities=identities,
        ),
        identities,
    )


def load_and_import_remote_evidence_bundle(
    bundle: Path,
    *,
    expected_manifest_identity: ContentIdentity,
    expected_manifest_size: int,
    expected_bundle_identity: ContentIdentity,
    expected_bundle_size: int,
    store_root: Path,
) -> tuple[
    RemoteLifecycleEvidenceManifest, ContentIdentity, tuple[ContentIdentity, ...]
]:
    """Verify compact-control sizes/digests, then import the referenced manifest."""

    source = Path(bundle)
    try:
        if (
            source.is_symlink()
            or not source.is_file()
            or source.stat().st_size != expected_bundle_size
        ):
            raise OSError
    except OSError as exc:
        raise RemoteExecutionError(
            "execution.remote_evidence_bundle_size_mismatch",
            "transported evidence bundle does not match its declared size",
        ) from exc
    if _file_identity(source) != expected_bundle_identity:
        raise RemoteExecutionError(
            "execution.remote_evidence_bundle_mismatch",
            "transported evidence bundle does not match its declared identity",
        )
    if (
        expected_manifest_size < 1
        or expected_manifest_size > MAX_REMOTE_EVIDENCE_MANIFEST_BYTES
    ):
        raise RemoteExecutionError(
            "execution.remote_evidence_manifest_size_invalid",
            "declared evidence manifest size exceeds its deterministic bound",
        )
    try:
        with tarfile.open(source, mode="r:gz") as archive:
            matches = [
                item
                for item in archive.getmembers()
                if item.name == "remote-evidence-manifest.json"
            ]
            if (
                len(matches) != 1
                or not matches[0].isfile()
                or matches[0].size != expected_manifest_size
            ):
                raise RemoteExecutionError(
                    "execution.remote_evidence_manifest_size_mismatch",
                    "transported evidence manifest does not match its declared size",
                )
            stream = archive.extractfile(matches[0])
            if stream is None:
                raise RemoteExecutionError(
                    "execution.remote_evidence_manifest_invalid",
                    "transported remote evidence manifest is unavailable",
                )
            manifest_bytes = stream.read(expected_manifest_size + 1)
    except RemoteExecutionError:
        raise
    except (OSError, tarfile.TarError) as exc:
        raise RemoteExecutionError(
            "execution.remote_evidence_bundle_invalid",
            "transported remote evidence bundle is unreadable",
        ) from exc
    observed_manifest_identity = ContentIdentity(
        HashAlgorithm.SHA256, hashlib.sha256(manifest_bytes).hexdigest()
    )
    if (
        len(manifest_bytes) != expected_manifest_size
        or observed_manifest_identity != expected_manifest_identity
    ):
        raise RemoteExecutionError(
            "execution.remote_evidence_manifest_mismatch",
            "transported evidence manifest does not match its declared identity",
        )
    try:
        manifest = RemoteLifecycleEvidenceManifest.from_dict(
            json.loads(manifest_bytes.decode("utf-8"))
        )
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RemoteExecutionError(
            "execution.remote_evidence_manifest_invalid",
            "transported remote evidence manifest is invalid",
        ) from exc
    if (
        canonical_json_bytes(manifest.to_dict()) != manifest_bytes
        or manifest.identity != expected_manifest_identity
    ):
        raise RemoteExecutionError(
            "execution.remote_evidence_manifest_mismatch",
            "transported evidence manifest is not canonical control-bound content",
        )
    store_identity, imported = import_remote_evidence_bundle(
        source,
        manifest,
        expected_bundle_identity=expected_bundle_identity,
        store_root=store_root,
    )
    return manifest, store_identity, imported


def acknowledge_remote_evidence_cleanup(
    ticket: Path,
    *,
    manifest_identity: ContentIdentity,
    bundle_identity: ContentIdentity,
    acknowledgement_root: Path,
    retries: int = 3,
) -> ContentIdentity:
    """Join exact acknowledged evidence to fresh original native cleanup custody."""
    try:
        return acknowledge_cleanup(
            ticket,
            manifest_identity=manifest_identity,
            bundle_identity=bundle_identity,
            acknowledgement_root=acknowledgement_root,
            retries=retries,
        )
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        raise RemoteExecutionError(
            "execution.remote_cleanup_custody_invalid",
            "native remote cleanup refused; original or conflicting state retained: "
            + _redact_diagnostic(exc),
        ) from exc


def _restore_accepted_source_cache(build_dir: Path, archive: Path) -> None:
    cache_root = build_dir / "accepted-source-cache"
    try:
        ensure_safe_directory(build_dir)
        try:
            cache_root.lstat()
        except FileNotFoundError:
            pass
        else:
            raise RemoteExecutionError(
                "execution.remote_accepted_source_cache_exists",
                "accepted-source-cache destination must not already exist",
            )
    except (UnsafeFilesystemPathError, OSError) as exc:
        raise RemoteExecutionError(
            "execution.remote_accepted_source_cache_destination_invalid",
            "accepted-source-cache destination parent is not a safe directory",
        ) from exc
    try:
        extract_accepted_source_cache_archive(archive, cache_root)
    except SourceGuardError as exc:
        raise RemoteExecutionError(
            "execution.remote_accepted_source_cache_invalid",
            "staged accepted-source-cache archive could not be restored",
        ) from exc


__all__ = [
    "RemoteExecutionError",
    "RemoteLifecycleRebuilder",
    "acknowledge_remote_evidence_cleanup",
    "execute_remote_request",
    "import_remote_evidence_bundle",
    "load_and_import_remote_evidence_bundle",
    "materialize_and_execute",
    "remote_control_summary",
]
