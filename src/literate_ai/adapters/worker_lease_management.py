"""Explicit provider lookup and idempotent release of recorded allocations.

The provisioning journal remains the authority. This module never allocates,
discovers an unrecorded worker, or deletes a static registration by name alone.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from literate_ai._cache_lock import exclusive_cache_lock
from literate_ai.contracts import ExecutionWorkerCatalog
from literate_ai.contracts._validation import contract_fields, string_value
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.worker_provisioning import WorkerProvisioner

from .worker_provisioning import (
    LIMIT,
    admitted,
    invoke,
    operation_path,
    read_private,
    read_record,
    refuse,
    registered_worker,
    validate_response,
    write_private,
)
from .worker_registry import change_registry

REQUEST_SCHEMA = "urn:literate-ai:schema:v1:worker-lease-request"
RESPONSE_SCHEMA = "urn:literate-ai:schema:v1:worker-lease-response"
JOURNAL_SCHEMA = "literate-ai/worker-lease-management@1"


def _expiry(value):
    string_value(value, "WorkerLeaseResponse.expires_at", max_length=64)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        refuse("lease_invalid", "Lease expiry must be a UTC timestamp.")
    if not value.endswith("Z") or result.tzinfo != UTC:
        refuse("lease_invalid", "Lease expiry must be a UTC timestamp ending in Z.")
    return result


def _request(value, record):
    request = contract_fields(
        value,
        path="WorkerLeaseRequest",
        schema_uri=REQUEST_SCHEMA,
        required=frozenset(
            {
                "operation",
                "nonce",
                "provision_request_identity",
                "request_id",
                "worker_id",
                "lease_id",
            }
        ),
    )
    nonce = string_value(request["nonce"], "WorkerLeaseRequest.nonce", max_length=64)
    if (
        len(nonce) != 64
        or any(character not in "0123456789abcdef" for character in nonce)
        or request["operation"] not in ("observe", "release")
        or request["provision_request_identity"] != record["request_identity"]
        or request["request_id"] != record["request"]["request_id"]
        or request["worker_id"] != record["request"]["worker_id"]
    ):
        refuse("lease_invalid", "Lease request differs from its allocation journal.")
    if request["lease_id"] is not None:
        string_value(
            request["lease_id"], "WorkerLeaseRequest.lease_id", max_length=1024
        )
        if (
            record["response"] is None
            or request["lease_id"] != record["response"]["lease_id"]
        ):
            refuse(
                "lease_mismatch", "Lease identity differs from the saved allocation."
            )
    return request


def _response(value, request, record):
    response = contract_fields(
        value,
        path="WorkerLeaseResponse",
        schema_uri=RESPONSE_SCHEMA,
        required=frozenset(
            {"request_identity", "status", "provision_response", "expires_at"}
        ),
    )
    if response["request_identity"] != canonical_identity(request).uri:
        refuse("lease_mismatch", "Lease reply does not match this management request.")
    if response["status"] not in ("ready", "pending", "absent", "released"):
        refuse("lease_invalid", "Unknown provider lease status.")
    if request["operation"] == "release" and response["status"] not in (
        "pending",
        "released",
    ):
        refuse(
            "lease_invalid", "Release requires an explicit pending or released reply."
        )
    if response["status"] == "ready":
        validate_response(response["provision_response"], record["request"])
        _expiry(response["expires_at"])
        if (
            record["response"] is not None
            and record["response"] != response["provision_response"]
        ):
            refuse("lease_mismatch", "Provider returned a different allocation.")
    elif (
        response["provision_response"] is not None or response["expires_at"] is not None
    ):
        refuse("lease_invalid", "A non-ready reply cannot assert an available worker.")
    return response


def validate_saved_management(record):
    if record.get("managed") is not True:
        refuse("lease_invalid", "Lease management requires a bound allocation record.")
    management = contract_fields(
        record["management"],
        path="WorkerLeaseManagement",
        schema_uri=JOURNAL_SCHEMA,
        required=frozenset({"state", "request", "response", "release_request"}),
    )
    request = _request(management["request"], record)
    release = management["release_request"]
    if release is not None and _request(release, record)["operation"] != "release":
        refuse("lease_invalid", "Saved release intent must be a release request.")
    if request["operation"] == "release" and request != release:
        refuse("lease_invalid", "Release retry must preserve its original request.")
    if management["state"] == "pending":
        if management["response"] is not None or record["status"] == "released":
            refuse("lease_invalid", "Pending management cannot assert completion.")
    elif management["state"] == "complete":
        response = _response(management["response"], request, record)
        if (record["status"] == "released") != (response["status"] == "released"):
            refuse("lease_invalid", "Release journal and provider reply disagree.")
    else:
        refuse("lease_invalid", "Unknown lease management state.")
    if release is not None and record["status"] not in ("releasing", "released"):
        refuse("lease_invalid", "Release intent cannot return to ready or registered.")


def require_recoverable_lease(record):
    management = record["management"]
    response = management["response"]
    if (
        record["status"] in ("releasing", "released")
        or management["state"] != "complete"
        or response["status"] != "ready"
        or _expiry(response["expires_at"]) <= datetime.now(UTC)
    ):
        refuse(
            "lease_unavailable",
            "Recovery requires an observed, unexpired lease with no release intent.",
        )


def _unregister_owned(record):
    def transform(catalog):
        existing = next(
            (
                w
                for w in catalog.workers
                if w.worker_id == record["request"]["worker_id"]
            ),
            None,
        )
        if existing is None:
            return catalog
        if record["response"] is None or existing != registered_worker(record):
            refuse(
                "registration_conflict",
                "Worker registration changed; preserve it and inspect ownership.",
            )
        return ExecutionWorkerCatalog(
            tuple(w for w in catalog.workers if w != existing)
        )

    change_registry(Path(record["catalog_path"]), transform)


def _configuration(config_path, environment, record):
    if record.get("managed") is not True:
        refuse(
            "management_unconfigured",
            "This allocation predates managed registration; reconcile its ownership.",
        )
    config, child, _ = admitted(config_path, environment, allow_disabled=True)
    if not config.management_command:
        refuse(
            "management_unconfigured", "Configure a separate lease management command."
        )
    # Disabling allocation must leave explicit cleanup available. Other command,
    # environment, deadline or provider changes require ownership reconciliation.
    identity = canonical_identity(replace(config, enabled=True).to_dict()).uri
    if identity != record["config_identity"]:
        refuse(
            "config_changed", "Lease management must use the allocation configuration."
        )
    return config, child


def manage_lease(
    config_path, state, worker_id, environment, *, operation, expired_only=False
):
    if operation not in ("observe", "release") or (
        expired_only and operation != "release"
    ):
        raise ValueError("invalid lease management operation")
    path = operation_path(state, worker_id)
    with exclusive_cache_lock(path.with_suffix(".lock")):
        record = read_record(path)
        if record["status"] == "released":
            _unregister_owned(record)
            return record
        config, child = _configuration(config_path, environment, record)
        previous = record.get("management")
        release = previous["release_request"] if previous else None
        if expired_only and release is None:
            response = previous["response"] if previous else None
            if (
                previous is None
                or previous["state"] != "complete"
                or response["status"] != "ready"
                or _expiry(response["expires_at"]) > datetime.now(UTC)
            ):
                refuse(
                    "lease_not_expired",
                    "No observed expired lease is available for cleanup.",
                )
        request = (
            release
            if operation == "release" and release is not None
            else {
                "schema": REQUEST_SCHEMA,
                "operation": operation,
                "nonce": secrets.token_hex(32),
                "provision_request_identity": record["request_identity"],
                "request_id": record["request"]["request_id"],
                "worker_id": record["request"]["worker_id"],
                "lease_id": record["response"]["lease_id"]
                if record["response"]
                else None,
            }
        )
        if operation == "release":
            release = request
            record["status"] = "releasing"
        record["management"] = {
            "schema": JOURNAL_SCHEMA,
            "state": "pending",
            "request": request,
            "response": None,
            "release_request": release,
        }
        write_private(path, record, limit=3 * LIMIT)
        if operation == "release":
            # Stop future selections before asking the provider to terminate it.
            # A crash here retains the exact release request for an idempotent retry.
            _unregister_owned(record)
        output = invoke(
            replace(config, command=config.management_command), child, request=request
        )
        response = _response(json.loads(output), request, record)
        current = WorkerProvisioner.from_dict(read_private(config_path))
        if replace(current, enabled=True) != replace(config, enabled=True):
            refuse("config_changed", "Lease configuration changed during management.")
        if response["status"] == "ready":
            record["response"] = response["provision_response"]
            if release is None and record["status"] != "registered":
                record["status"] = "ready"
        elif response["status"] == "released":
            record["status"] = "released"
        elif release is None:
            record["status"] = "uncertain"
        record["management"].update(state="complete", response=response)
        write_private(path, record, limit=3 * LIMIT)
        if (
            release is not None
            or response["status"] in ("pending", "absent", "released")
            or (
                response["status"] == "ready"
                and _expiry(response["expires_at"]) <= datetime.now(UTC)
            )
        ):
            _unregister_owned(record)
        return record
