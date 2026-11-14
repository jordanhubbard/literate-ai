"""Canonical lock selection under one actual creating source read owner.

The participant observes the selected store; it grants no canonical writer,
project partition, source movement or qualification rights.
"""

from __future__ import annotations

import os
import stat
import threading
import unicodedata
from dataclasses import dataclass, fields, replace
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity

_KEY = object()
_OWNERS = {}
_BOUND = {}
_CREATED = {}
_READERS = {}
_BINDINGS = {}


def _fail(message):
    raise ValueError("layout.canonical-storage: " + message)


@dataclass(frozen=True, slots=True)
class _Record:
    owner: object
    preparation: object
    reader: object
    ledger: object
    root: Path
    component: Path
    pid: int
    thread: int
    storage: Path | None = None
    path: Path | None = None
    paths: tuple = ()
    snapshot: object = None
    anchor: object = None
    presence: object = None
    identity: object = None
    plan: object = None


_FIELDS = tuple(field.name for field in fields(_Record))
_SNAPSHOT_FIELDS = ("path", "signature", "content")
_IDENTITY_FIELDS = ("algorithm", "digest")


def _seal(value):
    return (
        value,
        tuple(getattr(value, name) for name in _FIELDS),
        None
        if value.snapshot is None
        else (
            type(value.snapshot),
            tuple(getattr(value.snapshot, name) for name in _SNAPSHOT_FIELDS),
        ),
        None
        if value.identity is None
        else (
            type(value.identity),
            tuple(getattr(value.identity, name) for name in _IDENTITY_FIELDS),
        ),
    )


def _require_seal(owner, value):
    expected = _BINDINGS.get(owner)
    if (
        type(value) is not _Record
        or expected is None
        or expected[0] is not value
        or any(
            getattr(value, name) is not original
            for name, original in zip(_FIELDS, expected[1], strict=True)
        )
    ):
        _fail("original canonical record was replaced or changed")
    for actual, witness, names in (
        (value.snapshot, expected[2], _SNAPSHOT_FIELDS),
        (value.identity, expected[3], _IDENTITY_FIELDS),
    ):
        if witness is not None and (
            type(actual) is not witness[0]
            or any(
                getattr(actual, name) is not original
                for name, original in zip(names, witness[1], strict=True)
            )
        ):
            _fail("original canonical observation fields changed")


def _record(owner, *, ready=True, reading=False):
    from .bounded_role_observation import current_role_observation
    from .retained_layout_source_preparation import _LIVE, _SourcePreparation

    if type(owner) is not _Selection:
        _fail("actual original canonical selection required")
    value = _OWNERS.get(owner)
    _require_seal(owner, value)
    if value.owner is not owner or (
        _BOUND.get(value.preparation) is not owner
        or _CREATED.get(value.preparation) is not owner
        or _READERS.get(value.reader) is not owner
    ):
        _fail("original canonical selection ended or was replaced")
    original = _LIVE.get(value.preparation)
    if (
        type(value.preparation) is not _SourcePreparation
        or original is None
        or original.reader is not value.reader
        or original.ledger is not value.ledger
        or original.root != value.root
        or (value.pid, value.thread) != (os.getpid(), threading.get_ident())
        or (original.plan is not None and original.plan is not value.plan)
        or (ready and value.identity is None)
    ):
        _fail("actual original canonical selection lifetime required")
    value.reader._live()
    if reading and current_role_observation() is not value.reader:
        _fail("actual active original canonical reader required")
    if value.snapshot is not None and (
        value.ledger.cache.get(value.path) is not value.snapshot
        or value.ledger.ancestry.get(value.path) != value.anchor
        or any(
            path not in value.reader._presences or value.reader._presences[path] != node
            for path, node in value.paths
        )
        or value.path not in value.reader._presences
        or value.reader._presences[value.path] != value.presence
    ):
        _fail("original canonical selection observations changed")
    return value


def _advance(owner, before, **changes):
    if _record(owner, ready=False, reading=True) is not before:
        _fail("original canonical selection predecessor changed")
    if before.identity is not None or before.plan is not None:
        _fail("completed canonical observations are immutable")
    after = replace(before, **changes)
    _OWNERS[owner] = after
    _BINDINGS[owner] = _seal(after)
    return after


