"""Observe an explicit native CI contract without executing or promoting code."""

from __future__ import annotations

import math
import os
import time
from pathlib import Path

from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.builders.python import BuildError
from literate_ai.adapters.github_observation import (
    GitHubObservationError,
    read_json,
    run_identity,
    workflow_runs,
)
from literate_ai.adapters.native_project_bootstrap import _require_actual_git_scope
from literate_ai.application.project_tracker import (
    _repository_selector,
    exact_git_revision,
)
from literate_ai.contracts import canonical_identity
from literate_ai.projects import ProjectConfigurationStore, parse_project_configuration


class NativeCIError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = f"project.native_ci.{code}"
        self.message = message
        super().__init__(message)


def _invalid(message: str):
    raise NativeCIError("invalid", message)


def _positive(value: object) -> bool:
    return type(value) is int and 0 < value < 2**63


def _text(value: object, *, maximum: int = 256) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and value.strip() == value
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
    )


def _git(root: Path, deadline: float, *arguments: str) -> bytes:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise NativeCIError("timeout", "Native CI observation exhausted its deadline")
    result = run_bounded_process(
        (
            "git",
            "--no-optional-locks",
            "--no-replace-objects",
            "--no-lazy-fetch",
            "-C",
            str(root),
            *arguments,
        ),
        cwd=root,
        environment={
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        },
        timeout_seconds=min(30, remaining),
        stdout_limit_bytes=2 * 1024 * 1024,
        stderr_limit_bytes=64 * 1024,
        error_prefix="native_ci_git",
        terminate_descendants=True,
        trace=False,
    )
    if result.returncode:
        raise NativeCIError(
            "source_unavailable",
            "Native CI needs Git 2.45+ and readable local Git metadata and objects",
        )
    return result.stdout


def _git_text(root: Path, deadline: float, *arguments: str) -> str:
    content = _git(root, deadline, *arguments)
    assert content is not None
    try:
        return content.decode("utf-8", errors="strict").strip()
    except UnicodeError as exc:
        raise NativeCIError("source_invalid", "Git metadata is not UTF-8") from exc


def _api(root: Path, deadline: float, endpoint: str) -> object:
    return read_json(
        root,
        ("gh", "api", "--hostname", "github.com", "--method", "GET", endpoint),
        deadline=deadline,
    )


def _pull_request(value: object, number: int, repository: str) -> dict[str, object]:
    if (
        not isinstance(value, dict)
        or not _positive(value.get("number"))
        or value.get("number") != number
        or not _positive(value.get("id"))
    ):
        _invalid("GitHub omitted the selected PR identity")
    if value.get("state") != "open":
        raise NativeCIError("unsupported", "Native CI verification requires an open PR")
    result: dict[str, object] = {"number": number, "id": value["id"], "state": "open"}
    for side in ("base", "head"):
        row = value.get(side)
        if not isinstance(row, dict) or not isinstance(row.get("repo"), dict):
            _invalid("GitHub omitted the PR repository or revision")
        repo = row["repo"]
        if (
            not _text(repo.get("full_name"))
            or repo["full_name"].casefold() != repository.casefold()
            or not _positive(repo.get("id"))
        ):
            raise NativeCIError(
                "unsupported", "Only same-repository GitHub PRs are supported"
            )
        if not _text(row.get("ref")):
            _invalid("GitHub returned an invalid PR branch")
        try:
            revision = exact_git_revision(row.get("sha", ""))
        except (TypeError, ValueError) as exc:
            raise NativeCIError(
                "invalid", "GitHub returned an invalid PR revision"
            ) from exc
        result[side] = {
            "repository_id": repo["id"],
            "repository": repo["full_name"],
            "ref": row["ref"],
            "sha": revision,
        }
    if result["base"]["repository_id"] != result["head"]["repository_id"]:
        _invalid("The PR repository identity is inconsistent")
    return result


