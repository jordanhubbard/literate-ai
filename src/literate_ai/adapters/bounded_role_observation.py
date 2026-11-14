"""Operation-local finite canonical metadata reads; never mutation authority."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_CURRENT = ContextVar("bounded-role-observation", default=None)
_KEY = object()


def _fail(message):
    raise ValueError("layout.role-inputs: " + message)


def current_role_observation():
    value = _CURRENT.get()
    if value is not None:
        if type(value) is not _RoleObservation:
            raise TypeError("actual bounded role read scope required")
        value._live()
    return value


class _RoleObservation:
    def __init__(self, key, ledger):
        if key is not _KEY:
            raise TypeError("actual bounded role read scope required")
        self._ledger = ledger
        self._pid, self._active, self._poisoned = os.getpid(), True, False
        self._thread, self._io_active = threading.get_ident(), False
        self._lineage_allowances, self._lineages = set(), {}
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
        self._ledger.require_capacity()

    def _begin_io(self):
        self._live()
        if self._io_active:
            self._poisoned = True
            _fail("reentrant role I/O cannot borrow the shared allowance")
        self._io_active = True

    def reserve_lineage(self, path):
        self._live()
        if path in self._lineage_allowances:
            return
        try:
            count = len(path.parts)
            self._ledger.charge_records(2 * count)
            size = 0
            for parent in path.parents:
                size += len(str(parent).encode("utf-8"))
                if 128 * size > self._ledger.metadata - self._ledger.charged:
                    _fail("ancestry exceeds shared metadata allowance")
            size += len(str(path).encode("utf-8"))
            self._ledger.charged += 128 * size
            self._ledger.require_capacity()
            self._lineage_allowances.add(path)
        except BaseException:
            self._poisoned = True
            raise

    def remember_lineage(self, path, value):
        self._live()
        if path in self._lineages and self._lineages[path] != value:
            self._poisoned = True
            _fail("original role ancestry changed")
        self._lineages[path] = value
        self._live()

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
        try:
            value = self._ledger.json_value(content, label)
            self._live()
            return value
        except BaseException:
            self._poisoned = True
            raise

    def git(self, root, arguments, *, timeout_seconds):
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
def bounded_role_observation(*, budget, maximum_metadata_bytes, _ledger=None):
    """Scope only canonical read helpers; saved observations grant no effects."""
    from .catalog_copy_plan import _Observation

    if _CURRENT.get() is not None:
        _fail("nested role read scopes are ambiguous")
    if _ledger is None:
        _ledger = _Observation(budget, maximum_metadata_bytes, ())
    elif (
        type(_ledger) is not _Observation
        or _ledger.budget != budget
        or _ledger.metadata != maximum_metadata_bytes
    ):
        raise TypeError("actual matching shared observation ledger required")
    owner = _RoleObservation(_KEY, _ledger)
    token = _CURRENT.set(owner)
    try:
        yield owner
        owner.require_current()
    finally:
        owner._active = False
        _CURRENT.reset(token)
