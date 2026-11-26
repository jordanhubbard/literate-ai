"""Read-only native source queries for canonical harness inspection at root.

This is a query adapter over an original complete capture, not a replacement
filesystem, path-based exclusion convention or serialized source owner. Existing
canonical detectors see retained members only; every read rejoins actual bytes,
and a complete closing capture rejects namespace/content/mode drift. No write,
command-execution or recovery capability is issued.
"""

from __future__ import annotations

import fnmatch
import hashlib
import io
import os
import threading
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from literate_ai.adapters.retained_layout import RetainedLayoutError, _fail
from literate_ai.adapters.retained_layout_partition import (
    _layout_modes,
    _layout_source_identity,
    _require_original,
    _signature,
    capture_retained_layout_source,
)
from literate_ai.adapters.retained_project_inputs import _directory_access, _stream
from literate_ai.contracts.native_sdk_trees import NativeSdkTree, _ResolutionBudget
from literate_ai.contracts.paths import canonical_relative_posix_path

_VIEWS = weakref.WeakKeyDictionary()
_PATHS = weakref.WeakKeyDictionary()


def _original(view):
    record = _VIEWS.get(view)
    if (
        record is None
        or not record["active"]
        or record["pid"] != os.getpid()
        or record["thread"] is not threading.current_thread()
    ):
        _fail("original_inspection_required", "original source inspection has retired")
    if record["failure"] is not None:
        raise RetainedLayoutError(*record["failure"])
    try:
        _require_original(record["context"])
        record["access"].require_current()
    except (ValueError, OSError) as exc:
        record["failure"] = (
            getattr(exc, "code", "retained.layout.source_changed"),
            "original source inspection custody is no longer current",
        )
        raise RetainedLayoutError(*record["failure"]) from exc
    return record


def _refuse(record, suffix, message):
    # Canonical metadata parsers may catch ValueError for malformed TOML/JSON.
    # Keep a private monotonic denial so such a catch can never hide a source or
    # resource failure: the factory replays it before any successful return.
    record["failure"] = ("retained.layout." + suffix, message)
    raise RetainedLayoutError(*record["failure"])


def _admit(record, amount):
    context = _require_original(record["context"])
    record["memory"] += amount
    if record["memory"] + context["retained"] > context["maximum"]:
        _refuse(
            record,
            "metadata_limit",
            "source inspection exceeds original metadata memory",
        )


def _selected(path):
    selected = _PATHS.get(path)
    if selected is None:
        _fail("original_inspection_required", "original source query path required")
    owner, relative = selected
    return _original(owner), relative


def _path(owner, relative):
    record = _original(owner)
    if relative != ".":
        candidate = PurePosixPath(relative)
        if (
            candidate.is_absolute()
            or candidate.as_posix() != relative
            or any(part in {"..", ""} for part in candidate.parts)
        ):
            _refuse(
                record, "inspection_escape", "source query escaped its original root"
            )
        try:
            canonical_relative_posix_path(relative, label="original source query")
        except ValueError:
            _refuse(record, "inspection_escape", "canonical source query required")
    result = record["paths"].get(relative)
    if result is None:
        _admit(record, 2048 + 64 * len(relative.encode()))
        result = _InspectionPath()
        _PATHS[result] = (owner, relative)
        record["paths"][relative] = result
    return result


def _resolve(record, relative):
    if record["failure"] is not None:
        raise RetainedLayoutError(*record["failure"])
    if relative == ".":
        return "."
    cache = record["resolutions"]
    if relative in cache:
        return cache[relative]
    # Reuse the original already-admitted complete indexes. ComposedTree's
    # convenience resolve_all intentionally rebuilds them for a whole batch;
    # using that convenience entrypoint for every leaf would be quadratic.
    _admit(record, 512 + 64 * len(relative.encode()))
    try:
        canonical_relative_posix_path(relative, label="original source query")
    except ValueError:
        _refuse(record, "inspection_escape", "canonical source query required")
    try:
        resolved = NativeSdkTree._resolve(
            relative,
            record["directories"],
            record["files"],
            record["aliases"],
            record["resolution_budget"],
        )
    except ValueError as exc:
        if record["resolution_budget"].remaining < 0:
            _refuse(record, "metadata_limit", "source query resolution work exhausted")
        if str(exc) not in {
            "SDK alias target is absent from its inventoried tree",
            "SDK alias traverses a non-directory",
        }:
            _refuse(
                record, "source_invalid", "canonical source alias resolution failed"
            )
        resolved = None
    cache[relative] = resolved
    return resolved


