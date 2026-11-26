"""One original candidate controller through independent packaged acceptance.

Each private pipeline pass runs exactly one candidate. The same controller,
allocation sequence, runtime ports, admitted action pool and original deadline
survive replacements; the legacy node retry loop is not nested inside this one.
The filesystem backend owns native observation and current physical custody.
"""

from __future__ import annotations

from contextlib import ExitStack
from contextvars import ContextVar
from dataclasses import dataclass, replace

from literate_ai.application.native_root_candidate_sequence import (
    LiveNativeRootCandidateSequence,
    open_native_root_candidate_sequence,
)
from literate_ai.application.native_root_run import NativeRootRunError
from literate_ai.contracts.executable_components import (
    CandidateFailureClassification,
    CandidateRepairDiagnostic,
)
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_root_continuation import (
    NATIVE_ROOT_REPAIR_MESSAGE,
    NATIVE_ROOT_RESULT_MISMATCH,
    NativeRootAcceptanceClosure,
    NativeRootCandidateAttempt,
    NativeRootContinuationStop,
    NativeRootExecutionResult,
    NativeRootPackageBinding,
    NativeRootRepairDiagnostic,
)
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailureEvidence,
    StandardNodeFailurePhase,
)

_ACTIVE: ContextVar[NativeRootController | None] = ContextVar(
    "native_root_controller", default=None
)


class NativeRootPackageRejected(RuntimeError):
    """Correlation to a held original outcome, never rejection authority itself."""

    def __init__(
        self, controller, observation_identity: ContentIdentity, original_error=None
    ):
        self.controller = controller
        self.observation_identity = observation_identity
        self.original_error = original_error
        self.code = NATIVE_ROOT_RESULT_MISMATCH
        super().__init__(self.code)


@dataclass(frozen=True)
class _NativeObservation:
    outcome: object
    plan: object
    source_generation: object
    output: object
    acceptance_evidence: object
    scope: str
    identity: ContentIdentity


def current_native_root_controller() -> NativeRootController | None:
    return _ACTIVE.get()


def _note_refusal(error: BaseException, message: str) -> None:
    # Annotation must never replace the terminal error it is meant to preserve.
    try:
        BaseException.add_note(error, message)
    except Exception:
        pass


