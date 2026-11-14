"""Nonexecuting original initializer rosters proved by bounded raw Git objects."""

from __future__ import annotations

import ast
import hashlib
import os
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from weakref import WeakKeyDictionary

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.repository_tree import git_object_identity
from literate_ai.repository_urls import repository_urls_equivalent

from . import harness_inventory, project_initialization
from .builders._process import run_bounded_process
from .flavor_markdown import parse_flavor_markdown
from .repository_refresh import _file, _signature
from .retained_layout_ast import initializer_ast_fingerprint

_INITIALIZER = "src/literate_ai/adapters/project_initialization.py"
_HARNESS = "src/literate_ai/adapters/harness_inventory.py"
_RESOURCES = "src/literate_ai/project_template/"

# Reviewed byte-publication and declared-layout dispatch changes since the
# pre-bootstrap producer. Arbitrary changes to these helpers are not ignored.
_HELPER_PAIRS = {
    "_atomic_replace": (
        "fa7d3a8ff78202115c3a73941760a3993b28e4729925650a6162ba02621f4176",
        "bf35a9eda50c6f1fc60cbde970de8443306e37a22546a6c6806eea6e64f406d1",
    ),
    "record_authority_review": (
        "c6965bf989fdfdbabe170e7868f5cf1214d81b43f89737fcc170e2a71c4e8045",
        "544676dc1435c88a364e63ef1d16505f5e38a841a70807716ab43a883cfc2f71",
    ),
    "_record_authority_review": (
        "1f8e150ea3154ee6bef60393d0eff05b38332c653885fd71fe18364de7ab5b31",
        "e4af97fdba51837d8f6e88ebafa25e14f0ce3aecc86b08482fed7dc9407b7f16",
    ),
    "prepare_native_rewrite_program": (
        "14e1b47fad68c75c4c2f6d4477271fb042ac4355e24dc329ff63eddd11d14470",
        "0daa476af5335b0f5ba5cb1c8ab131fa47f99cc9807e01b819acaeb2276bb9f0",
    ),
    "record_project_authority_review": (
        "411504527dc140ff33e63c0c8c888464aadf950ff6c515083d348426121072dd",
        "de80b293e659fd69a798644948a7b13a352017398a92422729d10bde23d98ec5",
    ),
}


def _fail(message):
    raise ValueError("layout.provider: " + message)


_PROFILES = WeakKeyDictionary()


def _profile(instance):
    """Construction provenance outlives a shared handle's mutable hints."""
    try:
        shared = _PROFILES[instance]
    except KeyError:
        _fail("actual constructed provider observer required")
    if instance._shared is not shared:
        _fail("original provider construction profile changed")
    if shared is not None:
        shared.require_profile(instance)
    return shared


