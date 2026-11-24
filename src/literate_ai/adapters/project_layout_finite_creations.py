"""Original finite creation inputs and absence custody; never an effect grant.

Only the contained ignore file and the original bootstrap process helper are
eligible. Application files, arbitrary missing templates and decoded plans do
not join this inventory. A writer still needs the original observed selection,
same layout lease, journal and original no-replace publication owner.
"""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
import weakref
from dataclasses import dataclass, fields

from literate_ai._filesystem import stat_is_link_or_reparse
from literate_ai.adapters import project_scaffold_placement as scaffold
from literate_ai.adapters.project_layout_framework_observation import (
    _child_cursor,
    _named,
    _root_cursor,
)
from literate_ai.adapters.project_layout_framework_resources import (
    require_current_framework_resources,
    require_original_framework_resources,
)
from literate_ai.adapters.project_layout_framework_source_proofs import (
    require_original_initialized_framework_file_proof,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutPlanError,
    _capture,
)
from literate_ai.adapters.project_scaffold_transitions import (
    reviewed_bootstrap_transition,
)
from literate_ai.contracts import canonical_identity

_IGNORE = scaffold._FRAMEWORK_IGNORE
_HELPER = "scripts/_bootstrap_processes.py"
_BOOTSTRAP = "scripts/bootstrap_litai.py"
_RESOURCE_CURRENT = require_current_framework_resources
_RESOURCE_ORIGINAL = require_original_framework_resources
_PROOF_ORIGINAL = require_original_initialized_framework_file_proof
_TRANSITION = reviewed_bootstrap_transition
_CONSTANTS = tuple(
    (name, globals()[name]) for name in ("_IGNORE", "_HELPER", "_BOOTSTRAP")
)


def _fail(message):
    raise ProjectLayoutPlanError("framework_creation_unavailable", message)


def _alias(name):
    return unicodedata.normalize("NFC", name.casefold())


def _bootstrap_current(proof, resources):
    _PROOF_ORIGINAL(proof)
    if proof.resources is not resources or proof.logical != _BOOTSTRAP:
        _fail("helper requires the same original bootstrap source proof")
    nodes, contents = _capture(
        resources.snapshot.root, selected_scopes=(proof.source_path,)
    )
    if contents.get(proof.source_path) != proof.source_bytes or nodes.get(
        proof.source_path
    ) != dict(proof.native_observation):
        _fail("original bootstrap source changed before helper creation")


def _absence(resources, coordinate):
    """Observe missing frontier via original no-follow directory descriptors.

    No target-following exists/stat/open, private payload or missing descendant
    probe occurs. Existing parents and portable names are checked outer first.
    """
    root = resources.snapshot.root
    expected = resources.context.directory_binding[0][:3]
    parts = coordinate.split("/")
    witness = []

    def visit(cursor, index):
        names = os.listdir(cursor)
        if index and any(_alias(value) == ".git" for value in names):
            _fail("creation ancestry has independent Git authority")
        name = parts[index]
        aliases = [value for value in names if _alias(value) == _alias(name)]
        if not aliases:
            witness.append(("missing", "/".join(parts[: index + 1])))
            return
        if aliases != [name]:
            _fail("creation coordinate has a portable namespace alias")
        if index == len(parts) - 1:
            _fail("creation target already exists; equal bytes cannot replace it")
        native = _named(cursor, name)
        if not stat.S_ISDIR(native.st_mode) or stat_is_link_or_reparse(native):
            _fail("creation ancestry is not an original direct directory")
        identity = (native.st_dev, native.st_ino, native.st_mode)
        if native.st_dev != expected[0]:
            _fail("creation ancestor crosses the original filesystem")
        witness.append(("directory", "/".join(parts[: index + 1]), identity))
        with _child_cursor(
            cursor, name, root.joinpath(*parts[: index + 1]), identity
        ) as child:
            visit(child, index + 1)

    with _root_cursor(root, expected) as cursor:
        visit(cursor, 0)
    return tuple(witness)


@dataclass(frozen=True, slots=True, weakref_slot=True)
class OriginalFiniteFrameworkCreation:
    resources: object
    logical: str
    destination: str
    content: bytes
    mode: int
    bootstrap_proof: object
    coordinates: tuple
    absence: tuple
    identity: str


_FIELDS = tuple(field.name for field in fields(OriginalFiniteFrameworkCreation))
_CLASS = OriginalFiniteFrameworkCreation
_NAMESPACE = tuple(vars(_CLASS).items())
_BASES, _MRO = _CLASS.__bases__, _CLASS.__mro__
_FUNCTIONS = tuple(
    (name, globals()[name])
    for name in (
        "_root_cursor",
        "_child_cursor",
        "_named",
        "_absence",
        "_alias",
        "_bootstrap_current",
        "_capture",
        "stat_is_link_or_reparse",
        "_RESOURCE_CURRENT",
        "_RESOURCE_ORIGINAL",
        "_PROOF_ORIGINAL",
        "_TRANSITION",
    )
)


