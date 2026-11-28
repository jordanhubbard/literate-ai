"""Finite private polling between a query and actual operation-local owners.

No listener, execution factory or decoded-history owner exists here. The query
collector and response service use only observational namespace files; they never
take an execution/result lock, retain an execution lease or signal selected jobs.
"""

from __future__ import annotations

import secrets
import threading
import time
from contextlib import ExitStack, contextmanager
from contextvars import Context
from datetime import UTC, datetime
from functools import partial

from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.worker_telemetry_v2 import (
    MAX_RESPONSE_BYTES,
    TelemetryScope,
    WorkerTelemetryResponse,
)

from .action_dispatch_wire import ActionDispatchDeadline, ActionWireError
from .worker_telemetry_authentication_v2 import encode_telemetry_response
from .worker_telemetry_configuration import CurrentWorkerTelemetryConfiguration
from .worker_telemetry_contributions import (
    contribute_actual_worker_sample,
    verify_worker_telemetry_contribution,
)
from .worker_telemetry_live_slots import (
    claim_actual_owner_slot,
    live_slot_directory,
    require_unambiguous_slot,
)
from .worker_telemetry_namespace import open_worker_telemetry_namespace, refuse
from .worker_telemetry_owner import ConfiguredWorkerTelemetryPublisher
from .worker_telemetry_replay import _locked, consume_worker_telemetry_request
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError, _decode

_DESCRIPTOR_SCHEMA = "literate-ai/private-worker-telemetry-live-descriptor@2"
_ERROR_SCHEMA = "literate-ai/private-worker-telemetry-slot-refusal@1"
_ERROR = canonical_json_bytes(
    {"schema": _ERROR_SCHEMA, "code": "worker_telemetry.owner_unavailable"}
)


class WorkerTelemetryRelay:
    """Only an observation-stop event; no execution/cancellation handle."""

    def __init__(self):
        self._stopped = threading.Event()

    def close(self):
        # Never join or wait for file I/O from the action's completion path.
        self._stopped.set()

    def __reduce__(self):
        raise TypeError("an observation relay cannot be restored")


def _overloaded(error):
    return error.code == "worker_telemetry.observation_overloaded"


@contextmanager
def _claim_owner(publisher, owner, stopped):
    # Only transient observation-lock contention retries. Each failed context
    # releases its private descriptors; foreign/corrupt custody never retries.
    ends_at = time.monotonic() + 30
    with ExitStack() as stack:
        while True:
            owner.require_open()
            if stopped.is_set() or time.monotonic() >= ends_at:
                refuse("owner_unavailable")
            try:
                selected = stack.enter_context(
                    claim_actual_owner_slot(publisher, owner)
                )
                break
            except WorkerTelemetryWireError as exc:
                if not _overloaded(exc):
                    raise
                stopped.wait(0.05)
        yield selected


def _publish_pending(files, current, owner, stopped, raw, response):
    # Retain one finite same-generation response across brief collector I/O
    # contention. Never recompute it or publish it into a later query generation.
    ends_at = time.monotonic() + 30
    while not stopped.is_set() and time.monotonic() < ends_at:
        owner.require_open()
        current()
        try:
            with _locked(files[".io"].descriptor):
                files[".io"].require_current()
                current()
                if files["request"].read() != raw:
                    return
                owner.require_open()
                files["response"].write(response)
                return
        except WorkerTelemetryWireError as exc:
            if not _overloaded(exc):
                raise
            stopped.wait(0.05)