def _associated_run(value: object, selected: dict, pr: dict, workflow: str) -> None:
    if not isinstance(value, dict):
        _invalid("GitHub omitted the selected workflow run detail")
    expected = {
        "id": selected["databaseId"],
        "workflow_id": selected["workflowDatabaseId"],
        "run_number": selected["number"],
        "run_attempt": selected["attempt"],
        "head_sha": pr["head"]["sha"],
        "head_branch": pr["head"]["ref"],
        "event": "pull_request",
        "path": workflow,
        "status": selected["status"],
        "conclusion": selected["conclusion"] or None,
    }
    for key, expected_value in expected.items():
        actual = value.get(key)
        if key == "conclusion":
            actual = actual or None
        if type(expected_value) is int and not _positive(actual):
            _invalid("GitHub omitted the selected run identity")
        if actual != expected_value:
            raise NativeCIError(
                "stale", "The workflow run changed or does not match the PR contract"
            )
    associations = value.get("pull_requests")
    if not isinstance(associations, list) or len(associations) > 50:
        _invalid("GitHub PR associations are unavailable or incomplete")
    matches = [
        row
        for row in associations
        if isinstance(row, dict)
        and _positive(row.get("number"))
        and row.get("number") == pr["number"]
    ]
    if len(matches) != 1:
        _invalid("The workflow run is not uniquely associated with the selected PR")
    for side in ("base", "head"):
        row = matches[0].get(side)
        if (
            not isinstance(row, dict)
            or row.get("sha") != pr[side]["sha"]
            or row.get("ref") != pr[side]["ref"]
            or not isinstance(row.get("repo"), dict)
            or not _positive(row["repo"].get("id"))
            or row["repo"].get("id") != pr[side]["repository_id"]
        ):
            raise NativeCIError(
                "stale", "The run's PR source/base association is stale"
            )


def _jobs(
    root: Path, deadline: float, repository: str, selected: dict, revision: str
) -> list[dict]:
    from literate_ai.adapters.github_observation import workflow_jobs

    return workflow_jobs(root, deadline, repository, selected, revision)


