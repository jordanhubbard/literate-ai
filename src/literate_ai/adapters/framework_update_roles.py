"""One live, bounded framework update; saved checkpoint rows grant no roles.

This internal development context applies a fresh ordinary update under its
canonical mutex, then yields read-only provenance after releasing that mutex.
Failure to close provenance after application preserves the completed update.
"""

from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from literate_ai.application.agent_skill_catalog import AgentSkillCatalog
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import (
    PROJECT_FILENAME,
    LoadedProject,
    parse_project_configuration,
)

from .lifecycle_lock import project_lifecycle_lock
from .repository_refresh import RefreshFileObservation, _file, _signature
from .retained_cargo_tree_v2 import _node, capture_retained_cargo_tree_v2
from .retained_layout_partition import _lineage
from .update_merge import CHECKPOINT, UpdateBases, digest, safe_path

_KEY = object()


class FrameworkUpdateRoleError(RuntimeError):
    """No handoff was issued; application may already have completed."""


def _fail(message):
    raise FrameworkUpdateRoleError("layout.update-roles: " + message)


def _node_receipt(signature):
    return signature


def _native_facts(node):
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
        node.st_nlink,
        node.st_uid,
        node.st_gid,
    )


class _FrameworkUpdateRoles:
    def __init__(self, key, root, budget, metadata):
        if key is not _KEY:
            raise TypeError("actual framework update context required")
        if type(budget) is not RetainedCargoInputBudget:
            _fail("explicit input budget required")
        if type(metadata) is not int or not 64 * 1024**2 <= metadata <= 16 * 1024**3:
            _fail("explicit metadata budget required")
        self._root, self._budget, self._metadata = root, budget, metadata
        self._pid, self._active, self._spent, self._ready = (
            os.getpid(),
            True,
            False,
            False,
        )
        self._cache, self._lineages = {}, {}
        self._writing = False
        self._retirement_directory = None
        self._retirement_known = set()
        self._retirement_sequence = 0
        self._json_documents = set()
        self._total, self._records, self._charged = 0, 0, budget.maximum_file_bytes * 64
        # Reserve a complete reread buffer before retaining any observations.
        self._reserve = budget.maximum_file_bytes
        initial_total = budget.maximum_total_bytes - self._reserve
        if initial_total < 1:
            _fail("initial namespace leaves no reread reserve")
        initial_limit = min(budget.maximum_file_bytes, initial_total)
        initial_budget = RetainedCargoInputBudget(
            budget.maximum_files,
            budget.maximum_entries,
            initial_limit,
            min(initial_total, budget.maximum_files * initial_limit),
        )
        self._tree = capture_retained_cargo_tree_v2(
            root, budget=initial_budget, maximum_metadata_bytes=metadata // 4
        )
        self._total = self._tree.payload_bytes
        self._records = self._tree.entry_count
        self._initial_files = self._tree.file_count
        self._charged += metadata // 2
        self._namespace = dict(self._tree._physical[1])
        self._initial = {name: blob for name, blob, _ in self._tree.files}
        for alias in self._tree.aliases:
            if alias.kind == "hardlink":
                self._initial[alias.path] = self._initial[alias.target]
        self._names = set(self._initial) | {a.path for a in self._tree.aliases}
        self._charged += 4096 * (1 + self._tree.entry_count)
        self._root_lineage = _lineage(root)
        self._paths = ()
        self._removed = ()
        self._nonce = os.urandom(16).hex()
        self._identity = None
        self._plan = None
        self._applied = None

    @property
    def root(self):
        return self._root

    @property
    def budget(self):
        return self._budget

    @property
    def metadata(self):
        return self._metadata

    @property
    def _used_bytes(self):
        provider = getattr(self, "_git", None)
        return self._total + (provider.total if provider else 0)

    @property
    def _used_entries(self):
        provider = getattr(self, "_git", None)
        return self._records + len(self._cache) + (provider.entries if provider else 0)

    @property
    def _used_metadata(self):
        provider = getattr(self, "_git", None)
        return self._charged + (provider.charged if provider else 0)

    @property
    def _used_files(self):
        provider = getattr(self, "_git", None)
        return (
            self._initial_files
            + len(self._cache)
            + (provider.file_count if provider else 0)
        )

    def _live(self, *, ready=False):
        if not self._active or self._spent or self._pid != os.getpid():
            _fail("handoff ended or was spent")
        if ready and not self._ready:
            _fail("actual successful update required")

    def _write_live(self):
        self._live()
        if not self._writing or self._ready:
            _fail("actual updater write scope required")

    def _prepare_retirement(self, directory, descriptor, guard):
        self._write_live()
        if (
            not directory.is_absolute()
            or ".." in directory.parts
            or directory.is_relative_to(self.root)
            or self.root.is_relative_to(directory)
        ):
            _fail("explicit private retirement directory must be outside the project")
        node = directory.lstat()
        if (
            node.st_uid != os.geteuid()
            or stat.S_IMODE(node.st_mode) != 0o700
            or node.st_dev != self.root.stat().st_dev
        ):
            _fail(
                "private retirement directory must be owned, mode0700 "
                "and on the project filesystem"
            )
        lineage = _lineage(directory)
        project_nodes = {self._tree._physical[0][:2]} | {
            n[:2] for _name, n in self._tree._physical[1]
        }
        if project_nodes & {n[1:3] for n in lineage}:
            _fail("private retirement directory physically overlaps the project")
        before = _native_facts(node)
        with os.scandir(directory) as entries:
            if next(entries, None) is not None:
                _fail("private retirement directory must be empty")
        if _native_facts(directory.lstat()) != before:
            _fail("private retirement directory changed")
        self._retirement_directory = directory
        self._retirement_descriptor, self._retirement_guard = descriptor, guard
        self._retirement_lineage, self._retirement_facts = lineage, before
        self._records += 1
        self._charged += 4096 + 64 * len(str(directory).encode())
        self._retirement_record(
            "owner.json",
            {
                "schema": "literate-ai/framework-update-private-area@1",
                "nonce": self._nonce,
                "project": str(self.root),
                "original_namespace": self._tree.identity.uri,
            },
        )
        from .retained_layout_control_publication import _pinned_directory

        with _pinned_directory(directory.parent) as (parent, parent_guard):
            os.fsync(parent)
            parent_guard()

    def _close_retirement(self):
        if self._retirement_directory is None:
            return
        self._retirement_guard()
        if (
            _lineage(self._retirement_directory) != self._retirement_lineage
            or _native_facts(self._retirement_directory.lstat())
            != self._retirement_facts
            or _native_facts(os.fstat(self._retirement_descriptor))
            != self._retirement_facts
        ):
            _fail("original private retirement area changed")

    def _seal_retirement(self):
        directory = self._retirement_directory
        before = _native_facts(directory.lstat())
        observed = set()
        with os.scandir(directory) as entries:
            for entry in entries:
                if len(observed) >= self.budget.maximum_entries:
                    _fail("private retirement inventory exceeds entry budget")
                observed.add(entry.name)
                expected = self._cache.get(directory / entry.name)
                if (
                    expected is None
                    or _signature(directory / entry.name) != expected.signature
                ):
                    _fail(
                        "private retirement inventory contains foreign or changed nodes"
                    )
        if observed != self._retirement_known:
            _fail("private retirement membership changed")
        if _native_facts(directory.lstat()) != before:
            _fail("private retirement directory changed during inventory")
        self._retirement_facts = before
        self._close_retirement()

    def _retirement_record(self, name, value):
        from literate_ai.contracts.identity import canonical_json_bytes

        self._write_live()
        self._close_retirement()
        content = canonical_json_bytes(value)
        cost = 4096 + 64 * (
            len(str(self._retirement_directory / name).encode()) + len(content)
        )
        if (
            len(content) > self.budget.maximum_file_bytes
            or len(content)
            > self.budget.maximum_total_bytes - self._used_bytes - self._reserve
            or cost > self.metadata - self._used_metadata
            or self._used_files >= self.budget.maximum_files
            or self._used_entries >= self.budget.maximum_entries
        ):
            _fail("retirement intent exceeds shared budget")
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=self._retirement_descriptor,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(content)
                stream.flush()
                prepared = _native_facts(os.fstat(descriptor))
                os.fsync(descriptor)
                if _native_facts(os.fstat(descriptor)) != prepared:
                    _fail("private retirement intent changed during fsync")
            os.fsync(self._retirement_descriptor)
            receipt = (
                prepared[0],
                prepared[1],
                prepared[2],
                prepared[3],
                prepared[4],
                prepared[5],
            )
            path = self._retirement_directory / name
            self._accept_observation(path, content, receipt)
            self._retirement_known.add(name)
            self._seal_retirement()
        finally:
            os.close(descriptor)
        self._write_live()

    def retire(self, path):
        from .exclusive_entry import layout_entry_node, move_layout_entry_exclusive
        from .repository_refresh_reservations import _custody_wire
        from .retained_layout_control_publication import _pinned_directory

        self._write_live()
        if self._retirement_directory is None:
            _fail("actual private retirement owner required")
        original = self._cache[path]
        source = layout_entry_node(path)
        if (
            source.device,
            source.inode,
            source.mode,
            source.size,
            source.modified_ns,
            source.changed_ns,
        ) != original.signature:
            _fail("original retirement source changed")
        self._retirement_sequence += 1
        destination = (
            self._retirement_directory / f"node-{self._retirement_sequence:06d}"
        )
        source_parent = layout_entry_node(path.parent)
        destination_parent = layout_entry_node(self._retirement_directory)
        self._retirement_record(
            f"intent-{self._retirement_sequence:06d}.json",
            {
                "schema": "literate-ai/framework-update-retirement-intent@1",
                "nonce": self._nonce,
                "plan": self._plan.identity.uri,
                "source": str(path),
                "destination": str(destination),
                "source_node": _custody_wire(source),
                "source_parent": _custody_wire(source_parent),
                "destination_parent": _custody_wire(destination_parent),
            },
        )
        cost = 4096 + 64 * (len(str(destination).encode()) + len(original.content))
        if (
            len(original.content)
            > self.budget.maximum_total_bytes - self._used_bytes - self._reserve
            or cost > self.metadata - self._used_metadata
            or self._used_files >= self.budget.maximum_files
            or self._used_entries >= self.budget.maximum_entries
        ):
            _fail("retirement observation exceeds remaining shared budget")
        with _pinned_directory(path.parent) as (_descriptor, guard):
            self.before_replace(path)
            guard()
            self._close_retirement()
            self._write_live()
            move_layout_entry_exclusive(
                path,
                destination,
                expected_source=source,
                expected_source_parent=source_parent,
                expected_destination_parent=destination_parent,
                maximum_directory_entries=self.budget.maximum_entries,
            )
            actual = layout_entry_node(destination)
            if actual.after_rename() != source.after_rename():
                _fail("retired node differs from the actual original source")
            receipt = (
                actual.device,
                actual.inode,
                actual.mode,
                actual.size,
                actual.modified_ns,
                actual.changed_ns,
            )
            self._accept_observation(destination, original.content, receipt)
            self._retirement_known.add(destination.name)
            os.fsync(self._retirement_descriptor)
            os.fsync(_descriptor)
            self._seal_retirement()
            guard()
        self._write_live()

    def _anchor(self, path):
        parent = path.parent
        while not parent.exists():
            parent = parent.parent
        return parent, _lineage(parent)

    def _observe(self, path, *, optional=False):
        anchor = self._anchor(path)
        cost = 4096 + 64 * len(str(path).encode())
        remaining = min(
            self.budget.maximum_file_bytes,
            self.budget.maximum_total_bytes - self._reserve - self._used_bytes,
            (self.metadata - self._used_metadata - cost) // 64,
        )
        if (
            self._used_files >= self.budget.maximum_files
            or self._used_entries >= self.budget.maximum_entries
            or remaining < 1
        ):
            _fail("observation exceeds shared input budget")
        if not path.parent.exists() and optional:
            item = RefreshFileObservation(path, None, None)
        else:
            item = _file(path, optional=optional, maximum_bytes=remaining)
        self._total += len(item.content or b"")
        self._charged += cost + 64 * len(item.content or b"")
        return item, anchor

    def _snapshot(self, path, *, optional=False, initial=True):
        self._live()
        if path in self._cache:
            item = self._cache[path]
            self._check(item)
            return item.content
        item, ancestry = self._observe(path, optional=optional)
        if initial and path.is_relative_to(self.root):
            original = self._initial.get(path.relative_to(self.root).as_posix())
            if (
                original is None
                and item.content is not None
                or original is not None
                and (item.content is None or digest(item.content) != original.identity)
            ):
                _fail("planning input changed after bounded namespace capture")
        self._cache[path], self._lineages[path] = item, ancestry
        return item.content

    def _check(self, item):
        self._close_file(item)
        if item.content is not None:
            observed = _file(item.path, maximum_bytes=self.budget.maximum_file_bytes)
            if observed != item:
                _fail("original update input changed")
        self._close_file(item)

    def _close_file(self, item):
        anchor, expected = self._lineages[item.path]
        if _lineage(anchor) != expected:
            _fail("update input ancestry changed")
        try:
            actual = _signature(item.path)
        except FileNotFoundError:
            actual = None
        if actual != item.signature:
            _fail("update input native facts changed")

    def read(self, relative, *, optional=False):
        return self._snapshot(safe_path(self.root, relative), optional=optional)

    def project(self, selected):
        if selected != self.root:
            _fail("planning must select the exact observed project")
        content = self.read(PROJECT_FILENAME)
        self.json_value(content, PROJECT_FILENAME)
        return LoadedProject(self.root, parse_project_configuration(content))

    def json_value(self, content, label):
        value = json.loads(content)
        key = label, digest(content)
        if key in self._json_documents:
            return value
        count = 0
        stack = [iter((value,))]
        while stack:
            try:
                item = next(stack[-1])
            except StopIteration:
                stack.pop()
                continue
            count += 1 + (len(item) if isinstance(item, dict) else 0)
            if (
                count + self._used_entries > self.budget.maximum_entries
                or 4096 * count > self.metadata - self._used_metadata
                or len(stack) > 128
            ):
                _fail("decoded metadata exceeds shared entry budget")
            if isinstance(item, dict):
                stack.append(iter(item.values()))
            elif isinstance(item, list):
                stack.append(iter(item))
        self._records += count
        self._charged += 4096 * count
        self._json_documents.add(key)
        return value

    def bases(self):
        content = self.read(CHECKPOINT, optional=True)
        if content is not None:
            self.json_value(content, CHECKPOINT)
        reserved = getattr(self, "_base_records", 0)
        limit = min(
            self.budget.maximum_entries - self._used_entries + reserved,
            (self.metadata - self._used_metadata) // 4096 + reserved,
        )
        bases = UpdateBases.from_observed(
            self.root, content, maximum_entries=max(0, limit)
        )
        if not hasattr(self, "_base_records"):
            self._records += bases.entry_count
            self._charged += 4096 * bases.entry_count
            self._base_records = bases.entry_count
        return bases

    def paths_beneath(self, directory):
        prefix = directory.relative_to(self.root).as_posix()
        return tuple(
            self.root / name
            for name in sorted(self._names)
            if name == prefix or name.startswith(prefix + "/")
        )

    def component_paths(self, directory):
        return tuple(
            p for p in self.paths_beneath(directory) if p.name == "component.md"
        )

    def skill_sources(self, project):
        documents = {}
        directories = {".", *self._tree.directories}
        for directory in project.roots("skill"):
            if directory.relative_to(self.root).as_posix() not in directories:
                _fail("skill catalog root is unavailable")
            for path in self.paths_beneath(directory):
                name = path.relative_to(self.root).as_posix()
                documents[PurePosixPath(name)] = self.read(name)
        name = project.agent_skill.relative_to(self.root).as_posix()
        documents[PurePosixPath(name)] = self.read(name)
        return {
            str(path): documents[path]
            for path in AgentSkillCatalog.manifest_paths_from_documents(documents)
        }

    def template_text(self, relative):
        directory = self._resource_directory()
        path = safe_path(directory, relative)
        return (
            self._snapshot(path, initial=False)
            .decode("utf-8")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )

    def _resource_directory(self):
        from importlib.resources import files

        directory = files("literate_ai.project_template")
        if (
            not isinstance(directory, Path)
            or directory != self._provider_checkout / "src/literate_ai/project_template"
        ):
            _fail("actual physical source resources required")
        return directory

    def _provider(self):
        import sys

        from literate_ai.application import agent_skill_catalog

        from . import (
            project_initialization,
            project_update_apply,
            project_update_compatibility,
            project_updates,
            retained_layout,
            update_merge,
        )

        modules = (
            project_initialization,
            project_updates,
            project_update_apply,
            project_update_compatibility,
            retained_layout,
            update_merge,
            agent_skill_catalog,
            sys.modules[__name__],
        )
        for module in modules:
            self._snapshot(Path(module.__file__), initial=False)
        self._provider_origin = self.current_origin()
        self._registry = self._registry_value()
        maps = (
            project_updates._TEMPLATE_FILES,
            project_updates._STARTER_TEMPLATE_FILES,
            project_initialization._STARTER_DOCS,
        )
        size = sum(
            12 * (len(name) + len(value))
            for mapping in maps
            for name, value in mapping.items()
        )
        size += 12 * len(str(self._resource_directory()))
        entries = sum(map(len, maps))
        if (
            size > self.budget.maximum_total_bytes - self._total - self._reserve
            or self._records + len(self._cache) + entries > self.budget.maximum_entries
            or 64 * size + entries * 4096 > self.metadata - self._charged
        ):
            _fail("producer registry exceeds remaining shared budget")
        self._total += size
        self._records += entries
        self._charged += 64 * size + entries * 4096
        from .retained_layout_provider import _Objects

        allowance, metadata = self.remaining(self.budget, self.metadata)
        self._git = _Objects(
            self._provider_checkout, self._provider_origin, allowance, metadata
        )
        self._bind_current_refs()

    def _bind_current_refs(self):
        git_directory, common, _objects = self._git.git_paths
        head = self._snapshot(git_directory / "HEAD", initial=False)
        self._snapshot(common / "packed-refs", optional=True, initial=False)
        pending, visited = [head], set()
        while pending:
            raw = pending.pop()
            if not raw or not raw.startswith(b"ref: "):
                continue
            relative = raw[5:].decode("utf-8").strip()
            if relative in visited:
                _fail("current provider symbolic refs are cyclic")
            if len(visited) >= 32:
                _fail("current provider symbolic refs exceed their bound")
            visited.add(relative)
            for directory in dict.fromkeys((git_directory, common)):
                path = safe_path(directory, relative)
                value = self._snapshot(path, optional=True, initial=False)
                if value is not None:
                    pending.append(value)

    def current_origin(self):
        self._live()
        from literate_ai.contracts import ProjectInitializationOrigin

        from . import project_initialization, project_updates
        from .builders import run_bounded_process

        if getattr(self, "_git", None) is not None:
            self._git.close_native()
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }
        environment.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_SYSTEM=os.devnull,
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            GIT_OPTIONAL_LOCKS="0",
            GIT_NO_LAZY_FETCH="1",
        )
        directory = Path(project_updates.__file__).parent
        module = Path(project_updates.__file__)
        if (
            len(module.parents) < 4
            or module
            != module.parents[3] / "src/literate_ai/adapters/project_updates.py"
        ):
            _fail(
                "actual physical source provider required; "
                "packaged provider is unsupported"
            )
        source_root = module.parents[3]

        def git(*args, optional=False):
            result = run_bounded_process(
                ("git", "--no-pager", "-c", "core.fsmonitor=false", *args),
                cwd=directory,
                environment=environment,
                timeout_seconds=10,
                stdout_limit_bytes=min(16384, self.budget.maximum_file_bytes),
                stderr_limit_bytes=4096,
                error_prefix="layout.update-origin",
            )
            if optional and result.returncode == 1:
                return None
            if result.returncode:
                _fail("bounded source provider origin is unavailable")
            return result.stdout.decode("utf-8").strip()

        checkout = Path(git("rev-parse", "--show-toplevel"))
        if not checkout.is_absolute() or checkout != source_root:
            _fail("actual source provider checkout is redirected")
        if hasattr(self, "_provider_checkout") and self._provider_checkout != checkout:
            _fail("actual source provider checkout changed")
        self._provider_checkout = checkout
        reference_format = git(
            "config", "--local", "--get", "extensions.refStorage", optional=True
        )
        if reference_format not in (None, "files"):
            _fail("current provider requires observed file-based Git refs")
        origin = ProjectInitializationOrigin(
            repository_url=git(
                "config", "--local", "--no-includes", "--get", "remote.origin.url"
            ),
            git_revision=git("rev-parse", "--verify", "HEAD^{commit}"),
            distribution_name="literate-ai",
            distribution_version=project_initialization.DISTRIBUTION_VERSION,
        )
        if getattr(self, "_git", None) is not None:
            self._git.close_native()
        self._live()
        return origin

    def _registry_value(self):
        from . import project_initialization as initialization
        from . import project_updates as updates

        maps = (
            updates._TEMPLATE_FILES,
            updates._STARTER_TEMPLATE_FILES,
            initialization._STARTER_DOCS,
        )
        if sum(map(len, maps)) > self.budget.maximum_entries:
            _fail("actual producer registry exceeds entry budget")
        for mapping in maps:
            for name, value in mapping.items():
                if (
                    not isinstance(name, str)
                    or not isinstance(value, str)
                    or max(len(name), len(value)) * 4 > self.budget.maximum_file_bytes
                ):
                    _fail("actual producer registry exceeds file budget")
        size = sum(
            12 * (len(name) + len(value))
            for mapping in maps
            for name, value in mapping.items()
        )
        directory = self._resource_directory()
        size += 12 * len(str(directory))
        if (
            size > self.budget.maximum_file_bytes
            or size * 64 > self.metadata - self._used_metadata
        ):
            _fail("actual producer registry exceeds aggregate budget")
        return canonical_identity(
            {
                "templates": dict(updates._TEMPLATE_FILES),
                "starter_templates": dict(updates._STARTER_TEMPLATE_FILES),
                "documents": dict(initialization._STARTER_DOCS),
                "resource_directory": str(directory),
            }
        )

    def _before_apply(self, plan, root):
        self._write_live()
        if root != self.root or plan is not self._plan or self._ready:
            _fail("actual fresh operation plan required")
        if 3 * len(plan.files) + self._used_entries > self.budget.maximum_entries:
            _fail("update plan exceeds shared entry budget")
        self._records += 3 * len(plan.files)
        self._charged += 3 * len(plan.files) * 4096
        if self._used_metadata > self.metadata:
            _fail("update plan exceeds metadata budget")
        self._tree.require_unchanged()
        for item in self._cache.values():
            self._check(item)

    def before_writes(self, items):
        self._write_live()
        from .exclusive_entry import layout_entry_node

        for item in items:
            observed = self._cache[self.root / item.path]
            self._close_file(observed)
            if (
                observed.signature is not None
                and layout_entry_node(observed.path).links != 1
            ):
                _fail(
                    "framework alias-group mutations require "
                    "their complete ownership join"
                )
        self._write_live()

    def _accept(self, path, content, receipt):
        # Accept only exact bytes and the inode actually published by the updater.
        self._accept_observation(path, content, receipt)
        relative = path.relative_to(self.root).as_posix()
        if content is None:
            self._namespace.pop(relative, None)
        else:
            self._namespace[relative] = _node(path.lstat())
        parent = path.parent
        while parent != self.root:
            name = parent.relative_to(self.root).as_posix()
            if name not in self._namespace:
                self._namespace[name] = _node(parent.lstat())
            parent = parent.parent

    def _accept_observation(self, path, content, receipt):
        item, ancestry = self._observe(path, optional=content is None)
        if item.content != content or _node_receipt(item.signature) != receipt:
            _fail("published update node changed before handoff")
        self._cache[path], self._lineages[path] = item, ancestry

    def before_replace(self, target, temporary=None, prepared=None):
        self._write_live()
        self._close_namespace(
            target=target, temporary=temporary, prepared=prepared, close_inputs=True
        )
        self._write_live()

    def after_publication(self, path, content, receipt):
        self._write_live()
        self._accept(path, content, receipt)
        self._write_live()

    def _close_namespace(
        self, *, target=None, temporary=None, prepared=None, close_inputs=False
    ):
        from .retained_project_inputs import _directory_access, _inventory

        expected = dict(self._namespace)
        if temporary is not None:
            expected[temporary.relative_to(self.root).as_posix()] = _node(prepared)
        if target is not None:
            parent = target.parent
            while parent != self.root:
                name = parent.relative_to(self.root).as_posix()
                if name not in expected:
                    actual = parent.lstat()
                    if not stat.S_ISDIR(actual.st_mode):
                        _fail("publication parent is redirected")
                    expected[name] = _node(actual)
                parent = parent.parent
        observed, complete = {}, {}
        root_facts = _native_facts(self.root.lstat())

        def observe(name, node):
            observed[name] = _node(node)
            complete[name] = _native_facts(node)

        with _directory_access(self.root) as access:
            roots = []
            with os.scandir(self.root) as entries:
                for entry in entries:
                    if len(roots) >= self.budget.maximum_entries:
                        _fail("publication namespace exceeds entry budget")
                    roots.append(entry.name)
            _inventory(
                self.root,
                tuple(sorted(roots)),
                self.budget.maximum_entries,
                allow_internal_symlinks=True,
                access=access,
                observe=observe,
            )
        if observed != expected or _lineage(self.root) != self._root_lineage:
            _fail("original project namespace changed before publication")
        if close_inputs:
            for item in self._cache.values():
                self._close_file(item)
            self._git.close_native()
            self._close_retirement()
            self._write_live()
        ordered = sorted(
            complete,
            key=lambda name: (stat.S_ISDIR(complete[name][2]), -len(Path(name).parts)),
        )
        for name in ordered:
            if _native_facts((self.root / name).lstat()) != complete[name]:
                _fail("publication namespace changed during closing observations")
        if target is not None:
            relative = target.relative_to(self.root).as_posix()
            try:
                target_facts = _native_facts(target.lstat())
            except FileNotFoundError:
                target_facts = None
            if target_facts != complete.get(relative):
                _fail("original publication target changed during final close")
            parent = target.parent
            while parent != self.root:
                name = parent.relative_to(self.root).as_posix()
                if _native_facts(parent.lstat()) != complete[name]:
                    _fail("publication parent changed during final close")
                parent = parent.parent
        if _native_facts(self.root.lstat()) != root_facts:
            _fail("project directory changed during final publication close")

    def _complete(
        self,
        plan,
        result,
        advanced,
        upstream,
        written,
        receipts,
        checkpoint,
        checkpoint_receipt,
    ):
        from literate_ai.contracts import ProjectUpdateClassification as Classification

        self._write_live()
        self._applied = result
        for relative, content in written.items():
            if self.read(relative, optional=True) != content:
                _fail("actual published update changed")
        paths = []
        for item in advanced:
            content = upstream.get(item.path)
            if content is None or item.compatibility is not None:
                continue
            if digest(content) != item.upstream_identity.uri:
                _fail("advanced upstream no longer matches actual plan")
            if item.path not in written:
                if item.classification not in (
                    Classification.UNCHANGED,
                    Classification.ALREADY_CURRENT,
                ):
                    _fail("unselected update row supplied an advancement")
                if self.read(item.path) != content:
                    _fail("unchanged/current update input changed")
            paths.append(item.path)
        if self.read(CHECKPOINT) != checkpoint:
            _fail("actual published checkpoint changed")
        self._close_namespace()
        self._paths = tuple(sorted(paths))
        self._removed = tuple(
            sorted(path for path, content in written.items() if content is None)
        )
        from .repository_refresh_reservations import _custody_wire

        document = {
            "schema": "literate-ai/live-framework-update@1",
            "nonce": self._nonce,
            "root": str(self.root),
            "plan": plan.identity.uri,
            "provider": self._provider_origin.identity.uri,
            "registry": self._registry.uri,
            "checkpoint": digest(checkpoint),
            "paths": self._paths,
            "removed": self._removed,
            "retirement_directory": str(self._retirement_directory),
            "retirement_directory_facts": _custody_wire(self._retirement_facts),
            "observations": [
                (
                    str(p),
                    digest(i.content) if i.content is not None else None,
                    _custody_wire(i.signature),
                    _custody_wire(self._lineages[p]),
                )
                for p, i in sorted(self._cache.items())
            ],
        }
        encoded = json.dumps(document, sort_keys=True).encode()
        if 64 * len(encoded) > self.metadata - self._used_metadata:
            _fail("live update observation exceeds metadata budget")
        self._charged += 64 * len(encoded)
        self._document = encoded
        self._identity = canonical_identity(document)
        self._ready = True
        self.require_current()

    def original_node(self, relative):
        return _node_receipt(self._cache[self.root / relative].signature)

    def check_publication(self, bases):
        # Bound JSON/base64 allocation before constructing serialized output.
        upper = 512
        for mapping in (*bases.scopes.values(), bases.sources):
            for name, value in mapping.items():
                upper += 128 + 12 * (len(name) + len(value))
        for key, content in bases.blobs.items():
            upper += 128 + 12 * len(key) + 4 * ((len(content) + 2) // 3)
        if upper > min(
            self.budget.maximum_file_bytes,
            self.budget.maximum_total_bytes - self._used_bytes - self._reserve,
        ):
            _fail("checkpoint publication exceeds remaining input budget")

    def reserve_merge(self, base, ours, theirs):
        size = sum(len(content or b"") for content in (base, ours, theirs))
        limit = min(self.budget.maximum_file_bytes, max(4096, size + 4096))
        allocation = 2 * size + 2 * limit + 4096
        if (
            allocation
            > self.budget.maximum_total_bytes - self._used_bytes - self._reserve
            or 64 * allocation > self.metadata - self._used_metadata
            or self._used_entries + 2 > self.budget.maximum_entries
        ):
            _fail("merge transformation exceeds shared input budget")
        self._total += allocation
        self._charged += 64 * allocation
        self._records += 2
        return limit

    def resolutions(self, value):
        count = size = 0

        def bound(item, depth=0):
            nonlocal count, size
            count += 1
            if count > self.budget.maximum_entries or depth > 16:
                _fail("resolution configuration exceeds entry budget")
            if isinstance(item, str):
                size += 12 * len(item)
                if len(item) * 4 > self.budget.maximum_file_bytes:
                    _fail("resolution text exceeds file budget")
            elif isinstance(item, dict):
                if len(item) > self.budget.maximum_entries:
                    _fail("resolution map exceeds entry budget")
                for key, child in item.items():
                    if not isinstance(key, str):
                        _fail("resolution keys must be text")
                    bound(key, depth + 1)
                    bound(child, depth + 1)
            elif item is not None:
                _fail("resolution configuration must contain text mappings")
            if (
                size
                > self.budget.maximum_total_bytes - self._used_bytes - self._reserve
            ):
                _fail("resolution configuration exceeds byte budget")

        bound(value)
        if (
            size * 64 + count * 4096 > self.metadata - self._used_metadata
            or count + self._used_entries > self.budget.maximum_entries
        ):
            _fail("resolution configuration exceeds metadata budget")
        encoded = json.dumps(value).encode()
        self._total += len(encoded)
        self._charged += size * 64 + count * 4096
        self._records += count
        return json.loads(encoded)

    @property
    def identity(self):
        self._live(ready=True)
        return self._identity

    @property
    def paths(self):
        self._live(ready=True)
        return self._paths

    @property
    def removed_paths(self):
        self._live(ready=True)
        return self._removed

    @property
    def result(self):
        self._live(ready=True)
        return json.loads(json.dumps(self._applied.to_dict()))

    @property
    def document(self):
        self._live(ready=True)
        return json.loads(self._document)

    def require_current(self):
        self._live(ready=True)
        if (
            self._registry_value() != self._registry
            or self.current_origin() != self._provider_origin
        ):
            _fail("actual upstream provider changed")
        for item in self._cache.values():
            self._check(item)
        self.close_native()

    def close_native(self):
        self._live(ready=True)
        for item in self._cache.values():
            self._close_file(item)
        if _lineage(self.root) != self._root_lineage:
            _fail("original project ancestry changed")
        if getattr(self, "_git", None) is not None:
            self._git.close_native()
        self._live(ready=True)
        self._close_retirement()
        self._live(ready=True)

    def bind(self, root):
        self.require_current()
        if root != self.root:
            _fail("handoff belongs to another project")
        return self.identity.uri

    def require_plan(self, plan):
        self._live(ready=True)
        if plan.root != self.root or plan.framework_update != self.identity.uri:
            _fail("fresh source plan does not bind actual update handoff")
        checkpoint = self._cache[self.root / CHECKPOINT]
        if checkpoint not in plan.inputs:
            _fail("fresh source plan does not bind exact post-update checkpoint")

    def remaining(self, budget, metadata):
        self._live()
        files = budget.maximum_files - self._used_files
        entries = budget.maximum_entries - self._used_entries
        total = budget.maximum_total_bytes - self._used_bytes - self._reserve
        charged = self._used_metadata
        if min(files, entries, total, metadata - charged) < 1:
            _fail("handoff leaves no complete ownership budget")
        files = min(files, entries)
        limit = min(budget.maximum_file_bytes, total)
        return RetainedCargoInputBudget(
            files, entries, limit, min(total, files * limit)
        ), metadata - charged

    def spend(self):
        self.close_native()
        self._live(ready=True)
        self._spent = True


def _require_handoff(value):
    if type(value) is not _FrameworkUpdateRoles:
        raise TypeError("actual live framework update handoff required")
    value._live(ready=True)
    return value


@contextmanager
def applied_framework_update_roles(
    root,
    *,
    budget,
    maximum_metadata_bytes,
    retirement_directory,
    adopt_added=False,
    resolutions=None,
):
    from .project_update_apply import apply_project_update
    from .project_updates import FilesystemProjectUpdateAdapter
    from .retained_layout_control_roles import layout_pending_control_path

    root = Path(root)
    if type(adopt_added) is not bool:
        _fail("addition adoption must be an explicit boolean")
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute project root required")
    owner = None
    try:
        from .retained_layout_control_publication import _pinned_directory

        directory = Path(retirement_directory)
        with _pinned_directory(directory) as (descriptor, guard):
            try:
                with project_lifecycle_lock(root, operation="layout.framework-update"):
                    if os.path.lexists(layout_pending_control_path(root)):
                        _fail("pending layout requires explicit recovery")
                    owner = _FrameworkUpdateRoles(
                        _KEY, root, budget, maximum_metadata_bytes
                    )
                    owner._writing = True
                    try:
                        owner._prepare_retirement(directory, descriptor, guard)
                        owner._provider()
                        resolutions = owner.resolutions(resolutions)
                        owner._plan = FilesystemProjectUpdateAdapter(
                            adopt_added=adopt_added,
                            resolutions=resolutions,
                            _observation=owner,
                            origin_provider=owner.current_origin,
                        ).plan(root)
                        apply_project_update(
                            owner._plan,
                            root,
                            adopt_added=adopt_added,
                            resolutions=resolutions,
                            _role_observation=owner,
                        )
                    finally:
                        owner._writing = False
                owner.require_current()
                yield owner
                if not owner._spent:
                    owner.require_current()
            finally:
                if owner is not None:
                    owner._writing = False
                    owner._active = False
    finally:
        if owner is not None:
            owner._writing = False
            owner._active = False
