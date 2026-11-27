"""Fixed verifier intent, original-capture issuance and operation grant custody.

The public factory acknowledges a narrow workflow. Only the private issuer may
classify and authorize a bound, enrolled capture; neither a digest nor supplied
scan DATA can stand in for those original owners. Host selection remains manual
until this producer and its lifecycle enforcement are qualified together.
"""

import dataclasses
import hashlib
import json
import threading
import types
import weakref
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_library_verifier_request as requests
from literate_ai.adapters import node_sdk_verifier_authority as membership
from literate_ai.adapters import node_sdk_verifier_runtime as runtime
from literate_ai.adapters import node_sdk_verifier_scan as scans
from literate_ai.adapters.lifecycle import local as local_policy
from literate_ai.adapters.lifecycle.local import PolicyBuildAuthorizer
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthoritySnapshot,
)
from literate_ai.adapters.node_library_verifier_request import (
    NodeLibraryVerifierRequestDescription,
)
from literate_ai.adapters.process_liveness import _close_preserving_primary_failure
from literate_ai.application.locked_generation_authority import (
    LockedGenerationAuthority,
)
from literate_ai.contracts import ComponentExecutionPlan, canonical_identity
from literate_ai.contracts import identity as identities
from literate_ai.security import policy as security
from literate_ai.security import scanning as scanning
from literate_ai.security.policy import (
    BuildAuthorization,
    BuildRequest,
    FindingSeverity,
    LiveBuildAuthorizationVerifier,
    OriginAttestation,
    SecurityClassification,
    SecurityPolicy,
    SecurityProfile,
)
from literate_ai.security.scanning import AuthorizationRevocationSet, SecurityScanReport

_ISSUER_TOKEN = object()
_DATA_SUFFIXES = (".json", ".map", ".txt", ".text", ".md", ".markdown")
_LICENSE_NAMES = ("LICENSE", "NOTICE")
_MAX_LIFETIME = timedelta(hours=1)
_PRIVILEGES = frozenset({"execute-library-verifier"})
_EMPTY_REVOCATIONS = ()
_GRANT_LOCK = threading.RLock()
_OPERATION_GRANTS = {}
_MAX_GRANT_OPERATIONS = 64
_GRANT_DENIED = False
_POLICY_ID = canonical_identity(
    {
        "schema": "literate-ai/node-sdk-verifier-security-policy@1",
        "privileges": sorted(_PRIVILEGES),
        "blocked_at_or_above": int(FindingSeverity.CRITICAL),
        "maximum_lifetime_seconds": 3600,
        "scanner": scans._SCANNER_ID,
        "rules": scans._SCANNER.rule_set_digest,
        "source_suffixes": list(scans._SUFFIXES),
        "extensionless_compiler_sources": scans._compiler_launcher_policy(),
        "data_suffixes": list(_DATA_SUFFIXES),
        "license_names": list(_LICENSE_NAMES),
        "non_source_executable_modes": "refuse",
        "native_node_binary": "explicit-identity-only-acknowledgement",
        "revocations": "constructor-owned-immutable-empty@1",
    }
).uri
_POLICY = SecurityPolicy(
    policy_digest=_POLICY_ID,
    maximum_authorization_lifetime=_MAX_LIFETIME,
    _known_privileges=_PRIVILEGES,
    _constrained_privileges=_PRIVILEGES,
    _reviewed_privileges=_PRIVILEGES,
    _privileged_review_privileges=_PRIVILEGES,
)
_SNAPSHOT_REQUIRE = LockedGenerationAuthoritySnapshot.require_unchanged
_SNAPSHOT_SLOTS = tuple(
    vars(LockedGenerationAuthoritySnapshot)[name]
    for name in LockedGenerationAuthoritySnapshot.__slots__
)
_AUTHORITY_SLOTS = tuple(
    vars(LockedGenerationAuthority)[name]
    for name in LockedGenerationAuthority.__slots__
)
_POLICY_SLOTS = tuple(vars(SecurityPolicy)[name] for name in SecurityPolicy.__slots__)
_POLICY_VALUES = tuple(
    types.MemberDescriptorType.__get__(slot, _POLICY, SecurityPolicy)
    for slot in _POLICY_SLOTS
)
_AUTHORIZE = PolicyBuildAuthorizer.authorize
_REQUIRE_BUILD = BuildAuthorization.require_valid
_REVOCATIONS_ENTRIES = vars(AuthorizationRevocationSet)["entries"]
_VERIFIER_PROVIDER = vars(LiveBuildAuthorizationVerifier)["provider"]
_AUTHORIZER_SLOTS = tuple(
    vars(PolicyBuildAuthorizer)[name] for name in PolicyBuildAuthorizer.__slots__
)


def _class_baseline(cls):
    namespace = tuple(type.__getattribute__(cls, "__dict__").items())
    fields = dict(namespace).get("__dataclass_fields__")
    # asdict traverses Field.name and Field._field_type. A class-dict identity
    # fence alone would miss mutation of these original metadata objects.
    metadata = (
        ()
        if fields is None
        else tuple(
            (key, value, value.name, value._field_type) for key, value in fields.items()
        )
    )
    return cls, type.__getattribute__(cls, "__mro__"), namespace, fields, metadata