class _Objects:
    def __init__(self, root, origin, budget, metadata_limit, *, _shared=None):
        if self in _PROFILES:
            _fail("provider construction profile cannot be reinitialized")
        if _shared is None:
            from .bounded_role_observation import current_role_observation

            if current_role_observation() is not None:
                _fail("canonical observation requires an actual shared provider")
        else:
            from .retained_layout_source_provider import _Provider, _record

            if type(_shared) is not _Provider:
                _fail("actual registered source provider construction required")
            _record(_shared, reading=True)
        self._shared = _shared
        _PROFILES[self] = _shared
        self.root, self.origin, self.budget = Path(root).absolute(), origin, budget
        if _shared is not None:
            _shared.bind_objects(self)
        require_safe_directory(self.root)
        node = self.root.stat()
        self.node = node.st_dev, node.st_ino
        self.limit = metadata_limit
        self.charged = self.total = self.entries = self.calls = self.reads = 0
        self.scratch_size = 0
        self.cache, self.trees = {}, {}
        self.file_count = 0
        self.snapshots, self.ancestry, self.directories = {}, {}, {}
        self.object_stores = ()
        self.deadline = time.monotonic() + 120
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }
        self.environment.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_SYSTEM=os.devnull,
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_OPTIONAL_LOCKS="0",
            GIT_TERMINAL_PROMPT="0",
            GIT_NO_LAZY_FETCH="1",
            GIT_NO_REPLACE_OBJECTS="1",
            GIT_ALLOW_PROTOCOL="",
        )
        if _profile(self) is not None:
            self.environment = MappingProxyType(self.environment)
        self.close_locator()
        commit = self.read("commit", origin.git_revision)
        first = commit.partition(b"\n")[0]
        if not first.startswith(b"tree "):
            _fail("original commit omits its root tree")
        self.tree = first[5:].decode("ascii")
        self._tree(self.tree)

    def run(self, *arguments, maximum):
        _profile(self)
        if _profile(self) is not None:
            return _profile(self).run(self, arguments, maximum)
        maximum = min(maximum, self.remaining())
        remaining = self.deadline - time.monotonic()
        self.calls += 1
        if (
            remaining <= 0
            or maximum < 1
            or self.calls > self.budget.maximum_entries + self.budget.maximum_files + 8
        ):
            _fail("original provider observation exhausted its bounds")
        result = run_bounded_process(
            (
                "git",
                "--no-pager",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=" + os.devnull,
                *arguments,
            ),
            cwd=self.root,
            environment=self.environment,
            timeout_seconds=min(30, remaining),
            stdout_limit_bytes=maximum,
            stderr_limit_bytes=4096,
            poll_interval_seconds=0.01,
            error_prefix="layout.provider",
        )
        if result.returncode or time.monotonic() >= self.deadline:
            _fail("original local provider objects are unavailable")
        return result.stdout

    def close_locator(self):
        _profile(self)
        require_safe_directory(self.root)
        node = self.root.stat()
        if (node.st_dev, node.st_ino) != self.node:
            _fail("original provider checkout was replaced")
        if not hasattr(self, "configuration"):
            self.git_paths = self.discover_paths()
            git_directory, common, objects = self.git_paths
            for path in (self.root, git_directory, common):
                self.directory(path)
            self.configuration = self.snapshot(common / "config")
            boundary = self.root / ".git"
            if boundary.is_dir():
                self.directory(boundary)
            else:
                self.snapshot(boundary, optional=True)
            self.snapshot(git_directory / "commondir", optional=True)
            worktree_configuration = self.snapshot(
                git_directory / "config.worktree", optional=True
            )
            self.configuration_graph((self.configuration, worktree_configuration))
            pending, visited = [objects], set()
            object_stores = []
            while pending:
                selected = pending.pop()
                self.directory(selected)
                node = _signature(selected)[:2]
                if node in visited:
                    continue
                visited.add(node)
                # Retain exact original object-store roots, not all traversed
                # prefixes. Successors must keep external alternate stores out
                # of private effect areas without treating '/' as a store.
                self.count_entry(str(selected))
                object_stores.append((selected, self.directories[selected]))
                info = selected / "info"
                if not info.exists():
                    self.snapshot(info, optional=True)
                    continue
                self.directory(info)
                alternates = self.snapshot(info / "alternates", optional=True)
                for line in (alternates.content or b"").decode("utf-8").split("\n"):
                    if not line:
                        continue
                    if line.startswith('"') or any(ord(char) < 32 for char in line):
                        _fail("quoted or control-character alternates are unsupported")
                    current = self.external_path(selected, line)
                    self.count_entry(str(current))
                    pending.append(current)
            self.object_stores = tuple(object_stores)
        if self.discover_paths() != self.git_paths:
            _fail("original provider Git routing changed")
        self.close_native()
        remote = self.run(
            "config",
            "--local",
            "--no-includes",
            "--get",
            "remote.origin.url",
            maximum=min(16384, self.budget.maximum_file_bytes),
        )
        if not repository_urls_equivalent(
            remote.decode("utf-8").strip(), self.origin.repository_url
        ):
            _fail("provider checkout does not match the recorded repository")
        self.close_native()

    def discover_paths(self):
        _profile(self)
        paths = []
        for arguments in (
            ("--git-dir",),
            ("--git-common-dir",),
            ("--git-path", "objects"),
        ):
            raw = self.run(
                "rev-parse", "--path-format=absolute", *arguments, maximum=16384
            )
            text = raw.decode("utf-8").removesuffix("\n")
            path = Path(text)
            if not path.is_absolute() or "\n" in text or "\r" in text:
                _fail("original provider Git directory is ambiguous")
            paths.append(path)
        return tuple(paths)

    def count_entry(self, label):
        _profile(self)
        if _profile(self) is not None:
            _profile(self).records(1, 4 * len(label))
        encoded = label.encode("utf-8")
        self.entries += 1
        self.charged += 4096 + 64 * len(encoded)
        if (
            len(encoded) > 4096
            or self.entries > self.budget.maximum_entries
            or self.charged > self.limit
            or time.monotonic() >= self.deadline
        ):
            _fail("original provider path occurrences exceed their explicit budget")

    def directory(self, path):
        _profile(self)
        if _profile(self) is not None:
            _profile(self).directory(path)
        if time.monotonic() >= self.deadline:
            _fail("original provider observation exhausted its bounds")
        require_safe_directory(path)
        if path not in self.directories:
            self.count_entry(str(path))
        self.directories[path] = _signature(path)[:3]
        for parent in (path, *path.parents):
            if parent not in self.ancestry:
                self.count_entry(str(parent))
                self.ancestry[parent] = _signature(parent)[:3]

    def external_path(self, base, value):
        _profile(self)
        target = Path(value)
        if len(target.parts) > 128 or len(value.encode("utf-8")) > 4096:
            _fail("original provider external path exceeds its explicit bound")
        if any(ord(char) < 32 for char in value):
            _fail("original provider external path contains control characters")
        current = Path(target.anchor) if target.is_absolute() else base
        for part in target.parts[1:] if target.is_absolute() else target.parts:
            # Preserve every traversed prefix, including ones canceled by '..'.
            self.directory(current)
            current = current.parent if part == ".." else current / part
        return current

    def configuration_graph(self, roots):
        _profile(self)
        pending, visited = list(roots), set()
        while pending:
            item = pending.pop()
            if item.path in visited or item.content is None:
                continue
            visited.add(item.path)
            keys = self.run(
                "config",
                "--file",
                str(item.path),
                "--no-includes",
                "--null",
                "--list",
                "--name-only",
                maximum=self.remaining(),
            ).split(b"\0")
            if not any(
                key.lower().startswith((b"include.", b"includeif.")) for key in keys
            ):
                continue
            declared = self.run(
                "config",
                "--file",
                str(item.path),
                "--no-includes",
                "--null",
                "--path",
                "--get-regexp",
                r"^include(if)?\.",
                maximum=self.remaining(),
            )
            if declared and not declared.endswith(b"\0"):
                _fail("original provider include records are incomplete")
            for record in declared.split(b"\0")[:-1]:
                key, separator, value = record.partition(b"\n")
                if not (
                    key == b"include.path"
                    or (key.startswith(b"includeif.") and key.endswith(b".path"))
                ):
                    continue
                if not separator or not value:
                    _fail("original provider include path is absent")
                target = self.external_path(item.path.parent, value.decode("utf-8"))
                self.count_entry(str(target))
                pending.append(self.snapshot(target, optional=True))

    def snapshot(self, path, *, optional=False):
        _profile(self)
        if path in self.snapshots:
            return self.snapshots[path]
        self.directory(path.parent)
        if self.file_count >= self.budget.maximum_files:
            _fail("original provider inputs exceed their explicit file budget")
        self.count_entry(str(path))
        item = _file(path, optional=optional, maximum_bytes=self.remaining())
        self.charge(item.content or b"")
        self.file_count += 1
        self.snapshots[path] = item
        return item

    def close_native(self):
        _profile(self)
        for path, signature in self.object_stores:
            if _signature(path)[:3] != signature:
                _fail("original provider object-store root changed")
        for path, signature in self.ancestry.items():
            if _signature(path)[:3] != signature:
                _fail("original provider ancestry changed")
        for path, item in self.snapshots.items():
            try:
                current = _signature(path)
            except FileNotFoundError:
                current = None
            if current != item.signature:
                _fail(
                    "original provider configuration changed"
                    if path == self.configuration.path
                    else "original provider routing or object-store input changed"
                )

    def remaining(self):
        _profile(self)
        return min(
            self.budget.maximum_file_bytes
            if _profile(self) is None
            else _profile(self).remaining(),
            self.budget.maximum_file_bytes,
            self.budget.maximum_total_bytes - self.total,
            (self.limit - self.charged - 4096 + 128 * self.scratch_size) // 256,
        )

    def charge(self, content):
        _profile(self)
        self.total += len(content)
        self.charged += 4096 + 128 * len(content)
        # Reserve a distinct largest-object scratch buffer for streaming closes.
        self.charged += 128 * max(0, len(content) - self.scratch_size)
        self.scratch_size = max(self.scratch_size, len(content))
        if self.total > self.budget.maximum_total_bytes or self.charged > self.limit:
            _fail("original provider payloads exceed their explicit budget")

    def read(self, kind, oid, *, maximum_bytes=None):
        _profile(self)
        if (
            len(oid) != len(self.origin.git_revision)
            or len(oid) not in {40, 64}
            or any(character not in "0123456789abcdef" for character in oid)
        ):
            _fail("original provider object identity is invalid")
        key = kind, oid
        if key in self.cache:
            return self.cache[key]
        if (
            self.file_count >= self.budget.maximum_files
            or self.entries >= self.budget.maximum_entries
            or self.remaining() < 1
        ):
            _fail("original provider objects exceed their explicit budget")
        maximum = self.remaining()
        if maximum_bytes is not None:
            maximum = min(maximum, max(1, maximum_bytes))
        if _profile(self) is not None:
            _profile(self).object_input()
        content = self.run("cat-file", kind, oid, maximum=maximum)
        if git_object_identity(kind, content, len(oid)) != oid:
            _fail("original provider object bytes disagree with their identity")
        self.charge(content)
        self.reads += 1
        self.file_count += 1
        self.entries += 1
        self.cache[key] = content
        return content

    def entry(self, path):
        _profile(self)
        parsed = PurePosixPath(path)
        encoded = path.encode("utf-8")
        if (
            not path
            or parsed.is_absolute()
            or parsed.as_posix() != path
            or ".." in parsed.parts
            or "\\" in path
            or len(parsed.parts) > 128
            or len(encoded) > 4096
        ):
            _fail("original provider path is unsafe or exceeds its bound")
        self.count_entry(path)

    def _tree(self, oid):
        _profile(self)
        if oid in self.trees:
            return self.trees[oid]
        raw = self.read("tree", oid)
        entries, aliases, position = {}, set(), 0
        width = len(oid) // 2
        while position < len(raw):
            end = raw.find(b"\0", position)
            if end < 0 or end + 1 + width > len(raw):
                _fail("original provider tree is truncated")
            mode, name = raw[position:end].split(b" ", 1)
            name = name.decode("utf-8")
            if (
                not name
                or name in {".", "..", ".git"}
                or "/" in name
                or "\\" in name
                or unicodedata.normalize("NFC", name) != name
                or name.casefold() in aliases
                or mode not in {b"40000", b"100644", b"100755", b"120000", b"160000"}
            ):
                _fail("original provider tree has unsupported entries")
            if _profile(self) is not None:
                _profile(self).records(1, len(name.encode("utf-8")))
            aliases.add(name.casefold())
            self.entries += 1
            self.charged += 4096 + 64 * len(name.encode("utf-8"))
            if self.entries > self.budget.maximum_entries or self.charged > self.limit:
                _fail("original provider tree metadata exceeds its explicit budget")
            entries[name] = mode, raw[end + 1 : end + 1 + width].hex()
            position = end + 1 + width
        self.trees[oid] = entries
        return entries

    def locate(self, path):
        _profile(self)
        self.entry(path)
        parsed = PurePosixPath(path)
        if (
            not path
            or parsed.is_absolute()
            or parsed.as_posix() != path
            or ".." in parsed.parts
            or "\\" in path
        ):
            _fail("original provider path is unsafe")
        mode, oid = b"40000", self.tree
        for name in parsed.parts:
            if mode != b"40000":
                _fail("original provider path crosses a non-directory")
            member = self._tree(oid).get(name)
            if member is None:
                _fail("original provider endpoint is missing")
            mode, oid = member
        return mode, oid

    def blob(self, path):
        _profile(self)
        mode, oid = self.locate(path)
        if mode not in {b"100644", b"100755"}:
            _fail("original provider input must be a regular blob")
        return self.read("blob", oid)

    def flavor_files(self):
        _profile(self)
        mode, oid = self.locate(_RESOURCES + "flavors")
        if mode != b"40000":
            _fail("original Flavor resources require a directory")
        pending, files = [("flavors", oid)], []
        while pending:
            parent, oid = pending.pop()
            for name, (mode, child) in self._tree(oid).items():
                relative = parent + "/" + name
                self.entry(relative)
                if len(files) + len(pending) >= self.budget.maximum_entries:
                    _fail("original Flavor namespace exceeds its explicit budget")
                if mode == b"40000":
                    pending.append((relative, child))
                elif mode in {b"100644", b"100755"}:
                    files.append(relative)
                else:
                    _fail("original Flavor resource aliases are unsupported")
        return tuple(sorted(files))


