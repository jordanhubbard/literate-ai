"""Bounded private SHA DATA reuse after every original byte is freshly read."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import PosixPath, WindowsPath
from threading import RLock
from types import BuiltinFunctionType

try:
    from _hashlib import openssl_sha256 as _NATIVE_SHA256
except ImportError:
    _NATIVE_SHA256 = None

_MAX_ENTRIES = 8
_MAX_FILE_BYTES = 32 * 1024 * 1024
_MAX_RETAINED_BYTES = 64 * 1024 * 1024
_MAX_CHUNKS = 64
_MAX_PATH_CHARACTERS = 1024
_CURRENT = ContextVar("read_only_executable_digest_data", default=None)


def _readers(
    digest,
    chunk_bytes,
    *,
    template=None,
    capacity=0,
    maximum_chunks=0,
    is_active=lambda: False,
    publish=None,
    key_bytes=0,
):
    # Original associations live in closures, never mutable object fields.
    matching = template is not None
    matched_chunks = 0
    chunks = []
    payload_bytes = key_bytes
    capturing = publish is not None and template is None and key_bytes <= capacity
    live = True

    def replay_prefix():
        nonlocal matching
        for index in range(matched_chunks):
            digest.update(template[0][index])
        matching = False

    def consume(stream):
        nonlocal matching, matched_chunks, capturing, payload_bytes
        while chunk := stream.read(chunk_bytes):
            if (
                matching
                and live
                and is_active()
                and type(chunk) is bytes
                and matched_chunks < len(template[0])
                and chunk == template[0][matched_chunks]
            ):
                matched_chunks += 1
            else:
                if matching:
                    replay_prefix()
                digest.update(chunk)
            if capturing:
                if (
                    not live
                    or not is_active()
                    or type(chunk) is not bytes
                    or len(chunks) >= maximum_chunks
                    or payload_bytes + len(chunk) > capacity
                ):
                    capturing = False
                    chunks.clear()
                else:
                    try:
                        chunks.append(chunk)
                    except MemoryError:
                        capturing = False
                        chunks.clear()
                    else:
                        payload_bytes += len(chunk)
        if matching and matched_chunks != len(template[0]):
            replay_prefix()

    def finish():
        if matching and (not live or not is_active()):
            replay_prefix()
        value = template[1] if matching else digest.hexdigest()
        if capturing and live and is_active():
            try:
                publish((tuple(chunks), value, payload_bytes))
            except MemoryError:
                pass
        return value

    def close():
        nonlocal live
        live = False
        chunks.clear()

    return consume, finish, close


@contextmanager
def read_only_executable_digest_data():
    """Own exact-byte DATA; no native/currentness observation is retained.

    Like the Skill DATA frame, this owns state in private source-created
    closures. It does not claim protection against arbitrary Python module or
    closure-cell rewriting. Callback object-field changes cannot substitute
    the original byte/digest association, index, limits or readers.
    """
    maximum_entries, maximum_file_bytes, maximum_bytes, maximum_chunks, maximum_path = (
        _MAX_ENTRIES,
        _MAX_FILE_BYTES,
        _MAX_RETAINED_BYTES,
        _MAX_CHUNKS,
        _MAX_PATH_CHARACTERS,
    )
    native_factory, make_readers = _NATIVE_SHA256, _readers
    entries = {}
    retained_bytes = 0
    active, busy = True, False
    lock = RLock()

    def is_active():
        return active

    @contextmanager
    def observe(path, factory, chunk_bytes):
        nonlocal busy, retained_bytes
        # Exactly once, before the caller's original OSError boundary. Direct
        # private calls cannot supply a fabricated completed hasher.
        digest = factory()
        eligible = (
            active
            and factory is native_factory
            and type(factory) is BuiltinFunctionType
            and factory.__name__ == "openssl_sha256"
            and type(path) in (PosixPath, WindowsPath)
            and type(chunk_bytes) is int
            and 0 < chunk_bytes <= 1024 * 1024
        )
        key = (str(path), chunk_bytes) if eligible else None
        acquired = bool(
            key is not None and len(key[0]) <= maximum_path and lock.acquire(False)
        )
        owns = acquired and active and not busy
        close = None
        try:
            if owns:
                busy = True
                key_bytes = 4 * len(key[0]) + 64
                capacity = min(
                    maximum_file_bytes + key_bytes, maximum_bytes - retained_bytes
                )

                def publish(entry):
                    nonlocal retained_bytes
                    if active and key not in entries and len(entries) < maximum_entries:
                        entries[key] = entry
                        retained_bytes += entry[2]

                consume, finish, close = make_readers(
                    digest,
                    chunk_bytes,
                    template=entries.get(key),
                    capacity=capacity,
                    maximum_chunks=maximum_chunks,
                    is_active=is_active,
                    publish=publish if len(entries) < maximum_entries else None,
                    key_bytes=key_bytes,
                )
            else:
                consume, finish, close = make_readers(digest, chunk_bytes)
            yield consume, finish
        finally:
            if close is not None:
                close()
            if owns:
                busy = False
            if acquired:
                if not active:
                    entries.clear()
                    retained_bytes = 0
                lock.release()

    def statistics():
        # Detached diagnostics; original entries/readers are never exposed.
        if not lock.acquire(False):
            return {
                "active": active,
                "entries": None,
                "payload_bytes": None,
                "digests": (),
            }
        try:
            return {
                "active": active,
                "entries": len(entries),
                "payload_bytes": retained_bytes,
                "digests": tuple(value[1] for value in entries.values()),
            }
        finally:
            lock.release()

    observe.statistics = statistics
    owner = _CURRENT
    token = owner.set(observe)
    try:
        yield
    finally:
        active = False
        try:
            # Never wait for copied-context I/O. Its finally clears deferred
            # storage, and inactive prevents any in-flight publication.
            if lock.acquire(False):
                try:
                    entries.clear()
                    retained_bytes = 0
                finally:
                    lock.release()
        finally:
            owner.reset(token)


@contextmanager
def executable_digest_observation(path, factory, chunk_bytes):
    observe = _CURRENT.get()
    if observe is not None:
        with observe(path, factory, chunk_bytes) as readers:
            yield readers
        return
    digest = factory()
    consume, finish, close = _readers(digest, chunk_bytes)
    try:
        yield consume, finish
    finally:
        close()
