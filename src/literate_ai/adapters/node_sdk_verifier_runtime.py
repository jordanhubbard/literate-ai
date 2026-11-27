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
_GRANT_OPERATIONS = weakref.WeakKeyDictionary()
_GRANT_MEMBERSHIP_LOCK = threading.RLock()


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
    from literate_ai.contracts.library_imports import AuthoredLibraryImport
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
        FindingSeverity,
        SecurityClassification,
        SecurityProfile,
    )

    classes.update(
        (
            AuthoredLibraryImport,
            CommonJSModuleDeclaration,
            NodeSDKExportDeclaration,
            BuildAuthorization,
            BuildRequest,
            FindingSeverity,
            SecurityClassification,
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
    data = result = item = None
    try:
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
                type.__getattribute__(base, "__dict__").get(name, _MISSING)
                is not expected
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
    finally:
        value = data = item = None
        if result is not None:
            result.clear()


def _finite_metadata(*roots, _with_release=False):
    """Bounded public storage observations; no properties or serializers.

    Opaque path/datetime values and enum internals retain original references only.
    Existing lifecycle owners still fence physical and execution ownership.
    Opt-in release returns (guard, release, primitive-source estimate). The owner
    must separately account metadata, opaque values and any unobserved storage.
    Release requires the owner's in-flight readers to have settled.
    """
    if type(_with_release) is not bool:
        raise TypeError("finite metadata release selection requires an exact bool")
    records, seen = [], set()
    released = False
    size = 0
    primitive = (str, bytes, int, bool, float, type(None))

    def visit(value, depth=0):
        nonlocal size
        items = item = key = _value = None
        try:
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
                if _with_release:
                    for key, _value in items:
                        visit(key, depth + 1)
                items = tuple(v for _, v in items)
            elif type(value) in _SUPPORTED_RECORDS:
                items = _record_values(value, _SUPPORTED_RECORDS[type(value)])
                records.append(
                    (
                        "record",
                        value,
                        (type(value), _SUPPORTED_RECORDS[type(value)], items),
                    )
                )
            else:
                raise TypeError("unsupported finite inspection metadata record")
            for item in items:
                visit(item, depth + 1)
        finally:
            value = items = item = key = _value = None

    try:
        for root in roots:
            visit(root)
    except BaseException:
        records.clear()
        raise
    finally:
        roots = ()
        root = None

    def same(actual, expected):
        try:
            return (
                type(actual) is type(expected) and actual == expected
                if type(expected) in primitive
                else actual is expected
            )
        finally:
            actual = expected = None

    def require_original():
        if released:
            raise ValueError("finite metadata observation was released")
        try:
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
            if released:
                raise ValueError(
                    "finite metadata observation retired during validation"
                )
        finally:
            value = baseline = current = cls = spec = None

    def release():
        nonlocal released
        try:
            released = True
        finally:
            records.clear()

    try:
        require_original()
    except BaseException:
        release()
        raise
    return (require_original, release, size) if _with_release else require_original


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

    def _resume_retiring(self):
        with self.lock:
            state = self.active
            if state is None or not state._retiring:
                return
        state.retire()
        with self.lock:
            if self.active is state and state._retirement_complete:
                self.active = None

    @contextmanager
    def operation(self, execution, prepared, receipts):
        state = primary = None
        try:
            self._resume_retiring()
            self.require_finite()
            with self.lock:
                if self.active is not None:
                    self.active._poisoned = True
                    raise ValueError("runtime inspection operations cannot nest")
                handle = object.__new__(_RuntimeInspectionOperation)
                state = _OperationState(self, handle)
                self.active = state
                _OPERATIONS[handle] = weakref.ref(state)
            state.start(execution, prepared, receipts)
            state.require_live()
            yield handle
        except BaseException as error:
            primary = error
            if state is not None:
                state._poisoned = True
            raise
        finally:
            if state is not None:
                try:
                    try:
                        _close_preserving_primary_failure(state.close, primary)
                    except BaseException as error:
                        primary = error
                        state._poisoned = True
                        raise
                finally:
                    try:
                        _close_preserving_primary_failure(state.retire, primary)
                    except BaseException as error:
                        primary = error
                        state._poisoned = True
                        raise
                    finally:

                        def clear_active():
                            with self.lock:
                                if self.active is state and state._retirement_complete:
                                    self.active = None

                        try:
                            _close_preserving_primary_failure(clear_active, primary)
                        finally:
                            primary = None


def _poison_on_failure(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            with self.binding.lock:
                try:
                    return method(self, *args, **kwargs)
                except BaseException:
                    self._poisoned = True
                    raise
        except BaseException:
            # Include lock entry/exit cancellation in the failure boundary. The
            # inner guard still poisons method failures before releasing the lock.
            self._poisoned = True
            raise

    return guarded


class _OperationState:
    def __init__(self, binding, handle):
        self.binding, self.handle = binding, handle
        self._execution = self._prepared = self._invocation = None
        self._receipts, self._seams, self._tickets = {}, {}, {}
        self._scans = {}
        self._classifications = {}
        self._grants, self._grant_payloads = {}, {}
        self._grant_intent = None
        self._capture_leases, self._handoffs = {}, {}
        self._closing_publication = None
        self._witness = self._invocation_witness = None
        self._original_witness = self._original_invocation_witness = None
        self._poisoned = False
        self._state = "OPENING"
        self._resource_pool = self._resource_owner_handle = None
        self._pending_resource_owners = {}
        self._retiring = self._retirement_complete = False
        self._retirement_attempt = None

    def _settle_resource_publication(self, publication, record):
        from literate_ai.adapters.node_sdk_verifier_resources import _published_owner

        with self.binding.lock:
            if self._pending_resource_owners.get(publication) is not record:
                return
            if not record[1]:
                raise ValueError("operation resource allocation is still pending")
            pool, handle = record[0], _published_owner(publication)
        if handle is not None:
            pool.retire(handle, failed=True)
        with self.binding.lock:
            if self._pending_resource_owners.get(publication) is record:
                self._pending_resource_owners.pop(publication)

    def resource_owner_for(self, pool):
        """Journal allocation before side effects; no pool calls under binding."""
        from literate_ai.adapters.node_sdk_verifier_resources import (
            _new_owner_publication,
            _published_owner,
            _VerifierResourcePool,
        )

        publication = record = primary = None
        try:
            if type(pool) is not _VerifierResourcePool:
                raise TypeError("operation resource owner requires its exact pool")
            with self.binding.lock:
                self.require_live()
                if self._resource_pool is not None:
                    if (
                        self._resource_pool is not pool
                        or self._resource_owner_handle is None
                    ):
                        raise ValueError("operation resource pool identity changed")
                    return self._resource_owner_handle
                if len(self._pending_resource_owners) >= 33:
                    raise ValueError(
                        "operation resource allocations exceed their bound"
                    )
                publication = _new_owner_publication(pool)
                record = [pool, False]
                self._pending_resource_owners[publication] = record
            try:
                pool.create_owner(_publication=publication)
            finally:
                record[1] = True
            candidate = _published_owner(publication)
            with self.binding.lock:
                self.require_live()
                if candidate is None:
                    raise ValueError("operation resource allocation lost publication")
                if self._resource_pool is None and self._resource_owner_handle is None:
                    self._resource_pool, self._resource_owner_handle = pool, candidate
                    self._pending_resource_owners.pop(publication)
                    publication = None
                elif (
                    self._resource_pool is not pool
                    or self._resource_owner_handle is None
                ):
                    raise ValueError("operation resource owner publication changed")
                selected = self._resource_owner_handle
            return selected
        except BaseException as error:
            primary = error
            self._poisoned = True
            raise
        finally:
            if record is not None:
                # This allocator stack has finished (or never entered) its pool
                # call, including cancellation at the reservation-lock exit.
                record[1] = True
            try:
                if publication is not None:
                    try:
                        _close_preserving_primary_failure(
                            lambda: self._settle_resource_publication(
                                publication, record
                            ),
                            primary,
                        )
                    except BaseException:
                        self._poisoned = True
                        raise
            finally:
                publication = record = primary = None

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
        self._original_witness = self._witness
        self._sealed = False
        self._state = "LIVE"

    @_poison_on_failure
    def require_live(self):
        with self.binding.lock:
            if self._grant_intent is not None or self.handle in _GRANT_OPERATIONS:
                from literate_ai.adapters.node_sdk_verifier_authorization import (
                    _require_grant_state_shape,
                )

                _require_grant_state_shape(self)
            if (
                self._state != "LIVE"
                or self._poisoned
                or self.binding.active is not self
            ):
                raise ValueError("runtime inspection operation ended or poisoned")
            self.binding.require_finite()
            if self._grant_intent is not None or self.handle in _GRANT_OPERATIONS:
                from literate_ai.adapters.node_sdk_verifier_authorization import (
                    _require_live_operation_grants,
                )

                _require_live_operation_grants(self)

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
            self._original_invocation_witness = self._invocation_witness
            if self._grant_intent is not None or self.handle in _GRANT_OPERATIONS:
                from literate_ai.adapters.node_sdk_verifier_authorization import (
                    _register_grant_invocation_witness,
                )

                _register_grant_invocation_witness(self)
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
    def enroll(self, owner, description, *, resource_pool, resource_lease):
        from literate_ai.adapters.node_library_verifier_inspection import (
            _ProviderInspectionOwner,
            _RootInspectionOwner,
        )
        from literate_ai.adapters.node_sdk_verifier_resources import (
            _CaptureHandle,
            _VerifierResourcePool,
        )

        self.require_live()
        self._witness()
        if (
            type(resource_pool) is not _VerifierResourcePool
            or type(resource_lease) is not _CaptureHandle
            or any(
                pool is resource_pool and lease is resource_lease
                for pool, lease in self._capture_leases.values()
            )
        ):
            raise ValueError("inspection enrollment requires a unique original lease")
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
            self._capture_leases[ticket] = resource_pool, resource_lease
            return ticket

    def prepare_capture_handoff(
        self,
        ticket,
        pool,
        lease,
        payload,
        *,
        closing_bytes,
        compiler,
        compiler_facts,
        compiler_bytes,
    ):
        """Reserve/attach outside binding; journal only original opaque handles.

        This support does not establish capture-owner provenance by itself. The
        fixed owner must supply its enrolled lease and original closing DATA.
        Compiler source can deduplicate, but each observation keeps 2 MiB of
        metadata charged in its own closing payload, including the first one.
        """
        from literate_ai.adapters.node_sdk_verifier_closing_payload import (
            _require_original_storage,
        )
        from literate_ai.adapters.node_sdk_verifier_compiler_witness import (
            COMPILER_OBSERVATION_METADATA_BYTES,
        )

        owner_handle = join = None
        try:
            if type(closing_bytes) is not int or closing_bytes < 0:
                raise ValueError("closing resource charge requires exact byte DATA")
            _require_original_storage(payload)
            with self.binding.lock:
                self.require_ticket(ticket)
                original = self._capture_leases.get(ticket)
                if (
                    original is None
                    or original[0] is not pool
                    or original[1] is not lease
                    or ticket in self._handoffs
                    or self._tickets[_TICKETS[ticket][1][:2]][2] != "CAPTURING"
                ):
                    raise ValueError("handoff requires its original capturing lease")
            owner_handle = self.resource_owner_for(pool)
            with self.binding.lock:
                self.require_ticket(ticket)
                if (
                    self._capture_leases.get(ticket) is not original
                    or ticket in self._handoffs
                    or self._tickets[_TICKETS[ticket][1][:2]][2] != "CAPTURING"
                    or any(record[2] is lease for record in self._handoffs.values())
                ):
                    raise ValueError("handoff membership changed during reservation")
                join = [pool, owner_handle, lease, "PREPARING"]
                self._handoffs[ticket] = join
            pool.prepare_handoff(
                lease,
                owner_handle,
                closing_bytes=closing_bytes + COMPILER_OBSERVATION_METADATA_BYTES,
                compiler=compiler,
                compiler_facts=compiler_facts,
                compiler_bytes=compiler_bytes,
            )
            pool.attach_payload(lease, payload)
            with self.binding.lock:
                self.require_ticket(ticket)
                if self._handoffs.get(ticket) is not join or join[3] != "PREPARING":
                    raise ValueError("handoff lost original preparation membership")
                join[3] = "PREPARED"
        except BaseException as error:
            self._poisoned = True
            if owner_handle is not None:
                _close_preserving_primary_failure(
                    lambda: pool.retire(owner_handle, failed=True), error
                )
            raise
        finally:
            payload = compiler = compiler_facts = original = join = None

    def commit_capture_handoff(self, ticket):
        """Commit once outside binding; uncertain writes are never retried."""
        join = pool = owner_handle = lease = None
        try:
            with self.binding.lock:
                self.require_ticket(ticket)
                join = self._handoffs.get(ticket)
                if (
                    join is None
                    or join[3] != "PREPARED"
                    or join[0] is not self._resource_pool
                    or join[1] is not self._resource_owner_handle
                    or self._tickets[_TICKETS[ticket][1][:2]][2] != "CAPTURING"
                ):
                    raise ValueError("handoff cannot commit its current membership")
                pool, owner_handle, lease = join[:3]
                join[3] = "COMMITTING"
            pool.commit_handoff(lease)
            with self.binding.lock:
                self.require_ticket(ticket)
                if (
                    self._handoffs.get(ticket) is not join
                    or join[3] != "COMMITTING"
                    or self._tickets[_TICKETS[ticket][1][:2]][2] != "CAPTURING"
                ):
                    raise ValueError("handoff lost original commit membership")
                join[3] = "COMMITTED"
        except BaseException as error:
            self._poisoned = True
            if owner_handle is not None:
                _close_preserving_primary_failure(
                    lambda: pool.retire(owner_handle, failed=True), error
                )
            raise
        finally:
            join = pool = owner_handle = lease = None

    @_poison_on_failure
    def require_ticket(self, ticket):
        if type(ticket) is not _InspectionTicket:
            raise TypeError("inspection requires an exact original ticket")
        self.require_live()
        self._witness()
        record = _TICKETS.get(ticket)
        if record is None or record[0]() is not self:
            raise ValueError("inspection ticket is copied or changed")
        stored = self._tickets.get(record[1][:2])
        if stored is None or stored[0] is not ticket or stored[2] == "FAILED":
            raise ValueError("inspection ticket is copied or failed")

    @_poison_on_failure
    def begin_scan(self, ticket):
        self.require_ticket(ticket)
        record = _TICKETS[ticket]
        stored = self._tickets[record[1][:2]]
        if stored[2] != "CAPTURING" or ticket in self._scans:
            raise ValueError("SDK scan requires one original live capturing ticket")
        self._scans[ticket] = ("SCANNING", None)

    @_poison_on_failure
    def finish_scan(self, ticket, digest):
        from literate_ai.contracts import ContentIdentity

        self.require_ticket(ticket)
        record = _TICKETS[ticket]
        stored = self._tickets[record[1][:2]]
        if (
            stored[2] != "CAPTURING"
            or self._scans.get(ticket) != ("SCANNING", None)
            or type(digest) is not str
            or len(digest) != 71
            or not digest.startswith("sha256:")
        ):
            raise ValueError("SDK scan lost its original capturing reservation")
        ContentIdentity.parse_uri(digest)
        self._scans[ticket] = ("SCANNED", digest)

    def fail_scan(self, ticket):
        with self.binding.lock:
            self._poisoned = True
            if type(ticket) is _InspectionTicket and ticket in self._scans:
                self._scans[ticket] = ("FAILED", None)

    @_poison_on_failure
    def begin_classification(self, ticket, acknowledgement):
        from literate_ai.contracts import ContentIdentity

        self.require_ticket(ticket)
        record = _TICKETS[ticket]
        stored = self._tickets[record[1][:2]]
        if (
            stored[2] != "CAPTURING"
            or ticket in self._scans
            or ticket in self._classifications
            or type(acknowledgement) is not str
            or len(acknowledgement) != 71
            or not acknowledgement.startswith("sha256:")
        ):
            raise ValueError(
                "SDK classification requires one original unscanned capture"
            )
        ContentIdentity.parse_uri(acknowledgement)
        self._classifications[ticket] = ("CLASSIFYING", acknowledgement, None, None)

    @_poison_on_failure
    def finish_classification(
        self, ticket, acknowledgement, observation, classification
    ):
        from literate_ai.contracts import ContentIdentity

        self.require_ticket(ticket)
        record = _TICKETS[ticket]
        stored = self._tickets[record[1][:2]]
        if (
            stored[2] != "CAPTURING"
            or type(acknowledgement) is not str
            or self._classifications.get(ticket)
            != ("CLASSIFYING", acknowledgement, None, None)
            or self._scans.get(ticket, (None,))[0] != "SCANNED"
        ):
            raise ValueError("SDK classification lost its original capture reservation")
        for digest in (observation, classification):
            if (
                type(digest) is not str
                or len(digest) != 71
                or not digest.startswith("sha256:")
            ):
                raise ValueError(
                    "SDK classification requires bounded content identities"
                )
            ContentIdentity.parse_uri(digest)
        self._classifications[ticket] = (
            "CLASSIFIED",
            acknowledgement,
            observation,
            classification,
        )

    def fail_classification(self, ticket):
        with self.binding.lock:
            self._poisoned = True
            if type(ticket) is _InspectionTicket and ticket in self._classifications:
                # Keep only primitive witnesses; never retain policy/scan payloads.
                acknowledgement = self._classifications[ticket][1]
                self._classifications[ticket] = ("FAILED", acknowledgement, None, None)

    @_poison_on_failure
    def begin_issuance(self, ticket, acknowledgement, identity):
        from literate_ai.contracts import ContentIdentity

        if self._grant_intent is None and self.handle in _GRANT_OPERATIONS:
            from literate_ai.adapters.node_sdk_verifier_authorization import (
                _publish_initial_grant_intent,
            )

            _publish_initial_grant_intent(self, acknowledgement, identity)
        self.require_ticket(ticket)
        stored = self._tickets[_TICKETS[ticket][1][:2]]
        if (
            stored[2] != "CAPTURING"
            or ticket in self._scans
            or ticket in self._classifications
            or ticket in self._grants
            or any(record[0] == "ISSUING" for record in self._grants.values())
            or type(identity) is not str
            or len(identity) != 71
            or (
                self._grant_intent is not None
                and (
                    self._grant_intent[0] is not acknowledgement
                    or self._grant_intent[1] != identity
                )
            )
        ):
            raise ValueError(
                "verifier issuance requires one original unscanned reservation"
            )
        ContentIdentity.parse_uri(identity)
        self._grant_intent = (acknowledgement, identity)
        self._grants[ticket] = ("ISSUING", identity, None, None)

    @_poison_on_failure
    def finish_issuance(
        self,
        ticket,
        identity,
        request,
        authorization,
        request_identity,
        grant_identity,
        payload,
    ):
        from literate_ai.adapters.node_sdk_verifier_authorization import (
            _commit_issuing_payload,
            _require_issuing_payload,
        )
        from literate_ai.contracts import ContentIdentity
        from literate_ai.security.policy import BuildAuthorization, BuildRequest

        try:
            self.require_ticket(ticket)
            stored = self._tickets[_TICKETS[ticket][1][:2]]
            if (
                stored[2] != "CAPTURING"
                or self._grants.get(ticket) != ("ISSUING", identity, None, None)
                or self._classifications.get(ticket, (None, None))[:2]
                != ("CLASSIFIED", identity)
                or type(request) is not BuildRequest
                or type(authorization) is not BuildAuthorization
            ):
                raise ValueError("verifier issuance lost its original reservation")
            for digest in (request_identity, grant_identity):
                if type(digest) is not str or len(digest) != 71:
                    raise ValueError(
                        "verifier grant requires bounded original identities"
                    )
                ContentIdentity.parse_uri(digest)
            _require_issuing_payload(
                self, ticket, payload, request_identity, grant_identity
            )
            if (
                type(payload) is not tuple
                or payload[0] is not request
                or payload[1] is not authorization
            ):
                raise ValueError(
                    "verifier publication requires its fixed original payload"
                )
            self._grant_payloads[ticket] = payload
            self._grants[ticket] = (
                "ISSUED",
                identity,
                request_identity,
                grant_identity,
            )
            _commit_issuing_payload(
                self, ticket, payload, request_identity, grant_identity
            )
        finally:
            request = authorization = payload = None

    def fail_issuance(self, ticket):
        with self.binding.lock:
            self._poisoned = True
            if type(ticket) is _InspectionTicket and ticket in self._grants:
                self._grants[ticket] = ("FAILED", self._grants[ticket][1], None, None)

    @_poison_on_failure
    def report_capture(self, ticket, *, failed):
        if type(ticket) is not _InspectionTicket:
            raise TypeError("inspection requires an exact original ticket")
        record = _TICKETS.get(ticket)
        stored = None if record is None else self._tickets.get(record[1][:2])
        if (
            stored is None
            or stored[0] is not ticket
            or (not failed and stored[2] != "CAPTURING")
            or (
                not failed
                and ticket in self._handoffs
                and self._handoffs[ticket][3] != "COMMITTED"
            )
        ):
            self._poisoned = True
            raise ValueError("inspection capture lifecycle changed")
        stored[2] = "FAILED" if failed else "CLOSED"
        if failed:
            self._poisoned = True

    def _closing_leases(self):
        """Binding-locked metadata only; no quota calls or retained views."""
        has_grants = self._grant_intent is not None or self.handle in _GRANT_OPERATIONS
        if has_grants:
            from literate_ai.adapters.node_sdk_verifier_authorization import (
                _require_grant_tables,
            )

            _require_grant_tables(self)
        if (
            self._poisoned
            or self.binding.active is not self
            or self._state != "CLOSING"
        ):
            raise ValueError("inspection operation changed during final witnesses")
        if any(record[2] != "CLOSED" for record in self._tickets.values()):
            raise ValueError("inspection operation has unclosed captures")
        if any(record[0] != "SCANNED" for record in self._scans.values()):
            raise ValueError("inspection operation has unfinished scans")
        if any(record[0] != "CLASSIFIED" for record in self._classifications.values()):
            raise ValueError("inspection operation has unfinished classifications")
        ticket_handles = {record[0] for record in self._tickets.values()}
        if has_grants and (
            set(self._grants) != ticket_handles
            or set(self._grant_payloads) != ticket_handles
            or set(self._classifications) != ticket_handles
            or any(record[0] != "ISSUED" for record in self._grants.values())
        ):
            raise ValueError("inspection operation has incomplete original grants")
        if self._capture_leases or self._handoffs or self._resource_pool is not None:
            if len(self._capture_leases) != len(self._tickets) or len(
                self._handoffs
            ) != len(self._tickets):
                raise ValueError(
                    "inspection operation lacks original committed handoffs"
                )
            for ticket, join in self._handoffs.items():
                original = self._capture_leases.get(ticket)
                if (
                    original is None
                    or join[3] != "COMMITTED"
                    or join[0] is not self._resource_pool
                    or join[1] is not self._resource_owner_handle
                    or original[0] is not join[0]
                    or original[1] is not join[2]
                ):
                    raise ValueError("inspection operation closing membership changed")
        return tuple(join[2] for join in self._handoffs.values())

    def close(self):
        """Borrow original closing DATA outside binding; never replay checks."""
        from literate_ai.adapters.node_sdk_verifier_closing_payload import (
            _REQUIRE_CLOSING_PAYLOAD,
            _VerifierClosingPayload,
        )
        from literate_ai.adapters.node_sdk_verifier_resources import (
            _mark_closing_views_dropped,
            _new_closing_publication,
        )

        view = payload = compiler = facts = None
        pool = owner_handle = publication = leases = primary = None
        try:
            with self.binding.lock:
                if self._grant_intent is not None or self.handle in _GRANT_OPERATIONS:
                    from literate_ai.adapters.node_sdk_verifier_authorization import (
                        _require_grant_state_shape,
                    )

                    _require_grant_state_shape(self)
                if self._poisoned or not self._sealed:
                    raise ValueError(
                        "inspection operation failed or lacks actual invocation"
                    )
                if self._state != "LIVE" or self._closing_publication is not None:
                    raise ValueError("inspection operation closing cannot be repeated")
                self._state = "CLOSING"
                self.binding.require_finite()
                self._witness()
                self._invocation_witness()
                self._closing_leases()
                self.binding.require_finite()
                pool, owner_handle = self._resource_pool, self._resource_owner_handle
                leases = self._closing_leases()
            if pool is not None:
                publication = _new_closing_publication(pool, owner_handle)
                with self.binding.lock:
                    self._closing_leases()
                    if self._closing_publication is not None:
                        raise ValueError("closing publication was already reserved")
                    self._closing_publication = publication
                view = pool.prepare_closing(
                    owner_handle, expected_captures=leases, _publication=publication
                )
                with self.binding.lock:
                    self._closing_leases()
                    if self._closing_publication is not publication:
                        raise ValueError("closing publication identity changed")
                for payload, compiler, facts in view:
                    if type(payload) is not _VerifierClosingPayload:
                        raise TypeError("closing requires original typed observations")
                    if compiler is None or type(facts) is not tuple:
                        raise ValueError("closing compiler membership is incomplete")
                    _REQUIRE_CLOSING_PAYLOAD(payload)
            with self.binding.lock:
                self._closing_leases()
                if (
                    publication is not None
                    and self._closing_publication is not publication
                ):
                    raise ValueError("closing publication identity changed")
                self.binding.require_finite()
                self._witness()
                self._invocation_witness()
                current = self._closing_leases()
                if len(current) != len(leases) or any(
                    a is not b for a, b in zip(current, leases, strict=True)
                ):
                    raise ValueError(
                        "closing joined lease set changed during observation"
                    )
        except BaseException as error:
            self._poisoned = True
            primary = error
            raise
        finally:
            # This proof is published only after all source-bearing view locals
            # have dropped. An interrupted drop retains the original borrow.
            view = payload = compiler = facts = None
            try:
                if publication is not None:
                    _mark_closing_views_dropped(publication)

                    def settle():
                        pool.settle_closing_cleanup(owner_handle, publication)
                        with self.binding.lock:
                            if self._closing_publication is not publication:
                                raise ValueError(
                                    "closing publication changed at settlement"
                                )
                            self._closing_publication = None
                            # Settlement may drain other retired DATA outside
                            # locks. Its callbacks cannot publish a stale close.
                            current = self._closing_leases()
                            if len(current) != len(leases) or any(
                                a is not b for a, b in zip(current, leases, strict=True)
                            ):
                                raise ValueError(
                                    "closing membership changed at settlement"
                                )
                            self.binding.require_finite()
                            self._witness()
                            self._invocation_witness()
                            self._closing_leases()

                    _close_preserving_primary_failure(settle, primary)
                if primary is None and (
                    self._grant_intent is not None or self.handle in _GRANT_OPERATIONS
                ):
                    from literate_ai.adapters.node_sdk_verifier_authorization import (
                        _close_operation_grants,
                    )

                    _close_operation_grants(self)
            except BaseException:
                self._poisoned = True
                if primary is None:
                    raise
            finally:
                pool = owner_handle = publication = leases = primary = None

    def retire(self):
        self._retiring = True
        terminal_error = None
        retirement_token = primary = None
        pool = handle = capture_leases = handoffs = closing = None
        try:
            if self._grant_intent is not None or self.handle in _GRANT_OPERATIONS:
                with self.binding.lock:
                    if self._retirement_attempt is not None:
                        self._poisoned = True
                        raise ValueError("verifier resource retirement reentered")
                    retirement_token = object()
                    self._retirement_attempt = retirement_token
            with self.binding.lock:
                self._state = "TERMINAL"
                pool, handle = self._resource_pool, self._resource_owner_handle
                closing = self._closing_publication
                for ticket, _facts, _capture_state in self._tickets.values():
                    _TICKETS.pop(ticket, None)
                _OPERATIONS.pop(self.handle, None)
                self._receipts.clear()
                self._seams.clear()
                self._tickets.clear()
                capture_leases, handoffs = self._capture_leases, self._handoffs
                self._capture_leases, self._handoffs = {}, {}
                self._scans.clear()
                self._classifications.clear()
                self._execution = self._prepared = self._invocation = None
                self._witness = self._invocation_witness = None
                self._original_witness = self._original_invocation_witness = None
                pending = tuple(self._pending_resource_owners.items())
            # Even an enrollment-only pool may lose its last reference here.
            # Detach metadata under binding, then drop it outside the lock.
            capture_leases.clear()
            handoffs.clear()
            for publication, record in pending:
                self._settle_resource_publication(publication, record)
            if closing is not None:
                from literate_ai.adapters.node_sdk_verifier_resources import (
                    _closing_publication_values,
                )

                closing_pool, closing_owner, _token, _claimed, dropped = (
                    _closing_publication_values(closing)
                )
                if closing_pool is not pool or closing_owner is not handle:
                    raise ValueError("closing retirement identity changed")
                if dropped is not True:
                    raise ValueError("closing reader settlement remains pending")
                pool.settle_closing_cleanup(handle, closing)
                with self.binding.lock:
                    if self._closing_publication is closing:
                        self._closing_publication = None
            if handle is not None:
                pool.retire(handle, failed=self._poisoned)
            if self._grant_intent is not None or self.handle in _GRANT_OPERATIONS:
                from literate_ai.adapters.node_sdk_verifier_authorization import (
                    _retire_operation_grants,
                )

                terminal_error = _retire_operation_grants(self)
            with self.binding.lock:
                if (
                    self._resource_pool is pool
                    and self._resource_owner_handle is handle
                ):
                    self._resource_pool = self._resource_owner_handle = None
                self._retirement_complete = (
                    not self._pending_resource_owners
                    and self._closing_publication is None
                    and self._resource_owner_handle is None
                    and self._grant_intent is None
                    and type(self._grant_payloads) is dict
                    and not self._grant_payloads
                    and self.handle not in _GRANT_OPERATIONS
                )
                if not self._retirement_complete:
                    if terminal_error is not None:
                        raise terminal_error
                    raise ValueError("operation resource retirement remains pending")
            if terminal_error is not None:
                raise terminal_error
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                if retirement_token is not None:

                    def end_retirement():
                        try:
                            with self.binding.lock:
                                if self._retirement_attempt is not retirement_token:
                                    raise ValueError(
                                        "verifier retirement attempt changed"
                                    )
                                self._retirement_attempt = None
                        except BaseException:
                            self._poisoned = True
                            self._retirement_complete = False
                            raise

                    _close_preserving_primary_failure(end_retirement, primary)
            finally:
                pool = handle = pending = publication = record = None
                capture_leases = handoffs = None
                closing = closing_pool = closing_owner = None
                terminal_error = retirement_token = primary = None


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


def require_node_verifier_grant_use(ports, operation, authorization, request):
    """Preserve manual execution; a typed operation requires explicit ownership.

    The independently retained marker prevents clearing the runtime's intent
    field, or omitting the operation argument, from selecting the manual path.
    This mode check does not supply an operation to the caller.
    """
    state = None
    try:
        if operation is None:
            # Inspect independently registered originals before consulting any
            # writable host pointer. A cleared/replaced pointer is not absence.
            with _GRANT_MEMBERSHIP_LOCK:
                markers = tuple(_GRANT_OPERATIONS.values())
            for marker in markers:
                if (
                    type(marker) is not tuple
                    or len(marker) != 2
                    or any(type(ref) is not weakref.ReferenceType for ref in marker)
                ):
                    raise ValueError("verifier grant mode membership changed")
                original_ports, original_state = marker
                if original_ports() is ports:
                    state = original_state()
                    if state is not None and type(state) is not _OperationState:
                        state = None
                        raise ValueError("verifier grant original operation changed")
                    raise ValueError(
                        "verifier execution requires explicitly threaded operation"
                    )
            bound = ports._node_sdk_host_binding
            if bound is None:
                return
            handle = bound._inspection_binding
            reference = (
                _BINDINGS.get(handle)
                if type(handle) is _RuntimeInspectionBinding
                else None
            )
            binding = None if reference is None else reference()
            if binding is None or binding.originals[0] is not bound:
                raise ValueError("verifier execution lost original host binding")
            binding.require_finite()
            state = binding.active
            if state is None:
                return
            if state.handle not in _GRANT_OPERATIONS and state._grant_intent is None:
                return
            raise ValueError(
                "verifier execution requires explicitly threaded operation"
            )
        state = _operation_state(operation)
        if operation not in _GRANT_OPERATIONS:
            raise ValueError(
                "verifier execution requires original typed grant membership"
            )
        # Fixed operation validation pins the authorization dependency before
        # loading its current module binding, so a replacement is never invoked.
        state.require_live()
        from literate_ai.adapters.node_sdk_verifier_authorization import (
            _ORIGINAL_NODE_VERIFIER_AUTHORIZATION,
        )

        _ORIGINAL_NODE_VERIFIER_AUTHORIZATION(ports, operation, authorization, request)
    except BaseException:
        if state is not None:
            state._poisoned = True
        raise
    finally:
        ports = operation = authorization = request = state = bound = None
        handle = reference = binding = marker = original_ports = original_state = None
        markers = None


def enroll_node_verifier_capture(
    operation, owner, description, *, resource_pool, resource_lease
):
    return _operation_state(operation).enroll(
        owner, description, resource_pool=resource_pool, resource_lease=resource_lease
    )


def report_node_verifier_capture(operation, ticket, *, failed):
    _operation_state(operation).report_capture(ticket, failed=failed)


# Trusted module initialization captures the execution seam without importing
# this heavy runtime from the lifecycle module during its initialization.
_ORIGINAL_NODE_VERIFIER_GRANT_USE = require_node_verifier_grant_use