class NativeRootController:
    """Application owner; only its original backend can seal native rejection."""

    def __init__(self, scope, repair_port, sequence, start_replacement=None):
        self.scope = scope
        self.repair_port = repair_port
        self.sequence = sequence
        self._original_scope = scope
        self._original_sequence = sequence
        self._require_pairing()
        self._close_original_scope = scope.close
        self.prepared_candidate = scope.prepared_root
        self._contexts = ExitStack()
        self.node_observation = None
        self.package_binding = None
        self._native = None
        self._incoming = None
        self._closure = None
        self._accepted_ledger = None
        self._registered = False
        self._issued_failed_stage_diagnostic = None
        self._original_issued_failed_stage_diagnostic = None
        self._start_replacement = start_replacement

    @property
    def contexts(self):
        return self._contexts

    def _require_pairing(self):
        if (
            self.scope is not self._original_scope
            or self.sequence is not self._original_sequence
            or type(self.sequence) is not LiveNativeRootCandidateSequence
        ):
            if type(self._original_sequence) is LiveNativeRootCandidateSequence:
                self._original_sequence.close()
            raise NativeRootRunError("candidate_sequence_changed")
        self.sequence.require_scope_pairing(self.scope)

    def require_current(self):
        try:
            self._require_pairing()
            # The sealed sequence calls this scope's original guard freshly, once.
            self.sequence.require_current()
            self._require_pairing()
        except BaseException as error:
            # Sequence checks can reject before the backend callback runs. Retire
            # the original scope too, without another scan or a foreign owner.
            try:
                self._close_original_scope()
            except BaseException:
                _note_refusal(error, "native root scope cleanup failed")
            raise

    def observe_node(self, prepared, generation, plan, result):
        self.require_current()
        if prepared is not self.prepared_candidate:
            raise ValueError("root node differs from its actual allocated candidate")
        self.node_observation = generation, plan, result

    def observe_native_outcome(
        self,
        outcome,
        *,
        plan,
        source_generation,
        output,
        acceptance_evidence,
        acceptance_scope,
    ):
        """Keep the actual holder for later joining to a completed node record.

        This does not classify an exception or grant a replacement. The original
        backend must independently consume and seal the exact holder later.
        """
        self.require_current()
        outcome.require_current(self.scope.original_run, self.scope.continuation_owner)
        if outcome.values_differ is False:
            return None
        if outcome.values_differ is not True or self._native is not None:
            raise ValueError("ambiguous native outcome cannot authorize repair")
        if acceptance_scope not in {"node-native-precheck", "packaged-root"}:
            raise ValueError("unknown native acceptance scope")
        if acceptance_scope == "packaged-root" and self.package_binding is None:
            raise ValueError("native package rejection has no actual package binding")
        identity = self.scope.retain_record(outcome.observation)
        self._native = _NativeObservation(
            outcome,
            plan,
            source_generation,
            output,
            acceptance_evidence,
            acceptance_scope,
            identity,
        )
        return identity

    def _retain_node(self, result):
        if result.source_output is not None:
            self.scope.retain_record(result.source_output)
        if result.failure_evidence is not None:
            self.scope.retain_record(result.failure_evidence)
        membership = result.source_cache_membership
        if membership is not None:
            identity = membership.identity
            if (
                self.scope.retain_record(membership) != identity
                or result.source_cache_membership is not membership
                or membership.identity != identity
            ):
                raise NativeRootRunError("membership_record_changed")
        self.scope.retain_record(result.identity_document())

    def _record_attempt(self, result, outcome, failure, diagnostic, retryability):
        if result is not None:
            self._retain_node(result)
        source = None if result is None else result.source_output
        attempt = NativeRootCandidateAttempt(
            self.scope.run_binding.identity,
            len(self.sequence.attempts),
            tuple(a.identity for a in self.sequence.attempts),
            "initial" if self._incoming is None else "native-root-repair",
            None if self._incoming is None else self._incoming.identity,
            self.prepared_candidate.request.request.identity,
            self.prepared_candidate.workspace.allocation_identity,
            None if source is None else source.identity,
            None if source is None else result.identity,
            None,
            None,
            outcome,
            None if failure is None else failure.identity,
            None if diagnostic is None else diagnostic.identity,
            retryability,
            None,
            self.package_binding
            if outcome in {"package-rejected", "root-terminal"}
            else None,
        )
        self.sequence.record_attempt(attempt)
        self._registered = False
        self.scope.retain_record(attempt)
        self.scope.retain_record(self.sequence.ledger())
        return attempt

    def _record_terminal_exception(self):
        """Retain an ordinary pipeline failure without reclassifying its node.

        This is evidence only: no diagnostic, native rejection or replacement
        is derived from the exception. A closed/expired authority cannot close
        a new ledger through this path.
        """
        if not self._registered or self._accepted_ledger is not None:
            return
        self.require_current()
        node = None if self.node_observation is None else self.node_observation[2]
        failure = StandardNodeFailureEvidence(
            self.scope.run_binding.root_revision,
            StandardNodeFailurePhase.LIFECYCLE,
            "native-root.root-stage-failed",
            (
                self.prepared_candidate.request.request.identity
                if node is None
                else node.identity
            ),
            "the original root pipeline did not complete",
        )
        self.scope.retain_record(failure)
        self._record_attempt(
            node,
            (
                "terminal-before-node"
                if node is None or node.source_output is None
                else "root-terminal"
            ),
            failure,
            None,
            "terminal",
        )

    def _seal_native(self, node):
        observed = self._native
        if observed is None:
            raise ValueError("no original native rejection is held")
        if observed.scope == "node-native-precheck" and (
            node.failure_evidence is None
            or node.failure_evidence.phase is not StandardNodeFailurePhase.ACCEPT
            or node.failure_evidence.subject_identity != observed.identity
        ):
            raise ValueError("native precheck differs from the actual node failure")
        original_contexts = self.contexts
        rejection = self.scope.seal_native_rejection(
            observed.outcome,
            candidate_ordinal=len(self.sequence.attempts),
            prepared_candidate=self.prepared_candidate,
            source_generation=observed.source_generation,
            output=observed.output,
            plan=observed.plan,
            node_result=node,
            acceptance_evidence=observed.acceptance_evidence,
            acceptance_scope=observed.scope,
            packaged_binding=self.package_binding,
        )
        # The original observation is fully joined, retained and consumed.
        # Run its genuine final guards now, before closed history bookkeeping
        # spends more of the same verifier operation's fixed lifetime.
        original_contexts.close()
        self.require_current()
        if self.contexts is not original_contexts:
            raise ValueError("native rejection changed its original verifier contexts")
        diagnostic = NativeRootRepairDiagnostic(
            self.scope.run_binding.root_revision,
            rejection.identity,
            NATIVE_ROOT_RESULT_MISMATCH,
            "retryable",
            NATIVE_ROOT_REPAIR_MESSAGE,
        )
        self.scope.retain_record(diagnostic)
        return rejection, diagnostic

    def close_accepted_root(self, integration):
        """Close native contexts before a success ledger can reach publication."""
        self.require_current()
        if self._native is not None or self.node_observation is None:
            raise ValueError("rejected or unobserved root cannot close acceptance")
        generation, plan, node = self.node_observation
        if node.failure_evidence is not None or self.package_binding is None:
            raise ValueError("incomplete root cannot close acceptance")
        actual_package = NativeRootPackageBinding(
            integration.artifact_graph.identity,
            integration.link_plan.identity,
            integration.package_plan.identity,
            integration.package_result.identity,
            integration.root_generated_integration_test_identity,
            integration.packaged_execution_identity,
        )
        if self.package_binding != actual_package:
            raise ValueError("root acceptance changed its actual package coordinates")
        self.scope.require_generated_source(
            self.prepared_candidate, generation, node.source_output
        )
        self.contexts.close()
        if self.package_binding != actual_package:
            raise ValueError("native closure changed actual package coordinates")
        # Independent acceptance may add original process/summary records after
        # the pre-native package snapshot. Native contexts must close first;
        # durable data capture must finish before an accepted ledger can exist.
        self.scope._snapshot_recorded_evidence(
            required_identities=(integration.independent_acceptance_identity,)
        )
        self.scope.retain_record(integration)
        self._retain_node(node)
        attempt = NativeRootCandidateAttempt(
            self.scope.run_binding.identity,
            len(self.sequence.attempts),
            tuple(a.identity for a in self.sequence.attempts),
            "initial" if self._incoming is None else "native-root-repair",
            None if self._incoming is None else self._incoming.identity,
            self.prepared_candidate.request.request.identity,
            self.prepared_candidate.workspace.allocation_identity,
            node.source_output.identity,
            node.identity,
            None,
            None,
            "root-accepted",
            None,
            None,
            "none",
            integration.independent_acceptance_identity,
            self.package_binding,
        )
        self.sequence.record_attempt(attempt)
        self._registered = False
        ledger = self.sequence.ledger()
        closure = NativeRootAcceptanceClosure(
            self.scope.run_binding.identity,
            ledger.identity,
            integration.independent_acceptance_identity,
            node.source_output.identity,
            integration.package_plan.identity,
            integration.package_result.identity,
        )
        closure.require_records(self.scope.run_binding, ledger)
        for record in (attempt, ledger, closure):
            self.scope.retain_record(record)
        self.require_current()
        self._closure, self._accepted_ledger = closure, ledger
        return replace(integration, independent_acceptance_identity=closure.identity)

    def _prepare_next(self, diagnostic, rejection):
        self.contexts.close()
        self.require_current()
        self.sequence.require_allocation_available()
        try:
            prepared, request = self.repair_port.prepare_root_repair(
                self.scope.prepared_root,
                self.scope.run_binding,
                self.sequence.attempts,
                diagnostic,
                live_run=self.scope.original_run,
                project_authority_identity=(
                    self.scope.run_binding.project_authority_identity
                ),
                execution_plan_identity=self.scope.run_binding.execution_plan_identity,
                rejection=rejection,
            )
        except BaseException as error:
            # Allocated failures carry actual partial identities. They are not
            # no-allocation stops and must remain available to forensic callers.
            if getattr(error, "native_root_repair_allocation", None) is not None:
                raise
            if isinstance(error, Exception):
                failure = StandardNodeFailureEvidence(
                    self.scope.run_binding.root_revision,
                    StandardNodeFailurePhase.LIFECYCLE,
                    "native-root.repair-preparation-failed",
                    self.sequence.attempts[-1].identity,
                    "fresh root replacement preparation did not complete",
                )
                self.scope.retain_record(failure)
                stop = NativeRootContinuationStop(
                    self.scope.run_binding.identity,
                    len(self.sequence.attempts),
                    self.sequence.attempts[-1].identity,
                    failure.identity,
                    "prepare-repair",
                    "native-root.repair-preparation-failed",
                )
                self.sequence.record_preparation_stop(stop)
                self.scope.retain_record(stop)
                self.scope.retain_record(self.sequence.ledger())
            raise
        self.prepared_candidate, self._incoming = prepared, request
        # The allocated replacement has no observed source/node/package yet.
        # Clear the previous candidate before any registration, retention or
        # checkpoint callback can fail and trigger terminal accounting.
        self.node_observation = None
        self.package_binding = None
        self._native = None
        self._contexts = ExitStack()
        self._register_current_candidate()
        self.scope.retain_record(request)
        if self._start_replacement is not None:
            self._start_replacement()

    def _retain_current_preparation(self):
        from .native_root_preparation_retention import retain_native_root_preparation

        retain_native_root_preparation(self)

    def _register_current_candidate(self):
        self.sequence.register_allocated_candidate(
            self.prepared_candidate.request.request.identity,
            self.prepared_candidate.workspace.allocation_identity,
            incoming_request_kind=(
                "initial" if self._incoming is None else "native-root-repair"
            ),
            incoming_request_identity=(
                None if self._incoming is None else self._incoming.identity
            ),
        )
        self._registered = True
        self._retain_current_preparation()

    def _audit_result(self, result):
        ledger = self.sequence.ledger()
        for node in result.node_results:
            self._retain_node(node)
        root = result.root_integration
        if root is not None:
            identity = root.identity
            if (
                self.scope.retain_record(root) != identity
                or result.root_integration is not root
                or root.identity != identity
            ):
                raise NativeRootRunError("root_record_changed")
        self.scope.retain_record(result.identity_document())
        audit = NativeRootExecutionResult(
            self.scope.run_binding.identity,
            ledger.identity,
            result.identity,
            None if self._closure is None else self._closure.identity,
            ledger.disposition,
        )
        audit.require_records(self.scope.run_binding, ledger, closure=self._closure)
        self.scope.retain_record(audit)
        # Preserve the existing lifecycle@4 identity and receipt comparisons.
        return replace(result, native_root_execution=audit)

    def execute(self, pipeline):
        """Close ordinary failures across pipeline and replacement boundaries."""
        try:
            return self._execute(pipeline)
        except Exception as error:
            try:
                self._record_terminal_exception()
            except Exception:
                # Preserve the actual lifecycle error even when storage or
                # current authority also prevents closing its evidence.
                _note_refusal(error, "native root terminal evidence could not close")
            raise

    def _execute(self, pipeline):
        """Repeat one private full pipeline per actual globally counted candidate."""
        from .native_root_failed_stage import (
            diagnose_native_root_failed_stage,
            native_root_failed_stage_retryable,
        )

        while True:
            self.require_current()
            self._contexts = ExitStack()
            self.node_observation = None
            self.package_binding = None
            self._native = None
            self._issued_failed_stage_diagnostic = None
            self._original_issued_failed_stage_diagnostic = None
            if not self._registered:
                self._register_current_candidate()
            try:
                result = pipeline(self.prepared_candidate)
            except NativeRootPackageRejected as error:
                if (
                    error.controller is not self
                    or self._native is None
                    or self._native.scope != "packaged-root"
                    or error.observation_identity != self._native.identity
                    or self.node_observation is None
                ):
                    raise
                node = self.node_observation[2]
                rejection, diagnostic = self._seal_native(node)
                self._record_attempt(
                    node, "package-rejected", rejection, diagnostic, "retryable"
                )
                if self.sequence.ledger().disposition == "exhausted":
                    if error.original_error is not None:
                        raise error.original_error from error
                    raise
                self._prepare_next(diagnostic, rejection)
                continue
            if self._accepted_ledger is not None:
                return self._audit_result(result)
            node = next(
                node
                for node in result.node_results
                if node.component_revision == self.scope.run_binding.root_revision
            )
            failure = node.failure_evidence
            if failure is None:
                raise ValueError("root pipeline returned without packaged acceptance")
            diagnostic, rejection = None, None
            outcome = (
                "terminal-before-node"
                if node.source_output is None
                else "node-rejected"
            )
            if node.source_output is not None:
                self.scope.require_generated_source(
                    self.prepared_candidate, node.source_generation, node.source_output
                )
                if self._native is not None:
                    rejection, diagnostic = self._seal_native(node)
                    outcome = "native-precheck-rejected"
                elif (
                    failure.phase
                    in {
                        StandardNodeFailurePhase.BUILD,
                        StandardNodeFailurePhase.TEST,
                    }
                    and native_root_failed_stage_retryable(self, failure) is not False
                ):
                    diagnostic = diagnose_native_root_failed_stage(self, failure)
                    if diagnostic is None:
                        diagnostic = self.repair_port.diagnose(
                            failure, node.source_output
                        )
                    if (
                        type(diagnostic) is not CandidateRepairDiagnostic
                        or diagnostic.component_revision != failure.component_revision
                        or diagnostic.failure_evidence_identity != failure.identity
                        or diagnostic.phase is not failure.phase
                        or diagnostic.code != failure.code
                    ):
                        raise ValueError(
                            "root repair diagnostic changed actual failure"
                        )
                    self.scope.retain_record(diagnostic)
            retryable = rejection is not None or (
                diagnostic is not None
                and diagnostic.classification
                is CandidateFailureClassification.RETRYABLE
            )
            self._record_attempt(
                node,
                outcome,
                rejection or failure,
                diagnostic,
                "retryable" if retryable else "terminal",
            )
            if self.sequence.ledger().disposition in {"terminal", "exhausted"}:
                return self._audit_result(result)
            self._prepare_next(diagnostic, rejection)


