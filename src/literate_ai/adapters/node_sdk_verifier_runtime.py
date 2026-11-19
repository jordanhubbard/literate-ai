"""Original runtime/operation joins for inspection, never execution grants.

Opaque handles have no writable authority. Independently owned state retains only
bounded membership metadata, never released inspection closures or tool readsets.
"""

import dataclasses
import threading
import types
import weakref
from contextlib import contextmanager
from datetime import datetime
from enum import Enum, EnumType
from functools import wraps
from pathlib import PosixPath, PurePosixPath, PureWindowsPath, WindowsPath

from literate_ai.adapters.process_liveness import _close_preserving_primary_failure
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.node_sdk import MAX_NODE_SDK_PROVIDERS

_BINDINGS = weakref.WeakKeyDictionary()
_OPERATIONS = weakref.WeakKeyDictionary()
_TICKETS = weakref.WeakKeyDictionary()


_MISSING = object()


def _supported_records():
    # A closed registry of framework-owned class objects, captured before any
    # instance/operation callbacks. User-supplied dataclass types are not admitted.
    import literate_ai.contracts as contracts
    from literate_ai.adapters import node_sdk_generation
    from literate_ai.adapters.models import coding_cli
    from literate_ai.application import (
        component_generation_context,
        component_generation_preparation,
    )
    from literate_ai.contracts.node_sdk import (
        CommonJSModuleDeclaration,
        NodeSDKExportDeclaration,
    )

    classes = {
        getattr(contracts, name)
        for name in contracts.__all__
        if isinstance(getattr(contracts, name), type)
    }
    from literate_ai.security.policy import (
        BuildAuthorization,
        BuildRequest,
        SecurityProfile,
    )

    classes.update(
        (
            CommonJSModuleDeclaration,
            NodeSDKExportDeclaration,
            BuildAuthorization,
            BuildRequest,
            SecurityProfile,
        )
    )
    for module in (
        coding_cli,
        node_sdk_generation,
        component_generation_context,
        component_generation_preparation,
    ):
        classes.update(
            value for value in vars(module).values() if isinstance(value, type)
        )
    records, enums = {}, set()
    for cls in classes:
        if issubclass(cls, Enum):
            enums.add(cls)
        if type(cls) is not type or not dataclasses.is_dataclass(cls):
            continue
        mro = type.__getattribute__(cls, "__mro__")
        dict_lookup = tuple(
            (base, type.__getattribute__(base, "__dict__").get("__dict__", _MISSING))
            for base in mro
        )
        dict_descriptor = next(
            (value for _, value in dict_lookup if value is not _MISSING), None
        )
        dict_slot = None if dict_descriptor is None else (dict_lookup, dict_descriptor)
        fields = []
        supported = True
        for field in dataclasses.fields(cls):
            if field.name.startswith("_"):
                continue
            declaring = next(
                (
                    base
                    for base in mro
                    if field.name in type.__getattribute__(base, "__dict__")
                ),
                cls,
            )
            descriptor = type.__getattribute__(declaring, "__dict__").get(
                field.name, _MISSING
            )
            lookup = tuple(
                (
                    base,
                    type.__getattribute__(base, "__dict__").get(field.name, _MISSING),
                )
                for base in mro
            )
            if type(descriptor) is types.MemberDescriptorType:
                fields.append((field.name, lookup, descriptor, "slot"))
            elif (
                dict_slot is not None
                and type(dict_slot[1]) is types.GetSetDescriptorType
                and (descriptor is _MISSING or not hasattr(type(descriptor), "__get__"))
            ):
                fields.append((field.name, lookup, descriptor, "dict"))
            else:
                supported = False
                break
        if supported:
            records[cls] = (mro, dict_slot, tuple(fields))
    return records, frozenset(enums)


_SUPPORTED_RECORDS, _SUPPORTED_ENUMS = _supported_records()


