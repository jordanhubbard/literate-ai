"""Capture exact current-controller source history before candidate CAS cleanup.

This traversal retains immutable data only. It neither selects native policy,
replays native acceptance, authenticates archived authority, nor restores grants.
"""

from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
    capture_qualification_source_records,
)
from literate_ai.application.standard_project_lifecycle import (
    StandardProjectLifecycleResult,
)
from literate_ai.contracts.executable_components import (
    CandidateAttemptChain,
    SourceGenerationDisposition,
    SourceGenerationNodeResult,
    SourceGenerationRunOutput,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceClosure,
    NativeRootCandidateAttempt,
    NativeRootContinuationLedger,
    NativeRootContinuationStop,
    NativeRootExecutionResult,
    NativeRootRepairRequest,
    NativeRootRunBinding,
)
from literate_ai.storage import FileSystemCAS


def capture_native_root_source_history(
    lifecycle: StandardProjectLifecycleResult,
    recorder: QualificationEvidenceRecorder,
    *,
    cas: FileSystemCAS,
) -> tuple[ContentIdentity, ...]:
    """Copy each generated attempt's exact source closure into bounded capture.

    The caller supplies the current application's nonserialized typed result and
    original candidate CAS. Trusted provider authority decides when such history
    is mandatory. Absence here preserves the caller's existing final-node path;
    archive fields never select this path or authorize any execution.
    """
    if not isinstance(lifecycle, StandardProjectLifecycleResult):
        raise QualificationCaptureError("qualification.capture.lifecycle-invalid")
    audit = getattr(lifecycle, "native_root_execution", None)
    if audit is None:
        return ()
    if (
        type(audit) is not NativeRootExecutionResult
        or not isinstance(recorder, QualificationEvidenceRecorder)
        or not isinstance(cas, FileSystemCAS)
    ):
        raise QualificationCaptureError("qualification.capture.native-history-invalid")
    reader = QualificationEvidenceReader(
        recorder.entries, max_bytes=recorder.max_bytes, max_records=recorder.max_records
    )

    def read(identity, decode):
        value = decode(reader.read_json(identity))
        if value.identity != identity:
            raise QualificationCaptureError("qualification.capture.record-mismatch")
        return value

    try:
        if read(audit.identity, NativeRootExecutionResult.from_dict) != audit:
            raise ValueError("current audit differs from retained record")
        run = read(audit.run_binding_identity, NativeRootRunBinding.from_dict)
        ledger = read(audit.ledger_identity, NativeRootContinuationLedger.from_dict)
        closure = (
            None
            if audit.acceptance_closure_identity is None
            else read(
                audit.acceptance_closure_identity, NativeRootAcceptanceClosure.from_dict
            )
        )
        chains = tuple(
            read(identity, CandidateAttemptChain.from_dict)
            for identity in ledger.historical_legacy_node_chain_identities
        )
        stop = (
            None
            if ledger.terminal_stop_identity is None
            else read(
                ledger.terminal_stop_identity, NativeRootContinuationStop.from_dict
            )
        )
        ledger.require_records(run, historical_chains=chains, terminal_stop=stop)
        audit.require_records(run, ledger, closure=closure)
        if (
            audit.final_lifecycle_result_identity != lifecycle.identity
            or run.execution_plan_identity != lifecycle.execution_plan_identity
        ):
            raise ValueError("native history differs from current lifecycle")
        sources = []
        for attempt in ledger.attempts:
            if read(attempt.identity, NativeRootCandidateAttempt.from_dict) != attempt:
                raise ValueError("retained root attempt differs")
            if attempt.incoming_request_kind == "native-root-repair":
                repair = read(
                    attempt.incoming_request_identity, NativeRootRepairRequest.from_dict
                )
                if (
                    repair.run_binding_identity != run.identity
                    or repair.candidate_ordinal != attempt.ordinal
                    or repair.predecessor_root_attempt_identities
                    != attempt.predecessor_root_attempt_identities
                    or repair.bounded_generation_request_identity
                    != attempt.bounded_generation_request_identity
                    or repair.workspace_allocation_identity
                    != attempt.workspace_allocation_identity
                ):
                    raise ValueError("retained repair allocation differs")
            if attempt.source_output_identity is None:
                continue
            document = reader.read_json(attempt.node_lifecycle_result_identity)
            source = read(
                attempt.source_output_identity, SourceGenerationRunOutput.from_dict
            )
            if (
                type(document) is not dict
                or document.get("schema")
                != "literate-ai/standard-node-lifecycle-result@4"
                or canonical_identity(document)
                != attempt.node_lifecycle_result_identity
                or document.get("component_revision") != run.root_revision.uri
                or document.get("source_output") != source.to_dict()
            ):
                raise ValueError("retained node differs from exact source output")
            generation = SourceGenerationNodeResult.from_dict(
                document["source_generation"]
            )
            candidate, provenance = source.candidate, source.provenance
            if (
                generation.disposition is not SourceGenerationDisposition.GENERATED
                or generation.failure_code is not None
                or provenance.retained_source_identity is not None
                or candidate.component_revision != run.root_revision
                or candidate.source_generation_request_identity
                != attempt.bounded_generation_request_identity
                or candidate.workspace_allocation_identity
                != attempt.workspace_allocation_identity
                or candidate.recipe_identity != run.original_recipe_identity
                or provenance.component_lock_identity != run.component_lock_identity
                or provenance.application_root_revision_identity != run.root_revision
                or provenance.generated_component_revision_identity != run.root_revision
                or generation.candidate_identity != source.candidate_identity
                or generation.provenance_identity != source.provenance_identity
                or generation.workspace_allocation_identity
                != attempt.workspace_allocation_identity
                or generation.component_revision != candidate.component_revision
                or generation.generation_plan_identity
                != candidate.component_generation_plan_identity
                or generation.generation_key_identity
                != candidate.generation_key_identity
                or generation.context_manifest_identity
                != candidate.context_manifest_identity
                or generation.prompt_identity != candidate.prompt_identity
                or generation.recipe_identity != candidate.recipe_identity
                or any(
                    getattr(candidate, name) != getattr(provenance, name)
                    for name in (
                        "component_generation_plan_identity",
                        "generation_key_identity",
                        "context_manifest_identity",
                        "prompt_identity",
                        "recipe_identity",
                        "workspace_allocation_identity",
                    )
                )
            ):
                raise ValueError("history is not the actual generated candidate")
            sources.append(source)
        # Reopen all identity joins before traversing candidate CAS. Each read
        # and insertion then uses the existing capture's byte/record limits.
        for source in sources:
            capture_qualification_source_records(
                recorder, candidate=source.candidate, cas=cas
            )
        return tuple(source.identity for source in sources)
    except QualificationCaptureError:
        raise
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError) as exc:
        raise QualificationCaptureError(
            "qualification.capture.native-history-invalid"
        ) from exc