def execute_native_root_continuation(
    scope, repair_port, pipeline, *, start_replacement=None
):
    """Keep one original root scope/counter around every private pipeline pass."""
    if _ACTIVE.get() is not None:
        raise ValueError("a root controller cannot be nested or renewed")
    with open_native_root_candidate_sequence(
        scope.original_run,
        scope.run_binding,
        project_authority_identity=scope.run_binding.project_authority_identity,
        require_current=scope.require_current,
        **(
            {"qualified_dependencies": scope.qualified_dependencies}
            if scope.run_binding.qualified_dependency_binding_identities
            else {}
        ),
    ) as sequence:
        controller = NativeRootController(
            scope, repair_port, sequence, start_replacement
        )
        token = _ACTIVE.set(controller)
        terminal_error = None
        try:
            scope.retain_record(scope.original_run.policy)
            scope.retain_record(scope.original_run.deadline)
            scope.retain_record(scope.run_binding)
            if scope.run_binding.qualified_dependency_binding_identities:
                for dependency in scope.qualified_dependencies:
                    scope.retain_record(dependency)
            return controller.execute(pipeline)
        except BaseException as error:
            terminal_error = error
            raise
        finally:
            try:
                try:
                    controller.contexts.close()
                except Exception:
                    if terminal_error is None:
                        # Cleanup is part of successful closure. Its refusal
                        # cannot be converted into a successful return.
                        raise
                    _note_refusal(
                        terminal_error,
                        "native root cleanup failed after terminal refusal",
                    )
            finally:
                _ACTIVE.reset(token)