def _verify_project_ci(
    path: Path, *, pull_request: int, timeout_seconds: float
) -> dict:
    if not _positive(pull_request):
        raise NativeCIError("argument", "A positive PR number is required")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 300
    ):
        raise NativeCIError(
            "argument", "Observation timeout must be between zero and 300 seconds"
        )
    deadline = time.monotonic() + timeout_seconds
    _require_actual_git_scope()
    snapshot = ProjectConfigurationStore.discover(path)
    if snapshot is None or snapshot.definition.framework_directory != "litai":
        raise NativeCIError("profile", "Select a contained native project")
    root = snapshot.root
    manifest = snapshot.manifest_path.relative_to(root).as_posix()
    head = exact_git_revision(_git_text(root, deadline, "rev-parse", "HEAD^{commit}"))
    if (
        Path(_git_text(root, deadline, "rev-parse", "--show-toplevel")).resolve()
        != root
    ):
        raise NativeCIError("profile", "Select the actual application Git root")
    if _git(root, deadline, "status", "--porcelain=v1", "-z", "--untracked-files=all"):
        raise NativeCIError(
            "dirty", "Commit or resolve local changes before CI verification"
        )
    if _git(root, deadline, "show", f"{head}:{manifest}") != snapshot.content:
        raise NativeCIError(
            "dirty", "The local contained policy differs from the committed source"
        )
    current_policy = snapshot.definition.repository_policy
    remote = _git_text(root, deadline, "remote", "get-url", current_policy.remote)
    selector = _repository_selector(remote, "github")
    if selector is None or not selector.startswith("github.com/"):
        raise NativeCIError(
            "unsupported", "The configured remote must identify github.com"
        )
    repository = selector.removeprefix("github.com/")
    endpoint = f"repos/{repository}/pulls/{pull_request}"
    pr = _pull_request(_api(root, deadline, endpoint), pull_request, repository)
    repository = pr["base"]["repository"]
    endpoint = f"repos/{repository}/pulls/{pull_request}"
    if pr["head"]["sha"] != head:
        raise NativeCIError("stale", "Local HEAD differs from the PR head")
    base_revision = pr["base"]["sha"]
    # Missing base objects are unknown; observation never fetches them.
    _git(root, deadline, "cat-file", "-e", f"{base_revision}^{{commit}}")
    entry = _git(
        root, deadline, "ls-tree", "-z", "--full-tree", base_revision, "--", manifest
    )
    base_bytes = None
    if entry:
        rows = entry.split(b"\0")
        if len(rows) != 2 or rows[-1]:
            _invalid("The base policy tree entry is ambiguous")
        metadata, separator, name = rows[0].partition(b"\t")
        fields = metadata.split(b" ")
        if (
            separator != b"\t"
            or name != manifest.encode("utf-8")
            or len(fields) != 3
            or fields[0] not in {b"100644", b"100755"}
            or fields[1] != b"blob"
        ):
            _invalid("The base policy must be one regular Git blob")
        blob = exact_git_revision(fields[2].decode("ascii", errors="strict"))
        base_bytes = _git(root, deadline, "cat-file", "blob", blob)
    policy = None
    if base_bytes is not None:
        definition = parse_project_configuration(base_bytes)
        if (
            definition.framework_directory != "litai"
            or definition.project_id != snapshot.definition.project_id
        ):
            raise NativeCIError(
                "profile", "Base and head do not name the same contained project"
            )
        if definition.repository_policy.remote != current_policy.remote:
            raise NativeCIError("stale", "The PR changes the selected policy remote")
        policy = definition.repository_policy.native_ci
    report = {
        "schema": "literate-ai/native-ci-observation@1",
        "observation_status": "unconfigured",
        "expectation_source": "configured_fallback",
        "forge": "github.com",
        "repository": repository,
        "remote": current_policy.remote,
        "pull_request": pr,
        "local_head": head,
        "policy_source_revision": base_revision,
        "policy_identity": canonical_identity(policy.to_dict()).uri if policy else None,
        "head_policy_changed": policy != current_policy.native_ci,
        "associated_source_revision": head,
        "tested_tree_revision": None,
        "admitted": False,
        "release_qualification": False,
        "merge_readiness": "not_assessed",
        "platform_coverage": "not_assessed",
        "run": None,
        "required_jobs": [],
        "limitations": [
            "Configured CI contract only; forge merge requirements are not inferred.",
            "Job metadata associates a PR head, not a checkout tree or artifacts.",
            "The base policy governs this PR; initial policy needs native review.",
        ],
    }
    if policy is None:
        return report
    rows = workflow_runs(
        root,
        repository,
        pr["head"]["ref"],
        head,
        policy.workflow,
        timeout_seconds=max(0, deadline - time.monotonic()),
        host="github.com",
        event="pull_request",
    )
    selected = rows[0] if rows else None
    if selected is None:
        report["observation_status"] = "incomplete"
        return report
    run_endpoint = f"repos/{repository}/actions/runs/{selected['databaseId']}"
    _associated_run(_api(root, deadline, run_endpoint), selected, pr, policy.workflow)
    jobs = _jobs(root, deadline, repository, selected, head)
    required = []
    for name in policy.required_jobs:
        candidates = [row for row in jobs if row["name"] == name]
        latest = max((row["run_attempt"] for row in candidates), default=0)
        matches = [row for row in candidates if row["run_attempt"] == latest]
        if len(matches) > 1:
            _invalid("A required job name identifies multiple jobs in one attempt")
        row = matches[0] if matches else None
        state = (
            "missing"
            if row is None
            else (
                "success"
                if row["status"] == "completed" and row["conclusion"] == "success"
                else "pending"
                if row["status"] != "completed"
                else row["conclusion"]
            )
        )
        # Whole reruns are observed. Partial retry still needs a native pilot.
        if row is not None and row["run_attempt"] != selected["attempt"]:
            state = "partial_retry_unverified"
        required.append({"name": name, "observation_status": state, "job": row})
    closing = workflow_runs(
        root,
        repository,
        pr["head"]["ref"],
        head,
        policy.workflow,
        timeout_seconds=max(0, deadline - time.monotonic()),
        host="github.com",
        event="pull_request",
    )
    if (
        not closing
        or closing[0] != selected
        or run_identity(closing[0]) != run_identity(selected)
    ):
        raise NativeCIError(
            "stale", "The selected CI run or attempt changed during observation"
        )
    if _pull_request(_api(root, deadline, endpoint), pull_request, repository) != pr:
        raise NativeCIError("stale", "The PR changed during observation")
    if (
        ProjectConfigurationStore(root).read() != snapshot
        or _git_text(root, deadline, "rev-parse", "HEAD^{commit}") != head
        or _git_text(root, deadline, "remote", "get-url", current_policy.remote)
        != remote
        or _git(
            root, deadline, "status", "--porcelain=v1", "-z", "--untracked-files=all"
        )
    ):
        raise NativeCIError(
            "stale", "Local source or policy changed during observation"
        )
    states = {row["observation_status"] for row in required}
    status = (
        "pending"
        if selected["status"] != "completed"
        else "failed"
        if selected["conclusion"] != "success"
        else "verified"
        if states == {"success"}
        else "incomplete"
        if states & {"missing", "partial_retry_unverified"}
        else "pending"
        if "pending" in states
        else "failed"
    )
    report.update(observation_status=status, run=selected, required_jobs=required)
    return report


def verify_project_ci(
    path: Path, *, pull_request: int, timeout_seconds: float = 60
) -> dict:
    try:
        return _verify_project_ci(
            path, pull_request=pull_request, timeout_seconds=timeout_seconds
        )
    except GitHubObservationError as exc:
        raise NativeCIError(exc.code, str(exc)) from exc
    except BuildError as exc:
        code = "timeout" if exc.code.endswith("_timeout") else "unavailable"
        raise NativeCIError(
            code, "Native CI metadata could not be collected safely"
        ) from exc
    except (OSError, ValueError, TypeError) as exc:
        raise NativeCIError(
            "invalid", "Native CI source or metadata is invalid"
        ) from exc
