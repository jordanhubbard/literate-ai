"""Original complete project facts and receipt-backed control projection.

The acknowledged namespace is immutable. Only actual publications from the
creating live pool, joined to canonical acquired descriptors, can produce its
controlled view. Neither a census nor a saved projection grants effect rights.
"""

from __future__ import annotations

import hashlib
import os
import stat
import threading
from dataclasses import dataclass, fields, replace

from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)

from .bounded_role_observation import current_role_observation
from .exclusive_entry import _from_stat, layout_entry_node
from .repository_refresh_reservations import _custody_wire

_KEY = object()
_OWNERS = {}
_PREPARATIONS = {}
_CREATED = {}
_READERS = {}
_SEALS = {}


def _fail(message):
    raise ValueError("layout.source-namespace: " + message)


@dataclass(frozen=True, slots=True)
class _Record:
    owner: object
    preparation: object
    root: object
    reader: object
    ledger: object
    census: object
    native: tuple
    identity: object
    pid: int
    thread: int
    plan: object = None
    controlled: object = None
    controlled_native: object = None
    controls: object = None
    control_binding: object = None
    publications: object = None


def _seal(value):
    return (
        tuple(getattr(value, item.name) for item in fields(_Record)),
        canonical_json_bytes(
            _custody_wire(
                (
                    value.census,
                    value.native,
                    value.identity,
                    value.controlled,
                    value.controlled_native,
                )
            )
        ),
    )


def _fact_refs(value):
    """Retain bounded original objects, never enumerate a replacement roster."""
    objects = [value.census, value.identity]
    for tree in (value.census.tree, value.controlled):
        if tree is not None:
            objects.extend((tree, tree.budget))
            objects.extend(blob for _name, blob, _mode in tree.files)
            objects.extend(tree.aliases)
    for native in (value.native, value.controlled_native):
        if native is not None:
            objects.extend(node for _name, node in native)
    unique = {id(obj): obj for obj in objects}
    return tuple(
        (obj, tuple((f.name, getattr(obj, f.name)) for f in fields(obj)))
        for obj in unique.values()
    )


def _sealed_record(value):
    return (
        value,
        _seal(value),
        (value.identity.algorithm, value.identity.digest),
        _fact_refs(value),
    )


def _require_fact_refs(seal):
    if any(
        getattr(obj, name) is not old
        for obj, observed in seal[3]
        for name, old in observed
    ):
        _fail("original namespace facts changed")


def _record(owner, *, reading=False, deep=False, references=False):
    from .retained_layout_source_preparation import _LIVE, _SourcePreparation

    value = _OWNERS.get(owner)
    seal = _SEALS.get(owner)
    if (
        type(owner) is not _Namespace
        or type(value) is not _Record
        or type(seal) is not tuple
        or len(seal) != 4
    ):
        _fail("actual original namespace participant required")
    refs = tuple(getattr(value, item.name) for item in fields(_Record))
    if (
        seal[0] is not value
        or any(a is not b for a, b in zip(refs, seal[1][0], strict=True))
        or type(value.identity) is not ContentIdentity
        or type(value.identity.digest) is not str
        or value.identity.algorithm is not seal[2][0]
        or value.identity.digest != seal[2][1]
    ):
        _fail("original namespace record changed")
    if reading or deep:
        _require_fact_refs(seal)
        if _seal(value)[1] != seal[1][1]:
            _fail("original namespace facts changed")
    original = _LIVE.get(value.preparation)
    if (
        value.owner is not owner
        or _PREPARATIONS.get(value.preparation) is not owner
        or _CREATED.get(value.preparation) is not owner
        or _READERS.get(value.reader) is not owner
        or type(value.preparation) is not _SourcePreparation
        or original is None
        or original.root != value.root
        or original.reader is not value.reader
        or original.ledger is not value.ledger
        or (value.pid, value.thread) != (os.getpid(), threading.get_ident())
        or (original.plan is not None and original.plan is not value.plan)
        or (reading and current_role_observation() is not value.reader)
    ):
        _fail("original namespace lifetime or reader ended")
    value.reader._live()
    if reading or deep or references:
        _require_fact_refs(seal)
    if _OWNERS.get(owner) is not value or _SEALS.get(owner) is not seal:
        _fail("original namespace registration changed during closure")
    return value


