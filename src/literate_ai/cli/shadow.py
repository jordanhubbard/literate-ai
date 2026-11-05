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


def plan_shadow(args: argparse.Namespace) -> dict[str, object]:
    source = Path(args.upstream).expanduser()
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
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    body["plan_identity"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    return body


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


__all__ = ["add_shadow_parser", "plan_shadow"]