_CLASSES = tuple(
    _class_baseline(cls)
    for cls in (
        LockedGenerationAuthoritySnapshot,
        LockedGenerationAuthority,
        ComponentExecutionPlan,
        NodeLibraryVerifierRequestDescription,
        SecurityPolicy,
        OriginAttestation,
        SecurityClassification,
        SecurityScanReport,
        security.SecurityFinding,
        BuildAuthorization,
        BuildRequest,
        PolicyBuildAuthorizer,
        AuthorizationRevocationSet,
        LiveBuildAuthorizationVerifier,
    )
)
_FIELD_NAME = vars(dataclasses.Field)["name"]
_FIELD_TYPE = vars(dataclasses.Field)["_field_type"]
_DEPENDENCIES = (
    (
        (membership, "_new_acknowledgement", membership._new_acknowledgement),
        (membership, "_attach_policy_owner", membership._attach_policy_owner),
        (membership, "_registered_policy_owner", membership._registered_policy_owner),
        (membership, "_require_acknowledgement", membership._require_acknowledgement),
        (membership, "_state", membership._state),
        (membership, "_values", membership._values),
        (membership, "_require_originals", membership._require_originals),
        (runtime, "_finite_metadata", runtime._finite_metadata),
        (runtime, "_operation_state", runtime._operation_state),
        (runtime, "_BINDINGS", runtime._BINDINGS),
        (runtime, "_BindingState", runtime._BindingState),
        (runtime._BindingState, "require_finite", runtime._BindingState.require_finite),
        (runtime, "_GRANT_OPERATIONS", runtime._GRANT_OPERATIONS),
        (runtime, "_GRANT_MEMBERSHIP_LOCK", runtime._GRANT_MEMBERSHIP_LOCK),
        (
            runtime,
            "_ORIGINAL_NODE_VERIFIER_GRANT_USE",
            runtime._ORIGINAL_NODE_VERIFIER_GRANT_USE,
        ),
        (
            runtime,
            "require_node_verifier_grant_use",
            runtime.require_node_verifier_grant_use,
        ),
        (
            runtime._InspectionTicket,
            "__hash__",
            vars(runtime._InspectionTicket).get("__hash__"),
        ),
        (
            runtime._InspectionTicket,
            "__eq__",
            vars(runtime._InspectionTicket).get("__eq__"),
        ),
        (captures, "_read_runtime_scan_inputs", captures._read_runtime_scan_inputs),
        (
            captures,
            "enroll_runtime_verifier_inspection",
            captures.enroll_runtime_verifier_inspection,
        ),
        (
            captures,
            "capture_node_provider_verifier_inspection",
            captures.capture_node_provider_verifier_inspection,
        ),
        (
            captures,
            "capture_node_sdk_project_verifier_inspection",
            captures.capture_node_sdk_project_verifier_inspection,
        ),
        (
            captures,
            "_require_runtime_scan_enrollment",
            captures._require_runtime_scan_enrollment,
        ),
        (
            scans,
            "scan_enrolled_node_verifier_inputs",
            scans.scan_enrolled_node_verifier_inputs,
        ),
        (scans, "_fixed_scanner", scans._fixed_scanner),
        (scans, "_compiler_launcher_policy", scans._compiler_launcher_policy),
        (security, "OriginAttestation", OriginAttestation),
        (security, "SecurityClassification", SecurityClassification),
        (security, "SecurityPolicy", SecurityPolicy),
        (security, "asdict", dataclasses.asdict),
        (json, "loads", json.loads),
        (hashlib, "sha256", hashlib.sha256),
        (dataclasses.Field, "name", _FIELD_NAME),
        (dataclasses.Field, "_field_type", _FIELD_TYPE),
        (local_policy, "_classification", local_policy._classification),
        (local_policy, "_build_request", local_policy._build_request),
        (local_policy, "SecurityClassification", SecurityClassification),
        (local_policy, "BuildRequest", BuildRequest),
    )
    + tuple(
        (module, name, value)
        for module in (security, requests, scanning, identities)
        for name, value in vars(module).items()
        if not name.startswith("__")
    )
    + tuple(
        (dataclasses, name, vars(dataclasses)[name])
        for name in (
            "asdict",
            "_asdict_inner",
            "fields",
            "_is_dataclass_instance",
            "Field",
        )
    )
)


def _require_fixed():
    for module, name, original in _DEPENDENCIES:
        if vars(module).get(name) is not original:
            raise ValueError("fixed SDK verifier dependency changed")
    for name, value in _CONSTANTS:
        if globals().get(name) is not value:
            raise ValueError("fixed SDK verifier policy implementation changed")
    for cls, mro, namespace, fields, metadata in _CLASSES:
        current = type.__getattribute__(cls, "__dict__")
        if (
            type.__getattribute__(cls, "__mro__") is not mro
            or any(type(key) is not str for key in current)
            or len(current) != len(namespace)
            or any(current.get(name) is not value for name, value in namespace)
        ):
            raise ValueError("fixed SDK verifier DATA class changed")
        if fields is not None:
            if (
                any(type(key) is not str for key in fields)
                or len(fields) != len(metadata)
                or any(
                    dict.get(fields, key) is not value
                    or types.MemberDescriptorType.__get__(
                        _FIELD_NAME, value, dataclasses.Field
                    )
                    is not name
                    or types.MemberDescriptorType.__get__(
                        _FIELD_TYPE, value, dataclasses.Field
                    )
                    is not field_type
                    for key, value, name, field_type in metadata
                )
            ):
                raise ValueError("fixed SDK verifier DATA field metadata changed")
    if any(
        types.MemberDescriptorType.__get__(slot, _POLICY, SecurityPolicy) is not value
        for slot, value in zip(_POLICY_SLOTS, _POLICY_VALUES, strict=True)
    ):
        raise ValueError("fixed SDK verifier security policy changed")
    _, require_scanner = scans._fixed_scanner()
    require_scanner()


def _source_guard(snapshot, execution):
    values = authority = authority_witness = execution_witness = None
    release_authority = release_execution = None
    released = False

    def release():
        nonlocal snapshot, execution, values, authority, released
        nonlocal \
            authority_witness, \
            execution_witness, \
            release_authority, \
            release_execution
        released = True
        try:
            if release_authority is not None:
                release_authority()
        finally:
            try:
                if release_execution is not None:
                    release_execution()
            finally:
                snapshot = execution = values = authority = None
                authority_witness = execution_witness = None
                release_authority = release_execution = None

    def finite():
        if released:
            raise ValueError("verifier original source witness was released")
        _require_fixed()
        if any(
            types.MemberDescriptorType.__get__(
                slot, snapshot, LockedGenerationAuthoritySnapshot
            )
            is not value
            for slot, value in zip(_SNAPSHOT_SLOTS, values, strict=True)
        ):
            raise ValueError("original verifier authority snapshot changed")
        authority_witness()
        execution_witness()
        if (
            execution.component_lock_identity != authority.lock.identity
            or execution.root_revision != authority.lock.root_revision
        ):
            raise ValueError("verifier intent execution differs from locked authority")

    def require_current():
        finite()
        _SNAPSHOT_REQUIRE(snapshot)
        finite()

    try:
        values = tuple(
            types.MemberDescriptorType.__get__(
                slot, snapshot, LockedGenerationAuthoritySnapshot
            )
            for slot in _SNAPSHOT_SLOTS
        )
        authority = snapshot.authority
        if type(authority) is not LockedGenerationAuthority:
            raise TypeError("verifier intent requires original locked authority")
        authority_witness, release_authority, _ = runtime._finite_metadata(
            tuple(
                types.MemberDescriptorType.__get__(
                    slot, authority, LockedGenerationAuthority
                )
                for slot in _AUTHORITY_SLOTS
            ),
            _with_release=True,
        )
        execution_witness, release_execution, _ = runtime._finite_metadata(
            execution, _with_release=True
        )
        require_current()
        return require_current, finite, release
    except BaseException as error:
        _close_preserving_primary_failure(release, error)
        raise


def _clock():
    return datetime.now(UTC)


