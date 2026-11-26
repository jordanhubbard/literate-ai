"""Acknowledged placement of legacy retained-project manifest and producer records."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import stat
import subprocess
import tempfile
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.adapters.catalog_import import _contained_catalog_records
from literate_ai.adapters.conversion_authority import FilesystemConversionAuthorityStore
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    move_file_between_owned_parents_exclusive,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.forward_skill_placement import plan_forward_skill_placement
from literate_ai.adapters.project_layout_planning import (
    _MAX_FILE_BYTES,
    _PRODUCERS,
    _SHARED,
    ProjectLayoutPlanError,
    _capture,
    _fail,
    _git_state,
    _stamp,
    plan_project_layout,
)
from literate_ai.adapters.repository_lineage import FilesystemRepositoryLineageStore
from literate_ai.adapters.retained_harness_receipts import (
    _load_retained_documents,
    _require_qualified_parity,
)
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.documentation import _INLINE_LINK, extract_markdown_links
from literate_ai.projects import (
    CONTAINED_SKILL_ROOT,
    FORWARD_SKILL_ROOT,
    PROJECT_FILENAME,
    ProjectConfigurationStore,
    documentation_files,
    load_project,
    serialize_project_configuration,
)
from literate_ai.test_receipts import (
    _canonical_tracked_bytes,
    _parse_tracked,
    _policy_mismatch,
)

SCHEMA = "literate-ai/project-layout-migration@1"
JOURNAL_SCHEMA = "literate-ai/project-layout-migration-journal@1"
_JOURNAL = "literate-layout-migration"
_RECORDS = tuple(".literate/" + name for name in sorted(_PRODUCERS))
_SOURCES = (*_RECORDS, PROJECT_FILENAME)
_LEGACY_RECEIPT = "verification/current.json"
_PRODUCER_LOCKS = (
    ".literate/conversion-authority.lock",
    ".literate/repository-lineage.lock",
)


def _ordered_sources(files: dict) -> tuple[str, ...]:
    additional = sorted(set(files) - set(_SOURCES))
    return (*_RECORDS, *additional, PROJECT_FILENAME)


def _worktree(root: Path) -> Path:
    require_safe_directory(root)
    if os.name != "posix":
        _fail("migration_platform", "exclusive legacy migration requires POSIX custody")
    if os.environ.keys() & {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_COMMON_DIR",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    }:
        _fail("git_unavailable", "migration requires actual Git worktree authority")
    directory = ProjectConfigurationStore.layout_metadata_directory(root)
    if directory is None or directory.stat().st_dev != root.stat().st_dev:
        _fail("git_unavailable", "migration requires same-volume Git administration")
    observed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if observed.returncode or Path(observed.stdout.strip()) != root:
        _fail("git_unavailable", "migration requires the application worktree root")
    return directory


def _require_worktree_members(root: Path, coordinates: tuple[str, ...]) -> None:
    staged = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    if staged.returncode:
        _fail("git_unavailable", "cannot inspect index boundaries")
    gitlinks = set()
    for item in staged.stdout.split(b"\0"):
        if item.startswith(b"160000 "):
            gitlinks.add(os.fsdecode(item.split(b"\t", 1)[1]))
    for coordinate in coordinates:
        target = root / coordinate
        for parent in target.parents:
            if parent == root:
                break
            relative = parent.relative_to(root).as_posix()
            if relative in gitlinks or os.path.lexists(parent / ".git"):
                _fail(
                    "git_boundary",
                    f"migration path belongs to another worktree: {coordinate}",
                )
        if coordinate in gitlinks:
            _fail("git_boundary", f"migration path is a Git link: {coordinate}")


def _identity(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _file(path: Path) -> tuple[list[int], bytes, int]:
    require_safe_directory(path.parent)
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or stat_is_link_or_reparse(before)
        or before.st_nlink != 1
        or before.st_size > _MAX_FILE_BYTES
    ):
        _fail("path_unsafe", f"migration requires bounded direct file {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if _stamp(os.fstat(stream.fileno())) != _stamp(before):
            _fail(
                "plan_stale", f"migration file changed before observation: {path.name}"
            )
        content = stream.read(_MAX_FILE_BYTES + 1)
    if _stamp(path.lstat()) != _stamp(before) or len(content) != before.st_size:
        _fail("plan_stale", f"migration file changed during observation: {path.name}")
    return (
        [before.st_dev, before.st_ino, before.st_mode],
        content,
        stat.S_IMODE(before.st_mode),
    )


def _flush(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write(path: Path, content: bytes, mode: int = 0o600) -> None:
    with path.open("xb") as stream:
        os.fchmod(stream.fileno(), mode)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _documentation_edits(
    project, requested: tuple[str, ...], files: dict, moved: dict
) -> tuple[dict, dict, list]:
    root = project.root
    plans, contents, mandatory = {}, {}, []
    approved = set(requested)
    for path in approved:
        canonical_relative_posix_path(path, label="reviewed reference")
    if len(approved) != len(requested):
        _fail("reference_authority", "duplicate reference approval")
    for document in sorted({project.agent_skill, *documentation_files(project)}):
        if document.suffix.casefold() != ".md":
            continue
        path = document.relative_to(root).as_posix()
        _, old, mode = _file(document)
        text = old.decode("utf-8")
        lines = text.splitlines(keepends=True)
        reviewed = []
        for link in extract_markdown_links(text):
            target = urlsplit(link.destination)
            if target.scheme or target.netloc or not target.path:
                continue
            subject = posixpath.normpath(
                posixpath.join(posixpath.dirname(path), unquote(target.path))
            )
            if subject not in moved:
                continue
            if (
                path not in approved
                or path in _SHARED
                or files.get(path, {}).get("role") == "application"
                or link.syntax != "inline"
            ):
                mandatory.append({"path": path, "line": link.line, "target": subject})
                continue
            target_path = posixpath.relpath(
                "litai/" + subject, posixpath.dirname(path) or "."
            )
            replacement = urlunsplit(
                ("", "", target_path, target.query, target.fragment)
            )
            line = lines[link.line - 1]
            candidates = [
                match.span(3 if match.group(3) is not None else 4)
                for match in _INLINE_LINK.finditer(line)
                if (match.group(3) or match.group(4)) == link.destination
            ]
            if len(candidates) != 1:
                mandatory.append({"path": path, "line": link.line, "target": subject})
                continue
            start, end = candidates[0]
            lines[link.line - 1] = line[:start] + replacement + line[end:]
            reviewed.append(
                {"line": link.line, "from": link.destination, "to": replacement}
            )
        if reviewed:
            new = "".join(lines).encode("utf-8")
            plans[path] = {
                "from": _identity(old),
                "to": _identity(new),
                "mode": mode,
                "links": reviewed,
            }
            contents[path] = new
    if approved - set(plans) - {item["path"] for item in mandatory}:
        _fail(
            "reference_authority",
            "approval selects no discovered moved-target reference",
        )
    return plans, contents, mandatory


def _read_selection(
    root: Path, references: tuple[str, ...], place_forward_skills: bool
) -> tuple[dict, Path, dict]:
    inventory = plan_project_layout(root)
    snapshot = ProjectConfigurationStore.discover(root)
    assert snapshot is not None
    root = snapshot.root
    git_dir = _worktree(root)
    if inventory["framework_directory"] is not None:
        _fail("migration_profile", "migration requires canonical legacy root authority")
    if os.path.lexists(git_dir / _JOURNAL):
        _fail("recovery_pending", "inspect or recover the existing migration journal")
    files = {item["path"]: item for item in inventory["members"]}
    if not all(path in files for path in _SOURCES):
        _fail(
            "migration_profile",
            "required retained-project producer records are missing",
        )
    project = load_project(root)
    state = FilesystemConversionAuthorityStore(root).load_optional()
    if state is None or state.project_id != snapshot.definition.project_id:
        _fail("migration_profile", "conversion authority does not own this project")
    _require_qualified_parity(_load_retained_documents(project))
    _, lineage = FilesystemRepositoryLineageStore(root).load()
    _contained_catalog_records(json.loads(_file(root / ".literate/imports.json")[1]))
    definition = snapshot.definition
    receipt = definition.test_receipt
    if receipt == _LEGACY_RECEIPT:
        policy = definition.test_receipt_policy
        if policy is None:
            _fail("migration_profile", "retained receipt requires its producer policy")
        if receipt in files:
            old = _file(root / receipt)[1]
            tracked, envelope = _parse_tracked(
                old, code="project.layout.receipt_invalid", label="legacy receipt"
            )
            if (
                tracked.project_id != definition.project_id
                or _policy_mismatch(policy, tracked) is not None
                or _canonical_tracked_bytes(tracked, envelope) != old
            ):
                _fail("receipt_invalid", "legacy receipt does not bind its producer")
        definition = replace(definition, test_receipt="litai/" + receipt)
    skill_coordinates, rewritten = {}, {}
    if place_forward_skills:
        skill_coordinates, rewritten = plan_forward_skill_placement(
            snapshot, lineage, files
        )
        definition = replace(
            definition, skill_roots=(*definition.skill_roots, CONTAINED_SKILL_ROOT)
        )
    selected = set(_SOURCES) | set(skill_coordinates)
    if receipt == _LEGACY_RECEIPT and receipt in files:
        selected.add(_LEGACY_RECEIPT)
    sources = _ordered_sources(selected)
    rewritten[PROJECT_FILENAME] = serialize_project_configuration(
        replace(definition, framework_directory="litai")
    )
    moves = {
        path: {
            "from": files[path]["identity"],
            "to": _identity(rewritten[path])
            if path in rewritten
            else files[path]["identity"],
            "mode": files[path]["mode"],
        }
        for path in sources
    }
    edits, new_documents, required_references = _documentation_edits(
        project, references, files, moves
    )
    _require_worktree_members(root, (*moves, *edits))
    result = {
        "schema": SCHEMA,
        "reference_edits": edits,
        "blocked_references": required_references,
        "applicable": not required_references,
        "project": str(root),
        "project_id": snapshot.definition.project_id,
        "root_node": list(directory_node(root)),
        "inventory_identity": inventory["plan_identity"],
        "git_state": inventory["git_state"],
        "scope": (
            "legacy retained metadata and imported forward Skill placement"
            if skill_coordinates
            else "legacy retained manifest and producer-record placement"
        ),
        "move": moves,
        "held": [
            {
                "path": item["path"],
                "role": item["role"],
                "disposition": item["decision"],
                "identity": item["identity"],
                "mode": item["mode"],
            }
            for item in inventory["members"]
            if item["path"] not in moves
        ],
        "remaining": [
            item for item in inventory["blockers"] if item["path"] not in moves
        ],
        "topology": inventory["topology"],
        "forward_skill_placements": skill_coordinates,
        "receipt_coordinate": definition.test_receipt,
        "receipt_renewal_required": True,
        "full_containment": False,
        "writes": False,
    }
    result["plan_identity"] = canonical_identity(result).uri
    return result, git_dir, {"rewritten": rewritten, "edits": new_documents}


def plan_legacy_layout_migration(
    selected: Path, references: tuple[str, ...], *, place_forward_skills: bool
) -> dict:
    return _read_selection(selected, references, place_forward_skills)[0]


def _known_locks(root: Path, framework: Path) -> tuple[Path, ...]:
    identity = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
    return (
        framework / ".litai-locks" / identity / "lifecycle.lock",
        *(framework / path for path in _PRODUCER_LOCKS),
        framework / f".{PROJECT_FILENAME}.write.lock",
    )


@contextmanager
def _reserve(root: Path, future: Path):
    with ExitStack() as held:
        for framework in (root, future):
            for path in _known_locks(root, framework):
                require_safe_directory(path.parent, allow_missing=True)
                held.enter_context(exclusive_cache_lock(path, timeout_seconds=0))
        yield


def _require_framework_git_boundary(root: Path, directory: Path) -> None:
    # The general observer omits the Git administration of its scan root. A
    # staged or placed framework directory is only eligible as ordinary data.
    if os.path.lexists(directory / ".git"):
        _fail(
            "git_boundary", "the framework directory gained independent Git authority"
        )
    if directory == root / "litai":
        _require_worktree_members(root, ("litai/" + PROJECT_FILENAME,))


def _inspect(root: Path, path: Path, files: dict) -> None:
    _require_framework_git_boundary(root, path)
    observed, _ = _capture(path)
    if any(Path(name).name == ".git" for name in observed):
        _fail("git_boundary", "a nested framework path gained Git authority")
    expected = {name: (item["mode"], item["to"]) for name, item in files.items()}
    lock_names = {
        item.relative_to(path).as_posix() for item in _known_locks(root, path)
    }
    actual = {
        name: (item["mode"], item["identity"])
        for name, item in observed.items()
        if item["kind"] == "file" and name not in lock_names
    }
    allowed_directories = {
        ancestor.as_posix()
        for name in (*expected, *lock_names)
        for ancestor in Path(name).parents
        if ancestor != Path(".")
    }
    if actual != expected or any(
        name not in allowed_directories
        for name, item in observed.items()
        if item["kind"] == "directory"
    ):
        _fail(
            "recovery_conflict",
            "placed framework contains unexpected or changed members",
        )


def _guard_application(root: Path, plan: dict, *, placed: bool) -> None:
    observed, _ = _capture(root)
    ignored_locks = {
        path.relative_to(root).as_posix() for path in _known_locks(root, root)
    }
    ignored_parents = {
        parent.as_posix()
        for path in ignored_locks
        for parent in Path(path).parents
        if parent != Path(".")
    }

    def relevant(path: str) -> bool:
        return not (placed and (path == "litai" or path.startswith("litai/")))

    files = {
        name: (item["mode"], item["identity"])
        for name, item in observed.items()
        if item["kind"] == "file" and name not in ignored_locks and relevant(name)
    }
    required = {
        item["path"]: (item["mode"], item["identity"])
        for item in plan["held"]
        if item["path"] not in ignored_locks
    }
    if placed:
        required.update(
            {
                name: (item["mode"], item["to"])
                for name, item in plan["reference_edits"].items()
            }
        )
    else:
        required.update(
            {name: (item["mode"], item["from"]) for name, item in plan["move"].items()}
        )
    directories = {
        name: item["mode"]
        for name, item in observed.items()
        if item["kind"] == "directory"
        and name not in ignored_parents
        and relevant(name)
    }
    required_directories = {
        item["path"]: item["mode"]
        for item in plan["topology"]
        if item["path"] not in ignored_parents | {"."}
    }
    if files != required or directories != required_directories:
        _fail("plan_stale", "application bytes or topology changed during migration")


def _move_file(source: Path, target: Path, item: dict, *, edited: bool = False) -> None:
    node, content, mode = _file(source)
    expected = (
        (item["edited_node"], item["to"]) if edited else (item["node"], item["from"])
    )
    if (node, _identity(content), mode) != (*expected, item["mode"]):
        _fail("recovery_conflict", f"legacy producer record changed: {source.name}")
    move_file_between_owned_parents_exclusive(
        source,
        target,
        expected_source=tuple(node),
        expected_source_parent=directory_node(source.parent),
        expected_destination_parent=directory_node(target.parent),
    )
    if _file(target) != (node, content, mode):
        _fail("recovery_conflict", f"moved producer record changed: {source.name}")
    _flush(source.parent)
    _flush(target.parent)


def _move_directory(source: Path, target: Path, node: list[int]) -> None:
    publish_directory_between_owned_parents_exclusive(
        source,
        target,
        expected_source=tuple(node),
        expected_source_parent=directory_node(source.parent),
        expected_destination_parent=directory_node(target.parent),
    )
    _flush(source.parent)
    _flush(target.parent)


def _journal(root: Path, git_dir: Path, plan: dict, content: dict) -> tuple[Path, dict]:
    with tempfile.TemporaryDirectory(
        prefix="litai-layout-stage-", dir=git_dir
    ) as stage:
        incoming = Path(stage) / "intent"
        incoming.mkdir(mode=0o700)
        (incoming / "original/.literate").mkdir(parents=True)
        future = incoming / "future"
        (future / ".literate").mkdir(parents=True)
        files = {}
        for path, item in plan["move"].items():
            node, old_content, mode = _file(root / path)
            if (_identity(old_content), mode) != (item["from"], item["mode"]):
                _fail("plan_stale", f"migration file changed after review: {path}")
            staged = content["rewritten"].get(path, old_content)
            (incoming / "original" / path).parent.mkdir(parents=True, exist_ok=True)
            (future / path).parent.mkdir(parents=True, exist_ok=True)
            _write(future / path, staged, mode)
            files[path] = {**item, "node": node}
        edits = {}
        for path, item in plan["reference_edits"].items():
            node, old, mode = _file(root / path)
            if (_identity(old), mode) != (item["from"], item["mode"]):
                _fail("plan_stale", f"reference document changed after review: {path}")
            (incoming / "original" / path).parent.mkdir(parents=True, exist_ok=True)
            edited = incoming / "edited" / path
            edited.parent.mkdir(parents=True, exist_ok=True)
            _write(edited, content["edits"][path], mode)
            edits[path] = {**item, "node": node, "edited_node": _file(edited)[0]}
        intent = {
            "schema": JOURNAL_SCHEMA,
            "edits": edits,
            "plan": plan,
            "files": files,
            "future_node": list(directory_node(future)),
        }
        intent["identity"] = canonical_identity(intent).uri
        _write(incoming / "intent.json", canonical_json_bytes(intent) + b"\n")
        for directory, _, _ in os.walk(incoming, topdown=False):
            _flush(Path(directory))
        target = git_dir / _JOURNAL
        _move_directory(incoming, target, list(directory_node(incoming)))
        return target, intent


def _guard_git(root: Path, plan: dict) -> None:
    if (
        list(directory_node(root)) != plan["root_node"]
        or _git_state(root) != plan["git_state"]
    ):
        _fail(
            "plan_stale",
            "worktree root, HEAD or index changed; inspect before recovery",
        )


def _load_journal(git_dir: Path, expected: str) -> tuple[Path, dict]:
    journal = git_dir / _JOURNAL
    if not journal.is_dir():
        _fail("recovery_unavailable", "no retained migration intent exists")
    try:
        intent = json.loads(_file(journal / "intent.json")[1])
        if not isinstance(intent, dict):
            raise ValueError("journal intent must be an object")
        identity = intent.pop("identity")
        plan = intent["plan"]
        files = intent["files"]
        edits = intent.get("edits", {})
        if not all(isinstance(item, dict) for item in (plan, files, edits)):
            raise ValueError("journal records must be objects")
        comparable = {
            key: value for key, value in plan.items() if key != "plan_identity"
        }
        skill_coordinates = plan.get("forward_skill_placements", {})
        expected_paths = {*_SOURCES, _LEGACY_RECEIPT, *skill_coordinates}
        if (
            intent["schema"] != JOURNAL_SCHEMA
            or canonical_identity(intent).uri != identity
            or plan["plan_identity"] != expected
            or canonical_identity(comparable).uri != expected
            or not {*_SOURCES, *skill_coordinates} <= set(files) <= expected_paths
            or set(files) != set(plan["move"])
            or any(
                not source.startswith(f"{FORWARD_SKILL_ROOT}/")
                or destination != f"litai/{source}"
                or files[source]["from"] != files[source]["to"]
                for source, destination in skill_coordinates.items()
            )
        ):
            raise ValueError("journal bindings differ")
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        raise ProjectLayoutPlanError(
            "recovery_conflict", "journal does not bind the acknowledged migration"
        ) from exc
    if set(edits) != set(plan.get("reference_edits", {})):
        _fail("recovery_conflict", "recorded reference edits differ from the plan")
    if (
        _LEGACY_RECEIPT in intent["files"]
        and plan.get("receipt_coordinate") != "litai/" + _LEGACY_RECEIPT
    ):
        _fail("recovery_conflict", "legacy receipt has no acknowledged destination")
    for name, rows in (("move", intent["files"]), ("reference_edits", edits)):
        for path, row in rows.items():
            canonical_relative_posix_path(path, label="journal member")
            if any(row.get(key) != value for key, value in plan[name][path].items()):
                _fail(
                    "recovery_conflict", f"recorded identities differ from plan: {path}"
                )
    return journal, intent


def _rollback(root: Path, directory: Path, intent: dict) -> None:
    plan, files = intent["plan"], intent["files"]
    edits = intent.get("edits", {})
    _guard_git(root, plan)
    _require_worktree_members(root, (*files, *edits))
    marker = directory / "rolled-back"
    if os.path.lexists(marker) and _file(marker)[1] != b"rolled back\n":
        _fail("recovery_conflict", "rollback completion marker changed")
    future = directory / "future"
    placed = root / "litai"
    visible = os.path.lexists(placed)
    current = placed if visible else future
    if list(directory_node(current)) != intent["future_node"]:
        _fail("recovery_conflict", "contained directory has foreign custody")
    _inspect(root, current, files)
    with _reserve(root, current):
        _inspect(root, current, files)
        for path, item in files.items():
            old, backup = root / path, directory / "original" / path
            old_present, backup_present = os.path.lexists(old), os.path.lexists(backup)
            if old_present == backup_present:
                _fail("recovery_conflict", f"cannot select one original at {path}")
            node, data, mode = _file(old if old_present else backup)
            if (node, _identity(data), mode) != (
                item["node"],
                item["from"],
                item["mode"],
            ):
                _fail("recovery_conflict", f"original producer record changed: {path}")
        for path, item in edits.items():
            live, backup, edited = (
                root / path,
                directory / "original" / path,
                directory / "edited" / path,
            )
            backup_present = os.path.lexists(backup)
            live_present, staged_present = (
                os.path.lexists(live),
                os.path.lexists(edited),
            )
            if not backup_present and (not live_present or not staged_present):
                _fail("recovery_conflict", f"reference recovery cannot identify {path}")
            if backup_present and live_present == staged_present:
                _fail(
                    "recovery_conflict",
                    f"reference recovery found a collision at {path}",
                )
            original = backup if backup_present else live
            node, data, mode = _file(original)
            if (node, _identity(data), mode) != (
                item["node"],
                item["from"],
                item["mode"],
            ):
                _fail("recovery_conflict", f"original reference changed: {path}")
            node, data, mode = _file(edited if staged_present else live)
            if (node, _identity(data), mode) != (
                item["edited_node"],
                item["to"],
                item["mode"],
            ):
                _fail("recovery_conflict", f"edited reference changed: {path}")
        if visible:
            _inspect(root, placed, files)
            _move_directory(placed, future, intent["future_node"])
        for path, item in edits.items():
            live, backup, edited = (
                root / path,
                directory / "original" / path,
                directory / "edited" / path,
            )
            if os.path.lexists(backup):
                if os.path.lexists(live):
                    _move_file(live, edited, item, edited=True)
                _move_file(backup, live, item)
        for path in _ordered_sources(files):
            backup = directory / "original" / path
            if os.path.lexists(backup):
                _move_file(backup, root / path, files[path])
        _guard_git(root, plan)
        if not os.path.lexists(marker):
            _write(marker, b"rolled back\n")
        elif _file(marker)[1] != b"rolled back\n":
            _fail("recovery_conflict", "rollback completion marker changed")
        _flush(directory)


def apply_legacy_layout_migration(
    selected: Path,
    expected: str,
    *,
    acknowledge: bool,
    references: tuple[str, ...],
    place_forward_skills: bool,
) -> dict:
    if not acknowledge:
        _fail("acknowledgement_required", "acknowledge the exact migration plan")
    snapshot = ProjectConfigurationStore.discover(selected)
    if snapshot is None:
        _fail("migration_profile", "no canonical legacy project is discoverable")
    root = snapshot.root
    _worktree(root)
    with ProjectConfigurationStore.layout_lock(root):
        plan, git_dir, content = _read_selection(root, references, place_forward_skills)
        if plan["plan_identity"] != expected:
            _fail("plan_stale", "migration inputs changed after review")
        if not plan["applicable"]:
            _fail(
                "reference_authority", "review and authorize the listed reference edits"
            )
        journal, intent = _journal(root, git_dir, plan, content)
        future = journal / "future"
        try:
            with _reserve(root, future):
                _guard_git(root, plan)
                _guard_application(root, plan, placed=False)
                _require_worktree_members(root, (*intent["files"], *intent["edits"]))
                _inspect(root, future, intent["files"])
                for path in _ordered_sources(intent["files"]):
                    _move_file(
                        root / path, journal / "original" / path, intent["files"][path]
                    )
                _guard_git(root, plan)
                _inspect(root, future, intent["files"])
                _require_framework_git_boundary(root, root / "litai")
                _move_directory(future, root / "litai", intent["future_node"])
                for path, item in intent["edits"].items():
                    _move_file(root / path, journal / "original" / path, item)
                    _move_file(
                        journal / "edited" / path, root / path, item, edited=True
                    )
                _inspect(root, root / "litai", intent["files"])
                _guard_application(root, plan, placed=True)
                _guard_git(root, plan)
                snapshot = ProjectConfigurationStore(root).read()
                if snapshot.manifest_path != root / "litai" / PROJECT_FILENAME:
                    _fail(
                        "recovery_conflict",
                        "contained authority did not become canonical",
                    )
                _write(journal / "completed", b"placement complete\n")
                _flush(journal)
        except (OSError, ValueError, RuntimeError) as exc:
            suffix = (
                exc.code.removeprefix("project.layout.")
                if isinstance(exc, ProjectLayoutPlanError)
                else "migration_interrupted"
            )
            raise ProjectLayoutPlanError(
                suffix,
                f"{exc} (retained journal; run project layout recover with {expected})",
            ) from exc
    return {**plan, "writes": True, "applied": True, "journal": str(journal)}


def recover_legacy_layout_migration(
    root: Path, expected: str, *, acknowledge: bool
) -> dict:
    if not acknowledge:
        _fail("acknowledgement_required", "acknowledge rollback of the exact migration")
    root = Path(root).absolute()
    _worktree(root)
    with ProjectConfigurationStore.layout_lock(root):
        git_dir = _worktree(root)
        journal, intent = _load_journal(git_dir, expected)
        if intent["plan"]["project"] != str(root):
            _fail("recovery_conflict", "journal belongs to another worktree")
        _rollback(root, journal, intent)
        archive = git_dir / f"{_JOURNAL}-rolled-back-{journal.stat().st_ino}"
        _move_directory(journal, archive, list(directory_node(journal)))
    return {
        **intent["plan"],
        "writes": True,
        "rolled_back": True,
        "journal": str(archive),
    }
