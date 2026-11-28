"""Internal verifier resource leases; no inspection or execution authority."""

import threading
import types
from dataclasses import dataclass, field
from functools import wraps

from literate_ai.adapters.node_sdk_verifier_closing_payload import (
    _RELEASE_CLOSING_PAYLOAD,
    _VerifierClosingPayload,
)
from literate_ai.adapters.process_liveness import _close_preserving_primary_failure


def _poison_capture_errors(method):
    @wraps(method)
    def guarded(self, handle, *args, **kwargs):
        try:
            return method(self, handle, *args, **kwargs)
        except BaseException as error:
            with self._lock:
                capture = (
                    self._captures.get(handle)
                    if type(handle) is _CaptureHandle
                    else None
                )
                if capture is not None:
                    capture.failed = True
                owner = None if capture is None else capture.owner
            if owner is not None:
                _close_preserving_primary_failure(
                    lambda: self.retire(owner, failed=True), error
                )
            raise
        finally:
            args = kwargs = capture = owner = None

    return guarded


def _poison_owner_errors(method):
    @wraps(method)
    def guarded(self, handle, *args, **kwargs):
        try:
            return method(self, handle, *args, **kwargs)
        except BaseException as error:
            if type(handle) is _OwnerHandle:
                _close_preserving_primary_failure(
                    lambda: self.retire(handle, failed=True), error
                )
            raise
        finally:
            args = kwargs = None

    return guarded


class _OriginalTupleReference(tuple):
    """Opaque original field DATA; structural tuple containers stay separate."""

    __slots__ = ()

    def __new__(cls):
        raise TypeError("tuple field observations require their fixed factory")


_TUPLE_MRO = type.__getattribute__(_OriginalTupleReference, "__mro__")
_TUPLE_NAMESPACES = tuple(
    (cls, tuple(type.__getattribute__(cls, "__dict__").items())) for cls in _TUPLE_MRO
)
_TUPLE_ABSENT = object()


def _require_tuple_reference_storage():
    if type.__getattribute__(_OriginalTupleReference, "__mro__") is not _TUPLE_MRO:
        raise ValueError("original tuple field storage changed")
    for cls, expected in _TUPLE_NAMESPACES:
        current = type.__getattribute__(cls, "__dict__")
        if len(current) != len(expected) or any(
            current.get(name, _TUPLE_ABSENT) is not value for name, value in expected
        ):
            raise ValueError("original tuple field namespace changed")


def _tuple_field_reference(value):
    result = None
    try:
        if type(value) is not tuple:
            raise TypeError("original tuple fields require exact tuple storage")
        _require_tuple_reference_storage()
        result = tuple.__new__(_OriginalTupleReference, (value,))
        return result
    finally:
        value = result = None


def _tuple_field_value(reference):
    value = None
    try:
        _require_tuple_reference_storage()
        if tuple.__len__(reference) != 1:
            raise ValueError("original tuple field reference changed")
        value = tuple.__getitem__(reference, 0)
        if type(value) is not tuple:
            raise ValueError("original tuple field reference changed")
        return value
    finally:
        reference = value = None


def _validate_compiler_facts(facts):
    """Bound tuple containers; every other value is an opaque original leaf.

    This compares storage observations only. The fixed capture owner must still
    fence original fields, reserve retention first and validate actual bytes.
    """
    if type(facts) is not tuple or not 1 <= len(facts) <= 32:
        raise ValueError("compiler resource facts are not bounded original DATA")
    count = 0
    ancestors = set()

    def visit(value, depth):
        nonlocal count
        item = None
        try:
            count += 1
            if count > 16384 or depth > 8:
                raise ValueError("compiler snapshot structure exceeds its bound")
            if type(value) is _OriginalTupleReference:
                _tuple_field_value(value)
                return
            if type(value) is not tuple:
                if issubclass(type(value), tuple):
                    raise TypeError("compiler snapshot containers require exact tuples")
                return
            identity = id(value)
            if identity in ancestors:
                raise ValueError("compiler snapshot contains a cycle")
            if len(value) > 4096:
                raise ValueError("compiler snapshot container exceeds its bound")
            ancestors.add(identity)
            try:
                for item in value:
                    visit(item, depth + 1)
            finally:
                ancestors.remove(identity)
        finally:
            value = item = None

    try:
        visit(facts, 0)
    finally:
        facts = ()


