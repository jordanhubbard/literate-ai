"""Acknowledged placement of legacy retained-project manifest and producer records."""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import subprocess
import tempfile
from contextlib import ExitStack, contextmanager
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.catalog_import import _contained_catalog_records
from literate_ai.adapters.conversion_authority import FilesystemConversionAuthorityStore
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    move_file_between_owned_parents_exclusive,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.forward_skill_placement import plan_forward_skill_placement
from literate_ai.adapters.project_layout_filesystem import (
    flush_migration_directory,
    read_migration_file,
    write_migration_file,
)
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
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.documentation import _INLINE_LINK, extract_markdown_links
from literate_ai.projects import (
    CATALOG_PLACEMENT_ROOTS,
    CATALOG_SOURCE_ROOTS,
    CONTAINED_SKILL_ROOT,
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
_IMPORTS = ".literate/imports.json"
_REQUIRED_SOURCES = frozenset(_SOURCES) - {_IMPORTS}
_LEGACY_RECEIPT = "verification/current.json"
_LEGACY_RELEASE_POLICY = "literate.release.json"
_PRODUCER_LOCKS = (
    ".literate/conversion-authority.lock",
    ".literate/repository-lineage.lock",
)


def _ordered_sources(files: dict) -> tuple[str, ...]:
    additional = sorted(set(files) - set(_SOURCES))
    return (
        *(path for path in _RECORDS if path in files),
        *additional,
        PROJECT_FILENAME,
    )


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
    return read_migration_file(
        path, maximum_bytes=_MAX_FILE_BYTES, fail=_fail, stamp=_stamp
    )


def _flush(directory: Path) -> None:
    flush_migration_directory(directory)


def _write(path: Path, content: bytes, mode: int = 0o600) -> None:
    write_migration_file(path, content, mode)


def _reference_framework_base_transition(root, files, rewritten, edits, documents):
    """Build a current base only for original owned before-bytes, never review pins.

    The caller stages this ordinary producer record with the reference edits in
    the existing journal. Historical initialization rows and old blobs remain.
    """
    if not documents:
        return None

    def original_record(path):
        raw = _file(root / path)[1]
        if _identity(raw) != files[path]["identity"]:
            _fail("plan_stale", f"reference producer changed during planning: {path}")
        return raw

    baseline = ProjectInitializationBaseline.from_dict(
        json.loads(original_record(".literate/initialization-baseline.json"))
    )
    origin = ProjectInitializationOrigin.from_dict(
        json.loads(original_record(".literate/initialization-origin.json"))
    )
    if baseline.origin_identity != origin.identity:
        _fail(
            "reference_authority", "reference initialization origin and baseline differ"
        )
    checkpoint = ".literate/update-bases.json"
    old = original_record(checkpoint)
    bases = UpdateBases.from_observed(root, rewritten.get(checkpoint, old))
    initial = {row.path: row.identity.uri for row in baseline.files}
    imported = set()
    if _IMPORTS in files:
        catalog = CatalogImportsFile.from_dict(json.loads(original_record(_IMPORTS)))
        imported.update(
            row.path
            for item in (*catalog.imports, *catalog.decisions)
            for row in item.files
        )
    changed = False
    for path, content in documents.items():
        before = bases.scopes["framework"].get(path, initial.get(path))
        if (
            path not in imported
            and path not in bases.scopes["catalog"]
            and path not in bases.sources
            and before == edits[path]["from"]
        ):
            bases.advance("framework", path, content)
            changed = True
    return bases.serialized() if changed else None


def _documentation_edits(
    project,
    requested: tuple[str, ...],
    files: dict,
    moved: dict,
    *,
    catalog_paths: bool = False,
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
        if catalog_paths:
            for line_number, line in enumerate(lines, 1):
                edits = []
                tokens = list(re.finditer(r"(?<!\x60)\x60([^\x60]+)\x60(?!\x60)", line))
                command = re.match(
                    r"^\s*litai (?:lock|plan|rebuild|generate) "
                    r"((?:components|samples)/[A-Za-z0-9_./-]+)(?:\s|$)",
                    line,
                )
                if command and f"{command[1].removesuffix('/')}/component.md" in moved:
                    tokens.append(command)
                for match in tokens:
                    token = match[1]
                    subject = token.removesuffix("/")
                    if subject.split("/", 1)[0] not in CATALOG_SOURCE_ROOTS:
                        continue
                    selected = subject in moved or match is command
                    if match is not command and token.endswith("/"):
                        subtree = {
                            name for name in files if name.startswith(subject + "/")
                        }
                        selected = bool(subtree) and subtree.issubset(moved)
                    if not selected:
                        continue
                    if (
                        path not in approved
                        or path in _SHARED
                        or files.get(path, {}).get("role") == "application"
                    ):
                        mandatory.append(
                            {"path": path, "line": line_number, "target": subject}
                        )
                        continue
                    replacement = f"litai/{token}"
                    edits.append((*match.span(1), replacement))
                    reviewed.append(
                        {"line": line_number, "from": token, "to": replacement}
                    )
                boundary = len(line)
                for start, end, replacement in sorted(edits, reverse=True):
                    if end > boundary:
                        _fail(
                            "reference_authority",
                            f"overlapping references in {path} at line {line_number}",
                        )
                    line = line[:start] + replacement + line[end:]
                    boundary = start
                lines[line_number - 1] = line
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
    root: Path,
    references: tuple[str, ...],
    place_forward_skills: bool,
    place_imported_catalogs: bool = False,
    place_release_policy: bool = False,
) -> tuple[dict, Path, dict]:
    inventory = plan_project_layout(root)
    snapshot = ProjectConfigurationStore.discover(root)
    assert snapshot is not None
    root = snapshot.root
    git_dir = _worktree(root)
    if inventory["framework_directory"] is not None:
        if (
            inventory["framework_directory"] != "litai"
            or not place_imported_catalogs
            or place_forward_skills
            or place_release_policy
        ):
            _fail(
                "migration_profile",
                "contained continuation requires only --place-imported-catalogs",
            )
        from literate_ai.adapters.project_layout_planning import (
            plan_contained_catalog_continuation,
        )

        plan, selection = plan_contained_catalog_continuation(root, references)
        return plan, git_dir, {"catalog_continuation": selection}
    if os.path.lexists(git_dir / _JOURNAL):
        _fail("recovery_pending", "inspect or recover the existing migration journal")
    files = {item["path"]: item for item in inventory["members"]}
    if not _REQUIRED_SOURCES <= files.keys():
        _fail(
            "migration_profile",
            "required retained-project producer records are missing",
        )
    project = load_project(root)
    state = FilesystemConversionAuthorityStore(root).load_optional()
    if state is None or state.project_id != snapshot.definition.project_id:
        _fail("migration_profile", "conversion authority does not own this project")
    _require_qualified_parity(_load_retained_documents(project))
    parent, lineage = FilesystemRepositoryLineageStore(root).load()
    if _IMPORTS in files:
        _contained_catalog_records(json.loads(_file(root / _IMPORTS)[1]))
    else:
        bases = UpdateBases(root)
        if (
            parent.mode.value != "root"
            or bases.scopes["catalog"]
            or bases.sources
            or place_forward_skills
            or place_imported_catalogs
        ):
            _fail(
                "migration_profile",
                "missing catalog provenance permits only root metadata placement "
                "without catalog history",
            )
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
    skill_coordinates, rewritten, catalog_blockers = {}, {}, []
    if place_forward_skills and place_imported_catalogs:
        _fail("migration_profile", "select one catalog placement scope")
    if place_forward_skills or place_imported_catalogs:
        skill_coordinates, rewritten, catalog_blockers = plan_forward_skill_placement(
            snapshot,
            lineage,
            files,
            read_file=lambda relative: _file(root / relative)[1],
            include_related=place_imported_catalogs,
        )
        definition = replace(
            definition, skill_roots=(*definition.skill_roots, CONTAINED_SKILL_ROOT)
        )
        for kind, primary in CATALOG_PLACEMENT_ROOTS.items():
            if kind == "skill":
                continue
            candidates = (primary, "samples") if kind == "component" else (primary,)
            placed_roots = tuple(
                f"litai/{name}"
                for name in candidates
                if any(path.startswith(name + "/") for path in skill_coordinates)
            )
            if placed_roots:
                field = f"{kind}_roots"
                definition = replace(
                    definition, **{field: (*getattr(definition, field), *placed_roots)}
                )
    selected = (set(_SOURCES) & files.keys()) | set(skill_coordinates)
    if receipt == _LEGACY_RECEIPT and receipt in files:
        selected.add(_LEGACY_RECEIPT)
    if place_release_policy:
        from literate_ai.project_releases import (
            ProjectReleaseError,
            ReleasePolicy,
            current_release_version,
        )

        try:
            policy = ReleasePolicy.from_dict(
                json.loads(_file(root / _LEGACY_RELEASE_POLICY)[1])
            )
            current_release_version(root, policy)
        except (OSError, ValueError, ProjectReleaseError) as exc:
            _fail(
                "release_policy_placement",
                f"cannot place the declared release policy: {exc}",
            )
        selected.add(_LEGACY_RELEASE_POLICY)
        external_paths = {
            policy.changelog_path,
            *policy.documentation_authority_paths,
            *(
                item.path
                for item in (policy.version_authority, *policy.version_mirrors)
            ),
        } - {PROJECT_FILENAME}
        if external_paths & selected:
            _fail(
                "release_policy_placement",
                "a released external file would move out of its declared path",
            )
        typed_gate = policy.gate_argv[:2] == ("litai", "test")
        if any(
            Path(arg).as_posix() in selected
            or (Path(arg) / "component.md").as_posix() in selected
            for index, arg in enumerate(policy.gate_argv)
            if not (typed_gate and index == 2)
        ):
            _fail(
                "release_policy_placement",
                "release gate references a moved path outside its Component argument",
            )
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
        project, references, files, moves, catalog_paths=place_imported_catalogs
    )
    reference_bases = _reference_framework_base_transition(
        root, files, rewritten, edits, new_documents
    )
    if reference_bases is not None:
        checkpoint = ".literate/update-bases.json"
        rewritten[checkpoint] = reference_bases
        moves[checkpoint]["to"] = _identity(reference_bases)
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
            "legacy retained metadata and imported catalog placement"
            if place_imported_catalogs
            else "legacy retained metadata and imported forward Skill placement"
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
        "forward_skill_placements": {
            k: v
            for k, v in skill_coordinates.items()
            if k.startswith("skills/specification-to-source/")
        },
        **(
            {
                "catalog_placements": skill_coordinates,
                "catalog_placement_blockers": catalog_blockers,
            }
            if place_imported_catalogs
            else {}
        ),
        **(
            {"release_policy_coordinate": f"litai/{_LEGACY_RELEASE_POLICY}"}
            if place_release_policy
            else {}
        ),
        "receipt_coordinate": definition.test_receipt,
        "receipt_renewal_required": True,
        "full_containment": False,
        "writes": False,
    }
    result["plan_identity"] = canonical_identity(result).uri
    return result, git_dir, {"rewritten": rewritten, "edits": new_documents}