def _advance(owner, before, **changes):
    from .component_lock_observation import _require_plan as require_storage_plan
    from .retained_layout_transaction import _PreparedSourceMovePlan

    if _record(owner, reading=True) is not before:
        _fail("original namespace predecessor changed")
    # This gateway binds exactly one actual creating plan. It can never replace
    # original facts or accept caller-supplied controlled views. Control views
    # are derived and installed only by the verified descriptor transition below.
    if (
        before.plan is not None
        or before.controlled is not None
        or len(changes) != 1
        or "plan" not in changes
    ):
        _fail("immutable original namespace cannot be advanced")
    plan = changes["plan"]
    if type(plan) is not _PreparedSourceMovePlan or not _matches_plan(before, plan):
        _fail("actual creating namespace plan required")
    require_storage_plan(plan)
    after = replace(before, **changes)
    _OWNERS[owner], _SEALS[owner] = after, _sealed_record(after)
    return after


class _Namespace:
    __slots__ = ()

    def __init__(self, key):
        if key is not _KEY:
            raise TypeError("actual creating source namespace required")

    @property
    def identity(self):
        return _record(self).identity

    def require_current(self):
        value = _record(self, reading=True)
        tree, _native = _view(value)
        tree.require_unchanged()
        self.close_native()
        if _record(self, reading=True) is not value:
            _fail("original namespace changed during observation")

    def close_native(self):
        from .retained_layout_transaction import _close_tree

        value = _record(self, deep=True)
        tree, native = _view(value)
        _close_tree(
            tree,
            native,
            controls=value.controls,
            _namespace_preparation=value.preparation,
        )
        if _record(self, references=True) is not value:
            _fail("original namespace changed during native closure")


def observe_project_namespace(preparation):
    from .retained_layout_source_preparation import _state

    original = _state(preparation, ready=False)
    if (
        original.plan is not None
        or current_role_observation() is not original.reader
        or preparation in _PREPARATIONS
        or preparation in _CREATED
        or original.reader in _READERS
    ):
        _fail("one actual creating source reader required")
    census = original.ledger.capture(original.root)
    if original.ledger.censuses[-1] is not census:
        _fail("actual original funded census required")
    native = original.ledger.native[-1]
    count = 1 + len(native)
    size = (
        65536
        + 512 * count
        + 32 * sum(len(str(original.root / n).encode()) for n, _ in native)
    )
    original.ledger.charge_records(16 + 6 * count, size)
    owner = _Namespace(_KEY)
    identity = canonical_identity(
        {
            "schema": "literate-ai/original-project-namespace@1",
            "namespace": census.identity.uri,
            "native": canonical_identity(_custody_wire(native)).uri,
        }
    )
    value = _Record(
        owner,
        preparation,
        original.root,
        original.reader,
        original.ledger,
        census,
        native,
        identity,
        os.getpid(),
        threading.get_ident(),
    )
    _OWNERS[owner], _SEALS[owner] = value, _sealed_record(value)
    _PREPARATIONS[preparation], _READERS[original.reader] = owner, owner
    _CREATED[preparation] = owner
    owner.require_current()
    return owner


def _bind_plan(owner, plan):
    from .retained_layout_transaction import _PreparedSourceMovePlan

    value = _record(owner, reading=True)
    if (
        type(plan) is not _PreparedSourceMovePlan
        or value.plan is not None
        or not _matches_plan(value, plan)
    ):
        _fail("actual creating namespace plan required")
    _advance(owner, value, plan=plan)


def _require_registration(preparation, original):
    value = _record(_PREPARATIONS.get(preparation))
    if value.plan is not original.plan or not _matches_plan(value, value.plan):
        _fail("original acknowledged namespace plan changed")
    return value


def _require_plan(plan):
    value = _record(_READERS.get(current_role_observation()), reading=True)
    if value.plan is not plan or not _matches_plan(value, plan):
        _fail("actual original namespace plan binding required")
    return value.owner


def _matches_plan(value, plan):
    return (
        type(plan.root) is type(value.root)
        and plan.root == value.root
        and type(plan.project_namespace) is str
        and plan.project_namespace == value.identity.uri
    )