def _make_issuance_owner(actor, reason, lifetime, deadline):
    revocations = AuthorizationRevocationSet()

    def provider():
        _require_fixed()
        if (
            types.MemberDescriptorType.__get__(
                _REVOCATIONS_ENTRIES, revocations, AuthorizationRevocationSet
            )
            is not _EMPTY_REVOCATIONS
        ):
            raise ValueError("fixed verifier revocation state changed")
        return revocations

    verifier = LiveBuildAuthorizationVerifier(provider)
    authorizer = PolicyBuildAuthorizer(
        policy=_POLICY,
        actor=actor,
        reason=reason,
        authorization_lifetime=lifetime,
        yolo_acknowledged=False,
        clock=_clock,
        authorization_deadline=deadline,
    )
    values = tuple(
        types.MemberDescriptorType.__get__(slot, authorizer, PolicyBuildAuthorizer)
        for slot in _AUTHORIZER_SLOTS
    )
    return revocations, provider, verifier, authorizer, values


def _require_issuance_owner(owner):
    revocations, provider, verifier, authorizer, values = owner[9:]
    if (
        type(revocations) is not AuthorizationRevocationSet
        or types.MemberDescriptorType.__get__(
            _REVOCATIONS_ENTRIES, revocations, AuthorizationRevocationSet
        )
        is not _EMPTY_REVOCATIONS
        or type(verifier) is not LiveBuildAuthorizationVerifier
        or types.MemberDescriptorType.__get__(
            _VERIFIER_PROVIDER, verifier, LiveBuildAuthorizationVerifier
        )
        is not provider
        or type(authorizer) is not PolicyBuildAuthorizer
        or any(
            types.MemberDescriptorType.__get__(slot, authorizer, PolicyBuildAuthorizer)
            is not original
            for slot, original in zip(_AUTHORIZER_SLOTS, values, strict=True)
        )
    ):
        raise ValueError("fixed verifier issuance or revocation owner changed")


def acknowledge_node_sdk_verifier_execution(
    *,
    snapshot,
    execution,
    actor,
    reason,
    authorization_lifetime,
    authorization_deadline,
    acknowledge_identity_only_inputs,
):
    """Record explicit verifier intent; this returns no execution permission.

    Node and closed non-source DATA are checked by identity, not text rules.
    The caller supplies the original finite overall deadline; it is never rebased.
    """
    guard = facts = handle = owner = None
    try:
        _require_fixed()
        if (
            type(snapshot) is not LockedGenerationAuthoritySnapshot
            or type(execution) is not ComponentExecutionPlan
            or type(authorization_lifetime) is not timedelta
            or not timedelta(0) < authorization_lifetime <= _MAX_LIFETIME
            or type(authorization_deadline) is not datetime
            or authorization_deadline.tzinfo is not UTC
            or acknowledge_identity_only_inputs is not True
            or any(
                type(value) is not str
                or not value.strip()
                or len(value.encode("utf-8")) > 4096
                for value in (actor, reason)
            )
        ):
            raise ValueError(
                "verifier intent requires exact finite explicit acknowledgement"
            )
        if authorization_deadline <= datetime.now(UTC):
            raise ValueError("verifier intent original deadline has expired")
        guard = _source_guard(snapshot, execution)
        facts = (
            "literate-ai/fixed-node-sdk-verifier-intent@1",
            snapshot.authority.identity.uri,
            snapshot.catalog_audit_identity.uri,
            snapshot.input_closure_identity,
            execution.identity.uri,
            _POLICY_ID,
            scans._SCANNER_ID,
            scans._SCANNER.rule_set_digest,
            actor,
            reason,
            authorization_lifetime // timedelta(microseconds=1),
            authorization_deadline.isoformat(),
            True,
        )
        handle = membership._new_acknowledgement(facts, (snapshot, execution))
        owner = (
            _ISSUER_TOKEN,
            weakref.ref(handle),
            snapshot,
            execution,
            facts,
            guard,
            authorization_lifetime,
            authorization_deadline,
            _POLICY,
        ) + _make_issuance_owner(
            actor, reason, authorization_lifetime, authorization_deadline
        )
        membership._attach_policy_owner(handle, owner, retire=guard[2])
        guard[0]()
        if authorization_deadline <= datetime.now(UTC):
            raise ValueError("verifier intent original deadline has expired")
        return handle
    except BaseException as error:
        if handle is not None:
            _close_preserving_primary_failure(
                lambda: membership._retire_acknowledgement(handle), error
            )
        if guard is not None:
            _close_preserving_primary_failure(guard[2], error)
        raise
    finally:
        snapshot = execution = guard = facts = owner = handle = None


def _original_owner(acknowledgement):
    owner = None
    try:
        _require_fixed()
        owner = membership._registered_policy_owner(acknowledgement)
        if (
            type(owner) is not tuple
            or len(owner) != 14
            or owner[0] is not _ISSUER_TOKEN
            or type(owner[1]) is not weakref.ReferenceType
            or owner[1]() is not acknowledgement
            or owner[8] is not _POLICY
        ):
            raise ValueError("verifier acknowledgement lacks its original fixed issuer")
        membership._require_originals(
            membership._state(acknowledgement), owner[4], (owner[2], owner[3])
        )
        _require_issuance_owner(owner)
        return owner
    finally:
        acknowledgement = owner = None


def _verifier_intent_identity(acknowledgement):
    """Original finite intent metadata only; no permission or issuer callback."""
    _require_fixed()
    owner = None
    try:
        owner = _original_owner(acknowledgement)
        owner[5][1]()
        if _clock() >= owner[7]:
            raise ValueError("verifier intent original deadline has expired")
        return membership._values(membership._state(acknowledgement))[1]
    finally:
        acknowledgement = owner = None


def _require_host_verifier_intent(acknowledgement, configuration, bound):
    _require_fixed()
    owner = state = None
    try:
        identity = _verifier_intent_identity(acknowledgement)
        owner = _original_owner(acknowledgement)
        state = membership._state(acknowledgement)
        if (
            configuration.snapshot is not owner[2]
            or configuration.expected_execution is not owner[3]
        ):
            raise ValueError("verifier host intent lost original authority")
        if bound is None:
            if membership._values(state)[3] is not None:
                raise ValueError("verifier host intent was already consumed")
        else:
            membership._require_acknowledgement(
                acknowledgement,
                configuration,
                bound,
                facts=owner[4],
                originals=(owner[2], owner[3]),
            )
        return identity
    except BaseException:
        if state is not None:
            membership._poison_preserving_failure(state)
        raise
    finally:
        acknowledgement = configuration = bound = owner = state = None


