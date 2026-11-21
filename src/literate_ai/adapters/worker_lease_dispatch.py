"""Durable, single-attempt admission for an exact managed SSH registration."""

from __future__ import annotations

import os
import secrets
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from literate_ai._cache_lock import CacheLockError, exclusive_cache_lock
from literate_ai.contracts import (
    DispatchResultStatus,
    LifecycleDispatchAction,
    RemoteEvidenceCustodyReceipt,
    coordinator_evidence_import_identity,
    remote_cleanup_acknowledgement_identity,
)
from literate_ai.contracts._validation import contract_fields, string_value
from literate_ai.contracts.identity import ContentIdentity, canonical_identity

from .builders._process import remote_cleanup_wait_seconds
from .execution_dispatch import ExecutionDispatchAdapterError
from .ssh_execution import SshLifecycleRequestHandler
from .worker_lease_management import (
    _configuration,
    _expiry,
    _management_request,
    _set_management_intent,
    manage_lease,
)
from .worker_provisioning import (
    LIMIT,
    operation_path,
    read_record,
    refuse,
    registered_worker,
    require_deadline,
    write_private,
)
from .worker_registry import read_registry

SCHEMA = "literate-ai/worker-lease-dispatch@1"
COMPLETION_SCHEMA = "literate-ai/worker-terminal-run-completion@1"


def _validate_completion(record, dispatch):
    completion = contract_fields(
        dispatch["completion"],
        path="WorkerTerminalRunCompletion",
        schema_uri=COMPLETION_SCHEMA,
        required=frozenset(
            {
                "identity",
                "attempt",
                "request_identity",
                "worker_identity",
                "outcome",
                "exit_status",
                "result_evidence_identity",
                "custody_receipt_identity",
                "manifest_identity",
                "bundle_identity",
                "coordinator_store_identity",
                "cleanup_acknowledgement_identity",
                "store_path",
                "release_request_identity",
            }
        ),
    )
    if (
        dispatch.get("terminal_release") is not True
        or dispatch["state"] not in ("complete", "released")
        or dispatch["cancellation_requested"]
        or record["status"] not in ("releasing", "released")
        or not record.get("management", {}).get("release_request")
        or any(
            completion[key] != dispatch[key]
            for key in ("attempt", "request_identity", "worker_identity")
        )
        or completion["outcome"]
        not in tuple(value.value for value in DispatchResultStatus)
        or (
            completion["exit_status"] is not None
            and type(completion["exit_status"]) is not int
        )
        or not Path(
            string_value(completion["store_path"], "store_path", max_length=4096)
        ).is_absolute()
    ):
        refuse("completion_invalid", "Terminal completion differs from its attempt.")
    for key in (
        "identity",
        "request_identity",
        "worker_identity",
        "result_evidence_identity",
        "custody_receipt_identity",
        "manifest_identity",
        "bundle_identity",
        "coordinator_store_identity",
        "cleanup_acknowledgement_identity",
        "release_request_identity",
    ):
        ContentIdentity.parse_uri(completion[key])
    if (
        completion["identity"]
        != canonical_identity(
            {key: value for key, value in completion.items() if key != "identity"}
        ).uri
    ):
        refuse("completion_invalid", "Terminal completion identity changed.")
    if (
        completion["release_request_identity"]
        != canonical_identity(record["management"]["release_request"]).uri
    ):
        refuse("completion_invalid", "Terminal completion's release request changed.")


def require_terminal_completion(record, attempt, identity):
    dispatch = record.get("dispatch", {})
    if (
        dispatch.get("attempt") != attempt
        or dispatch.get("completion", {}).get("identity") != identity
        or dispatch.get("cancellation_requested")
    ):
        refuse("dispatch_changed", "Terminal release requires its original completion.")


def _terminal_receipt(manifest, bundle_identity):
    """Derive the same RUN custody binding at capture and recovery."""
    if manifest.action != "run" or manifest.artifact_identity is not None:
        raise ValueError("Terminal release requires RUN evidence without an artifact")
    files = tuple(
        sorted({item.identity for item in manifest.files}, key=lambda item: item.uri)
    )
    return RemoteEvidenceCustodyReceipt(
        manifest.request_identity,
        manifest.worker_identity,
        manifest.identity,
        bundle_identity,
        coordinator_evidence_import_identity(
            manifest_identity=manifest.identity,
            bundle_identity=bundle_identity,
            file_identities=files,
        ),
        files,
        None,
        remote_cleanup_acknowledgement_identity(
            request_identity=manifest.request_identity,
            manifest_identity=manifest.identity,
            bundle_identity=bundle_identity,
            cleanup_token=manifest.cleanup_token,
        ),
    )


