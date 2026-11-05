"""Read-only, commit-bound planning for a separate upstream shadow repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from .errors import CliFailure

_MAX_BRANCHES = 32
_MAX_REF_CHARS = 200
_MAX_PR_BYTES = 256 * 1024
_MAX_BUNDLE_BYTES = 128 * 1024 * 1024
_HEX_COMMIT = re.compile(r"[0-9a-f]{40,64}\Z")
_GITHUB_SSH = re.compile(
    r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?\Z"
)
_GITHUB_HTTPS = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?\Z"
)


def _git(root: Path, *arguments: str, timeout: int = 10) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *arguments],
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1"},
            capture_output=True,
            text=True,
            timeout=timeout,
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


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _create_bounded_bundle(upstream: Path, bundle: Path, refs: list[str]) -> None:
    try:
        process = subprocess.Popen(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(upstream),
                "bundle",
                "create",
                str(bundle),
                *refs,
            ],
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise CliFailure(
            "shadow.git_unavailable", "Bundle creation could not start"
        ) from exc
    deadline = time.monotonic() + 90
    try:
        while process.poll() is None:
            if time.monotonic() >= deadline:
                raise CliFailure(
                    "shadow.bundle_timeout", "Bundle creation exceeded its time bound"
                )
            if bundle.exists() and bundle.stat().st_size > _MAX_BUNDLE_BYTES:
                raise CliFailure(
                    "shadow.bundle_unbounded", "Upstream bundle exceeds its size bound"
                )
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
        if process.returncode or not bundle.is_file():
            raise CliFailure(
                "shadow.bundle_invalid", "Git could not create the source bundle"
            )
        if bundle.stat().st_size > _MAX_BUNDLE_BYTES:
            raise CliFailure(
                "shadow.bundle_unbounded", "Upstream bundle exceeds its size bound"
            )
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise


def create_shadow(args: argparse.Namespace) -> dict[str, object]:
    """Custody exact initial refs in a separate Git repository after plan review."""
    if not args.acknowledge:
        raise CliFailure(
            "shadow.acknowledgement_required", "Creation requires --acknowledge"
        )
    plan = plan_shadow(args)
    if args.expect_plan != plan["plan_identity"]:
        raise CliFailure(
            "shadow.plan_stale", "Current upstream state differs from the reviewed plan"
        )
    upstream = Path(str(plan["upstream"]))
    destination = Path(str(plan["shadow"]))
    parent = destination.parent
    if not parent.is_dir() or parent.is_symlink():
        raise CliFailure(
            "shadow.parent_invalid",
            "The shadow parent must be an existing real directory",
        )
    with tempfile.TemporaryDirectory(prefix=".shadow-stage-", dir=parent) as temporary:
        bundle = Path(temporary) / "source.bundle"
        selected = plan["branches"]
        refs = [str(item["ref"]) for item in selected]
        _create_bounded_bundle(upstream, bundle, refs)
        observed = {}
        for line in _git(upstream, "bundle", "list-heads", str(bundle)).splitlines():
            commit, separator, ref = line.partition(" ")
            if not separator or not _HEX_COMMIT.fullmatch(commit):
                raise CliFailure(
                    "shadow.bundle_invalid", "Bundle head identity is invalid"
                )
            observed[ref] = commit
        if observed != {str(item["ref"]): str(item["commit"]) for item in selected}:
            raise CliFailure(
                "shadow.plan_stale", "Upstream refs changed while creating the bundle"
            )
        _git(upstream, "bundle", "verify", str(bundle), timeout=90)
        if plan_shadow(args)["plan_identity"] != args.expect_plan:
            raise CliFailure(
                "shadow.plan_stale", "Upstream refs changed after bundle creation"
            )
        with bundle.open("rb") as source_bundle:
            digest = hashlib.file_digest(source_bundle, "sha256").hexdigest()
        object_name = f"sha256-{digest}.bundle"
        try:
            destination.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise CliFailure(
                "shadow.destination_exists",
                "The shadow destination appeared before creation",
            ) from exc
        owned = destination / ".literate-shadow"
        owned.mkdir(mode=0o700)
        objects = owned / "objects"
        objects.mkdir(mode=0o700)
        hooks = owned / "empty-hooks"
        hooks.mkdir()
        shutil.copyfile(bundle, objects / object_name)
        with (objects / object_name).open("rb") as copied_bundle:
            if hashlib.file_digest(copied_bundle, "sha256").hexdigest() != digest:
                raise CliFailure(
                    "shadow.bundle_invalid", "Copied source bundle changed"
                )
        registry = {
            "schema": "literate-ai/shadow-registry@1",
            "upstream": plan["upstream"],
            "forge": plan["forge"],
            "branches": selected,
            "source_bundle": object_name,
            "source_bundle_identity": f"sha256:{digest}",
            "projection_version": 1,
            "source_layout_mapping": None,
            "target_capabilities": [],
            "qualification": "unqualified",
            "create_plan_identity": args.expect_plan,
        }
        (owned / "registry.json").write_bytes(_json_bytes(registry))
        journal = {
            "schema": "literate-ai/shadow-journal-event@1",
            "operation": "create",
            "plan_identity": args.expect_plan,
            "source_bundle_identity": f"sha256:{digest}",
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        (owned / "journal.jsonl").write_bytes(_json_bytes(journal))
        _git(destination, "-c", "init.templateDir=", "init", "-q", "-b", "main")
        _git(destination, "add", ".literate-shadow")
        _git(
            destination,
            "-c",
            "user.name=Literate AI Shadow",
            "-c",
            "user.email=shadow@literate-ai.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            f"core.hooksPath={hooks}",
            "commit",
            "-qm",
            "Create initial upstream shadow custody",
        )
        commit = _git(destination, "rev-parse", "HEAD")
        if (
            {item.name for item in destination.iterdir()}
            != {
                ".git",
                ".literate-shadow",
            }
            or {item.name for item in owned.iterdir()}
            != {
                "objects",
                "empty-hooks",
                "registry.json",
                "journal.jsonl",
            }
            or {item.name for item in objects.iterdir()} != {object_name}
            or tuple(hooks.iterdir())
            or _git(destination, "status", "--porcelain=v1", "--untracked-files=all")
        ):
            raise CliFailure("shadow.foreign_write", "Shadow changed during creation")
    return {
        "schema": "literate-ai/shadow-create-result@1",
        "shadow": str(destination),
        "shadow_commit": commit,
        "source_bundle_identity": registry["source_bundle_identity"],
        "branches": selected,
        "qualification": "unqualified",
    }


def _bounded_file(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise CliFailure(
            "shadow.custody_invalid", "Shadow custody file is missing or unsafe"
        )
    content = path.read_bytes()
    if len(content) > maximum:
        raise CliFailure(
            "shadow.custody_invalid", "Shadow custody file exceeds its bound"
        )
    return content


def status_shadow(args: argparse.Namespace) -> dict[str, object]:
    candidate = Path(args.shadow).expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise CliFailure("shadow.root_invalid", "Shadow root must be a real directory")
    shadow = candidate.resolve(strict=True)
    if (
        Path(_git(shadow, "rev-parse", "--show-toplevel")).resolve(strict=True)
        != shadow
    ):
        raise CliFailure("shadow.root_invalid", "Select the shadow repository root")
    owned = shadow / ".literate-shadow"
    if owned.is_symlink() or not owned.is_dir():
        raise CliFailure(
            "shadow.custody_invalid", "Shadow custody directory is missing"
        )
    registry_bytes = _bounded_file(owned / "registry.json", 64 * 1024)
    journal_bytes = _bounded_file(owned / "journal.jsonl", 1024 * 1024)
    try:
        registry = json.loads(registry_bytes)
        events = [json.loads(line) for line in journal_bytes.splitlines()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CliFailure(
            "shadow.custody_invalid", "Shadow custody JSON is invalid"
        ) from exc
    if (
        not isinstance(registry, dict)
        or registry.get("schema") != "literate-ai/shadow-registry@1"
        or registry.get("qualification") != "unqualified"
        or not isinstance(events, list)
        or len(events) != 1
        or not isinstance(events[0], dict)
        or events[0].get("schema") != "literate-ai/shadow-journal-event@1"
        or events[0].get("operation") != "create"
        or events[0].get("plan_identity") != registry.get("create_plan_identity")
        or events[0].get("source_bundle_identity")
        != registry.get("source_bundle_identity")
    ):
        raise CliFailure(
            "shadow.custody_invalid", "Shadow registry and journal disagree"
        )
    digest = registry.get("source_bundle_identity")
    name = registry.get("source_bundle")
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        or name != f"sha256-{digest[7:]}.bundle"
    ):
        raise CliFailure("shadow.custody_invalid", "Shadow bundle identity is invalid")
    objects = owned / "objects"
    hooks = owned / "empty-hooks"
    bundle = objects / name
    if (
        objects.is_symlink()
        or hooks.is_symlink()
        or not objects.is_dir()
        or not hooks.is_dir()
        or bundle.is_symlink()
        or not bundle.is_file()
        or bundle.stat().st_size > _MAX_BUNDLE_BYTES
    ):
        raise CliFailure("shadow.custody_invalid", "Shadow bundle is missing or unsafe")
    with bundle.open("rb") as source_bundle:
        if hashlib.file_digest(source_bundle, "sha256").hexdigest() != digest[7:]:
            raise CliFailure("shadow.custody_invalid", "Shadow bundle digest changed")
    _git(shadow, "bundle", "verify", str(bundle), timeout=90)
    selected = registry.get("branches")
    if not isinstance(selected, list) or not 1 <= len(selected) <= _MAX_BRANCHES:
        raise CliFailure("shadow.custody_invalid", "Shadow branch registry is invalid")
    expected = {}
    for item in selected:
        if not isinstance(item, dict) or set(item) != {"ref", "commit"}:
            raise CliFailure("shadow.custody_invalid", "Shadow branch entry is invalid")
        ref, commit = item["ref"], item["commit"]
        if (
            not isinstance(ref, str)
            or not ref.startswith("refs/heads/")
            or len(ref) > len("refs/heads/") + _MAX_REF_CHARS
            or not isinstance(commit, str)
            or not _HEX_COMMIT.fullmatch(commit)
            or ref in expected
        ):
            raise CliFailure("shadow.custody_invalid", "Shadow branch entry is invalid")
        expected[ref] = commit
    actual = {}
    for line in _git(shadow, "bundle", "list-heads", str(bundle)).splitlines():
        commit, separator, ref = line.partition(" ")
        if not separator or ref in actual:
            raise CliFailure(
                "shadow.custody_invalid", "Shadow bundle heads are invalid"
            )
        actual[ref] = commit
    if actual != expected:
        raise CliFailure("shadow.custody_invalid", "Shadow bundle heads changed")
    if (
        {item.name for item in shadow.iterdir()} != {".git", ".literate-shadow"}
        or {item.name for item in owned.iterdir()}
        != {"objects", "empty-hooks", "registry.json", "journal.jsonl"}
        or {item.name for item in objects.iterdir()} != {name}
        or tuple(hooks.iterdir())
    ):
        raise CliFailure("shadow.custody_invalid", "Shadow custody layout changed")
    for relative in (
        ".literate-shadow/registry.json",
        ".literate-shadow/journal.jsonl",
        f".literate-shadow/objects/{name}",
    ):
        if _git(shadow, "hash-object", relative) != _git(
            shadow, "rev-parse", f"HEAD:{relative}"
        ):
            raise CliFailure(
                "shadow.custody_invalid", "Shadow commit and files disagree"
            )
    if _git(shadow, "status", "--porcelain=v1", "--untracked-files=all"):
        raise CliFailure(
            "shadow.custody_invalid", "Shadow repository has local changes"
        )
    upstream_value = registry.get("upstream")
    if not isinstance(upstream_value, str) or not Path(upstream_value).is_absolute():
        raise CliFailure("shadow.custody_invalid", "Shadow upstream locator is invalid")
    upstream = Path(upstream_value)
    reasons = []
    if upstream.is_symlink() or not upstream.is_dir():
        reasons.append("upstream-unavailable")
    else:
        try:
            if (
                Path(_git(upstream, "rev-parse", "--show-toplevel")).resolve(
                    strict=True
                )
                != upstream
            ):
                reasons.append("upstream-root-changed")
            if _forge_identity(
                _git(upstream, "config", "--local", "--get", "remote.origin.url")
            ) != registry.get("forge"):
                reasons.append("forge-identity-changed")
            for ref, commit in expected.items():
                if _branch_commit(upstream, ref.removeprefix("refs/heads/")) != commit:
                    reasons.append(f"upstream-ref-changed:{ref}")
        except CliFailure:
            reasons.append("upstream-inspection-failed")
    return {
        "schema": "literate-ai/shadow-status@1",
        "shadow": str(shadow),
        "shadow_commit": _git(shadow, "rev-parse", "HEAD"),
        "source_bundle_identity": digest,
        "branches": selected,
        "upstream_current": not reasons,
        "currentness_reasons": reasons,
        "qualification": "unqualified",
    }


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
    create = actions.add_parser(
        "create", help="create a separate Git shadow with exact initial source custody"
    )
    create.add_argument("--upstream", required=True)
    create.add_argument("--shadow", required=True)
    create.add_argument("--branch", action="append")
    create.add_argument("--expect-plan", required=True, metavar="SHA256")
    create.add_argument("--acknowledge", action="store_true")
    status = actions.add_parser(
        "status",
        help="reverify shadow custody and current upstream refs without writing",
    )
    status.add_argument("--shadow", required=True)
    pr = actions.add_parser(
        "pr-plan", help="bind a GitHub PR base and head without fetching or writing"
    )
    pr.add_argument(
        "--upstream", required=True, help="local upstream Git repository root"
    )
    pr.add_argument(
        "--number", required=True, type=int, help="positive pull request number"
    )


__all__ = [
    "add_shadow_parser",
    "create_shadow",
    "plan_shadow",
    "plan_shadow_pr",
    "status_shadow",
]