def _serve_owner(publisher, owner, stopped):
    try:
        with _claim_owner(publisher, owner, stopped) as (files, current):
            # Thread startup/IO belongs ONLY to this separate observer service.
            # No query starts a process; no execution/result lock is held here.
            from .worker_telemetry_native_measurement import (
                start_native_resource_sampling,
            )

            start_native_resource_sampling(owner)
            processed = None
            while not stopped.is_set():
                owner.require_open()
                current()
                try:
                    with _locked(files[".io"].descriptor):
                        files[".io"].require_current()
                        raw = files["request"].read()
                except WorkerTelemetryWireError as exc:
                    if not _overloaded(exc):
                        raise
                    stopped.wait(0.05)
                    continue
                if not raw or raw == processed:
                    stopped.wait(0.05)
                    continue
                processed = raw  # One bounded request retained, never history.
                try:
                    expected = publisher._epoch.digest.encode("ascii") + b"\n"
                    if raw[:65] != expected:
                        refuse("publisher_epoch_changed")
                    response = contribute_actual_worker_sample(
                        publisher, raw[65:], owner.operation_identity
                    )
                except Exception:
                    response = _ERROR  # No exception text, argv, environment or paths.
                _publish_pending(files, current, owner, stopped, raw, response)
    except Exception:
        # Missing/corrupt/ended observation ownership stops only this service.
        # The collector will refuse rather than infer a terminal action result.
        return


def start_worker_telemetry_relay(publisher):
    """Start only inside the actual configured worker, never the query receiver.

    Threads inherit an empty context, so observation work cannot register itself
    as a job child. At most64 services are started for actual registered owners;
    every service stops on original admission closure or its action deadline.
    """
    if type(publisher) is not ConfiguredWorkerTelemetryPublisher:
        refuse("actual_receiver_required")
    publisher._require_local()
    relay = WorkerTelemetryRelay()

    def watch():
        services = {}
        seen_owner = False
        while not relay._stopped.is_set():
            publisher._require_local()
            if not publisher._lock.acquire(blocking=False):
                relay._stopped.wait(0.05)
                continue
            try:
                owners = tuple(publisher._owners.items())
            finally:
                publisher._lock.release()
            if owners:
                seen_owner = True
            active = False
            for identity, owner in owners:
                if owner._closed.is_set():
                    continue
                active = True
                if identity in services:
                    continue
                thread = threading.Thread(
                    target=lambda selected=owner: Context().run(
                        _serve_owner, publisher, selected, relay._stopped
                    ),
                    daemon=True,
                    name="litai-telemetry-owner",
                )
                services[identity] = thread
                thread.start()
            if seen_owner and not active:
                return
            relay._stopped.wait(0.05)

    def guarded_watch():
        try:
            watch()
        except Exception:
            relay.close()

    threading.Thread(
        target=lambda: Context().run(guarded_watch),
        daemon=True,
        name="litai-telemetry-relay",
    ).start()
    return relay


def _descriptor(raw, operation):
    value = _decode(raw, 2048)
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema",
            "operation_identity",
            "action_identity",
            "publisher_epoch",
            "owner_epoch",
            "reservation_identity",
            "claim_index",
        }
        or value["schema"] != _DESCRIPTOR_SCHEMA
        or ContentIdentity.from_dict(value["operation_identity"]) != operation
        or type(value["claim_index"]) is not int
        or not 0 <= value["claim_index"] < 64
    ):
        refuse("owner_descriptor_invalid")
    # These values locate/compare a fresh signed contribution. They grant no
    # owner, process access or authority by being decoded from a saved file.
    return (
        ContentIdentity.from_dict(value["publisher_epoch"]),
        ContentIdentity.from_dict(value["action_identity"]),
        ContentIdentity.from_dict(value["owner_epoch"]),
        None
        if value["reservation_identity"] is None
        else ContentIdentity.from_dict(value["reservation_identity"]),
        value["claim_index"],
    )