def _implementation_current():
    if (
        globals().get("OriginalFiniteFrameworkCreation") is not _CLASS
        or _CLASS.__bases__ is not _BASES
        or _CLASS.__mro__ is not _MRO
        or set(vars(_CLASS)) != {name for name, _value in _NAMESPACE}
        or any(vars(_CLASS)[name] is not value for name, value in _NAMESPACE)
        or any(globals().get(name) is not value for name, value in _FUNCTIONS)
        or any(globals().get(name) is not value for name, value in _CONSTANTS)
        or scaffold._FRAMEWORK_IGNORE is not _IGNORE
    ):
        _fail("original finite creation implementation changed")


def _admissions():
    registry = {}
    implementation_current = _implementation_current

    def require(owner):
        record = registry.get(id(owner))
        if record is None or record[0]() is not owner or record[2] != os.getpid():
            _fail("original same-process finite creation factory required")
        implementation_current()
        if any(
            object.__getattribute__(owner, name) is not value
            for name, value in zip(_FIELDS, record[1], strict=True)
        ):
            _fail("original finite creation data changed")
        _RESOURCE_ORIGINAL(record[1][0])
        return record[1]

    def register(owner):
        key = id(owner)

        def release(dead):
            old = registry.get(key)
            if old is not None and old[0] is dead:
                registry.pop(key, None)

        registry[key] = (
            weakref.ref(owner, release),
            tuple(object.__getattribute__(owner, name) for name in _FIELDS),
            os.getpid(),
        )
        require(owner)

    def close(owner):
        old = registry.get(id(owner))
        if old is not None and old[0]() is owner:
            registry.pop(id(owner), None)

    return register, require, close


_register, _require, close_original_finite_framework_creation = _admissions()


def require_original_finite_framework_creation(owner):
    _require(owner)


def require_current_finite_framework_creation(owner):
    admit = _require
    values = admit(owner)
    resources, logical, destination = values[:3]
    _RESOURCE_CURRENT(resources)
    admit(owner)
    if logical == _HELPER:
        _bootstrap_current(values[5], resources)
    original = values[7]
    current = (_absence(resources, destination),)
    if logical == _HELPER:
        current += (_absence(resources, logical),)
    if current != original:
        _fail("original finite creation absence frontier changed")
    _RESOURCE_CURRENT(resources)
    admit(owner)
    # Last resource callback is behind us; close all native absence facts again.
    if logical == _HELPER:
        _bootstrap_current(values[5], resources)
    closing = (_absence(resources, destination),)
    if logical == _HELPER:
        closing += (_absence(resources, logical),)
    if closing != original:
        _fail("finite creation namespace changed during closing")
    admit(owner)


def observe_original_finite_framework_creation(
    resources, logical, *, bootstrap_proof=None, coordinate_map=None
):
    implementation_current = _implementation_current
    retire = close_original_finite_framework_creation
    implementation_current()
    _RESOURCE_ORIGINAL(resources)
    if type(logical) is not str or logical not in (".gitignore", _HELPER):
        _fail("creation is outside the finite original inventory")
    _RESOURCE_CURRENT(resources)
    implementation_current()
    if logical == ".gitignore":
        if bootstrap_proof is not None or coordinate_map is not None:
            _fail("ignore creation accepts no bootstrap attachment")
        content, coordinates = _IGNORE, ()
    else:
        _PROOF_ORIGINAL(bootstrap_proof)
        if (
            bootstrap_proof.resources is not resources
            or bootstrap_proof.logical != _BOOTSTRAP
        ):
            _fail("helper requires the same original bootstrap source proof")
        if type(coordinate_map) is not dict:
            _fail("original bootstrap coordinate projection required")
        if (
            coordinate_map.get(_HELPER) != "litai/" + _HELPER
            or coordinate_map.get(_BOOTSTRAP) != "litai/" + _BOOTSTRAP
        ):
            _fail("original bootstrap/helper must share their contained directory")
        content = resources.files[_HELPER]
        _TRANSITION(
            bootstrap_proof.source_bytes,
            original_before_bytes=bootstrap_proof.base_bytes,
            original_after_bytes=resources.files[_BOOTSTRAP],
            before_sha256=hashlib.sha256(bootstrap_proof.base_bytes).hexdigest(),
            after_sha256=hashlib.sha256(resources.files[_BOOTSTRAP]).hexdigest(),
            coordinate_map=coordinate_map,
            original_helper_bytes=content,
            helper_sha256=hashlib.sha256(content).hexdigest(),
        )
        coordinates = tuple(sorted(coordinate_map.items()))
    destination = "litai/" + logical
    absence = (_absence(resources, destination),)
    if logical == _HELPER:
        absence += (_absence(resources, logical),)
    identity = canonical_identity(
        {
            "domain": "original-finite-framework-creation-v1",
            "resource_selection": resources.identity,
            "logical": logical,
            "destination": destination,
            "content": "sha256:" + hashlib.sha256(content).hexdigest(),
            "mode": 0o644,
            "coordinates": dict(coordinates),
        }
    ).uri
    owner = OriginalFiniteFrameworkCreation(
        resources,
        logical,
        destination,
        content,
        0o644,
        bootstrap_proof,
        coordinates,
        absence,
        identity,
    )
    try:
        _register(owner)
        require_current_finite_framework_creation(owner)
    except BaseException:
        retire(owner)
        raise
    return owner


_FUNCTIONS += tuple(
    (name, globals()[name])
    for name in (
        "_implementation_current",
        "_register",
        "_require",
        "close_original_finite_framework_creation",
        "require_current_finite_framework_creation",
    )
)
