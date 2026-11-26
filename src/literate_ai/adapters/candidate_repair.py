"""Conservative production adapter for bounded generated-candidate repair."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator,
)
from literate_ai.application.component_generation_context import (
    PreparedComponentGenerationRequest,
)
from literate_ai.application.component_generation_preparation import (
    ComponentGenerationWorkspaceDescriptor,
    PreparedComponentGenerationNode,
)
from literate_ai.application.native_root_repair_prompt import (
    render_native_root_repair_prompt,
)
from literate_ai.application.native_root_run import (
    LiveNativeRootRun,
    current_native_root_run,
)
from literate_ai.application.source_generation_scheduling import (
    validate_prepared_component_generation_node,
)
from literate_ai.contracts import ContentIdentity, HashAlgorithm
from literate_ai.contracts.executable_components import (
    CandidateFailureClassification,
    CandidateRepairDiagnostic,
    SourceGenerationRunOutput,
)
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceRejection,
    NativeRootCandidateAttempt,
    NativeRootContinuationLedger,
    NativeRootQualifiedDependencyBinding,
    NativeRootRepairDiagnostic,
    NativeRootRepairRequest,
    NativeRootRunBinding,
)
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailureEvidence,
    StandardNodeFailurePhase,
)

_RETRYABLE_CODES = frozenset(
    {
        "builder.generated-source-rejected",
        "dependencies.import-bom-mismatch",
        "generated-test.failed",
    }
)
_MISSING_INCLUDE = re.compile(
    r"fatal error:\s*['\"]?([A-Za-z0-9_.+-]{1,128})['\"]?\s+file not found",
    re.IGNORECASE,
)
_GENERATED_TEST_FACTS = (
    "generated-test runner did not emit attributable case results",
    "generated-test runner emitted an invalid case result protocol",
    "generated-test runner emitted an invalid or failed case result",
    "generated-test runner did not execute every and only selected case",
)
_GENERATED_BUILD_FACTS = ("generated build did not produce the exact declared export",)
_IMPORT_BOM_MISMATCH_FACT = (
    "generated external imports are absent from manifests and the source BOM"
)
_ZIPAPP_ARGV_FAILURE = re.compile(
    r"\b_cli\(\) missing 1 required positional argument: ['\"]argv['\"]"
)


def _prompt_identity(prompt: bytes) -> ContentIdentity:
    return ContentIdentity(HashAlgorithm.SHA256, hashlib.sha256(prompt).hexdigest())


def _safe_diagnostic(failure: StandardNodeFailureEvidence, raw: str | None) -> str:
    """Return only a bounded, portable fact that is useful for a fresh replacement."""

    if (
        failure.phase is StandardNodeFailurePhase.ACCEPT
        and failure.code == "component_acceptance.rust_harness_result_mismatch"
    ):
        return (
            "the independent native library verifier rejected the generated public "
            "results; recheck every approved public boundary behavior and exact "
            "static error before producing a complete fresh replacement"
        )
    phase = failure.phase.value
    if isinstance(raw, str):
        match = _MISSING_INCLUDE.search(raw[:8192])
        if match is not None:
            return (
                f"generated {phase} failed because required file "
                f"{match.group(1)} was unavailable to a generated target"
            )
        for fact in _GENERATED_TEST_FACTS:
            if fact in raw[:8192]:
                return f"generated {phase} failed because its {fact}"
        for fact in _GENERATED_BUILD_FACTS:
            if fact in raw[:8192]:
                return (
                    "generated build failed because it did not produce the exact "
                    "declared export"
                )
        if _IMPORT_BOM_MISMATCH_FACT in raw[:8192]:
            return (
                "generated build failed because an imported module is absent from "
                "both generated source paths and declared dependency metadata"
            )
        if _ZIPAPP_ARGV_FAILURE.search(raw[:8192]) is not None:
            return (
                "generated test failed because its Python zipapp entry point requires "
                "argv even though the archive invokes that callable with no arguments"
            )
    return (
        f"generated source failed its {phase} command; regenerate a complete "
        "replacement whose source, generated tests, and build metadata agree"
    )


@dataclass(frozen=True)
class NativeRootRepairAllocation:
    """Actual allocator report retained for terminal bookkeeping, never authority.

    The raw allocation may not be a valid replacement. Optional records exist
    only if construction completed; their presence does not grant execution.
    """

    generation_request: PreparedComponentGenerationRequest
    workspace: ComponentGenerationWorkspaceDescriptor
    prepared: PreparedComponentGenerationNode[object, object] | None = None
    repair_request: NativeRootRepairRequest | None = None


class AllocatedNativeRootRepairPreparationError(RuntimeError):
    """Preparation failed after an actual allocator return; retain its evidence."""

    def __init__(
        self, allocation: NativeRootRepairAllocation, original_error: Exception
    ):
        self.native_root_repair_allocation = allocation
        self.original_error = original_error
        self.code = getattr(
            original_error, "code", "native_root_repair.preparation_failed"
        )
        super().__init__(str(original_error))


class FilesystemStandardCandidateRepairAdapter:
    """Retry allowlisted candidate rejection in a fresh sibling workspace."""

    def __init__(self, diagnostics: Mapping[str, str]) -> None:
        self._diagnostics = diagnostics

    def diagnose(
        self,
        failure: StandardNodeFailureEvidence,
        output: SourceGenerationRunOutput,
    ) -> CandidateRepairDiagnostic:
        if not isinstance(failure, StandardNodeFailureEvidence) or not isinstance(
            output, SourceGenerationRunOutput
        ):
            raise TypeError("candidate repair requires typed failure and source output")
        if output.candidate.component_revision != failure.component_revision:
            raise ValueError("candidate repair output names another Component")
        retryable = (
            failure.code in _RETRYABLE_CODES
            and failure.phase
            in {
                StandardNodeFailurePhase.BUILD,
                StandardNodeFailurePhase.TEST,
            }
        ) or (
            failure.phase is StandardNodeFailurePhase.ACCEPT
            and failure.code == "component_acceptance.rust_harness_result_mismatch"
        )
        return CandidateRepairDiagnostic(
            failure.component_revision,
            failure.phase,
            failure.code,
            _safe_diagnostic(
                failure, self._diagnostics.get(failure.component_revision.uri)
            ),
            (
                CandidateFailureClassification.RETRYABLE
                if retryable
                else CandidateFailureClassification.TERMINAL
            ),
            failure.identity,
        )

    def prepare_root_repair(
        self,
        original: PreparedComponentGenerationNode[object, object],
        run_binding: NativeRootRunBinding,
        predecessors: tuple[NativeRootCandidateAttempt, ...],
        diagnostic: NativeRootRepairDiagnostic | CandidateRepairDiagnostic,
        *,
        live_run: LiveNativeRootRun,
        project_authority_identity: ContentIdentity,
        execution_plan_identity: ContentIdentity,
        rejection: NativeRootAcceptanceRejection | None = None,
        qualified_dependencies: tuple[NativeRootQualifiedDependencyBinding, ...] = (),
    ) -> tuple[
        PreparedComponentGenerationNode[object, object], NativeRootRepairRequest
    ]:
        """Prepare only after the controller consumed its original native witness.

        Closed joins and this original live lifetime do not grant execution or
        prove native eligibility. No legacy v2 chain is extended by this port.
        Failure returns no candidate: the controller retains its actual prefix.
        """
        if type(live_run) is not LiveNativeRootRun:
            raise TypeError("root repair requires the original live run")
        live_run.require_current()
        if current_native_root_run() is not live_run:
            raise ValueError("root repair must retain the active original owner")
        if type(run_binding) is not NativeRootRunBinding:
            raise TypeError("root repair requires its typed original run binding")
        validate_prepared_component_generation_node(original)
        definition, framework, lifecycle_policy = live_run.bindings
        run_binding.require_records(
            live_run.policy,
            live_run.deadline,
            qualified_dependencies,
            project_definition_identity=definition,
            project_authority_identity=project_authority_identity,
        )
        recipe = getattr(original.recipe, "identity", None)
        recipe_identity = (
            recipe
            if isinstance(recipe, ContentIdentity)
            else ContentIdentity.parse_uri(recipe)
            if isinstance(recipe, str)
            else None
        )
        if (
            type(execution_plan_identity) is not ContentIdentity
            or run_binding.execution_plan_identity != execution_plan_identity
            or run_binding.framework_distribution_identity != framework
            or run_binding.lifecycle_policy_identity != lifecycle_policy
            or run_binding.root_revision != original.plan.component_revision
            or run_binding.component_lock_identity
            != original.plan.component_graph_identity
            or run_binding.original_recipe_identity != recipe_identity
            or run_binding.original_generation_plan_identity != original.plan.identity
            or run_binding.original_bounded_request_identity
            != original.request.request.identity
        ):
            raise ValueError("root repair differs from original prepared authority")
        if type(predecessors) is not tuple or not 1 <= len(predecessors) <= 2:
            raise ValueError("root repair requires one or two actual predecessors")
        if any(
            type(attempt) is not NativeRootCandidateAttempt for attempt in predecessors
        ):
            raise TypeError("root repair requires typed actual predecessor attempts")
        # Construction validates exact ordinals/prefix, no repeated allocation or
        # request, and a retryable pending tail. Every history ID comes from the
        # actual prefix; this pure check grants no authority over those records.
        NativeRootContinuationLedger(
            run_binding.identity,
            predecessors,
            tuple(
                sorted(
                    {
                        p.legacy_node_chain_identity
                        for p in predecessors
                        if p.legacy_node_chain_identity is not None
                    },
                    key=lambda value: value.uri,
                )
            ),
            "pending",
            None,
        )
        if (
            predecessors[0].bounded_generation_request_identity
            != run_binding.original_bounded_request_identity
            or predecessors[0].workspace_allocation_identity
            != original.workspace.allocation_identity
        ):
            raise ValueError("root repair prefix changed the original candidate")
        last = predecessors[-1]
        native = type(diagnostic) is NativeRootRepairDiagnostic
        if native:
            if type(rejection) is not NativeRootAcceptanceRejection:
                raise TypeError("native repair requires the exact typed rejection")
            rejection.require_binding(run_binding)
            diagnostic.require_rejection(rejection)
            if (
                rejection.candidate_ordinal != last.ordinal
                or rejection.bounded_generation_request_identity
                != last.bounded_generation_request_identity
                or rejection.source_output_identity != last.source_output_identity
                or rejection.workspace_allocation_identity
                != last.workspace_allocation_identity
                or rejection.node_lifecycle_result_identity
                != last.node_lifecycle_result_identity
                or rejection.packaged_binding != last.final_packaged_binding
                or last.outcome
                != (
                    "package-rejected"
                    if rejection.acceptance_scope == "packaged-root"
                    else "native-precheck-rejected"
                )
                or last.failure_evidence_identity != rejection.identity
                or last.diagnostic_identity != diagnostic.identity
            ):
                raise ValueError("native repair rejection changed the actual candidate")
            failure_identity = rejection.identity
        else:
            if (
                type(diagnostic) is not CandidateRepairDiagnostic
                or rejection is not None
                or diagnostic.component_revision != run_binding.root_revision
                or diagnostic.phase
                not in {StandardNodeFailurePhase.BUILD, StandardNodeFailurePhase.TEST}
                or diagnostic.classification
                is not CandidateFailureClassification.RETRYABLE
                or diagnostic.code not in _RETRYABLE_CODES
                or last.outcome != "node-rejected"
                or last.failure_evidence_identity
                != diagnostic.failure_evidence_identity
                or last.diagnostic_identity != diagnostic.identity
            ):
                raise ValueError(
                    "root repair requires an actual retryable build/test failure"
                )
            failure_identity = diagnostic.failure_evidence_identity
        request, prompt = render_native_root_repair_prompt(
            original.request, predecessors, diagnostic
        )
        live_run.require_current()
        locator = Path(original.workspace.locator)
        original_workspace = locator.resolve(strict=True)
        if locator != original_workspace or not original_workspace.is_dir():
            raise ValueError(
                "root repair original workspace must retain its native path"
            )
        generation_request = PreparedComponentGenerationRequest(request, prompt)
        workspace = FilesystemComponentWorkspaceAllocator(
            original_workspace.parent
        ).allocate(original.plan)
        allocation = NativeRootRepairAllocation(generation_request, workspace)
        try:
            root_request = NativeRootRepairRequest(
                run_binding.identity,
                len(predecessors),
                recipe_identity,
                tuple(attempt.identity for attempt in predecessors),
                diagnostic.identity,
                rejection.identity if native else None,
                request.identity,
                workspace.allocation_identity,
                "native-acceptance" if native else "node-build-test",
                failure_identity,
            )
            allocation = replace(allocation, repair_request=root_request)
            prepared = replace(
                original, request=generation_request, workspace=workspace
            )
            allocation = replace(allocation, prepared=prepared)
            validate_prepared_component_generation_node(prepared)
            if (
                workspace.locator == original.workspace.locator
                or workspace.allocation_identity
                in {attempt.workspace_allocation_identity for attempt in predecessors}
            ):
                raise ValueError("root repair must allocate a fresh workspace")
            root_request.require_records(
                run_binding, predecessors, diagnostic, rejection=rejection
            )
            live_run.require_current()
            return prepared, root_request
        except BaseException as error:
            if isinstance(error, Exception):
                raise AllocatedNativeRootRepairPreparationError(
                    allocation, error
                ) from error
            # Preserve operator cancellation identity/type and control flow.
            error.native_root_repair_allocation = allocation
            raise

    def prepare_repair(
        self,
        original: PreparedComponentGenerationNode[object, object],
        diagnostic: CandidateRepairDiagnostic,
        predecessor_attempt_identities: tuple[ContentIdentity, ...],
    ) -> PreparedComponentGenerationNode[object, object]:
        if not isinstance(original, PreparedComponentGenerationNode):
            raise TypeError("candidate repair requires one prepared Component")
        if (
            not isinstance(diagnostic, CandidateRepairDiagnostic)
            or diagnostic.classification is not CandidateFailureClassification.RETRYABLE
            or not predecessor_attempt_identities
            or len(predecessor_attempt_identities) > 2
            or any(
                not isinstance(item, ContentIdentity)
                for item in predecessor_attempt_identities
            )
            or len({item.uri for item in predecessor_attempt_identities})
            != len(predecessor_attempt_identities)
            or diagnostic.component_revision != original.plan.component_revision
        ):
            raise ValueError("candidate repair request is not an exact retryable chain")
        prompt = (
            original.request.prompt
            + (
                "\n\n## Bounded candidate-repair evidence\n"
                f"Failure: {diagnostic.sanitized_text}\n"
                f"Diagnostic identity: {diagnostic.identity.uri}\n"
                "Predecessor candidate attempt identities:\n"
                + "".join(
                    f"- {identity.uri}\n" for identity in predecessor_attempt_identities
                )
                + "Produce a complete fresh replacement; do not reuse prior candidate "
                "files.\n"
            ).encode()
        )
        request = replace(
            original.request.request,
            prompt_identity=_prompt_identity(prompt),
        )
        original_workspace = Path(original.workspace.locator).resolve(strict=True)
        workspace = FilesystemComponentWorkspaceAllocator(
            original_workspace.parent
        ).allocate(original.plan)
        return replace(
            original,
            request=PreparedComponentGenerationRequest(request, prompt),
            workspace=workspace,
        )


__all__ = [
    "AllocatedNativeRootRepairPreparationError",
    "FilesystemStandardCandidateRepairAdapter",
    "NativeRootRepairAllocation",
]