@contextmanager
def collect_worker_telemetry(raw, configuration, *, ends_at_monotonic=None):
    """Yield an exact fresh batch while holding only an observer collector lease.

    The caller must bound stdin/stdout and the full30-second observation lifetime.
    It may cancel/close this context without touching any action's ownership.
    The initial backend serializes collectors; excess refuses without waiting.
    """
    if (
        type(configuration) is not CurrentWorkerTelemetryConfiguration
        or configuration.role != "receiver"
    ):
        refuse("receiver_configuration_required")
    request = consume_worker_telemetry_request(raw, configuration)
    if request.scope is not TelemetryScope.OPERATIONS:
        refuse("aggregate_backend_unsupported")
    deadline = ActionDispatchDeadline(
        datetime.fromtimestamp(request.expires_at_ms / 1000, UTC)
    )
    ends_at = time.monotonic() + min(30, deadline.remaining())
    if ends_at_monotonic is not None:
        ends_at = min(ends_at, ends_at_monotonic)
    posted = []
    samples = []
    used_contribution_bytes = 0
    # This is one actual finite collector, not a persistent streaming receiver.
    # Job continuity uses each sample's actual owner epoch and sample sequence.
    collector_epoch = canonical_identity(
        {
            "schema": "literate-ai/actual-worker-telemetry-collector-epoch@1",
            "registration_identity": configuration.registration_identity.to_dict(),
            "namespace_identity": (
                configuration.observation_namespace_identity.to_dict()
            ),
            "nonce": secrets.token_hex(32),
        }
    )

    def current():
        try:
            deadline.remaining()
        except ActionWireError as exc:
            raise WorkerTelemetryWireError("worker_telemetry.query_expired") from exc
        if time.monotonic() >= ends_at:
            refuse("query_expired")

    def selected_current(
        files, slot_current, claim_current, operation, expected, content=None
    ):
        current()
        # Reopen the bounded operator/key/scope closure during contention.
        # Full code/provider currentness still brackets signed publication.
        try:
            configuration.require_observation_inputs_current(deadline=deadline)
        except WorkerTelemetryWireError:
            # The input guard may wrap a deadline crossing as configuration
            # unavailability. Preserve THIS request's absolute expiry reason;
            # an unexpired configuration failure is rethrown without retry.
            current()
            raise
        slot_current()
        files[".io"].require_current()
        require_unambiguous_slot(files)
        if (
            _descriptor(files["descriptor"].read(), operation) != expected
            or content is not None
            and files["request"].read() != content
        ):
            refuse("query_generation_changed")
        epoch, _action, owner_epoch, _reservation, claim_index = expected
        claim_current(epoch, owner_epoch, claim_index)
        slot_current()
        current()

    @contextmanager
    def slot_io(files, guard):
        # This waits only for an observational file lock, never an execution
        # owner. The SAME absolute request/receiver deadline bounds every wait.
        while True:
            current()
            guard()
            acquired = False
            try:
                with _locked(files[".io"].descriptor):
                    acquired = True
                    current()
                    guard()
                    yield
                return
            except WorkerTelemetryWireError as exc:
                # Guard/body failures are not lock-acquisition contention and
                # must never replay a partially executed publication block.
                if acquired or not _overloaded(exc):
                    raise
            current()
            guard()
            time.sleep(min(0.01, max(0, ends_at - time.monotonic())))

    def posted_current():
        # Exact sequential rejoin; no atomic multi-operation snapshot is claimed.
        for (
            operation,
            epoch,
            action,
            owner_epoch,
            reservation,
            claim_index,
            content,
        ) in posted:
            with live_slot_directory(configuration, operation) as (
                files,
                slot_current,
                claim_current,
            ):
                expected = epoch, action, owner_epoch, reservation, claim_index

                guard = partial(
                    selected_current,
                    files,
                    slot_current,
                    claim_current,
                    operation,
                    expected,
                    content,
                )
                with slot_io(files, guard):
                    guard()

    try:
        with (
            open_worker_telemetry_namespace(configuration) as (
                _directory,
                collector,
                _allocation,
                _live,
                _claim_lock,
                _claims,
                _poison,
                namespace_current,
            ),
            _locked(collector),
        ):
            try:
                # Open/close each owner in turn: a64-operation batch must not
                # require64 complete descriptor stacks or exhaust native FD caps.
                for operation in request.operation_identities:
                    current()
                    with live_slot_directory(configuration, operation) as (
                        files,
                        slot_current,
                        claim_current,
                    ):
                        expected = _descriptor(files["descriptor"].read(), operation)
                        epoch, action, owner_epoch, reservation, claim_index = expected

                        guard = partial(
                            selected_current,
                            files,
                            slot_current,
                            claim_current,
                            operation,
                            expected,
                        )
                        with slot_io(files, guard):
                            guard()
                            if (reservation is not None) != (
                                configuration.protected_parent_configuration is not None
                            ):
                                refuse("protected_parent_mismatch")
                            content = epoch.digest.encode("ascii") + b"\n" + raw
                            files["response"].write(b"")
                            files["request"].write(content)
                            slot_current()
                    posted.append(
                        (
                            operation,
                            epoch,
                            action,
                            owner_epoch,
                            reservation,
                            claim_index,
                            content,
                        )
                    )
                for (
                    operation,
                    epoch,
                    action,
                    owner_epoch,
                    reservation,
                    claim_index,
                    content,
                ) in posted:
                    while True:
                        current()
                        try:
                            with (
                                live_slot_directory(configuration, operation) as (
                                    files,
                                    slot_current,
                                    _claim_current,
                                ),
                                _locked(files[".io"].descriptor),
                            ):
                                require_unambiguous_slot(files)
                                if files["request"].read() != content:
                                    refuse("query_generation_changed")
                                response = files["response"].read()
                                _claim_current(epoch, owner_epoch, claim_index)
                                slot_current()
                        except WorkerTelemetryWireError as exc:
                            if exc.code != "worker_telemetry.observation_overloaded":
                                raise
                            response = b""
                        if response:
                            if response == _ERROR:
                                refuse("owner_unavailable")
                            # Bound actual internal transfer bytes BEFORE decoding
                            # another sample. Public framing is measured below.
                            used_contribution_bytes += len(response)
                            if used_contribution_bytes > MAX_RESPONSE_BYTES:
                                refuse("contribution_batch_limit")
                            sample = verify_worker_telemetry_contribution(
                                response,
                                request=request,
                                scope=configuration.scope,
                                expected_operation_identity=operation,
                                expected_publisher_epoch=epoch,
                                now_ms=int(datetime.now(UTC).timestamp() * 1000),
                            )
                            if (
                                sample.action_identity != action
                                or sample.owner_epoch != owner_epoch
                                or sample.reservation_identity != reservation
                            ):
                                refuse("owner_epoch_changed")
                            samples.append(sample)
                            break
                        time.sleep(min(0.05, max(0, ends_at - time.monotonic())))
                current()
                posted_current()
                batch = WorkerTelemetryResponse(
                    request.identity,
                    collector_epoch,
                    0,
                    tuple(samples),
                )
                frame = encode_telemetry_response(
                    batch,
                    request,
                    configuration.scope,
                    configuration.signer,
                    now_ms=int(datetime.now(UTC).timestamp() * 1000),
                )
                configuration.require_current(deadline=deadline)
                namespace_current()
                current()
                # Signing and full configuration validation may be slow. Known
                # conflicts must still refuse at the final publication boundary.
                posted_current()
                current()
                yield frame, deadline
            finally:
                for (
                    operation,
                    _epoch,
                    _action,
                    _owner_epoch,
                    _reservation,
                    _claim_index,
                    content,
                ) in posted:
                    try:
                        with (
                            live_slot_directory(configuration, operation) as (
                                files,
                                _current,
                                _claim_current,
                            ),
                            _locked(files[".io"].descriptor),
                        ):
                            if files["request"].read() == content:
                                files["request"].write(b"")
                                files["response"].write(b"")
                    except Exception:
                        # A stopped reader never waits for a producer's file I/O.
                        # Its unchanged generation remains bounded/stale; later
                        # queries replace it only under that same observer lock.
                        pass
    except WorkerTelemetryWireError:
        raise
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        raise WorkerTelemetryWireError(
            "worker_telemetry.collector_unavailable"
        ) from exc
