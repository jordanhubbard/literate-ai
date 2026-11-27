"""Additive in-process liveness fences, never execution or network permission."""

import inspect
import threading
from contextlib import contextmanager
from contextvars import ContextVar

_CHECKING = ContextVar("literate_ai_process_liveness_checking", default=())
_MAX_SCOPES = 64


class ProcessLivenessError(RuntimeError):
    pass


class _LiveGuard:
    def __init__(self, callback):
        self.callback = callback
        self.active = True
        self.lock = threading.Lock()

    def retire(self):
        with self.lock:
            self.active = False

    def is_active(self):
        with self.lock:
            return self.active

    def require_current(self):
        if not self.is_active():
            raise ProcessLivenessError("process liveness scope has ended")
        checking = _CHECKING.get()
        if self in checking:
            self.retire()
            raise ProcessLivenessError(
                "process liveness checks cannot launch guarded children"
            )
        token = _CHECKING.set((*checking, self))
        try:
            returned = self.callback()
            if returned is not None:
                if inspect.iscoroutine(returned) or inspect.isgenerator(returned):
                    returned.close()
                raise TypeError("process liveness owner must return None synchronously")
            if not self.is_active():
                raise ProcessLivenessError(
                    "process liveness scope ended during validation"
                )
        except BaseException:
            self.retire()
            raise
        finally:
            _CHECKING.reset(token)


_GUARDS = ContextVar("literate_ai_process_liveness", default=())


def _require_guards(guards):
    for guard in guards:
        guard.require_current()
    # A later callback may block while an earlier original scope retires. Close
    # all captured memberships without invoking callbacks or reopening owners.
    if any(not guard.is_active() for guard in guards):
        raise ProcessLivenessError("process liveness scope ended during validation")


def require_process_liveness():
    """Poll exact original scopes, including retired scopes in copied contexts."""
    _require_guards(_GUARDS.get())


def capture_process_liveness():
    """Retain entering scopes across setup callbacks that change the context."""
    original = _GUARDS.get()

    def require_original():
        current = _GUARDS.get()
        _require_guards(tuple(dict.fromkeys((*original, *current))))

    return require_original


def _close_preserving_primary_failure(close, primary):
    """Perform the original close, retaining an already propagating body error.

    A failed operation cannot publish a result. Callers still owe unconditional
    retirement; no exception or traceback is retained beyond that local unwind.
    """
    try:
        close()
    except BaseException:
        if primary is None:
            raise


@contextmanager
def process_liveness(require_current):
    """Keep synchronous owner checks active through child launch, poll and close.

    Nested scopes are additive. Copied worker contexts retain the original guard
    objects and fail after their scope exits; they do not extend the lifetime.
    This context neither selects tools nor authorizes any child operation.
    """
    if not callable(require_current) or any(
        inspect.iscoroutinefunction(item)
        or inspect.isasyncgenfunction(item)
        or inspect.isgeneratorfunction(item)
        for item in (require_current, type(require_current).__call__)
    ):
        raise TypeError("process liveness owner must be synchronous")
    previous = _GUARDS.get()
    if len(previous) >= _MAX_SCOPES:
        raise ProcessLivenessError("process liveness scope capacity exhausted")
    guard = _LiveGuard(require_current)
    token = _GUARDS.set((*previous, guard))
    completed = False
    primary = None
    try:
        require_process_liveness()
        yield
        completed = True
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if completed or all(item.is_active() for item in _GUARDS.get()):
                _close_preserving_primary_failure(require_process_liveness, primary)
        finally:
            try:
                guard.retire()
                _GUARDS.reset(token)
            finally:
                primary = None