def _bind_host_verifier_intent(acknowledgement, configuration, bound):
    _require_fixed()
    from literate_ai.adapters.node_sdk_host import (
        LocalNodeSDKHostConfiguration,
        _BoundAdmission,
    )

    state = owner = None
    try:
        state = membership._state(acknowledgement)
        owner = _original_owner(acknowledgement)
        if (
            type(configuration) is not LocalNodeSDKHostConfiguration
            or type(bound) is not _BoundAdmission
            or configuration.verifier_acknowledgement is not acknowledgement
            or bound.configuration is not configuration
            or configuration._binding is not bound
            or configuration._original_binding is not bound
            or configuration.snapshot is not owner[2]
            or configuration.expected_execution is not owner[3]
        ):
            raise ValueError("verifier intent requires original host composition")
        registration = bound._inspection_registration
        reference = runtime._BINDINGS.get(bound._inspection_binding)
        if (
            type(registration) is not runtime._BindingState
            or reference is None
            or reference() is not registration
            or registration.originals[0] is not bound
        ):
            raise ValueError("verifier intent lost original inspection binding")
        registration.require_finite()
        _verifier_intent_identity(acknowledgement)
        membership._bind_acknowledgement(
            acknowledgement,
            configuration,
            bound,
            facts=owner[4],
            originals=(owner[2], owner[3]),
        )
    except BaseException:
        if state is not None:
            membership._poison_preserving_failure(state)
        raise
    finally:
        acknowledgement = configuration = bound = state = owner = registration = (
            reference
        ) = None


def _require_host_verifier_operation(acknowledgement, operation, ports):
    _require_fixed()
    from literate_ai.adapters.node_sdk_host import (
        LocalNodeSDKHostConfiguration,
        _BoundAdmission,
    )

    state = bound = configuration = None
    try:
        state = runtime._operation_state(operation)
        bound, configuration, original_ports = state.binding.originals[:3]
        if (
            type(configuration) is not LocalNodeSDKHostConfiguration
            or type(bound) is not _BoundAdmission
            or ports is not original_ports
            or configuration.verifier_acknowledgement is not acknowledgement
            or configuration.authorize_verifier is not None
            or state._execution is not configuration.expected_execution
        ):
            raise ValueError("verifier issuance lost original host selection")
        _require_host_verifier_intent(acknowledgement, configuration, bound)
        state.binding.require_finite()
        state.require_live()
    except BaseException:
        if state is not None:
            state._poisoned = True
        raise
    finally:
        acknowledgement = operation = ports = state = bound = configuration = (
            original_ports
        ) = None


def _issue_host_verifier_capture(acknowledgement, operation, ports, handle):
    _require_fixed()
    try:
        _require_host_verifier_operation(acknowledgement, operation, ports)
        ticket = captures.enroll_runtime_verifier_inspection(operation, handle)
        return _issue_enrolled_node_verifier_authorization(
            acknowledgement, operation, handle, ticket
        )
    finally:
        acknowledgement = operation = ports = handle = ticket = None


def _require_supported_coverage(inventory):
    for row in inventory:
        path = PurePosixPath(row["path"])
        if path.suffix.lower() in scans._SUFFIXES:
            continue
        if row.get("coverage") == "rule-covered-compiler-launcher" and any(
            row.get("role") == source["role"]
            and row["path"] == source["path"]
            and row.get("digest") == source["content_digest"]
            and row.get("scan_path") == source["scan_path"]
            for source in scans._compiler_launcher_policy()
        ):
            continue
        # The native Node binary has a separate original tool binding, not an
        # inventory-row exception. Refuse executable DATA before license names.
        if row["mode"] & 0o111:
            raise ValueError("verifier policy refuses executable non-source DATA")
        if (
            path.suffix.lower() not in _DATA_SUFFIXES
            and path.name not in _LICENSE_NAMES
        ):
            raise ValueError("verifier policy does not support this DATA coverage")


def _classify_enrolled_node_verifier_inputs(acknowledgement, operation, handle, ticket):
    """Private fixed issuer entry; no caller-supplied scan or classification."""
    state = None
    owner = rows = description = encoded = document = report = result = None
    snapshot = execution = facts = guard = bound = configuration = None
    try:
        state = runtime._operation_state(operation)
        owner = _original_owner(acknowledgement)
        _, _weak_ack, snapshot, execution, facts, guard, _lifetime, deadline, policy = (
            owner[:9]
        )
        bound, configuration = state.binding.originals[:2]
        identity = membership._require_acknowledgement(
            acknowledgement,
            configuration,
            bound,
            facts=facts,
            originals=(snapshot, execution),
        )
        if (
            configuration.snapshot is not snapshot
            or configuration.expected_execution is not execution
            or state._execution is not execution
        ):
            raise ValueError("verifier classification lost original runtime authority")
        captures._require_runtime_scan_enrollment(operation, handle, ticket)
        state.begin_classification(ticket, identity)
        guard[0]()
        rows, description = captures._read_runtime_scan_inputs(
            operation, handle, ticket
        )
        encoded = scans.scan_enrolled_node_verifier_inputs(operation, handle, ticket)
        guard[0]()
        _require_fixed()
        document = json.loads(encoded)
        _require_supported_coverage(document["inventory"])
        # Read the exact original preimages again instead of accepting detached
        # scan/request DATA from a caller. The closed description checks builders,
        # outputs, compiler, privilege, sandbox and source digest together.
        current_rows, current_description = captures._read_runtime_scan_inputs(
            operation, handle, ticket
        )
        _require_fixed()
        if current_description is not description or current_rows is not rows:
            raise ValueError("verifier classification original capture changed")
        request = NodeLibraryVerifierRequestDescription(*description).request
        report = SecurityScanReport.from_dict(document["report"])
        observation = {
            "schema": "literate-ai/local-node-sdk-verifier-origin@1",
            "scope": "original-enrolled-capture-local-custody",
            "vendor_signature_verified": False,
            "acknowledgement": identity,
            "authority": facts[1],
            "execution": facts[4],
            "scan": "sha256:" + hashlib.sha256(encoded).hexdigest(),
            "native_node_binary": document["inputs_preimage"]["node"],
        }
        observation_identity = canonical_identity(observation).uri
        attestation = OriginAttestation(
            source_digest=request.source_bundle_digest,
            signer="local-node-sdk-verifier-custody",
            trust_root=identity,
            signature_identity=observation_identity,
            verified=True,
        )
        result = policy.classify(
            effective_revision_digest=request.effective_revision_digest,
            attestations=(attestation,),
            findings=report.findings,
        )
        guard[0]()
        captures._read_runtime_scan_inputs(operation, handle, ticket)
        guard[1]()
        _require_fixed()
        membership._require_acknowledgement(
            acknowledgement,
            configuration,
            bound,
            facts=facts,
            originals=(snapshot, execution),
        )
        if (
            configuration.snapshot is not snapshot
            or configuration.expected_execution is not execution
            or state._execution is not execution
        ):
            raise ValueError("verifier classification lost original runtime authority")
        if deadline <= datetime.now(UTC):
            raise ValueError("verifier classification original deadline has expired")
        state.finish_classification(
            ticket, identity, observation_identity, result.digest
        )
        return result, observation, attestation
    except BaseException as error:
        if state is not None:
            _close_preserving_primary_failure(
                lambda: state.fail_classification(ticket), error
            )
        try:
            membership._poison_preserving_failure(membership._state(acknowledgement))
        except BaseException:
            pass
        if guard is not None:
            _close_preserving_primary_failure(guard[2], error)
        raise
    finally:
        owner = rows = current_rows = description = current_description = None
        encoded = document = report = result = request = attestation = None
        acknowledgement = operation = handle = ticket = state = None
        snapshot = execution = facts = guard = bound = configuration = None
        _weak_ack = _lifetime = deadline = policy = observation = None