class _Selection:
    __slots__ = ()

    def __init__(self, key):
        if key is not _KEY or self in _OWNERS:
            raise TypeError("actual creating canonical selection required")

    @property
    def path(self):
        return _record(self).path

    @property
    def identity(self):
        return _record(self).identity

    @property
    def selector_paths(self):
        return _record(self).paths

    def require_current(self):
        value = _record(self, reading=True)
        observed = value.reader.file(
            value.path,
            optional=value.snapshot.content is None,
            maximum_bytes=max(1, len(value.snapshot.content or b"")),
        )
        if observed is not value.snapshot:
            _fail("actual original canonical lock observation required")
        self.close_native()
        if _record(self, reading=True) is not value:
            _fail("original canonical selection changed during observation")

    def close_native(self):
        from .bounded_role_observation import current_role_observation
        from .catalog_copy_plan import _anchor
        from .retained_layout_git_controls import _presence

        value = _record(self)
        current = current_role_observation()
        if current is not None and current is not value.reader:
            _fail("foreign active reader cannot close original canonical observations")
        for path, expected in value.paths:
            if _presence(path) != expected:
                _fail("original canonical selector native facts changed")
        if (
            _anchor(value.path) != value.anchor
            or _presence(value.path) != value.presence
        ):
            _fail("original canonical lock native facts changed")
        if _record(self) is not value:
            _fail("original canonical selection ended during native closure")


def _walk(owner, path):
    from .retained_layout_git_controls import _presence
    from .retained_layout_partition import _lineage

    value = _record(owner, ready=False, reading=True)
    count = len(path.parts)
    value.ledger.charge_records(
        8 + 4 * count,
        4096 + 128 * count * len(str(path).encode()),
    )
    # Retain cumulative prefixes only after reserving their quadratic text bound.
    paths = [Path(path.anchor)]
    for part in path.parts[1:]:
        paths.append(paths[-1].parent if part == ".." else paths[-1] / part)
    facts = dict(value.paths)
    for prefix in paths:
        node = _presence(prefix)
        if node is not None:
            if not stat.S_ISDIR(node[2]):
                _fail("canonical selection requires direct directories")
            _lineage(prefix)
        facts[prefix] = node
        if _record(owner, ready=False, reading=True) is not value:
            _fail("original canonical selection changed during resolution")
    _advance(owner, value, paths=tuple(facts.items()))


def observe_selection(preparation, component_root):
    from .bounded_role_observation import current_role_observation
    from .component_locks import LOCK_FILENAME, ComponentLockStore
    from .repository_refresh_reservations import _custody_wire
    from .retained_layout_git_controls import _presence
    from .retained_layout_source_preparation import _state

    original = _state(preparation, ready=False)
    if (
        original.plan is not None
        or current_role_observation() is not original.reader
        or preparation in _BOUND
        or preparation in _CREATED
        or original.reader in _READERS
        or not isinstance(component_root, Path)
        or not component_root.is_absolute()
        or ".." in component_root.parts
        or not component_root.is_relative_to(original.root)
    ):
        _fail("one actual creating original canonical selection required")
    original.ledger.charge_records(64, 65536 + 128 * len(str(component_root).encode()))
    owner = _Selection(_KEY)
    value = _Record(
        owner,
        preparation,
        original.reader,
        original.ledger,
        original.root,
        component_root,
        os.getpid(),
        threading.get_ident(),
    )
    _OWNERS[owner], _BOUND[preparation] = value, owner
    _BINDINGS[owner] = _seal(value)
    _CREATED[preparation], _READERS[original.reader] = owner, owner
    try:
        _walk(owner, component_root)
        if dict(_record(owner, ready=False).paths)[component_root] is None:
            _fail("actual existing canonical Component root required")
        selected = os.environ.get("LITAI_MATRIX_CELL_ROOT")
        matrix = None
        if selected:
            original.ledger.charge_records(8, 4096 + 4 * len(selected))
            supplied = Path(selected)
            if not supplied.is_absolute():
                original.ledger.charge_records(8, 65536)
                supplied = Path.cwd() / supplied
            _walk(owner, supplied)
            matrix = Path(os.path.normpath(str(supplied)))
        storage = ComponentLockStore._storage_root(component_root, matrix)
        _walk(owner, storage)
        path = storage / LOCK_FILENAME
        value = _advance(
            owner,
            _record(owner, ready=False, reading=True),
            storage=storage,
            path=path,
        )
        snapshot = original.reader.file(
            path, optional=True, maximum_bytes=original.ledger.budget.maximum_file_bytes
        )
        presence = _presence(path)
        anchor = original.ledger.ancestry[path]
        project = original.reader._lineages[original.root][-1][1:3]
        if not path.is_relative_to(original.root) and project in {
            row[1:3] for row in anchor[1]
        }:
            _fail("external canonical storage aliases the actual project")
        identity = canonical_identity(
            {
                "schema": "literate-ai/canonical-lock-observation@1",
                "facts": _custody_wire(
                    (component_root, storage, snapshot, anchor, value.paths, presence)
                ),
            }
        )
        _advance(
            owner,
            value,
            snapshot=snapshot,
            anchor=anchor,
            presence=presence,
            identity=identity,
        )
        owner.require_current()
        return owner
    except BaseException:
        _OWNERS.pop(owner, None)
        _BINDINGS.pop(owner, None)
        if _BOUND.get(preparation) is owner:
            _BOUND.pop(preparation, None)
        if _CREATED.get(preparation) is owner:
            _CREATED.pop(preparation, None)
        if _READERS.get(original.reader) is owner:
            _READERS.pop(original.reader, None)
        raise


