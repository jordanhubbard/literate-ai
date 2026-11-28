"""Filesystem adapter for explicit Literate AI project roots and catalogs."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from pathlib import Path

from literate_ai._atomic_publication import (
    publish_atomic_file_if_scoped,
    scoped_writer_permits_project_read,
)
from literate_ai._cache_lock import (
    _is_windows,
    _lock_cleanup_allowed,
    _windows_identity_matches,
)
from literate_ai._filesystem import (
    UnsafeFilesystemPathError,
    _readonly_directory_batch,
    capture_directory_ancestries,
    path_is_link_or_reparse,
    require_safe_directory,
    stat_is_link_or_reparse,
)
from literate_ai.adapters.initialized_records import (
    ProjectUpdateError as _InitializedRecordError,
)
from literate_ai.adapters.initialized_records import _initialization_record_ports
from literate_ai.application.agent_skill_catalog import (
    AgentSkillCatalog,
    AgentSkillCatalogError,
    read_only_agent_skill_metadata_parses,
)
from literate_ai.contracts import (
    CANONICAL_PROJECT_PROFILE,
    ContentIdentity,
    ProjectDefinition,
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
    SourceCacheRootKind,
    canonical_identity,
)
from literate_ai.documentation import is_python_bytecode_cache_path

# Windows ``msvcrt.locking`` has no blocking-with-clean-error mode: ``LK_LOCK``
# retries internally for ~10s and then raises a bare ``OSError`` that surfaces as
# ``manifest lock failed`` even under ordinary contention. We instead poll
# ``LK_NBLCK`` -- which fails fast with EACCES/EDEADLOCK when another holder owns
# the byte -- on a bounded retry loop so transient contention is retried while a
# genuine failure still raises promptly. POSIX keeps its blocking ``flock`` path.
_LOCK_TIMEOUT_SECONDS = 30.0
_LOCK_RETRY_SECONDS = 0.01

PROJECT_FILENAME = "literate.project.json"
DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES = 1024 * 1024
DEFAULT_MAXIMUM_PINNED_INPUT_FILES = 1024
DEFAULT_MAXIMUM_PINNED_INPUT_BYTES = 2 * 1024 * 1024
DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES = 64 * 1024 * 1024
DEFAULT_MAXIMUM_DOCUMENTATION_FILES = 1_024
DEFAULT_MAXIMUM_DOCUMENTATION_ENTRIES = 4_096
# Rich literate assets such as editable slide decks must fit without turning the
# documentation graph into an unbounded binary store. Sixteen MiB admits normal
# presentation/PDF artifacts while the independent 64 MiB catalog ceiling remains.
DEFAULT_MAXIMUM_DOCUMENTATION_FILE_BYTES = 16 * 1024 * 1024
DEFAULT_MAXIMUM_DOCUMENTATION_TOTAL_BYTES = 64 * 1024 * 1024
DEFAULT_MAXIMUM_DOCUMENTATION_PATH_BYTES = 1_024
DEFAULT_MAXIMUM_DOCUMENTATION_DEPTH = 32
CANONICAL_AGENT_SHIMS = {
    "AGENTS.md": "SKILL.md",
    "CLAUDE.md": "SKILL.md",
    ".cursor/rules/literate-ai.mdc": "SKILL.md",
    "agents/openai.yaml": "$literate-ai",
}


class ProjectError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_PROJECT_PARSE_MAX_ENTRIES = 16
_PROJECT_PARSE_MAX_BYTES = 2 * 1024 * 1024
_PROJECT_PARSE_MAX_NODES = 4096


def _project_parse_size(content: bytes, definition: ProjectDefinition) -> int | None:
    """Bound encoded and decoded template storage; unknown shapes bypass reuse."""
    pending: list[object] = [content, definition]
    seen: set[int] = set()
    total = 0
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        total += sys.getsizeof(item)
        if total > _PROJECT_PARSE_MAX_BYTES or len(seen) > _PROJECT_PARSE_MAX_NODES:
            return None
        if is_dataclass(item) and not isinstance(item, type):
            pending.extend(getattr(item, field.name) for field in fields(item))
        elif isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, (tuple, list, set, frozenset)):
            pending.extend(item)
        elif isinstance(item, Enum):
            pending.append(item.value)
        elif item is not None and not isinstance(item, (str, bytes, int, float, bool)):
            return None
        if len(pending) + len(seen) > _PROJECT_PARSE_MAX_NODES:
            return None
    return total


class _ProjectConfigurationParses:
    def __init__(self) -> None:
        self.templates: dict[bytes, ProjectDefinition] = {}
        self.retained_bytes = 4096  # Bounded map, lock and accounting overhead.
        self.lock = threading.Lock()

    def parse(self, content: bytes) -> ProjectDefinition:
        with self.lock:
            return self._parse(content)

    def _parse(self, content: bytes) -> ProjectDefinition:
        if content in self.templates:
            return deepcopy(self.templates[content])
        definition = parse_project_configuration(content)
        if len(self.templates) < _PROJECT_PARSE_MAX_ENTRIES:
            size = _project_parse_size(content, definition)
            if (
                size is not None
                and self.retained_bytes + size <= _PROJECT_PARSE_MAX_BYTES
            ):
                self.templates[content] = definition
                self.retained_bytes += size
                # Neither the first nor a later caller receives the private template.
                return deepcopy(definition)
        return definition


_PROJECT_CONFIGURATION_PARSES: ContextVar[_ProjectConfigurationParses | None] = (
    ContextVar("read_only_project_configuration_parses", default=None)
)


@contextmanager
def read_only_project_configuration_parses(*, isolated: bool = False) -> Iterator[None]:
    """Share parsing templates, never file reads or currentness decisions.

    An isolated frame restores any ambient frame on exit and retains no new
    templates in that ambient frame.
    """
    with read_only_agent_skill_metadata_parses(isolated=isolated):
        if not isolated and _PROJECT_CONFIGURATION_PARSES.get() is not None:
            yield
            return
        token = _PROJECT_CONFIGURATION_PARSES.set(_ProjectConfigurationParses())
        try:
            yield
        finally:
            _PROJECT_CONFIGURATION_PARSES.reset(token)


def parse_project_configuration(content: bytes) -> ProjectDefinition:
    try:
        return ProjectDefinition.from_dict(json.loads(content.decode("utf-8")))
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ProjectError(
            "project.manifest_invalid", "project manifest is invalid"
        ) from exc


_MANIFEST_DECLARATION_METADATA: ContextVar[Callable[[bytes], str | None] | None] = (
    ContextVar("read_only_manifest_declaration_metadata", default=None)
)


@contextmanager
def read_only_project_manifest_metadata() -> Iterator[None]:
    """Reuse only a full parser's immutable declaration field after fresh reads.

    This private closure has the same module/closure-introspection boundary as
    Skill DATA. No context, native observation or placement decision is cached.
    """
    parser = parse_project_configuration
    entry_limit, byte_limit = _PROJECT_PARSE_MAX_ENTRIES, _PROJECT_PARSE_MAX_BYTES
    entries: dict[bytes, str | None] = {}
    retained_bytes = hits = parses = 0
    active = True
    lock = threading.RLock()

    def load(content):
        nonlocal retained_bytes, hits, parses
        with lock:
            retired = not active
            if not retired and type(content) is bytes and content in entries:
                hits += 1
                return entries[content]
            parses += 1
        if retired:
            return parse_project_configuration(content).framework_directory
        # Full schema validation still runs on every miss. Never replace it with
        # a permissive JSON-field lookup, nor retain exceptions or parsed objects.
        directory = parser(content).framework_directory
        if type(content) is not bytes or not (
            directory is None or type(directory) is str and directory == "litai"
        ):
            return directory
        size = len(content) + (0 if directory is None else 4 * len(directory)) + 64
        with lock:
            if (
                active
                and content not in entries
                and len(entries) < entry_limit
                and retained_bytes + size <= byte_limit
            ):
                entries[content] = directory
                retained_bytes += size
        return directory

    def statistics():
        with lock:
            return {
                "active": active,
                "entries": len(entries),
                "payload_bytes": retained_bytes,
                "hits": hits,
                "parses": parses,
            }

    load.statistics = statistics
    owner = _MANIFEST_DECLARATION_METADATA
    token = owner.set(load)
    try:
        yield
    finally:
        active = False
        try:
            with lock:
                entries.clear()
                retained_bytes = 0
        finally:
            owner.reset(token)


def serialize_project_configuration(definition: ProjectDefinition) -> bytes:
    if not isinstance(definition, ProjectDefinition):
        raise TypeError("project configuration must be a ProjectDefinition")
    return (
        json.dumps(definition.to_dict(), indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ProjectContext:
    """Application coordinates and the selected framework authority location.

    Declared paths always remain relative to ``root``. ``framework_root`` owns
    implicit framework metadata; it never rebases native source or commands.
    """

    root: Path
    framework_root: Path
    directory_binding: tuple[tuple[int, ...], tuple[int, ...]] | None = None

    @classmethod
    def observe(cls, root: Path, framework: Path) -> ProjectContext:
        def node(path: Path) -> tuple[int, ...]:
            value = path.stat()
            return value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid

        try:
            binding = (node(root), node(framework))
        except FileNotFoundError:
            binding = None
        return cls(root, framework, binding)

    @property
    def manifest_path(self) -> Path:
        return self.framework_root / PROJECT_FILENAME

    def framework_path(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise ValueError("framework path must be a nonescaping relative path")
        return self.framework_root / path


@dataclass(frozen=True, slots=True)
class ProjectConfigurationSnapshot:
    root: Path
    definition: ProjectDefinition
    content: bytes
    manifest_path: Path
    directory_binding: tuple[tuple[int, ...], tuple[int, ...]] | None

    @property
    def content_identity(self) -> ContentIdentity:
        return ContentIdentity.parse_uri(
            f"sha256:{hashlib.sha256(self.content).hexdigest()}"
        )


_LAYOUT_ACQUIRED_LEASE_KEY = object()


class ProjectConfigurationStore:
    """Atomic project manifest storage using exact-byte compare-and-swap."""

    def __init__(
        self,
        root: Path,
        *,
        maximum_bytes: int = DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES,
    ) -> None:
        if type(maximum_bytes) is not int or maximum_bytes < 1:
            raise ValueError("project configuration byte limit must be positive")
        self.root = Path(root)
        self.maximum_bytes = maximum_bytes

    @property
    def path(self) -> Path:
        return self.manifest_path(self.root)

    @staticmethod
    def manifest_path(root: Path) -> Path:
        return ProjectConfigurationStore.context(root).manifest_path

    @staticmethod
    def context(root: Path) -> ProjectContext:
        """Select direct authority without probing redirected target ancestry."""
        from literate_ai._filesystem import stat_is_link_or_reparse

        root = Path(root)

        def entry(path):
            try:
                return path.lstat()
            except FileNotFoundError:
                return None

        def unsafe():
            raise ProjectError(
                "project.framework_directory_unsafe",
                "framework directory must be direct and unredirected",
            )

        def direct_directory(path, *, missing=False):
            try:
                require_safe_directory(path.absolute(), allow_missing=missing)
            except (UnsafeFilesystemPathError, OSError) as error:
                raise ProjectError(
                    "project.framework_directory_unsafe",
                    "framework directory must be direct and unredirected",
                ) from error
            node = entry(path)
            if node is not None and (
                stat_is_link_or_reparse(node) or not stat.S_ISDIR(node.st_mode)
            ):
                unsafe()
            return node

        def observed(application, framework):
            values = []
            for path in (application, framework):
                node = direct_directory(path, missing=True)
                if node is None:
                    return ProjectContext(application, framework)
                values.append(
                    (node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid)
                )
            return ProjectContext(application, framework, tuple(values))

        def pending(directory, *, owned):
            parent = directory
            for name in (".literate", "retained-harness-readmission"):
                parent = parent / name
                node = entry(parent)
                if node is None:
                    return
                if stat_is_link_or_reparse(node) or not stat.S_ISDIR(node.st_mode):
                    if owned:
                        unsafe()
                    return  # unrelated unmanaged metadata: no target descent
                direct_directory(parent)
            if entry(
                parent / "active.json"
            ) is not None and not scoped_writer_permits_project_read(directory):
                raise ProjectError(
                    "project.retained_readmission_recovery_required",
                    "retained readmission metadata publication requires recovery",
                )

        def declared(path):
            node = entry(path)
            if node is None:
                return False
            if stat_is_link_or_reparse(node) or not stat.S_ISREG(node.st_mode):
                raise ProjectError(
                    "project.manifest_unavailable",
                    f"project root must contain {PROJECT_FILENAME}",
                )
            content = ProjectConfigurationStore(path.parent)._read_manifest(path)
            metadata = _MANIFEST_DECLARATION_METADATA.get()
            directory = (
                parse_project_configuration(content).framework_directory
                if metadata is None
                else metadata(content)
            )
            return directory == "litai"

        if direct_directory(root, missing=True) is None:
            return observed(root, root)
        direct = root / PROJECT_FILENAME
        direct_node = entry(direct)
        if root.name == "litai" and direct_node is not None:
            pending(root, owned=True)  # this coordinate owns either profile's metadata
            if declared(direct):
                direct_directory(root.parent)
                if entry(root.parent / PROJECT_FILENAME) is not None:
                    raise ProjectError(
                        "project.manifest_ambiguous",
                        "root and contained project authority cannot coexist",
                    )
                return observed(root.parent, root)
        child = root / "litai"
        child_node = entry(child)
        if child_node is not None:
            if stat_is_link_or_reparse(child_node):
                unsafe()  # never ask exists/stat about a child target
            if stat.S_ISDIR(child_node.st_mode):
                direct_directory(child)
                contained = child / PROJECT_FILENAME
                if direct_node is None and entry(contained) is not None:
                    # An interrupted contained publication can leave invalid
                    # manifest bytes. Report its pending owner before parsing.
                    pending(child, owned=True)
                if entry(contained) is not None and declared(contained):
                    if direct_node is not None:
                        raise ProjectError(
                            "project.manifest_ambiguous",
                            "root and contained project authority cannot coexist",
                        )
                    pending(child, owned=True)
                    # Root .literate is application-owned in this profile.
                    return observed(root, child)
        pending(root, owned=direct_node is not None)
        if direct_node is not None and stat_is_link_or_reparse(direct_node):
            raise ProjectError(
                "project.manifest_unavailable",
                f"project root must contain {PROJECT_FILENAME}",
            )
        return observed(root, root)

    @classmethod
    def lock_path(cls, root: Path) -> Path:
        """Use the same manifest coordinate for writers and reservations."""
        manifest = cls.manifest_path(root)
        return manifest.with_name(f".{manifest.name}.write.lock")

    def _root(self, *, create: bool = False) -> Path:
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        # Inspect a declared contained coordinate before resolve can erase a
        # redirected framework directory or application ancestor.
        self.context(self.root.absolute())
        try:
            root = self.root.resolve(strict=True)
        except OSError as exc:
            raise ProjectError(
                "project.root_unavailable", "project root is unavailable"
            ) from exc
        if self.root.is_symlink() or not root.is_dir():
            raise ProjectError("project.root_unavailable", "project root is unsafe")
        return root

    def read(self) -> ProjectConfigurationSnapshot:
        context = self.context(self._root())
        root, path = context.root, context.manifest_path
        content = self._read_manifest(path)
        parses = _PROJECT_CONFIGURATION_PARSES.get()
        definition = (
            parse_project_configuration(content)
            if parses is None
            else parses.parse(content)
        )
        self._require_layout(context, definition)
        if self.context(root) != context:
            raise ProjectError(
                "project.manifest_stale",
                "project manifest location changed while it was read",
            )
        return ProjectConfigurationSnapshot(
            root, definition, content, path, context.directory_binding
        )

    @staticmethod
    def _require_layout(context: ProjectContext, definition: ProjectDefinition) -> None:
        expected = (
            context.root / definition.framework_directory
            if definition.framework_directory is not None
            else context.root
        )
        if expected != context.framework_root:
            raise ProjectError(
                "project.manifest_location",
                "project manifest location differs from its declared "
                "framework directory",
            )

    @classmethod
    def discover(cls, start: Path) -> ProjectConfigurationSnapshot | None:
        selected = Path(start).absolute()
        candidate = selected.parent if selected.is_file() else selected
        for root in (candidate, *candidate.parents):
            context = cls.context(root)
            path = context.manifest_path
            if path.exists() or path.is_symlink():
                if context.framework_root != context.root:
                    try:
                        require_safe_directory(candidate, allow_missing=True)
                    except (UnsafeFilesystemPathError, OSError) as exc:
                        raise ProjectError(
                            "project.framework_directory_unsafe",
                            "contained discovery must not cross redirected paths",
                        ) from exc
                if path_is_link_or_reparse(path) or not path.is_file():
                    raise ProjectError(
                        "project.manifest_unavailable",
                        "selected project manifest is not a direct regular file",
                    )
                return cls(root).read()
        return None

    @staticmethod
    def layout_metadata_directory(root: Path) -> Path | None:
        """Return this worktree's direct Git administration directory, if present.

        Git's per-worktree coordinate is independent of configurable user-state
        roots and filesystem case aliases. A new non-Git scaffold has no such
        directory yet; its creator uses a transient root reservation instead.
        """
        root = Path(root).absolute()
        marker = root / ".git"
        if not marker.exists() and not marker.is_symlink():
            return None
        if path_is_link_or_reparse(marker):
            raise ProjectError("project.layout_lock_unsafe", "Git entry is redirected")
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--absolute-git-dir"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode or not result.stdout.strip():
                raise ValueError("Git administration directory is unavailable")
            directory = Path(result.stdout.strip())
            require_safe_directory(directory)
            return directory
        except (
            OSError,
            ValueError,
            subprocess.TimeoutExpired,
            UnsafeFilesystemPathError,
        ) as exc:
            raise ProjectError(
                "project.layout_lock_unsafe", "Git layout coordination is unavailable"
            ) from exc

    @classmethod
    @contextmanager
    def layout_lock(cls, root: Path) -> Iterator[None]:
        """Serialize authority publication across layouts at one physical path.

        Native adoption requires Git, so its transient reservation lives in the
        worktree administration directory. Non-Git creation uses a separate
        transient root reservation. Both reuse the manifest lock's bounded
        identity-checked protocol and idle-file cleanup.
        """
        try:
            require_safe_directory(Path(root).absolute())
        except (UnsafeFilesystemPathError, OSError) as error:
            raise ProjectError(
                "project.layout_lock_unsafe", "original layout root is unsafe"
            ) from error
        root = Path(root).resolve(strict=True)
        from literate_ai.adapters.project_layout_lease import (
            current_layout_lease,
            require_layout_lease,
        )

        existing = current_layout_lease(root)
        if existing is not None:
            require_layout_lease(existing, root)
            yield
            require_layout_lease(existing, root)
            return
        directory = cls.layout_metadata_directory(root)
        coordinate = (directory or root) / "literate-layout"
        with cls(root)._lock(root, manifest_path=coordinate, _layout_lease_root=root):
            yield

    def create(self, definition: ProjectDefinition) -> ProjectConfigurationSnapshot:
        content = serialize_project_configuration(definition)
        self._require_bounded(content)
        root = self._root(create=True)
        with self.layout_lock(root):
            return self._create_locked(root, definition, content)

    def _create_locked(
        self, root: Path, definition: ProjectDefinition, content: bytes
    ) -> ProjectConfigurationSnapshot:
        context = self.context(root)
        if context.root != root or context.manifest_path.exists():
            raise ProjectError(
                "project.manifest_exists", "project manifest already exists"
            )
        framework = (
            root / definition.framework_directory
            if definition.framework_directory
            else root
        )
        if framework != root:
            framework.mkdir(exist_ok=True)
            try:
                require_safe_directory(framework)
            except (UnsafeFilesystemPathError, OSError) as exc:
                raise ProjectError(
                    "project.framework_directory_unsafe",
                    "framework directory is unsafe",
                ) from exc
        context = ProjectContext.observe(root, framework)
        path = context.manifest_path
        with self._lock(root, manifest_path=path):
            current = self.context(root)
            if current.manifest_path.exists() or current.manifest_path.is_symlink():
                raise ProjectError(
                    "project.manifest_exists", "project manifest already exists"
                )
            if path.exists() or path.is_symlink():
                raise ProjectError(
                    "project.manifest_exists", "project manifest already exists"
                )
            if ProjectContext.observe(root, framework) != context:
                raise ProjectError(
                    "project.manifest_stale",
                    "project directory changed during creation",
                )
            self._replace(path, content)
        return ProjectConfigurationSnapshot(
            root, definition, content, path, context.directory_binding
        )

    def update(
        self,
        expected: ProjectConfigurationSnapshot,
        definition: ProjectDefinition,
        *,
        require_current: Callable[[], None] | None = None,
    ) -> ProjectConfigurationSnapshot:
        if not isinstance(expected, ProjectConfigurationSnapshot):
            raise TypeError("expected must be a ProjectConfigurationSnapshot")
        content = serialize_project_configuration(definition)
        self._require_bounded(content)
        context = self.context(self._root())
        root = context.root
        if expected.root != root:
            raise ProjectError(
                "project.manifest_stale", "project snapshot belongs to another root"
            )
        self._require_layout(context, definition)
        with self._lock(root):
            selected = self.context(root)
            path = selected.manifest_path
            if (
                path != expected.manifest_path
                or selected != context
                or selected.directory_binding != expected.directory_binding
            ):
                raise ProjectError(
                    "project.manifest_stale",
                    "project manifest location changed since it was read",
                )
            before = path.lstat() if require_current is not None else None
            current = self._read_manifest(path)
            if current != expected.content:
                raise ProjectError(
                    "project.manifest_stale",
                    "project manifest changed since it was read",
                )
            if self.context(root) != selected:
                raise ProjectError(
                    "project.manifest_stale",
                    "project manifest location changed while it was read",
                )

            def close_publication_inputs():
                require_current()
                if self.context(root) != selected:
                    raise ProjectError(
                        "project.manifest_stale",
                        "project manifest location changed during publication checks",
                    )
                after = path.lstat()
                if any(
                    getattr(before, name) != getattr(after, name)
                    for name in (
                        "st_dev",
                        "st_ino",
                        "st_mode",
                        "st_size",
                        "st_mtime_ns",
                        "st_ctime_ns",
                    )
                ):
                    raise ProjectError(
                        "project.manifest_stale",
                        "project manifest changed during publication checks",
                    )

            if content != current:
                if require_current is None:
                    self._replace(path, content)
                else:
                    self._replace(
                        path, content, require_current=close_publication_inputs
                    )
            elif require_current is not None:
                close_publication_inputs()
        return ProjectConfigurationSnapshot(
            root, definition, content, path, selected.directory_binding
        )

    def _read_manifest(self, path: Path) -> bytes:
        from literate_ai.adapters.bounded_role_observation import (
            current_role_observation,
        )

        observation = current_role_observation()
        if observation is not None:
            content = observation.file(path, maximum_bytes=self.maximum_bytes).content
            observation.json_value(content, str(path))
            return content
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        flags |= (
            getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            before = path.lstat()
            if not stat.S_ISREG(before.st_mode):
                raise OSError("manifest is not a regular file")
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise ProjectError(
                "project.manifest_unavailable",
                f"project root must contain {PROJECT_FILENAME}",
            ) from exc
        try:
            opened = os.fstat(descriptor)
            observed = path.lstat()
            if (
                not stat.S_ISREG(opened.st_mode)
                or stat.S_ISLNK(observed.st_mode)
                or not self._same_file(opened, before)
                or not self._same_file(opened, observed)
                or opened.st_size > self.maximum_bytes
            ):
                raise ProjectError(
                    "project.manifest_unavailable",
                    "project manifest is unsafe or exceeds the byte limit",
                )
            content = bytearray()
            while len(content) <= self.maximum_bytes:
                chunk = os.read(
                    descriptor,
                    min(64 * 1024, self.maximum_bytes + 1 - len(content)),
                )
                if not chunk:
                    break
                content.extend(chunk)
            after = path.lstat()
            final = os.fstat(descriptor)
            if (
                len(content) > self.maximum_bytes
                or not self._same_file(opened, final)
                or not self._same_file(opened, after)
            ):
                raise ProjectError(
                    "project.manifest_unavailable",
                    "project manifest changed while it was read",
                )
            return bytes(content)
        except ProjectError:
            raise
        except OSError as exc:
            raise ProjectError(
                "project.manifest_unavailable", "project manifest is unavailable"
            ) from exc
        finally:
            os.close(descriptor)

    def _require_bounded(self, content: bytes) -> None:
        if len(content) > self.maximum_bytes:
            raise ProjectError(
                "project.manifest_too_large",
                "project manifest exceeds the byte limit",
            )

    @staticmethod
    def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
        return os.path.samestat(left, right)

    @staticmethod
    def _lock_identity_matches(
        path: Path,
        path_metadata: os.stat_result,
        descriptor: int,
        descriptor_metadata: os.stat_result,
    ) -> bool:
        """Return whether ``path`` and the held descriptor name the same file.

        On POSIX this is the exact ``(st_dev, st_ino)`` compare-and-swap check the
        lock relied on before. On Windows ``os.open``/``os.fstat`` frequently
        report ``st_ino == 0`` (CPython issue #76): the bare ``st_ino`` compare is
        then either a no-op that treats a swapped lock file as safe or a flake
        that aborts on an unchanged file. When Windows cannot supply a reliable
        inode we fall back to ``GetFileInformationByHandle`` file-index/volume
        identity -- reopening the path without following reparse points and
        comparing it against the descriptor's own identity -- which is
        Microsoft's documented reliable per-volume file identity. Symlink and
        regular-file checks are enforced by the callers regardless.
        """

        if _is_windows() and (
            path_metadata.st_ino == 0 or descriptor_metadata.st_ino == 0
        ):
            return _windows_identity_matches(path, descriptor)
        return (path_metadata.st_dev, path_metadata.st_ino) == (
            descriptor_metadata.st_dev,
            descriptor_metadata.st_ino,
        )

    @staticmethod
    def _acquire_exclusive(descriptor: int) -> None:
        """Take an exclusive advisory lock on byte 0, blocking until acquired.

        POSIX uses a single blocking ``flock(LOCK_EX)`` -- byte-for-byte the
        original behavior. Windows has no blocking mode that raises a clean errno,
        so we poll non-blocking ``LK_NBLCK`` on a bounded deadline: transient
        contention (EACCES/EAGAIN/EDEADLOCK) is retried, and any other error --
        or the deadline -- propagates as ``OSError`` for the caller to surface as
        ``project.manifest_lock``.
        """

        if os.name != "nt":
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
            return
        import msvcrt

        contention = {
            errno.EACCES,
            errno.EAGAIN,
            getattr(errno, "EDEADLOCK", errno.EDEADLK),
        }
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        while True:
            try:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:
                # EDEADLOCK is what ``msvcrt.locking`` reports when the byte is
                # already locked by another holder; EACCES/EAGAIN cover the same
                # contention on other configurations.
                if exc.errno not in contention:
                    raise
                if time.monotonic() >= deadline:
                    raise
                time.sleep(_LOCK_RETRY_SECONDS)

    @staticmethod
    def _release_exclusive(descriptor: int) -> None:
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)

    @contextmanager
    def _lock(
        self,
        root: Path,
        *,
        manifest_path: Path | None = None,
        require_path: Callable[[Path], None] | None = None,
        _layout_lease_root: Path | None = None,
    ) -> Iterator[None]:
        path = (
            self.lock_path(root)
            if manifest_path is None
            else manifest_path.with_name(f".{manifest_path.name}.write.lock")
        )
        descriptor = -1
        locked = False
        opened: os.stat_result | None = None
        try:
            if require_path is not None:
                require_path(path)
            descriptor, locked, opened = self._open_and_acquire(path)
            if _layout_lease_root is None:
                yield
            else:
                from literate_ai.adapters.project_layout_lease import (
                    ProjectLayoutLeaseError,
                    acquired_layout_lease,
                )

                try:
                    with acquired_layout_lease(
                        _layout_lease_root,
                        path,
                        descriptor,
                        _origin=_LAYOUT_ACQUIRED_LEASE_KEY,
                    ):
                        yield
                except ProjectLayoutLeaseError as error:
                    raise ProjectError(
                        "project.layout_lock_unsafe", str(error)
                    ) from error
        except ProjectError:
            raise
        except OSError as exc:
            raise ProjectError("project.manifest_lock", "manifest lock failed") from exc
        finally:
            if descriptor != -1:
                if locked:
                    try:
                        self._release_exclusive(descriptor)
                    except OSError:
                        pass
                os.close(descriptor)
            if opened is not None and _lock_cleanup_allowed(path, require_path):
                self._remove_idle_lock(path, opened, require_path=require_path)

    def _open_and_acquire(self, path: Path) -> tuple[int, bool, os.stat_result]:
        """Open the lock file, take the exclusive lock, and verify identity.

        Returns ``(descriptor, locked, opened)`` with the exclusive lock held.

        A concurrent holder's ``_remove_idle_lock`` may unlink the lock file
        after this process has already opened it but before -- on POSIX -- this
        process wins the *blocking* ``flock``. When that happens the descriptor
        we hold names an inode that the path no longer resolves to (or the path
        has vanished entirely). That is a benign lost race for the *lock*, not a
        malicious swap and not a lost compare-and-swap: the correct response is
        to release, reopen the freshly recreated lock file, and retry -- never to
        surface ``project.manifest_lock`` to a caller that simply queued behind a
        prior writer. Retrying keeps the writer serialized so it can go on to
        read the changed manifest and fail its CAS with ``project.manifest_stale``
        (the loser contract). Every attempt re-verifies symlink/regular-file and
        descriptor-vs-path identity, so the swap and reparse protections are
        unchanged.
        """

        # WINDOWS-LOCK-001: converge on the byte-for-byte open flags of the
        # proven-on-Windows ``_cache_lock.exclusive_cache_lock`` path
        # (``O_RDWR | O_CREAT | O_BINARY | O_NOFOLLOW``). Notably this drops
        # ``O_CLOEXEC``: that flag is meaningless for a lock descriptor held only
        # within this process, it is absent from the lock implementation that
        # passes on Windows CI, and it is one of only two things the failing
        # manifest path did that the working cache path did not.
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        while True:
            try:
                descriptor = os.open(path, flags, 0o600)
            except PermissionError as exc:
                # Windows delete-pending race: another writer's idle-lock cleanup
                # unlinked the file but a handle is still closing, so O_CREAT open
                # transiently fails EACCES until the delete completes. Retry within
                # the deadline. POSIX has no such state; raise there immediately.
                if os.name == "nt" and time.monotonic() < deadline:
                    time.sleep(_LOCK_RETRY_SECONDS)
                    continue
                raise ProjectError(
                    "project.manifest_lock", "manifest lock is unsafe"
                ) from exc
            except OSError as exc:
                raise ProjectError(
                    "project.manifest_lock", "manifest lock is unsafe"
                ) from exc
            locked = False
            retry = False
            try:
                opened = os.fstat(descriptor)
                observed = path.lstat()
            except FileNotFoundError:
                # An idle-lock cleanup can unlink the inode after this process
                # opened it but before it starts waiting on the lock. No lock is
                # held yet, so discard the orphaned descriptor and retry the normal
                # sequence. A path that exists but names another inode remains a
                # hard failure in the identity check below.
                os.close(descriptor)
                if time.monotonic() >= deadline:
                    raise ProjectError(
                        "project.manifest_lock",
                        "manifest lock changed before it was acquired",
                    ) from None
                time.sleep(_LOCK_RETRY_SECONDS)
                continue
            except BaseException:
                os.close(descriptor)
                raise
            try:
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or stat.S_ISLNK(observed.st_mode)
                    or not self._lock_identity_matches(
                        path, observed, descriptor, opened
                    )
                ):
                    raise ProjectError(
                        "project.manifest_lock", "manifest lock is unsafe"
                    )
                # Windows ``msvcrt.locking`` locks a byte range that must lie
                # within the file: locking byte [0, 1) of a 0-byte lock file
                # returns EACCES *permanently* (not transient contention), so the
                # retry loop would spin until the deadline and then raise
                # ``manifest_lock``. Ensure the file holds its placeholder byte
                # BEFORE acquiring the lock. This is safe on a freshly created,
                # not-yet-locked file: nobody can hold a byte-range lock on a byte
                # that does not exist yet, so the write can never collide with
                # another holder. When the file already has content (another
                # holder wrote the placeholder first) we skip the write.
                #
                # WINDOWS-LOCK-001: mirror the proven ``_cache_lock`` path exactly
                # -- write the byte, then ``lseek`` back to 0, and NOTHING ELSE.
                # The failing manifest path additionally called ``os.fsync`` here,
                # which is ``_commit()``/``FlushFileBuffers`` on Windows. That was
                # one of only two behaviours the manifest lock added over the
                # cache lock that passes on Windows CI, and it is unnecessary: the
                # placeholder byte only has to exist in the file so the 1-byte
                # region is lockable -- it is advisory-lock scratch, not durable
                # state, so there is no reason to force it to disk before locking.
                if opened.st_size == 0:
                    os.write(descriptor, b"\0")
                    os.lseek(descriptor, 0, os.SEEK_SET)
                # POSIX blocks here on ``flock(LOCK_EX)`` so a concurrent loser
                # waits for the current writer, then loses the compare-and-swap
                # cleanly. This must remain blocking (not timeout-bounded) on
                # POSIX so the loser surfaces ``manifest_stale``, never
                # ``manifest_lock``.
                self._acquire_exclusive(descriptor)
                locked = True
                try:
                    observed = path.lstat()
                except FileNotFoundError:
                    # The lock file we held was unlinked by a prior holder's idle
                    # cleanup while we blocked on ``flock`` -- ``_remove_idle_lock``
                    # only ever *unlinks* the lock inode, never replaces it with a
                    # different regular file. A vanished path is therefore a benign
                    # lost race for the *lock*, not a malicious swap and not a
                    # compare-and-swap loss: release, reopen the recreated lock
                    # file, and retry so the writer stays serialized and can go on
                    # to fail its manifest CAS with ``manifest_stale``. A path that
                    # still exists but names a *different* inode is a genuine swap
                    # and is rejected below.
                    if time.monotonic() >= deadline:
                        raise ProjectError(
                            "project.manifest_lock",
                            "manifest lock changed while it was acquired",
                        ) from None
                    retry = True
                    observed = None
                opened = os.fstat(descriptor)
                if observed is not None and (
                    not stat.S_ISREG(opened.st_mode)
                    or stat.S_ISLNK(observed.st_mode)
                    or not self._lock_identity_matches(
                        path, observed, descriptor, opened
                    )
                ):
                    raise ProjectError(
                        "project.manifest_lock",
                        "manifest lock changed while it was acquired",
                    )
                if not retry:
                    return descriptor, locked, opened
            except BaseException:
                if locked:
                    try:
                        self._release_exclusive(descriptor)
                    except OSError:
                        pass
                os.close(descriptor)
                raise
            # Benign lost race: clean up this attempt, back off, and retry.
            if locked:
                try:
                    self._release_exclusive(descriptor)
                except OSError:
                    pass
            os.close(descriptor)
            if retry:
                time.sleep(_LOCK_RETRY_SECONDS)

    def _remove_idle_lock(
        self,
        path: Path,
        expected: os.stat_result,
        *,
        require_path: Callable[[Path], None] | None = None,
    ) -> None:
        """Remove only the same unlocked inode when no waiter has acquired it."""

        flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError:
            return
        locked = False
        try:
            opened = os.fstat(descriptor)
            observed = path.lstat()
            # ``expected`` is a stat_result captured earlier; on Windows its
            # ``st_ino`` may be 0, so a bare ``samestat`` against it would treat
            # any lock file as "the same" one. Only trust the historical
            # stat-to-stat identity when the inode is reliable; the live
            # path-vs-descriptor identity is verified through the reliable helper.
            expected_still_matches = (
                self._same_file(expected, opened)
                if not (_is_windows() and expected.st_ino == 0)
                else self._lock_identity_matches(path, observed, descriptor, opened)
            )
            if (
                not stat.S_ISREG(opened.st_mode)
                or stat.S_ISLNK(observed.st_mode)
                or not expected_still_matches
                or not self._lock_identity_matches(path, observed, descriptor, opened)
            ):
                return
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                except OSError:
                    return
            else:
                import fcntl

                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    return
            locked = True
            observed = path.lstat()
            opened = os.fstat(descriptor)
            if stat.S_ISLNK(observed.st_mode) or not self._lock_identity_matches(
                path, observed, descriptor, opened
            ):
                return
            if os.name != "nt" and _lock_cleanup_allowed(path, require_path):
                path.unlink()
        except OSError:
            return
        finally:
            if locked:
                try:
                    self._release_exclusive(descriptor)
                except OSError:
                    pass
            os.close(descriptor)
        if os.name == "nt" and locked:
            # On Windows the file must be unlinked after the descriptor closes and
            # the byte lock is released. Re-verify the path still names the inode
            # we just held (never a symlink) before removing it.
            try:
                observed = path.lstat()
                if (
                    not stat.S_ISLNK(observed.st_mode)
                    and (
                        self._same_file(expected, observed)
                        if not (_is_windows() and expected.st_ino == 0)
                        else True
                    )
                    and _lock_cleanup_allowed(path, require_path)
                ):
                    path.unlink()
            except OSError:
                pass

    @staticmethod
    def _replace(
        path: Path, content: bytes, *, require_current: Callable[[], None] | None = None
    ) -> None:
        if publish_atomic_file_if_scoped(
            path, content, require_current=require_current
        ):
            return
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if require_current is not None:
                require_current()
            temporary.replace(path)
            # Fsync the parent directory so the rename is durable. Windows does
            # not permit FlushFileBuffers on a directory handle (it raises
            # PermissionError/EACCES), and NTFS metadata durability does not
            # require it, so this is POSIX-only.
            if os.name != "nt":
                directory = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)


class PinnedInputClosureError(ProjectError):
    """A generation-authority file is unsafe, unbounded, or changed."""


@dataclass(frozen=True, slots=True)
class _PinnedInput:
    path: Path
    boundary: Path
    content: bytes
    labels: tuple[str, ...]

    @property
    def content_identity(self) -> str:
        return f"sha256:{hashlib.sha256(self.content).hexdigest()}"


class PinnedInputClosure:
    """Bounded exact files whose bytes authorize one generation operation.

    Entries retain their original bytes and boundary. Revalidation rejects mutation,
    disappearance, non-regular replacements, and a symlink in any path component.
    Logical labels make the closure identity portable without publishing host paths.
    """

    def __init__(
        self,
        *,
        maximum_files: int = DEFAULT_MAXIMUM_PINNED_INPUT_FILES,
        maximum_file_bytes: int = DEFAULT_MAXIMUM_PINNED_INPUT_BYTES,
        maximum_total_bytes: int = DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES,
    ) -> None:
        if (
            maximum_files < 1
            or maximum_file_bytes < 1
            or maximum_total_bytes < maximum_file_bytes
        ):
            raise ValueError("pinned-input closure limits must be positive and ordered")
        self.maximum_files = maximum_files
        self.maximum_file_bytes = maximum_file_bytes
        self.maximum_total_bytes = maximum_total_bytes
        self._entries: dict[tuple[Path, Path], _PinnedInput] = {}
        self._total_bytes = 0
        self._labels: dict[str, tuple[Path, Path, bytes]] = {}

    @classmethod
    def for_project(cls, project: object | None) -> PinnedInputClosure:
        limits = getattr(getattr(project, "definition", None), "scale_limits", None)
        if limits is None:
            return cls()
        return cls(
            maximum_files=limits.pinned_input_files,
            maximum_total_bytes=limits.pinned_input_total_bytes,
        )

    def pin(
        self,
        path: Path,
        *,
        boundary: Path,
        label: str,
        expected_content: bytes | None = None,
        expected_identity: str | ContentIdentity | None = None,
    ) -> bytes:
        """Capture one regular file and optionally bind bytes already consumed."""

        if not label or len(label.encode("utf-8")) > 1024:
            raise PinnedInputClosureError(
                "inputs.closure_label_invalid",
                "pinned-input labels must be non-empty and at most 1024 bytes",
            )
        expected_identity = _expected_identity_before_read(expected_identity)
        configured_boundary, resolved_boundary = self._boundary(boundary)
        resolved_path, content = self._read(
            path, resolved_boundary, configured_boundary=configured_boundary
        )
        return self._admit_read(
            resolved_path,
            resolved_boundary,
            content,
            label=label,
            expected_content=expected_content,
            expected_identity=expected_identity,
        )

    def _admit_read(
        self,
        resolved_path,
        resolved_boundary,
        content,
        *,
        label,
        expected_content=None,
        expected_identity=None,
    ) -> bytes:
        """One common identity, quota and label admission after a current read."""
        if expected_content is not None and content != expected_content:
            raise PinnedInputClosureError(
                "inputs.closure_capture_drift",
                f"generation authority changed while it was captured: {label}",
            )
        if expected_identity is not None:
            identity = (
                expected_identity.uri
                if isinstance(expected_identity, ContentIdentity)
                else expected_identity
            )
            try:
                parsed = ContentIdentity.parse_uri(identity)
            except (TypeError, ValueError) as exc:
                raise PinnedInputClosureError(
                    "inputs.closure_identity_invalid",
                    f"generation authority has an invalid identity: {label}",
                ) from exc
            if hashlib.sha256(content).hexdigest() != parsed.digest:
                raise PinnedInputClosureError(
                    "inputs.closure_identity_changed",
                    f"generation authority identity changed: {label}",
                )
        self._admit(_PinnedInput(resolved_path, resolved_boundary, content, (label,)))
        return content

    def _supports_direct_capture(self):
        namespace = object.__getattribute__(self, "__dict__")
        return (
            type(self) is PinnedInputClosure
            and "_read" not in namespace
            and "pin" not in namespace
            and type(self).__dict__.get("_read") is _DEFAULT_PINNED_INPUT_READ
            and type(self).__dict__.get("pin") is _DEFAULT_PINNED_INPUT_PIN
            and _pinned_read_batch_supported()
        )

    def _try_pin_direct(
        self,
        path,
        *,
        boundary,
        label,
        directories,
        expected_identity,
        unsafe_code,
        unavailable_code,
    ):
        """Fuse a strict local path check and bounded capture, or decline early.

        None is eligibility-only, before payload IO. The caller then retains its
        original path-helper plus ordinary pin policy. Errors never ask to retry.
        """
        if not self._supports_direct_capture():
            return None
        configured = Path(os.path.abspath(path))
        if (
            not boundary.is_absolute()
            or ".." in boundary.parts
            or not configured.is_relative_to(boundary)
            or configured == boundary
        ):
            return None
        maximum = self.maximum_file_bytes

        def settings_current():
            if (
                self.maximum_file_bytes != maximum
                or not self._supports_direct_capture()
            ):
                raise PinnedInputClosureError(
                    "inputs.closure_changed",
                    "pinned input reader or limit changed during capture",
                )

        if not label or len(label.encode("utf-8")) > 1024:
            raise PinnedInputClosureError(
                "inputs.closure_label_invalid",
                "pinned-input labels must be non-empty and at most 1024 bytes",
            )
        expected_identity = _expected_identity_before_read(expected_identity)
        content = None
        try:
            with directories.capture(configured.parent) as directory:
                if directory is not None:
                    parent = directory.binding.descriptor
                    named = os.stat(
                        configured.name, dir_fd=parent, follow_symlinks=False
                    )
                    if stat_is_link_or_reparse(named) or not stat.S_ISREG(
                        named.st_mode
                    ):
                        raise PinnedInputClosureError(
                            unsafe_code,
                            "Component content must be a direct regular file "
                            "without reparse points",
                        )
                    if named.st_ino:
                        if named.st_size > maximum:
                            raise PinnedInputClosureError(
                                "inputs.closure_file_size_limit",
                                "generation authority exceeds the "
                                "pinned-input per-file limit",
                            )
                        original = _pinned_file_stamp(named)
                        descriptor = os.open(
                            configured.name,
                            os.O_RDONLY
                            | os.O_NOFOLLOW
                            | os.O_NONBLOCK
                            | getattr(os, "O_CLOEXEC", 0),
                            dir_fd=parent,
                        )
                        try:
                            if _pinned_file_stamp(os.fstat(descriptor)) != original:
                                raise _pinned_replaced()
                            content = _read_pinned_descriptor(descriptor, maximum)
                            if _pinned_file_stamp(os.fstat(descriptor)) != original:
                                raise _pinned_replaced()
                        finally:
                            os.close(descriptor)
                        if len(content) > maximum:
                            raise PinnedInputClosureError(
                                "inputs.closure_file_size_limit",
                                "generation authority exceeds the "
                                "pinned-input per-file limit",
                            )
                        if (
                            _pinned_file_stamp(
                                os.stat(
                                    configured.name,
                                    dir_fd=parent,
                                    follow_symlinks=False,
                                )
                            )
                            != original
                        ):
                            raise _pinned_replaced()
                settings_current()
            settings_current()
        except UnsafeFilesystemPathError as error:
            raise PinnedInputClosureError(
                unsafe_code,
                "Component content traverses an unsafe directory",
            ) from error
        except OSError as error:
            raise PinnedInputClosureError(
                unavailable_code,
                "Component content is unavailable",
            ) from error
        if content is None:
            return None
        return self._admit_read(
            configured,
            boundary,
            content,
            label=label,
            expected_identity=expected_identity,
        )

    def include(self, other: PinnedInputClosure) -> None:
        """Merge an independently captured authority set without rereading it."""

        if other is self:
            return
        other.require_unchanged()
        for entry in other._entries.values():
            self._admit(entry)

    def fork(self) -> PinnedInputClosure:
        """Create an independent closure initialized with this exact authority set."""

        copied = PinnedInputClosure(
            maximum_files=self.maximum_files,
            maximum_file_bytes=self.maximum_file_bytes,
            maximum_total_bytes=self.maximum_total_bytes,
        )
        for entry in self._entries.values():
            copied._admit(entry)
        return copied

    @property
    def identity(self) -> str:
        return canonical_identity(self._identity_document()).uri

    @property
    def file_count(self) -> int:
        return len(self._entries)

    @property
    def total_bytes(self) -> int:
        return self._total_bytes

    @property
    def pinned_paths(self) -> tuple[Path, ...]:
        """Current bounded leaf names for native closing checks, not ownership.

        This read-only inspection grants no exclusion, write or execution rights.
        Consumers must still validate this actual closure and its original inputs.
        """
        return tuple(dict.fromkeys(entry.path for entry in self._entries.values()))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "literate-ai/pinned-input-closure@1",
            "identity": self.identity,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "inputs": self._identity_document()["inputs"],
        }

    def require_unchanged(self) -> None:
        if (
            _pinned_read_batch_supported()
            and type(self) is PinnedInputClosure
            and getattr(self._read, "__func__", None) is _DEFAULT_PINNED_INPUT_READ
            and self._require_unchanged_posix()
        ):
            return
        for entry in self._entries.values():
            _resolved, content = self._read(entry.path, entry.boundary)
            if content != entry.content:
                raise PinnedInputClosureError(
                    "inputs.closure_changed",
                    "generation authority changed during the operation: "
                    + ", ".join(entry.labels),
                )

    def _require_unchanged_posix(self):
        """Read original pinned DATA once per entry using fresh bounded handles."""
        values, entries_current = self._capture_entry_values()
        limits = (self.maximum_files, self.maximum_file_bytes, self.maximum_total_bytes)
        rows = tuple(
            (Path(path), Path(boundary), content, labels)
            for path, boundary, content, labels in values
        )
        for path, boundary, _content, _labels in rows:
            if (
                not path.is_absolute()
                or not boundary.is_absolute()
                or ".." in path.parts
                or ".." in boundary.parts
                or not path.is_relative_to(boundary)
                or path == boundary
            ):
                raise PinnedInputClosureError(
                    "inputs.closure_path_escape", "pinned input escaped its boundary"
                )

        def metadata_current():
            entries_current()
            if limits != (
                self.maximum_files,
                self.maximum_file_bytes,
                self.maximum_total_bytes,
            ):
                raise PinnedInputClosureError(
                    "inputs.closure_changed",
                    "pinned input limits changed during validation",
                )

        try:
            parents = tuple(dict.fromkeys(row[0].parent for row in rows))
            with _readonly_directory_batch(parents) as view:
                if view is None:
                    metadata_current()
                    return False
                descriptors, _directories_current = view
                originals = []
                # Establish the entire original file set BEFORE reading payloads.
                # Unknown identity declines the optimization before any file read.
                for path, _boundary, content, labels in rows:
                    parent = descriptors[path.parent]
                    value = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                    original = _pinned_file_stamp(value)
                    if not value.st_ino:
                        metadata_current()
                        return False
                    if value.st_size > limits[1]:
                        raise PinnedInputClosureError(
                            "inputs.closure_file_size_limit",
                            "generation authority exceeds the pinned-input "
                            "per-file limit",
                        )
                    originals.append((path, parent, original, content, labels))
                for path, parent, original, expected, labels in originals:
                    descriptor = os.open(
                        path.name,
                        os.O_RDONLY
                        | os.O_NOFOLLOW
                        | os.O_NONBLOCK
                        | getattr(os, "O_CLOEXEC", 0),
                        dir_fd=parent,
                    )
                    try:
                        if _pinned_file_stamp(os.fstat(descriptor)) != original:
                            raise _pinned_replaced()
                        content = _read_pinned_descriptor(descriptor, limits[1])
                        if _pinned_file_stamp(os.fstat(descriptor)) != original:
                            raise _pinned_replaced()
                    finally:
                        os.close(descriptor)
                    if len(content) > limits[1]:
                        raise PinnedInputClosureError(
                            "inputs.closure_file_size_limit",
                            "generation authority exceeds the pinned-input "
                            "per-file limit",
                        )
                    if content != expected:
                        raise PinnedInputClosureError(
                            "inputs.closure_changed",
                            "generation authority changed during the operation: "
                            + ", ".join(labels),
                        )
                for path, parent, original, _content, _labels in originals:
                    named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
                    if _pinned_file_stamp(named) != original:
                        raise _pinned_replaced()
                metadata_current()
            return True
        except UnsafeFilesystemPathError as error:
            raise PinnedInputClosureError(
                "inputs.closure_symlink",
                "pinned directory changed or traverses a symbolic link",
            ) from error
        except OSError as error:
            raise PinnedInputClosureError(
                "inputs.closure_unavailable",
                "pinned generation authority is unavailable",
            ) from error

    def _capture_entry_values(self):
        """Snapshot immutable entry DATA without retaining aliased entry DTOs."""

        def current_values():
            rows = []
            for key, entry in self._entries.items():
                path, boundary = str(entry.path), str(entry.boundary)
                if (
                    tuple(str(part) for part in key) != (path, boundary)
                    or not isinstance(entry.content, bytes)
                    or type(entry.labels) is not tuple
                    or any(not isinstance(label, str) for label in entry.labels)
                ):
                    raise PinnedInputClosureError(
                        "inputs.closure_changed", "pinned input entry metadata changed"
                    )
                rows.append(
                    (
                        path,
                        boundary,
                        (
                            entry.content
                            if type(entry.content) is bytes
                            else memoryview(entry.content).tobytes()
                        ),
                        tuple(str.__str__(label) for label in entry.labels),
                    )
                )
            return tuple(sorted(rows, key=lambda row: (row[0], row[1])))

        original = current_values()

        def require_entries():
            if current_values() != original:
                raise PinnedInputClosureError(
                    "inputs.closure_changed", "pinned inputs changed before close"
                )

        return original, require_entries

    def capture_current_stamps(self):
        """Fence original POSIX files after owner callbacks without reading again.

        This is observation only. It neither renews authority nor replaces byte
        validation. Directory identity is pinned without rejecting unrelated
        sibling writes; original files retain metadata-change timestamps.
        """
        if os.name != "posix":
            raise ValueError("live pinned files require POSIX change timestamps")
        entries, entries_current = self._capture_entry_values()
        files = {}

        def file_stamp(path):
            value = path.lstat()
            if not stat.S_ISREG(value.st_mode):
                raise PinnedInputClosureError(
                    "inputs.closure_changed", "pinned file is no longer regular"
                )
            return (
                value.st_dev,
                value.st_ino,
                value.st_mode,
                value.st_nlink,
                value.st_size,
                value.st_mtime_ns,
                value.st_ctime_ns,
            )

        for path, _boundary, _content, _labels in entries:
            path = Path(path)
            files[path] = file_stamp(path)
        directories_current = capture_directory_ancestries(
            tuple(dict.fromkeys(Path(row[0]).parent for row in entries))
        )

        def require_stamps():
            try:
                directories_current()
            except (OSError, UnsafeFilesystemPathError) as error:
                raise PinnedInputClosureError(
                    "inputs.closure_changed", "pinned directory changed"
                ) from error
            entries_current()
            if any(file_stamp(path) != value for path, value in files.items()):
                raise PinnedInputClosureError(
                    "inputs.closure_changed", "pinned inputs changed before close"
                )

        self.require_unchanged()
        require_stamps()
        return require_stamps

    def _identity_document(self) -> dict[str, object]:
        return {
            "schema": "literate-ai/pinned-input-closure@1",
            "inputs": [
                {
                    "labels": list(item.labels),
                    "content_identity": item.content_identity,
                    "bytes": len(item.content),
                }
                for item in sorted(
                    self._entries.values(), key=lambda value: value.labels
                )
            ],
        }

    def _admit(self, entry: _PinnedInput) -> None:
        key = (entry.path, entry.boundary)
        existing = self._entries.get(key)
        labels = set(entry.labels)
        if existing is not None:
            if existing.content != entry.content:
                raise PinnedInputClosureError(
                    "inputs.closure_capture_drift",
                    "one generation authority path was captured with different bytes",
                )
            labels.update(existing.labels)
        candidate = _PinnedInput(
            entry.path,
            entry.boundary,
            entry.content,
            tuple(sorted(labels)),
        )
        for label in candidate.labels:
            claimed = self._labels.get(label)
            claim = (candidate.path, candidate.boundary, candidate.content)
            if claimed is not None and claimed != claim:
                raise PinnedInputClosureError(
                    "inputs.closure_label_conflict",
                    f"generation authority label is ambiguous: {label}",
                )
        prospective_files = len(self._entries) + (existing is None)
        prospective_bytes = self.total_bytes + (
            len(candidate.content) if existing is None else 0
        )
        if len(candidate.content) > self.maximum_file_bytes:
            raise PinnedInputClosureError(
                "inputs.closure_file_size_limit",
                "generation authority exceeds the pinned-input per-file limit",
            )
        if prospective_files > self.maximum_files:
            raise PinnedInputClosureError(
                "inputs.closure_file_limit",
                f"pinned-input files: observed {prospective_files}, "
                f"allowed {self.maximum_files}",
            )
        if prospective_bytes > self.maximum_total_bytes:
            raise PinnedInputClosureError(
                "inputs.closure_total_size_limit",
                f"pinned-input bytes: observed {prospective_bytes}, "
                f"allowed {self.maximum_total_bytes}",
            )
        self._entries[key] = candidate
        self._total_bytes = prospective_bytes
        for label in candidate.labels:
            self._labels[label] = (
                candidate.path,
                candidate.boundary,
                candidate.content,
            )

    def _boundary(self, boundary: Path) -> tuple[Path, Path]:
        configured = Path(os.path.abspath(boundary))
        if configured.is_symlink():
            raise PinnedInputClosureError(
                "inputs.closure_boundary_invalid",
                "generation-authority boundary cannot be a symbolic link",
            )
        try:
            resolved = configured.resolve(strict=True)
        except OSError as exc:
            raise PinnedInputClosureError(
                "inputs.closure_boundary_invalid",
                "generation-authority boundary is unavailable",
            ) from exc
        if not resolved.is_dir():
            raise PinnedInputClosureError(
                "inputs.closure_boundary_invalid",
                "generation-authority boundary must be a directory",
            )
        return configured, resolved

    def _read(
        self,
        path: Path,
        boundary: Path,
        *,
        configured_boundary: Path | None = None,
    ) -> tuple[Path, bytes]:
        configured = Path(os.path.abspath(path))
        lexical_boundary = configured_boundary or boundary
        if configured.is_relative_to(lexical_boundary):
            current = lexical_boundary
            for part in configured.relative_to(lexical_boundary).parts:
                current /= part
                if current.is_symlink():
                    raise PinnedInputClosureError(
                        "inputs.closure_symlink",
                        "generation authority cannot traverse a symbolic link",
                    )
        if configured.is_symlink():
            raise PinnedInputClosureError(
                "inputs.closure_symlink",
                "generation authority cannot traverse a symbolic link",
            )
        try:
            resolved = configured.resolve(strict=True)
        except OSError as exc:
            raise PinnedInputClosureError(
                "inputs.closure_unavailable",
                f"generation authority is unavailable: {configured}",
            ) from exc
        if not resolved.is_relative_to(boundary):
            raise PinnedInputClosureError(
                "inputs.closure_path_escape",
                "generation authority escapes its declared boundary",
            )
        relative = resolved.relative_to(boundary)
        current = boundary
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise PinnedInputClosureError(
                    "inputs.closure_symlink",
                    "generation authority cannot traverse a symbolic link",
                )
        if not resolved.is_file():
            raise PinnedInputClosureError(
                "inputs.closure_not_regular",
                "generation authority must be a regular file",
            )
        try:
            with resolved.open("rb") as stream:
                remaining = self.maximum_file_bytes + 1
                chunks = []
                while remaining > 0:
                    chunk = stream.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                content = b"".join(chunks)
        except OSError as exc:
            raise PinnedInputClosureError(
                "inputs.closure_unavailable",
                f"generation authority could not be read: {configured}",
            ) from exc
        if len(content) > self.maximum_file_bytes:
            raise PinnedInputClosureError(
                "inputs.closure_file_size_limit",
                "generation authority exceeds the pinned-input per-file limit",
            )
        if resolved.is_symlink() or resolved.resolve(strict=True) != resolved:
            raise PinnedInputClosureError(
                "inputs.closure_replaced",
                "generation authority changed while it was read",
            )
        return resolved, content


_DEFAULT_PINNED_INPUT_READ = PinnedInputClosure._read
_DEFAULT_PINNED_INPUT_PIN = PinnedInputClosure.pin


def _expected_identity_before_read(value):
    if isinstance(value, ContentIdentity):
        value = value.uri
    # Detach str subclasses without invoking their overridable formatting.
    # Other input types retain the common admission owner's invalid-ID error.
    return str.__str__(value) if isinstance(value, str) else value


def _pinned_read_batch_supported():
    return (
        os.name == "posix"
        and all(
            hasattr(os, name) for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
        )
        and os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )


def _pinned_replaced():
    return PinnedInputClosureError(
        "inputs.closure_replaced", "generation authority changed while it was read"
    )


def _pinned_file_stamp(value):
    if stat.S_ISLNK(value.st_mode):
        raise PinnedInputClosureError(
            "inputs.closure_symlink",
            "generation authority cannot traverse a symbolic link",
        )
    if not stat.S_ISREG(value.st_mode):
        raise PinnedInputClosureError(
            "inputs.closure_not_regular", "generation authority must be a regular file"
        )
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _read_pinned_descriptor(descriptor, maximum):
    parts, remaining = [], maximum + 1
    while remaining:
        content = os.read(descriptor, min(remaining, 64 * 1024))
        if not content:
            break
        parts.append(content)
        remaining -= len(content)
    return b"".join(parts)


@dataclass(frozen=True, slots=True)
class LoadedProject:
    root: Path
    definition: ProjectDefinition
    _snapshot: ProjectConfigurationSnapshot | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )

    @property
    def context(self) -> ProjectContext:
        framework = (
            self.root / self.definition.framework_directory
            if self.definition.framework_directory is not None
            else self.root
        )
        return ProjectContext(self.root, framework)

    @property
    def framework_root(self) -> Path:
        return self.context.framework_root

    def roots(self, catalog: str) -> tuple[Path, ...]:
        try:
            configured = getattr(self.definition, f"{catalog}_roots")
        except AttributeError as exc:
            raise ValueError(f"unknown project catalog: {catalog}") from exc
        return tuple(self.root.joinpath(*Path(item).parts) for item in configured)

    @property
    def agent_skill(self) -> Path:
        return self.root.joinpath(*Path(self.definition.agent_skill).parts)

    def resolve_file(self, base: Path, uri: str, *, label: str) -> Path:
        configured = base / uri
        if configured.is_symlink():
            raise ProjectError(
                "project.reference_symlink",
                f"{label} cannot be a symbolic link",
            )
        try:
            path = configured.resolve(strict=True)
        except OSError as exc:
            raise ProjectError(
                "project.reference_unavailable", f"{label} is unavailable"
            ) from exc
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ProjectError(
                "project.reference_escape",
                f"{label} must be a regular file inside the project root",
            )
        return path

    def flavor_selectors_for(
        self, component: Path, explicit: tuple[str, ...] = ()
    ) -> tuple[str, ...]:
        """Return persisted Component selectors followed by CLI overrides."""

        resolved = component.resolve(strict=True)
        try:
            relative = resolved.relative_to(self.root).as_posix()
        except ValueError as exc:
            raise ProjectError(
                "project.component_outside_root",
                "Component Flavor selectors require a Component inside the project",
            ) from exc
        configured = self.definition.component_flavor_selectors.get(relative, ())
        return (*configured, *explicit)


def load_project(root: Path) -> LoadedProject:
    snapshot = ProjectConfigurationStore(root).read()
    return LoadedProject(snapshot.root, snapshot.definition, _snapshot=snapshot)


def discover_project(start: Path) -> LoadedProject | None:
    snapshot = ProjectConfigurationStore.discover(start)
    if snapshot is None:
        return None
    return LoadedProject(snapshot.root, snapshot.definition, _snapshot=snapshot)


def project_boundary(start: Path, *, legacy: Path) -> Path:
    project = discover_project(start)
    return project.root if project is not None else legacy.resolve(strict=True)


FORWARD_SKILL_ROOT = "skills/specification-to-source"
CONTAINED_SKILL_ROOT = "litai/skills"
CATALOG_PLACEMENT_ROOTS = {
    "skill": "skills",
    "flavor": "flavors",
    "component": "components",
    "workflow": "workflows",
    "routing": "routing",
}
CATALOG_SOURCE_ROOTS = frozenset((*CATALOG_PLACEMENT_ROOTS.values(), "samples"))


def catalog_placement_root(kind: str, coordinate: str) -> str | None:
    if kind == "component" and coordinate.startswith(("samples/", "litai/samples/")):
        return "samples"
    return CATALOG_PLACEMENT_ROOTS.get(kind)


def initialization_coordinate_baseline(
    root: Path,
    *,
    _observation=None,
    _initialization=None,
    _record_ports,
    _record_check,
    _normal,
):
    """Read existing paired coordinate provenance; never issue a live owner."""
    project_path, read_at, parse_bytes, pair, record_error, project_error = (
        _record_ports
    )
    _record_check(_normal)

    if _observation is not None and _initialization is not None:
        raise project_error(
            "project.skill_placement_conflict",
            "one initialization read source required",
        )
    try:
        if _initialization is not None:
            if type(_initialization) is not tuple or len(_initialization) != 2:
                raise ValueError("exact initialization pair required")
            origin, baseline = _initialization
        else:
            names = (
                ".literate/initialization-origin.json",
                ".literate/initialization-baseline.json",
            )
            if _observation is not None:
                payloads = []
                for name in names:
                    _record_check(_normal)
                    payloads.append(_observation.read(name, optional=True))
                _record_check(_normal)
                present = tuple(payload is not None for payload in payloads)
            else:
                _record_check(_normal)
                context = ProjectConfigurationStore.context(root)
                present = []
                for name in names:
                    _record_check(_normal)
                    present.append(project_path(context.framework_root, name).exists())
                _record_check(_normal)
            if not any(present):
                return None
            if not all(present):
                raise ValueError("initialization provenance pair is incomplete")
            if _observation is not None:
                _record_check(_normal)
                origin = parse_bytes(
                    payloads[0], names[0], ProjectInitializationOrigin, _observation
                )
                _record_check(_normal)
                baseline = parse_bytes(
                    payloads[1], names[1], ProjectInitializationBaseline, _observation
                )
            else:
                # Preserve the original independent selection before EACH read,
                # in addition to the original presence-selection above.
                _record_check(_normal)
                origin = read_at(
                    ProjectConfigurationStore.context(root).framework_root,
                    names[0],
                    ProjectInitializationOrigin,
                )
                _record_check(_normal)
                baseline = read_at(
                    ProjectConfigurationStore.context(root).framework_root,
                    names[1],
                    ProjectInitializationBaseline,
                )
        _record_check(_normal)
        return pair(origin, baseline)
    except (record_error, OSError, TypeError, ValueError) as error:
        _record_check(_normal)
        raise project_error(
            "project.skill_placement_conflict",
            "initialized coordinate provenance is unavailable or invalid",
        ) from error


def _bind_initialization_coordinate_baseline(implementation):
    path, read_at, parse, pair, record_guard = _initialization_record_ports()
    namespace, exact, size, some, text, mapping, failure = (
        globals(),
        type,
        len,
        any,
        str,
        vars,
        ValueError,
    )
    error, store = ProjectError, ProjectConfigurationStore
    context = mapping(store)["context"].__func__
    ports = (path, read_at, parse, pair, _InitializedRecordError, error)
    aliases = tuple(
        (
            name,
            name in namespace,
            namespace.get(name, implementation.__builtins__.get(name)),
        )
        for name in (
            "ProjectInitializationOrigin",
            "ProjectInitializationBaseline",
            "ProjectError",
            "_InitializedRecordError",
            "type",
            "tuple",
            "len",
            "any",
            "all",
            "ValueError",
            "OSError",
            "TypeError",
        )
    )
    builtins = implementation.__builtins__
    context_descriptor = mapping(store)["context"]
    error_items = tuple(mapping(error).items())

    def row(function):
        return (
            function,
            function.__code__,
            function.__defaults__,
            function.__kwdefaults__,
            tuple((function.__kwdefaults__ or {}).items()),
        )

    def same(function, code, defaults, keywords, items):
        actual = function.__kwdefaults__
        return (
            function.__code__ is code
            and function.__defaults__ is defaults
            and actual is keywords
            and size(actual or {}) == size(items)
            and not some(exact(key) is not text for key in (actual or {}))
            and not some((actual or {}).get(key) is not value for key, value in items)
        )

    codes = tuple(row(fn) for fn in (implementation, record_guard, error.__init__))
    context_code = row(context)

    def checked(normal):
        if (
            namespace.get("initialization_coordinate_baseline") is not baseline
            or (
                normal
                and (
                    namespace.get("ProjectConfigurationStore") is not store
                    or mapping(store).get("context") is not context_descriptor
                    or not same(*context_code)
                )
            )
            or size(mapping(error)) != size(error_items)
            or some(
                mapping(error).get(name) is not value for name, value in error_items
            )
            or some(not same(*entry) for entry in codes)
            or some(not same(*entry) for entry in boundary_codes)
            or some(
                (name in namespace) != present
                or namespace.get(name, builtins.get(name)) is not value
                for name, present, value in aliases
            )
        ):
            raise failure("original initialization coordinate port changed")
        record_guard()

    def baseline(root: Path, *, _observation=None, _initialization=None):
        normal = _observation is None and _initialization is None
        checked(normal)
        result = implementation(
            root,
            _observation=_observation,
            _initialization=_initialization,
            _record_ports=ports,
            _record_check=checked,
            _normal=normal,
        )
        checked(normal)
        return result

    boundary_codes = tuple(row(fn) for fn in (same, checked, baseline))
    return baseline


initialization_coordinate_baseline = _bind_initialization_coordinate_baseline(
    initialization_coordinate_baseline
)
del _bind_initialization_coordinate_baseline


def contained_catalog_coordinates(root: Path) -> dict[str, str]:
    """Resolve recorded initialized and imported contained catalog coordinates."""
    store = ProjectConfigurationStore(root)
    if store.context(root).framework_root == root:
        return {}
    snapshot = store.read()
    enabled = {
        name
        for kind, primary in CATALOG_PLACEMENT_ROOTS.items()
        for name in ((primary, "samples") if kind == "component" else (primary,))
        if f"litai/{name}" in getattr(snapshot.definition, f"{kind}_roots")
    }
    if not enabled:
        return {}

    from literate_ai.adapters.catalog_import import (
        CatalogImportError,
        read_contained_catalog_imports,
    )

    try:
        imports = read_contained_catalog_imports(snapshot)
    except CatalogImportError as exc:
        raise ProjectError(exc.code, str(exc)) from exc
    imported_paths = (
        {row.path for entry in imports.imports for row in entry.files}
        if imports is not None
        else set()
    )
    mixed = {
        name
        for kind, primary in CATALOG_PLACEMENT_ROOTS.items()
        for name in ((primary, "samples") if kind == "component" else (primary,))
        if name in enabled and name in getattr(snapshot.definition, f"{kind}_roots")
    }
    coordinates = {}
    if mixed:
        # The original migration relocates baseline coordinates through its
        # acknowledged writer. This is a resolver, never permission to move or
        # adopt a neighboring file, nor a replacement for current input checks.
        from literate_ai.adapters.project_updates import (
            ProjectUpdateError,
            _project_path,
        )

        baseline_path = _project_path(
            store.context(root).framework_root, ".literate/initialization-baseline.json"
        )
        if baseline_path.exists():
            baseline = initialization_coordinate_baseline(root)
            if baseline is None:
                raise ProjectError(
                    "project.skill_placement_conflict",
                    "initialized catalog evidence disappeared during coordinate read",
                )
            for item in baseline.files:
                # Initialization may snapshot inherited files. Their current
                # import producer remains the owner, even after an update has
                # changed bytes since the historical initialization snapshot.
                if item.path in imported_paths or not item.path.startswith("litai/"):
                    continue
                logical = item.path.removeprefix("litai/")
                if logical.split("/", 1)[0] not in mixed:
                    continue
                try:
                    original = _project_path(root, logical)
                    require_safe_directory(
                        (root / item.path).parent, allow_missing=True
                    )
                except (ProjectUpdateError, UnsafeFilesystemPathError, OSError) as exc:
                    raise ProjectError(
                        "project.skill_placement_conflict",
                        f"initialized catalog coordinate is redirected: {logical}",
                    ) from exc
                if logical in coordinates or os.path.lexists(original):
                    raise ProjectError(
                        "project.skill_placement_conflict",
                        f"old-root or duplicate initialized catalog file: {logical}",
                    )
                coordinates[logical] = item.path

    if imports is None:
        # A newly authored contained-only catalog is declared directly, without
        # invented parent imports. Mixed old/new imported catalogs still require
        # their original strict provenance mapping.
        if coordinates or all(
            name not in getattr(snapshot.definition, f"{kind}_roots")
            for kind, primary in CATALOG_PLACEMENT_ROOTS.items()
            for name in ((primary, "samples") if kind == "component" else (primary,))
            if name in enabled
        ):
            return coordinates
        raise ProjectError(
            "project.skill_placement_missing",
            "contained Skill import authority is absent",
        )
    for entry in imports.imports:
        touched = {
            catalog_placement_root(entry.kind, row.path)
            for row in entry.files
            if row.path.startswith("litai/")
        }
        if not touched.intersection(enabled):
            continue
        if len(touched) != 1:
            raise ProjectError(
                "project.skill_placement_conflict",
                f"catalog has multiple placement roots: {entry.name}",
            )
        name = next(iter(touched))
        prefix = f"litai/{name}/{entry.name}"
        if any(
            row.path != prefix and not row.path.startswith(prefix + "/")
            for row in entry.files
        ):
            raise ProjectError(
                "project.skill_placement_conflict",
                f"catalog has mixed import ownership: {entry.name}",
            )
        for item in entry.files:
            logical = item.path.removeprefix("litai/")
            if logical in coordinates or os.path.lexists(root / logical):
                raise ProjectError(
                    "project.skill_placement_conflict",
                    f"old-root or duplicate catalog file shadows authority: {logical}",
                )
            coordinates[logical] = item.path
    return coordinates


def configured_catalog_path(boundary: Path, base: Path, uri: str, *, kind: str) -> Path:
    """Resolve an original typed URI through recorded catalog placement."""
    configured = base / uri
    if (
        kind
        not in {
            "specification-to-source-skill",
            "agent-skill",
            "source-to-specification-skill",
            "workflow",
            "routing-policy",
        }
        or Path(uri).is_absolute()
    ):
        return configured
    old = Path(os.path.abspath(configured))
    if not old.is_relative_to(boundary):
        return configured
    relative = old.relative_to(boundary).as_posix()
    if not relative.startswith(("skills/", "litai/skills/", "workflows/", "routing/")):
        return configured
    coordinates = contained_catalog_coordinates(boundary)
    relative_base = (
        base.relative_to(boundary).as_posix() if base.is_relative_to(boundary) else ""
    )
    if (
        relative.startswith("litai/skills/")
        and f"{relative_base}/flavor.md" in coordinates.values()
    ):
        relative = relative.removeprefix("litai/")
        destination = coordinates.get(relative, relative)
    else:
        destination = coordinates.get(relative)
    if destination is None:
        root_name = relative.split("/", 1)[0]
        field = {
            "skills": "skill_roots",
            "workflows": "workflow_roots",
            "routing": "routing_roots",
        }.get(root_name)
        if field is not None:
            store = ProjectConfigurationStore(boundary)
            if store.context(boundary).framework_root == boundary:
                return configured
            snapshot = store.read()
            declared = getattr(snapshot.definition, field)
            if (
                snapshot.definition.framework_directory == "litai"
                and f"litai/{root_name}" in declared
                and root_name not in declared
            ):
                from literate_ai.adapters.retained_layout import (
                    original_source_occupies_coordinate,
                )

                if original_source_occupies_coordinate(boundary, relative):
                    raise ProjectError(
                        "project.skill_placement_conflict",
                        "old-root source shadows an explicitly contained "
                        "catalog reference",
                    )
                destination = f"litai/{relative}"
        if destination is None:
            return configured
    selected = boundary / destination
    try:
        require_safe_directory(selected.parent, allow_missing=True)
    except (UnsafeFilesystemPathError, OSError) as exc:
        raise ProjectError(
            "project.skill_placement_conflict",
            f"contained Skill path is redirected: {destination}",
        ) from exc
    return selected


def configured_component_coordinate(project: LoadedProject, coordinate: str) -> str:
    """Resolve a moved imported Component named by an app-relative CLI argument."""
    path = Path(coordinate)
    if (
        path.is_absolute()
        or ".." in path.parts
        or not path.parts
        or path.parts[0] not in {"components", "samples"}
    ):
        return coordinate
    relative = path if path.name == "component.md" else path / "component.md"
    placement = contained_catalog_coordinates(project.root).get(relative.as_posix())
    if placement is None:
        return coordinate
    return (
        placement if path.name == "component.md" else Path(placement).parent.as_posix()
    )


def project_skill_catalog(project: LoadedProject) -> AgentSkillCatalog:
    """Return the one validated skill-taxonomy authority for a project."""

    roots = project.roots("skill")
    if not roots:
        raise ProjectError("project.skill_invalid", "project declares no skill roots")
    coordinates = {
        old: new
        for old, new in contained_catalog_coordinates(project.root).items()
        if old.startswith("skills/")
    }
    contained_only = (
        project.definition.framework_directory == "litai"
        and "litai/skills" in project.definition.skill_roots
        and "skills" not in project.definition.skill_roots
    )
    contained_agent = (
        project.definition.framework_directory == "litai"
        and project.definition.agent_skill == "litai/SKILL.md"
    )
    if contained_agent:
        coordinates["SKILL.md"] = "litai/SKILL.md"
    try:
        catalog = AgentSkillCatalog.discover(
            project.root,
            catalog_roots=roots,
            root_manifests=(project.agent_skill,),
            validate_dependencies=True,
            validate_references=True,
            reference_coordinates=coordinates,
            **(
                {"reference_root_coordinates": {"skills": "litai/skills"}}
                if contained_only
                else {}
            ),
        )
        if contained_only or contained_agent:
            from literate_ai.adapters.retained_layout import (
                original_source_occupies_coordinate,
            )

            for skill in catalog.skills:
                for logical in skill.owned_paths:
                    if not (
                        contained_only
                        and logical.parts[0] == "skills"
                        or str(logical) == "SKILL.md"
                        and coordinates.get("SKILL.md") == "litai/SKILL.md"
                    ):
                        continue
                    if original_source_occupies_coordinate(project.root, str(logical)):
                        raise ProjectError(
                            "project.skill_placement_conflict",
                            "old-root file shadows contained skill authority",
                        )
        return catalog
    except AgentSkillCatalogError as exc:
        raise ProjectError(exc.code, exc.message) from exc


def _skill_manifest_paths(
    project: LoadedProject,
    direction: str,
    *,
    validate_catalog: bool = True,
) -> tuple[Path, ...]:
    """Return manifests admitted beneath one declared skill-catalog direction."""

    roots = project.roots("skill")
    if not roots:
        return ()
    prefixes = tuple((root / direction).resolve() for root in roots)
    if validate_catalog:
        manifests = tuple(
            skill.manifest_path
            for skill in project_skill_catalog(project).skills
            if skill.manifest_path is not None
        )
    else:
        try:
            manifests = AgentSkillCatalog.discover_manifest_paths(
                project.root,
                catalog_roots=roots,
                root_manifests=(project.agent_skill,),
            )
        except AgentSkillCatalogError as exc:
            code = (
                "project.skill_ambiguous"
                if exc.code == "agent_skill.authority_ambiguous"
                else "project.skill_invalid"
            )
            raise ProjectError(code, exc.message) from exc
    return tuple(
        sorted(
            manifest
            for manifest in manifests
            if any(manifest.is_relative_to(prefix) for prefix in prefixes)
        )
    )


def specification_to_source_skill_paths(
    project: LoadedProject, *, validate_catalog: bool = True
) -> tuple[Path, ...]:
    """Return exact files admitted by declared forward-generation skill roots."""

    return _skill_manifest_paths(
        project,
        "specification-to-source",
        validate_catalog=validate_catalog,
    )


def source_to_specification_skill_paths(
    project: LoadedProject, *, validate_catalog: bool = True
) -> tuple[Path, ...]:
    """Return exact files admitted by declared inverse-authoring skill roots."""

    return _skill_manifest_paths(
        project,
        "source-to-specification",
        validate_catalog=validate_catalog,
    )


def documentation_files(project: LoadedProject) -> tuple[Path, ...]:
    """Return every bounded regular file admitted by documentation roots."""

    configured_roots = project.roots("documentation")
    resolved_roots: list[Path] = []
    for configured_root in configured_roots:
        current = project.root
        try:
            relative_root = configured_root.relative_to(project.root)
        except ValueError as exc:
            raise ProjectError(
                "project.documentation_invalid",
                "declared documentation root escapes the project root",
            ) from exc
        for part in relative_root.parts:
            current /= part
            if current.is_symlink():
                raise ProjectError(
                    "project.documentation_invalid",
                    "declared documentation roots cannot traverse symbolic links",
                )
        if not configured_root.is_dir():
            raise ProjectError(
                "project.documentation_invalid",
                "declared documentation roots must be regular directories",
            )
        root = configured_root.resolve(strict=True)
        if not root.is_relative_to(project.root):
            raise ProjectError(
                "project.documentation_invalid",
                "declared documentation root escapes the project root",
            )
        if any(
            root == previous
            or root.is_relative_to(previous)
            or previous.is_relative_to(root)
            for previous in resolved_roots
        ):
            raise ProjectError(
                "project.documentation_invalid",
                "declared documentation roots cannot overlap",
            )
        resolved_roots.append(root)

    paths: set[Path] = set()
    entries = 0
    total_bytes = 0
    for configured_root, root in zip(configured_roots, resolved_roots, strict=True):
        for configured in configured_root.rglob("*"):
            entries += 1
            if entries > DEFAULT_MAXIMUM_DOCUMENTATION_ENTRIES:
                raise ProjectError(
                    "project.documentation_limit",
                    "declared documentation contains too many filesystem entries",
                )
            if configured.is_symlink():
                raise ProjectError(
                    "project.documentation_invalid",
                    "declared documentation cannot contain symbolic links",
                )
            relative = configured.relative_to(configured_root)
            if (
                len(relative.as_posix().encode("utf-8"))
                > DEFAULT_MAXIMUM_DOCUMENTATION_PATH_BYTES
                or len(relative.parts) > DEFAULT_MAXIMUM_DOCUMENTATION_DEPTH
            ):
                raise ProjectError(
                    "project.documentation_limit",
                    "declared documentation path exceeds portable limits",
                )
            if configured.is_dir():
                continue
            if not configured.is_file():
                raise ProjectError(
                    "project.documentation_invalid",
                    "declared documentation entries must be regular files",
                )
            resolved = configured.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_relative_to(
                project.root
            ):
                raise ProjectError(
                    "project.documentation_invalid",
                    "declared documentation file escapes its documentation root",
                )
            if is_python_bytecode_cache_path(
                resolved.relative_to(project.root).as_posix()
            ):
                continue
            size = resolved.stat().st_size
            if size > DEFAULT_MAXIMUM_DOCUMENTATION_FILE_BYTES:
                raise ProjectError(
                    "project.documentation_limit",
                    "declared documentation file exceeds the per-file byte limit",
                )
            total_bytes += size
            if total_bytes > DEFAULT_MAXIMUM_DOCUMENTATION_TOTAL_BYTES:
                raise ProjectError(
                    "project.documentation_limit",
                    "declared documentation exceeds the total byte limit",
                )
            paths.add(resolved)
            if len(paths) > DEFAULT_MAXIMUM_DOCUMENTATION_FILES:
                raise ProjectError(
                    "project.documentation_limit",
                    "declared documentation contains too many files",
                )
    return tuple(sorted(paths))


def documentation_paths(project: LoadedProject) -> tuple[Path, ...]:
    """Return Markdown documents admitted by declared documentation roots."""

    return tuple(
        path for path in documentation_files(project) if path.suffix.casefold() == ".md"
    )


def documentation_asset_paths(project: LoadedProject) -> tuple[Path, ...]:
    """Return non-Markdown assets admitted by declared documentation roots."""

    return tuple(
        path for path in documentation_files(project) if path.suffix.casefold() != ".md"
    )


def _require_disjoint_source_cache_roots(
    project: LoadedProject, authority_paths: dict[str, Path]
) -> None:
    """Keep a committable cache away from every authority, onboarding, and receipt path.

    A project-relative source-cache root may be tracked in Git, which is the point. It
    must never sit on top of a declared catalog, the onboarding skill, or the test
    receipt: derived source landing inside an authority root would be read as authority
    on the next scan, and a cache write could silently overwrite a specification. The
    contract has always stated this constraint; nothing enforced it.
    """

    configuration = project.definition.source_cache
    if configuration is None:
        return
    protected = dict(authority_paths)
    receipt = project.definition.test_receipt
    if receipt:
        protected["test_receipt"] = project.root.joinpath(*Path(receipt).parts)
    for target in configuration.targets:
        if target.root_kind is not SourceCacheRootKind.PROJECT_RELATIVE:
            continue
        root = project.root.joinpath(*Path(target.root_reference).parts)
        if root == project.root:
            raise ProjectError(
                "project.source_cache_overlaps_authority",
                f"source-cache target {target.target_id!r} names the project root",
            )
        for label, path in protected.items():
            if root == path or root.is_relative_to(path) or path.is_relative_to(root):
                raise ProjectError(
                    "project.source_cache_overlaps_authority",
                    f"source-cache target {target.target_id!r} overlaps {label}; a "
                    "committable cache must not sit on an authority path",
                )


def project_owns_agent_shim(definition: ProjectDefinition, relative: str) -> bool:
    """Optional provider shims inside independent children are not root authority."""
    if (
        definition.agent_entrypoints is not None
        and relative not in definition.agent_entrypoints
    ):
        return False
    binding = definition.repository_orchestration
    if binding is None:
        return True
    path = relative.casefold()
    return not any(
        path == pin.path.casefold() or path.startswith(pin.path.casefold() + "/")
        for pin in binding.repositories
    )


def validate_project_structure(project: LoadedProject) -> dict[str, object]:
    if project.definition.profile != CANONICAL_PROJECT_PROFILE:
        raise ProjectError(
            "project.profile_unsupported",
            f"unsupported project profile: {project.definition.profile}",
        )
    source_intelligence = project.definition.source_intelligence
    paths = {"agent_skill": project.agent_skill}
    for catalog in (
        "component",
        "flavor",
        "skill",
        "mcp",
        "workflow",
        "routing",
        "documentation",
    ):
        for index, path in enumerate(project.roots(catalog)):
            paths[f"{catalog}_roots[{index}]"] = path
    for label, path in paths.items():
        expected = path.is_file() if label == "agent_skill" else path.is_dir()
        if path.is_symlink() or not expected:
            raise ProjectError(
                "project.layout_incomplete",
                f"declared project path is unavailable: {label}",
            )
        if not path.resolve(strict=True).is_relative_to(project.root):
            raise ProjectError(
                "project.layout_escape",
                f"declared project path escapes the project root: {label}",
            )
    _require_disjoint_source_cache_roots(project, paths)
    for relative, marker in CANONICAL_AGENT_SHIMS.items():
        if marker == "SKILL.md":
            marker = project.definition.agent_skill
        if not project_owns_agent_shim(project.definition, relative):
            continue
        path = project.root.joinpath(*Path(relative).parts)
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file():
            raise ProjectError(
                "project.agent_shim_invalid",
                f"optional agent shim must be a regular file: {relative}",
            )
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(project.root):
            raise ProjectError(
                "project.agent_shim_invalid",
                f"optional agent shim escapes the project root: {relative}",
            )
        try:
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ProjectError(
                "project.agent_shim_invalid",
                f"optional agent shim is unreadable: {relative}",
            ) from exc
        if marker not in content:
            raise ProjectError(
                "project.agent_shim_invalid",
                "optional agent shim does not delegate to the provider-neutral "
                f"onboarding skill: {relative}",
            )
    return {
        "project_identity": project.definition.identity.uri,
        "project_id": project.definition.project_id,
        "profile": project.definition.profile,
        "agent_skill": project.definition.agent_skill,
        "source_intelligence": {
            "state": "configured",
            "policy": source_intelligence.to_dict(),
        },
        "default_flavor_selectors": list(project.definition.default_flavor_selectors),
        "catalogs": {
            catalog: [
                path.relative_to(project.root).as_posix()
                for path in project.roots(catalog)
            ]
            for catalog in (
                "component",
                "flavor",
                "skill",
                "workflow",
                "routing",
                "documentation",
            )
        },
    }


__all__ = [
    "CANONICAL_AGENT_SHIMS",
    "DEFAULT_MAXIMUM_PINNED_INPUT_BYTES",
    "DEFAULT_MAXIMUM_PINNED_INPUT_FILES",
    "DEFAULT_MAXIMUM_PINNED_INPUT_TOTAL_BYTES",
    "LoadedProject",
    "PROJECT_FILENAME",
    "PinnedInputClosure",
    "PinnedInputClosureError",
    "ProjectError",
    "discover_project",
    "documentation_asset_paths",
    "documentation_files",
    "documentation_paths",
    "load_project",
    "project_boundary",
    "source_to_specification_skill_paths",
    "specification_to_source_skill_paths",
    "validate_project_structure",
]
