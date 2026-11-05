"""Read-only, commit-bound planning for a separate upstream shadow repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from .errors import CliFailure

_MAX_BRANCHES = 32
_MAX_REF_CHARS = 200
_MAX_PR_BYTES = 256 * 1024
_HEX_COMMIT = re.compile(r"[0-9a-f]{40,64}\Z")
_GITHUB_SSH = re.compile(
    r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?\Z"
)
_GITHUB_HTTPS = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?\Z"
)


def _git(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *arguments],
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1"},
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise CliFailure(
            "shadow.git_unavailable", "Git inspection did not complete"
        ) from exc
    if result.returncode:
        raise CliFailure(
            "shadow.git_invalid", "Git could not resolve the requested upstream state"
        )
    if len(result.stdout) > 4096:
        raise CliFailure(
            "shadow.git_unbounded", "Git inspection exceeded its output bound"
        )
    return result.stdout.strip()


def _forge_identity(remote: str) -> dict[str, str]:
    match = _GITHUB_SSH.fullmatch(remote) or _GITHUB_HTTPS.fullmatch(remote)
    if match is None or any(part in {".", ".."} for part in match.groups()):
        raise CliFailure(
            "shadow.forge_unsupported",
            "The upstream origin must be a credential-free GitHub SSH "
            "or HTTPS repository URL",
        )
    owner, repository = match.groups()
    return {"host": "github.com", "owner": owner, "repository": repository}


def _branch_commit(root: Path, branch: str) -> str:
    if not branch or len(branch) > _MAX_REF_CHARS or branch.startswith("-"):
        raise CliFailure(
            "shadow.branch_invalid",
            "The branch name is empty or outside its finite bound",
        )
    _git(root, "check-ref-format", "--branch", branch)
    commit = _git(root, "rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}")
    if _HEX_COMMIT.fullmatch(commit) is None:
        raise CliFailure(
            "shadow.object_invalid", "The selected branch did not resolve to one commit"
        )
    return commit


def _upstream_root(value: str) -> Path:
    source = Path(value).expanduser()
    if source.is_symlink() or not source.is_dir():
        raise CliFailure(
            "shadow.upstream_invalid",
            "The upstream must be a real repository directory",
        )
    upstream = source.resolve(strict=True)
    if (
        Path(_git(upstream, "rev-parse", "--show-toplevel")).resolve(strict=True)
        != upstream
    ):
        raise CliFailure(
            "shadow.upstream_invalid", "Select the upstream repository root"
        )
    return upstream


def _plan_identity(body: dict[str, object]) -> dict[str, object]:
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    body["plan_identity"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return body


def plan_shadow(args: argparse.Namespace) -> dict[str, object]:
    upstream = _upstream_root(args.upstream)
    destination = Path(args.shadow).expanduser()
    if destination.is_symlink() or destination.exists():
        raise CliFailure(
            "shadow.destination_exists", "The shadow destination must not exist"
        )
    shadow = destination.resolve(strict=False)
    if shadow == upstream or upstream in shadow.parents or shadow in upstream.parents:
        raise CliFailure(
            "shadow.destination_unsafe",
            "The shadow and upstream must be separate trees",
        )
    if args.branch and len(args.branch) > _MAX_BRANCHES:
        raise CliFailure("shadow.branches_unbounded", "Too many selected branches")
    branches = args.branch or ["main"]
    if len(set(branches)) != len(branches):
        raise CliFailure("shadow.branch_duplicate", "A selected branch is repeated")
    forge = _forge_identity(
        _git(upstream, "config", "--local", "--get", "remote.origin.url")
    )
    selected = [
        {"ref": f"refs/heads/{branch}", "commit": _branch_commit(upstream, branch)}
        for branch in branches
    ]
    body: dict[str, object] = {
        "schema": "literate-ai/shadow-create-plan@1",
        "upstream": str(upstream),
        "forge": forge,
        "shadow": str(shadow),
        "branches": selected,
        "effect": "read-only; no shadow repository was created",
    }
    return _plan_identity(body)


def _github_pr(forge: dict[str, str], number: int) -> dict[str, object]:
    route = f"repos/{forge['owner']}/{forge['repository']}/pulls/{number}"
    try:
        result = subprocess.run(
            ["gh", "api", "--method", "GET", route],
            env={**os.environ, "GH_PROMPT_DISABLED": "1"},
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CliFailure(
            "shadow.forge_unavailable", "Forge PR inspection did not complete"
        ) from exc
    if result.returncode or len(result.stdout) > _MAX_PR_BYTES:
        raise CliFailure(
            "shadow.forge_unavailable",
            "Forge PR inspection failed or exceeded its bound",
        )
    try:
        value = json.loads(result.stdout)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CliFailure(
            "shadow.forge_invalid", "Forge PR response was not valid JSON"
        ) from exc
    if not isinstance(value, dict):
        raise CliFailure("shadow.forge_invalid", "Forge PR response was not an object")
    return value


def plan_shadow_pr(args: argparse.Namespace) -> dict[str, object]:
    if args.number <= 0 or args.number > 10_000_000:
        raise CliFailure(
            "shadow.pr_number_invalid", "PR number is outside its finite bound"
        )
    upstream = _upstream_root(args.upstream)
    forge = _forge_identity(
        _git(upstream, "config", "--local", "--get", "remote.origin.url")
    )
    pr = _github_pr(forge, args.number)
    try:
        base, head = pr["base"], pr["head"]
        base_repo, head_repo = base["repo"]["full_name"], head["repo"]["full_name"]
        base_ref, head_ref = base["ref"], head["ref"]
        base_commit, head_commit = base["sha"], head["sha"]
        pr_id, number, state = pr["id"], pr["number"], pr["state"]
    except (KeyError, TypeError) as exc:
        raise CliFailure(
            "shadow.forge_invalid", "Forge PR identity is incomplete"
        ) from exc
    if (
        state != "open"
        or isinstance(number, bool)
        or number != args.number
        or isinstance(pr_id, bool)
        or not isinstance(pr_id, int)
        or pr_id <= 0
        or not isinstance(base_repo, str)
        or base_repo.casefold() != f"{forge['owner']}/{forge['repository']}".casefold()
        or not isinstance(head_repo, str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", head_repo)
        or not isinstance(base_commit, str)
        or not isinstance(head_commit, str)
        or not _HEX_COMMIT.fullmatch(base_commit)
        or not _HEX_COMMIT.fullmatch(head_commit)
        or not isinstance(base_ref, str)
        or not isinstance(head_ref, str)
        or len(head_ref) > _MAX_REF_CHARS
    ):
        raise CliFailure(
            "shadow.forge_invalid", "Forge PR identity is invalid or closed"
        )
    local_base = _branch_commit(upstream, base_ref)
    if local_base != base_commit:
        raise CliFailure(
            "shadow.pr_base_stale",
            "Local target branch differs from the current PR base",
        )
    try:
        head_available = _git(upstream, "cat-file", "-t", head_commit) == "commit"
    except CliFailure as exc:
        if exc.code != "shadow.git_invalid":
            raise
        head_available = False
    body: dict[str, object] = {
        "schema": "literate-ai/shadow-pr-plan@1",
        "upstream": str(upstream),
        "forge": forge,
        "pull_request": {
            "id": pr_id,
            "number": number,
            "base_ref": f"refs/heads/{base_ref}",
            "base_commit": base_commit,
            "head_repository": head_repo,
            "head_ref": head_ref,
            "head_commit": head_commit,
            "head_object_available": head_available,
        },
        "effect": "read-only; no PR lane was created or qualified",
    }
    return _plan_identity(body)


def add_shadow_parser(commands: argparse._SubParsersAction) -> None:
    shadow = commands.add_parser(
        "shadow", help="plan a separate upstream shadow repository"
    )
    actions = shadow.add_subparsers(dest="shadow_command", required=True)
    plan = actions.add_parser(
        "plan", help="inspect exact local Git refs without fetching or writing"
    )
    plan.add_argument(
        "--upstream", required=True, help="local upstream Git repository root"
    )
    plan.add_argument("--shadow", required=True, help="new separate shadow destination")
    plan.add_argument(
        "--branch", action="append", help="selected upstream branch; defaults to main"
    )
    pr = actions.add_parser(
        "pr-plan", help="bind a GitHub PR base and head without fetching or writing"
    )
    pr.add_argument(
        "--upstream", required=True, help="local upstream Git repository root"
    )
    pr.add_argument(
        "--number", required=True, type=int, help="positive pull request number"
    )


__all__ = ["add_shadow_parser", "plan_shadow", "plan_shadow_pr"]