def _same_compiler_facts(left, right):
    """Fresh tuple structure is allowed; original leaves must be identical."""
    pending = [(left, right)]
    before = after = None
    try:
        while pending:
            before, after = pending.pop()
            if type(before) is tuple and type(after) is tuple:
                if len(before) != len(after):
                    return False
                pending.extend(zip(before, after, strict=True))
            elif (
                type(before) is _OriginalTupleReference
                or type(after) is _OriginalTupleReference
            ):
                if (
                    type(before) is not _OriginalTupleReference
                    or type(after) is not _OriginalTupleReference
                ):
                    return False
                if _tuple_field_value(before) is not _tuple_field_value(after):
                    return False
            elif before is not after:
                return False
        return True
    finally:
        left = right = before = after = None
        pending.clear()


class _OwnerPublication:
    __slots__ = ("pool", "owner", "claimed")

    def __init__(self):
        raise TypeError("owner publication requires the fixed allocation factory")


_PUBLICATION_SLOTS = {
    name: vars(_OwnerPublication)[name] for name in ("pool", "owner", "claimed")
}


def _new_owner_publication(pool):
    result = None
    try:
        result = object.__new__(_OwnerPublication)
        for name, value in (("pool", pool), ("owner", None), ("claimed", False)):
            types.MemberDescriptorType.__set__(_PUBLICATION_SLOTS[name], result, value)
        return result
    finally:
        pool = result = value = None


def _published_owner(publication):
    try:
        if type(publication) is not _OwnerPublication:
            raise TypeError("resource publication requires its original metadata")
        return types.MemberDescriptorType.__get__(
            _PUBLICATION_SLOTS["owner"], publication, _OwnerPublication
        )
    finally:
        publication = None


class _OwnerHandle:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("resource owners require original pool allocation")


class _CaptureHandle:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("capture leases require original pool allocation")


class _ClosingPublication:
    __slots__ = ("pool", "owner", "token", "claimed", "dropped")

    def __init__(self):
        raise TypeError("closing publication requires its fixed factory")


_CLOSING_SLOTS = {
    name: vars(_ClosingPublication)[name]
    for name in ("pool", "owner", "token", "claimed", "dropped")
}


def _new_closing_publication(pool, owner):
    """Publish original identities before borrowing, retaining no source views."""
    publication = value = None
    try:
        if type(pool) is not _VerifierResourcePool or type(owner) is not _OwnerHandle:
            raise TypeError("closing publication requires original resource identities")
        publication = object.__new__(_ClosingPublication)
        for name, value in (
            ("pool", pool),
            ("owner", owner),
            ("token", object()),
            ("claimed", False),
            ("dropped", False),
        ):
            types.MemberDescriptorType.__set__(_CLOSING_SLOTS[name], publication, value)
        return publication
    finally:
        pool = owner = publication = value = None


def _closing_publication_values(publication):
    values = None
    try:
        if type(publication) is not _ClosingPublication:
            raise TypeError("closing publication requires its original metadata")
        values = tuple(
            types.MemberDescriptorType.__get__(slot, publication, _ClosingPublication)
            for slot in _CLOSING_SLOTS.values()
        )
        if (
            type(values[0]) is not _VerifierResourcePool
            or type(values[1]) is not _OwnerHandle
            or type(values[2]) is not object
            or type(values[3]) is not bool
            or type(values[4]) is not bool
        ):
            raise TypeError("closing publication requires bounded original DATA")
        return values
    finally:
        publication = values = None


def _mark_closing_views_dropped(publication):
    """Fixed reader's proof after dropping all view and iteration references."""
    try:
        _closing_publication_values(publication)
        types.MemberDescriptorType.__set__(_CLOSING_SLOTS["dropped"], publication, True)
    finally:
        publication = None


@dataclass(slots=True)
class _Compiler:
    original: object
    facts: tuple
    byte_count: int
    releasing: bool = False


@dataclass(slots=True)
class _Owner:
    phase: str = "LIVE"
    failed: bool = False
    captures: dict = field(default_factory=dict)
    closing_borrowed: object = None
    compilers: dict = field(default_factory=dict)


@dataclass(slots=True)
class _Capture:
    base_bytes: int
    owner: object = None
    compiler_key: int | None = None
    closing_bytes: int = 0
    payload: object = None
    attached: bool = False
    committed: bool = False
    active: bool = True
    releasing: bool = False
    failed: bool = False

    @property
    def byte_count(self):
        return self.base_bytes + self.closing_bytes