def _view(value):
    if value.controls is not None:
        from .retained_layout_control_publication import _publication_history
        from .retained_layout_control_roles import _require_acquired_control_roles

        if (
            _require_acquired_control_roles(value.controls, value.root)
            is not value.control_binding
            or _publication_history(value.controls._pool) is not value.publications
        ):
            _fail("original controlled namespace participants changed or ended")
    return (
        (value.census.tree, value.native)
        if value.controlled is None
        else (value.controlled, value.controlled_native)
    )


def _current_view(preparation):
    return _view(_record(_PREPARATIONS.get(preparation), deep=True))


def _require_tree(preparation, tree, native, controls):
    value = _record(_PREPARATIONS.get(preparation), deep=True)
    expected = _view(value)
    if (
        tree is not expected[0]
        or native is not expected[1]
        or controls is not value.controls
    ):
        _fail("actual complete namespace closure required")


def _close_inputs(preparation, tree, native):
    from .component_lock_observation import _for_preparation
    from .retained_layout_transaction import _close_authored

    value = _record(_PREPARATIONS.get(preparation), deep=True)
    expected = _view(value)
    if tree is not expected[0] or native is not expected[1]:
        _fail("actual complete namespace closure required")
    value.reader._close_native_inputs()
    if value.plan is not None:
        _close_authored(value.plan)
    _for_preparation(preparation).close_native()
    _record(value.owner, references=True)


def _file_physical(node):
    return (
        node.device,
        node.inode,
        node.mode,
        node.size,
        node.modified_ns,
        node.changed_ns,
        node.links,
        node.uid,
        node.gid,
    )