def _shape(content, *, initializer, maximum_nodes, charge_path=None):
    module = ast.parse(content)
    pending, count = [(module, 0)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > maximum_nodes or depth > 96:
            _fail("original producer AST exceeds its explicit budget")
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    mapping, helpers = None, {}
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name in _HELPER_PAIRS:
            if node.name in helpers:
                _fail("ambiguous original producer helper")
            helpers[node.name] = initializer_ast_fingerprint(node)
    for node in module.body:
        if (
            initializer
            and isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_TEMPLATE_FILES"
                for target in node.targets
            )
        ):
            if mapping is not None:
                _fail("ambiguous original template producer")
            if (
                not isinstance(node.value, ast.Dict)
                or len(node.value.keys) > maximum_nodes
            ):
                _fail("original template mapping exceeds its explicit bound")
            for key, value in zip(node.value.keys, node.value.values, strict=True):
                if not (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    _fail("original template producer requires literal paths")
                if charge_path is not None:
                    charge_path(key.value)
                    charge_path(value.value)
            mapping = ast.literal_eval(node.value)
            node.value = ast.Dict(keys=[], values=[])
        if (
            initializer
            and isinstance(node, ast.ClassDef)
            and node.name == "FilesystemProjectInitializationAdapter"
        ):
            node.body = [
                method
                for method in node.body
                if not isinstance(method, ast.FunctionDef)
                or method.name
                not in {"record_authority_review", "_record_authority_review"}
            ]
    # The compared initializer still fixes every created endpoint. These byte
    # publication helpers cannot expand the accepted template mapping.
    ignored = (
        {"_atomic_replace", "record_project_authority_review"}
        if initializer
        else {"prepare_native_rewrite_program"}
    )
    module.body = [
        node
        for node in module.body
        if not isinstance(node, ast.FunctionDef) or node.name not in ignored
    ]
    if initializer and (
        not isinstance(mapping, dict)
        or not mapping
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in mapping.items()
        )
    ):
        _fail("original template producer requires an exact literal mapping")
    return ast.dump(module, include_attributes=False), mapping, helpers