class _VerifierResourcePool:
    """One slot survives capture-to-closing transfer without uncharging DATA.

    Caller code must reserve outside the binding lock, commit original runtime
    membership under that lock, and call commit_handoff afterward. Release and
    retirement also run outside that lock. Payload quantities are supplied only
    by the fixed capture owner; this pool cannot authorize their provenance.
    """

    def __init__(self, *, maximum_slots=33, maximum_bytes=512 * 1024 * 1024):
        self._amount(maximum_slots, positive=True)
        self._amount(maximum_bytes, positive=True)
        if maximum_slots > 33 or maximum_bytes > 512 * 1024 * 1024:
            raise ValueError(
                "verifier resource limits cannot exceed the shared ceiling"
            )
        self._maximum_slots = maximum_slots
        self._maximum_bytes = maximum_bytes
        self._lock = threading.RLock()
        self._drainer = None
        self._owners = {}
        self._captures = {}

    @staticmethod
    def _amount(value, *, positive=False):
        if type(value) is not int or value < (1 if positive else 0):
            raise ValueError("resource bounds require exact nonnegative integers")

    def _owner(self, handle):
        if type(handle) is not _OwnerHandle or handle not in self._owners:
            raise ValueError("resource owner is not current here")
        return self._owners[handle]

    def _capture(self, handle):
        if type(handle) is not _CaptureHandle or handle not in self._captures:
            raise ValueError("capture resource lease is not current here")
        return self._captures[handle]

    def _bytes(self):
        return sum(c.byte_count for c in self._captures.values()) + sum(
            c.byte_count for o in self._owners.values() for c in o.compilers.values()
        )

    def _capacity(self, slots, byte_count):
        if (
            len(self._captures) + slots > self._maximum_slots
            or self._bytes() + byte_count > self._maximum_bytes
        ):
            raise ValueError("verifier resource capacity exhausted")

    def create_owner(self, *, _publication=None):
        handle = None
        try:
            with self._lock:
                if _publication is not None:
                    if (
                        type(_publication) is not _OwnerPublication
                        or types.MemberDescriptorType.__get__(
                            _PUBLICATION_SLOTS["pool"], _publication, _OwnerPublication
                        )
                        is not self
                    ):
                        raise TypeError("owner allocation has a foreign publication")
                    if types.MemberDescriptorType.__get__(
                        _PUBLICATION_SLOTS["claimed"], _publication, _OwnerPublication
                    ):
                        raise ValueError(
                            "owner allocation publication was already used"
                        )
                    types.MemberDescriptorType.__set__(
                        _PUBLICATION_SLOTS["claimed"], _publication, True
                    )
                if len(self._owners) >= self._maximum_slots:
                    raise ValueError("verifier resource owner capacity exhausted")
                handle = object.__new__(_OwnerHandle)
                # Publish into the caller's already-journaled metadata before
                # retaining pool ownership; caller cancellation cannot lose it.
                if _publication is not None:
                    types.MemberDescriptorType.__set__(
                        _PUBLICATION_SLOTS["owner"], _publication, handle
                    )
                self._owners[handle] = _Owner()
            return handle
        except BaseException as error:
            if handle is not None:
                _close_preserving_primary_failure(
                    lambda: self.retire(handle, failed=True), error
                )
            raise

    def reserve_capture(self, byte_count=0):
        self._amount(byte_count)
        handle = None
        try:
            with self._lock:
                self._capacity(1, byte_count)
                handle = object.__new__(_CaptureHandle)
                self._captures[handle] = _Capture(byte_count)
            return handle
        except BaseException as error:
            with self._lock:
                capture = self._captures.get(handle)
                if capture is not None:
                    capture.active, capture.failed, capture.releasing = (
                        False,
                        True,
                        True,
                    )
            _close_preserving_primary_failure(self.drain_pending, error)
            raise

    @_poison_capture_errors
    def resize_capture(self, handle, byte_count):
        self._amount(byte_count)
        with self._lock:
            capture = self._capture(handle)
            if (
                not capture.active
                or capture.releasing
                or capture.failed
                or capture.owner is not None
            ):
                raise ValueError("capture reservation has already settled")
            self._capacity(0, byte_count - capture.base_bytes)
            capture.base_bytes = byte_count

    @_poison_capture_errors
    def prepare_handoff(
        self,
        handle,
        owner_handle,
        *,
        closing_bytes,
        compiler,
        compiler_facts,
        compiler_bytes,
    ):
        """Reserve before retaining facts; exact compiler dedup is owner-local."""
        try:
            self._amount(closing_bytes)
            self._amount(compiler_bytes, positive=True)
            _validate_compiler_facts(compiler_facts)
            if compiler is None:
                raise ValueError(
                    "compiler resource facts are not bounded original DATA"
                )
            with self._lock:
                capture, owner = self._capture(handle), self._owner(owner_handle)
                if (
                    not capture.active
                    or capture.releasing
                    or capture.failed
                    or capture.owner is not None
                    or owner.phase != "LIVE"
                    or owner.failed
                ):
                    raise ValueError(
                        "handoff requires original live uncommitted capture"
                    )
                key = id(compiler)
                existing = owner.compilers.get(key)
                if existing is not None and (
                    existing.releasing
                    or existing.original is not compiler
                    or existing.byte_count != compiler_bytes
                    or not _same_compiler_facts(existing.facts, compiler_facts)
                ):
                    raise ValueError("compiler resource snapshot changed")
                self._capacity(
                    0, closing_bytes + (compiler_bytes if existing is None else 0)
                )
                prepared = (
                    _Compiler(compiler, compiler_facts, compiler_bytes)
                    if existing is None
                    else None
                )
                # Complete or roll back all membership links under this lock.
                # Locals/arguments retain payloads during rollback, so deleting
                # an inserted record cannot release its final source reference.
                try:
                    if prepared is not None:
                        owner.compilers[key] = prepared
                    owner.captures[handle] = None
                    capture.owner, capture.compiler_key = owner_handle, key
                    capture.closing_bytes = closing_bytes
                except BaseException:
                    capture.owner, capture.compiler_key = None, None
                    capture.closing_bytes = 0
                    owner.captures.pop(handle, None)
                    if prepared is not None and owner.compilers.get(key) is prepared:
                        owner.compilers.pop(key)
                    raise
                return existing is None
        except BaseException as error:
            if type(owner_handle) is _OwnerHandle:
                _close_preserving_primary_failure(
                    lambda: self.retire(owner_handle, failed=True), error
                )
            raise
        finally:
            # Runtime callers cannot sever this factory's retained failure frame.
            compiler = compiler_facts = prepared = existing = None

    @_poison_capture_errors
    def attach_payload(self, handle, payload):
        try:
            with self._lock:
                capture = self._capture(handle)
                owner = self._owner(capture.owner)
                if (
                    not capture.active
                    or capture.releasing
                    or capture.failed
                    or capture.attached
                    or owner.phase != "LIVE"
                    or owner.failed
                ):
                    raise ValueError("handoff payload lacks its original reservation")
                capture.payload, capture.attached = payload, True
        finally:
            payload = None

    @_poison_capture_errors
    def commit_handoff(self, handle):
        with self._lock:
            capture = self._capture(handle)
            owner = self._owner(capture.owner)
            if (
                not capture.active
                or capture.releasing
                or capture.failed
                or capture.committed
                or not capture.attached
                or owner.phase != "LIVE"
                or owner.failed
            ):
                raise ValueError("handoff cannot commit current membership")
            capture.committed = True

    def _mark_closed(self, owner_handle):
        owner = self._owners[owner_handle]
        if owner.closing_borrowed:
            return
        for handle in owner.captures:
            capture = self._captures[handle]
            if not capture.active and not capture.releasing:
                capture.releasing = True

    @_poison_capture_errors
    def capture_closed(self, handle, *, successful):
        if type(successful) is not bool:
            raise TypeError("capture settlement requires its original boolean result")
        with self._lock:
            self._settle_capture_locked(handle, successful, repeat_ok=False)
        self.drain_pending()

    @_poison_capture_errors
    def settle_capture_cleanup(self, handle, *, successful):
        """Idempotent completion for an original capture owner's ended lease.

        The fixed owner must remove its identity/source references first. This
        only completes resource cleanup; it cannot revive a capture or its ACK.
        """
        if type(successful) is not bool:
            raise TypeError("capture cleanup requires its original boolean result")
        with self._lock:
            self._settle_capture_locked(handle, successful, repeat_ok=True)
        self.drain_pending()

    def _settle_capture_locked(self, handle, successful, *, repeat_ok):
        if type(handle) is not _CaptureHandle:
            raise TypeError("capture cleanup requires its original lease")
        capture = self._captures.get(handle)
        if capture is None:
            if repeat_ok:
                return
            raise ValueError("capture resource lease is not current here")
        if not capture.active or capture.releasing:
            if not repeat_ok:
                raise ValueError("capture resource settlement was repeated")
            if not successful:
                capture.failed = True
                owner = self._owners.get(capture.owner)
                if owner is not None:
                    owner.phase, owner.failed = "RETIRED", True
                    self._mark_closed(capture.owner)
            return
        capture.active = False
        if capture.owner is None:
            capture.releasing = True
        else:
            owner = self._owner(capture.owner)
            if (
                successful
                and capture.committed
                and not capture.failed
                and owner.phase == "LIVE"
                and not owner.failed
            ):
                capture.base_bytes = 0
            else:
                owner.phase, owner.failed = "RETIRED", True
                self._mark_closed(capture.owner)

    def prepare_closing(
        self, owner_handle, *, expected_captures=None, _publication=None
    ):
        """Borrow once; private publication also covers an unreturned view.

        A mutable claimed flag is not proof that an existing reader has ended.
        Only this call's newly published borrow may unwind in this frame.
        """
        owner = token = view = None
        borrowed_here = False
        try:
            token = object()
            with self._lock:
                if _publication is not None:
                    pool, original_owner, token, claimed, dropped = (
                        _closing_publication_values(_publication)
                    )
                    if (
                        pool is not self
                        or original_owner is not owner_handle
                        or claimed is not False
                        or dropped is not False
                    ):
                        raise ValueError(
                            "closing publication has foreign or repeated use"
                        )
                    types.MemberDescriptorType.__set__(
                        _CLOSING_SLOTS["claimed"], _publication, True
                    )
                owner = self._owner(owner_handle)
                if expected_captures is not None:
                    if (
                        type(expected_captures) is not tuple
                        or len(expected_captures) > 33
                        or any(type(h) is not _CaptureHandle for h in expected_captures)
                    ):
                        raise TypeError("closing requires exact original lease DATA")
                    if (
                        len(expected_captures) != len(owner.captures)
                        or len(set(expected_captures)) != len(expected_captures)
                        or any(h not in owner.captures for h in expected_captures)
                    ):
                        raise ValueError(
                            "closing lease membership differs from enrollment"
                        )
                if (
                    owner.phase != "LIVE"
                    or owner.failed
                    or owner.closing_borrowed is not None
                    or any(
                        self._captures[h].active
                        or self._captures[h].releasing
                        or self._captures[h].failed
                        or not self._captures[h].committed
                        for h in owner.captures
                    )
                ):
                    raise ValueError(
                        "resource closing requires settled original handoffs"
                    )
                owner.phase = "CLOSING"
                borrowed_here = True
                owner.closing_borrowed = token
                view = tuple(
                    (
                        self._captures[h].payload,
                        owner.compilers[self._captures[h].compiler_key].original,
                        owner.compilers[self._captures[h].compiler_key].facts,
                    )
                    for h in owner.captures
                )
            return view
        except BaseException as error:
            # Keep this unpublished borrow charged while dropping any temporary
            # view outside the lock. Never clear a different original reader.
            view = None
            with self._lock:
                if (
                    borrowed_here
                    and owner is not None
                    and self._owners.get(owner_handle) is owner
                    and owner.closing_borrowed is token
                ):
                    owner.closing_borrowed = None
            _close_preserving_primary_failure(
                lambda: self.retire(owner_handle, failed=True), error
            )
            raise

    def settle_closing_cleanup(self, owner_handle, publication):
        """Settle only the original dropped reader; never borrow or verify again."""
        if type(owner_handle) is not _OwnerHandle:
            raise TypeError("closing cleanup requires its exact original owner")
        pool, original_owner, token, _claimed, dropped = _closing_publication_values(
            publication
        )
        if (
            pool is not self
            or original_owner is not owner_handle
            or dropped is not True
        ):
            raise ValueError("closing cleanup lacks its original dropped-view proof")
        with self._lock:
            owner = self._owners.get(owner_handle)
            if owner is not None:
                if (
                    owner.closing_borrowed is not None
                    and owner.closing_borrowed is not token
                ):
                    raise ValueError("closing cleanup cannot settle another reader")
                owner.closing_borrowed = None
                if owner.phase == "RETIRED":
                    self._mark_closed(owner_handle)
                if not owner.captures:
                    self._mark_compilers(owner_handle)
        self.drain_pending()

    @_poison_owner_errors
    def closing_complete(self, owner_handle):
        """Acknowledge only after the fixed caller drops all closing views."""
        with self._lock:
            owner = self._owner(owner_handle)
            if not owner.closing_borrowed:
                raise ValueError("closing reader settlement was repeated")
            owner.closing_borrowed = None
            if owner.phase == "RETIRED":
                self._mark_closed(owner_handle)
            if not owner.captures:
                self._mark_compilers(owner_handle)
        self.drain_pending()

    def retire(self, owner_handle, *, failed=False):
        if type(owner_handle) is not _OwnerHandle or type(failed) is not bool:
            raise TypeError("resource retirement requires original owner DATA")
        with self._lock:
            owner = self._owners.get(owner_handle)
            if owner is not None:
                owner.failed |= failed
                owner.phase = "RETIRED"
                self._mark_closed(owner_handle)
                if not owner.captures:
                    self._mark_compilers(owner_handle)
        # Also resume cleanup after an earlier retirement removed this owner.
        self.drain_pending()
        return owner is not None

    def _mark_compilers(self, owner_handle):
        owner = self._owners[owner_handle]
        if (
            owner.phase == "RETIRED"
            and not owner.captures
            and not owner.closing_borrowed
        ):
            for compiler in owner.compilers.values():
                compiler.releasing = True
            if not owner.compilers:
                self._owners.pop(owner_handle)

    def _next_release(self):
        # Registry membership, retirement and per-record flags ARE the durable
        # work queue. Reconstruct it after interruption; no popped local job can
        # strand a RELEASING record. Caller holds the quota lock.
        for owner_handle in tuple(self._owners):
            owner = self._owners[owner_handle]
            if owner.phase == "RETIRED":
                self._mark_closed(owner_handle)
                if not owner.captures:
                    self._mark_compilers(owner_handle)
        for handle, capture in self._captures.items():
            if capture.owner is None and not capture.active:
                capture.releasing = True
            if capture.releasing:
                return "capture", handle
        for owner_handle, owner in self._owners.items():
            for key, compiler in owner.compilers.items():
                if compiler.releasing:
                    return "compiler", (owner_handle, key)
        return None

    def drain_pending(self):
        """Resume idempotent retired-DATA cleanup; never call an owner guard."""
        # A destructor may retire another owner. It must not wait for the drain
        # that invoked it; the current drainer will discover all durable work.
        token = object()
        garbage = payload = None
        try:
            with self._lock:
                if self._drainer is not None:
                    return
                self._drainer = token
            while True:
                try:
                    with self._lock:
                        job = self._next_release()
                        if job is None:
                            # Publish idle under the same lock as queue updates,
                            # so a new retire cannot lose its drain handoff.
                            self._drainer = None
                            return
                        kind, key = job
                        if kind == "capture":
                            record = self._captures[key]
                            payload = record.payload
                    # Keep the payload and its charge in the durable record until
                    # every fixed release component completes. No owner callback
                    # or duck-typed cleanup runs under the quota lock.
                    if type(payload) is _VerifierClosingPayload:
                        _RELEASE_CLOSING_PAYLOAD(payload)
                    with self._lock:
                        if kind == "capture" and (
                            self._captures.get(key) is not record
                            or record.payload is not payload
                        ):
                            raise ValueError(
                                "original retiring payload membership changed"
                            )
                        # Allocate before detachment. If allocation or later
                        # cancellation fails, records/charges stay discoverable.
                        garbage = list()
                        if kind == "capture":
                            record = self._captures[key]
                            owner_handle = record.owner
                            garbage.append(record.payload)
                            record.payload = None
                        else:
                            owner_handle, compiler_key = key
                            record = self._owners[owner_handle].compilers[compiler_key]
                            garbage.extend((record.original, record.facts))
                            record.original, record.facts = None, ()
                    payload = None
                    list.clear(garbage)
                    with self._lock:
                        owner = self._owners.get(owner_handle)
                        if kind == "capture":
                            # Remove the reverse link first. Interruption before
                            # the final global pop leaves a discoverable record;
                            # its owner may already have finished retiring.
                            if owner is not None:
                                owner.captures.pop(key, None)
                            self._captures.pop(key, None)
                        elif owner is not None:
                            owner.compilers.pop(compiler_key, None)
                finally:
                    # Clear all local source references outside the quota lock,
                    # including after partial detachment or accounting failure.
                    # Until this completes, the original record stays charged.
                    payload = None
                    if garbage is not None:
                        list.clear(garbage)
                        garbage = None
        finally:
            with self._lock:
                if self._drainer is token:
                    self._drainer = None

    def statistics(self):
        with self._lock:
            return {
                "bytes": self._bytes(),
                "slots": len(self._captures),
                "owners": len(self._owners),
                "compiler_snapshots": sum(
                    len(o.compilers) for o in self._owners.values()
                ),
            }
