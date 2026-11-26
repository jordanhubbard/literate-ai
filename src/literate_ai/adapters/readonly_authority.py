"""Task-local strict authority observation; no provider or execution permissions."""

from contextlib import contextmanager
from contextvars import ContextVar

_STRICT_READONLY = ContextVar("literate_strict_readonly_authority", default=False)


def strict_authority_reads_required() -> bool:
    return _STRICT_READONLY.get()


@contextmanager
def strict_readonly_authority():
    """Nested/parallel callers restore their original context even on refusal."""
    token = _STRICT_READONLY.set(True)
    try:
        yield
    finally:
        _STRICT_READONLY.reset(token)
