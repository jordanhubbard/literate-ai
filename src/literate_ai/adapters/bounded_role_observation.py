"""Operation-local finite canonical metadata reads; never mutation authority."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_CURRENT = ContextVar("bounded-role-observation", default=None)
_ACTIVATION = ContextVar("bounded-role-activation", default=None)
_KEY = object()
_OPERATIONS = {}
_ACTIVE = {}


def _fail(message):
    raise ValueError("layout.role-inputs: " + message)


def current_role_observation():
    value = _CURRENT.get()
    if value is not None:
        if type(value) is not _RoleObservation:
            raise TypeError("actual bounded role read scope required")
        value._live()
        if _ACTIVATION.get() is None or _ACTIVE.get(value) is not _ACTIVATION.get():
            _fail("original read activation ended")
    return value


class _RoleObservation:
    def __init__(self, key, ledger):
        if key is not _KEY:
            raise TypeError("actual bounded role read scope required")
        self._ledger = ledger
        self._pid, self._active, self._poisoned = os.getpid(), True, False
        self._thread, self._io_active = threading.get_ident(), False
        self._lineage_allowances, self._lineages = set(), {}
        # None is a prepaid slot, not a currentness observation. Completed
        # slots retain immutable native rows shared by endpoint tuples.
        self._lineage_rows = {}
        self._presences = {}

    @property
    def budget(self):
        return self._ledger.budget

    def _live(self):
        if (
            not self._active
            or self._pid != os.getpid()
            or self._poisoned
            or self._thread != threading.get_ident()
        ):
            _fail("read scope ended, inherited or exhausted")
        original = _OPERATIONS.get(self)
        if (
            original is None
            or original[0] is not self._ledger
            or original[3] is not self._ledger.budget
            or original[4] != self._ledger.metadata
            or original[5] != self._ledger.reserve
            or original[9] is not self._lineage_rows
            or type(self._lineage_rows) is not dict
        ):
            self._poisoned = True
            _fail("original canonical read policy changed")
        self._ledger.require_capacity()

    def _begin_io(self):
        self._live()
        if current_role_observation() is not self:
            _fail("actual active canonical read scope required")
        if self._io_active:
            self._poisoned = True
            _fail("reentrant role I/O cannot borrow the shared allowance")
        self._io_active = True

    def reserve_lineage(self, path):
        self._live()
        if path in self._lineage_allowances:
            return
        try:
            # Fund endpoint/reference containers separately from unique rows.
            # Reservations also precede controlled creation and source moves.
            self._ledger.charge_records(2)
            size = 0
            missing = 0
            for parent in path.parents:
                size += len(str(parent).encode("utf-8"))
                if 128 * size > self._ledger.metadata - self._ledger.charged:
                    _fail("ancestry exceeds shared metadata allowance")
                missing += str(parent) not in self._lineage_rows
            size += len(str(path).encode("utf-8"))
            missing += str(path) not in self._lineage_rows
            self._ledger.charge_records(2 * missing)
            # Keep the full original byte prepayment for endpoint reference
            # arrays and freshly acquired transient native observations.
            self._ledger.charged += 128 * size
            self._ledger.require_capacity()
            for parent in path.parents:
                self._lineage_rows.setdefault(str(parent), None)
            self._lineage_rows.setdefault(str(path), None)
            self._lineage_allowances.add(path)
        except BaseException:
            self._poisoned = True
            raise

    def remember_lineage(self, path, value):
        self._live()
        try:
            if (
                path not in self._lineage_allowances
                or type(value) is not tuple
                or len(value) != len(path.parents) + 1
                or any(
                    type(row) is not tuple
                    or len(row) != 6
                    or type(row[0]) is not str
                    or any(type(part) is not int for part in row[1:])
                    for row in value
                )
            ):
                _fail("actual funded original ancestry rows required")
            if path in self._lineages and self._lineages[path] != value:
                _fail("original role ancestry changed")
            # Validate every fresh row before retaining any. A prepaid None
            # never provides native facts or skips the original fresh walk.
            for row in value:
                if row[0] not in self._lineage_rows:
                    _fail("original ancestry row lacks its reservation")
                previous = self._lineage_rows[row[0]]
                if previous is not None and (
                    type(previous) is not tuple
                    or len(previous) != 6
                    or type(previous[0]) is not str
                    or any(type(part) is not int for part in previous[1:])
                    or previous != row
                ):
                    _fail("original role ancestry changed")
            if path in self._lineages:
                self._live()
                return self._lineages[path]
            for row in value:
                if self._lineage_rows[row[0]] is None:
                    self._lineage_rows[row[0]] = row
            self._lineages[path] = tuple(self._lineage_rows[row[0]] for row in value)
            self._live()
            return self._lineages[path]
        except BaseException:
            self._poisoned = True
            raise

    def remember_presence(self, path, value):
        self._live()
        if path not in self._presences:
            self._ledger.charge_records(2, 2 * len(str(path).encode("utf-8")))
        elif self._presences[path] != value:
            self._poisoned = True
            _fail("original Git role presence changed")
        self._presences[path] = value
        self._live()

    def file(self, path, *, optional=False, maximum_bytes):
        from .repository_refresh import RefreshFileObservation, _raw_file

        self._live()
        path = Path(path)
        self._begin_io()
        try:
            self.reserve_lineage(path.parent)
            if path not in self._ledger.cache:
                self._ledger.snapshot(
                    path,
                    optional=optional,
                    maximum_bytes=maximum_bytes,
                    _reader=_raw_file,
                )
            item = self._ledger.cache[path]
            if item.content is not None and len(item.content) > maximum_bytes:
                _fail("role file exceeds its original read ceiling")
            if item.content is None and not optional:
                raise FileNotFoundError(path)
            if item.content is None and not os.path.lexists(path.parent):
                observed = RefreshFileObservation(path, None, None)
            else:
                observed = _raw_file(
                    path,
                    optional=item.content is None,
                    maximum_bytes=min(maximum_bytes, max(1, len(item.content or b""))),
                )
            if observed != item:
                _fail("original role input changed")
            self._live()
            return item
        except BaseException:
            self._poisoned = True
            raise
        finally:
            self._io_active = False

    def json_value(self, content, label):
        self._live()
        if current_role_observation() is not self:
            _fail("actual active canonical read scope required")
        try:
            value = self._ledger.json_value(content, label)
            self._live()
            return value
        except BaseException:
            self._poisoned = True
            raise

    def git(self, root, arguments, *, timeout_seconds, _maximum_output_bytes=None):
        from .repository_orchestration import _raw_git

        self._live()
        ledger = self._ledger
        error_limit = min(65536, self.budget.maximum_file_bytes)
        limit = min(
            8 * 1024**2,
            self.budget.maximum_file_bytes,
            ledger.budget.maximum_total_bytes
            - ledger.bytes
            - ledger.reserve
            - error_limit,
            (ledger.metadata - ledger.charged) // 64 - error_limit,
        )
        if _maximum_output_bytes is not None:
            if (
                type(_maximum_output_bytes) is not int
                or not 1 <= _maximum_output_bytes <= 8 * 1024**2
            ):
                raise ValueError("canonical Git read ceiling cannot be enlarged")
            limit = min(limit, _maximum_output_bytes)
        if limit < 1:
            self._poisoned = True
            _fail("Git output has no remaining shared allowance")
        self._begin_io()
        ledger.bytes += limit + error_limit
        ledger.charged += 64 * (limit + error_limit)
        ledger.require_capacity()
        try:
            usage = []
            raw = _raw_git(
                root,
                *arguments,
                timeout_seconds=timeout_seconds,
                _maximum_output_bytes=limit,
                _maximum_error_bytes=error_limit,
                _output_usage=lambda output, error: usage.append((output, error)),
            )
            if (
                len(usage) != 1
                or usage[0][0] != len(raw)
                or type(usage[0][1]) is not int
                or not 0 <= usage[0][1] <= error_limit
                or len(raw) > limit
            ):
                _fail("canonical Git reader did not report bounded channel usage")
            # Peak capacity was held for both channels while I/O was active.
            # Keep actual stderr consumption, not unused capacity, in the shared
            # cumulative input ledger. Failed reads never reach this refund.
            unused = limit - len(raw) + error_limit - usage[0][1]
            ledger.bytes -= unused
            ledger.charged -= 64 * unused
            ledger.charge_records(1 + raw.count(b"\0") + raw.count(b"\n"))
            self._live()
            return raw
        except BaseException:
            self._poisoned = True
            raise
        finally:
            self._io_active = False

    def require_current(self):
        self._live()
        for item in tuple(self._ledger.cache.values()):
            self.file(
                item.path,
                optional=item.content is None,
                maximum_bytes=max(1, len(item.content or b"")),
            )
        self.close_native_inputs()

    def close_native_inputs(self):
        """Close only original named facts after all dependent payload reads."""
        self._live()
        if current_role_observation() is not self:
            _fail("actual active canonical read scope required")
        self._close_native_inputs()

    def _close_native_inputs(self):
        """Original named native facts; no payload reads or activation grant."""
        from .catalog_copy_plan import _anchor
        from .repository_refresh import _signature
        from .retained_layout_git_controls import _presence
        from .retained_layout_partition import _lineage

        self._live()
        for path, expected in self._lineages.items():
            if _lineage(path) != expected:
                _fail("original role ancestry changed")
        for path, expected in self._presences.items():
            if _presence(path) != expected:
                _fail("original Git role presence changed")
        for path, item in self._ledger.cache.items():
            if _anchor(path) != self._ledger.ancestry[path]:
                _fail("original role input ancestry changed")
            actual = _signature(path) if os.path.lexists(path) else None
            if actual != item.signature:
                _fail("original role native facts changed")
        self._live()


@contextmanager
def _role_observation_operation(
    *, budget, maximum_metadata_bytes, _ledger=None, _accounting=None
):
    """Retain one read owner without installing it across a caller yield."""
    if type(_accounting) is not tuple or len(_accounting) != 3:
        raise TypeError("original accounting issuer required")
    ledger_type, accounting_guard, accounting_seal = _accounting

    if _CURRENT.get() is not None:
        _fail("nested role read scopes are ambiguous")
    if _ledger is None:
        _ledger = ledger_type(budget, maximum_metadata_bytes, ())
    elif (
        type(_ledger) is not ledger_type
        or _ledger.budget != budget
        or _ledger.metadata != maximum_metadata_bytes
    ):
        raise TypeError("actual matching shared observation ledger required")
    owner = _RoleObservation(_KEY, _ledger)
    _OPERATIONS[owner] = (
        _ledger,
        os.getpid(),
        threading.get_ident(),
        _ledger.budget,
        maximum_metadata_bytes,
        _ledger.reserve,
        accounting_guard,
        accounting_seal,
        ledger_type,
        owner._lineage_rows,
    )
    try:
        yield owner
    finally:
        _OPERATIONS.pop(owner, None)
        owner._active = False


@contextmanager
def _activate_role_observation(owner, *, _borrow=False):
    """Activate only a live factory owner; foreign or reentrant I/O refuses."""
    original = _OPERATIONS.get(owner)
    if (
        type(owner) is not _RoleObservation
        or original is None
        or original[0] is not owner._ledger
        or original[1:3] != (os.getpid(), threading.get_ident())
    ):
        raise TypeError("actual live canonical read operation required")
    owner._live()
    current = _CURRENT.get()
    if owner._io_active:
        owner._poisoned = True
        _fail("nested or reentrant read activation is ambiguous")
    if current is not None and (current is not owner or not _borrow):
        _fail("nested or reentrant read activation is ambiguous")
    if current is owner:
        if current_role_observation() is not owner:
            _fail("original read activation ended")
        yield owner
        owner.require_current()
        if _OPERATIONS.get(owner) is not original:
            _fail("original canonical read operation ended")
        owner._live()
        return
    activation = object()
    token = _CURRENT.set(owner)
    activation_token = _ACTIVATION.set(activation)
    _ACTIVE[owner] = activation
    try:
        yield owner
        owner.require_current()
        if _OPERATIONS.get(owner) is not original:
            _fail("original canonical read operation ended")
        owner._live()
    finally:
        _ACTIVE.pop(owner, None)
        _ACTIVATION.reset(activation_token)
        _CURRENT.reset(token)


@contextmanager
def bounded_role_observation(*, budget, maximum_metadata_bytes, _ledger=None):
    """Scope only canonical read helpers; saved observations grant no effects."""
    with _role_observation_operation(
        budget=budget, maximum_metadata_bytes=maximum_metadata_bytes, _ledger=_ledger
    ) as owner:
        with _activate_role_observation(owner):
            yield owner


def _bind_original_role_metadata_guard():
    """Publish Role method facts before importing the accounting provider."""
    import builtins

    namespace, owner_type = globals(), _RoleObservation
    class_items = tuple(vars(owner_type).items())
    bases, mro = owner_type.__bases__, owner_type.__mro__
    methods = (
        "__init__",
        "_live",
        "_begin_io",
        "file",
        "json_value",
        "reserve_lineage",
        "remember_lineage",
        "require_current",
    )
    functions = tuple(vars(owner_type)[name] for name in methods) + (
        current_role_observation,
        _fail,
    )
    codes = tuple(
        (
            fn,
            fn.__code__,
            fn.__defaults__,
            fn.__kwdefaults__,
            tuple((fn.__kwdefaults__ or {}).items()),
        )
        for fn in functions
    )
    slots = [
        (namespace, name, True, namespace[name])
        for name in (
            "_RoleObservation",
            "_OPERATIONS",
            "_CURRENT",
            "_ACTIVATION",
            "_ACTIVE",
            "current_role_observation",
            "_fail",
        )
    ]
    for function in functions:
        scope = function.__globals__
        for name in function.__code__.co_names:
            if name in scope or hasattr(builtins, name):
                slots.append((scope, name, name in scope, scope.get(name)))
                if name not in scope and name in function.__builtins__:
                    inherited = function.__builtins__
                    slots.append((inherited, name, True, inherited[name]))
    slots = tuple(slots)
    native = (
        (vars(os), "getpid", os.getpid),
        (vars(threading), "get_ident", threading.get_ident),
    )
    exact, size, some, text, failure, mapping = type, len, any, str, ValueError, vars
    raw_attribute, missing_owner = object.__getattribute__, TypeError

    def implementation(function, code, defaults, keywords, items):
        actual = function.__kwdefaults__
        return (
            function.__code__ is code
            and function.__defaults__ is defaults
            and actual is keywords
            and size(actual or {}) == size(items)
            and not some(exact(key) is not text for key in (actual or {}))
            and not some((actual or {}).get(key) is not value for key, value in items)
        )

    def guard(owner=None):
        actual_class = mapping(owner_type)
        if (
            namespace.get("_original_role_metadata_guard") is not guard
            or owner_type.__bases__ is not bases
            or owner_type.__mro__ is not mro
            or size(actual_class) != size(class_items)
            or some(actual_class.get(name) is not value for name, value in class_items)
            or some(
                (name in scope) is not present or scope.get(name) is not value
                for scope, name, present, value in slots
            )
            or some(scope.get(name) is not value for scope, name, value in native)
            or some(not implementation(*row) for row in codes)
        ):
            raise failure("original Role metadata methods changed")
        if owner is None:
            return
        if exact(owner) is not owner_type or some(
            name in mapping(owner) for name in methods
        ):
            raise failure("actual issued Role metadata methods required")
        original = namespace["_OPERATIONS"].get(owner)
        if original is None:
            raise missing_owner("actual live canonical read operation required")
        if (
            size(original) != 10
            or original[0] is not raw_attribute(owner, "_ledger")
            or exact(original[0]) is not original[8]
            or not implementation(original[6], *original[7])
            or original[9] is not raw_attribute(owner, "_lineage_rows")
        ):
            raise failure("original issued Role accounting guard required")
        original[6](original[0])

    return guard


_original_role_metadata_guard = _bind_original_role_metadata_guard()
del _bind_original_role_metadata_guard


# Publish the independent Role guard first. A catalog-first or Role-first import
# may enter transaction while this module is still importing its ledger provider.
from .catalog_copy_plan import (  # noqa: E402
    _Observation as _ORIGINAL_METADATA_LEDGER,
)
from .catalog_copy_plan import (  # noqa: E402
    _original_metadata_accounting_guard as _ORIGINAL_ACCOUNTING_GUARD,
)


def _bind_original_accounted_role_operation(
    original, role_guard, ledger_type, ledger_guard
):
    size, some, exact, text, failure = len, any, type, str, ValueError

    def seal(function):
        return (
            function.__code__,
            function.__defaults__,
            function.__kwdefaults__,
            tuple((function.__kwdefaults__ or {}).items()),
        )

    role_seal, ledger_seal = seal(role_guard), seal(ledger_guard)
    code_rows = tuple((fn, seal(fn)) for fn in (original, original.__wrapped__))
    accounting = ledger_type, ledger_guard, ledger_seal

    def current():
        for function, before in (
            (role_guard, role_seal),
            (ledger_guard, ledger_seal),
            *code_rows,
        ):
            code, defaults, keywords, items = before
            actual_keywords = function.__kwdefaults__
            if (
                function.__code__ is not code
                or function.__defaults__ is not defaults
                or actual_keywords is not keywords
                or size(actual_keywords or {}) != size(items)
                or some(exact(key) is not text for key in (actual_keywords or {}))
                or some(
                    (actual_keywords or {}).get(key) is not value
                    for key, value in items
                )
            ):
                raise failure("original Role accounting issuer changed")
        role_guard()
        ledger_guard()

    @contextmanager
    def operation(*, budget, maximum_metadata_bytes, _ledger=None):
        current()
        with original(
            budget=budget,
            maximum_metadata_bytes=maximum_metadata_bytes,
            _ledger=_ledger,
            _accounting=accounting,
        ) as owner:
            role_guard(owner)
            yield owner
            current()
            role_guard(owner)
        current()

    return operation


_role_observation_operation = _bind_original_accounted_role_operation(
    _role_observation_operation,
    _original_role_metadata_guard,
    _ORIGINAL_METADATA_LEDGER,
    _ORIGINAL_ACCOUNTING_GUARD,
)
del _bind_original_accounted_role_operation
