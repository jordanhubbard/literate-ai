"""Read-only containment decisions for older initialized projects.

This is a consumer of producer provenance, not a migration writer. Historical
membership and matching bytes describe provenance; neither grants move authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import unicodedata
from pathlib import Path
from typing import Any

from literate_ai._filesystem import (
    require_safe_directory,
    stat_is_link_or_reparse,
)
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    ContentIdentity,
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
    canonical_identity,
)
from literate_ai.contracts.catalog_imports import CATALOG_IMPORTS_SCHEMA
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import ProjectConfigurationStore

PLAN_SCHEMA = "literate-ai/project-layout-plan@1"
_MAX_ENTRIES = 8192
_MAX_FILE_BYTES = 16 * 1024 * 1024
_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_ROOT_ADAPTERS = frozenset(
    {"AGENTS.md", "CLAUDE.md", ".cursor/rules/literate-ai.mdc", "agents/openai.yaml"}
)
_SHARED = _ROOT_ADAPTERS | {".gitignore", "CHANGELOG.md", "README.md", "Makefile"}
_ROOT_FIELDS = (
    "component_roots",
    "flavor_roots",
    "skill_roots",
    "workflow_roots",
    "routing_roots",
    "mcp_roots",
    "documentation_roots",
)
_PRODUCERS = {
    "initialization-origin.json": "initialization",
    "initialization-baseline.json": "initialization",
    "imports.json": "catalog import",
    "update-bases.json": "template/catalog update",
    "repository-parent.json": "repository lineage",
    "repository-lineage.json": "repository lineage",
    "conversion-authority.json": "conversion authority",
    "harness-inventory.json": "native harness inventory",
    "legacy-harness-baseline.json": "native harness baseline",
    "legacy-wrapper-parity.json": "retained parity",
    "legacy-lift-shift.json": "retained layout",
}


class ProjectLayoutPlanError(ValueError):
    def __init__(self, suffix: str, message: str) -> None:
        self.code = "project.layout." + suffix
        self.message = message
        super().__init__(message)


def _fail(suffix: str, message: str) -> None:
    raise ProjectLayoutPlanError(suffix, message)


def _stamp(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
        value.st_nlink,
    )


def _capture(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, bytes]]:
    """Bound a no-follow observation, including unknown and special members."""
    observations: dict[str, dict[str, Any]] = {}
    contents: dict[str, bytes] = {}
    total = 0
    device = root.lstat().st_dev
    pending = [root]
    while pending:
        directory = pending.pop()
        require_safe_directory(directory)
        before = directory.lstat()
        with os.scandir(directory) as entries:
            children = []
            aliases: set[str] = set()
            for entry in entries:
                if len(observations) + len(children) >= _MAX_ENTRIES:
                    _fail("entry_limit", "containment observation exceeds entry limit")
                alias = unicodedata.normalize("NFC", entry.name.casefold())
                if alias in aliases:
                    _fail("path_alias", "containment paths have a portable alias")
                aliases.add(alias)
                if directory == root and entry.name == ".git":
                    if stat_is_link_or_reparse(entry.stat(follow_symlinks=False)):
                        _fail("path_unsafe", "Git administration is redirected")
                    continue
                children.append(entry.name)
        for name in sorted(children):
            path = directory / name
            relative = path.relative_to(root).as_posix()
            canonical_relative_posix_path(relative, label="containment member")
            named = path.lstat()
            if stat_is_link_or_reparse(named) or named.st_dev != device:
                _fail("path_unsafe", f"containment member is redirected: {relative}")
            record: dict[str, Any] = {
                "kind": "directory" if stat.S_ISDIR(named.st_mode) else "file",
                "mode": stat.S_IMODE(named.st_mode),
                "stamp": _stamp(named),
            }
            if stat.S_ISDIR(named.st_mode):
                pending.append(path)
            elif stat.S_ISREG(named.st_mode) and named.st_nlink == 1:
                if (
                    named.st_size > _MAX_FILE_BYTES
                    or total + named.st_size > _MAX_TOTAL_BYTES
                ):
                    _fail("byte_limit", "containment observation exceeds byte limit")
                fd = os.open(
                    path,
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0)
                    | getattr(os, "O_BINARY", 0),
                )
                try:
                    opened = os.fstat(fd)
                    if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
                        _fail(
                            "path_unsafe",
                            f"containment member is not direct: {relative}",
                        )
                    with os.fdopen(fd, "rb", closefd=False) as stream:
                        content = stream.read(_MAX_FILE_BYTES + 1)
                    after = os.fstat(fd)
                    closing = path.lstat()
                    if (
                        _stamp(opened) != _stamp(after)
                        or _stamp(named) != _stamp(closing)
                        or (
                            opened.st_dev,
                            opened.st_ino,
                            opened.st_size,
                            opened.st_mtime_ns,
                        )
                        != (
                            named.st_dev,
                            named.st_ino,
                            named.st_size,
                            named.st_mtime_ns,
                        )
                        or len(content) != named.st_size
                    ):
                        _fail(
                            "capture_changed", f"containment member changed: {relative}"
                        )
                finally:
                    os.close(fd)
                total += len(content)
                contents[relative] = content
                record.update(
                    size=len(content),
                    identity="sha256:" + hashlib.sha256(content).hexdigest(),
                )
            else:
                _fail("path_unsafe", f"unsupported member topology: {relative}")
            observations[relative] = record
        if _stamp(before) != _stamp(directory.lstat()):
            _fail("capture_changed", "containment directory changed during capture")
    return observations, contents


def _json(contents: dict[str, bytes], relative: str) -> dict[str, Any]:
    if relative not in contents:
        _fail("provenance_missing", f"required producer record is missing: {relative}")
    try:

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON key")
                result[key] = value
            return result

        value = json.loads(contents[relative], object_pairs_hook=unique)
        if not isinstance(value, dict):
            raise ValueError("producer record must be an object")
        return value
    except (ValueError, UnicodeError) as exc:
        raise ProjectLayoutPlanError(
            "provenance_invalid", f"invalid producer record: {relative}"
        ) from exc


def _git_state(root: Path) -> dict[str, str] | None:
    # Git itself resolves the applicable worktree. A canonical project may be
    # nested in a larger repository; absence of a local marker is not absence
    # of index authority. Refuse an unreadable/redirected marker, rather than
    # treating failed discovery as an unversioned project.
    marker_found = False
    for ancestor in (root, *root.parents):
        try:
            marker = (ancestor / ".git").lstat()
        except FileNotFoundError:
            continue
        if stat_is_link_or_reparse(marker) or not (
            stat.S_ISREG(marker.st_mode) or stat.S_ISDIR(marker.st_mode)
        ):
            _fail("git_unavailable", "Git administration is redirected or unsafe")
        marker_found = True
        break
    if not marker_found:
        return None
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_OPTIONAL_LOCKS="0",
        GIT_ALLOW_PROTOCOL="",
        GIT_NO_LAZY_FETCH="1",
        GIT_NO_REPLACE_OBJECTS="1",
    )
    result = {}
    for label, arguments in (
        ("head", ["rev-parse", "--verify", "HEAD"]),
        ("index", ["ls-files", "--stage", "-z"]),
    ):
        process = run_bounded_process(
            [
                "git",
                "--no-optional-locks",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                "-C",
                str(root),
                *arguments,
            ],
            cwd=root,
            environment=environment,
            timeout_seconds=15,
            stdout_limit_bytes=8 * 1024 * 1024,
            stderr_limit_bytes=8192,
            error_prefix="layout_git",
            trace=False,
            terminate_descendants=True,
        )
        if process.returncode != 0:
            _fail("git_unavailable", "Git HEAD/index authority could not be inspected")
        result[label] = "sha256:" + hashlib.sha256(process.stdout).hexdigest()
    return result


def plan_project_layout(start: Path) -> dict[str, Any]:
    """Return prospective file decisions; never acquire a writer lock or fetch."""
    selected = Path(start).absolute()
    require_safe_directory(selected if selected.is_dir() else selected.parent)
    snapshot = ProjectConfigurationStore.discover(selected)
    if snapshot is None:
        _fail("project_missing", "no project authority found")
    root = snapshot.root
    context = ProjectConfigurationStore.context(root)

    def capture_git():
        return (
            _git_state(root),
            _git_state(context.framework_root)
            if context.framework_root != root
            else None,
        )

    git_state, framework_git_state = capture_git()
    prefix = context.framework_root.relative_to(root).as_posix()
    prefix = "" if prefix == "." else prefix + "/"

    def capture():
        nodes, data = _capture(context.framework_root)
        return (
            {prefix + path: value for path, value in nodes.items()},
            {prefix + path: value for path, value in data.items()},
        )

    observed, contents = capture()
    manifest = snapshot.manifest_path.relative_to(root).as_posix()
    if contents.get(manifest) != snapshot.content:
        _fail("capture_changed", "project authority changed during capture")
    baseline_path = prefix + ".literate/initialization-baseline.json"
    origin_path = prefix + ".literate/initialization-origin.json"
    baseline = ProjectInitializationBaseline.from_dict(_json(contents, baseline_path))
    origin = ProjectInitializationOrigin.from_dict(_json(contents, origin_path))
    if baseline.origin_identity != origin.identity:
        _fail("provenance_invalid", "initialization origin and baseline disagree")
    binding = context.directory_binding
    if binding is None:
        _fail("capture_changed", "project directory binding is unavailable")
    topology = [{"path": ".", "kind": "directory", "mode": stat.S_IMODE(binding[0][2])}]
    if context.framework_root != root:
        topology.append(
            {
                "path": prefix.rstrip("/"),
                "kind": "directory",
                "mode": stat.S_IMODE(binding[1][2]),
            }
        )
    topology.extend(
        [
            {"path": path, "mode": value["mode"], "kind": "directory"}
            for path, value in sorted(observed.items())
            if value["kind"] == "directory"
        ]
    )
    if context.framework_root != root and baseline.profile == "native":
        closing, _ = capture()
        if (
            observed != closing
            or ProjectConfigurationStore.context(root) != context
            or capture_git() != (git_state, framework_git_state)
        ):
            _fail("capture_changed", "contained native inputs changed during planning")
        result = {
            "schema": PLAN_SCHEMA,
            "mode": "read-only",
            "project_id": snapshot.definition.project_id,
            "profile": "native",
            "framework_directory": "litai",
            "target": "litai",
            "manifest": manifest,
            "git_state": git_state,
            "framework_git_state": framework_git_state,
            "producer_identities": {
                path: observed[path]["identity"]
                for path in (manifest, baseline_path, origin_path)
            },
            "members": [
                {
                    "path": path,
                    "decision": "keep",
                    "role": "existing native profile member",
                    "mode": value["mode"],
                    "size": value["size"],
                    "identity": value["identity"],
                    "target": None,
                    "provenance": None,
                    "renewal": None,
                }
                for path, value in sorted(observed.items())
                if value["kind"] == "file"
            ],
            "reference_edits": [],
            "topology": topology,
            "producer_coordinates": [],
            "blockers": [],
            "apply_supported": False,
            "writes": False,
            "qualification": False,
            "planning_complete": True,
            "scope": "already-contained native profile; no legacy relocation proposed",
        }
        result["plan_identity"] = canonical_identity(result).uri
        return result
    initialized = {item.path: item for item in baseline.files}
    blockers: list[dict[str, str]] = []

    def block(path: str, owner: str, reason: str) -> None:
        item = {"path": path, "owner": owner, "reason": reason}
        if item not in blockers:
            blockers.append(item)

    imports_path = prefix + CatalogImportsFile.PATH
    imported: dict[str, list[dict[str, str]]] = {}
    if imports_path in contents:
        value = _json(contents, imports_path)
        if value.get("schema") != CATALOG_IMPORTS_SCHEMA or not isinstance(
            value.get("imports"), list
        ):
            _fail(
                "provenance_invalid", "catalog import record has an unsupported shape"
            )
        imports = CatalogImportsFile.from_dict(value)
        for item in imports.imports:
            for file in item.files:
                canonical_relative_posix_path(file.path, label="catalog destination")
                ContentIdentity.parse_uri(file.identity)
                imported.setdefault(file.path, []).append(
                    {
                        "identity": file.identity,
                        "source_project": item.source.project_id,
                        "source_project_identity": item.source.project_identity,
                    }
                )
    bases_path = prefix + ".literate/update-bases.json"
    bases = UpdateBases(root)
    if bases.original != contents.get(bases_path):
        _fail("capture_changed", "update provenance changed during capture")
    catalog_bases = bases.scopes["catalog"]
    framework_bases = bases.scopes["framework"]
    layout_path = prefix + ".literate/legacy-lift-shift.json"
    implementation = None
    if layout_path in contents:
        from literate_ai.adapters.retained_layout import resolve_structural_layout

        layout = resolve_structural_layout(root, _json(contents, layout_path))
        implementation = layout.implementation_directory
    contained = context.framework_root != root
    native = baseline.profile == "native"
    if not contained and any(
        unicodedata.normalize("NFC", name.casefold()) == "litai"
        for name in {path.split("/", 1)[0] for path in observed}
    ):
        _fail("target_occupied", "the litai target is already occupied or aliased")
    if contained and not native:
        block(
            manifest,
            "project context",
            "contained canonical migration is not yet supported",
        )
    if not native and implementation is None:
        block(
            manifest,
            "retained layout",
            "profile has no supported retained application partition",
        )
    members = []
    roots = tuple(
        path for field in _ROOT_FIELDS for path in getattr(snapshot.definition, field)
    )
    for path, observation in sorted(observed.items()):
        if observation["kind"] != "file":
            continue
        provenance = {
            "initialization": initialized[path].identity.uri
            if path in initialized
            else None,
            "framework_base": framework_bases.get(path),
            "catalog_base": catalog_bases.get(path),
            "imports": imported.get(path, []),
        }
        target = None
        renewal = None
        if implementation is not None and (
            path == implementation or path.startswith(implementation + "/")
        ):
            role, decision = "application", "keep"
        elif path in _SHARED:
            role, decision = "shared integration", "owner decision required"
            block(
                path,
                "host repository",
                "partition custom text and establish the minimal external adapter",
            )
        elif path.rsplit("/", 1)[-1].startswith(".component.") and path.endswith(
            ".write.lock"
        ):
            role, decision = "coordination candidate", "writer fencing required"
            renewal = "Component writer"
            block(
                path,
                renewal,
                "named coordination file does not prove active ownership; "
                "reserve both writer coordinates",
            )
        elif (
            path.rsplit("/", 1)[-1]
            in {"component.lock.json", "component.resolution-audit.json"}
            or (
                path.rsplit("/", 1)[-1].startswith("component.resolution-audit.")
                and path.endswith(".json")
            )
            or b"<!-- literate-ai:authority-reviewed " in contents[path]
        ):
            role, decision = "producer evidence", "producer transition required"
            renewal = (
                "documentation authority"
                if b"<!-- literate-ai:authority-reviewed " in contents[path]
                else "Component resolution"
            )
            block(
                path,
                renewal,
                "path-bound evidence requires fresh producer review; "
                "preserve historical bytes",
            )
        elif path.startswith(prefix + ".literate/"):
            name = path.rsplit("/", 1)[-1]
            if name.endswith(".lock"):
                role, decision = "coordination", "writer fencing required"
                renewal = "reserve old and new producer lock coordinates"
            else:
                role, decision = "producer record", "producer transition required"
                renewal = _PRODUCERS.get(name, "unresolved producer")
            block(
                path,
                renewal or "producer",
                "preserve historical record; transition through its producing owner",
            )
        elif (
            path == manifest
            or path == snapshot.definition.agent_skill
            or (
                path.rsplit("/", 1)[-1]
                in {
                    "component.md",
                    "flavor.md",
                    "SKILL.md",
                    "workflow.md",
                    "routing.md",
                }
                and any(
                    path == catalog or path.startswith(catalog + "/")
                    for catalog in roots
                )
                and (
                    path in initialized
                    or path in imported
                    or path in catalog_bases
                    or path in framework_bases
                )
            )
        ):
            role, decision = "framework authority", "prospective whole-file relocation"
            target = path if contained else "litai/" + path
            if path != manifest:
                block(
                    path,
                    "authority references",
                    "typed and embedded references require owner review "
                    "before relocation",
                )
        else:
            role, decision = "unresolved", "owner decision required"
            block(
                path,
                "host repository",
                "producer provenance does not establish semantic ownership",
            )
        members.append(
            {
                "path": path,
                "role": role,
                "decision": decision,
                "target": target,
                "mode": observation["mode"],
                "size": observation["size"],
                "identity": observation["identity"],
                "provenance": provenance,
                "renewal": renewal,
            }
        )
    edits = []
    producer_coordinates = []
    if snapshot.definition.test_receipt is not None:
        producer_coordinates.append(
            {
                "field": "test_receipt",
                "path": snapshot.definition.test_receipt,
                "owner": "test receipt",
                "disposition": "renew through producer after relocation",
            }
        )
    if snapshot.definition.source_cache is not None:
        for cache in snapshot.definition.source_cache.targets:
            producer_coordinates.append(
                {
                    "field": "source_cache",
                    "target_id": cache.target_id,
                    "root_kind": cache.root_kind,
                    "reference": cache.root_reference,
                    "disposition": "not a project path"
                    if cache.root_kind == "operator-bound"
                    else "producer-owned coordinate; explicit transition required",
                }
            )
    if not contained:
        edits.append({"field": "framework_directory", "from": None, "to": "litai"})
        for field in (*_ROOT_FIELDS, "agent_skill"):
            old = getattr(snapshot.definition, field)
            values = (old,) if isinstance(old, str) else old
            targets = ["litai/" + value for value in values]
            known_agent = next(
                (
                    member["target"]
                    for member in members
                    if field == "agent_skill" and member["path"] == old
                ),
                None,
            )
            edits.append(
                {
                    "field": field,
                    "from": old,
                    "to": known_agent
                    if isinstance(old, str)
                    else []
                    if not targets
                    else None,
                    "status": "requires member and reference resolution",
                }
            )
        block(
            manifest,
            "migration transaction",
            "old/new writer fencing, durable journal and producer renewal "
            "remain required",
        )
    closing, _ = capture()
    if (
        observed != closing
        or ProjectConfigurationStore.context(root) != context
        or capture_git() != (git_state, framework_git_state)
    ):
        _fail("capture_changed", "containment inputs changed during planning")
    result = {
        "schema": PLAN_SCHEMA,
        "mode": "read-only",
        "project_id": snapshot.definition.project_id,
        "scope": "legacy containment planning; unresolved transitions block migration",
        "profile": baseline.profile,
        "framework_directory": snapshot.definition.framework_directory,
        "target": "litai",
        "manifest": manifest,
        "git_state": git_state,
        "framework_git_state": framework_git_state,
        "producer_identities": {
            path: observed[path]["identity"]
            for path in sorted(contents)
            if path
            in {
                manifest,
                baseline_path,
                origin_path,
                imports_path,
                bases_path,
                layout_path,
            }
        },
        "members": members,
        "topology": topology,
        "producer_coordinates": producer_coordinates,
        "reference_edits": edits,
        "blockers": sorted(
            blockers, key=lambda item: (item["path"], item["owner"], item["reason"])
        ),
        "apply_supported": False,
        "writes": False,
        "qualification": False,
        "planning_complete": contained and native and not blockers,
    }
    result["plan_identity"] = canonical_identity(result).uri
    return result
