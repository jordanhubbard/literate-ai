"""Actual registered Git control inputs and targets, not source exclusions.

No repository is established from bounded physical discovery absence, not a Git
error. Repository candidates must resolve through Git. This binds critical files
and writer roles without executing filters, fetching or rewriting the index.
"""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

from ._write_reservations import WriteReservationTarget
from .repository_orchestration import _git, _oid, _require_nonwriting_index, _worktree
from .repository_refresh import (
    RefreshFileObservation,
    RefreshReferenceObservation,
    _absent,
    _configuration_file,
    _configuration_files,
    _configuration_snapshot,
    _file,
    _git_path,
    _node,
)
from .repository_refresh_refs import _reference_file
from .repository_refresh_reservations import _custody_wire
from .retained_layout_partition import _lineage


def _fail(message):
    raise ValueError("layout.git-controls: " + message)


def _presence(path):
    try:
        node = path.lstat()
    except FileNotFoundError:
        return None
    basic = node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid
    if stat.S_ISDIR(node.st_mode):
        return basic
    return (*basic, node.st_size, node.st_mtime_ns, node.st_ctime_ns, node.st_nlink)


def _discovery(root):
    lineage = _lineage(root)
    if len(lineage) > 256:
        _fail("physical ancestry exceeds its bound")
    device = lineage[-1][1]
    facts, candidate = [], False
    # Git's default discovery stops at a filesystem boundary. Ambient Git
    # selectors/ceilings/cross-filesystem overrides are stripped by _git.
    for record in reversed(lineage):
        if record[1] != device:
            break
        directory = Path(record[0])
        entries = tuple(
            (directory / name, _presence(directory / name))
            for name in (".git", "HEAD", "objects")
        )
        facts.extend(entries)
        candidate |= entries[0][1] is not None
        candidate |= entries[1][1] is not None and entries[2][1] is not None
    if _lineage(root) != lineage:
        _fail("discovery ancestry changed")
    return lineage, tuple(facts), candidate


def _head(root, git_directory, common_directory, head, packed, reservations):
    if not head.content or len(head.content) > 4096:
        _fail("HEAD is empty or excessive")
    if head.path.lstat().st_nlink != 1:
        _fail("HEAD is hardlinked")
    chain, content = [], head.content
    while content is not None and content.startswith(b"ref: "):
        name = content[5:].removesuffix(b"\n").decode("utf-8")
        relative = canonical_relative_posix_path(name, label="layout Git reference")
        if (
            not name.startswith("refs/")
            or len(name.encode("utf-8")) > 4090
            or len(chain) >= 16
            or name in {ref.name for ref in chain}
        ):
            _fail("reference chain is ambiguous or excessive")
        _git(root, "check-ref-format", name)
        path = _git_path(root, "--git-path", name)
        anchors = [
            anchor
            for anchor in (git_directory, common_directory)
            if path == anchor / relative
        ]
        if not anchors:
            _fail("reference storage is redirected")
        observed = _reference_file(anchors[0], relative, reservations)
        chain.append(RefreshReferenceObservation(name, observed))
        content = observed.content
    reference = chain[-1].name if chain else None
    if reference is not None:
        actual = _git(root, "symbolic-ref", "HEAD").decode().removesuffix("\n")
        if actual != reference:
            _fail("symbolic reference resolution changed")
    if content is None:
        matches = [
            line.partition(b" ")[0]
            for line in (packed.content or b"").splitlines()
            if line.partition(b" ")[1:] == (b" ", reference.encode())
        ]
        if len(matches) > 1:
            _fail("packed HEAD reference is ambiguous")
        commit = _oid(matches[0]) if matches else None
    else:
        commit = _oid(content.removesuffix(b"\n"))
    if commit is None:
        if reference is None or _git(
            root,
            "for-each-ref",
            "--count=2",
            "--format=%(objectname) %(refname)",
            "--",
            reference,
        ):
            _fail("unborn reference is not absent in Git")
    elif _oid(_git(root, "rev-parse", "--verify", "HEAD^{commit}").strip()) != commit:
        _fail("HEAD bytes differ from the actual commit")
    return commit, tuple(chain)


