"""One original root's candidate accounting, never execution authorization.

The runtime controller must independently establish native rejection custody and
execute the complete lifecycle. This sequence only constrains its allocations
and retains the exact closed attempt prefix; records cannot reopen a sequence.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from threading import Lock
from types import MethodType

from literate_ai.application.native_root_run import (
    LiveNativeRootRun,
    NativeRootRunError,
)
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_root_continuation import (
    NativeRootCandidateAttempt,
    NativeRootContinuationLedger,
    NativeRootContinuationStop,
    NativeRootQualifiedDependencyBinding,
    NativeRootRunBinding,
)


class LiveNativeRootCandidateSequence:
    """A finite allocation constraint owned by one live command and controller."""

    def __init__(self):
        raise TypeError("candidate sequences come from their original live run")

    def __copy__(self):
        raise TypeError("a live candidate sequence cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("a live candidate sequence cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("a live candidate sequence cannot be serialized")

    def _require_owner(self) -> None:
        if self._seal is not self or self._pid != os.getpid():
            raise NativeRootRunError("candidate_sequence_closed")

    def _require_data(self) -> None:
        if not self._active:
            raise NativeRootRunError("candidate_sequence_closed")
        if (
            self._run is not self._original_run
            or self._binding is not self._original_binding
            or self._current is not self._original_current
            or self._binding.identity.uri != self._original_binding_uri
            or tuple(entry.identity.uri for entry in self._attempts)
            != self._original_attempt_uris
            or (None if self._stop is None else self._stop.identity.uri)
            != self._original_stop_uri
        ):
            raise NativeRootRunError("candidate_sequence_changed")

    def require_scope_pairing(self, scope) -> None:
        """Check original callback custody without invoking the backend guard."""
        self._require_owner()
        try:
            with self._lock:
                self._require_data()
                current = self._original_current
                original_run = self._original_run
                original_binding = self._original_binding
            # Properties and metaclass descriptors can execute foreign Python.
            # Snapshot them without holding this sequence's private lock.
            scope_function = getattr(type(scope), "require_current", None)
            scope_run = scope.original_run
            scope_binding = scope.run_binding
            with self._lock:
                self._require_data()
                if (
                    self._original_current is not current
                    or self._original_run is not original_run
                    or self._original_binding is not original_binding
                    or type(current) is not MethodType
                    or current.__self__ is not scope
                    or current.__func__ is not scope_function
                    or original_run is not scope_run
                    or original_binding is not scope_binding
                ):
                    raise NativeRootRunError("candidate_sequence_changed")
        except BaseException:
            self.close()
            raise

    def require_current(self) -> None:
        self._require_owner()
        try:
            with self._lock:
                self._require_data()
                current = self._current
                original_run = self._original_run
            original_run.require_current()
            current()
            original_run.require_current()
            with self._lock:
                self._require_data()
        except BaseException:
            self.close()
            raise

    @property
    def attempts(self) -> tuple[NativeRootCandidateAttempt, ...]:
        self.require_current()
        with self._lock:
            self._require_data()
            return self._attempts

    @property
    def consumed_candidates(self) -> int:
        self.require_current()
        with self._lock:
            self._require_data()
            return len(self._attempts) + int(self._pending is not None)

    def require_allocation_available(self) -> None:
        """Call before preparing a replacement or allocating its workspace."""
        self.require_current()
        with self._lock:
            self._require_allocation_available()

    def _require_allocation_available(self) -> None:
        self._require_data()
        if (
            self._pending is not None
            or self._stop is not None
            or len(self._attempts) >= self._binding.candidate_limit
            or (self._attempts and self._attempts[-1].retryability != "retryable")
        ):
            raise NativeRootRunError("candidate_budget_unavailable")

    def register_allocated_candidate(
        self,
        request: ContentIdentity,
        workspace: ContentIdentity,
        *,
        incoming_request_kind: str,
        incoming_request_identity: ContentIdentity | None,
    ) -> int:
        """Observe actual prepared identities; create neither request nor workspace."""
        self.require_allocation_available()
        with self._lock:
            self._require_allocation_available()
            if (
                type(request) is not ContentIdentity
                or type(workspace) is not ContentIdentity
            ):
                raise TypeError(
                    "actual prepared request and workspace identities required"
                )
            request.__post_init__()
            workspace.__post_init__()
            ordinal = len(self._attempts)
            if (
                (
                    ordinal == 0
                    and request != self._binding.original_bounded_request_identity
                )
                or (ordinal == 0) != (incoming_request_kind == "initial")
                or (ordinal == 0) != (incoming_request_identity is None)
                or incoming_request_kind
                not in {"initial", "legacy-node-repair", "native-root-repair"}
                or any(
                    request == entry.bounded_generation_request_identity
                    or workspace == entry.workspace_allocation_identity
                    for entry in self._attempts
                )
            ):
                raise NativeRootRunError("candidate_allocation_changed")
            if incoming_request_identity is not None:
                if type(incoming_request_identity) is not ContentIdentity:
                    raise TypeError(
                        "incoming request identity must be a ContentIdentity"
                    )
                incoming_request_identity.__post_init__()
            self._pending = (
                request.uri,
                workspace.uri,
                incoming_request_kind,
                None
                if incoming_request_identity is None
                else incoming_request_identity.uri,
            )
            return ordinal

    def record_attempt(self, attempt: NativeRootCandidateAttempt) -> None:
        self.require_current()
        with self._lock:
            self._require_data()
            if type(attempt) is not NativeRootCandidateAttempt:
                raise TypeError("actual closed root attempt required")
            attempt.__post_init__()
            if self._pending is None or self._pending != (
                attempt.bounded_generation_request_identity.uri,
                attempt.workspace_allocation_identity.uri,
                attempt.incoming_request_kind,
                None
                if attempt.incoming_request_identity is None
                else attempt.incoming_request_identity.uri,
            ):
                raise NativeRootRunError("candidate_observation_changed")
            entries = (*self._attempts, attempt)
            # The closed ledger independently checks ordinal, exact predecessors,
            # freshness and terminal/exhausted/accepted interpretation.
            ledger = self._ledger(entries, None)
            if ledger.attempts[0].bounded_generation_request_identity != (
                self._binding.original_bounded_request_identity
            ):
                raise NativeRootRunError("candidate_observation_changed")
            self._attempts = entries
            self._original_attempt_uris = tuple(entry.identity.uri for entry in entries)
            self._pending = None
        self.require_current()

    def record_preparation_stop(self, stop: NativeRootContinuationStop) -> None:
        self.require_allocation_available()
        with self._lock:
            self._require_allocation_available()
            if type(stop) is not NativeRootContinuationStop:
                raise TypeError("actual preparation stop required")
            stop.require_prefix(self._binding.identity, self._attempts)
            self._stop = stop

            self._original_stop_uri = stop.identity.uri

    def ledger(self) -> NativeRootContinuationLedger:
        self.require_current()
        with self._lock:
            self._require_data()
            if self._pending is not None:
                raise NativeRootRunError("candidate_observation_required")
            return self._ledger(self._attempts, self._stop)

    def _ledger(self, entries, stop):
        disposition = (
            "terminal"
            if stop is not None
            else "pending"
            if not entries
            else "accepted"
            if entries[-1].outcome == "root-accepted"
            else "terminal"
            if entries[-1].retryability == "terminal"
            else "exhausted"
            if len(entries) == self._binding.candidate_limit
            else "pending"
        )
        return NativeRootContinuationLedger(
            self._binding.identity,
            entries,
            tuple(
                sorted(
                    {
                        entry.legacy_node_chain_identity
                        for entry in entries
                        if entry.legacy_node_chain_identity is not None
                    },
                    key=lambda identity: identity.uri,
                )
            ),
            disposition,
            None if stop is None else stop.identity,
        )

    def close(self) -> None:
        if self._seal is self and self._pid == os.getpid():
            with self._lock:
                self._active = False
                self._current = None


@contextmanager
def open_native_root_candidate_sequence(
    original_run: LiveNativeRootRun,
    run_binding: NativeRootRunBinding,
    *,
    project_authority_identity: ContentIdentity,
    require_current: Callable[[], None],
    qualified_dependencies: tuple[NativeRootQualifiedDependencyBinding, ...] = (),
) -> Iterator[LiveNativeRootCandidateSequence]:
    """Claim one nonrenewable counter; typed records grant no execution rights."""
    if type(original_run) is not LiveNativeRootRun:
        raise TypeError("original live run required")
    if type(run_binding) is not NativeRootRunBinding or not callable(require_current):
        raise TypeError("exact run binding and current authority callback required")
    if type(project_authority_identity) is not ContentIdentity:
        raise TypeError("actual approved project authority identity required")
    run_binding.__post_init__()
    project_authority_identity.__post_init__()
    original_binding_uri = run_binding.identity.uri
    original_authority_uri = project_authority_identity.uri
    original_root = ContentIdentity.parse_uri(run_binding.root_revision.uri)
    original_run.require_current()
    definition, framework, policy = original_run.bindings
    run_binding.require_records(
        original_run.policy,
        original_run.deadline,
        qualified_dependencies,
        project_definition_identity=definition,
        project_authority_identity=project_authority_identity,
    )
    if (
        run_binding.framework_distribution_identity != framework
        or run_binding.lifecycle_policy_identity != policy
    ):
        raise NativeRootRunError("binding_changed")
    require_current()
    if (
        run_binding.identity.uri != original_binding_uri
        or project_authority_identity.uri != original_authority_uri
    ):
        raise NativeRootRunError("binding_changed")
    original_run._claim_root_sequence(original_root)
    sequence = object.__new__(LiveNativeRootCandidateSequence)
    sequence._seal = sequence
    sequence._pid = os.getpid()
    sequence._active = True
    sequence._lock = Lock()
    sequence._run = original_run
    sequence._original_run = original_run
    sequence._binding = run_binding
    sequence._original_binding = run_binding
    sequence._original_binding_uri = original_binding_uri
    sequence._attempts = ()
    sequence._original_attempt_uris = ()
    sequence._pending = None
    sequence._stop = None
    sequence._original_stop_uri = None
    sequence._current = require_current
    sequence._original_current = require_current
    try:
        sequence.require_current()
        yield sequence
    finally:
        sequence.close()
