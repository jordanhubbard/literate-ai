"""Bounded read-only GitHub metadata shared by native and release observers."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlsplit

from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.builders.python import BuildError


class GitHubObservationError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def read_json(
    root: Path, argv: tuple[str, ...], *, deadline: float, execute=None
) -> object:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise GitHubObservationError(
            "timeout", "GitHub observation exhausted its deadline"
        )
    try:
        completed = (execute or run_bounded_process)(
            argv,
            cwd=root,
            environment=dict(os.environ),
            timeout_seconds=min(60, remaining),
            stdout_limit_bytes=1024 * 1024,
            stderr_limit_bytes=64 * 1024,
            error_prefix="release_github_observation",
            terminate_descendants=True,
            trace=False,
        )
    except BuildError as exc:
        if exc.code.endswith("_output_limit"):
            code = "invalid"
        elif exc.code.endswith("_timeout"):
            code = "timeout"
        else:
            code = "unavailable"
        raise GitHubObservationError(
            code, "GitHub observation could not complete safely"
        ) from exc
    except OSError as exc:
        raise GitHubObservationError(
            "unavailable",
            "GitHub run polling requires an authenticated gh command",
        ) from exc
    if completed.returncode:
        raise GitHubObservationError(
            "unavailable",
            f"GitHub observation failed with exit status {completed.returncode}",
        )
    try:
        output = completed.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise GitHubObservationError("invalid", "GitHub response is not UTF-8") from exc

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate provider field")
            result[key] = value
        return result

    try:
        return json.loads(output, object_pairs_hook=unique_object)
    except ValueError as exc:
        raise GitHubObservationError(
            "invalid",
            "GitHub observation did not return unambiguous JSON",
        ) from exc


def workflow_runs(
    root: Path,
    repository: str,
    branch: str,
    revision: str,
    workflow: str = "CI",
    *,
    timeout_seconds: float = 60,
    execute=None,
    host: str | None = None,
    event: str | None = None,
) -> list[dict[str, object]]:
    """Return current attempts, newest run first, from a complete bounded set.

    Run numbers order executions within one workflow; attempts order retries of
    that same run. Response order and mutable timestamps grant no precedence.
    One extra row detects truncation; neither success nor completion is filtered.
    """
    deadline = time.monotonic() + timeout_seconds

    def invalid(message):
        raise GitHubObservationError("invalid", message)

    def positive(value):
        return type(value) is int and 0 < value < 2**63

    selector = f"{host}/{repository}" if host else repository
    workflows = read_json(
        root,
        (
            "gh",
            "workflow",
            "list",
            "--repo",
            selector,
            "--all",
            "--limit",
            "101",
            "--json",
            "id,name,path,state",
        ),
        deadline=deadline,
        execute=execute,
    )
    if not isinstance(workflows, list) or len(workflows) >= 101:
        invalid("GitHub workflow inventory is invalid or incomplete")
    matches = []
    workflow_ids = set()
    for row in workflows:
        if (
            not isinstance(row, dict)
            or not positive(row.get("id"))
            or any(
                not isinstance(row.get(key), str) or not 0 < len(row[key]) <= 4096
                for key in ("name", "path", "state")
            )
            or row["id"] in workflow_ids
        ):
            invalid("GitHub workflow identity is missing or ambiguous")
        workflow_ids.add(row["id"])
        if workflow in {
            str(row["id"]),
            row["name"],
            row["path"],
            Path(row["path"]).name,
        }:
            matches.append(row)
    if len(matches) != 1 or matches[0]["state"] != "active":
        invalid("Configured GitHub workflow is absent, ambiguous or inactive")
    workflow_id = matches[0]["id"]
    runs = read_json(
        root,
        (
            "gh",
            "run",
            "list",
            "--repo",
            selector,
            "--branch",
            branch,
            "--commit",
            revision,
            "--workflow",
            str(workflow_id),
            *(("--event", event) if event else ()),
            "--limit",
            "51",
            "--json",
            "databaseId,workflowDatabaseId,number,attempt,headSha,headBranch,"
            "status,conclusion,url,event",
        ),
        deadline=deadline,
        execute=execute,
    )
    if not isinstance(runs, list) or len(runs) >= 51:
        invalid("Exact-head GitHub run inventory is invalid or incomplete")
    pending = {"queued", "requested", "waiting", "pending", "in_progress"}
    conclusions = {
        "success",
        "failure",
        "neutral",
        "cancelled",
        "skipped",
        "timed_out",
        "action_required",
        "stale",
        "startup_failure",
    }
    numbers, identities, attempts = {}, {}, {}
    for row in runs:
        if not isinstance(row, dict) or any(
            not positive(row.get(key))
            for key in ("databaseId", "workflowDatabaseId", "number", "attempt")
        ):
            invalid("GitHub run lacks a positive workflow, run or attempt identity")
        if (
            row.get("headSha") != revision
            or row.get("headBranch") != branch
            or row["workflowDatabaseId"] != workflow_id
            or (event is not None and row.get("event") != event)
            or not isinstance(row.get("event"), str)
            or not 0 < len(row["event"]) <= 128
            or not isinstance(row.get("url"), str)
            or len(row["url"]) > 4096
        ):
            invalid("GitHub run does not match the selected source and workflow")
        try:
            url = urlsplit(row["url"])
            safe_url = (
                url.scheme == "https"
                and url.hostname
                and (host is None or url.hostname == host)
                and not url.username
                and not url.password
                and not url.query
                and not url.fragment
                and url.path == f"/{repository}/actions/runs/{row['databaseId']}"
            )
        except ValueError:
            safe_url = False
        if not safe_url:
            invalid("GitHub run URL does not identify its repository and run")
        status, conclusion = row.get("status"), row.get("conclusion")
        if (
            not isinstance(status, str)
            or (
                status == "completed"
                and (not isinstance(conclusion, str) or conclusion not in conclusions)
            )
            or (status in pending and conclusion not in (None, ""))
            or status not in pending | {"completed"}
        ):
            invalid("GitHub run has an invalid status/conclusion combination")
        number, run_id, attempt = row["number"], row["databaseId"], row["attempt"]
        if numbers.setdefault(number, run_id) != run_id:
            invalid("GitHub workflow run number identifies multiple runs")
        identity = (number, row["url"], row["event"])
        if identities.setdefault(run_id, identity) != identity:
            invalid("GitHub run identity changes between attempts")
        key = (run_id, attempt)
        if key in attempts and attempts[key] != row:
            invalid("GitHub reports conflicting versions of one attempt")
        attempts[key] = row
    latest = {}
    for row in attempts.values():
        previous = latest.get(row["databaseId"])
        if previous is None or row["attempt"] > previous["attempt"]:
            latest[row["databaseId"]] = row
    return sorted(latest.values(), key=lambda row: row["number"], reverse=True)


def run_identity(run: dict[str, object]) -> tuple[object, ...]:
    return tuple(
        run[key] for key in ("workflowDatabaseId", "number", "attempt", "databaseId")
    )