def _record_values(value, spec):
    cls = type(value)
    mro, dict_slot, fields = spec
    if type.__getattribute__(cls, "__mro__") is not mro:
        raise ValueError("inspection record type changed")
    data = None
    if any(storage == "dict" for _, _, _, storage in fields):
        # Invoke only the original C storage descriptor, never a Python property.
        dict_lookup, descriptor = dict_slot
        if any(
            type.__getattribute__(base, "__dict__").get("__dict__", _MISSING)
            is not expected
            for base, expected in dict_lookup
        ):
            raise ValueError("inspection record dictionary descriptor changed")
        data = types.GetSetDescriptorType.__get__(descriptor, value, cls)
        if type(data) is not dict or any(
            type(key) is not str for key in dict.keys(data)
        ):
            raise ValueError("inspection record has substituted dictionary keys")
    result = []
    for name, lookup, descriptor, storage in fields:
        if any(
            type.__getattribute__(base, "__dict__").get(name, _MISSING) is not expected
            for base, expected in lookup
        ):
            raise ValueError("inspection record field descriptor changed")
        if storage == "slot":
            item = types.MemberDescriptorType.__get__(descriptor, value, cls)
        else:
            if not dict.__contains__(data, name):
                raise ValueError("inspection record field lacks original storage")
            item = dict.__getitem__(data, name)
        result.append(item)
    return tuple(result)


def _finite_metadata(*roots):
    """Bounded public storage observations; no properties or serializers.

    Opaque path/datetime values and enum internals retain original references only.
    Existing lifecycle owners still fence physical and execution ownership.
    """
    records, seen = [], set()
    size = 0
    primitive = (str, bytes, int, bool, float, type(None))

    def visit(value, depth=0):
        nonlocal size
        kind = type(value)
        if type(kind) is not type and type(kind) is not EnumType:
            raise TypeError("unsupported finite inspection metadata metaclass")
        if depth > 64:
            raise ValueError("inspection metadata exceeds its depth bound")
        if id(value) in seen:
            return
        seen.add(id(value))
        if len(seen) > 65536:
            raise ValueError("inspection metadata exceeds its node bound")
        if type(value) in primitive:
            size += (
                (len(value) if str.isascii(value) else 4 * len(value))
                if type(value) is str
                else len(value)
                if type(value) is bytes
                else 8
            )
            if size > 64 * 1024 * 1024:
                raise ValueError("inspection metadata exceeds its byte bound")
            return
        if type(value) in _SUPPORTED_ENUMS or type(value) in (
            PosixPath,
            WindowsPath,
            PurePosixPath,
            PureWindowsPath,
            datetime,
        ):
            return
        if type(value) in (tuple, list):
            items = tuple(value)
            records.append(("sequence", value, items))
        elif type(value) is dict:
            if any(type(k) is not str for k in dict.keys(value)):
                raise ValueError(
                    "inspection metadata requires exact primitive mapping keys"
                )
            items = tuple(dict.items(value))
            records.append(("mapping", value, items))
            items = tuple(v for _, v in items)
        elif type(value) in _SUPPORTED_RECORDS:
            items = _record_values(value, _SUPPORTED_RECORDS[type(value)])
            records.append(
                ("record", value, (type(value), _SUPPORTED_RECORDS[type(value)], items))
            )
        else:
            raise TypeError("unsupported finite inspection metadata record")
        for item in items:
            visit(item, depth + 1)

    for root in roots:
        visit(root)

    def same(actual, expected):
        return (
            type(actual) is type(expected) and actual == expected
            if type(expected) in primitive
            else actual is expected
        )

    def require_original():
        for kind, value, baseline in records:
            if kind == "mapping":
                if any(type(key) is not str for key in dict.keys(value)):
                    raise ValueError("inspection mapping key type changed")
                current = tuple(dict.items(value))
                valid = len(current) == len(baseline) and all(
                    a[0] == b[0] and same(a[1], b[1])
                    for a, b in zip(current, baseline, strict=True)
                )
            else:
                if kind == "record":
                    cls, spec, baseline = baseline
                    if type(value) is not cls:
                        raise ValueError("inspection record type changed")
                    current = _record_values(value, spec)
                else:
                    current = tuple(value)
                valid = len(current) == len(baseline) and all(
                    same(a, b) for a, b in zip(current, baseline, strict=True)
                )
            if not valid:
                raise ValueError("inspection original finite metadata changed")

    require_original()
    return require_original


class _InspectionTicket:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("inspection tickets require original runtime enrollment")

    def require_current(self):
        record = _TICKETS.get(self)
        state = None if record is None else record[0]()
        if state is None:
            raise ValueError("inspection ticket operation ended")
        state.require_ticket(self)