def _configuration_inputs(root, git_directory, common_directory, identity, includes):
    if not includes:
        files = _configuration_files(git_directory, common_directory, False)
        if files is None:
            _fail("Git configuration files are unavailable or redirected")
        return files, ()
    raw = _git(root, "config", "--null", "--show-origin", "--list", "--includes")
    fields = raw.split(b"\0")
    if fields[-1] != b"" or len(fields) % 2 != 1:
        _fail("Git configuration origin records are incomplete")
    entries = fields[:-1]
    content = b"\0".join(entries[1::2]) + (b"\0" if entries else b"")
    if "sha256:" + hashlib.sha256(content).hexdigest() != identity:
        _fail("Git configuration changed during origin discovery")
    traversed = {}

    def configuration_path(base, value):
        raw = base / value.decode("utf-8")
        if len(raw.parts) > 256:
            _fail("Git configuration path exceeds its ancestry bound")
        current = Path(raw.anchor)
        for part in raw.parts[1:]:
            if part == "..":
                # Validate and retain a canceled prefix before normalizing it.
                # Otherwise link/../file could select a different native target
                # while silently minting a role for the lexical spelling.
                ancestry = _lineage(current)
                if current in traversed and traversed[current] != ancestry:
                    _fail("Git configuration traversal changed")
                traversed[current] = ancestry
                current = current.parent
            else:
                current /= part
        return current

    paths = {common_directory / "config", git_directory / "config.worktree"}
    for origin, value in zip(entries[0::2], entries[1::2], strict=True):
        if origin == b"command line:" and value == b"core.fsmonitor\nfalse":
            continue
        if not origin.startswith(b"file:"):
            _fail("Git configuration has an unsupported origin")
        path = configuration_path(root, origin[5:])
        paths.add(path)
        if len(paths) > 64:
            _fail("Git configuration file count exceeds its bound")
    # Origins omit empty or missing include files. Ask Git to expand declared
    # path values (including ~/ and its native prefix rules), then resolve any
    # relative value against the actual declaring file, never the worktree.
    # Conditional targets are conservatively reserved even when inactive. This
    # grants only writer exclusion; neither the file nor its parent is source
    # ownership or an exclusion. A missing/redirected parent refuses below.
    declared = _git(
        root,
        "config",
        "--null",
        "--show-origin",
        "--path",
        "--includes",
        "--get-regexp",
        r"^include(if)?\.",
    ).split(b"\0")
    if declared[-1] != b"" or len(declared) % 2 != 1:
        _fail("Git include target records are incomplete")
    for origin, entry in zip(declared[0:-1:2], declared[1:-1:2], strict=True):
        key, separator, value = entry.partition(b"\n")
        if not (
            key == b"include.path"
            or (key.startswith(b"includeif.") and key.endswith(b".path"))
        ):
            continue
        if not separator or not value or not origin.startswith(b"file:"):
            _fail("Git include target has an unsupported origin or path")
        declaring = configuration_path(root, origin[5:])
        if declaring not in paths:
            _fail("Git include declaring origin changed")
        target = configuration_path(declaring.parent, value)
        paths.add(target)
        if len(paths) > 64:
            _fail("Git configuration file count exceeds its bound")
    for parent in sorted({path.parent for path in paths}, key=str):
        ancestry = _lineage(parent)
        if parent in traversed and traversed[parent] != ancestry:
            _fail("Git configuration parent ancestry changed")
        traversed[parent] = ancestry
    parents = tuple(sorted(traversed.items(), key=lambda item: str(item[0])))
    files = tuple(_configuration_file(path) for path in sorted(paths, key=str))
    if (
        sum(file.signature[3] for file in files if file.signature is not None)
        > 8 * 1024**2
    ):
        _fail("Git configuration bytes exceed their bound")
    if tuple((path, _lineage(path)) for path, _ in parents) != parents:
        _fail("Git configuration parent ancestry changed")
    return files, parents


