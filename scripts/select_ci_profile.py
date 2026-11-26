"""Select explicit, fail-closed CI feedback from the exact changed paths."""

from __future__ import annotations

import json
import os
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from typing import NamedTuple

_DOCUMENTATION_FILES = frozenset(
    {
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "PROJECT.md",
        "README.md",
        "labs/README.md",
        "scripts/build_conference_site.mjs",
        "scripts/verify_conference_browser.mjs",
        "verification/1.3.1-release-publication.json",
        "verification/1.3.1-windows-qualification-exception.json",
    }
)
_DOCUMENTATION_PREFIXES = ("docs/",)
_CI_WORKFLOW = ".github/workflows/ci.yml"
_SDK_WORKFLOW = ".github/workflows/native-sdk-qualification.yml"
_CI_MATRIX = ".github/ci-matrix.json"
_CI_POLICY_FILES = frozenset(
    {
        _CI_MATRIX,
        _CI_WORKFLOW,
        "scripts/select_ci_profile.py",
        "tests/critical/test_ci_action_pins.py",
        _SDK_WORKFLOW,
        ".github/qualifications/native_sdk/qualify_public_sdk.py",
        ".github/qualifications/native_sdk/source_transport.py",
        ".github/qualifications/native_sdk/run_cell.py",
        ".github/qualifications/native_sdk/collect_results.py",
        "tests/critical/test_native_sdk_qualification_harness.py",
        "verification/freebsd-native-sdk-qualification.json",
    }
)
_QUALIFICATION_FIXTURE_FILES = frozenset(
    {
        "tests/critical/test_roadmap_dependencies.py",
        "tests/critical/test_retained_posix_acl.py",
        "verification/windows-portable-fixtures-qualification.json",
    }
)
_SCHEMA_PREFLIGHT_FILES = frozenset(
    {
        _CI_WORKFLOW,
        "Makefile",
        "pyproject.toml",
        "scripts/select_ci_profile.py",
        "src/literate_ai/cli/dispatch.py",
        "src/literate_ai/schema_catalog.py",
        "src/literate_ai/version.py",
        "src/literate_ai/version_check.py",
    }
)
_FREEBSD_ACL_FILES = frozenset(
    {
        _CI_WORKFLOW,
        "src/literate_ai/adapters/retained_posix_acl.py",
        "src/literate_ai/adapters/retained_project_execution.py",
        "tests/critical/test_retained_posix_acl.py",
        "tests/critical/test_retained_project_execution.py",
    }
)
_ELIXIR_PREFIXES = (
    "flavors/build-mix/",
    "flavors/lang-elixir/",
    "scripts/stage_elixir_",
    "skills/specification-to-source/elixir-portable-application/",
    "skills/specification-to-source/mix-build-system/",
    "src/literate_ai/adapters/builders/elixir.py",
    "src/literate_ai/adapters/builders/hex.py",
    "src/literate_ai/adapters/builders/mix",
    "src/literate_ai/adapters/lifecycle/standard_mix.py",
    "src/literate_ai/adapters/qualification_mix.py",
    "src/literate_ai/contracts/elixir_libraries.py",
    "src/literate_ai/contracts/mix_projects.py",
    "src/literate_ai/source_to_specification/builtin_skills/language-elixir/",
)


def _documentation_manifest_change() -> bool:
    """Only an exact documentation-roots-only JSON edit is documentation scope."""
    base = os.environ.get("CI_BASE_SHA", "")
    head = os.environ.get("CI_HEAD_SHA", "")
    if not base or not head:
        return False
    try:
        manifests = []
        for revision in (base, head):
            result = subprocess.run(
                ("git", "show", f"{revision}:literate.project.json"),
                check=False,
                capture_output=True,
                timeout=30,
            )
            if result.returncode:
                return False

            def unique_object(pairs):
                value = {}
                for key, item in pairs:
                    if key in value:
                        raise ValueError("duplicate manifest key")
                    value[key] = item
                return value

            value = json.loads(result.stdout, object_pairs_hook=unique_object)
            if not isinstance(value, dict):
                return False
            roots = value.pop("documentation_roots")
            if (
                not isinstance(roots, list)
                or not roots
                or not all(isinstance(p, str) for p in roots)
            ):
                return False
            manifests.append((value, roots))
        return manifests[0][0] == manifests[1][0] and manifests[0][1] != manifests[1][1]
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return False


