"""Original verifier acknowledgement membership; never classification or grants.

This dependency-light owner retains bounded pre-binding facts separately from
configuration/runtime membership. Only the fixed composition owner may construct
registrations. A digest describes intent; it never retrieves authority.
"""

import threading
import types
import weakref

from literate_ai.contracts import canonical_identity

_MAX_ACKNOWLEDGEMENTS = 64
_LOCK = threading.RLock()
_ORIGINAL_LOCK = _LOCK
_ACKNOWLEDGEMENTS = {}
_DENIED = False


class NodeSDKVerifierExecutionAcknowledgement:
    __slots__ = ("_registration", "__weakref__")

    def __init__(self):
        raise TypeError("verifier acknowledgement requires its fixed factory")

    def __copy__(self):
        raise TypeError("verifier acknowledgement cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("verifier acknowledgement cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("verifier acknowledgement cannot be serialized")


class _AcknowledgementState:
    __slots__ = ("_values",)


_ACK_CLASS = NodeSDKVerifierExecutionAcknowledgement
_STATE_CLASS = _AcknowledgementState
_ACK_SLOT = vars(_ACK_CLASS)["_registration"]
_STATE_SLOT = vars(_STATE_CLASS)["_values"]
_NAMESPACES = tuple(
    (cls, type.__getattribute__(cls, "__mro__"), tuple(vars(cls).items()))
    for cls in (_ACK_CLASS, _STATE_CLASS)
)


def _require_namespace():
    if _DENIED:
        raise ValueError("verifier acknowledgement registry is unavailable")
    if (
        NodeSDKVerifierExecutionAcknowledgement is not _ACK_CLASS
        or _AcknowledgementState is not _STATE_CLASS
    ):
        raise ValueError("original verifier acknowledgement class changed")
    for cls, mro, original in _NAMESPACES:
        current = type.__getattribute__(cls, "__dict__")
        if (
            type.__getattribute__(cls, "__mro__") is not mro
            or len(current) != len(original)
            or any(current.get(name) is not value for name, value in original)
        ):
            raise ValueError("original verifier acknowledgement class changed")


def _values(state):
    return types.MemberDescriptorType.__get__(_STATE_SLOT, state, _STATE_CLASS)


def _write(state, values):
    types.MemberDescriptorType.__set__(_STATE_SLOT, state, values)


def _poison(state):
    global _DENIED
    try:
        with _ORIGINAL_LOCK:
            facts, identity, originals, bound, _ = _values(state)
            _write(state, (facts, identity, originals, bound, True))
    except BaseException:
        # An uncertain failure update cannot leave another registration usable.
        # Cleanup remains available; this process cannot create/use new intent.
        _DENIED = True
        raise


def _poison_preserving_failure(state):
    try:
        _poison(state)
    except BaseException:
        # _poison has installed the process-lifetime denial fence. Keep the
        # original binding/validation exception rather than its cleanup failure.
        pass


def _facts(value):
    # All source/policy semantics belong to the fixed issuer. This owner accepts
    # only a small primitive tuple, never arbitrary JSON or callback-bearing DATA.
    if (
        type(value) is not tuple
        or not 1 <= len(value) <= 16
        or any(type(item) not in (str, int, bool) for item in value)
        or any(
            type(item) is str and (len(item) > 4096 or len(item.encode("utf-8")) > 4096)
            for item in value
        )
        or any(type(item) is int and not 0 <= item < 2**53 for item in value)
    ):
        raise ValueError("verifier acknowledgement facts exceed their closed bound")
    return value


def _drop_registration(key, reference):
    _retained = None
    try:
        with _LOCK:
            entry = _ACKNOWLEDGEMENTS.get(key)
            if entry is not None and entry[0] is reference:
                _retained = _ACKNOWLEDGEMENTS.pop(key)
    finally:
        # A registration can own source snapshots; release outside the lock.
        try:
            _release_retained(_retained)
        finally:
            entry = _retained = None


def _release_retained(entry):
    """Run only the fixed owner's private retirement action, outside the mutex."""
    global _DENIED
    try:
        if entry is not None and entry[4] is not None:
            entry[4]()
    except BaseException:
        _DENIED = True
        raise
    finally:
        entry = None


def _new_acknowledgement(facts, originals):
    """Fixed-owner seam only; not a caller's execution acknowledgement API."""
    _require_namespace()
    facts = _facts(facts)
    if type(originals) is not tuple or len(originals) != 2:
        raise TypeError("verifier acknowledgement requires original authority owners")
    identity = canonical_identity(
        {"schema": "literate-ai/node-sdk-verifier-acknowledgement@1", "facts": facts}
    ).uri
    state = handle = None
    try:
        with _LOCK:
            if len(_ACKNOWLEDGEMENTS) >= _MAX_ACKNOWLEDGEMENTS:
                raise ValueError("verifier acknowledgement capacity exhausted")
            handle = object.__new__(_ACK_CLASS)
            state = object.__new__(_STATE_CLASS)
            token = object()
            _write(state, (facts, identity, originals, None, False))
            types.MemberDescriptorType.__set__(_ACK_SLOT, handle, token)
            key = id(handle)
            reference = weakref.ref(
                handle, lambda ref, drop=_drop_registration: drop(key, ref)
            )
            _require_namespace()
            _ACKNOWLEDGEMENTS[key] = reference, state, token, None, None
        return handle
    finally:
        # Failed construction must not release original owners under _LOCK.
        state = handle = originals = None


def _state(handle):
    try:
        _require_namespace()
    except BaseException:
        # The original registry is sufficient to poison membership even when
        # class storage is unavailable. Never invoke the substituted descriptor.
        with _LOCK:
            entry = _ACKNOWLEDGEMENTS.get(id(handle))
            if entry is not None and entry[0]() is handle:
                _poison_preserving_failure(entry[1])
        raise
    if type(handle) is not _ACK_CLASS:
        raise TypeError("verifier acknowledgement is not its original handle")
    with _LOCK:
        entry = _ACKNOWLEDGEMENTS.get(id(handle))
        if entry is None or entry[0]() is not handle:
            raise ValueError("verifier acknowledgement is foreign or retired")
        state = entry[1]
        try:
            original_slot = types.MemberDescriptorType.__get__(
                _ACK_SLOT, handle, _ACK_CLASS
            )
        except BaseException:
            _poison_preserving_failure(state)
            raise
        if original_slot is not entry[2]:
            _poison(state)
        if _values(state)[4]:
            raise ValueError("verifier acknowledgement was poisoned")
        return state


def _require_originals(state, facts, originals):
    expected_facts, _identity, expected_originals, _bound, _failed = _values(state)
    observed = _facts(facts)
    if (
        len(observed) != len(expected_facts)
        or any(
            type(a) is not type(b) or a != b
            for a, b in zip(observed, expected_facts, strict=True)
        )
        or type(originals) is not tuple
        or len(originals) != len(expected_originals)
        or any(a is not b for a, b in zip(originals, expected_originals, strict=True))
    ):
        _poison(state)
        raise ValueError("verifier acknowledgement authority changed")


def _attach_policy_owner(handle, policy_owner, *, retire=None):
    """Attach the fixed issuer once, before consumption; never inspect its DATA.

    The issuer must keep only a weak reference back to the acknowledgement. This
    registry owns its lifetime and releases it outside the membership mutex.
    """
    state = None
    try:
        with _LOCK:
            state = _state(handle)
            entry = _ACKNOWLEDGEMENTS[id(handle)]
            if (
                policy_owner is None
                or entry[3] is not None
                or _values(state)[3] is not None
                or (retire is not None and type(retire) is not types.FunctionType)
            ):
                raise ValueError("verifier policy owner requires one unconsumed intent")
            _ACKNOWLEDGEMENTS[id(handle)] = (*entry[:3], policy_owner, retire)
    except BaseException:
        if state is not None:
            _poison_preserving_failure(state)
        raise


def _registered_policy_owner(handle):
    """Original registration lookup only; a content identity is never a key."""
    state = None
    try:
        with _LOCK:
            state = _state(handle)
            policy_owner = _ACKNOWLEDGEMENTS[id(handle)][3]
            if policy_owner is None:
                raise ValueError("verifier acknowledgement has no fixed policy owner")
            return policy_owner
    except BaseException:
        if state is not None:
            _poison_preserving_failure(state)
        raise


def _bind_acknowledgement(handle, configuration, runtime, *, facts, originals):
    """Consume original intent once; no callback or issuer runs in this seam."""
    state = None
    try:
        with _LOCK:
            state = _state(handle)
            _require_originals(state, facts, originals)
            before, identity, owners, bound, failed = _values(state)
            if bound is not None:
                raise ValueError("verifier acknowledgement was already consumed")
            bound = weakref.ref(configuration), weakref.ref(runtime)
            _write(state, (before, identity, owners, bound, failed))
    except BaseException:
        if state is not None:
            _poison_preserving_failure(state)
        raise


def _require_acknowledgement(handle, configuration, runtime, *, facts, originals):
    state = None
    try:
        with _LOCK:
            state = _state(handle)
            _require_originals(state, facts, originals)
            _facts_value, identity, _owners, bound, _failed = _values(state)
            configuration_target = None if bound is None else bound[0]()
            runtime_target = None if bound is None else bound[1]()
            if (
                configuration_target is None
                or runtime_target is None
                or (
                    configuration_target is not configuration
                    or runtime_target is not runtime
                )
            ):
                raise ValueError("verifier acknowledgement runtime changed")
            return identity
    except BaseException:
        if state is not None:
            _poison_preserving_failure(state)
        raise


def _retire_acknowledgement(handle):
    _retained = None
    try:
        with _LOCK:
            entry = _ACKNOWLEDGEMENTS.get(id(handle))
            if entry is None:
                return
            if entry[0]() is not handle:
                raise ValueError("verifier acknowledgement retirement is foreign")
            # Retirement can drain a poisoned/substituted handle without invoking
            # its fields, class methods, or the original owners' callbacks.
            _retained = _ACKNOWLEDGEMENTS.pop(id(handle))
    finally:
        try:
            _release_retained(_retained)
        finally:
            entry = _retained = None