@dataclass(frozen=True, slots=True)
class _GitFiles:
    git_directory: Path
    common_directory: Path
    boundary: object
    head: RefreshFileObservation
    index: RefreshFileObservation
    commit: str | None
    references: tuple[RefreshReferenceObservation, ...]
    packed_references: RefreshFileObservation
    common_locator: RefreshFileObservation
    configuration_identity: str
    configuration_files: tuple | None
    worktree_lock: RefreshFileObservation | None
    lineages: tuple
    native_files: tuple


@dataclass(frozen=True, slots=True)
class LayoutGitControls:
    project_root: Path
    git_root: Path | None
    discovery_lineage: tuple
    discovery: tuple
    files: _GitFiles | None

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/layout-git-controls@1",
                "observation": _custody_wire(self),
            }
        )

    @property
    def protected_admin_entries(self):
        if self.files is None:
            return ()
        return tuple(
            dict.fromkeys(
                (
                    self.git_root / ".git",
                    self.files.git_directory,
                    self.files.common_directory,
                )
            )
        )

    def targets(self):
        if self.files is None:
            return ()
        files = self.files
        captured = {path: lineage[-1][1:4] for path, lineage in files.lineages}
        anchors = (
            (files.git_directory, captured[files.git_directory]),
            (files.common_directory, captured[files.common_directory]),
        )

        def target(path):
            selected = next(
                (item for item in anchors if path.is_relative_to(item[0])), None
            )
            if selected is None:
                _fail("writer path is outside actual Git administration")
            return WriteReservationTarget(path, *selected)

        paths = [
            files.git_directory / "HEAD.lock",
            files.index.path.with_name(files.index.path.name + ".lock"),
            files.common_directory / "packed-refs.lock",
            files.common_directory / "config.lock",
            files.git_directory / "config.worktree.lock",
        ]
        paths.extend(
            ref.file.path.with_name(ref.file.path.name + ".lock")
            for ref in files.references
        )
        for config in files.configuration_files or ():
            path = config.path.with_name(config.path.name + ".lock")
            if path not in paths:
                paths.append(path)
        if files.worktree_lock is not None and files.worktree_lock.content is None:
            paths.append(files.worktree_lock.path)
        result = []
        for path in dict.fromkeys(paths):
            if path.parent in captured:
                result.append(
                    WriteReservationTarget(path, path.parent, captured[path.parent])
                )
            else:
                result.append(target(path))
        return tuple(result)

    def require_unchanged(self, reservations=None):
        if (
            observe_layout_git_controls(self.project_root, reservations=reservations)
            != self
        ):
            _fail("actual Git control inputs changed")

    def close_native_inputs(self, reservations=None):
        """Close captured facts after other role reads; this grants no exclusions."""
        if _discovery(self.project_root) != (
            self.discovery_lineage,
            self.discovery,
            self.files is not None,
        ):
            _fail("physical Git discovery changed")
        if self.files is None:
            return
        files = self.files
        owned_lock = (
            files.worktree_lock is not None
            and files.worktree_lock.signature is None
            and reservations is not None
            and reservations.owns(files.worktree_lock.path)
        )
        for path, expected in files.native_files:
            observed = (
                None
                if owned_lock and path == files.worktree_lock.path
                else _presence(path)
            )
            if observed != expected:
                _fail("critical Git native file facts changed")
        if (
            tuple((path, _lineage(path)) for path, _ in files.lineages)
            != files.lineages
        ):
            _fail("Git administrative ancestry changed")