def require_terminal_custody(record, *, deadline_monotonic):
    from .remote_execution import (
        RemoteExecutionError,
        verify_imported_remote_evidence_store,
    )

    completion = record["dispatch"]["completion"]
    try:
        manifest, store, files = verify_imported_remote_evidence_store(
            Path(completion["store_path"]),
            manifest_identity=ContentIdentity.parse_uri(
                completion["manifest_identity"]
            ),
            bundle_identity=ContentIdentity.parse_uri(completion["bundle_identity"]),
            deadline_monotonic=deadline_monotonic,
        )
        receipt = _terminal_receipt(
            manifest, ContentIdentity.parse_uri(completion["bundle_identity"])
        )
        if (
            manifest.request_identity.uri != completion["request_identity"]
            or manifest.worker_identity.uri != completion["worker_identity"]
            or manifest.outcome != completion["outcome"]
            or manifest.result_evidence_identity.uri
            != completion["result_evidence_identity"]
            or store.uri != completion["coordinator_store_identity"]
            or receipt.identity.uri != completion["custody_receipt_identity"]
            or receipt.cleanup_acknowledgement_identity.uri
            != completion["cleanup_acknowledgement_identity"]
            or receipt.coordinator_store_identity != store
            or receipt.imported_file_identities != files
        ):
            raise ValueError
    except (RemoteExecutionError, OSError, ValueError):
        refuse(
            "completion_custody_unavailable",
            "Current RUN evidence changed or exceeded its verification budget; "
            "release remains pending.",
        )


