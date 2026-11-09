"""Bounded failed-qualification observations, separate from qualified products."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    encode_directory_export,
    read_directory_export,
)
from literate_ai.adapters.evidence_storage import FileSystemEvidenceStore
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.security.evidence.storage import EvidenceReadLimits
from literate_ai.source_to_specification.qualification_lifecycle import (
    QualificationLifecyclePlan,
    QualificationParityCaseEvidence,
    QualificationVerifierCaseMap,
)

_SCHEMA = "literate-ai/qualification-failure-diagnostic@1"
_PLAN_FIELDS = (
    "target_profile_identity",
    "component_lock_identity",
    "specification_set_identity",
    "source_snapshot_identity",
    "generation_input_audit_identity",
    "promotion_tree_identity",
)


def _plan_document(plan: QualificationLifecyclePlan) -> dict[str, object]:
    if not isinstance(plan, QualificationLifecyclePlan):
        raise QualificationCaptureError("qualification.diagnostic.plan-invalid")
    return {
        **{name: getattr(plan, name).uri for name in _PLAN_FIELDS},
        "run_identities": [identity.uri for identity in plan.run_identities],
        "case_map": plan.case_map.to_dict(),
    }


def _failure_code(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z][a-z0-9_.-]{0,127}", value
    ):
        raise QualificationCaptureError("qualification.diagnostic.code-invalid")
    return value


@dataclass(frozen=True, slots=True)
class QualificationFailureDiagnostic:
    """Original observed bytes and their failed subject; no product admission."""

    identity: ContentIdentity
    plan: QualificationLifecyclePlan
    failure_code: str
    records: QualificationEvidenceReader
    case_records: tuple[ContentIdentity, ...]
    active_case: Mapping[str, object] | None


def _require_process(
    reader: QualificationEvidenceReader, identity: ContentIdentity
) -> None:
    process = reader.read_json(identity)
    if (
        not isinstance(process, dict)
        or set(process)
        != {"schema", "command", "exit_status", "stdout", "stderr", "json_output_valid"}
        or process["schema"] != "literate-ai/qualification-process-observation@1"
        or type(process["exit_status"]) is not int
        or type(process["json_output_valid"]) is not bool
        or not isinstance(process["command"], list)
        or not process["command"]
        or any(not isinstance(item, str) for item in process["command"])
        or canonical_json_bytes(process) != reader.read_bytes(identity)
    ):
        raise QualificationCaptureError("qualification.diagnostic.process-invalid")
    for stream in ("stdout", "stderr"):
        reader.read_bytes(ContentIdentity.parse_uri(process[stream]))


def _validate_active_case(
    plan: QualificationLifecyclePlan,
    value: Mapping[str, object] | None,
    reader: QualificationEvidenceReader,
) -> Mapping[str, object] | None:
    if value is None:
        return None
    fields = {
        "run_identity",
        "case_id",
        "case_identity",
        "process_role",
        "baseline_observation_identity",
        "generated_observation_identity",
        "process_status",
        "capture_status",
        "partial_stdout_identity",
        "partial_stderr_identity",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise QualificationCaptureError("qualification.diagnostic.active-case-invalid")
    for name in (
        "run_identity",
        "case_id",
        "case_identity",
        "process_role",
        "process_status",
        "capture_status",
    ):
        if not isinstance(value[name], str):
            raise QualificationCaptureError(
                "qualification.diagnostic.active-case-invalid"
            )
    binding = next(
        (item for item in plan.case_map.cases if item.case_id == value["case_id"]), None
    )
    if (
        ContentIdentity.parse_uri(value["run_identity"]) not in plan.run_identities
        or binding is None
        or ContentIdentity.parse_uri(value["case_identity"]) != binding.case_identity
        or value["process_role"] not in {"baseline", "generated"}
        or value["process_status"]
        not in {"timeout", "launch_failed", "observation_failed"}
        or value["capture_status"]
        not in {"available", "output_limit", "retention_unavailable", "not_recorded"}
        or (
            value["process_role"] == "generated"
            and value["baseline_observation_identity"] is None
        )
        or (
            value["process_role"] == "baseline"
            and value["generated_observation_identity"] is not None
        )
    ):
        raise QualificationCaptureError("qualification.diagnostic.active-case-mismatch")
    for name in ("baseline_observation_identity", "generated_observation_identity"):
        if value[name] is not None:
            _require_process(reader, ContentIdentity.parse_uri(value[name]))
    for name in ("partial_stdout_identity", "partial_stderr_identity"):
        if value[name] is not None:
            reader.read_bytes(ContentIdentity.parse_uri(value[name]))
    return MappingProxyType(dict(value))


def _validate_cases(
    plan: QualificationLifecyclePlan,
    identities: tuple[ContentIdentity, ...],
    reader: QualificationEvidenceReader,
) -> None:
    if not isinstance(identities, tuple) or any(
        not isinstance(item, ContentIdentity) for item in identities
    ):
        raise QualificationCaptureError("qualification.diagnostic.cases-invalid")
    if identities != tuple(sorted(set(identities), key=lambda item: item.uri)):
        raise QualificationCaptureError("qualification.diagnostic.cases-invalid")
    expected = {binding.case_id: binding for binding in plan.case_map.cases}
    seen = set()
    for identity in identities:
        document = reader.read_json(identity)
        if (
            not isinstance(document, dict)
            or set(document) != {"schema", "run_identity", "case"}
            or document["schema"] != "literate-ai/qualification-diagnostic-case@1"
            or canonical_json_bytes(document) != reader.read_bytes(identity)
        ):
            raise QualificationCaptureError("qualification.diagnostic.case-invalid")
        run = ContentIdentity.parse_uri(document["run_identity"])
        case = QualificationParityCaseEvidence.from_dict(document["case"])
        binding = expected.get(case.case_id)
        key = (run, case.case_id)
        if (
            run not in plan.run_identities
            or binding is None
            or binding.case_identity != case.case_identity
            or key in seen
        ):
            raise QualificationCaptureError("qualification.diagnostic.case-mismatch")
        seen.add(key)
        for observation in (
            case.baseline_observation_identity,
            case.generated_observation_identity,
        ):
            _require_process(reader, observation)


def encode_qualification_failure_diagnostic(
    plan: QualificationLifecyclePlan,
    failure_code: str,
    entries: tuple[tuple[ContentIdentity, bytes], ...],
    *,
    max_bytes: int,
    max_records: int,
    case_records: tuple[ContentIdentity, ...] = (),
    active_case: Mapping[str, object] | None = None,
) -> bytes:
    """Encode original available facts; archive overhead remains inside its limits."""
    plan_document = _plan_document(plan)
    reader = QualificationEvidenceReader(
        entries, max_bytes=max_bytes, max_records=max_records
    )
    _validate_cases(plan, case_records, reader)
    context = _validate_active_case(plan, active_case, reader)
    document = {
        "schema": _SCHEMA,
        "outcome": "failed",
        "plan": plan_document,
        "failure_code": _failure_code(failure_code),
        "records": [identity.uri for identity, _ in entries],
        "case_records": [identity.uri for identity in case_records],
        "active_case": None if context is None else dict(context),
    }
    # The distinct member makes the qualified archive reader refuse this archive,
    # including when an earlier clean run left successful observations in it.
    return encode_directory_export(
        (
            DirectoryExportFile(
                "diagnostic.json", canonical_json_bytes(document), 0o444
            ),
            *(
                DirectoryExportFile(f"records/{identity.digest}", payload, 0o444)
                for identity, payload in entries
            ),
        ),
        max_bytes=max_bytes,
        max_entries=max_records,
    )


def reopen_qualification_failure_diagnostic(
    content: bytes,
    expected: BlobRef,
    *,
    max_bytes: int,
    max_records: int,
) -> QualificationFailureDiagnostic:
    """Reopen the failed subject and available facts without granting admission."""
    files = read_directory_export(
        content, expected, max_bytes=max_bytes, max_entries=max_records
    )
    header = None
    entries = []
    for item in files:
        if item.mode != 0o444:
            raise QualificationCaptureError("qualification.diagnostic.member-invalid")
        if item.path == "diagnostic.json":
            header = item.content
        elif item.path.startswith("records/"):
            try:
                identity = ContentIdentity.parse_uri(
                    "sha256:" + item.path.removeprefix("records/")
                )
            except (TypeError, ValueError) as exc:
                raise QualificationCaptureError(
                    "qualification.diagnostic.member-invalid"
                ) from exc
            entries.append((identity, item.content))
        else:
            raise QualificationCaptureError("qualification.diagnostic.member-invalid")
    try:
        if header is None:
            raise ValueError("missing diagnostic header")
        document = json.loads(header)
        if (
            not isinstance(document, dict)
            or set(document)
            != {
                "schema",
                "outcome",
                "plan",
                "failure_code",
                "records",
                "case_records",
                "active_case",
            }
            or document["schema"] != _SCHEMA
            or document["outcome"] != "failed"
            or canonical_json_bytes(document) != header
        ):
            raise ValueError("invalid diagnostic header")
        value = document["plan"]
        if not isinstance(value, dict) or set(value) != {
            *_PLAN_FIELDS,
            "run_identities",
            "case_map",
        }:
            raise ValueError("invalid diagnostic plan")
        plan = QualificationLifecyclePlan(
            *(ContentIdentity.parse_uri(value[name]) for name in _PLAN_FIELDS),
            tuple(ContentIdentity.parse_uri(item) for item in value["run_identities"]),
            QualificationVerifierCaseMap.from_dict(value["case_map"]),
        )
        if _plan_document(plan) != value:
            raise ValueError("noncanonical diagnostic plan")
        code = _failure_code(document["failure_code"])
        if document["records"] != [identity.uri for identity, _ in entries]:
            raise ValueError("diagnostic membership differs")
        case_records = tuple(
            ContentIdentity.parse_uri(item) for item in document["case_records"]
        )
    except (TypeError, ValueError, KeyError, RecursionError) as exc:
        raise QualificationCaptureError(
            "qualification.diagnostic.header-invalid"
        ) from exc
    reader = QualificationEvidenceReader(
        tuple(entries), max_bytes=max_bytes, max_records=max_records
    )
    _validate_cases(plan, case_records, reader)
    active_case = _validate_active_case(plan, document["active_case"], reader)
    return QualificationFailureDiagnostic(
        canonical_identity(document), plan, code, reader, case_records, active_case
    )


def publish_qualification_failure_diagnostic(
    retained_store: Path,
    plan: QualificationLifecyclePlan,
    failure_code: str,
    entries: tuple[tuple[ContentIdentity, bytes], ...],
    *,
    max_bytes: int,
    max_records: int = 100_000,
    case_records: tuple[ContentIdentity, ...] = (),
    active_case: Mapping[str, object] | None = None,
) -> BlobRef:
    """Publish and reread only beneath the explicitly selected diagnostic store."""
    archive = encode_qualification_failure_diagnostic(
        plan,
        failure_code,
        entries,
        max_bytes=max_bytes,
        max_records=max_records,
        case_records=case_records,
        active_case=active_case,
    )
    store = FileSystemEvidenceStore(
        Path(retained_store) / "diagnostics",
        writable=True,
        limits=EvidenceReadLimits(
            maximum_blob_bytes=max_bytes, maximum_total_bytes=max_bytes
        ),
    )
    reference = store.put_bytes(archive, media_type="application/zip")
    reopened = reopen_qualification_failure_diagnostic(
        store.get_bytes(reference),
        reference,
        max_bytes=max_bytes,
        max_records=max_records,
    )
    if (
        reopened.plan != plan
        or reopened.failure_code != failure_code
        or reopened.case_records != case_records
        or reopened.active_case != active_case
    ):
        raise QualificationCaptureError("qualification.diagnostic.reopen-mismatch")
    return reference