def _scope(path: str) -> str | None:
    if path in _DOCUMENTATION_FILES or path.startswith(_DOCUMENTATION_PREFIXES):
        return "documentation"
    if path in _CI_POLICY_FILES:
        return "ci-policy"
    if path == "literate.project.json" and _documentation_manifest_change():
        return "documentation"
    if path.startswith("labs/") or path == "verification/unprompted-ai-labs-1.3.1.json":
        return "labs"
    if path in _QUALIFICATION_FIXTURE_FILES:
        return "qualification-fixtures"
    if path.startswith(_ELIXIR_PREFIXES) or "test_elixir" in path:
        return "elixir"
    return None


def _changed_paths(base_sha: str, head_sha: str) -> tuple[str, ...] | None:
    """Compare exact endpoints selected for the event."""

    if not base_sha or not head_sha:
        return None
    try:
        completed = subprocess.run(
            ("git", "diff", "--no-renames", "--name-only", "-z", base_sha, head_sha),
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return tuple(
            item.decode("utf-8") for item in completed.stdout.split(b"\0") if item
        )
    except UnicodeDecodeError:
        return None


class WorkflowDelta(NamedTuple):
    tasks: frozenset[str] = frozenset()
    broad: bool = False
    freebsd_acl: bool = False
    freebsd_sdk: bool = False


def _workflow_versions(path: str) -> tuple[str, str] | None:
    base = os.environ.get("CI_BASE_SHA", "")
    head = os.environ.get("CI_HEAD_SHA", "")
    if not base or not head:
        return None
    try:
        versions = []
        for revision in (base, head):
            result = subprocess.run(
                ("git", "show", f"{revision}:{path}"),
                check=False,
                capture_output=True,
                timeout=30,
            )
            if result.returncode:
                return None
            versions.append(result.stdout.decode("utf-8"))
        return versions[0], versions[1]
    except (OSError, UnicodeDecodeError, subprocess.TimeoutExpired):
        return None


def _workflow_parts(text: str) -> tuple[str, dict[str, str]] | None:
    """Split the checked-in block layout without interpreting YAML expressions."""
    if re.search(r"(?m)(?:^|\s)[&*][A-Za-z0-9_-]+|^ *\t", text):
        return None
    preamble, separator, body = text.partition("\njobs:\n")
    if not separator:
        if not text.startswith("jobs:\n"):
            return None
        preamble, body = "", text.removeprefix("jobs:\n")
    if re.search(r"(?m)^[^ #\n]", body):
        return None
    headers = list(re.finditer(r"(?m)^  ([a-zA-Z0-9_-]+): *$", body))
    if not headers or re.search(r"(?m)^  [^ #\n]", body[: headers[0].start()]):
        return None
    jobs = {}
    for index, header in enumerate(headers):
        name = header[1]
        end = headers[index + 1].start() if index + 1 < len(headers) else len(body)
        if name in jobs:
            return None
        job = body[header.start() : end]
        if re.search(r"(?m)^  [^ #\n]", job[header.end() - header.start() :]):
            return None
        jobs[name] = job
    return preamble + body[: headers[0].start()], jobs


def _changed_matrix_tasks(before: str, after: str) -> frozenset[str] | None:
    """Cover both sides of changed steps with a proved matrix task guard."""
    sections = [job.partition("\n    steps:\n") for job in (before, after)]
    if sections[0][:2] != sections[1][:2] or not sections[0][1]:
        return None
    if any(
        not line.startswith(("      - ", "        "))
        for section in sections
        for line in section[2].splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ):
        return None
    steps = [re.split(r"(?m)(?=^      - )", section[2]) for section in sections]
    if steps[0][0] != steps[1][0]:
        return None
    left, right = (blocks[1:] for blocks in steps)
    tasks = set()
    for tag, start, end, new_start, new_end in SequenceMatcher(
        None, left, right, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        for block in (*left[start:end], *right[new_start:new_end]):
            expressions = re.findall(r"(?m)^        if: (.+)$", block)
            if len(expressions) != 1:
                return None
            match = re.fullmatch(
                r"matrix\.task == '([a-z0-9-]+)'"
                r"(?: && (?:\((?:always|failure)\(\)\)"
                r"|\(runner\.os (?:==|!=) '[A-Za-z]+'\)"
                r"|matrix\.group == [0-9]+))?",
                expressions[0],
            )
            if not match:
                return None
            tasks.add(match[1])
    return frozenset(tasks)


def _ci_workflow_delta(versions: tuple[str, str] | None) -> WorkflowDelta:
    if versions is None:
        return WorkflowDelta(broad=True, freebsd_acl=True)
    before, after = map(_workflow_parts, versions)
    if before is None or after is None:
        return WorkflowDelta(broad=True, freebsd_acl=True)
    prior_header, prior_jobs = before
    new_header, new_jobs = after
    local_jobs = {"checks", "freebsd-posix-acl"}
    if (
        prior_header != new_header
        or prior_jobs.keys() != new_jobs.keys()
        or any(
            prior_jobs[job] != new_jobs[job] for job in prior_jobs.keys() - local_jobs
        )
    ):
        return WorkflowDelta(broad=True, freebsd_acl=True)
    acl_changed = prior_jobs.get("freebsd-posix-acl") != new_jobs.get(
        "freebsd-posix-acl"
    )
    if prior_jobs.get("checks") == new_jobs.get("checks"):
        return WorkflowDelta(freebsd_acl=acl_changed)
    tasks = _changed_matrix_tasks(prior_jobs["checks"], new_jobs["checks"])
    if tasks is None:
        return WorkflowDelta(broad=True, freebsd_acl=True)
    return WorkflowDelta(tasks=tasks, freebsd_acl=acl_changed)


def _workflow_delta(changed_paths: tuple[str, ...] | None) -> WorkflowDelta:
    paths = changed_paths or ()
    delta = (
        _ci_workflow_delta(_workflow_versions(_CI_WORKFLOW))
        if _CI_WORKFLOW in paths
        else WorkflowDelta()
    )
    unknown_workflow = any(
        path.startswith(".github/workflows/") and path not in _CI_POLICY_FILES
        for path in paths
    )
    known_tasks = {row["task"] for row in _matrix_rows()} if delta.tasks else set()
    if _CI_MATRIX in paths or unknown_workflow or delta.tasks - known_tasks:
        delta = delta._replace(broad=True, freebsd_acl=True)
    if _SDK_WORKFLOW in paths:
        versions = _workflow_versions(_SDK_WORKFLOW)
        # Keep top-level name and comment edits in policy feedback. Other edits
        # can change the action, inputs or the environment the SDK job inherits.
        sdk_changed = versions is None or _sdk_runtime(versions[0]) != _sdk_runtime(
            versions[1]
        )
        delta = delta._replace(freebsd_sdk=sdk_changed)
    return delta


def _sdk_runtime(text: str) -> tuple[str, ...]:
    return tuple(
        line for line in text.splitlines() if not line.startswith(("#", "name: "))
    )


def _scoped_main_push(event: str, base_ref: str, scopes: set[str | None]) -> bool:
    return (
        event == "push"
        and base_ref == "refs/heads/main"
        and bool(scopes)
        and scopes <= {"documentation", "ci-policy", "qualification-fixtures", "labs"}
    )


def _ordinary_pr(event: str, base_ref: str) -> bool:
    return event == "pull_request" and not base_ref.startswith("release/")


def _matrix_rows() -> list[dict]:
    return json.loads((Path(__file__).resolve().parents[1] / _CI_MATRIX).read_text())


def select_matrix(
    event: str,
    base_ref: str,
    changed_paths: tuple[str, ...] | None = None,
    *,
    delta: WorkflowDelta | None = None,
) -> dict:
    rows = _matrix_rows()
    scopes = {_scope(path) for path in changed_paths or ()}
    ordinary_pr = _ordinary_pr(event, base_ref)
    main_push = event == "push" and base_ref == "refs/heads/main"
    if not ordinary_pr and not main_push:
        return {"include": [row for row in rows if "scoped" not in row]}

    delta = delta if delta is not None else _workflow_delta(changed_paths)
    if main_push and not _scoped_main_push(event, base_ref, scopes):
        return {
            "include": [
                row for row in rows if "scoped" not in row or row["task"] in delta.tasks
            ]
        }
    if delta.broad:
        return {
            "include": [
                row for row in rows if "scoped" not in row or row["scoped"] in scopes
            ]
        }

    tasks = delta.tasks
    if "elixir" in scopes and None not in scopes:
        tasks = tasks | {"elixir-native"}
    scoped = bool(scopes) and None not in scopes
    return {
        "include": [
            row
            for row in rows
            if row["task"] in tasks
            or (row["pr"] and (not scoped or "elixir" in scopes))
            or (
                row.get("scoped") in scopes - {None}
                and (
                    scoped
                    or row.get("scoped") == "qualification-fixtures"
                    or (row.get("scoped") == "ci-policy" and delta.tasks)
                )
            )
        ]
    }


def select_full_qualification(
    event: str,
    base_ref: str,
    changed_paths: tuple[str, ...] | None = None,
    *,
    delta: WorkflowDelta | None = None,
) -> bool:
    scopes = {_scope(path) for path in changed_paths or ()}
    if not _ordinary_pr(event, base_ref) and not _scoped_main_push(
        event, base_ref, scopes
    ):
        return True
    delta = delta if delta is not None else _workflow_delta(changed_paths)
    return delta.broad


def select_schema_preflight(
    event: str,
    base_ref: str,
    changed_paths: tuple[str, ...] | None = None,
    *,
    delta: WorkflowDelta | None = None,
) -> bool:
    """Check schema inputs once before qualification fans out."""
    return (
        changed_paths is None
        or any(
            path in _SCHEMA_PREFLIGHT_FILES
            or path.startswith(("schemas/", "tools/build_backend/"))
            for path in changed_paths
        )
        or select_full_qualification(event, base_ref, changed_paths, delta=delta)
    )


def select_freebsd_acl(
    event: str,
    base_ref: str,
    changed_paths: tuple[str, ...] | None = None,
    *,
    delta: WorkflowDelta | None = None,
) -> bool:
    """Run the privileged ACL probe only where it can qualify the change."""
    scopes = {_scope(path) for path in changed_paths or ()}
    if not _ordinary_pr(event, base_ref) and not _scoped_main_push(
        event, base_ref, scopes
    ):
        return True
    if not changed_paths:
        return True
    delta = delta if delta is not None else _workflow_delta(changed_paths)
    return delta.freebsd_acl or any(
        path in _FREEBSD_ACL_FILES - {_CI_WORKFLOW} for path in changed_paths
    )


def _merge_base(base: str, head: str) -> str:
    if not base or not head:
        return ""
    try:
        found = subprocess.run(
            ("git", "merge-base", "--all", base, head),
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    revision = found.stdout.strip()
    if found.returncode or not re.fullmatch(rb"[0-9a-f]{40}", revision):
        return ""
    return revision.decode("ascii")


if __name__ == "__main__":
    event = os.environ["CI_EVENT"]
    base_ref = os.environ.get("CI_BASE_REF", "")
    paths = None
    ordinary_pr = _ordinary_pr(event, base_ref)
    ordinary_push = event == "push" and base_ref == "refs/heads/main"
    if ordinary_pr or ordinary_push:
        base = os.environ.get("CI_BASE_SHA", "")
        head = os.environ.get("CI_HEAD_SHA", "")
        if ordinary_pr:
            base = _merge_base(base, head)
            os.environ["CI_BASE_SHA"] = base
        paths = _changed_paths(base, head)
    delta = _workflow_delta(paths)
    if ordinary_pr and paths is None:
        delta = delta._replace(broad=True)
    matrix = select_matrix(event, base_ref, paths, delta=delta)
    print("matrix=" + json.dumps(matrix, separators=(",", ":")))
    print(
        "freebsd_acl="
        + str(select_freebsd_acl(event, base_ref, paths, delta=delta)).lower()
    )
    print("freebsd_sdk=" + str(delta.freebsd_sdk).lower())
    print(
        "full_qualification="
        + str(select_full_qualification(event, base_ref, paths, delta=delta)).lower()
    )
    print(
        "schema_preflight="
        + str(select_schema_preflight(event, base_ref, paths, delta=delta)).lower()
    )
