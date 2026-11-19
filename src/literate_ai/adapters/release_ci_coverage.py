"""Observe one current native coverage report without starting or retrying jobs."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path

from literate_ai.adapters.builders import run_bounded_process
from literate_ai.adapters.builders.python import BuildError
from literate_ai.adapters.github_observation import (
    read_json,
    workflow_jobs,
    workflow_runs,
)
from literate_ai.contracts import canonical_identity
from literate_ai.release_ci_coverage import (
    MAX_ARCHIVE_BYTES,
    PROOF_SCHEMA,
    TESTED_FILE_PROOF_SCHEMA,
    CICoverageError,
    CoverageContext,
    read_coverage_archive,
    validate_ci_coverage,
)
from literate_ai.release_qualification import ReleaseQualificationPolicy


def _fail(message: str, code: str = "invalid"):
    raise CICoverageError(code, message)


def _positive(value: object) -> bool:
    return type(value) is int and 0 < value < 2**63


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        _fail("Provider omitted an execution timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timezone missing")
        return result
    except ValueError as exc:
        raise CICoverageError(
            "invalid", "Provider returned an invalid execution timestamp"
        ) from exc


def observe_ci_coverage(
    root: Path,
    *,
    repository: str,
    branch: str,
    revision: str,
    tree: str,
    policy_identity: str,
    workflow: str,
    qualification: ReleaseQualificationPolicy,
    required_cells: set[tuple[str, str]],
    deadline: float,
    expected_run: dict | None = None,
    execute=None,
) -> dict:
    """Verify a fresh producer report and close the selected run/attempt.

    The caller owns committed source/policy checks and their closing observation.
    The reviewed producer supplies native execution and tested-file facts.
    Provider run metadata corroborates their job and attempt linkage.
    """
    binding = qualification.ci_coverage
    if binding is None:
        _fail("No explicit native coverage contract is configured")

    def api(endpoint):
        return read_json(
            root,
            ("gh", "api", "--hostname", "github.com", "--method", "GET", endpoint),
            deadline=deadline,
            execute=execute,
        )

    def current_run():
        matches = workflow_runs(
            root,
            repository,
            branch,
            revision,
            workflow,
            timeout_seconds=max(0, deadline - time.monotonic()),
            execute=execute,
            host="github.com",
            include_workflow_path=True,
        )
        if (
            not matches
            or matches[0]["status"] != "completed"
            or matches[0]["conclusion"] != "success"
        ):
            _fail("Current selected workflow has no successful coverage", "incomplete")
        return matches[0]

    selected = current_run()
    if expected_run is not None and any(
        selected[key] != expected_run[key]
        for key in (
            "databaseId",
            "workflowDatabaseId",
            "number",
            "attempt",
            "headSha",
            "headBranch",
            "event",
        )
    ):
        _fail("Selected run changed before coverage collection", "stale")
    path = selected["workflowPath"]
    if not isinstance(path, str) or not re.fullmatch(
        r"\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml", path
    ):
        _fail("Selected workflow has no supported repository path")
    repo = api(f"repos/{repository}")
    if (
        not isinstance(repo, dict)
        or not _positive(repo.get("id"))
        or not isinstance(repo.get("full_name"), str)
        or repo["full_name"].casefold() != repository.casefold()
    ):
        _fail("Provider repository identity is unavailable")
    run_id, attempt = selected["databaseId"], selected["attempt"]
    context = CoverageContext(
        repo["id"],
        repository,
        selected["workflowDatabaseId"],
        path,
        run_id,
        selected["number"],
        attempt,
        selected["event"],
        revision,
        tree,
        policy_identity,
    )
    observation = api(f"repos/{repository}/actions/runs/{run_id}/attempts/{attempt}")
    if (
        not isinstance(observation, dict)
        or any(
            not _positive(observation.get(key))
            for key in ("id", "run_attempt", "run_number", "workflow_id")
        )
        or any(
            observation.get(key) != expected
            for key, expected in {
                "id": run_id,
                "run_attempt": attempt,
                "run_number": selected["number"],
                "workflow_id": selected["workflowDatabaseId"],
                "head_sha": revision,
                "head_branch": branch,
                "event": selected["event"],
                "path": path,
                "status": "completed",
                "conclusion": "success",
            }.items()
        )
        or not isinstance(observation.get("repository"), dict)
        or not _positive(observation["repository"].get("id"))
        or observation["repository"].get("id") != repo["id"]
    ):
        _fail("Attempt observation differs from the selected run")
    attempt_started = _timestamp(observation.get("run_started_at"))
    jobs = workflow_jobs(
        root,
        deadline,
        repository,
        selected,
        revision,
        execute=execute,
        include_execution=True,
    )
    producers = [
        job
        for job in jobs
        if job["name"] == binding.producer_job and job["run_attempt"] == attempt
    ]
    if (
        len(producers) != 1
        or producers[0]["status"] != "completed"
        or producers[0]["conclusion"] != "success"
    ):
        _fail(
            "Current attempt has no unique successful coverage producer", "incomplete"
        )
    producer = producers[0]
    started, completed = (
        _timestamp(producer["started_at"]),
        _timestamp(producer["completed_at"]),
    )
    if not attempt_started <= started <= completed:
        _fail("Coverage producer was copied from an earlier execution", "incomplete")
    # Supporting successful executions may be provider-confirmed copies in this
    # attempt. Only the exporter must execute freshly after the attempt starts.
    successes = {
        job["id"]
        for job in jobs
        if job["run_attempt"] == attempt
        and job["status"] == "completed"
        and job["conclusion"] == "success"
    }
    artifacts = []
    count = None
    for page in range(1, 6):
        result = api(
            f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100&page={page}"
        )
        if (
            not isinstance(result, dict)
            or type(result.get("total_count")) is not int
            or not 0 <= result["total_count"] <= 500
            or not isinstance(result.get("artifacts"), list)
            or len(result["artifacts"]) > 100
        ):
            _fail("Artifact inventory is invalid or exceeds its bound")
        if count is not None and count != result["total_count"]:
            _fail("Artifact inventory changed during collection", "stale")
        count = result["total_count"]
        artifacts.extend(result["artifacts"])
        if len(artifacts) == count:
            break
        if len(artifacts) > count or len(result["artifacts"]) != 100:
            _fail("Artifact inventory is incomplete")
    if len(artifacts) != count:
        _fail("Artifact inventory is incomplete")
    seen = set()
    matches = []
    name = binding.artifact_for(attempt)
    for artifact in artifacts:
        if (
            not isinstance(artifact, dict)
            or not _positive(artifact.get("id"))
            or artifact["id"] in seen
            or not isinstance(artifact.get("name"), str)
            or not 1 <= len(artifact["name"]) <= 256
        ):
            _fail("Artifact inventory has missing or ambiguous identity")
        seen.add(artifact["id"])
        if artifact["name"] == name:
            matches.append(artifact)
    if len(matches) != 1:
        _fail("Current attempt has no unique coverage artifact", "incomplete")
    artifact = matches[0]
    artifact_id = artifact["id"]
    expected_workflow = {
        "id": run_id,
        "repository_id": repo["id"],
        "head_repository_id": repo["id"],
        "head_branch": branch,
        "head_sha": revision,
    }
    if (
        artifact.get("expired") is not False
        or not _positive(artifact.get("size_in_bytes"))
        or artifact["size_in_bytes"] > MAX_ARCHIVE_BYTES
        or not isinstance(artifact.get("digest"), str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", artifact["digest"])
        or not isinstance(artifact.get("workflow_run"), dict)
        or any(
            not _positive(artifact["workflow_run"].get(key))
            for key in ("id", "repository_id", "head_repository_id")
        )
        or any(
            artifact["workflow_run"].get(key) != expected
            for key, expected in expected_workflow.items()
        )
    ):
        _fail("Coverage artifact is expired or belongs to another source/run")
    created = _timestamp(artifact.get("created_at"))
    if not started <= created <= completed:
        _fail(
            "Coverage artifact was not created during the fresh producer", "incomplete"
        )
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        _fail("Coverage observation exhausted its deadline", "timeout")
    try:
        transfer = (execute or run_bounded_process)(
            (
                "gh",
                "api",
                "--hostname",
                "github.com",
                "--method",
                "GET",
                f"repos/{repository}/actions/artifacts/{artifact_id}/zip",
            ),
            cwd=root,
            environment=dict(os.environ),
            timeout_seconds=min(60, remaining),
            stdout_limit_bytes=MAX_ARCHIVE_BYTES,
            stderr_limit_bytes=64 * 1024,
            error_prefix="release_ci_coverage",
            terminate_descendants=True,
            trace=False,
        )
    except (BuildError, OSError) as exc:
        code = (
            "timeout"
            if isinstance(exc, BuildError) and exc.code.endswith("_timeout")
            else "unavailable"
        )
        raise CICoverageError(
            code, "Coverage archive transfer did not complete safely"
        ) from exc
    if transfer.returncode or len(transfer.stdout) != artifact["size_in_bytes"]:
        _fail("Coverage artifact transfer is incomplete", "unavailable")
    document = read_coverage_archive(
        transfer.stdout, expected_digest=artifact["digest"]
    )
    fresh_artifact_jobs = None
    if binding.tested_file is not None:
        fresh_artifact_jobs = {
            job["id"]
            for job in jobs
            if job["id"] in successes
            and attempt_started
            <= _timestamp(job["started_at"])
            <= _timestamp(job["completed_at"])
            <= started
        }
    cells = validate_ci_coverage(
        document,
        context=context,
        policy=qualification,
        required_cells=required_cells,
        successful_job_ids=successes,
        producer_job_id=producer["id"],
        fresh_artifact_job_ids=fresh_artifact_jobs,
    )
    closing_artifact = api(f"repos/{repository}/actions/artifacts/{artifact_id}")
    artifact_fields = (
        "id",
        "name",
        "digest",
        "size_in_bytes",
        "expired",
        "created_at",
        "workflow_run",
    )
    if (
        not isinstance(closing_artifact, dict)
        or canonical_identity(
            {key: closing_artifact.get(key) for key in artifact_fields}
        ).uri
        != canonical_identity({key: artifact.get(key) for key in artifact_fields}).uri
        or current_run() != selected
    ):
        _fail("Coverage source/run/artifact changed during observation", "stale")
    proof = {
        "schema": TESTED_FILE_PROOF_SCHEMA if binding.tested_file else PROOF_SCHEMA,
        "repository_id": repo["id"],
        "repository": repository,
        "workflow_id": context.workflow_id,
        "workflow_path": path,
        "run_id": run_id,
        "run_number": context.run_number,
        "attempt": attempt,
        "event": context.event,
        "revision": revision,
        "tree": tree,
        "policy_identity": policy_identity,
        "qualification_identity": qualification.identity,
        "producer_job_id": producer["id"],
        "producer_started_at": producer["started_at"],
        "producer_completed_at": producer["completed_at"],
        "attempt_started_at": observation["run_started_at"],
        "artifact_id": artifact_id,
        "artifact_name": name,
        "artifact_digest": artifact["digest"],
        "artifact_created_at": artifact["created_at"],
        "cells": cells,
        "tested_artifacts": document["tested_artifacts"]
        if binding.tested_file
        else False,
    }
    return dict(proof, identity=canonical_identity(proof).uri)
