"""Finite original framework/source observations for retained root placement.

Only an original active context can select exclusions. A saved publication is
joined to actual initialization authority and files; its path list by itself is
never an ignore API. Unknown files and empty directories remain retained inputs.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import threading
import weakref
from bisect import bisect_left
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.retained_layout import (
    LIFT_SHIFT_FILE,
    PENDING_LAYOUT_FILE,
    ResolvedRetainedLayout,
    _authority_stamp,
    _fail,
    read_layout_document,
    resolve_retained_layout,
)
from literate_ai.adapters.retained_project_inputs import (
    RetainedProjectInputError,
    _directory_access,
    _stamp,
    _stream,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.project_initialization import (
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
)
from literate_ai.contracts.retained_layout import (
    RETAINED_LAYOUT_FILE,
    RetainedLayoutSourcePolicy,
)
from literate_ai.projects import LoadedProject, parse_project_configuration

_ISSUED = weakref.WeakKeyDictionary()
_CONTROL_BASELINE = 64 * 1024
_MAX_FRAMEWORK_FILES = 100_000
_FIXED_FRAMEWORK_FILES = frozenset(
    {
        "literate.project.json",
        ".literate/initialization-baseline.json",
        ".literate/initialization-origin.json",
        ".literate/conversion-authority.json",
        ".literate/harness-inventory.json",
        ".literate/legacy-harness-baseline.json",
        ".literate/legacy-wrapper-parity.json",
        LIFT_SHIFT_FILE,
        RETAINED_LAYOUT_FILE,
        PENDING_LAYOUT_FILE,
        "litai.harness.mk",
    }
)


def _signature(node):
    return (*_stamp(node), node.st_uid, node.st_gid, node.st_nlink)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class RetainedLayoutSourceContext:
    """An original finite read-only observation; no mutation authority."""

    layout: ResolvedRetainedLayout
    retained_memory_bytes: int

    def __reduce__(self):
        raise TypeError("retained.layout.source-context-not-transportable")

    def require_framework_current(self, *, reserved_memory_bytes=0):
        record = _require_original(self)
        if (
            type(reserved_memory_bytes) is not int
            or reserved_memory_bytes < 0
            or reserved_memory_bytes + record["retained"] > record["maximum"]
        ):
            _fail("metadata_limit", "layout source observation exceeds metadata memory")
        _current(record)


def _require_original(context):
    if type(context) is not RetainedLayoutSourceContext:
        _fail(
            "original_source_context_required",
            "original layout source context required",
        )
    record = _ISSUED.get(context)
    if (
        record is None
        or not record["active"]
        or record["pid"] != os.getpid()
        or record["thread"] is not threading.current_thread()
    ):
        _fail(
            "original_source_context_required", "layout source context ended or changed"
        )
    if (
        context.layout is not record["layout"]
        or context.retained_memory_bytes != record["retained"]
        or context.layout.project_root != record["root"]
        or context.layout.implementation != record["source_root"]
        or context.layout.wrapper != record["wrapper"]
        or context.layout.identity != record["layout_identity"]
        or context.layout.project_manifest_bytes != record["project_bytes"]
        or context.layout.lift_shift_bytes != record["lift_bytes"]
        or context.layout.lift_shift != record["lift_value"]
        or context.layout.authority_observations != record["resolution_observations"]
    ):
        _fail(
            "original_source_context_required",
            "original layout observation was altered",
        )
    return record


def _lifecycle_roles(root):
    from .lifecycle_lock import project_lifecycle_lock_path

    lock = project_lifecycle_lock_path(root)
    return frozenset(
        {
            lock.relative_to(root).as_posix(),
            lock.with_name(lock.name + ".owner.json").relative_to(root).as_posix(),
            PENDING_LAYOUT_FILE,
        }
    )


def _framework_directory_roles(project):
    from .project_initialization import _INITIALIZATION_DIRECTORIES

    # These are exact canonical initialization/catalog coordinates. They never
    # prune unknown children: projection retains each new file/empty directory.
    roles = set(_INITIALIZATION_DIRECTORIES) | {"verification"}
    for kind in (
        "component",
        "flavor",
        "skill",
        "workflow",
        "routing",
        "documentation",
    ):
        for path in project.roots(kind):
            relative = path.relative_to(project.root).as_posix()
            if relative != ".":
                roles.add(relative)
    return frozenset(roles)


def _canonical_framework_file_roles(layout, reserve):
    from .project_initialization import (
        _STARTER_DOCS,
        _STARTER_TEMPLATE_FILES,
        _TEMPLATE_FILES,
        LEGACY_LIFT_SHIFT_ADR,
    )
    from .repository_lineage import REPOSITORY_LINEAGE_FILE, REPOSITORY_PARENT_FILE

    # Historical baseline data is not an ignore API. Only exact outputs of the
    # actual canonical initializer and retained-harness metadata owner can select
    # root exclusions. Unknown imported/operator files remain source or a root
    # destination collision until their genuine owner is integrated explicitly.
    reserve(
        64
        * (
            len(_TEMPLATE_FILES)
            + len(_STARTER_TEMPLATE_FILES)
            + len(_STARTER_DOCS)
            + 64
        )
        + sum(
            8 * len(name.encode())
            for group in (_TEMPLATE_FILES, _STARTER_TEMPLATE_FILES, _STARTER_DOCS)
            for name in group
        )
    )
    paths = set(_TEMPLATE_FILES) | set(_STARTER_TEMPLATE_FILES) | set(_STARTER_DOCS)
    paths.update(_FIXED_FRAMEWORK_FILES)
    paths.update(
        {
            REPOSITORY_LINEAGE_FILE,
            REPOSITORY_PARENT_FILE,
            LEGACY_LIFT_SHIFT_ADR,
            "docs/decisions/0002-native-literate-ai-rewrite.md",
            "docs/roadmap/native-rewrite-program.md",
            "flavors/legacy-project-shim/flavor.md",
            "flavors/legacy-project-shim/openspec/spec.md",
            "skills/specification-to-source/legacy-project-shim/SKILL.md",
            "workflows/legacy-adoption/workflow.md",
            "routing/legacy-adoption.json",
        }
    )
    component_files = [name for name in paths if name.endswith("/component.md")]
    component_files.append(layout.declaration.wrapper_component + "/component.md")
    for name in component_files:
        parent = PurePosixPath(name).parent.as_posix()
        paths.update(
            {
                parent + "/component.md",
                parent + "/component.lock.json",
                parent + "/component.resolution-audit.host.json",
            }
        )
    return frozenset(paths)


def _framework_paths(project, layout, reserve, *, _observations=None):
    from .component_locks import _OPERATION_LOCK_FILENAME, _WRITE_LOCK_FILENAME
    from .component_resolution_audits import _AUDIT_PREFIX, _AUDIT_SUFFIX
    from .conversion_authority import _CONVERSION_AUTHORITY_LOCK
    from .project_initialization import _INITIALIZATION_EMPTY_CATALOGS
    from .repository_lineage import REPOSITORY_LINEAGE_LOCK_FILE
    from .update_merge import CHECKPOINT

    baseline_value, _ = read_layout_document(
        project.root,
        ".literate/initialization-baseline.json",
        _reserve_metadata=reserve,
        _observations=_observations,
    )
    origin_value, _ = read_layout_document(
        project.root,
        ".literate/initialization-origin.json",
        _reserve_metadata=reserve,
        _observations=_observations,
    )
    baseline = ProjectInitializationBaseline.from_dict(baseline_value)
    origin = ProjectInitializationOrigin.from_dict(origin_value)
    if baseline.origin_identity != origin.identity:
        _fail(
            "origin_changed", "framework partition and initialization origin disagree"
        )
    canonical_roles = _canonical_framework_file_roles(layout, reserve)
    result = (
        {item.path for item in baseline.files if item.path in canonical_roles}
        | set(_FIXED_FRAMEWORK_FILES)
        | set(_lifecycle_roles(project.root))
    )
    result.update(
        {_CONVERSION_AUTHORITY_LOCK, REPOSITORY_LINEAGE_LOCK_FILE, CHECKPOINT}
    )
    result.update(
        layout.declaration.wrapper_component + "/" + name
        for name in (
            "component.md",
            "component.lock.json",
            "component.resolution-audit.host.json",
            _WRITE_LOCK_FILENAME,
            _OPERATION_LOCK_FILENAME,
            f".{_AUDIT_PREFIX}host{_AUDIT_SUFFIX}.write.lock",
        )
    )
    with _directory_access(project.root) as access:
        for directory in _INITIALIZATION_EMPTY_CATALOGS:
            relative = directory + "/.gitkeep"
            path = project.root / relative
            try:
                node = access.metadata(path) if access is not None else path.lstat()
            except FileNotFoundError:
                continue
            # A changed placeholder becomes an input; a path name alone never
            # hides newly authored source bytes or a cross-boundary hardlink.
            if stat.S_ISREG(node.st_mode) and node.st_nlink == 1 and node.st_size == 0:
                result.add(relative)
    if project.definition.test_receipt is not None:
        result.add(project.definition.test_receipt)
    # Supported publication records may retain only canonical framework roles.
    # Newly created ordinary inputs cannot disappear through an edited list.
    if (
        layout.publication is not None
        and not set(layout.publication.framework_owned_files) <= result
    ):
        _fail(
            "partition_disagreement",
            "layout claims files outside current framework authority",
        )
    if len(result) > _MAX_FRAMEWORK_FILES:
        _fail("metadata_limit", "framework ownership partition exceeds its entry bound")
    return tuple(sorted(result))


def _require_project_git(root):
    # Use the same bounded native Git execution port as canonical source and
    # retained Cargo custody. Ambient GIT_* cannot redirect the inspected root.
    from literate_ai.adapters.builders import run_bounded_process

    executable = shutil.which("git")
    if executable is None:
        _fail("git_required", "root placement requires actual project Git metadata")
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        GIT_OPTIONAL_LOCKS="0",
        GIT_TERMINAL_PROMPT="0",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
    )
    result = run_bounded_process(
        (
            executable,
            "-c",
            "core.hooksPath=" + os.devnull,
            "rev-parse",
            "--show-toplevel",
        ),
        cwd=root,
        environment=environment,
        timeout_seconds=10,
        stdout_limit_bytes=65536,
        stderr_limit_bytes=4096,
        error_prefix="retained.layout.git",
    )
    reported = Path(os.fsdecode(result.stdout).rstrip("\r\n"))
    if result.returncode or reported != root:
        _fail("git_root_changed", "retained root must be the actual project Git root")


def _current(record):
    record["original_root_access"].require_current()
    root = record["root"]
    require_safe_directory(root)
    node = root.lstat()
    if (node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid) != record[
        "root_node"
    ]:
        _fail("project_changed", "layout project root changed")
    if os.path.lexists(root / PENDING_LAYOUT_FILE):
        from .retained_layout_journal import _require_pending_owner

        _require_pending_owner(record["pending_owner"], root)
    with _directory_access(root) as access:
        for relative, (expected_bytes, expected_stamp) in record[
            "authority_observations"
        ].items():
            path = root / relative
            try:
                before = access.metadata(path) if access is not None else path.lstat()
                if (
                    _authority_stamp(before) != expected_stamp
                    or not stat.S_ISREG(before.st_mode)
                    or before.st_size != len(expected_bytes)
                ):
                    _fail(
                        "authority_changed",
                        "original layout authority changed after resolution",
                    )
                output = io.BytesIO()
                _stream(root, relative, len(expected_bytes), output, access=access)
                after = access.metadata(path) if access is not None else path.lstat()
                if (
                    output.getvalue() != expected_bytes
                    or _authority_stamp(after) != expected_stamp
                ):
                    _fail(
                        "authority_changed", "original layout authority bytes changed"
                    )
            except (OSError, RetainedProjectInputError) as exc:
                _fail(
                    "authority_changed",
                    "original layout authority is no longer current",
                )
                raise AssertionError from exc
        # The canonical project parser selected the finite framework roles.
        # Rejoin its exact original bytes, not a caller's typed assertion.
        output = io.BytesIO()
        _stream(
            root,
            "literate.project.json",
            len(record["project_bytes"]),
            output,
            access=access,
        )
        if output.getvalue() != record["project_bytes"]:
            _fail(
                "project_changed", "project manifest changed during layout observation"
            )
        for relative, expected in record["files"].items():
            path = root / relative
            try:
                node = access.metadata(path) if access is not None else path.lstat()
            except FileNotFoundError:
                if expected is not None:
                    _fail(
                        "framework_changed", "framework-owned layout input disappeared"
                    )
                continue
            if expected is None or _signature(node) != expected:
                _fail("framework_changed", "framework-owned layout input changed")
        for relative, expected in record["directories"].items():
            path = root / relative
            node = access.metadata(path) if access is not None else path.lstat()
            actual = (node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid)
            if not stat.S_ISDIR(node.st_mode) or actual != expected:
                _fail("framework_changed", "framework-owned layout directory changed")
        if record["git"] is not None:
            node = (root / ".git").lstat()
            if _signature(node) != record["git"]:
                _fail("git_changed", "original project Git administration changed")


@contextmanager
def observe_retained_layout_partition(
    project, *, maximum_metadata_bytes=1024**3, _pending_owner=None
):
    """Keep original root/ancestor descriptors across resolution and issuance."""
    if not isinstance(project, LoadedProject):
        raise TypeError("retained.layout.loaded-project-required")
    if (
        type(maximum_metadata_bytes) is not int
        or not _CONTROL_BASELINE <= maximum_metadata_bytes < 2**63
    ):
        _fail("metadata_limit", "finite layout metadata memory is required")
    root = project.root
    require_safe_directory(root)
    with _directory_access(root) as original_root_access:
        if original_root_access is None:
            _fail(
                "native_owner_unavailable",
                "layout observation requires original root handles",
            )
        with _observe_retained_layout_partition(
            project,
            maximum_metadata_bytes=maximum_metadata_bytes,
            _pending_owner=_pending_owner,
            _root_access=original_root_access,
        ) as context:
            yield context


@contextmanager
def _observe_retained_layout_partition(
    project, *, maximum_metadata_bytes, _pending_owner, _root_access
):
    """Issue finite exclusions from actual current project/framework observations.

    No source payload is copied or hidden by a prior source allowlist. The
    subsequent canonical tree walk must enumerate every remaining member twice.
    """
    if (
        type(maximum_metadata_bytes) is not int
        or not _CONTROL_BASELINE <= maximum_metadata_bytes < 2**63
    ):
        _fail("metadata_limit", "finite layout metadata memory is required")
    controls_memory = _CONTROL_BASELINE

    def reserve(size):
        nonlocal controls_memory
        # Admit JSON text, decode/parse graphs and overlapping contract/partition
        # representations BEFORE the held metadata bytes are read or decoded.
        controls_memory += 16 * size
        if controls_memory > maximum_metadata_bytes:
            _fail("metadata_limit", "layout controls exceed metadata memory")

    layout = resolve_retained_layout(
        project, _reserve_metadata=reserve, _pending_owner=_pending_owner
    )
    root = layout.project_root
    project = LoadedProject(
        root, parse_project_configuration(layout.project_manifest_bytes)
    )
    node = root.lstat()
    root_node = (node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid)
    authority_observations = {
        name: (raw, stamp) for name, raw, stamp in layout.authority_observations
    }
    paths = _framework_paths(
        project, layout, reserve, _observations=authority_observations
    )
    directory_roles = _framework_directory_roles(project)
    owned_directories = (
        layout.publication.framework_owned_directories
        if layout.publication is not None
        else ()
    )
    memory = (
        controls_memory
        + sum(768 + 32 * len(path.encode()) for path in paths)
        + sum(768 + 32 * len(path.encode()) for path in owned_directories)
        + sum(768 + 32 * len(path.encode()) for path in directory_roles)
    )
    if memory > maximum_metadata_bytes:
        _fail("metadata_limit", "framework partition exceeds metadata memory")
    files = {}
    excluded = set()
    with _directory_access(root) as access:
        for relative in paths:
            path = root / relative
            try:
                node = access.metadata(path) if access is not None else path.lstat()
            except FileNotFoundError:
                files[relative] = None
                continue
            if not stat.S_ISREG(node.st_mode) or node.st_nlink != 1:
                _fail(
                    "framework_unsafe",
                    "framework metadata is redirected or multiply linked",
                )
            files[relative] = _signature(node)
            if path.is_relative_to(layout.implementation):
                excluded.add(path.relative_to(layout.implementation).as_posix())
    # Git administration has a separate canonical owner. It is never moved or
    # treated as source. A redirected .git node is not a supported exclusion.
    git = None
    if os.path.lexists(root / ".git"):
        node = (root / ".git").lstat()
        if not stat.S_ISDIR(node.st_mode) and not (
            stat.S_ISREG(node.st_mode) and node.st_nlink == 1
        ):
            _fail("git_unsafe", "project Git administration is redirected")
        git = _signature(node)
        _require_project_git(root)
        if _signature((root / ".git").lstat()) != git:
            _fail(
                "git_changed", "project Git administration changed during observation"
            )
    framework_directories = set()
    directory_nodes = {}
    if layout.publication is not None:
        # An existing retained ancestor/empty directory is not made exclusive
        # merely by adding a framework child below it. Only directories recorded
        # as actually created by the supported framework transaction may prune.
        for name in layout.publication.framework_owned_directories:
            prefix = name + "/"
            selected = bisect_left(paths, prefix)
            if name not in directory_roles and (
                selected == len(paths) or not paths[selected].startswith(prefix)
            ):
                _fail(
                    "partition_disagreement",
                    "directory has no canonical framework-owned descendant",
                )
            path = root / name
            require_safe_directory(path)
            node = path.lstat()
            directory_nodes[name] = (
                node.st_dev,
                node.st_ino,
                node.st_mode,
                node.st_uid,
                node.st_gid,
            )
            if path.is_relative_to(layout.implementation):
                framework_directories.add(
                    path.relative_to(layout.implementation).as_posix()
                )
    context = RetainedLayoutSourceContext(layout, memory)
    record = {
        "active": True,
        "pid": os.getpid(),
        "thread": threading.current_thread(),
        "maximum": maximum_metadata_bytes,
        "root": root,
        "root_node": root_node,
        "original_root_access": _root_access,
        "source_root": layout.implementation,
        "layout": layout,
        "pending_owner": _pending_owner,
        "project_bytes": layout.project_manifest_bytes,
        "authority_observations": authority_observations,
        "resolution_observations": layout.authority_observations,
        "wrapper": layout.wrapper,
        "layout_identity": layout.identity,
        "lift_bytes": layout.lift_shift_bytes,
        "lift_value": json.loads(layout.lift_shift_bytes),
        "project_id": project.definition.project_id,
        "component_roots": tuple(project.roots("component")),
        "retained": memory,
        "files": files,
        "existing_framework_paths": tuple(
            sorted(name for name, value in files.items() if value is not None)
        ),
        "directories": directory_nodes,
        "git": git,
        "excluded_files": frozenset(excluded),
        "framework_directories": frozenset(framework_directories),
        "framework_directory_roles": directory_roles,
        "transient_roles": _lifecycle_roles(root),
    }
    # Close original read-byte/stamp custody BEFORE an owner is issued. Later
    # stat snapshots may never rebase the earlier parsed authority onto new data.
    _current(record)
    _ISSUED[context] = record
    try:
        yield context
        _current(record)
    finally:
        record["active"] = False
        _ISSUED.pop(context, None)


def _retained_layout_capture_selection(context, root, *, reserved_memory_bytes):
    record = _require_original(context)
    if root != record["source_root"]:
        _fail(
            "capture_root_changed",
            "layout source root differs from its actual observation",
        )
    own = record["retained"]
    if type(reserved_memory_bytes) is not int or reserved_memory_bytes < own:
        _fail("metadata_limit", "capture reservation omits live layout metadata")

    def closing(*, reserved_memory_bytes=own):
        if type(reserved_memory_bytes) is not int or reserved_memory_bytes < own:
            _fail("metadata_limit", "capture reservation omits live layout metadata")
        context.require_framework_current(
            reserved_memory_bytes=reserved_memory_bytes - own
        )

    closing(reserved_memory_bytes=reserved_memory_bytes)
    roots = {".git"} if record["git"] is not None and root == record["root"] else set()
    if record["pending_owner"] is not None and root == record["root"]:
        from .retained_layout_journal import _metadata_capture_exclusion

        stage = _metadata_capture_exclusion(record["pending_owner"], root)
        if stage is not None:
            roots.add(stage)
    roots = frozenset(roots)
    return roots, record["excluded_files"], closing


def _retained_layout_source_directories(
    context, directories, files, aliases, *, reserved_memory_bytes
):
    record = _require_original(context)
    projection_memory = 1024 * (len(directories) + len(files) + len(aliases)) + sum(
        32 * len(name.encode()) for name in directories
    )
    if reserved_memory_bytes < record["retained"]:
        _fail(
            "metadata_limit",
            "layout projection omits its original retained reservation",
        )
    context.require_framework_current(
        reserved_memory_bytes=(
            reserved_memory_bytes - record["retained"] + projection_memory
        )
    )
    # Keep all unknown empty directories and ancestors of retained members. Only
    # actual framework-only ancestors may disappear from the retained projection.
    retained = (
        {item.path for item in files}
        | {item.path for item in aliases}
        | {name for name in directories if name not in record["framework_directories"]}
    )
    ancestors = set()
    for name in retained:
        parent = PurePosixPath(name).parent
        while parent.parts:
            ancestors.add(parent.as_posix())
            parent = parent.parent
    return tuple(
        name
        for name in directories
        if name not in record["framework_directories"] or name in ancestors
    )


def _require_retained_alias_partition(context, tree, *, reserved_memory_bytes):
    record = _require_original(context)
    resolution_memory = 2048 * (
        len(tree.directories) + len(tree.files) + len(tree.aliases)
    )
    if reserved_memory_bytes < record["retained"]:
        _fail(
            "metadata_limit",
            "layout resolution omits its original retained reservation",
        )
    context.require_framework_current(
        reserved_memory_bytes=(
            reserved_memory_bytes
            - record["retained"]
            + tree.index.metadata_memory_bound
            + resolution_memory
        )
    )
    # A directory alias exposes its entire physical target. Even when all
    # selected files resolve within the retained projection, a shared target
    # containing framework metadata would expose the excluded partition too.
    names = tuple(item.path for item in tree.aliases if item.kind == "symlink")
    resolved = tree.resolve_all(names)
    excluded = record["excluded_files"]
    directories = set(tree.directories)
    for target in resolved:
        if (target == "." and excluded) or (
            target in directories
            and any(name.startswith(target + "/") for name in excluded)
        ):
            _fail(
                "alias_crosses_partition",
                "retained directory alias crosses framework ownership",
            )


def capture_retained_layout_source(
    context, *, limits, case_sensitive=False, reserved_memory_bytes=0
):
    """Hash the complete retained namespace using the canonical custody walk.

    The original context supplies finite exclusions, never a caller-authored
    ignore list. No CAS, temporary payload or source mutation is performed.
    """
    from .native_sdk_tree_custody import _capture_composed_native_tree

    record = _require_original(context)
    context.require_framework_current(reserved_memory_bytes=reserved_memory_bytes)
    tree = _capture_composed_native_tree(
        record["source_root"],
        store=None,
        limits=limits,
        case_sensitive=case_sensitive,
        max_metadata_memory_bytes=record["maximum"],
        layout_custody=context,
        reserved_memory_bytes=record["retained"] + reserved_memory_bytes,
        budget_capture=True,
        retain_payloads=False,
    )
    context.require_framework_current(
        reserved_memory_bytes=reserved_memory_bytes + tree.index.metadata_memory_bound
    )
    return tree


def _native_mode_memory(tree):
    members = len(tree.directories) + len(tree.files) + len(tree.aliases)
    mode_memory = (
        512 * members
        + sum(32 * len(name.encode()) for name in tree.directories)
        + sum(32 * len(item.path.encode()) for item in tree.files)
        + sum(32 * len(item.path.encode()) for item in tree.aliases)
    )
    return mode_memory


def _native_modes(root, tree):
    result = []
    with _directory_access(root) as access:
        for name in tree.directories:
            path = root / name
            node = access.metadata(path) if access is not None else path.lstat()
            if not stat.S_ISDIR(node.st_mode):
                _fail("source_changed", "retained source directory changed")
            result.append((name, stat.S_IMODE(node.st_mode)))
        for item in tree.files:
            path = root / item.path
            node = access.metadata(path) if access is not None else path.lstat()
            if not stat.S_ISREG(node.st_mode):
                _fail("source_changed", "retained source file changed")
            result.append((item.path, stat.S_IMODE(node.st_mode)))
        for item in tree.aliases:
            path = root / item.path
            node = access.metadata(path) if access is not None else path.lstat()
            correct = (
                stat.S_ISREG(node.st_mode)
                if item.kind == "hardlink"
                else stat.S_ISLNK(node.st_mode)
            )
            if not correct:
                _fail("source_changed", "retained source alias changed")
            result.append((item.path, stat.S_IMODE(node.st_mode)))
    return tuple(sorted(result))


def _layout_modes(context, tree, *, reserved_memory_bytes):
    record = _require_original(context)
    mode_memory = _native_mode_memory(tree)
    context.require_framework_current(
        reserved_memory_bytes=(
            reserved_memory_bytes + tree.index.metadata_memory_bound + mode_memory
        )
    )
    return _native_modes(record["source_root"], tree), mode_memory


def _layout_source_identity(tree_identity, modes):
    return canonical_identity(
        {
            "schema": "literate-ai/retained-layout-source-observation@1",
            "tree_identity": tree_identity.uri,
            "modes": modes,
        }
    )


def observe_retained_layout_tree(project, scope):
    """Observe an opt-in inventory's complete source, never its historical list.

    The ordinary inventory/baseline owner authors this versioned capture policy
    after a supported placement or relocation. A historic paths allowlist cannot
    qualify root placement or hide newly introduced retained inputs.
    """
    policy = RetainedLayoutSourcePolicy.from_dict(scope)
    limits = policy.limits
    with observe_retained_layout_partition(
        project, maximum_metadata_bytes=scope["maximum_metadata_bytes"]
    ) as context:
        tree = capture_retained_layout_source(
            context, limits=limits, case_sensitive=scope["case_sensitive"]
        )
        modes, mode_memory = _layout_modes(context, tree, reserved_memory_bytes=0)
        closing = capture_retained_layout_source(
            context,
            limits=limits,
            case_sensitive=scope["case_sensitive"],
            reserved_memory_bytes=tree.index.metadata_memory_bound + mode_memory,
        )
        closing_modes, _ = _layout_modes(
            context,
            closing,
            reserved_memory_bytes=tree.index.metadata_memory_bound + mode_memory,
        )
        if closing.identity != tree.identity or closing_modes != modes:
            _fail("source_changed", "retained source bytes, modes or topology changed")
        identity = _layout_source_identity(tree.identity, modes)
        result = {
            "identity": identity.uri,
            "file_count": len(tree.files) + len(tree.aliases),
            "missing_count": 0,
            "total_bytes": sum(item.blob.size for item in tree.files)
            + sum(
                len(item.target.encode("utf-8"))
                for item in tree.aliases
                if item.kind == "symlink"
            ),
            "scope": "complete-retained-layout@1",
        }
        # Release retained graph metadata before the outer context closes.
        del tree, closing, modes, closing_modes
    return result
