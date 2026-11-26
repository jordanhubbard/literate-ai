"""Finite committed-profile removal using Git's before-images and index owner.

This stages deletions and never commits, cleans caches, or restores worktree
bytes. An explicit immutable source commit permits fresh forward recovery.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import path_is_link_or_reparse, require_safe_directory
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.builders.python import BuildError
from literate_ai.adapters.lifecycle_lock import (
    project_lifecycle_lock,
    project_lifecycle_lock_path,
)
from literate_ai.adapters.native_profile_git import (
    NativeProfileGitBoundaryError,
    require_native_profile_git_boundary,
)
from literate_ai.adapters.native_project_bootstrap import PROFILE, native_template_files
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
    RepositoryLineage,
    RepositoryParentSelection,
    canonical_identity,
)
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
)
from literate_ai.contracts.original_project import OriginalProjectAdoptionPlan
from literate_ai.projects import ProjectConfigurationStore, parse_project_configuration

SCHEMA = "literate-ai/native-project-removal@1"
MANIFEST = "litai/literate.project.json"
BASELINE = "litai/.literate/initialization-baseline.json"
BASES = "litai/.literate/update-bases.json"
BOOTSTRAP = "litai/.literate/bootstrap.json"
_METADATA = frozenset(
    {
        MANIFEST,
        BASELINE,
        BASES,
        BOOTSTRAP,
        "litai/docs/authority.md",
        "litai/.literate/repository-parent.json",
        "litai/.literate/repository-lineage.json",
        "litai/.literate/repository-lineage.lock",
        "litai/.literate/initialization-origin.json",
        "litai/.literate/original-adoption.json",
        "litai/.literate/conversion-authority.json",
        "litai/.literate/conversion-authority.lock",
    }
)
_MAXIMUM_BYTES = 4 * 1024 * 1024
_AUTHORITY_METADATA = _METADATA - {"litai/docs/authority.md"}


class NativeProjectRemovalError(ValueError):
    def __init__(self, suffix: str, message: str):
        self.code = "native_removal." + suffix
        self.message = message
        super().__init__(message)


def _fail(suffix: str, message: str):
    raise NativeProjectRemovalError(suffix, message)


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _git(root, *args, content=None, allow_failure=False):
    try:
        result = run_bounded_process(
            [
                "git",
                "--literal-pathspecs",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "apply.ignoreWhitespace=no",
                "-C",
                str(root),
                *args,
            ],
            cwd=root,
            environment={**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"},
            timeout_seconds=30,
            poll_interval_seconds=0.01,
            stdout_limit_bytes=_MAXIMUM_BYTES,
            stderr_limit_bytes=_MAXIMUM_BYTES,
            input_bytes=content,
            input_limit_bytes=_MAXIMUM_BYTES,
            error_prefix="native_removal.git",
            terminate_descendants=True,
        )
    except BuildError as exc:
        raise NativeProjectRemovalError("git_failed", str(exc)) from exc
    if result.returncode and not allow_failure:
        _fail("git_refused", "Git refused the bounded native-profile operation")
    return result


def _entries(content: bytes):
    entries = {}
    for entry in content.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, blob, stage = metadata.decode("ascii").split()
        path = name.decode("utf-8")
        if path in entries or stage != "0":
            _fail("unmerged_index", "Resolve the native Git index before removal")
        entries[path] = (mode, blob)
    return entries


def _index(root):
    return _entries(_git(root, "ls-files", "--stage", "-z").stdout)


def _tree(root, source):
    entries = {}
    for entry in _git(root, "ls-tree", "-r", "-z", source, "--", "litai").stdout.split(
        b"\0"
    ):
        if entry:
            metadata, name = entry.split(b"\t", 1)
            mode, kind, blob = metadata.decode("ascii").split()
            entries[name.decode("utf-8")] = (mode, blob, kind)
    return entries


def _blob(root, entry, *, cache):
    if entry is None or entry[0] != "100644" or entry[2] != "blob":
        _fail(
            "authority_unavailable", "Native metadata must be committed regular files"
        )
    if entry[1] in cache:
        return cache[entry[1]]
    size = int(_git(root, "cat-file", "-s", entry[1]).stdout)
    if size > 256 * 1024:
        _fail("authority_limit", "Native metadata exceeds its bounded file size")
    content = _git(root, "cat-file", "blob", entry[1]).stdout
    if len(content) != size:
        _fail(
            "authority_changed", "Committed native metadata changed during inspection"
        )
    cache[entry[1]] = content
    return content


def _node(path):
    value = path.lstat()
    return {
        "device": str(value.st_dev),
        "inode": str(value.st_ino),
        "mode": value.st_mode,
        "links": value.st_nlink,
        "size": value.st_size,
        "modified_ns": str(value.st_mtime_ns),
    }


def _directory_node(path):
    require_safe_directory(path, allow_missing=True)
    if not path.exists():
        return None
    value = path.stat()
    return {
        "device": str(value.st_dev),
        "inode": str(value.st_ino),
        "mode": value.st_mode,
        "uid": value.st_uid,
        "gid": value.st_gid,
    }


def _directories(root, selected, git_directory):
    directories = {root, git_directory}
    for relative in selected:
        parent = (root / relative).parent
        while parent != root:
            directories.add(parent)
            parent = parent.parent
    return {str(path): _directory_node(path) for path in sorted(directories)}


def _require_git_boundary(root, paths):
    try:
        require_native_profile_git_boundary(root, paths)
    except NativeProfileGitBoundaryError as exc:
        raise NativeProjectRemovalError("nested_git_boundary", str(exc)) from exc


def _worktree(root, relative):
    path = root / relative
    require_safe_directory(path.parent, allow_missing=True)
    if not path.exists() and not path.is_symlink():
        return None
    if path_is_link_or_reparse(path):
        _fail("path_unsafe", "A selected native-profile path is redirected")
    before = _node(path)
    if (
        not stat.S_ISREG(before["mode"])
        or before["links"] != 1
        or before["size"] > 256 * 1024
    ):
        _fail("path_unsafe", "A selected native-profile path has unsupported custody")
    content = ProjectConfigurationStore(root, maximum_bytes=256 * 1024)._read_manifest(
        path
    )
    if _node(path) != before:
        _fail("path_changed", "A selected native-profile file changed while read")
    return {"identity": _digest(content), "node": before}


def _owned(root, tree, cache):
    templates = native_template_files()
    allowed = _METADATA | templates.keys()

    def record(relative):
        return json.loads(_blob(root, tree.get(relative), cache=cache))

    definition = parse_project_configuration(
        _blob(root, tree.get(MANIFEST), cache=cache)
    )
    baseline = ProjectInitializationBaseline.from_dict(record(BASELINE))
    origin = ProjectInitializationOrigin.from_dict(
        record("litai/.literate/initialization-origin.json")
    )
    selection = RepositoryParentSelection.from_dict(
        record("litai/.literate/repository-parent.json")
    )
    lineage = RepositoryLineage.from_dict(
        record("litai/.literate/repository-lineage.json")
    )
    conversion = ConversionAuthorityState.from_dict(
        record("litai/.literate/conversion-authority.json")
    )
    original = record("litai/.literate/original-adoption.json")
    adoption = OriginalProjectAdoptionPlan(
        original["project_id"],
        ContentIdentity.parse_uri(original["project_authority"]),
        original["git_commit"],
        original["git_tree"],
    )
    bootstrap = record(BOOTSTRAP)
    if (
        definition.framework_directory != "litai"
        or definition.lifecycle_driver is not None
        or baseline.profile != "native"
        or baseline.origin_identity != origin.identity
        or {item.path for item in baseline.files} != allowed - {BASELINE}
        or selection != RepositoryParentSelection.root()
        or lineage != RepositoryLineage(selection, (), ())
        or conversion.stage != ConversionAuthorityStage.ORIGINAL
        or conversion.project_id != definition.project_id
        or conversion.evidence_identities != (adoption.identity,)
        or original != adoption.to_dict()
        or adoption.project_id != definition.project_id
        or set(bootstrap) != {"schema", "bootstrap_identity", "source"}
        or bootstrap.get("schema") != PROFILE
        or bootstrap["source"]
        != {"commit": adoption.git_commit, "tree": adoption.git_tree}
    ):
        _fail(
            "profile_unsupported",
            "Removal supports only the minimal native Git profile",
        )
    expected = {item.path: item.identity.uri for item in baseline.files}
    ContentIdentity.parse_uri(bootstrap["bootstrap_identity"])
    bases_content = _blob(root, tree.get(BASES), cache=cache)
    bases = json.loads(bases_content)
    import base64

    from literate_ai.adapters.update_merge import SCHEMA as BASES_SCHEMA

    if (
        set(bases) != {"schema", "blobs", "framework", "catalog", "sources"}
        or bases["schema"] != BASES_SCHEMA
        or bases["catalog"]
        or bases["sources"]
        or set(bases["framework"]) != templates.keys()
    ):
        _fail(
            "ownership_unsupported",
            "Native update ownership needs explicit disposition",
        )
    blobs = {
        key: base64.b64decode(value, validate=True)
        for key, value in bases["blobs"].items()
    }
    if any(_digest(content) != key for key, content in blobs.items()):
        _fail("ownership_invalid", "Native update base content identity is invalid")
    for relative, identity in bases["framework"].items():
        if identity not in blobs:
            _fail("ownership_invalid", "Native update base bytes are unavailable")
        expected[relative] = identity
    # These two canonical tool records describe ownership; they are not editable
    # product documents. Their current committed bytes remain in the Git before-image.
    expected[BASELINE] = _digest(_blob(root, tree.get(BASELINE), cache=cache))
    expected[BASES] = _digest(bases_content)
    review = "litai/docs/authority.md"
    content = _blob(root, tree.get(review), cache=cache)
    if re.fullmatch(
        rb"# Documentation authority\n\n"
        rb"<!-- literate-ai:authority-reviewed sha256:[0-9a-f]{64} -->\n",
        content,
    ):
        expected[review] = _digest(content)
    owned, retained = {}, {}
    for relative, entry in tree.items():
        if relative not in allowed or entry[0] != "100644" or entry[2] != "blob":
            retained[relative] = "custom-or-unsupported"
        elif (
            relative not in expected
            or _digest(_blob(root, entry, cache=cache)) != expected[relative]
        ):
            retained[relative] = "customized"
        else:
            owned[relative] = entry
    if _AUTHORITY_METADATA - owned.keys():
        _fail(
            "authority_customized",
            "Preserve changed native authority metadata; removal needs disposition",
        )
    return owned, retained


@dataclass(frozen=True)
class PreparedNativeRemoval:
    document: dict
    entries: dict
    index: dict
    write_paths: tuple[str | Path, ...]


def prepare_native_project_removal(
    root: Path, *, source: str | None = None, only: tuple[str, ...] = ()
):
    root = Path(root).absolute()
    require_safe_directory(root)
    if any(
        name in os.environ
        for name in (
            "GIT_DIR",
            "GIT_WORK_TREE",
            "GIT_COMMON_DIR",
            "GIT_INDEX_FILE",
            "GIT_OBJECT_DIRECTORY",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        )
    ):
        _fail(
            "git_override_unsupported", "Use the actual worktree Git state for removal"
        )
    if source is not None and not only:
        _fail("selection_required", "Recovery needs the original finite --only paths")
    git_directory = ProjectConfigurationStore.layout_metadata_directory(root)
    if git_directory is None:
        _fail("git_required", "Native removal requires an actual Git worktree")
    if (git_directory / "index.lock").exists() or (
        git_directory / "index.lock"
    ).is_symlink():
        _fail(
            "git_lock_present",
            "Resolve the preserved index lock through native Git recovery",
        )
    top = Path(_git(root, "rev-parse", "--show-toplevel").stdout.decode().strip())
    if not os.path.samefile(top, root):
        _fail("git_root_required", "Select the actual native Git worktree root")
    sparse = _git(
        root, "config", "--bool", "--get", "core.sparseCheckout", allow_failure=True
    )
    if sparse.returncode not in {0, 1} or sparse.stdout.strip() == b"true":
        _fail("sparse_unsupported", "Sparse worktrees need native Git disposition")
    head = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    revision = head if source is None else source
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        _fail("source_required", "Recovery source must be an immutable full Git commit")
    if (
        _git(root, "rev-parse", revision + "^{commit}").stdout.decode().strip()
        != revision
    ):
        _fail("source_invalid", "Recovery source must identify the exact commit object")
    tree = _tree(root, revision)
    cache = {}
    try:
        owned, retained = _owned(root, tree, cache)
    except NativeProjectRemovalError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise NativeProjectRemovalError(
            "authority_invalid",
            "Committed native authority is malformed or inconsistent",
        ) from exc
    if only:
        if (
            len(set(only)) != len(only)
            or set(only) - owned.keys()
            or MANIFEST not in only
        ):
            _fail(
                "selection_invalid", "Select exact owned paths including the manifest"
            )
        retained.update(
            {path: "outside-selection" for path in owned if path not in only}
        )
        owned = {path: entry for path, entry in owned.items() if path in only}
    current_tree = _tree(root, head)
    index = _index(root)
    states = {}
    for relative, entry in sorted(owned.items()):
        if current_tree.get(relative) not in (None, entry):
            _fail(
                "head_changed",
                "Current HEAD contains a different selected file; preserve it",
            )
        indexed = index.get(relative)
        if indexed not in (None, entry[:2]):
            _fail(
                "index_changed", "A selected index entry has different content or mode"
            )
        state = _worktree(root, relative)
        if state is not None:
            if (
                state["identity"] != _digest(_blob(root, entry, cache=cache))
                or state["node"]["mode"] & 0o111
            ):
                if source is not None or relative in _AUTHORITY_METADATA:
                    _fail(
                        "worktree_changed",
                        "A selected path now has custom content or mode; preserve it",
                    )
                retained[relative] = "custom-working-tree"
                continue
        if indexed is None and state is not None:
            _fail(
                "index_disposition_required",
                "A selected file remains outside the index; inspect native Git "
                "staging before recovery. No index entry will be restored "
                "automatically.",
            )
        states[relative] = {"index": indexed, "worktree": state}
    selected = {relative: owned[relative] for relative in states}
    flags = _git(root, "ls-files", "-v", "-z", "--", *sorted(selected)).stdout
    if any(item and not item.startswith(b"H ") for item in flags.split(b"\0")):
        _fail(
            "index_flags_unsupported",
            "Selected index flags need native Git disposition",
        )
    attributes = _git(
        root,
        "check-attr",
        "-z",
        "--stdin",
        "filter",
        "working-tree-encoding",
        content=b"\0".join(path.encode() for path in selected) + b"\0",
    ).stdout.split(b"\0")
    if any(value not in {b"unspecified", b"unset"} for value in attributes[2::3]):
        _fail(
            "transform_unsupported",
            "Selected Git content transforms are not qualified for removal",
        )
    directories = _directories(root, selected, git_directory)
    write_paths: tuple[str | Path, ...] = tuple(selected)
    if states[MANIFEST]["worktree"] is not None:
        write_paths += (project_lifecycle_lock_path(root),)
    _require_git_boundary(root, write_paths)
    value = {
        "schema": SCHEMA,
        "root": str(root),
        "source_commit": revision,
        "current_head": head,
        "index_identity": canonical_identity(index).uri,
        "directory_bindings": directories,
        "git_directory": str(git_directory),
        "root_node": {
            key: value
            for key, value in _node(root).items()
            if key in {"device", "inode", "mode"}
        },
        "selected": states,
        "retained": retained,
        "effect": "stage-only-owned-deletions-without-commit",
        "recovery_argv": [
            "litai",
            "onboard",
            "remove",
            str(root),
            "--source",
            revision,
            *(argument for path in selected for argument in ("--only", path)),
        ],
        "external_files": [],
        "coordination": "worktree Git administration and existing lifecycle locks",
        "runtime_state": "preserved; no recursive cleanup",
        "writes": False,
    }
    value["plan_identity"] = canonical_identity(value).uri
    return PreparedNativeRemoval(value, selected, index, write_paths)


def plan_native_project_removal(
    root: Path, *, source: str | None = None, only: tuple[str, ...] = ()
):
    return prepare_native_project_removal(root, source=source, only=only).document


def _require_remaining(root, prepared, remaining):
    if (
        str(ProjectConfigurationStore.layout_metadata_directory(root))
        != (prepared.document["git_directory"])
    ):
        _fail("git_directory_changed", "Git administration changed during removal")
    for name, expected in prepared.document["directory_bindings"].items():
        directory = Path(name)
        actual = _directory_node(directory)
        # Git may prune an emptied selected parent. It may not replace a parent
        # or remove one still needed by a planned live path.
        needed = directory == root or name == prepared.document["git_directory"]
        needed = needed or any(
            directory in (root / relative).parents
            and prepared.document["selected"][relative]["worktree"] is not None
            for relative in remaining
        )
        if actual != expected and (actual is not None or needed):
            _fail("directory_changed", "A selected parent directory changed custody")
    if (
        _git(root, "rev-parse", "HEAD").stdout.decode().strip()
        != prepared.document["current_head"]
    ):
        _fail("head_changed", "HEAD changed; inspect a fresh recovery plan")
    index = _index(root)
    selected = prepared.entries.keys()
    if {path: entry for path, entry in index.items() if path not in selected} != {
        path: entry for path, entry in prepared.index.items() if path not in selected
    }:
        _fail(
            "concurrent_index",
            "Unrelated index entries changed; preserve the current index",
        )
    for relative in selected:
        state = _worktree(root, relative)
        if relative in remaining:
            expected = prepared.document["selected"][relative]
            if (
                index.get(relative) != expected["index"]
                or state != expected["worktree"]
            ):
                _fail(
                    "state_changed",
                    "Selected state changed; inspect a fresh recovery plan",
                )
        elif index.get(relative) is not None or state is not None:
            _fail(
                "cleanup_pending",
                "Git removal is incomplete; use the recorded recovery source and paths",
            )
    _require_git_boundary(root, prepared.write_paths)


def _remove_group(root, prepared, paths):
    source = prepared.document["source_commit"]
    states = prepared.document["selected"]
    missing = [
        path
        for path in paths
        if states[path]["index"] is not None and states[path]["worktree"] is None
    ]
    present = [path for path in paths if states[path]["worktree"] is not None]
    for selected, mode in ((missing, "--cached"), (present, "--index")):
        if not selected:
            continue
        if mode == "--index":
            # Refresh copied/touched files' stat cache without staging bytes.
            before_refresh = _index(root)
            _require_git_boundary(root, prepared.write_paths)
            _git(root, "add", "--refresh", "--", *selected)
            if _index(root) != before_refresh:
                _fail("concurrent_index", "Index content changed during stat refresh")
        empty = (
            _git(root, "hash-object", "-t", "tree", "--stdin", content=b"")
            .stdout.decode()
            .strip()
        )
        deletion = _git(
            root,
            "diff",
            "--binary",
            "--full-index",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            "--no-color",
            "--no-relative",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--line-prefix=",
            source,
            empty,
            "--",
            *selected,
        ).stdout
        if not deletion:
            _fail("patch_unavailable", "Exact native deletion patch is unavailable")
        # Both modes verify the exact indexed before-image under Git's lock.
        # Never restore an index entry or follow a newer HEAD with git rm.
        _require_git_boundary(root, prepared.write_paths)
        _git(
            root,
            "apply",
            mode,
            "-p1",
            "--whitespace=nowarn",
            *("--include=" + path for path in selected),
            "-",
            content=deletion,
        )
    index = _index(root)
    if any(path in index or _worktree(root, path) is not None for path in paths):
        _fail(
            "cleanup_pending",
            "Git deletion is incomplete; retain the manifest and recover",
        )


def apply_native_project_removal(
    root: Path,
    *,
    expected: str,
    acknowledge: bool,
    source: str | None = None,
    only: tuple[str, ...] = (),
):
    if acknowledge is not True:
        _fail("acknowledgement_required", "Acknowledge the exact staged-deletion plan")
    root = Path(root).absolute()
    prepared = prepare_native_project_removal(root, source=source, only=only)
    if prepared.document["plan_identity"] != expected:
        _fail("plan_changed", "Native removal plan changed after review")
    from contextlib import ExitStack

    def require_lock_path(path):
        _require_git_boundary(root, (path,))

    with ProjectConfigurationStore.layout_lock(root):
        current = prepare_native_project_removal(root, source=source, only=only)
        if current.document != prepared.document:
            _fail("plan_changed", "Native removal inputs changed before application")
        # Missing-manifest recovery cannot rediscover an ancestor project or
        # create root lifecycle files. Its Git layout lock still owns publication.
        live = prepared.document["selected"][MANIFEST]["worktree"] is not None
        with ExitStack() as locks:
            if live:
                locks.enter_context(
                    project_lifecycle_lock(
                        root, operation="native-remove", require_path=require_lock_path
                    )
                )
                locks.enter_context(
                    ProjectConfigurationStore(root)._lock(
                        root, require_path=require_lock_path
                    )
                )
            supporting = sorted(set(prepared.entries) - {MANIFEST})
            _require_remaining(root, prepared, set(prepared.entries))
            phase = "supporting-files"
            try:
                _remove_group(root, prepared, supporting)
                _require_remaining(root, prepared, {MANIFEST})
                phase = "manifest"
                _remove_group(root, prepared, [MANIFEST])
                _require_remaining(root, prepared, set())
            except (NativeProjectRemovalError, OSError) as exc:
                failure = (
                    exc
                    if isinstance(exc, NativeProjectRemovalError)
                    else NativeProjectRemovalError(
                        "filesystem_failed", "Filesystem operation failed"
                    )
                )
                recovery = json.dumps(prepared.document["recovery_argv"])
                failure.message += (
                    f" Removal may be partial (phase: {phase}). "
                    f"Inspect a fresh recovery plan using this argv: {recovery}"
                )
                if failure is exc:
                    raise
                raise failure from exc
    return {
        "schema": SCHEMA,
        "state": "removed",
        "staged_deletions": sorted(
            set(prepared.entries)
            & _tree(root, prepared.document["current_head"]).keys()
        ),
        "observed_absent": sorted(prepared.entries),
        "already_absent_at_start": sorted(
            path
            for path, state in prepared.document["selected"].items()
            if state["index"] is None and state["worktree"] is None
        ),
        "retained": prepared.document["retained"],
        "source_commit": prepared.document["source_commit"],
        "recovery_argv": prepared.document["recovery_argv"],
        "committed": False,
        "runtime_state": "preserved; no recursive cleanup",
    }