def _accept_controls(preparation, controls):
    from .retained_layout_control_publication import _publication_history
    from .retained_layout_control_roles import (
        _project_roles,
        _require_acquired_control_roles,
    )
    from .retained_layout_source_admission import _record as require_source_admission

    value = _record(_PREPARATIONS.get(preparation), reading=True)
    if value.plan is None or value.controlled is not None:
        _fail("one original namespace control projection required")
    admission = require_source_admission(preparation)
    if (
        admission.original.plan is not value.plan
        or admission.pool is not controls._pool
        or admission.controls is not controls
    ):
        _fail("actual original source control admission required")
    control_binding = _require_acquired_control_roles(controls, value.root)
    publications = _publication_history(controls._pool)
    targets = {
        t.path: t
        for t in (*_project_roles(value.root).targets(), *value.plan.git.targets())
    }
    markers = {m.target.path: m for m in controls.reservations._markers}
    if (
        len(markers) != len(controls.reservations._markers)
        or markers.keys() != targets.keys()
        or any(m.target != targets[p] for p, m in markers.items())
    ):
        _fail("exact canonical acquired descriptor roster required")
    tree, known = value.census.tree, dict(value.native)
    added_files, added_dirs = set(), set()
    for path, marker in markers.items():
        if not path.is_relative_to(value.root):
            continue
        name = path.relative_to(value.root).as_posix()
        if marker.created != (name not in known):
            _fail("canonical marker creation contradicts original namespace")
        if marker.created:
            added_files.add(name)
        elif known[name] != controls.reservations._expected[path]:
            _fail("existing canonical marker changed since acknowledgement")
        parent = path.parent
        while parent != value.root:
            relative = parent.relative_to(value.root).as_posix()
            if relative not in known:
                added_dirs.add(relative)
            elif not stat.S_ISDIR(known[relative].mode):
                _fail("canonical parent was not an original directory")
            parent = parent.parent
    actual_dirs = {
        p.relative_to(value.root).as_posix()
        for p, _, _ in controls.reservations._directories
        if p.is_relative_to(value.root)
    }
    if actual_dirs != added_dirs:
        _fail("canonical directory creation contradicts original namespace")
    # Fund new retained maps, seals and both enlarged recapture windows before
    # allocating the controlled projection. The original census stays immutable.
    count = len(known) + len(added_files) + len(added_dirs)
    increment = sum(
        65536 + 512 * len(str(value.root / n).encode())
        for n in added_files | added_dirs
    )
    value.ledger.charge_records(
        32 + 6 * count,
        65536
        + 512 * count
        + 32 * sum(len(str(value.root / n).encode()) for n in known),
    )
    value.ledger.charged += 2 * increment
    value.ledger.require_capacity()
    files = {n: (blob, mode) for n, blob, mode in tree.files}
    physical = dict(tree._physical[1])
    directories, seen = set(tree.directories), set()
    for receipt in publications:
        path = receipt.path
        if not path.is_relative_to(value.root):
            if path not in targets:
                _fail("publication lies outside canonical control roles")
            continue
        name = path.relative_to(value.root).as_posix()
        if name in seen or name not in added_files | added_dirs:
            _fail("publication lacks its exact original absent canonical role")
        parent = path.parent.relative_to(value.root).as_posix()
        parent = "" if parent == "." else parent
        if (
            known.get(parent) != receipt.parent_before
            or receipt.parent_after.directory_identity
            != receipt.parent_before.directory_identity
        ):
            _fail("publication parent differs from original namespace projection")
        if receipt.node.after_rename() != receipt.staged_node.after_rename():
            _fail("publication lost original staged custody")
        known[name], known[parent] = receipt.node, receipt.parent_after
        if name in added_dirs:
            if receipt.content is not None or not stat.S_ISDIR(receipt.node.mode):
                _fail("canonical directory lacks actual staged directory custody")
            directories.add(name)
            physical[name] = (
                receipt.node.device,
                receipt.node.inode,
                receipt.node.mode,
                receipt.node.uid,
                receipt.node.gid,
            )
        else:
            marker = markers[path]
            if (
                receipt.content != marker.content
                or receipt.node != controls.reservations._expected[path]
            ):
                _fail("canonical marker differs from original publication")
            files[name] = (
                BlobRef(
                    hashlib.sha256(marker.content).hexdigest(), len(marker.content)
                ),
                bool(receipt.node.mode & 0o111),
            )
            physical[name] = _file_physical(receipt.node)
        seen.add(name)
    if seen != added_files | added_dirs:
        _fail("canonical controls lack actual original publication receipts")
    for path, marker in markers.items():
        node = controls.reservations._expected[path]
        if (
            _from_stat(os.fstat(marker.descriptor)) != node
            or layout_entry_node(path) != node
            or os.pread(marker.descriptor, len(marker.content) + 1, 0) != marker.content
        ):
            _fail("actual canonical descriptor changed during namespace projection")
    controls.reservations._held.current()
    projected = replace(
        tree,
        directories=tuple(sorted(directories)),
        files=tuple(sorted((n, *data) for n, data in files.items())),
        maximum_metadata_bytes=tree.maximum_metadata_bytes + increment,
        _physical=(tree._physical[0], tuple(sorted(physical.items()))),
    )
    if (
        projected.entry_count > tree.budget.maximum_entries
        or projected.file_count > tree.budget.maximum_files
        or projected.payload_bytes > tree.budget.maximum_total_bytes
    ):
        _fail("controlled namespace exceeds its original funded view policy")
    # Closing issuer/descriptor/registration checks precede the sole controlled
    # transition. No general-purpose resealing helper accepts these derived facts.
    if (
        _record(value.owner, reading=True) is not value
        or require_source_admission(preparation) is not admission
        or _require_acquired_control_roles(controls, value.root) is not control_binding
        or _publication_history(controls._pool) is not publications
        or admission.controls is not controls
        or admission.control_binding is not control_binding
    ):
        _fail("original source control transition changed")
    after = replace(
        value,
        controlled=projected,
        controlled_native=tuple(
            sorted(known.items(), key=lambda item: (item[0] != "", item[0]))
        ),
        controls=controls,
        control_binding=control_binding,
        publications=publications,
    )
    _OWNERS[value.owner], _SEALS[value.owner] = after, _sealed_record(after)
    value.owner.require_current()
    if _publication_history(controls._pool) is not after.publications:
        _fail("original publication history advanced during projection")


def _require_matching_view(preparation, tree, native):
    expected, expected_native = _current_view(preparation)
    normalized = replace(
        tree,
        budget=expected.budget,
        maximum_metadata_bytes=expected.maximum_metadata_bytes,
    )
    if (
        normalized != expected
        or tree._physical != expected._physical
        or native != expected_native
    ):
        _fail("complete project differs from its acknowledged namespace projection")


def _end(preparation):
    owner = _CREATED.pop(preparation, None)
    _PREPARATIONS.pop(preparation, None)
    value = _OWNERS.pop(owner, None)
    _SEALS.pop(owner, None)
    if value is not None and _READERS.get(value.reader) is owner:
        _READERS.pop(value.reader, None)
