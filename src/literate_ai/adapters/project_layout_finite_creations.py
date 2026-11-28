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
    _MAX_ENTRIES,
    _MAX_TOTAL_BYTES,
    ProjectLayoutPlanError,
    _capture,
)
from literate_ai.adapters.project_scaffold_transitions import (
    reviewed_bootstrap_transition,
)
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

_IGNORE = scaffold._FRAMEWORK_IGNORE
_HELPER = "scripts/_bootstrap_processes.py"
_BOOTSTRAP = "scripts/bootstrap_litai.py"
_RESOURCE_CURRENT = require_current_framework_resources
_RESOURCE_ORIGINAL = require_original_framework_resources
_PROOF_ORIGINAL = require_original_initialized_framework_file_proof
_TRANSITION = reviewed_bootstrap_transition
_CONSTANTS = tuple(
    (name, globals()[name])
    for name in ("_IGNORE", "_HELPER", "_BOOTSTRAP", "_MAX_ENTRIES", "_MAX_TOTAL_BYTES")
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
    return _absence_at(
        resources.snapshot.root, resources.context.directory_binding[0][:3], coordinate
    )


def _absence_at(root, expected, coordinate, *, _costs=False, _limits=None):
    """Observe missing frontier via original no-follow directory descriptors.

    No target-following exists/stat/open, private payload or missing descendant
    probe occurs. Existing parents and portable names are checked outer first.
    """
    parts = coordinate.split("/")
    witness = []
    charged_entries = charged_bytes = 0

    def visit(cursor, index):
        nonlocal charged_entries, charged_bytes
        names = []
        with os.scandir(cursor) as entries:
            for entry in entries:
                charged_entries += 1
                if _limits is not None and charged_entries > _limits[0]:
                    _fail("shadow closing census exceeds its funded entry bound")
                charged_bytes += len(os.fsencode(entry.name))
                if _limits is not None and charged_bytes > _limits[1]:
                    _fail("shadow closing census exceeds its funded name-byte bound")
                if charged_entries > _MAX_ENTRIES or charged_bytes > _MAX_TOTAL_BYTES:
                    _fail("creation absence observation exceeds its census bound")
                names.append(entry.name)
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
    result = tuple(witness)
    return (result, charged_entries, charged_bytes) if _costs else result


def _retained_metadata_absence(root, expected, coordinate, *, charge=None):
    return _retained_metadata_absences(root, expected, (coordinate,), charge=charge)[0]


def _retained_metadata_absences(root, expected, coordinates, *, charge=None):
    """Finite read-only shadow frontier, without opening a leaf or granting effects."""
    if type(coordinates) is not tuple or len(coordinates) > 8192:
        _fail("finite original retained metadata coordinates required")
    for coordinate in coordinates:
        _retained_metadata_coordinate(coordinate)
    if charge is None:
        return tuple(_absence_at(root, expected, name) for name in coordinates)
    before, entries, name_bytes = [], 0, 0
    for name in coordinates:
        row = _absence_at(
            root,
            expected,
            name,
            _costs=True,
            _limits=(_MAX_ENTRIES - entries, _MAX_TOTAL_BYTES - name_bytes),
        )
        before.append(row)
        entries += row[1]
        name_bytes += row[2]
    before = tuple(before)
    # Reserve both censuses and one detection entry per closing scan. The final
    # native pass invokes no callback and refuses a larger unfunded census.
    charge(
        2 * entries + len(before), 2 * (128 * entries + name_bytes) + 128 * len(before)
    )
    after = tuple(
        _absence_at(root, expected, name, _limits=(row[1], row[2]))
        for name, row in zip(coordinates, before, strict=True)
    )
    if after != tuple(row[0] for row in before):
        _fail("retained metadata shadow frontier changed during accounting")
    return after


def _retained_metadata_coordinate(coordinate):
    if type(coordinate) is not str or len(coordinate.encode("utf-8")) > 4096:
        _fail("bounded retained metadata shadow coordinate required")
    canonical_relative_posix_path(coordinate, label="retained metadata shadow")
    parts = coordinate.split("/")
    if (
        len(parts) > 64
        or not (
            coordinate == "litai.harness.mk"
            or coordinate.startswith("components/legacy-project-wrapper/")
        )
        or coordinate == "components/legacy-project-wrapper/implementation"
        or coordinate.startswith("components/legacy-project-wrapper/implementation/")
        or any(
            part.casefold()
            in {".git", ".ssh", ".aws", ".azure", ".env", "credentials.json"}
            for part in parts
        )
    ):
        _fail("shadow observation is outside retained metadata")


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
        "_absence_at",
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
_ABSENCE_CODES = tuple(
    (
        function,
        function.__code__,
        function.__defaults__,
        function.__kwdefaults__,
        tuple((function.__kwdefaults__ or {}).items()),
    )
    for function in (_absence, _absence_at)
)


def _implementation_current():
    if (
        globals().get("OriginalFiniteFrameworkCreation") is not _CLASS
        or _CLASS.__bases__ is not _BASES
        or _CLASS.__mro__ is not _MRO
        or set(vars(_CLASS)) != {name for name, _value in _NAMESPACE}
        or any(vars(_CLASS)[name] is not value for name, value in _NAMESPACE)
        or any(globals().get(name) is not value for name, value in _FUNCTIONS)
        or any(
            function.__code__ is not code
            or function.__defaults__ is not defaults
            or function.__kwdefaults__ is not keywords
            or len(function.__kwdefaults__ or {}) != len(items)
            or any(
                (function.__kwdefaults__ or {}).get(key) is not value
                for key, value in items
            )
            for function, code, defaults, keywords, items in _ABSENCE_CODES
        )
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


def _bind_original_destination_absence(
    absence, implementation_current, admit, relative
):
    namespace = globals()
    error = ProjectLayoutPlanError
    bindings = tuple(
        (name, namespace[name])
        for name in (
            "_fail",
            "_absence",
            "_alias",
            "_implementation_current",
            "_RESOURCE_ORIGINAL",
            "_FUNCTIONS",
            "_CONSTANTS",
            "_bind_original_destination_absence",
        )
    )

    def current():
        if any(namespace.get(name) is not value for name, value in bindings) or (
            namespace.get("observe_original_framework_destination_absence")
            is not observe_original_framework_destination_absence
        ):
            raise error(
                "framework_creation_unavailable", "original destination reader changed"
            )
        implementation_current()

    def observe_original_framework_destination_absence(resources, coordinates):
        """Return native missing frontiers only; never issue an effect grant.

        Callers select exact planned targets from original source ownership.
        Read only ancestor names/directories; never stat/open an occupied leaf.
        The original native reader is shared with the two finite creation owners.
        """
        current()
        admit(resources)
        if (
            type(coordinates) is not tuple
            or len(coordinates) > 8192
            or any(type(path) is not str for path in coordinates)
            or len(set(coordinates)) != len(coordinates)
        ):
            _fail("bounded original destination coordinate tuple required")
        result = []
        for path in coordinates:
            relative(path, label="original framework destination")
            if not path.startswith("litai/") or ".git" in path.split("/"):
                _fail("original destination must remain in contained authority")
            current()
            result.append((path, absence(resources, path)))
            current()
        admit(resources)
        current()
        return tuple(result)

    return observe_original_framework_destination_absence


observe_original_framework_destination_absence = _bind_original_destination_absence(
    _absence, _implementation_current, _RESOURCE_ORIGINAL, canonical_relative_posix_path
)


def _bind_retained_metadata_reader():
    """Seal this finite read graph once, independently of creation admission."""
    import builtins
    from types import CodeType, FunctionType, ModuleType

    from literate_ai import _cache_lock as windows
    from literate_ai.adapters import project_layout_framework_observation as cursors

    namespace = globals()
    roots = {
        "retained_metadata_absence": _retained_metadata_absence,
        "retained_metadata_absences": _retained_metadata_absences,
    }
    pending = [
        *roots.values(),
        _retained_metadata_coordinate,
        _absence_at,
        _alias,
        _fail,
        canonical_relative_posix_path,
        stat_is_link_or_reparse,
        _root_cursor,
        _child_cursor,
        _named,
        cursors._identity,
        cursors._fail,
    ]
    if os.name == "nt":
        pending.extend(
            (
                cursors._windows_directory,
                windows._default_windows_kernel32,
                windows._Kernel32Windows.__init__,
                windows._Kernel32Windows.open_reparse_aware,
                windows._Kernel32Windows.close,
            )
        )
    functions, slots = {}, {}

    def slot(scope, name):
        slots[id(scope), name] = (scope, name, name in scope, scope.get(name))

    def names(code):
        result = set(code.co_names)
        for constant in code.co_consts:
            if type(constant) is CodeType:
                result.update(names(constant))
        return result

    while pending:
        function = pending.pop()
        if function in functions:
            continue
        if type(function) is not FunctionType:
            raise ValueError(
                "original retained metadata Python implementation required"
            )
        wrapped = vars(function).get("__wrapped__")
        functions[function] = (
            function.__code__,
            function.__defaults__,
            function.__kwdefaults__,
            tuple((function.__kwdefaults__ or {}).items()),
            wrapped,
        )
        if wrapped is not None:
            pending.append(wrapped)
        scope, used = function.__globals__, names(function.__code__)
        # Both the defining export and imported aliases remain original.
        if scope.get(function.__name__) is function:
            slot(scope, function.__name__)
        for name in used:
            if name in scope or hasattr(builtins, name):
                slot(scope, name)
                if name not in scope and name in function.__builtins__:
                    slot(function.__builtins__, name)
            value = scope.get(name)
            if type(value) is FunctionType:
                pending.append(value)
            if type(value) is ModuleType:
                for attribute in used:
                    if attribute in vars(value):
                        slot(vars(value), attribute)
                        delegate = vars(value)[attribute]
                        if type(delegate) is FunctionType:
                            pending.append(delegate)
    for name in ("_MAX_ENTRIES", "_MAX_TOTAL_BYTES"):
        slot(namespace, name)
    for name in ("O_RDONLY", "O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC"):
        slot(vars(os), name)
    if os.name == "nt":
        slot(vars(windows), "_default_windows_kernel32")
        for name in ("__init__", "open_reparse_aware", "close"):
            slot(vars(windows._Kernel32Windows), name)
    function_rows = tuple((fn, *row) for fn, row in functions.items())
    slot_rows, exports = tuple(slots.values()), {}
    size, some, exact, text, failure, mapping = len, any, type, str, ValueError, vars

    def check():
        for scope, name, present, value in slot_rows:
            if (name in scope) is not present or scope.get(name) is not value:
                raise failure("original retained metadata read dependency changed")
        for fn, code, defaults, keywords, items, wrapped in function_rows:
            actual = fn.__kwdefaults__
            if (
                fn.__code__ is not code
                or fn.__defaults__ is not defaults
                or actual is not keywords
                or size(actual or {}) != size(items)
                or some(exact(key) is not text for key in (actual or {}))
                or some((actual or {}).get(key) is not value for key, value in items)
                or mapping(fn).get("__wrapped__") is not wrapped
            ):
                raise failure("original retained metadata read implementation changed")
        for name, (function, code) in exports.items():
            if (
                namespace.get(name) is not function
                or function.__code__ is not code
                or function.__defaults__ is not None
                or function.__kwdefaults__ is not None
            ):
                raise failure("original retained metadata read boundary changed")

    check_code = check.__code__

    def current():
        if (
            check.__code__ is not check_code
            or check.__defaults__ is not None
            or check.__kwdefaults__ is not None
        ):
            raise failure("original retained metadata read checker changed")
        check()

    current_code = current.__code__

    def checked():
        if (
            current.__code__ is not current_code
            or current.__defaults__ is not None
            or current.__kwdefaults__ is not None
        ):
            raise failure("original retained metadata read guard changed")
        current()

    def bind(function):
        def call(*args, **kwargs):
            checked()
            charge = kwargs.get("charge")
            if charge is not None:

                def accounting(*values):
                    checked()
                    result = charge(*values)
                    checked()
                    return result

                kwargs["charge"] = accounting
            result = function(*args, **kwargs)
            checked()
            return result

        return call

    for name, function in roots.items():
        port = bind(function)
        exports[name] = (port, port.__code__)
    exports["retained_metadata_absence_guard"] = (current, current.__code__)
    return {name: function for name, (function, _code) in exports.items()}


globals().update(_bind_retained_metadata_reader())
del _bind_retained_metadata_reader