class _OriginalRoster:
    __slots__ = (
        "_objects",
        "_templates",
        "_inputs",
        "_active",
        "_pid",
        "_identity",
        "_shared",
        "__weakref__",
    )

    def __init__(self, objects, templates, inputs):
        if self in _PROFILES:
            _fail("provider roster construction profile cannot be reinitialized")
        profile = _profile(objects)
        self._objects, self._templates, self._inputs = objects, templates, inputs
        self._shared = profile
        _PROFILES[self] = self._shared
        self._active, self._pid = True, os.getpid()
        self._identity = canonical_identity(
            {
                "schema": "literate-ai/original-initializer-roster@1",
                "origin": objects.origin.to_dict(),
                "objects": sorted(objects.cache),
                "templates": templates,
                "provider_inputs": [
                    (
                        str(item.path),
                        item.signature,
                        None
                        if item.content is None
                        else hashlib.sha256(item.content).hexdigest(),
                    )
                    for item in objects.snapshots.values()
                ],
                "provider_directories": sorted(
                    (str(path), node) for path, node in objects.directories.items()
                ),
            }
        )

    @property
    def objects(self):
        _profile(self)
        return self._objects

    @property
    def templates(self):
        _profile(self)
        return self._templates

    @property
    def inputs(self):
        _profile(self)
        return self._inputs

    @property
    def identity(self):
        _profile(self)
        return self._identity

    def require_current(self):
        _profile(self)
        if _profile(self) is not None:
            _profile(self).require_current()
            return
        if not self._active or self._pid != os.getpid():
            _fail("original provider observation ended")
        self.close_native()
        observed = _Objects(
            self.objects.root,
            self.objects.origin,
            self.objects.budget,
            self.objects.limit,
        )
        if observed.node != self.objects.node:
            _fail("original provider checkout was replaced")
        self.close_native()
        verified = set(observed.cache)
        observed.cache.clear()
        observed.trees.clear()
        for kind, oid in self.objects.cache:
            if (kind, oid) not in verified:
                observed.read(
                    kind, oid, maximum_bytes=len(self.objects.cache[kind, oid])
                )
                observed.cache.clear()
        observed.close_locator()
        self.close_native()

    def close_native(self):
        _profile(self)
        if not self._active or self._pid != os.getpid():
            _fail("original provider observation ended")
        self.objects.close_native()
        for item in self.inputs:
            if _signature(item.path) != item.signature:
                _fail("current provider interpreter changed")