def plan_legacy_layout_migration(
    selected: Path,
    references: tuple[str, ...],
    *,
    place_forward_skills: bool,
    place_imported_catalogs: bool = False,
    place_release_policy: bool = False,
) -> dict:
    return _read_selection(
        selected,
        references,
        place_forward_skills,
        place_imported_catalogs,
        place_release_policy,
    )[0]


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
        skill_coordinates = plan.get(
            "catalog_placements", plan.get("forward_skill_placements", {})
        )
        expected_paths = {*_SOURCES, _LEGACY_RECEIPT, *skill_coordinates}
        release_paths = (
            {_LEGACY_RELEASE_POLICY}
            if plan.get("release_policy_coordinate")
            == f"litai/{_LEGACY_RELEASE_POLICY}"
            else set()
        )
        expected_paths.update(release_paths)
        if (
            intent["schema"] != JOURNAL_SCHEMA
            or canonical_identity(intent).uri != identity
            or plan["plan_identity"] != expected
            or canonical_identity(comparable).uri != expected
            or not {*_REQUIRED_SOURCES, *skill_coordinates, *release_paths}
            <= set(files)
            <= expected_paths
            or any(files[path]["from"] != files[path]["to"] for path in release_paths)
            or set(files) != set(plan["move"])
            or any(
                source.split("/", 1)[0] not in CATALOG_SOURCE_ROOTS
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
    place_imported_catalogs: bool = False,
    place_release_policy: bool = False,
) -> dict:
    if not acknowledge:
        _fail("acknowledgement_required", "acknowledge the exact migration plan")
    snapshot = ProjectConfigurationStore.discover(selected)
    if snapshot is None:
        _fail("migration_profile", "no canonical legacy project is discoverable")
    root = snapshot.root
    _worktree(root)
    with ProjectConfigurationStore.layout_lock(root):
        plan, git_dir, content = _read_selection(
            root,
            references,
            place_forward_skills,
            place_imported_catalogs,
            place_release_policy,
        )
        if plan["plan_identity"] != expected:
            _fail("plan_stale", "migration inputs changed after review")
        if not plan["applicable"]:
            _fail(
                "reference_authority", "review and authorize the listed reference edits"
            )
        if "catalog_continuation" in content:
            from literate_ai.adapters.project_layout_continuation import (
                apply_catalog_continuation,
            )

            return apply_catalog_continuation(content["catalog_continuation"], expected)
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
    root: Path,
    expected: str,
    *,
    acknowledge: bool,
    successor_plan_identity: str | None = None,
) -> dict:
    if not acknowledge:
        _fail("acknowledgement_required", "acknowledge rollback of the exact migration")
    root = Path(root).absolute()
    _worktree(root)
    with ProjectConfigurationStore.layout_lock(root):
        git_dir = _worktree(root)
        from literate_ai.adapters.project_layout_continuation import (
            journal_path,
            recover_catalog_continuation,
        )

        continuation = journal_path(root, expected)
        require_safe_directory(continuation.parent, allow_missing=True)
        if os.path.lexists(continuation):
            require_safe_directory(continuation)
            return recover_catalog_continuation(
                root,
                expected,
                **(
                    {"successor_plan_identity": successor_plan_identity}
                    if successor_plan_identity is not None
                    else {}
                ),
            )
        if successor_plan_identity is not None:
            _fail(
                "framework_scope_conflict",
                "successor identity requires a catalog journal",
            )
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