def _release_original_grants(registration):
    global _GRANT_DENIED
    record = primary = None
    try:
        for record in registration[3].values():
            if record[1] is not None:
                try:
                    record[1][3]()
                except BaseException as error:
                    _GRANT_DENIED = True
                    if primary is None:
                        primary = error
        if primary is not None:
            raise primary
    except BaseException:
        _GRANT_DENIED = True
        raise
    finally:
        registration = record = primary = None


def _drop_operation_grants(key, reference):
    retained = current = None
    try:
        with _GRANT_LOCK:
            current = _OPERATION_GRANTS.get(key)
            if current is not None and current[0] is reference:
                retained = _OPERATION_GRANTS.pop(key)
        if retained is not None:
            _release_original_grants(retained)
    finally:
        retained = current = None


def _grant_registration(state, acknowledgement=None, identity=None, *, create=False):
    original = None
    try:
        if _GRANT_DENIED and create:
            raise ValueError("verifier grant registry is unavailable")
        with _GRANT_LOCK:
            key = id(state.handle)
            original = _OPERATION_GRANTS.get(key)
            if original is None and create:
                if len(_OPERATION_GRANTS) >= _MAX_GRANT_OPERATIONS:
                    raise ValueError("verifier grant operation capacity exhausted")
                reference = weakref.ref(
                    state.handle,
                    lambda ref, drop=_drop_operation_grants: drop(key, ref),
                )
                original = (
                    reference,
                    weakref.ref(acknowledgement),
                    identity,
                    {},
                    [state._original_witness, state._original_invocation_witness],
                    weakref.ref(state.binding),
                    [None],
                )
                with runtime._GRANT_MEMBERSHIP_LOCK:
                    runtime._GRANT_OPERATIONS[state.handle] = (
                        weakref.ref(state.binding.originals[2]),
                        weakref.ref(state),
                    )
                _OPERATION_GRANTS[key] = original
            if original is None or original[0]() is not state.handle:
                raise ValueError("verifier grant operation has no original registry")
            return original
    finally:
        state = acknowledgement = original = None


def _publish_initial_grant_intent(state, acknowledgement, identity):
    _require_fixed()
    registration = _grant_registration(state)
    if (
        state._grant_intent is not None
        or state._poisoned
        or type(acknowledgement)
        is not membership.NodeSDKVerifierExecutionAcknowledgement
        or type(identity) is not str
        or len(identity) != 71
        or registration[1]() is not acknowledgement
        or registration[2] != identity
        or registration[3]
        or state._grants
        or state._grant_payloads
    ):
        raise ValueError("original grant intent cannot be adopted or republished")
    state._grant_intent = (acknowledgement, identity)


def _require_issuing_payload(state, ticket, payload, request_identity, grant_identity):
    original = _grant_registration(state)[3].get(ticket)
    if (
        original is None
        or original[0] != "PREPARED"
        or original[1] is not payload
        or original[2:] != (request_identity, grant_identity)
    ):
        raise ValueError("verifier grant payload differs from fixed issuer ownership")


def _commit_issuing_payload(state, ticket, payload, request_identity, grant_identity):
    _require_issuing_payload(state, ticket, payload, request_identity, grant_identity)
    _grant_registration(state)[3][ticket] = (
        "ISSUED",
        payload,
        request_identity,
        grant_identity,
    )


def _register_grant_invocation_witness(state):
    metadata = _grant_registration(state)[4]
    if (
        metadata[1] is not None
        or state._invocation_witness is not state._original_invocation_witness
    ):
        raise ValueError("verifier invocation witness cannot be replaced")
    metadata[1] = state._invocation_witness


def _operation_grant_owner(state, *, closing=False):
    owner = intent = bound = configuration = None
    try:
        _require_fixed()
        _require_grant_state_shape(state)
        if runtime._operation_state(state.handle) is not state:
            raise ValueError("verifier grant operation is foreign")
        intent = state._grant_intent
        if (
            type(intent) is not tuple
            or len(intent) != 2
            or type(intent[0]) is not membership.NodeSDKVerifierExecutionAcknowledgement
            or type(intent[1]) is not str
            or len(intent[1]) != 71
        ):
            raise ValueError("verifier grant operation lost its intent")
        owner = _original_owner(intent[0])
        registration = _grant_registration(state)
        if (
            _GRANT_DENIED
            or registration[1]() is not intent[0]
            or registration[2] != intent[1]
        ):
            raise ValueError("verifier grant fixed issuer membership changed")
        bound, configuration = state.binding.originals[:2]
        marker = runtime._GRANT_OPERATIONS.get(state.handle)
        if (
            type(marker) is not tuple
            or len(marker) != 2
            or any(type(ref) is not weakref.ReferenceType for ref in marker)
            or marker[0]() is not state.binding.originals[2]
            or marker[1]() is not state
        ):
            raise ValueError("verifier grant lost original ports membership")
        identity = membership._require_acknowledgement(
            intent[0],
            configuration,
            bound,
            facts=owner[4],
            originals=(owner[2], owner[3]),
        )
        if (
            identity != intent[1]
            or state._execution is not owner[3]
            or configuration.snapshot is not owner[2]
            or configuration.expected_execution is not owner[3]
            or state.binding.active is not state
            or state._poisoned
            or state._state != ("CLOSING" if closing else "LIVE")
            or state._witness is None
            or state._witness is not state._original_witness
            or state._witness is not registration[4][0]
            or (
                state._sealed
                and (
                    state._invocation_witness is None
                    or state._invocation_witness
                    is not state._original_invocation_witness
                    or state._invocation_witness is not registration[4][1]
                )
            )
        ):
            raise ValueError("verifier grant original operation metadata changed")
        state.binding.require_finite()
        state._original_witness()
        if state._sealed:
            state._original_invocation_witness()
        owner[5][1]()
        return owner
    finally:
        owner = intent = bound = configuration = state = registration = marker = None