def _glob_match(parts, pattern):
    # A small dynamic program preserves component-wise pathlib glob semantics;
    # '**' consumes zero or more components. Only already-captured names are
    # enumerated, so a new tree/alias cannot expand the query beyond its budget.
    reachable = {0}
    for piece in pattern:
        following = set()
        for index in reachable:
            if piece == "**":
                following.update(range(index, len(parts) + 1))
            elif index < len(parts) and fnmatch.fnmatchcase(parts[index], piece):
                following.add(index + 1)
        reachable = following
    return len(parts) in reachable


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class _InspectionPath:
    def __reduce__(self):
        raise TypeError("retained.layout.inspection-path-not-transportable")

    def __fspath__(self):
        record, relative = _selected(self)
        return os.fspath(record["root"] / relative)

    def __str__(self):
        return self.__fspath__()

    def __lt__(self, other):
        if not isinstance(other, _InspectionPath):
            return NotImplemented
        return str(self) < str(other)

    def __truediv__(self, child):
        record, relative = _selected(self)
        child = PurePosixPath(child)
        if child.is_absolute() or ".." in child.parts:
            _refuse(record, "inspection_escape", "relative source query required")
        return _path(_PATHS[self][0], (PurePosixPath(relative) / child).as_posix())

    @property
    def name(self):
        record, relative = _selected(self)
        return (record["root"] / relative).name

    @property
    def suffix(self):
        return PurePosixPath(self.name).suffix

    @property
    def stem(self):
        return PurePosixPath(self.name).stem

    @property
    def parent(self):
        _, relative = _selected(self)
        if relative == ".":
            _refuse(
                _selected(self)[0],
                "inspection_escape",
                "source query parent is outside its root",
            )
        return _path(_PATHS[self][0], PurePosixPath(relative).parent.as_posix())

    def as_posix(self):
        return str(self)

    def relative_to(self, other):
        return Path(str(self)).relative_to(Path(os.fspath(other)))

    def resolve(self, strict=False):
        record, relative = _selected(self)
        resolved = _resolve(record, relative)
        if resolved is None:
            if strict:
                raise FileNotFoundError(relative)
            return self
        return _path(_PATHS[self][0], resolved)

    def is_file(self):
        record, relative = _selected(self)
        selected = record["files"].get(_resolve(record, relative))
        if selected is not None:
            # Some canonical stdlib readers consume a filename after this
            # query. Admit that parse too, before any such allocation occurs.
            _admit(record, 16 * selected.blob.size)
        return selected is not None

    def is_dir(self):
        record, relative = _selected(self)
        target = _resolve(record, relative)
        return target == "." or target in record["directories"]

    def exists(self):
        record, relative = _selected(self)
        return _resolve(record, relative) is not None

    def is_symlink(self):
        record, relative = _selected(self)
        if relative == ".":
            return False
        name = PurePosixPath(relative)
        parent = _resolve(record, name.parent.as_posix())
        if parent is None:
            return False
        actual = (PurePosixPath(parent) / name.name).as_posix()
        alias = record["aliases"].get(actual)
        return alias is not None and alias.kind == "symlink"

    def read_bytes(self):
        record, relative = _selected(self)
        resolved = _resolve(record, relative)
        selected = record["files"].get(resolved)
        if selected is None:
            raise FileNotFoundError(relative)
        _admit(record, 16 * selected.blob.size)
        access = record["access"]
        if access is None:
            _fail("native_owner_unavailable", "original source query handles required")
        try:
            node = access.metadata(record["root"] / resolved)
            stream = io.BytesIO()
            _stream(record["root"], resolved, selected.blob.size, stream, access=access)
            raw = stream.getvalue()
            if (
                _signature(access.metadata(record["root"] / resolved))
                != _signature(node)
                or hashlib.sha256(raw).hexdigest() != selected.blob.digest
                or len(raw) != selected.blob.size
            ):
                _refuse(
                    record, "source_changed", "original inspected source bytes changed"
                )
        except (OSError, ValueError) as exc:
            if record["failure"] is None:
                record["failure"] = (
                    "retained.layout.source_changed",
                    "original inspected source is no longer readable",
                )
            raise RetainedLayoutError(*record["failure"]) from exc
        return raw

    def read_text(self, encoding=None, errors=None):
        return self.read_bytes().decode(encoding or "utf-8", errors or "strict")

    def iterdir(self):
        yield from self.glob("*")

    def rglob(self, pattern):
        yield from self.glob("**/" + pattern)

    def glob(self, pattern):
        record, relative = _selected(self)
        if type(pattern) is not str or len(pattern) > 4096:
            _refuse(
                record, "metadata_limit", "source glob exceeds its finite query bound"
            )
        pieces = PurePosixPath(pattern).parts
        if len(pieces) > 128:
            _refuse(record, "metadata_limit", "source glob exceeds its component bound")
        if PurePosixPath(pattern).is_absolute() or ".." in pieces:
            _refuse(record, "inspection_escape", "source glob must remain relative")
        resolved = _resolve(record, relative)
        if resolved != "." and resolved not in record["directories"]:
            return
        prefix = "" if resolved == "." else resolved + "/"
        for name in record["names"]:
            if not name.startswith(prefix):
                continue
            tail = name[len(prefix) :]
            if tail and _glob_match(PurePosixPath(tail).parts, pieces):
                yield _path(
                    _PATHS[self][0], (PurePosixPath(relative) / tail).as_posix()
                )


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class _InspectionOwner:
    def __reduce__(self):
        raise TypeError("retained.layout.inspection-not-transportable")