def _build_original_roster(
    origin, definition, *, checkout, budget, metadata_limit, _shared=None
):
    root = (
        _shared.select_root(checkout)
        if _shared is not None
        else (
            Path(project_initialization.__file__).resolve().parents[3]
            if checkout is None
            else Path(checkout)
        )
    )
    objects = _Objects(root, origin, budget, metadata_limit, _shared=_shared)
    inputs = []
    for module in (project_initialization, harness_inventory):
        item = objects.snapshot(Path(module.__file__))
        inputs.append(item)
    mapping = None
    for index, path in enumerate((_INITIALIZER, _HARNESS)):
        content = objects.blob(path)
        original = _shape(
            content,
            initializer=index == 0,
            maximum_nodes=metadata_limit // 512
            if _shared is None
            else _shared.shape_limit(content, metadata_limit // 512),
            charge_path=objects.entry,
        )
        current = _shape(
            inputs[index].content,
            initializer=index == 0,
            maximum_nodes=metadata_limit // 512
            if _shared is None
            else _shared.shape_limit(inputs[index].content, metadata_limit // 512),
        )
        if original[0] != current[0]:
            _fail("original initializer producer shape is unsupported")
        if original[2].keys() != current[2].keys() or any(
            original[2][name] != current[2][name]
            and (original[2][name], current[2][name]) != _HELPER_PAIRS[name]
            for name in original[2]
        ):
            _fail("original initializer helper shape is unsupported")
        if index == 0:
            mapping = original[1]
    flavors = objects.flavor_files()
    directories = {}
    for name in flavors:
        if len(PurePosixPath(name).parts) == 3 and name.endswith("/flavor.md"):
            flavor = parse_flavor_markdown(objects.blob(_RESOURCES + name), source=name)
            coordinate = f"flavor://{flavor.namespace}/{flavor.name}"
            if coordinate in directories:
                _fail("original Flavor coordinates are ambiguous")
            directories[coordinate] = PurePosixPath(name).parts[1]
    active = set()
    for selector in definition.default_flavor_selectors:
        directory = directories.get(selector.removeprefix("+"))
        if directory is None:
            _fail("original selected Flavor is unavailable")
        active.add(directory)
    mapping.update({name: name for name in flavors})
    templates = []
    for name, resource in mapping.items():
        if project_initialization._include_template_file(name, frozenset(active)):
            objects.entry(name)
            mode, _ = objects.locate(_RESOURCES + resource)
            if mode not in {b"100644", b"100755"}:
                _fail("original template endpoint lacks its regular resource")
            templates.append(name)
    if _shared is not None:
        _shared.roster_allowance(objects, templates, inputs)
    return _OriginalRoster(objects, tuple(sorted(templates)), tuple(inputs))


@contextmanager
def original_initializer_roster(
    origin, definition, *, checkout, budget, metadata_limit
):
    roster = _build_original_roster(
        origin,
        definition,
        checkout=checkout,
        budget=budget,
        metadata_limit=metadata_limit,
    )
    try:
        roster.require_current()
        yield roster
        roster.require_current()
    finally:
        roster._active = False
