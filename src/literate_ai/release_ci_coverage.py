"""Finite native-CI action evidence; this module never runs a native command.

The reviewed native producer remains the authority for execution facts. Provider
job success corroborates its report but does not attest hardware or binaries.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import stat
import struct
import zipfile
import zlib
from dataclasses import dataclass

from literate_ai.contracts import canonical_identity
from literate_ai.release_qualification import ReleaseQualificationPolicy, satisfies

REPORT_SCHEMA = "literate-ai/release-ci-coverage@1"
TESTED_FILE_REPORT_SCHEMA = "literate-ai/release-ci-coverage@2"
PROOF_SCHEMA = "literate-ai/verified-ci-coverage@1"
TESTED_FILE_PROOF_SCHEMA = "literate-ai/verified-ci-coverage@2"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_REPORT_BYTES = 4 * 1024 * 1024


class CICoverageError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _fail(message: str, *, code: str = "invalid"):
    raise CICoverageError(code, message)


def _fields(value: object, expected: set[str], description: str) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(f"{description} has missing or unknown fields")
    return value


def _positive(value: object) -> bool:
    return type(value) is int and 0 < value < 2**63


def read_coverage_archive(content: bytes, *, expected_digest: str) -> dict:
    """Read exactly one bounded regular coverage.json; extract nothing to disk."""
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_ARCHIVE_BYTES:
        _fail("Coverage archive exceeds its byte bound")
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    if expected_digest != digest:
        _fail("Coverage archive differs from the selected provider digest")
    # Bound member allocation before ZipFile constructs an object per directory
    # entry. This single-file contract needs an ordinary end directory and no
    # comment; bounded local ZIP64 size fields are harmless and remain allowed.
    if len(content) < 22 or content[-22:-18] != b"PK\x05\x06":
        _fail("Coverage archive needs a finite ordinary ZIP directory")
    disk, start_disk, count, total, size, offset, comment = struct.unpack_from(
        "<HHHHIIH", content, len(content) - 18
    )
    if (
        disk != 0
        or start_disk != 0
        or count != 1
        or total != 1
        or comment != 0
        or not 0 < size <= 4096
        or offset + size != len(content) - 22
    ):
        _fail("Coverage archive must have exactly one bounded directory entry")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) != 1:
                _fail("Coverage archive must contain exactly coverage.json")
            entry = entries[0]
            mode = entry.external_attr >> 16
            if (
                entry.filename != "coverage.json"
                or entry.orig_filename != "coverage.json"
                or entry.is_dir()
                or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                or entry.flag_bits & 1
                or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                or not 0 < entry.file_size <= MAX_REPORT_BYTES
            ):
                _fail("Coverage archive member is unsafe or exceeds its byte bound")
            with archive.open(entry) as stream:
                raw = stream.read(MAX_REPORT_BYTES + 1)
            if len(raw) != entry.file_size or len(raw) > MAX_REPORT_BYTES:
                _fail("Coverage report has inconsistent or excessive bytes")
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
        if isinstance(exc, CICoverageError):
            raise
        raise CICoverageError("invalid", "Coverage archive is unreadable") from exc

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail("Coverage report repeats a JSON field")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=unique_object,
            parse_constant=lambda _value: _fail(
                "Coverage report contains nonfinite JSON"
            ),
        )
    except (ValueError, RecursionError) as exc:
        raise CICoverageError(
            "invalid", "Coverage report is not finite unambiguous JSON"
        ) from exc
    if not isinstance(value, dict):
        _fail("Coverage report must be an object")
    return value


@dataclass(frozen=True, slots=True)
class CoverageContext:
    """Expected facts captured by the provider/source owner, not by the report."""

    repository_id: int
    repository: str
    workflow_id: int
    workflow_path: str
    run_id: int
    run_number: int
    attempt: int
    event: str
    revision: str
    tree: str
    policy_identity: str


def validate_ci_coverage(
    value: object,
    *,
    context: CoverageContext,
    policy: ReleaseQualificationPolicy,
    required_cells: set[tuple[str, str]],
    successful_job_ids: set[int],
    producer_job_id: int,
    fresh_artifact_job_ids: set[int] | None = None,
) -> list[dict]:
    """Return only explicit complete cells bound to current provider/source facts.

    The adapter separately establishes a fresh producer, archive custody and a
    closing observation. This pure result alone is never a promotion receipt.
    Version1 supports actual complete action invocations, not inferred shard or
    differently named command equivalence, GPU qualification or tested artifacts.
    """
    binding = policy.ci_coverage
    tested_file = binding.tested_file if binding else None
    document = _fields(
        value,
        {
            "schema",
            "repository",
            "workflow",
            "run",
            "checkout",
            "policy_identity",
            "qualification_identity",
            "producer_job_id",
            "cells",
        }
        | ({"tested_artifacts"} if tested_file else set()),
        "Coverage report",
    )
    if binding is None or document["schema"] != (
        TESTED_FILE_REPORT_SCHEMA if tested_file else REPORT_SCHEMA
    ):
        _fail("Coverage contract is absent or unsupported")
    repository = _fields(document["repository"], {"id", "name"}, "Repository")
    if (
        not _positive(repository["id"])
        or repository["id"] != context.repository_id
        or not isinstance(repository["name"], str)
        or repository["name"].casefold() != context.repository.casefold()
    ):
        _fail("Coverage belongs to another repository")
    workflow = _fields(document["workflow"], {"id", "path", "revision"}, "Workflow")
    if not _positive(workflow["id"]) or workflow != {
        "id": context.workflow_id,
        "path": context.workflow_path,
        "revision": context.revision,
    }:
        _fail("Coverage belongs to another workflow/source")
    run = _fields(document["run"], {"id", "number", "attempt", "event", "head"}, "Run")
    if any(not _positive(run[key]) for key in ("id", "number", "attempt")) or run != {
        "id": context.run_id,
        "number": context.run_number,
        "attempt": context.attempt,
        "event": context.event,
        "head": context.revision,
    }:
        _fail("Coverage belongs to another run or attempt")
    checkout = _fields(document["checkout"], {"revision", "tree"}, "Checkout")
    if checkout != {"revision": context.revision, "tree": context.tree}:
        _fail("Coverage did not test the selected commit and tree")
    if (
        document["policy_identity"] != context.policy_identity
        or document["qualification_identity"] != policy.identity
        or not _positive(document["producer_job_id"])
        or document["producer_job_id"] != producer_job_id
    ):
        _fail("Coverage policy or current producer differs")
    allowed = {
        (platform, action.name)
        for platform in policy.ci_platforms
        for action in policy.actions
    }
    if not required_cells or not required_cells <= allowed:
        _fail("Required coverage cells are outside the configured CI scope")
    cells = document["cells"]
    if not isinstance(cells, list) or not 1 <= len(cells) <= min(4096, len(allowed)):
        _fail("Coverage cells are absent or exceed the configured bound")
    actions = {action.name: action for action in policy.actions}
    seen = set()
    accepted = []
    for item in cells:
        cell = _fields(
            item,
            {
                "platform",
                "action",
                "action_identity",
                "argv",
                "os_family",
                "cpu_architecture",
                "job_ids",
                "exit_status",
            },
            "Coverage cell",
        )
        if not isinstance(cell["platform"], str) or not isinstance(cell["action"], str):
            _fail("Coverage cell has no platform/action")
        pair = (cell["platform"], cell["action"])
        if pair not in allowed or pair in seen:
            _fail("Coverage cell is duplicated or outside the policy")
        seen.add(pair)
        os_family, cpu = cell["os_family"], cell["cpu_architecture"]
        if (
            os_family not in ("linux", "macos", "windows", "freebsd")
            or not isinstance(cpu, str)
            or not 1 <= len(cpu) <= 32
            or not all(
                character in "abcdefghijklmnopqrstuvwxyz0123456789_"
                for character in cpu
            )
            or not satisfies(cell["platform"], os_family, cpu)
        ):
            _fail("Coverage cell does not establish the requested native platform")
        action = actions[cell["action"]]
        argv = action.argv_for(os_family)
        if (
            argv is None
            or cell["argv"] != list(argv)
            or cell["action_identity"] != canonical_identity(action.to_dict()).uri
            or type(cell["exit_status"]) is not int
            or cell["exit_status"] != 0
        ):
            _fail("Coverage does not establish the complete configured action")
        jobs = cell["job_ids"]
        if (
            not isinstance(jobs, list)
            or not 1 <= len(jobs) <= 64
            or any(not _positive(job) for job in jobs)
            or len(set(jobs)) != len(jobs)
            or not set(jobs) <= successful_job_ids
            or producer_job_id in jobs
        ):
            _fail("Coverage lacks successful current-attempt supporting jobs")
        accepted.append(dict(cell, argv=list(cell["argv"]), job_ids=list(jobs)))
    if not required_cells <= seen:
        _fail(
            "Coverage report is missing required platform/action cells",
            code="incomplete",
        )
    if tested_file is not None:
        artifact = _fields(
            document["tested_artifacts"],
            {"role", "path", "size", "identity", "job_id", "environment_identity"},
            "Tested release file",
        )
        job = artifact["job_id"]
        if (
            artifact["role"] != tested_file.role
            or artifact["path"] != tested_file.path
            or not _positive(artifact["size"])
            or not _positive(job)
            or any(
                not isinstance(artifact[key], str)
                or not _SHA256.fullmatch(artifact[key])
                for key in ("identity", "environment_identity")
            )
            or not any(
                (cell["platform"], cell["action"])
                == (tested_file.platform, tested_file.action)
                and cell["job_ids"] == [job]
                for cell in accepted
            )
        ):
            _fail("Tested release file differs from the policy or its test action")
        if fresh_artifact_job_ids is not None and job not in fresh_artifact_job_ids:
            _fail(
                "Tested release file lacks a fresh supporting execution", code="stale"
            )
    return accepted


def validate_retained_ci_coverage(
    proof: object,
    *,
    policy: ReleaseQualificationPolicy,
    revision: str,
    release_policy_identity: str,
    required_cells: set[tuple[str, str]],
) -> dict:
    """Check stored proof structure/linkage; this never waives live observation."""
    value = _fields(
        proof,
        {
            "schema",
            "repository_id",
            "repository",
            "workflow_id",
            "workflow_path",
            "run_id",
            "run_number",
            "attempt",
            "event",
            "revision",
            "tree",
            "policy_identity",
            "qualification_identity",
            "producer_job_id",
            "producer_started_at",
            "producer_completed_at",
            "attempt_started_at",
            "artifact_id",
            "artifact_name",
            "artifact_digest",
            "artifact_created_at",
            "cells",
            "tested_artifacts",
            "identity",
        },
        "Retained CI coverage",
    )
    binding = policy.ci_coverage
    tested_file = binding.tested_file if binding else None
    if (
        binding is None
        or value["schema"]
        != (TESTED_FILE_PROOF_SCHEMA if tested_file else PROOF_SCHEMA)
        or value["revision"] != revision
        or value["policy_identity"] != release_policy_identity
        or (tested_file is None and value["tested_artifacts"] is not False)
        or not _positive(value["artifact_id"])
        or not _positive(value["attempt"])
        or value["artifact_name"] != binding.artifact_for(value["attempt"])
        or not isinstance(value["artifact_digest"], str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", value["artifact_digest"])
        or not isinstance(value["tree"], str)
        or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value["tree"])
        or not isinstance(value["repository"], str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value["repository"])
        or not isinstance(value["workflow_path"], str)
        or not re.fullmatch(
            r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", value["workflow_path"]
        )
        or not isinstance(value["event"], str)
        or not 0 < len(value["event"]) <= 128
        or any(
            not isinstance(value[key], str) or not 0 < len(value[key]) <= 64
            for key in (
                "producer_started_at",
                "producer_completed_at",
                "attempt_started_at",
                "artifact_created_at",
            )
        )
        or value["identity"]
        != canonical_identity(
            {key: item for key, item in value.items() if key != "identity"}
        ).uri
    ):
        _fail("Retained coverage does not bind this source/policy/contract")
    context = CoverageContext(
        value["repository_id"],
        value["repository"],
        value["workflow_id"],
        value["workflow_path"],
        value["run_id"],
        value["run_number"],
        value["attempt"],
        value["event"],
        revision,
        value["tree"],
        release_policy_identity,
    )
    cells = value["cells"]
    if not isinstance(cells, list) or not 1 <= len(cells) <= 4096:
        _fail("Retained coverage has invalid cells")
    jobs = set()
    for cell in cells:
        if not isinstance(cell, dict) or not isinstance(cell.get("job_ids"), list):
            _fail("Retained coverage has invalid supporting jobs")
        for job in cell["job_ids"]:
            if not _positive(job):
                _fail("Retained coverage has invalid supporting jobs")
            jobs.add(job)
    validate_ci_coverage(
        {
            "schema": TESTED_FILE_REPORT_SCHEMA if tested_file else REPORT_SCHEMA,
            "repository": {"id": value["repository_id"], "name": value["repository"]},
            "workflow": {
                "id": value["workflow_id"],
                "path": value["workflow_path"],
                "revision": revision,
            },
            "run": {
                "id": value["run_id"],
                "number": value["run_number"],
                "attempt": value["attempt"],
                "event": value["event"],
                "head": revision,
            },
            "checkout": {"revision": revision, "tree": value["tree"]},
            "policy_identity": release_policy_identity,
            "qualification_identity": value["qualification_identity"],
            "producer_job_id": value["producer_job_id"],
            "cells": cells,
            **({"tested_artifacts": value["tested_artifacts"]} if tested_file else {}),
        },
        context=context,
        policy=policy,
        required_cells=required_cells,
        successful_job_ids=jobs,
        producer_job_id=value["producer_job_id"],
    )
    return value