def _require_grant_state_shape(state):
    if (
        type(state._poisoned) is not bool
        or type(state._sealed) is not bool
        or type(state._state) is not str
        or type(state._retiring) is not bool
    ):
        raise ValueError(
            "verifier operation phase or flags are not closed primitive metadata"
        )


def _require_grant_tables(state):
    _require_fixed()
    _require_grant_state_shape(state)
    intent = state._grant_intent
    if (
        type(intent) is not tuple
        or len(intent) != 2
        or type(intent[0]) is not membership.NodeSDKVerifierExecutionAcknowledgement
        or type(intent[1]) is not str
        or len(intent[1]) != 71
    ):
        raise ValueError("verifier grant operation lost its closed intent")
    tables = (
        (state._grants, 4, tuple),
        (state._grant_payloads, 4, tuple),
        (state._classifications, 4, tuple),
        (state._scans, 2, tuple),
        (state._capture_leases, 2, tuple),
        (state._handoffs, 4, list),
    )
    for table, width, storage in tables:
        if type(table) is not dict or any(
            type(key) is not runtime._InspectionTicket for key in dict.keys(table)
        ):
            raise ValueError("verifier grant table keys are not original tickets")
        if any(
            type(record) is not storage or len(record) != width
            for record in dict.values(table)
        ):
            raise ValueError("verifier grant table contains foreign record storage")
    for table in (state._grants, state._classifications, state._scans):
        if any(
            type(item) is not str and item is not None
            for record in dict.values(table)
            for item in record
        ):
            raise ValueError("verifier grant table contains foreign primitive metadata")
    if any(type(record[3]) is not str for record in dict.values(state._handoffs)):
        raise ValueError("verifier handoff phase is not primitive metadata")
    if type(state._tickets) is not dict or any(
        type(record) is not list
        or len(record) != 3
        or type(record[0]) is not runtime._InspectionTicket
        or type(record[2]) is not str
        for record in dict.values(state._tickets)
    ):
        raise ValueError("verifier capture ticket metadata changed")


def _require_grant_metadata(state, owner, now, *, closing=False):
    payload = request = authorization = None
    try:
        _require_fixed()
        _require_issuance_owner(owner)
        _require_grant_tables(state)
        if type(state._grants) is not dict or type(state._grant_payloads) is not dict:
            raise ValueError("verifier grant tables changed their original storage")
        if type(now) is not datetime or now.tzinfo is not UTC or now >= owner[7]:
            raise ValueError("verifier grant original deadline has expired")
        originals = _grant_registration(state)[3]
        if set(originals) != set(state._grants):
            raise ValueError("verifier grant original ticket membership changed")
        for ticket, record in state._grants.items():
            if (
                type(record) is not tuple
                or len(record) != 4
                or any(type(item) is not str and item is not None for item in record)
            ):
                raise ValueError(
                    "verifier grant record is not closed primitive metadata"
                )
            original = originals[ticket]
            if record[1] != state._grant_intent[1]:
                raise ValueError("verifier grant intent identity changed")
            if record[0] == "ISSUING" and not closing:
                if ticket in state._grant_payloads or original[0] not in (
                    "RESERVED",
                    "PREPARED",
                ):
                    raise ValueError("pending verifier grant already has a payload")
                continue
            payload = state._grant_payloads.get(ticket)
            if (
                record[0] != "ISSUED"
                or type(payload) is not tuple
                or len(payload) != 4
                or original[0] != "ISSUED"
                or original[1] is not payload
                or original[2:] != record[2:]
            ):
                raise ValueError("verifier grant publication is incomplete")
            request, authorization, finite, _release = payload
            finite()
            if (
                canonical_identity(request.to_dict()).uri != record[2]
                or canonical_identity(authorization.to_dict()).uri != record[3]
                or authorization.profile is not SecurityProfile.CONSTRAINED
                or authorization.privileges != ("execute-library-verifier",)
            ):
                raise ValueError("original verifier grant or request changed")
            _REQUIRE_BUILD(authorization, request, now=now)
        if set(state._grant_payloads) != {
            ticket for ticket, record in state._grants.items() if record[0] == "ISSUED"
        }:
            raise ValueError("verifier grant payload membership changed")
        if closing:
            state._closing_leases()
    finally:
        payload = request = authorization = finite = _release = owner = state = (
            originals
        ) = original = None


def _require_live_operation_grants(state):
    owner = payload = None
    try:
        owner = _operation_grant_owner(state)
        now = _clock()
        _require_grant_metadata(state, owner, now)
        for payload in state._grant_payloads.values():
            owner[11].require_build_valid(payload[1], payload[0], now=now)
        # The fixed verifier's provider is still a callback boundary. Recheck
        # original empty state and use a fresh cut after it, without calling it again.
        _operation_grant_owner(state)
        _require_grant_metadata(state, owner, _clock())
    finally:
        owner = payload = state = None


def require_node_verifier_authorization(ports, operation, authorization, request):
    """Use an original issued grant only after its capture successfully closes.

    A freshly described request may match the enrolled request's closed identity;
    a copied authorization never replaces the original grant in the journal.
    This boundary does not issue, renew, or discover authority by content digest.
    """
    state = owner = registration = record = payload = ticket = None
    finite = release = primary = None
    try:
        state = runtime._operation_state(operation)
        state.require_live()
        owner = _operation_grant_owner(state)
        if state.binding.originals[2] is not ports:
            raise ValueError("verifier grant belongs to another runtime's ports")
        if (
            type(request) is not BuildRequest
            or type(authorization) is not BuildAuthorization
        ):
            raise TypeError("verifier use requires original typed request and grant")
        # Reject callback-bearing fields before invoking the pinned serializer.
        finite, release, _ = runtime._finite_metadata(request, _with_release=True)
        _require_fixed()
        request_identity = canonical_identity(request.to_dict()).uri
        registration = _grant_registration(state)
        matches = [
            (key, value)
            for key, value in registration[3].items()
            if value[0] == "ISSUED" and value[1][1] is authorization
        ]
        if len(matches) != 1:
            raise ValueError("verifier use requires its exact original issued grant")
        ticket, record = matches[0]
        payload = record[1]
        state.require_ticket(ticket)
        stored = state._tickets[runtime._TICKETS[ticket][1][:2]]
        handoff = state._handoffs.get(ticket)
        if (
            record[2] != request_identity
            or stored[0] is not ticket
            or stored[2] != "CLOSED"
            or type(handoff) is not list
            or len(handoff) != 4
            or handoff[3] != "COMMITTED"
        ):
            raise ValueError("verifier grant requires its successfully closed capture")
        # Closing the capture and all fixed policy callbacks precede this final
        # finite cut. The actual runner reuses it after its own last callbacks.
        _operation_grant_owner(state)
        finite()
        payload[2]()
        _require_grant_metadata(state, owner, _clock())
    except BaseException as error:
        primary = error
        if state is not None:
            state._poisoned = True
        raise
    finally:
        try:
            if release is not None:
                _close_preserving_primary_failure(release, primary)
        except BaseException:
            if state is not None:
                state._poisoned = True
            raise
        finally:
            ports = operation = authorization = request = state = owner = None
            registration = record = payload = ticket = matches = stored = handoff = None
            finite = release = primary = None


