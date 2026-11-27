"""Fixed private closing DATA cleanup; this object grants no runtime authority.

Only the original capture owner may attach this payload to its existing lease.
Operation membership, phase, charging and in-flight reader settlement remain
with their independent owners. Releases are idempotent metadata cleanup only.
"""

import types

from literate_ai.adapters.process_liveness import _close_preserving_primary_failure


def _require_original_storage(value):
    try:
        if type(value) is not _VerifierClosingPayload:
            raise TypeError("closing cleanup requires the original payload type")
        if (
            type.__getattribute__(_VerifierClosingPayload, "__mro__")
            is not _PAYLOAD_MRO
        ):
            raise ValueError("original closing payload storage changed")
        for cls, expected in _PAYLOAD_NAMESPACES:
            current = type.__getattribute__(cls, "__dict__")
            if len(current) != len(expected) or any(
                current.get(name, _ABSENT) is not item for name, item in expected
            ):
                raise ValueError("original closing payload namespace changed")
    finally:
        value = None


class _VerifierClosingPayload:
    __slots__ = (
        "_guards",
        "_releases",
        "_done",
        "_releasing",
        "_retired",
        "_failed",
        "__weakref__",
    )

    def __init__(self, guards, releases):
        try:
            if (
                type(guards) is not tuple
                or len(guards) != 4
                or type(releases) is not tuple
                or len(releases) != 3
                or any(
                    type(fn) is not types.FunctionType for fn in (*guards, *releases)
                )
            ):
                raise TypeError(
                    "closing payload requires the fixed original observations"
                )
            self._guards = guards
            self._releases = list(releases)
            self._done = [False, False, False]
            self._releasing = self._retired = self._failed = False
        finally:
            self = guards = releases = None

    def require_current(self):
        """Read-only observations; caller independently proves CLOSING ownership."""
        guard = None
        try:
            _require_original_storage(self)
            if self._retired or self._releasing or self._failed:
                raise ValueError("closing payload retired or failed")
            for guard in self._guards:
                guard()
                _require_original_storage(self)
            if self._retired or self._releasing or self._failed:
                raise ValueError("closing payload changed during observation")
        except BaseException:
            types.MemberDescriptorType.__set__(_FLAG_SLOTS["_failed"], self, True)
            raise
        finally:
            guard = None

    def _release_one(self, index):
        release = None
        try:
            _require_original_storage(self)
            if not self._done[index]:
                release = self._releases[index]
                release()
                _require_original_storage(self)
                self._done[index] = True
            # A cancellation after recording success may still leave the cleared
            # callback attached. Resume that detachment without calling it again.
            self._releases[index] = None
        finally:
            release = None

    def release(self, _release_one=_release_one):
        """Resume owned cleanup outside locks while its original charge survives.

        An uncertain component completion may be retried because the three fixed
        component releases clear DATA idempotently; no mutation or CLOSED report
        is replayed here. Completed components are never called a second time.
        """
        if types.MemberDescriptorType.__get__(
            _FLAG_SLOTS["_releasing"], self, _VerifierClosingPayload
        ):
            raise ValueError("closing payload cleanup reentered")
        types.MemberDescriptorType.__set__(_FLAG_SLOTS["_retired"], self, True)
        failure = closer = None
        try:
            _require_original_storage(self)
            if not self._releases:
                return
            types.MemberDescriptorType.__set__(_FLAG_SLOTS["_releasing"], self, True)
            for index in (0, 1, 2):
                try:

                    def closer(index=index):
                        _release_one(self, index)

                    _close_preserving_primary_failure(closer, failure)
                except BaseException as error:
                    failure = error
                finally:
                    closer = None
            if failure is not None:
                raise failure
            _require_original_storage(self)
            if all(self._done):
                self._guards = ()
                self._releases.clear()
        finally:
            types.MemberDescriptorType.__set__(_FLAG_SLOTS["_releasing"], self, False)
            failure = closer = None


# The pool calls the original fixed class function, never a payload-provided
# property, method override, destructor or arbitrary duck-typed release hook.
_RELEASE_CLOSING_PAYLOAD = _VerifierClosingPayload.release
_REQUIRE_CLOSING_PAYLOAD = _VerifierClosingPayload.require_current

_ABSENT = object()
_PAYLOAD_MRO = type.__getattribute__(_VerifierClosingPayload, "__mro__")
_PAYLOAD_NAMESPACES = tuple(
    (cls, tuple(type.__getattribute__(cls, "__dict__").items())) for cls in _PAYLOAD_MRO
)
_FLAG_SLOTS = {
    name: vars(_VerifierClosingPayload)[name]
    for name in ("_retired", "_releasing", "_failed")
}


_ORIGINAL_PAYLOAD_INIT = _VerifierClosingPayload.__init__


def _new_closing_payload(guards, releases):
    """Fixed construction; never dispatch a replaced constructor or field setter."""
    value = None
    try:
        value = object.__new__(_VerifierClosingPayload)
        _require_original_storage(value)
        _ORIGINAL_PAYLOAD_INIT(value, guards, releases)
        return value
    finally:
        value = guards = releases = None
