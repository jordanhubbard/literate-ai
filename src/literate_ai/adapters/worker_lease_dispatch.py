"""Durable, single-attempt admission for an exact managed SSH registration."""

from __future__ import annotations

import secrets
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai.contracts._validation import contract_fields
from literate_ai.contracts.identity import ContentIdentity

from .ssh_execution import SshLifecycleRequestHandler
from .worker_lease_management import _configuration, _expiry, manage_lease
from .worker_provisioning import (
    LIMIT,
    operation_path,
    read_record,
    refuse,
    registered_worker,
    write_private,
)
from .worker_registry import read_registry

SCHEMA = "literate-ai/worker-lease-dispatch@1"


def validate_saved_dispatch(record):
    dispatch = contract_fields(
        record["dispatch"],
        path="WorkerLeaseDispatch",
        schema_uri=SCHEMA,
        required=frozenset(
            {
                "attempt",
                "request_identity",
                "worker_identity",
                "deadline_at",
                "state",
                "cancellation_requested",
            }
        ),
    )
    attempt = dispatch["attempt"]
    if (
        record.get("managed") is not True
        or type(attempt) is not str
        or len(attempt) != 64
        or any(c not in "0123456789abcdef" for c in attempt)
        or dispatch["state"]
        not in ("active", "not-started", "complete", "uncertain", "released")
        or type(dispatch["cancellation_requested"]) is not bool
        or dispatch["worker_identity"] != registered_worker(record).identity.uri
        or (dispatch["state"] == "released" and record["status"] != "released")
    ):
        refuse("dispatch_invalid", "Managed dispatch does not bind its allocation.")
    ContentIdentity.parse_uri(dispatch["request_identity"])
    _expiry(dispatch["deadline_at"])


def release_dispatch(record, cancel_attempt):
    """Drain by default; cancellation must name the actual outstanding attempt."""
    dispatch = record.get("dispatch")
    if record["status"] == "released":
        if cancel_attempt is not None and (
            dispatch is None
            or not dispatch["cancellation_requested"]
            or cancel_attempt != dispatch["attempt"]
        ):
            refuse("dispatch_changed", "Cancellation must name the cancelled attempt.")
        return False
    outstanding = dispatch is not None and dispatch["state"] in (
        "active",
        "uncertain",
    )
    if cancel_attempt is not None:
        if not outstanding or cancel_attempt != dispatch["attempt"]:
            refuse("dispatch_changed", "Cancellation must name the current attempt.")
        dispatch["cancellation_requested"] = True
    return outstanding and not dispatch["cancellation_requested"]


def _available(record, worker):
    if record["status"] != "registered" or registered_worker(record) != worker:
        refuse("lease_unavailable", "Dispatch requires its exact registered lease.")
    dispatch = record.get("dispatch")
    if dispatch is not None and dispatch["state"] in ("active", "uncertain"):
        refuse(
            "dispatch_outstanding",
            "An active or interrupted attempt remains; inspect status and drain "
            "or explicitly cancel that attempt before releasing its lease.",
        )
    if worker not in read_registry(Path(record["catalog_path"])).workers:
        refuse("registration_changed", "Managed worker registration changed.")


@contextmanager
def admitted_lease_dispatch(config_path, state, worker, request, environment):
    """No timeout or controller crash silently forgets a possibly running job."""
    path = operation_path(state, worker.worker_id)
    lock = path.with_suffix(".lock")
    started, observed_at = time.monotonic(), datetime.now(UTC)
    reserved_seconds = (
        request.timeout_seconds + SshLifecycleRequestHandler.cleanup_wait_seconds()
    )

    def current_time():
        # A backward wall-clock step during lookup/execution cannot extend TTL.
        return max(
            datetime.now(UTC),
            observed_at + timedelta(seconds=time.monotonic() - started),
        )

    with exclusive_cache_lock(lock):
        _available(read_record(path), worker)
    # This is lookup only, never allocation. A second locked admission checks
    # concurrent observation, release or dispatch after the provider reply.
    manage_lease(config_path, state, worker.worker_id, environment, operation="observe")
    with exclusive_cache_lock(lock):
        record = read_record(path)
        _available(record, worker)
        _configuration(config_path, environment, record)
        management = record.get("management")
        response = management["response"] if management else None
        deadline = current_time() + timedelta(seconds=reserved_seconds)
        if (
            management is None
            or management["state"] != "complete"
            or response["status"] != "ready"
            or management["release_request"] is not None
            or _expiry(response["expires_at"]) <= deadline
        ):
            refuse(
                "lease_deadline_insufficient",
                "An observed ready lease must cover the whole job and termination.",
            )
        attempt = secrets.token_hex(32)
        record["dispatch"] = dict(
            schema=SCHEMA,
            attempt=attempt,
            request_identity=request.identity.uri,
            worker_identity=worker.identity.uri,
            deadline_at=response["expires_at"],
            state="active",
            cancellation_requested=False,
        )
        write_private(path, record, limit=3 * LIMIT)
        expires_at = _expiry(response["expires_at"])
        # fsync/publication is outside the handler's execution deadline. Never
        # start its fresh whole timeout if that work consumed the lease headroom.
        execution_deadline = time.monotonic() + request.timeout_seconds
        deadline = current_time() + timedelta(seconds=reserved_seconds)
        if deadline >= expires_at:
            record["dispatch"]["state"] = "not-started"
            write_private(path, record, limit=3 * LIMIT)
            refuse(
                "lease_deadline_insufficient",
                "Lease headroom was consumed before launch.",
            )
    complete = False
    try:
        yield execution_deadline
        if current_time() >= min(deadline, expires_at):
            refuse(
                "dispatch_deadline_exceeded",
                "Managed dispatch exceeded its lease deadline.",
            )
        complete = True
    finally:
        with exclusive_cache_lock(lock):
            record = read_record(path)
            dispatch = record.get("dispatch")
            if dispatch is None or dispatch["attempt"] != attempt:
                refuse("dispatch_changed", "Admitted dispatch record changed.")
            if record["status"] == "released" or dispatch["cancellation_requested"]:
                if complete:
                    refuse(
                        "dispatch_cancelled",
                        "Lease cancellation invalidated this attempt.",
                    )
            else:
                dispatch["state"] = "complete" if complete else "uncertain"
                write_private(path, record, limit=3 * LIMIT)