@contextmanager
def _inspect_source_paths_open(context, access):
    _require_original(context)
    publication = context.layout.publication
    if publication is None:
        _fail("transition_required", "complete layout publication is required")
    policy = publication.source_policy
    tree = capture_retained_layout_source(
        context, limits=policy.limits, case_sensitive=policy.case_sensitive
    )
    modes, mode_memory = _layout_modes(context, tree, reserved_memory_bytes=0)
    index_memory = 4096 * (len(tree.files) + len(tree.aliases) + len(tree.directories))
    memory = tree.index.metadata_memory_bound + mode_memory + index_memory
    context.require_framework_current(reserved_memory_bytes=memory)
    owner = _InspectionOwner()
    issued = {
        "active": True,
        "pid": os.getpid(),
        "thread": threading.current_thread(),
        "context": context,
        "access": access,
        "root": context.layout.implementation,
        "tree": tree,
        "directories": set(tree.directories),
        "files": {x.path: x for x in tree.files},
        "aliases": {x.path: x for x in tree.aliases},
        "names": tuple(
            sorted(
                (
                    *tree.directories,
                    *(x.path for x in tree.files),
                    *(x.path for x in tree.aliases),
                )
            )
        ),
        "paths": {},
        "resolutions": {},
        "resolution_budget": _ResolutionBudget(),
        "failure": None,
        "memory": memory,
    }
    _VIEWS[owner] = issued
    try:
        yield _path(owner, "."), _layout_source_identity(tree.identity, modes)
        _original(owner)
        closing = capture_retained_layout_source(
            context,
            limits=policy.limits,
            case_sensitive=policy.case_sensitive,
            reserved_memory_bytes=issued["memory"],
        )
        closing_modes, _ = _layout_modes(
            context, closing, reserved_memory_bytes=issued["memory"]
        )
        if closing.identity != tree.identity or closing_modes != modes:
            _fail("source_changed", "source changed during harness inspection")
        del closing, closing_modes
    finally:
        issued["active"] = False
        _VIEWS.pop(owner, None)
        issued.clear()
        del tree, modes


@contextmanager
def _inspect_source_paths(context):
    record = _require_original(context)
    with _directory_access(record["source_root"]) as access:
        if access is None:
            _fail("native_owner_unavailable", "original source query handles required")
        with _inspect_source_paths_open(context, access) as observation:
            yield observation


def inspect_retained_layout_harness(context):
    """Reuse canonical detectors through original source-only read queries."""
    from .harness_inventory import (
        HARNESS_INVENTORY_SCHEMA,
        _detect_build_system,
        _detect_gitlab_ci,
        _detect_operating_systems,
        _detect_packaging,
        _detect_release_workflow,
        classify_ci,
    )

    with _inspect_source_paths(context) as (root, identity):
        detected, commands, stages = _detect_build_system(root)
        findings = [
            *detected,
            *_detect_packaging(root),
            *_detect_operating_systems(root),
            *_detect_gitlab_ci(root),
            *_detect_release_workflow(root),
        ]
        result = {
            "schema": HARNESS_INVENTORY_SCHEMA,
            "findings": findings,
            "commands": commands,
            "stages": stages,
            "ci": classify_ci(findings, commands),
            "source_scope": context.layout.publication.source_policy.to_dict(),
            "layout_identity": context.layout.identity.uri,
            "layout_source_identity": identity.uri,
        }
    return result