def _close_operation_grants(state):
    owner = payload = None
    try:
        # Original source checks and revocation callbacks precede the final cut.
        # Runtime calls this only after all closing view/cleanup settlement.
        owner = _operation_grant_owner(state, closing=True)
        owner[5][0]()
        before = _clock()
        for payload in state._grant_payloads.values():
            owner[11].require_build_valid(payload[1], payload[0], now=before)
        with state.binding.lock:
            _operation_grant_owner(state, closing=True)
            cut = _clock()
            _require_grant_metadata(state, owner, cut, closing=True)
            _operation_grant_owner(state, closing=True)
            registration = _grant_registration(state)
            if registration[6][0] is not None:
                raise ValueError("verifier closing proof cannot be repeated")
            registration[6][0] = tuple(registration[3].items())
    finally:
        owner = payload = state = registration = None


def _final_retiring_grant_check(state, registration):
    owner = binding = certificate = record = None
    try:
        _require_fixed()
        certificate = registration[6][0]
        if state._poisoned is True:
            if certificate is not None:
                raise ValueError(
                    "closed verifier operation was poisoned during retirement"
                )
            return
        _require_grant_state_shape(state)
        if certificate is None:
            if registration[3]:
                raise ValueError("verifier aggregate never completed original closing")
            return
        binding = registration[5]()
        if (
            binding is None
            or state.binding is not binding
            or binding.active is not state
            or not state._retiring
            or state._state != "TERMINAL"
            or len(certificate) != len(registration[3])
            or any(
                registration[3].get(ticket) is not original
                for ticket, original in certificate
            )
        ):
            raise ValueError("verifier retiring aggregate membership changed")
        acknowledgement = registration[1]()
        owner = _original_owner(acknowledgement)
        bound, configuration = binding.originals[:2]
        if (
            configuration.snapshot is not owner[2]
            or configuration.expected_execution is not owner[3]
        ):
            raise ValueError(
                "verifier retiring configuration changed original authority"
            )
        membership._require_acknowledgement(
            acknowledgement,
            configuration,
            bound,
            facts=owner[4],
            originals=(owner[2], owner[3]),
        )
        owner[5][0]()
        _require_fixed()
        _require_issuance_owner(owner)
        before = _clock()
        for _ticket, record in certificate:
            record[1][2]()
            owner[11].require_build_valid(record[1][1], record[1][0], now=before)
        with binding.lock:
            _require_fixed()
            _require_grant_state_shape(state)
            if (
                state._poisoned
                or state.binding is not binding
                or binding.active is not state
                or state._state != "TERMINAL"
                or not state._retiring
            ):
                raise ValueError(
                    "verifier retiring operation changed during final callbacks"
                )
            if (
                configuration.snapshot is not owner[2]
                or configuration.expected_execution is not owner[3]
            ):
                raise ValueError(
                    "verifier retiring configuration changed original authority"
                )
            binding.require_finite()
            owner[5][1]()
            for witness in registration[4]:
                if witness is not None:
                    witness()
            cut = _clock()
            _require_grant_metadata(state, owner, cut)
            owner[5][1]()
            binding.require_finite()
            if (
                configuration.snapshot is not owner[2]
                or configuration.expected_execution is not owner[3]
            ):
                raise ValueError("verifier retiring configuration changed at final cut")
    finally:
        owner = binding = certificate = record = state = registration = None
        acknowledgement = bound = configuration = witness = None


def _retire_operation_grants(state):
    payloads = intent = original = _retained_runtime = None
    terminal_error = None
    try:
        with state.binding.lock:
            with _GRANT_LOCK:
                if id(state.handle) not in _OPERATION_GRANTS:
                    if (
                        state._grant_intent is not None
                        or type(state._grants) is not dict
                        or type(state._grant_payloads) is not dict
                        or len(state._grants)
                        or len(state._grant_payloads)
                    ):
                        raise ValueError(
                            "verifier grant retirement lost its original journal"
                        )
                    with runtime._GRANT_MEMBERSHIP_LOCK:
                        runtime._GRANT_OPERATIONS.pop(state.handle, None)
                    return
            original = _grant_registration(state)
            payloads, intent = tuple(original[3].items()), state._grant_intent
            _retained_runtime = state._grant_payloads, state._grants
        try:
            _final_retiring_grant_check(state, original)
        except BaseException as error:
            state._poisoned = True
            terminal_error = error
        try:
            _release_original_grants(original)
        except BaseException:
            if terminal_error is not None:
                return terminal_error
            raise
        with state.binding.lock:
            if (
                state._grant_intent is not intent
                or _grant_registration(state) is not original
                or len(original[3]) != len(payloads)
                or any(
                    original[3].get(ticket) is not payload
                    for ticket, payload in payloads
                )
            ):
                raise ValueError("verifier grant retirement membership changed")
            state._grants = {}
            state._grant_payloads = {}
            state._grant_intent = None
            with _GRANT_LOCK:
                _OPERATION_GRANTS.pop(id(state.handle))
                with runtime._GRANT_MEMBERSHIP_LOCK:
                    runtime._GRANT_OPERATIONS.pop(state.handle, None)
        return terminal_error
    finally:
        # In particular, dropping the final acknowledgement can release its
        # source witness. Retain it until outside the operation mutex as well.
        payloads = intent = state = original = _retained_runtime = terminal_error = None