def observe_layout_git_controls(project_root, *, reservations=None):
    """Bind actual critical Git state for a project without qualifying its source."""
    root = Path(project_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("project root must be direct and absolute")
    lineage, discovery, candidate = _discovery(root)
    if not candidate:
        if _discovery(root) != (lineage, discovery, candidate):
            _fail("repository appeared during discovery")
        return LayoutGitControls(root, None, lineage, discovery, None)
    actual = (
        _git(root, "rev-parse", "--show-toplevel").decode("utf-8").removesuffix("\n")
    )
    if not actual or "\n" in actual or "\r" in actual:
        _fail("Git root is absent or ambiguous")
    git_root = Path(actual)
    if not git_root.is_absolute() or not root.is_relative_to(git_root):
        _fail("registered Git worktree does not contain this project")
    _worktree(git_root)
    boundary_path = git_root / ".git"
    boundary = (
        _node(boundary_path)
        if boundary_path.is_dir()
        else _file(boundary_path, maximum_bytes=4096)
    )
    git_directory = _git_path(git_root, "--git-dir")
    common_directory = _git_path(git_root, "--git-common-dir")
    directories = tuple(dict.fromkeys((git_root, git_directory, common_directory)))
    lineages = tuple((path, _lineage(path)) for path in directories)
    _require_nonwriting_index(git_root)
    for name in (
        "HEAD.lock",
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-merge",
        "rebase-apply",
        "sequencer",
        "BISECT_LOG",
    ):
        _absent(git_directory / name, reservations)
    index_path = _git_path(git_root, "--git-path", "index")
    for path in (
        index_path.with_name(index_path.name + ".lock"),
        common_directory / "packed-refs.lock",
        common_directory / "config.lock",
        git_directory / "config.worktree.lock",
    ):
        _absent(path, reservations)
    head = _file(git_directory / "HEAD", maximum_bytes=4096)
    index = _file(index_path, optional=True)
    packed = _file(
        common_directory / "packed-refs", optional=True, maximum_bytes=1024**2
    )
    configuration, includes = _configuration_snapshot(git_root, clean=False)
    commit, references = _head(
        git_root, git_directory, common_directory, head, packed, reservations
    )
    worktree_lock = None
    if git_directory != common_directory:
        lock_path = git_directory / "locked"
        if reservations is not None and reservations.owns(lock_path):
            worktree_lock = RefreshFileObservation(lock_path, None, None)
        else:
            worktree_lock = _file(lock_path, optional=True, maximum_bytes=4096)
            if (worktree_lock.content or b"").startswith(
                b"literate-ai-refresh-reservation\n"
            ):
                _fail("retained worktree control requires explicit recovery")
    locator = _file(git_directory / "commondir", optional=True, maximum_bytes=4096)
    configuration_files, config_lineages = _configuration_inputs(
        git_root, git_directory, common_directory, configuration, includes
    )
    original = dict(lineages)
    for path, ancestry in config_lineages:
        if path in original and original[path] != ancestry:
            _fail("Git configuration administration changed")
        original[path] = ancestry
    lineages = tuple(original.items())
    inputs = [
        head,
        index,
        packed,
        locator,
        *(ref.file for ref in references),
        *(configuration_files or ()),
    ]
    if isinstance(boundary, RefreshFileObservation):
        inputs.append(boundary)
    if worktree_lock is not None:
        inputs.append(worktree_lock)
    native_files = []
    for observed in inputs:
        owned_lock = (
            worktree_lock is not None
            and observed.path == worktree_lock.path
            and observed.signature is None
            and reservations is not None
            and reservations.owns(observed.path)
        )
        presence = None if owned_lock else _presence(observed.path)
        signature = (
            None
            if presence is None
            else (presence[0], presence[1], presence[2], *presence[5:8])
            if len(presence) == 9
            else False
        )
        if signature != observed.signature:
            _fail("critical Git input changed during role observation")
        native_files.append((observed.path, presence))
    if _configuration_snapshot(git_root, clean=False)[0] != configuration:
        _fail("Git configuration changed during role observation")
    files = _GitFiles(
        git_directory,
        common_directory,
        boundary,
        head,
        index,
        commit,
        references,
        packed,
        locator,
        configuration,
        configuration_files,
        worktree_lock,
        lineages,
        tuple(native_files),
    )
    if (
        _discovery(root) != (lineage, discovery, candidate)
        or tuple((path, _lineage(path)) for path, _ in lineages) != lineages
        or (
            _node(boundary_path)
            if boundary_path.is_dir()
            else _file(boundary_path, maximum_bytes=4096)
        )
        != boundary
    ):
        _fail("Git registration or physical ancestry changed")
    result = LayoutGitControls(root, git_root, lineage, discovery, files)
    result.close_native_inputs(reservations)
    return result