class _RuntimeInspectionOperation:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("inspection operations require original runtime entry")

    def require_current(self):
        _operation_state(self).require_live()


class _RuntimeInspectionBinding:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("inspection bindings require original host assembly")


class _BindingState:
    def __init__(self, handle, bound):
        self.handle = handle
        self.originals = (
            bound,
            bound.configuration,
            bound.ports,
            bound.closure,
            bound.consumer,
            bound.target,
        )
        self.active = None
        self.lock = threading.RLock()

    def require_finite(self):
        bound, configuration, ports, closure, consumer, target = self.originals
        if (
            bound._inspection_binding is not self.handle
            or bound._inspection_registration is not self
            or bound.configuration is not configuration
            or bound.ports is not ports
            or bound.closure is not closure
            or bound.consumer is not consumer
            or bound.target is not target
            or configuration._binding is not bound
            or configuration._original_binding is not bound
            or ports._node_sdk_host_binding is not bound
        ):
            raise ValueError("inspection lost its original runtime binding")

    @contextmanager
    def operation(self, execution, prepared, receipts):
        self.require_finite()
        with self.lock:
            if self.active is not None:
                self.active._poisoned = True
                raise ValueError("runtime inspection operations cannot nest")
            handle = object.__new__(_RuntimeInspectionOperation)
            state = _OperationState(self, handle)
            self.active = state
            _OPERATIONS[handle] = weakref.ref(state)
            try:
                state.start(execution, prepared, receipts)
            except BaseException:
                state.retire()
                self.active = None
                raise
        primary = None
        try:
            state.require_live()
            yield handle
        except BaseException as error:
            primary = error
            state._poisoned = True
            raise
        finally:
            try:
                _close_preserving_primary_failure(state.close, primary)
            finally:
                with self.lock:
                    state.retire()
                    if self.active is state:
                        self.active = None
                primary = None