def _issue_enrolled_node_verifier_authorization(
    acknowledgement, operation, handle, ticket
):
    """Fixed issuer only: reserve, classify original inputs, issue and register."""
    state = owner = classification = description = None
    primary = None
    request = authorization = classification_guard = release_classification = (
        payload
    ) = registration = None
    payload_owned = False
    try:
        state = runtime._operation_state(operation)
        owner = _original_owner(acknowledgement)
        identity = membership._values(membership._state(acknowledgement))[1]
        with state.binding.lock:
            registration = _grant_registration(
                state, acknowledgement, identity, create=True
            )
            state.begin_issuance(ticket, acknowledgement, identity)
            if ticket in registration[3]:
                raise ValueError("verifier fixed issuer reservation cannot be repeated")
            registration[3][ticket] = ("RESERVED", None, None, None)
        classification, _observation, _attestation = (
            _classify_enrolled_node_verifier_inputs(
                acknowledgement, operation, handle, ticket
            )
        )
        classification_guard, release_classification, _ = runtime._finite_metadata(
            classification, _with_release=True
        )
        _, description = captures._read_runtime_scan_inputs(operation, handle, ticket)
        _require_fixed()
        _require_issuance_owner(owner)
        classification_guard()
        request = NodeLibraryVerifierRequestDescription(*description).request
        document = _AUTHORIZE(owner[12], classification.to_dict(), request.to_dict())
        _require_fixed()
        authorization = BuildAuthorization.from_dict(document)
        if authorization.classification_digest != classification.digest:
            raise ValueError("verifier grant lost original classification")
        owner[11].require_build_valid(authorization, request, now=_clock())
        finite, release, _ = runtime._finite_metadata(
            request, authorization, _with_release=True
        )
        payload = request, authorization, finite, release
        request_identity = canonical_identity(request.to_dict()).uri
        grant_identity = canonical_identity(authorization.to_dict()).uri
        with state.binding.lock:
            if _grant_registration(state) is not registration or registration[3].get(
                ticket
            ) != ("RESERVED", None, None, None):
                raise ValueError("verifier fixed issuer reservation changed")
            registration[3][ticket] = (
                "PREPARED",
                payload,
                request_identity,
                grant_identity,
            )
            payload_owned = True
        # Authority/capture callbacks finish before publishing the grant record.
        owner[5][0]()
        captures._read_runtime_scan_inputs(operation, handle, ticket)
        _require_fixed()
        _require_issuance_owner(owner)
        classification_guard()
        owner[5][1]()
        _REQUIRE_BUILD(authorization, request, now=_clock())
        state.finish_issuance(
            ticket,
            identity,
            request,
            authorization,
            request_identity,
            grant_identity,
            payload,
        )
        with state.binding.lock:
            _operation_grant_owner(state)
            _require_grant_metadata(state, owner, _clock())
        return authorization
    except BaseException as error:
        primary = error
        if state is not None:
            _close_preserving_primary_failure(
                lambda: state.fail_issuance(ticket), error
            )
        try:
            membership._poison_preserving_failure(membership._state(acknowledgement))
        except BaseException:
            pass
        raise
    finally:
        try:
            if release_classification is not None:
                _close_preserving_primary_failure(release_classification, primary)
        except BaseException as error:
            if state is not None:
                _close_preserving_primary_failure(
                    lambda: state.fail_issuance(ticket), error
                )
            raise
        finally:
            try:
                if payload is not None and not payload_owned:
                    _close_preserving_primary_failure(payload[3], primary)
            finally:
                acknowledgement = operation = handle = ticket = state = owner = None
                classification = _observation = _attestation = description = request = (
                    authorization
                ) = None
                classification_guard = release_classification = document = primary = (
                    None
                )
                registration = payload = finite = release = None


_ORIGINAL_VERIFIER_INTENT_IDENTITY = _verifier_intent_identity
_ORIGINAL_REQUIRE_HOST_VERIFIER_INTENT = _require_host_verifier_intent
_ORIGINAL_BIND_HOST_VERIFIER_INTENT = _bind_host_verifier_intent
_ORIGINAL_REQUIRE_HOST_VERIFIER_OPERATION = _require_host_verifier_operation
_ORIGINAL_ISSUE_HOST_VERIFIER_CAPTURE = _issue_host_verifier_capture


_ORIGINAL_NODE_VERIFIER_AUTHORIZATION = require_node_verifier_authorization


_CONSTANTS = tuple(
    (name, globals()[name])
    for name in (
        "_ISSUER_TOKEN",
        "_DATA_SUFFIXES",
        "_LICENSE_NAMES",
        "_MAX_LIFETIME",
        "_PRIVILEGES",
        "_EMPTY_REVOCATIONS",
        "_GRANT_LOCK",
        "_OPERATION_GRANTS",
        "_MAX_GRANT_OPERATIONS",
        "_release_original_grants",
        "_drop_operation_grants",
        "_grant_registration",
        "_require_issuing_payload",
        "_publish_initial_grant_intent",
        "_commit_issuing_payload",
        "_register_grant_invocation_witness",
        "_require_grant_tables",
        "_require_grant_state_shape",
        "_final_retiring_grant_check",
        "threading",
        "_POLICY_ID",
        "_POLICY",
        "_SNAPSHOT_REQUIRE",
        "_SNAPSHOT_SLOTS",
        "_AUTHORITY_SLOTS",
        "_POLICY_SLOTS",
        "_POLICY_VALUES",
        "_AUTHORIZE",
        "_REQUIRE_BUILD",
        "_REVOCATIONS_ENTRIES",
        "_VERIFIER_PROVIDER",
        "_AUTHORIZER_SLOTS",
        "_clock",
        "_make_issuance_owner",
        "_require_issuance_owner",
        "_operation_grant_owner",
        "_require_grant_metadata",
        "_require_live_operation_grants",
        "require_node_verifier_authorization",
        "_ORIGINAL_NODE_VERIFIER_AUTHORIZATION",
        "_close_operation_grants",
        "_retire_operation_grants",
        "_issue_enrolled_node_verifier_authorization",
        "_require_fixed",
        "_source_guard",
        "acknowledge_node_sdk_verifier_execution",
        "_original_owner",
        "_ORIGINAL_VERIFIER_INTENT_IDENTITY",
        "_ORIGINAL_REQUIRE_HOST_VERIFIER_INTENT",
        "_ORIGINAL_BIND_HOST_VERIFIER_INTENT",
        "_ORIGINAL_REQUIRE_HOST_VERIFIER_OPERATION",
        "_ORIGINAL_ISSUE_HOST_VERIFIER_CAPTURE",
        "_verifier_intent_identity",
        "_require_host_verifier_intent",
        "_bind_host_verifier_intent",
        "_require_host_verifier_operation",
        "_issue_host_verifier_capture",
        "_require_supported_coverage",
        "_classify_enrolled_node_verifier_inputs",
        "LockedGenerationAuthoritySnapshot",
        "LockedGenerationAuthority",
        "ComponentExecutionPlan",
        "NodeLibraryVerifierRequestDescription",
        "SecurityPolicy",
        "OriginAttestation",
        "SecurityClassification",
        "SecurityScanReport",
        "BuildAuthorization",
        "BuildRequest",
        "SecurityProfile",
        "LiveBuildAuthorizationVerifier",
        "PolicyBuildAuthorizer",
        "AuthorizationRevocationSet",
        "local_policy",
        "canonical_identity",
        "datetime",
        "timedelta",
        "UTC",
        "dataclasses",
        "json",
        "hashlib",
        "types",
        "weakref",
        "PurePosixPath",
        "membership",
        "runtime",
        "captures",
        "scans",
        "security",
        "requests",
        "scanning",
        "identities",
    )
)