class TerminalManagedRunRelease:
    """One explicit RUN/cache-disposal request, not a reusable allocation policy."""

    def __init__(self, timeout_seconds):
        self.started_monotonic = time.monotonic()
        self.observed_at = datetime.now(UTC)
        self.deadline_monotonic = self.started_monotonic + timeout_seconds
        self.attempt = None
        self.completion = None
        self.saved = False

    def bind(self, config_path, state, worker, request, environment, attempt):
        if (
            self.attempt is not None
            or request.action is not LifecycleDispatchAction.RUN
        ):
            refuse("completion_invalid", "Terminal release requires one exact RUN.")
        self.config_path, self.state = config_path, state
        self.worker, self.request = worker, request
        self.environment = dict(environment)
        self.attempt = attempt

    def capture(self, worker, request, result, *, cwd):
        receipt, manifest, reference = (
            result.custody_receipt,
            result.evidence_manifest,
            result.evidence_reference,
        )
        if (
            self.attempt is None
            or self.completion is not None
            or receipt is None
            or manifest is None
            or reference is None
        ):
            refuse(
                "completion_custody_missing",
                "Terminal release requires imported RUN evidence.",
            )
        try:
            expected_receipt = _terminal_receipt(manifest, reference.identity)
        except ValueError:
            refuse(
                "completion_custody_invalid", "Terminal release requires RUN custody."
            )
        if (
            worker != self.worker
            or request != self.request
            or receipt.request_identity != request.identity
            or receipt.worker_identity != worker.identity
            or manifest.request_identity != request.identity
            or manifest.worker_identity != worker.identity
            or manifest.authority_identity != request.authority_identity
            or manifest.action != "run"
            or manifest.outcome != result.status.value
            or manifest.result_evidence_identity != result.evidence_identity
            or manifest.artifact_identity is not None
            or receipt != expected_receipt
        ):
            refuse(
                "completion_custody_invalid",
                "Terminal release requires exact verified RUN custody.",
            )
        obj = Path(os.environ.get("OBJ_DIR", str(Path(cwd) / "_build")))
        if not obj.is_absolute():
            obj = Path(cwd) / obj
        store = obj.resolve() / "remote-evidence-cas"
        value = {
            "schema": COMPLETION_SCHEMA,
            "attempt": self.attempt,
            "request_identity": request.identity.uri,
            "worker_identity": worker.identity.uri,
            "outcome": result.status.value,
            "exit_status": result.exit_status,
            "result_evidence_identity": result.evidence_identity.uri,
            "custody_receipt_identity": receipt.identity.uri,
            "manifest_identity": manifest.identity.uri,
            "bundle_identity": reference.identity.uri,
            "coordinator_store_identity": receipt.coordinator_store_identity.uri,
            "cleanup_acknowledgement_identity": (
                receipt.cleanup_acknowledgement_identity.uri
            ),
            "store_path": str(store),
        }
        self.completion = {**value, "identity": canonical_identity(value).uri}

    def stage(self, record, attempt):
        if self.attempt != attempt or self.completion is None:
            refuse(
                "completion_custody_missing", "Terminal RUN has no verified completion."
            )
        release = _management_request(record, "release")
        value = {
            key: value for key, value in self.completion.items() if key != "identity"
        }
        value["release_request_identity"] = canonical_identity(release).uri
        self.completion = {**value, "identity": canonical_identity(value).uri}
        record["dispatch"].update(state="complete", completion=self.completion)
        _set_management_intent(record, release)

    def release(self):
        if not self.saved or self.completion is None:
            refuse(
                "completion_custody_missing",
                "Terminal completion was not durably saved.",
            )
        try:
            record = manage_lease(
                self.config_path,
                self.state,
                self.worker.worker_id,
                self.environment,
                operation="release",
                deadline_monotonic=self.deadline_monotonic,
                completion_attempt=self.attempt,
                completion_identity=self.completion["identity"],
            )
        except ExecutionDispatchAdapterError:
            raise
        except (OSError, ValueError, CacheLockError):
            refuse(
                "cleanup_pending",
                "RUN outcome is retained; inspect status and recover "
                "its pending release.",
            )
        if record["status"] != "released":
            refuse(
                "cleanup_pending",
                "RUN outcome is retained; provider release remains pending.",
            )


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
        optional=frozenset({"terminal_release", "completion"}),
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
    if "terminal_release" in dispatch and dispatch["terminal_release"] is not True:
        refuse("dispatch_invalid", "Terminal release requires explicit authorization.")
    if "completion" in dispatch:
        _validate_completion(record, dispatch)


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
def admitted_lease_dispatch(
    config_path, state, worker, request, environment, *, terminal_release=None
):
    """No timeout or controller crash silently forgets a possibly running job."""
    path = operation_path(state, worker.worker_id)
    lock = path.with_suffix(".lock")
    started, observed_at = time.monotonic(), datetime.now(UTC)
    operation_end = (
        None if terminal_release is None else terminal_release.deadline_monotonic
    )
    timing = {} if operation_end is None else {"deadline_monotonic": operation_end}
    cleanup = SshLifecycleRequestHandler.cleanup_wait_seconds()
    if terminal_release is not None:
        if request.action is not LifecycleDispatchAction.RUN:
            refuse("completion_invalid", "Terminal release is supported only for RUN.")
        started, observed_at = (
            terminal_release.started_monotonic,
            terminal_release.observed_at,
        )
        cleanup = max(cleanup, remote_cleanup_wait_seconds(has_stdin_writer=True))

    def reserved_end():
        remaining = (
            request.timeout_seconds
            if operation_end is None
            else max(0.0, operation_end - time.monotonic())
        )
        return current_time() + timedelta(seconds=remaining + cleanup)

    def current_time():
        # A backward wall-clock step during lookup/execution cannot extend TTL.
        return max(
            datetime.now(UTC),
            observed_at + timedelta(seconds=time.monotonic() - started),
        )

    with exclusive_cache_lock(lock, **timing):
        _available(read_record(path), worker)
    # This is lookup only, never allocation. A second locked admission checks
    # concurrent observation, release or dispatch after the provider reply.
    manage_lease(
        config_path, state, worker.worker_id, environment, operation="observe", **timing
    )
    with exclusive_cache_lock(lock, **timing):
        record = read_record(path)
        _available(record, worker)
        config, _child = _configuration(config_path, environment, record)
        management = record.get("management")
        response = management["response"] if management else None
        deadline = reserved_end()
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
        if terminal_release is not None:
            terminal_release.bind(
                config_path, state, worker, request, environment, attempt
            )
        record["dispatch"] = dict(
            schema=SCHEMA,
            attempt=attempt,
            request_identity=request.identity.uri,
            worker_identity=worker.identity.uri,
            deadline_at=response["expires_at"],
            state="active",
            cancellation_requested=False,
            **({} if terminal_release is None else {"terminal_release": True}),
        )
        write_private(path, record, limit=3 * LIMIT)
        expires_at = _expiry(response["expires_at"])
        # fsync/publication is outside the handler's execution deadline. Never
        # start its fresh whole timeout if that work consumed the lease headroom.
        execution_deadline = (
            time.monotonic() + request.timeout_seconds
            if operation_end is None
            else operation_end - cleanup - config.timeout_seconds
        )
        deadline = reserved_end()
        if deadline >= expires_at or (
            operation_end is not None and time.monotonic() >= execution_deadline
        ):
            record["dispatch"]["state"] = "not-started"
            write_private(path, record, limit=3 * LIMIT)
            refuse(
                "lease_deadline_insufficient",
                "Lease headroom was consumed before launch.",
            )
    complete = False
    try:
        yield execution_deadline
        require_deadline(operation_end)
        if current_time() >= min(deadline, expires_at):
            refuse(
                "dispatch_deadline_exceeded",
                "Managed dispatch exceeded its lease deadline.",
            )
        complete = True
    finally:
        try:
            with exclusive_cache_lock(lock, **timing):
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
                    if complete and terminal_release is not None:
                        terminal_release.stage(record, attempt)
                    write_private(path, record, limit=3 * LIMIT)
                    if complete and terminal_release is not None:
                        terminal_release.saved = True
                        require_deadline(operation_end)
        except CacheLockError:
            # An expired opt-in may be unable to mark uncertainty. Its already
            # durable active attempt still fences retry; never mask the original
            # failure or launch another management command to repair it here.
            if terminal_release is None:
                raise
            if complete:
                refuse(
                    "cleanup_pending",
                    "RUN result was collected; its attempt remains fenced "
                    "pending journal recovery.",
                )