def _for_preparation(preparation):
    owner = _BOUND.get(preparation)
    _record(owner)
    return owner


def _require_path(owner, root, component, path):
    value = _record(owner, reading=True)
    if (value.root, value.component, value.path) != (root, component, path):
        _fail("canonical selected endpoint differs from its actual owner")
    owner.require_current()


def _bind_plan(owner, plan):
    from .retained_layout_transaction import _PreparedSourceMovePlan

    value = _record(owner, reading=True)
    if (
        type(plan) is not _PreparedSourceMovePlan
        or value.plan is not None
        or plan.root != value.root
        or plan.layout.wrapper_root != value.component
        or plan.authored_lock != value.path
        or plan.authored_storage != value.identity.uri
    ):
        _fail("actual creating canonical source plan required")
    after = replace(value, plan=plan)
    _OWNERS[owner] = after
    _BINDINGS[owner] = _seal(after)


def _require_plan(plan):
    from .bounded_role_observation import current_role_observation

    reader = current_role_observation()
    if reader is None:
        _fail("actual active original canonical plan reader required")
    owner = _READERS.get(reader)
    actual = _record(owner, reading=True)
    if (
        actual.plan is not plan
        or actual.root != plan.root
        or actual.component != plan.layout.wrapper_root
        or actual.path != plan.authored_lock
        or actual.identity.uri != plan.authored_storage
    ):
        _fail("actual canonical plan binding changed")
    return owner


def _fold(path):
    return tuple(unicodedata.normalize("NFC", part.casefold()) for part in path.parts)


def _separate_effects(preparation, candidate_lineage):
    value = _record(_for_preparation(preparation), reading=True)
    candidate = Path(candidate_lineage[-1][0])
    native = candidate_lineage[-1][1:3]
    store = dict(value.paths)[value.storage]
    left, right = _fold(candidate), _fold(value.storage)
    if (
        left[: len(right)] == right
        or right[: len(left)] == left
        or native in {row[1:3] for row in value.anchor[1]}
        or (store is not None and store[:2] in {row[1:3] for row in candidate_lineage})
    ):
        _fail("private effects overlap original canonical storage")
    value.owner.close_native()


def _separate_project(preparation, tree):
    value = _record(_for_preparation(preparation))
    if value.path.is_relative_to(value.root):
        return
    identity = (
        None if value.snapshot.signature is None else value.snapshot.signature[:2]
    )
    store = dict(value.paths)[value.storage]
    for _name, node in tree._physical[1]:
        if node[:2] == identity or (store is not None and node[:2] == store[:2]):
            _fail("external canonical storage overlaps the actual project namespace")


def _end(preparation):
    original = _CREATED.pop(preparation, None)
    bound = _BOUND.pop(preparation, None)
    for owner in (original, bound):
        value = _OWNERS.get(owner)
        if value is not None and value.preparation is preparation:
            _OWNERS.pop(owner, None)
            _BINDINGS.pop(owner, None)
            if _READERS.get(value.reader) is owner:
                _READERS.pop(value.reader, None)