def _poison_on_failure(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        with self.binding.lock:
            try:
                return method(self, *args, **kwargs)
            except BaseException:
                self._poisoned = True
                raise

    return guarded


class _OperationState:
    def __init__(self, binding, handle):
        self.binding, self.handle = binding, handle
        self._execution = self._prepared = self._invocation = None
        self._receipts, self._seams, self._tickets = {}, {}, {}
        self._witness = self._invocation_witness = None
        self._poisoned = False
        self._state = "OPENING"

    @_poison_on_failure
    def start(self, execution, prepared, receipts):
        from literate_ai.application.component_generation_preparation import (
            PreparedComponentGenerationNode,
        )
        from literate_ai.contracts import (
            ComponentExecutionPlan,
            StandardComponentAcceptanceEvidence,
        )

        bound = self.binding.originals[0]
        if (
            type(execution) is not ComponentExecutionPlan
            or type(prepared) is not PreparedComponentGenerationNode
            or execution.identity != bound.configuration.expected_execution.identity
            or type(receipts) is not tuple
            or not 1 <= len(receipts) <= MAX_NODE_SDK_PROVIDERS
            or any(
                type(row) is not StandardComponentAcceptanceEvidence for row in receipts
            )
        ):
            raise TypeError(
                "inspection requires original bounded execution and receipts"
            )
        by_revision = {row.component_revision.uri: row for row in receipts}
        if len(by_revision) != len(receipts) or set(by_revision) != set(
            bound.revisions
        ):
            raise ValueError("inspection provider membership differs from runtime")
        self._execution, self._prepared = execution, prepared
        self._prepared_identity = prepared.recipe.identity
        self._receipts = by_revision
        self._witness = _finite_metadata(execution, prepared, receipts)
        self._sealed = False
        self._state = "LIVE"

    @_poison_on_failure
    def require_live(self):
        with self.binding.lock:
            if (
                self._state != "LIVE"
                or self._poisoned
                or self.binding.active is not self
            ):
                raise ValueError("runtime inspection operation ended or poisoned")
            self.binding.require_finite()

    @_poison_on_failure
    def provider(self, ports, scope, revision, oracle, compiler):
        self.require_live()
        self._witness()
        binding = self.binding
        with binding.lock:
            bound = binding.originals[0]
            key = revision.identity.uri
            if (
                self._sealed
                or key in self._seams
                or ports is not bound.ports
                or bound.revisions.get(key) is not revision
                or bound.configuration.provider_oracles.get(key) is not oracle
                or bound.target.typescript.compiler is not compiler
                or self._receipts.get(key) is not scope.acceptance
            ):
                self._poisoned = True
                raise ValueError(
                    "inspection provider seam differs from original operation"
                )
            ports._require_library_provider_membership(scope)
            self._seams[key] = (
                weakref.ref(scope),
                scope.export.identity.uri,
                scope.contract.identity.uri,
                revision,
                oracle,
                compiler,
            )

    @_poison_on_failure
    def seal(self, execution, prepared, invocation, providers):
        self.require_live()
        self._witness()
        binding = self.binding
        with binding.lock:
            if (
                self._sealed
                or execution is not self._execution
                or prepared is not self._prepared
                or set(self._seams) != set(self._receipts)
                or len(providers) != len(self._receipts)
                or {row.artifact.component_revision.uri for row in providers}
                != set(self._receipts)
                or invocation.base_recipe.uri != self._prepared_identity
                or invocation.prepared.plan is not self._prepared.plan
                or invocation.prepared.workspace is not self._prepared.workspace
                or len(invocation.prepared.recipe.node_sdk_providers) != len(providers)
                or any(
                    a is not b
                    for a, b in zip(
                        invocation.prepared.recipe.node_sdk_providers,
                        providers,
                        strict=True,
                    )
                )
            ):
                self._poisoned = True
                raise ValueError(
                    "inspection invocation cannot replace original membership"
                )
            for row in providers:
                key = row.artifact.component_revision.uri
                seam = self._seams.get(key)
                if (
                    seam is None
                    or row.artifact.identity.uri != seam[1]
                    or row.acceptance != self._receipts[key].identity
                    or row.oracle != seam[4].identity
                    or row.compiler != seam[5].identity
                ):
                    self._poisoned = True
                    raise ValueError(
                        "actual invocation differs from original provider seam"
                    )
            self._invocation, self._invocation_identity = (
                invocation,
                invocation.identity.uri,
            )
            self._invocation_witness = _finite_metadata(invocation)
            self._sealed = True

    @_poison_on_failure
    def require_invocation(self, ports, execution, invocation):
        self.require_live()
        bound = self.binding.originals[0]
        if (
            not self._sealed
            or ports is not bound.ports
            or execution is not self._execution
            or invocation is not self._invocation
        ):
            raise ValueError("inspection requires the actual original invocation")

    @_poison_on_failure
    def enroll(self, owner, description):
        from literate_ai.adapters.node_library_verifier_inspection import (
            _ProviderInspectionOwner,
            _RootInspectionOwner,
        )

        self.require_live()
        self._witness()
        binding = self.binding
        with binding.lock:
            bound = binding.originals[0]
            key = owner.revision.identity.uri
            if type(owner) is _ProviderInspectionOwner:
                seam = self._seams.get(key)
                valid = (
                    not self._sealed
                    and seam is not None
                    and seam[0]() is owner.subject
                    and seam[3] is owner.revision
                    and seam[4] is owner.oracle
                    and seam[5] is owner.compiler
                    and owner.subject.acceptance is self._receipts.get(key)
                )
                role = "provider"
            elif type(owner) is _RootInspectionOwner:
                policy = owner.prepared.policy
                valid = (
                    self._sealed
                    and policy.inspection_operation is self.handle
                    and policy.invocation is self._invocation
                    and policy.execution is self._execution
                    and policy.oracle is bound.configuration.root_oracle
                    and owner.compiler is bound.target.typescript.compiler
                    and key == bound.configuration.expected_execution.root_revision.uri
                )
                role = "root"
            else:
                raise TypeError(
                    "inspection enrollment requires its original resource owner"
                )
            slot = role, key
            if not valid or owner.ports is not bound.ports or slot in self._tickets:
                self._poisoned = True
                raise ValueError(
                    "inspection enrollment has foreign, late or repeated membership"
                )
            if (
                description.owner_revision_uri != key
                or len(self._tickets) >= MAX_NODE_SDK_PROVIDERS + 1
            ):
                self._poisoned = True
                raise ValueError(
                    "inspection enrollment exceeds its exact role or capacity"
                )
            facts = (role, key, canonical_identity(description.request.to_dict()).uri)
            ticket = object.__new__(_InspectionTicket)
            self._tickets[slot] = [ticket, facts, "CAPTURING"]
            _TICKETS[ticket] = weakref.ref(self), facts
            return ticket

    @_poison_on_failure
    def require_ticket(self, ticket):
        self.require_live()
        self._witness()
        record = _TICKETS.get(ticket)
        if record is None or record[0]() is not self:
            raise ValueError("inspection ticket is copied or changed")
        stored = self._tickets.get(record[1][:2])
        if stored is None or stored[0] is not ticket or stored[2] == "FAILED":
            raise ValueError("inspection ticket is copied or failed")

    @_poison_on_failure
    def report_capture(self, ticket, *, failed):
        record = _TICKETS.get(ticket)
        stored = None if record is None else self._tickets.get(record[1][:2])
        if (
            stored is None
            or stored[0] is not ticket
            or (not failed and stored[2] != "CAPTURING")
        ):
            self._poisoned = True
            raise ValueError("inspection capture lifecycle changed")
        stored[2] = "FAILED" if failed else "CLOSED"
        if failed:
            self._poisoned = True

    @_poison_on_failure
    def close(self):
        self._state = "CLOSING"
        if self._poisoned or not self._sealed:
            raise ValueError("inspection operation failed or lacks actual invocation")
        self.binding.require_finite()
        self._witness()
        self._invocation_witness()
        if (
            self._poisoned
            or self.binding.active is not self
            or self._state != "CLOSING"
        ):
            raise ValueError("inspection operation changed during final witnesses")
        self.binding.require_finite()
        if any(record[2] != "CLOSED" for record in self._tickets.values()):
            raise ValueError("inspection operation has unclosed captures")

    def retire(self):
        self._state = "TERMINAL"
        for ticket, _facts, _capture_state in self._tickets.values():
            _TICKETS.pop(ticket, None)
        _OPERATIONS.pop(self.handle, None)
        self._receipts.clear()
        self._seams.clear()
        self._tickets.clear()
        self._execution = self._prepared = self._invocation = None
        self._witness = self._invocation_witness = None


def _operation_state(handle):
    if type(handle) is not _RuntimeInspectionOperation:
        raise TypeError("inspection requires original explicitly threaded operation")
    ref = _OPERATIONS.get(handle)
    state = None if ref is None else ref()
    if state is None or state.handle is not handle:
        raise ValueError("runtime inspection operation ended")
    return state


def create_runtime_inspection_binding(bound):
    from literate_ai.adapters.node_sdk_host import _BoundAdmission

    if type(bound) is not _BoundAdmission:
        raise TypeError("inspection binding requires original host assembly")
    if hasattr(bound, "_inspection_binding") or hasattr(
        bound, "_inspection_registration"
    ):
        raise ValueError("inspection runtime binding cannot be replaced")
    handle = object.__new__(_RuntimeInspectionBinding)
    state = _BindingState(handle, bound)
    bound._inspection_registration = state
    _BINDINGS[handle] = weakref.ref(state)
    return handle


@contextmanager
def runtime_inspection_operation(bound, execution, prepared, receipts):
    handle = bound._inspection_binding
    ref = _BINDINGS.get(handle) if type(handle) is _RuntimeInspectionBinding else None
    state = None if ref is None else ref()
    if state is None or state.originals[0] is not bound:
        raise ValueError("inspection operation requires original runtime binding")
    with state.operation(execution, prepared, receipts) as operation:
        yield operation


def register_node_verifier_provider(
    operation, ports, scope, revision, oracle, compiler
):
    _operation_state(operation).provider(ports, scope, revision, oracle, compiler)


def seal_node_verifier_invocation(
    operation, execution, prepared, invocation, providers
):
    _operation_state(operation).seal(execution, prepared, invocation, providers)


def require_node_verifier_invocation(operation, ports, execution, invocation):
    _operation_state(operation).require_invocation(ports, execution, invocation)


def enroll_node_verifier_capture(operation, owner, description):
    return _operation_state(operation).enroll(owner, description)


def report_node_verifier_capture(operation, ticket, *, failed):
    _operation_state(operation).report_capture(ticket, failed=failed)
