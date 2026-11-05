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

from literate_ai.adapters.exclusive_directory import (
    directory_node,
    publish_directory_between_owned_parents_exclusive,
)

from .errors import CliFailure

_MAX_BRANCHES = 32
_MAX_REF_CHARS = 200
_MAX_PR_BYTES = 256 * 1024
_MAX_BUNDLE_BYTES = 128 * 1024 * 1024
_MAX_FETCH_BYTES = 512 * 1024 * 1024
_MAX_JOURNAL_EVENTS = 64
_HEX_COMMIT = re.compile(r"[0-9a-f]{40,64}\Z")
_GITHUB_SSH = re.compile(
    r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?\Z"
)
_GITHUB_HTTPS = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?\Z"
)


def _git(
    root: Path,
    *arguments: str,
    timeout: int = 10,
    environment: dict[str, str] | None = None,
) -> str:
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *arguments],
            env={
                **os.environ,
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                **(environment or {}),
            },
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


def plan_shadow(
    args: argparse.Namespace, *, allow_existing: bool = False
) -> dict[str, object]:
    upstream = _upstream_root(args.upstream)
    destination = Path(args.shadow).expanduser()
    if destination.is_symlink() or (destination.exists() and not allow_existing):
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
    shadow_state = (
        status_shadow(argparse.Namespace(shadow=args.shadow))
        if args.shadow is not None
        else None
    )
    registry = (
        json.loads(
            _bounded_file(
                Path(str(shadow_state["shadow"]))
                / ".literate-shadow"
                / "registry.json",
                64 * 1024,
            )
        )
        if shadow_state is not None
        else None
    )
    upstream = _upstream_root(str(registry["upstream"]) if registry else args.upstream)
    forge = _forge_identity(
        _git(upstream, "config", "--local", "--get", "remote.origin.url")
    )
    if registry is not None and forge != registry["forge"]:
        raise CliFailure("shadow.forge_changed", "Upstream forge identity changed")
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
        or len(base_ref) > _MAX_REF_CHARS
        or not isinstance(head_ref, str)
        or len(head_ref) > _MAX_REF_CHARS
    ):
        raise CliFailure(
            "shadow.forge_invalid", "Forge PR identity is invalid or closed"
        )
    _git(upstream, "check-ref-format", "--branch", base_ref)
    if shadow_state is None:
        if _branch_commit(upstream, base_ref) != base_commit:
            raise CliFailure(
                "shadow.pr_base_stale",
                "Local target branch differs from the current PR base",
            )
    else:
        selected = {item["ref"]: item["commit"] for item in shadow_state["branches"]}
        target_ref = f"refs/heads/{base_ref}"
        if target_ref not in selected or selected[target_ref] != base_commit:
            raise CliFailure(
                "shadow.pr_base_stale",
                "Shadow target branch differs from the current PR base",
            )
        remote = _remote_heads(upstream, [target_ref])
        if remote.get(target_ref) != base_commit:
            raise CliFailure(
                "shadow.pr_base_stale",
                "Remote target branch changed during PR planning",
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
    if shadow_state is not None:
        body["shadow"] = shadow_state["shadow"]
        body["shadow_commit"] = shadow_state["shadow_commit"]
        body["source_bundle_identity"] = shadow_state["source_bundle_identity"]
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


def _directory_bytes(root: Path) -> int:
    total = 0
    for directory, _, files in os.walk(root):
        for name in files:
            total += (Path(directory) / name).stat().st_size
            if total > _MAX_FETCH_BYTES:
                return total
    return total


def _fetch_selected_refs(
    upstream: Path, destination: Path, selected: list[dict[str, object]]
) -> Path:
    refs = [str(item["ref"]) for item in selected]
    commits = {str(item["ref"]): str(item["commit"]) for item in selected}
    if len({len(commit) for commit in commits.values()}) != 1:
        raise CliFailure("shadow.remote_invalid", "Remote object formats disagree")
    object_format = "sha256" if len(next(iter(commits.values()))) == 64 else "sha1"
    repository = destination / "remote.git"
    hooks = destination / "empty-hooks"
    hooks.mkdir()
    _git(
        destination,
        "-c",
        "init.templateDir=",
        "init",
        "--bare",
        "-q",
        f"--object-format={object_format}",
        str(repository),
    )
    remote_url = _git(upstream, "config", "--local", "--get", "remote.origin.url")
    try:
        process = subprocess.Popen(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(repository),
                "-c",
                f"core.hooksPath={hooks}",
                "fetch",
                "--no-tags",
                "--recurse-submodules=no",
                "--",
                remote_url,
                *(f"+{ref}:{ref}" for ref in refs),
            ],
            env={
                **os.environ,
                "GIT_OPTIONAL_LOCKS": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise CliFailure(
            "shadow.fetch_unavailable", "Remote fetch could not start"
        ) from exc
    deadline = time.monotonic() + 120
    try:
        while process.poll() is None:
            if time.monotonic() >= deadline:
                raise CliFailure(
                    "shadow.fetch_timeout", "Remote fetch exceeded its time bound"
                )
            if _directory_bytes(repository) > _MAX_FETCH_BYTES:
                raise CliFailure(
                    "shadow.fetch_unbounded", "Remote fetch exceeded its byte bound"
                )
            try:
                process.wait(timeout=0.1)
            except subprocess.TimeoutExpired:
                pass
        if process.returncode:
            raise CliFailure("shadow.fetch_failed", "Remote fetch did not complete")
        if _directory_bytes(repository) > _MAX_FETCH_BYTES:
            raise CliFailure(
                "shadow.fetch_unbounded", "Remote fetch exceeded its byte bound"
            )
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    for ref, expected_commit in commits.items():
        actual = _git(repository, "rev-parse", "--verify", f"{ref}^{{commit}}")
        if actual != expected_commit:
            raise CliFailure("shadow.plan_stale", "Remote ref changed during fetch")
    return repository


def create_shadow(args: argparse.Namespace) -> dict[str, object]:
    """Custody exact initial refs in a separate Git repository after plan review."""
    if not args.acknowledge:
        raise CliFailure(
            "shadow.acknowledgement_required", "Creation requires --acknowledge"
        )
    plan = plan_shadow(args, allow_existing=True)
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
    if destination.exists() or destination.is_symlink():
        try:
            existing = status_shadow(argparse.Namespace(shadow=str(destination)))
            owned = destination / ".literate-shadow"
            registry = json.loads(_bounded_file(owned / "registry.json", 64 * 1024))
            journal = _bounded_file(owned / "journal.jsonl", 1024 * 1024)
            if (
                registry.get("create_plan_identity") == args.expect_plan
                and registry.get("branches") == plan["branches"]
                and len(journal.splitlines()) == 1
            ):
                return {
                    "schema": "literate-ai/shadow-create-result@1",
                    "shadow": str(destination),
                    "shadow_commit": existing["shadow_commit"],
                    "source_bundle_identity": existing["source_bundle_identity"],
                    "branches": plan["branches"],
                    "qualification": "unqualified",
                }
        except (CliFailure, ValueError, TypeError, json.JSONDecodeError):
            pass
        raise CliFailure(
            "shadow.destination_exists", "The shadow destination already exists"
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
        if plan_shadow(args, allow_existing=True)["plan_identity"] != args.expect_plan:
            raise CliFailure(
                "shadow.plan_stale", "Upstream refs changed after bundle creation"
            )
        with bundle.open("rb") as source_bundle:
            digest = hashlib.file_digest(source_bundle, "sha256").hexdigest()
        object_name = f"sha256-{digest}.bundle"
        staged_shadow = Path(temporary) / "repository"
        staged_shadow.mkdir(mode=0o700)
        owned = staged_shadow / ".literate-shadow"
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
        _git(staged_shadow, "-c", "init.templateDir=", "init", "-q", "-b", "main")
        _git(staged_shadow, "add", ".literate-shadow")
        _git(
            staged_shadow,
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
        commit = _git(staged_shadow, "rev-parse", "HEAD")
        if (
            {item.name for item in staged_shadow.iterdir()}
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
            or _git(staged_shadow, "status", "--porcelain=v1", "--untracked-files=all")
        ):
            raise CliFailure("shadow.foreign_write", "Shadow changed during creation")
        try:
            publish_directory_between_owned_parents_exclusive(
                staged_shadow,
                destination,
                expected_source=directory_node(staged_shadow),
                expected_source_parent=directory_node(Path(temporary)),
                expected_destination_parent=directory_node(parent),
            )
        except FileExistsError as exc:
            raise CliFailure(
                "shadow.destination_exists",
                "The shadow destination appeared before creation",
            ) from exc
        except CliFailure:
            raise
        except (OSError, ValueError) as exc:
            raise CliFailure(
                "shadow.publish_failed", "The verified shadow could not be published"
            ) from exc
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


def _remote_heads(upstream: Path, refs: list[str]) -> dict[str, str]:
    output = _git(
        upstream,
        "ls-remote",
        "--heads",
        "origin",
        *refs,
        timeout=15,
        environment={"GIT_TERMINAL_PROMPT": "0"},
    )
    observed = {}
    for line in output.splitlines():
        commit, separator, ref = line.partition("\t")
        if not separator or not _HEX_COMMIT.fullmatch(commit) or ref in observed:
            raise CliFailure("shadow.remote_invalid", "Remote ref response is invalid")
        observed[ref] = commit
    if any(ref not in refs for ref in observed):
        raise CliFailure("shadow.remote_invalid", "Remote returned an unselected ref")
    return observed


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
    if _git(shadow, "symbolic-ref", "--short", "HEAD") != "main":
        raise CliFailure("shadow.root_invalid", "Shadow must be on its main branch")
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
        or not 1 <= len(events) <= _MAX_JOURNAL_EVENTS
        or not isinstance(events[0], dict)
        or events[0].get("schema") != "literate-ai/shadow-journal-event@1"
        or events[0].get("operation") != "create"
        or events[0].get("plan_identity") != registry.get("create_plan_identity")
    ):
        raise CliFailure(
            "shadow.custody_invalid", "Shadow registry and journal disagree"
        )
    bundle_identities = []
    previous_identity = None
    for index, event in enumerate(events):
        identity = event.get("source_bundle_identity")
        if (
            event.get("schema") != "literate-ai/shadow-journal-event@1"
            or not isinstance(identity, str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", identity)
            or (index == 0 and event.get("operation") != "create")
            or (
                index > 0
                and (
                    event.get("operation") != "sync"
                    or event.get("previous_bundle_identity") != previous_identity
                    or not isinstance(event.get("plan_identity"), str)
                )
            )
        ):
            raise CliFailure(
                "shadow.custody_invalid", "Shadow journal chain is invalid"
            )
        bundle_identities.append(identity)
        previous_identity = identity
    if bundle_identities[-1] != registry.get("source_bundle_identity") or (
        len(events) > 1 and events[-1].get("branches") != registry.get("branches")
    ):
        raise CliFailure("shadow.custody_invalid", "Shadow journal tip disagrees")
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
    expected_names = {f"sha256-{identity[7:]}.bundle" for identity in bundle_identities}
    if {item.name for item in objects.iterdir()} != expected_names:
        raise CliFailure("shadow.custody_invalid", "Shadow bundle inventory changed")
    for identity in bundle_identities:
        candidate_bundle = objects / f"sha256-{identity[7:]}.bundle"
        if (
            candidate_bundle.is_symlink()
            or not candidate_bundle.is_file()
            or candidate_bundle.stat().st_size > _MAX_BUNDLE_BYTES
        ):
            raise CliFailure(
                "shadow.custody_invalid", "Shadow bundle is missing or unsafe"
            )
        with candidate_bundle.open("rb") as source_bundle:
            if hashlib.file_digest(source_bundle, "sha256").hexdigest() != identity[7:]:
                raise CliFailure(
                    "shadow.custody_invalid", "Shadow bundle digest changed"
                )
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
        or {item.name for item in objects.iterdir()} != expected_names
        or tuple(hooks.iterdir())
    ):
        raise CliFailure("shadow.custody_invalid", "Shadow custody layout changed")
    for relative in (
        ".literate-shadow/registry.json",
        ".literate-shadow/journal.jsonl",
        *(f".literate-shadow/objects/{item}" for item in expected_names),
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
    local_current = False
    remote_current: bool | None = None
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
            local_current = not reasons
            try:
                remote = _remote_heads(upstream, list(expected))
            except CliFailure:
                reasons.append("remote-inspection-unavailable")
            else:
                remote_current = remote == expected
                for ref, commit in expected.items():
                    if ref not in remote:
                        reasons.append(f"remote-ref-missing:{ref}")
                    elif remote[ref] != commit:
                        reasons.append(f"remote-ref-changed:{ref}")
        except CliFailure:
            reasons.append("upstream-inspection-failed")
    return {
        "schema": "literate-ai/shadow-status@1",
        "shadow": str(shadow),
        "shadow_commit": _git(shadow, "rev-parse", "HEAD"),
        "source_bundle_identity": digest,
        "branches": selected,
        "local_refs_current": local_current,
        "remote_refs_current": remote_current,
        "upstream_current": not reasons,
        "currentness_reasons": reasons,
        "qualification": "unqualified",
    }


def _require_ancestor(upstream: Path, previous: str, current: str) -> None:
    try:
        result = subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(upstream),
                "merge-base",
                "--is-ancestor",
                previous,
                current,
            ],
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CliFailure(
            "shadow.ancestry_unavailable", "Git ancestry inspection did not complete"
        ) from exc
    if result.returncode == 1:
        raise CliFailure(
            "shadow.non_fast_forward", "Selected upstream branch was rewritten"
        )
    if result.returncode:
        raise CliFailure(
            "shadow.ancestry_invalid", "Selected upstream ancestry is unavailable"
        )


def plan_shadow_sync(args: argparse.Namespace) -> dict[str, object]:
    state = status_shadow(args)
    shadow = Path(str(state["shadow"]))
    registry = json.loads(
        _bounded_file(shadow / ".literate-shadow" / "registry.json", 64 * 1024)
    )
    upstream = _upstream_root(str(registry["upstream"]))
    forge = _forge_identity(
        _git(upstream, "config", "--local", "--get", "remote.origin.url")
    )
    if forge != registry["forge"]:
        raise CliFailure("shadow.forge_changed", "Upstream forge identity changed")
    prior = {str(item["ref"]): str(item["commit"]) for item in state["branches"]}
    additions = args.add_branch or []
    if len(prior) + len(additions) > _MAX_BRANCHES:
        raise CliFailure("shadow.branches_unbounded", "Too many selected branches")
    if len(set(additions)) != len(additions) or any(
        f"refs/heads/{branch}" in prior for branch in additions
    ):
        raise CliFailure("shadow.branch_duplicate", "A selected branch is repeated")
    all_refs = [*prior, *(f"refs/heads/{branch}" for branch in additions)]
    for branch in additions:
        if not branch or len(branch) > _MAX_REF_CHARS or branch.startswith("-"):
            raise CliFailure(
                "shadow.branch_invalid", "The branch name is outside its finite bound"
            )
        _git(upstream, "check-ref-format", "--branch", branch)
    remote = _remote_heads(upstream, all_refs) if args.remote else None
    if remote is not None and set(remote) != set(all_refs):
        raise CliFailure("shadow.remote_missing", "A selected remote branch is missing")
    selected = []
    for ref, previous in prior.items():
        current = (
            remote[ref]
            if remote is not None
            else _branch_commit(upstream, ref.removeprefix("refs/heads/"))
        )
        if remote is None:
            _require_ancestor(upstream, previous, current)
        selected.append(
            {
                "ref": ref,
                "previous_commit": previous,
                "commit": current,
                "change": "unchanged" if previous == current else "advanced",
            }
        )
    for branch in additions:
        commit = (
            remote[f"refs/heads/{branch}"]
            if remote is not None
            else _branch_commit(upstream, branch)
        )
        selected.append(
            {
                "ref": f"refs/heads/{branch}",
                "previous_commit": None,
                "commit": commit,
                "change": "added",
            }
        )
    body: dict[str, object] = {
        "schema": "literate-ai/shadow-sync-plan@1",
        "shadow": str(shadow),
        "shadow_commit": state["shadow_commit"],
        "source_bundle_identity": state["source_bundle_identity"],
        "upstream": str(upstream),
        "forge": forge,
        "source": "remote" if args.remote else "local",
        "branches": selected,
        "effect": "read-only; no refs were fetched or shadow state changed",
    }
    return _plan_identity(body)


def _worktree_matches_old(shadow: Path, old: str, names: list[str]) -> bool:
    owned = shadow / ".literate-shadow"
    try:
        if (
            {item.name for item in shadow.iterdir()} != {".git", ".literate-shadow"}
            or {item.name for item in owned.iterdir()}
            != {"objects", "empty-hooks", "registry.json", "journal.jsonl"}
            or {item.name for item in (owned / "objects").iterdir()} != set(names)
            or tuple((owned / "empty-hooks").iterdir())
        ):
            return False
        _git(shadow, "diff", "--quiet", old, "--")
        _git(shadow, "diff", "--cached", "--quiet", old, "--")
        return True
    except (CliFailure, OSError):
        return False


def _worktree_matches_transition(
    shadow: Path, old: str, new: str, old_names: list[str], new_name: str
) -> bool:
    owned = shadow / ".literate-shadow"
    objects = owned / "objects"
    hooks = owned / "empty-hooks"
    try:
        if (
            {item.name for item in shadow.iterdir()} != {".git", ".literate-shadow"}
            or owned.is_symlink()
            or objects.is_symlink()
            or hooks.is_symlink()
            or {item.name for item in owned.iterdir()}
            != {"objects", "empty-hooks", "registry.json", "journal.jsonl"}
            or {item.name for item in objects.iterdir()}
            not in (set(old_names), {*old_names, new_name})
            or tuple(hooks.iterdir())
        ):
            return False
        index_matches = False
        for commit in (old, new):
            try:
                _git(shadow, "diff", "--cached", "--quiet", commit, "--")
                index_matches = True
                break
            except CliFailure:
                pass
        if not index_matches:
            return False
        relatives = [
            ".literate-shadow/registry.json",
            ".literate-shadow/journal.jsonl",
            *(f".literate-shadow/objects/{name}" for name in old_names),
            f".literate-shadow/objects/{new_name}",
        ]
        for relative in relatives:
            path = shadow / relative
            if not path.exists():
                if relative != f".literate-shadow/objects/{new_name}":
                    return False
                continue
            if path.is_symlink() or not path.is_file():
                return False
            observed = _git(shadow, "hash-object", relative, timeout=90)
            allowed = set()
            for commit in (old, new):
                try:
                    allowed.add(_git(shadow, "rev-parse", f"{commit}:{relative}"))
                except CliFailure:
                    pass
            if observed not in allowed:
                return False
        return True
    except (CliFailure, OSError):
        return False


def _committed_bytes(shadow: Path, commit: str, relative: str) -> bytes:
    object_name = f"{commit}:{relative}"
    try:
        size = int(_git(shadow, "cat-file", "-s", object_name))
    except (CliFailure, ValueError) as exc:
        raise CliFailure(
            "shadow.pending_invalid", "Pending metadata object is missing"
        ) from exc
    if size > 1024 * 1024:
        raise CliFailure(
            "shadow.pending_invalid", "Pending metadata object is unbounded"
        )
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(shadow), "show", object_name],
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1"},
            capture_output=True,
            timeout=10,
            check=False,
        )
        if result.returncode or len(result.stdout) != size:
            raise ValueError("pending metadata read failed")
        return result.stdout
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise CliFailure(
            "shadow.pending_invalid", "Pending metadata is invalid"
        ) from exc


def _finish_pending_sync(shadow: Path, expected_plan: str) -> dict[str, object]:
    pending_path = shadow / ".git" / "literate-shadow.pending.json"
    try:
        pending = json.loads(_bounded_file(pending_path, 16 * 1024))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CliFailure(
            "shadow.pending_invalid", "Pending sync record is invalid"
        ) from exc
    if (
        not isinstance(pending, dict)
        or pending.get("schema") != "literate-ai/shadow-pending-sync@1"
        or not isinstance(pending.get("old"), str)
        or not isinstance(pending.get("new"), str)
        or pending.get("plan_identity") != expected_plan
        or not _HEX_COMMIT.fullmatch(pending["old"])
        or not _HEX_COMMIT.fullmatch(pending["new"])
        or not isinstance(pending.get("old_bundle_names"), list)
        or not 1 <= len(pending["old_bundle_names"]) <= _MAX_JOURNAL_EVENTS
        or not all(
            isinstance(name, str) and re.fullmatch(r"sha256-[0-9a-f]{64}\.bundle", name)
            for name in pending["old_bundle_names"]
        )
        or len(set(pending["old_bundle_names"])) != len(pending["old_bundle_names"])
    ):
        raise CliFailure("shadow.pending_invalid", "Pending sync record is invalid")
    old, new = pending["old"], pending["new"]
    if (
        _git(shadow, "symbolic-ref", "--short", "HEAD") != "main"
        or _git(shadow, "cat-file", "-t", new) != "commit"
        or _git(shadow, "rev-parse", f"{new}^@") != old
    ):
        raise CliFailure("shadow.pending_invalid", "Pending sync commit is invalid")
    changed = set(
        _git(
            shadow, "diff-tree", "--no-commit-id", "--name-only", "-r", old, new
        ).splitlines()
    )
    try:
        registry = json.loads(
            _committed_bytes(shadow, new, ".literate-shadow/registry.json")
        )
        journal = [
            json.loads(line)
            for line in _committed_bytes(
                shadow, new, ".literate-shadow/journal.jsonl"
            ).splitlines()
        ]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CliFailure(
            "shadow.pending_invalid", "Pending registry or journal is invalid"
        ) from exc
    if not isinstance(registry, dict):
        raise CliFailure("shadow.pending_invalid", "Pending registry is invalid")
    bundle_name = registry.get("source_bundle")
    if (
        not isinstance(bundle_name, str)
        or not re.fullmatch(r"sha256-[0-9a-f]{64}\.bundle", bundle_name)
        or registry.get("source_bundle_identity")
        != f"sha256:{bundle_name[len('sha256-') : -len('.bundle')]}"
        or changed
        != {
            ".literate-shadow/registry.json",
            ".literate-shadow/journal.jsonl",
            f".literate-shadow/objects/{bundle_name}",
        }
        or not journal
        or not isinstance(journal[-1], dict)
        or journal[-1].get("operation") != "sync"
        or journal[-1].get("plan_identity") != expected_plan
        or journal[-1].get("source_bundle_identity")
        != registry.get("source_bundle_identity")
        or journal[-1].get("branches") != registry.get("branches")
    ):
        raise CliFailure("shadow.pending_invalid", "Pending commit content is invalid")
    current = _git(shadow, "rev-parse", "HEAD")
    if current not in {old, new}:
        raise CliFailure(
            "shadow.pending_conflict", "Shadow head changed outside the pending sync"
        )
    if current == old:
        if not _worktree_matches_old(shadow, old, pending["old_bundle_names"]):
            raise CliFailure(
                "shadow.pending_conflict",
                "Shadow worktree changed before sync publication",
            )
        _git(shadow, "update-ref", "refs/heads/main", new, old)
    try:
        state = status_shadow(argparse.Namespace(shadow=str(shadow)))
    except CliFailure:
        if not _worktree_matches_transition(
            shadow,
            old,
            new,
            pending["old_bundle_names"],
            bundle_name,
        ):
            raise CliFailure(
                "shadow.pending_conflict", "Shadow worktree has foreign changes"
            ) from None
        _git(shadow, "reset", "--hard", new, timeout=90)
        state = status_shadow(argparse.Namespace(shadow=str(shadow)))
    pending_path.unlink()
    return {
        "schema": "literate-ai/shadow-sync-result@1",
        "shadow": str(shadow),
        "shadow_commit": state["shadow_commit"],
        "source_bundle_identity": state["source_bundle_identity"],
        "branches": state["branches"],
        "upstream_current": state["upstream_current"],
        "qualification": "unqualified",
    }


def apply_shadow_sync(args: argparse.Namespace) -> dict[str, object]:
    if not args.acknowledge:
        raise CliFailure(
            "shadow.acknowledgement_required", "Sync requires --acknowledge"
        )
    candidate = Path(args.shadow).expanduser()
    if candidate.is_symlink() or not candidate.is_dir():
        raise CliFailure("shadow.root_invalid", "Shadow root must be a real directory")
    shadow = candidate.resolve(strict=True)
    pending_path = shadow / ".git" / "literate-shadow.pending.json"
    if pending_path.exists():
        if not args.resume:
            raise CliFailure("shadow.pending_sync", "Resume the existing shadow sync")
        return _finish_pending_sync(shadow, args.expect_plan)
    if args.resume:
        raise CliFailure("shadow.pending_missing", "No shadow sync is pending")
    state = status_shadow(argparse.Namespace(shadow=str(shadow)))
    owned = shadow / ".literate-shadow"
    journal_bytes = _bounded_file(owned / "journal.jsonl", 1024 * 1024)
    events = [json.loads(line) for line in journal_bytes.splitlines()]
    if len(events) > 1 and events[-1].get("plan_identity") == args.expect_plan:
        return {
            "schema": "literate-ai/shadow-sync-result@1",
            "shadow": str(shadow),
            "shadow_commit": state["shadow_commit"],
            "source_bundle_identity": state["source_bundle_identity"],
            "branches": state["branches"],
            "upstream_current": state["upstream_current"],
            "qualification": "unqualified",
            "idempotent": True,
        }
    plan = plan_shadow_sync(args)
    if args.expect_plan != plan["plan_identity"]:
        raise CliFailure(
            "shadow.plan_stale", "Current sync state differs from the reviewed plan"
        )
    if all(item["change"] == "unchanged" for item in plan["branches"]):
        return {
            "schema": "literate-ai/shadow-sync-result@1",
            "shadow": str(shadow),
            "shadow_commit": state["shadow_commit"],
            "source_bundle_identity": state["source_bundle_identity"],
            "branches": state["branches"],
            "upstream_current": True,
            "qualification": "unqualified",
            "idempotent": True,
        }
    if len(events) >= _MAX_JOURNAL_EVENTS:
        raise CliFailure(
            "shadow.journal_unbounded", "Shadow journal event bound reached"
        )
    registry = json.loads(_bounded_file(owned / "registry.json", 64 * 1024))
    upstream = Path(str(plan["upstream"]))
    selected = [
        {"ref": item["ref"], "commit": item["commit"]} for item in plan["branches"]
    ]
    with tempfile.TemporaryDirectory(
        prefix=".shadow-sync-", dir=shadow.parent
    ) as temporary:
        stage = Path(temporary)
        bundle = stage / "source.bundle"
        source_repo = (
            _fetch_selected_refs(upstream, stage, plan["branches"])
            if plan["source"] == "remote"
            else upstream
        )
        if plan["source"] == "remote":
            for item in plan["branches"]:
                previous = item["previous_commit"]
                if previous is not None:
                    _require_ancestor(source_repo, str(previous), str(item["commit"]))
        _create_bounded_bundle(
            source_repo, bundle, [str(item["ref"]) for item in selected]
        )
        observed = {}
        for line in _git(source_repo, "bundle", "list-heads", str(bundle)).splitlines():
            commit, separator, ref = line.partition(" ")
            if not separator or ref in observed:
                raise CliFailure(
                    "shadow.bundle_invalid", "Bundle head identity is invalid"
                )
            observed[ref] = commit
        if observed != {str(item["ref"]): str(item["commit"]) for item in selected}:
            raise CliFailure("shadow.plan_stale", "Upstream refs changed during sync")
        _git(source_repo, "bundle", "verify", str(bundle), timeout=90)
        if plan_shadow_sync(args)["plan_identity"] != args.expect_plan:
            raise CliFailure(
                "shadow.plan_stale", "Upstream or shadow changed during sync"
            )
        with bundle.open("rb") as source_bundle:
            digest = hashlib.file_digest(source_bundle, "sha256").hexdigest()
        name = f"sha256-{digest}.bundle"
        registry.update(
            branches=selected,
            source_bundle=name,
            source_bundle_identity=f"sha256:{digest}",
        )
        event = {
            "schema": "literate-ai/shadow-journal-event@1",
            "operation": "sync",
            "plan_identity": args.expect_plan,
            "previous_bundle_identity": state["source_bundle_identity"],
            "source_bundle_identity": f"sha256:{digest}",
            "branches": selected,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        registry_file = stage / "registry.json"
        journal_file = stage / "journal.jsonl"
        registry_file.write_bytes(_json_bytes(registry))
        journal_file.write_bytes(journal_bytes + _json_bytes(event))
        old = str(state["shadow_commit"])
        index = stage / "index"
        index_environment = {"GIT_INDEX_FILE": str(index)}
        _git(shadow, "read-tree", old, environment=index_environment)
        for relative, content in (
            (".literate-shadow/registry.json", registry_file),
            (".literate-shadow/journal.jsonl", journal_file),
            (f".literate-shadow/objects/{name}", bundle),
        ):
            oid = _git(shadow, "hash-object", "-w", str(content), timeout=90)
            _git(
                shadow,
                "update-index",
                "--add",
                "--cacheinfo",
                f"100644,{oid},{relative}",
                environment=index_environment,
            )
        tree = _git(shadow, "write-tree", environment=index_environment)
        new = _git(
            shadow,
            "commit-tree",
            tree,
            "-p",
            old,
            "-m",
            "Synchronize upstream shadow refs",
            environment={
                "GIT_AUTHOR_NAME": "Literate AI Shadow",
                "GIT_AUTHOR_EMAIL": "shadow@literate-ai.invalid",
                "GIT_COMMITTER_NAME": "Literate AI Shadow",
                "GIT_COMMITTER_EMAIL": "shadow@literate-ai.invalid",
            },
        )
        pending = {
            "schema": "literate-ai/shadow-pending-sync@1",
            "old": old,
            "new": new,
            "plan_identity": args.expect_plan,
            "old_bundle_names": sorted(
                item.name for item in (owned / "objects").iterdir()
            ),
        }
        if plan_shadow_sync(args)["plan_identity"] != args.expect_plan:
            raise CliFailure(
                "shadow.plan_stale",
                "Upstream or shadow changed before sync publication",
            )
        try:
            with pending_path.open("xb") as pending_file:
                pending_file.write(_json_bytes(pending))
                pending_file.flush()
                os.fsync(pending_file.fileno())
        except FileExistsError as exc:
            raise CliFailure("shadow.pending_sync", "Another sync is pending") from exc
        return _finish_pending_sync(shadow, args.expect_plan)


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
    sync = actions.add_parser(
        "sync", help="plan exact selected-branch changes without fetching or writing"
    )
    sync_actions = sync.add_subparsers(dest="sync_command", required=True)
    sync_plan = sync_actions.add_parser("plan")
    sync_plan.add_argument("--shadow", required=True)
    sync_plan.add_argument("--add-branch", action="append")
    sync_plan.add_argument("--remote", action="store_true")
    sync_apply = sync_actions.add_parser("apply")
    sync_apply.add_argument("--shadow", required=True)
    sync_apply.add_argument("--add-branch", action="append")
    sync_apply.add_argument("--remote", action="store_true")
    sync_apply.add_argument("--expect-plan", required=True, metavar="SHA256")
    sync_apply.add_argument("--acknowledge", action="store_true")
    sync_apply.add_argument("--resume", action="store_true")
    pr = actions.add_parser(
        "pr-plan", help="bind a GitHub PR base and head without fetching or writing"
    )
    pr_location = pr.add_mutually_exclusive_group(required=True)
    pr_location.add_argument("--upstream", help="local upstream Git repository root")
    pr_location.add_argument("--shadow", help="created shadow Git repository root")
    pr.add_argument(
        "--number", required=True, type=int, help="positive pull request number"
    )


__all__ = [
    "add_shadow_parser",
    "apply_shadow_sync",
    "create_shadow",
    "plan_shadow",
    "plan_shadow_pr",
    "plan_shadow_sync",
    "status_shadow",
]
