"""Current public preparation and closed history checks, NOT archive acceptance.

Project current context independently of archive contents, before deriving run
binding expectations. Verify history only after the caller's trusted policy/run/
ledger joins. These inert records restore no workspace, owner or execution grant.
Native outcomes, historical source/build/package validation and qualification
remain separate mandatory checks. Frozen legacy-node-repair rendering and SDK
producer-backed context are deliberately unsupported here and fail closed.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field

from literate_ai.adapters.generation_preparation import (
    LockedComponentModelSelectionAdapter,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthoritySnapshot,
)
from literate_ai.adapters.qualification_capture import QualificationEvidenceReader
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectPlanningAdapter,
)
from literate_ai.application.candidate_repair_prompt import (
    render_candidate_repair_prompt,
)
from literate_ai.application.component_generation_context import (
    PreparedComponentGenerationRequest,
    prepare_component_generation_context,
)
from literate_ai.application.component_generation_preparation import (
    ComponentGenerationWorkspaceDescriptor,
)
from literate_ai.application.native_root_repair_prompt import (
    render_native_root_repair_prompt,
)
from literate_ai.contracts.executable_components import (
    CandidateAttemptChain,
    CandidateRepairDiagnostic,
    CandidateRepairRequest,
    ComponentExecutionPlan,
    ComponentGenerationPlan,
    ReplacementWorkspace,
)
from literate_ai.contracts.executable_components.context import (
    BoundedComponentGenerationRequest,
    GenerationComplexityBudget,
    deterministic_token_estimate,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceRejection,
    NativeRootContinuationLedger,
    NativeRootContinuationStop,
    NativeRootRepairDiagnostic,
    NativeRootRepairRequest,
    NativeRootRunBinding,
)


class NativeRootPreparationReplayError(ValueError):
    """Public preparation cannot be joined to independent current expectations."""


def _require(condition, name):
    if not condition:
        raise NativeRootPreparationReplayError("native_root_preparation_replay." + name)


def _prompt_identity(prompt):
    return ContentIdentity.parse_uri("sha256:" + hashlib.sha256(prompt).hexdigest())


@dataclass(frozen=True, slots=True)
class CurrentNativeRootPreparation:
    """Inert expectations, not a capability; caller still owns provider authority."""

    snapshot: LockedGenerationAuthoritySnapshot
    execution_plan: ComponentExecutionPlan
    generation_plan: ComponentGenerationPlan
    recipe_identity: ContentIdentity
    original: PreparedComponentGenerationRequest
    _budget_selector: Callable[[], GenerationComplexityBudget] = field(
        repr=False, compare=False
    )
    _execution_identity: ContentIdentity = field(repr=False)
    _request_identity: ContentIdentity = field(repr=False)
    _qualified_library_inputs: object = field(default=None, repr=False, compare=False)
    _original_qualified_library_inputs: object = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self):
        object.__setattr__(
            self, "_original_qualified_library_inputs", self._qualified_library_inputs
        )

    def _require_qualified_inputs(self):
        original = self._original_qualified_library_inputs
        _require(self._qualified_library_inputs is original, "qualified_owner_changed")
        if original is not None:
            from literate_ai.adapters.native_root_external_runtime import (
                require_qualified_library_inputs,
            )

            require_qualified_library_inputs(original, self.snapshot)
            _require(
                self._qualified_library_inputs is original, "qualified_owner_changed"
            )

    def require_unchanged(self):
        self._require_qualified_inputs()
        self.snapshot.require_unchanged()
        budget = self._budget_selector()
        _require(type(budget) is GenerationComplexityBudget, "budget_invalid")
        budget.__post_init__()
        _require(
            self.execution_plan.identity == self._execution_identity
            and self.execution_plan.component_lock_identity
            == self.snapshot.authority.lock.identity
            and self.execution_plan.root_revision
            == self.snapshot.authority.lock.root_revision
            and any(
                plan is self.generation_plan
                for plan in self.execution_plan.generation_plans
            )
            and self.original.request.identity == self._request_identity
            and self.original.request.budget == budget
            and _prompt_identity(self.original.prompt)
            == self.original.request.prompt_identity,
            "current_context_changed",
        )
        self.snapshot.require_unchanged()
        self._require_qualified_inputs()


def project_current_native_root_preparation(
    *,
    snapshot: LockedGenerationAuthoritySnapshot,
    execution_plan: ComponentExecutionPlan,
    provider_id: str,
    pipeline_model: str | None,
    budget_selector: Callable[[], GenerationComplexityBudget],
    qualified_library_inputs=None,
) -> CurrentNativeRootPreparation:
    """Use current locked bytes and qualification's trusted default-budget selector.

    `provider_id`, `pipeline_model`, snapshot, plan and budget selector are caller
    authority, never selected from an archive. No allocator or executable selector
    is called. Do not substitute Runtime.prepare, which creates workspaces.
    """
    if (
        type(snapshot) is not LockedGenerationAuthoritySnapshot
        or type(execution_plan) is not ComponentExecutionPlan
        or type(provider_id) is not str
        or not provider_id.strip()
        or (
            pipeline_model is not None
            and (type(pipeline_model) is not str or not pipeline_model.strip())
        )
        or not callable(budget_selector)
    ):
        raise TypeError(
            "independent current snapshot, plan, provider/model and "
            "budget selector required"
        )
    snapshot.require_unchanged()
    execution_plan.__post_init__()
    lock = snapshot.authority.lock
    _require(
        execution_plan.component_lock_identity == lock.identity
        and execution_plan.root_revision == lock.root_revision,
        "current_plan_changed",
    )
    selected = tuple(
        plan
        for plan in execution_plan.generation_plans
        if plan.component_revision == lock.root_revision
    )
    _require(len(selected) == 1, "root_plan_missing")
    root_plan = selected[0]
    selector = LockedComponentModelSelectionAdapter(pipeline_model=pipeline_model)
    replanned = FilesystemStandardProjectPlanningAdapter(
        model_selector=selector,
        **(
            {"qualified_library_inputs": qualified_library_inputs}
            if qualified_library_inputs is not None
            else {}
        ),
    ).plan_for_coding_cli(snapshot, coding_cli=provider_id)
    _require(replanned == execution_plan, "current_plan_changed")
    projection = LockedComponentNodePreparationAdapter(
        model_selector=selector,
        coding_cli=provider_id,
        **(
            {"qualified_library_inputs": qualified_library_inputs}
            if qualified_library_inputs is not None
            else {}
        ),
    ).project(snapshot, root_plan)
    _require(
        projection.component_revision == root_plan.component_revision,
        "root_projection_changed",
    )
    budget = budget_selector()
    _require(type(budget) is GenerationComplexityBudget, "budget_invalid")
    budget.__post_init__()
    original = prepare_component_generation_context(
        root_plan,
        framework_envelope=projection.recipe.prompt(
            include_locked_authority_documents=False
        ).encode("utf-8"),
        authority_segments=projection.authority_segments,
        budget=budget,
    )
    current = CurrentNativeRootPreparation(
        snapshot,
        execution_plan,
        root_plan,
        ContentIdentity.parse_uri(projection.recipe.identity),
        original,
        budget_selector,
        execution_plan.identity,
        original.request.identity,
        qualified_library_inputs,
    )
    current.require_unchanged()
    return current


@dataclass(frozen=True, slots=True)
class ReopenedNativeRootPreparation:
    """Historical data only; a locator is never opened or adopted as a workspace."""

    request: BoundedComponentGenerationRequest
    prompt: bytes
    workspace: ComponentGenerationWorkspaceDescriptor


def verify_closed_native_root_preparation_history(
    reader: QualificationEvidenceReader,
    *,
    current: CurrentNativeRootPreparation,
    run: NativeRootRunBinding,
    ledger: NativeRootContinuationLedger,
) -> tuple[ReopenedNativeRootPreparation, ...]:
    """Verify request/prompt/plan/allocation preimages after exact binding joins.

    This does not infer trusted selection, verify native mismatches or accept an
    archive. Ordinary v2 repair uses its separate exact public renderer.
    """
    if (
        not isinstance(reader, QualificationEvidenceReader)
        or type(current) is not CurrentNativeRootPreparation
        or type(run) is not NativeRootRunBinding
        or type(ledger) is not NativeRootContinuationLedger
    ):
        raise TypeError(
            "bounded reader, independent current context and joined run/ledger required"
        )
    current.require_unchanged()
    run.__post_init__()
    ledger.__post_init__()

    def read(identity, kind):
        current.require_unchanged()
        value = kind.from_dict(reader.read_json(identity))
        _require(value.identity == identity, "record_changed")
        current.require_unchanged()
        return value

    _require(
        run.execution_plan_identity == current.execution_plan.identity
        and run.component_lock_identity
        == current.execution_plan.component_lock_identity
        and run.root_revision == current.generation_plan.component_revision
        and run.original_generation_plan_identity == current.generation_plan.identity
        and run.original_recipe_identity == current.recipe_identity
        and run.original_bounded_request_identity == current.original.request.identity,
        "original_context_changed",
    )
    _require(
        read(run.execution_plan_identity, ComponentExecutionPlan)
        == current.execution_plan,
        "execution_plan_changed",
    )
    _require(
        read(run.original_generation_plan_identity, ComponentGenerationPlan)
        == current.generation_plan,
        "generation_plan_changed",
    )
    chains = tuple(
        read(identity, CandidateAttemptChain)
        for identity in ledger.historical_legacy_node_chain_identities
    )
    stop = (
        None
        if ledger.terminal_stop_identity is None
        else read(ledger.terminal_stop_identity, NativeRootContinuationStop)
    )
    ledger.require_records(run, historical_chains=chains, terminal_stop=stop)
    _require(bool(ledger.attempts), "attempts_missing")
    reopened, locators = [], set()
    for index, attempt in enumerate(ledger.attempts):
        current.require_unchanged()
        if index == 0:
            expected, prompt = current.original.request, current.original.prompt
        elif attempt.incoming_request_kind == "legacy-node-repair":
            chain = next(
                (
                    chain
                    for chain in chains
                    if chain.identity == attempt.legacy_node_chain_identity
                ),
                None,
            )
            legacy_index = attempt.legacy_node_attempt_index
            _require(
                chain is not None
                and type(legacy_index) is int
                and 1 <= legacy_index < len(chain.attempts),
                "legacy_chain_changed",
            )
            legacy = chain.attempts[legacy_index]
            repair = read(attempt.incoming_request_identity, CandidateRepairRequest)
            diagnostic = read(repair.diagnostic_identity, CandidateRepairDiagnostic)
            prefix = tuple(item.identity for item in chain.attempts[:legacy_index])
            bases = [
                position
                for position, prior in enumerate(ledger.attempts[:index])
                if prior.legacy_node_chain_identity == chain.identity
                and prior.legacy_node_attempt_index == 0
            ]
            _require(
                len(bases) == 1
                and repair == legacy.repair_request
                and repair.attempt_index == legacy_index
                and repair.component_revision == run.root_revision
                and repair.original_recipe_identity == run.original_recipe_identity
                and repair.predecessor_attempt_identities == prefix
                and diagnostic == chain.attempts[legacy_index - 1].diagnostic
                and repair.bounded_generation_request_identity
                == attempt.bounded_generation_request_identity
                and repair.workspace_allocation_identity
                == attempt.workspace_allocation_identity,
                "legacy_repair_changed",
            )
            base = reopened[bases[0]]
            _require(
                base.request.identity == chain.attempts[0].generation_request_identity,
                "legacy_original_changed",
            )
            expected, prompt = render_candidate_repair_prompt(
                PreparedComponentGenerationRequest(base.request, base.prompt),
                diagnostic,
                prefix,
            )
            # The original global request owns the budget; legacy rendering
            # preserves its decision instead of authoring a fresh allowance.
            feedback_bytes = len(prompt) - len(current.original.prompt)
            _require(
                feedback_bytes >= 0
                and expected.context_manifest.estimated_tokens
                + deterministic_token_estimate(feedback_bytes)
                <= expected.budget.max_estimated_tokens
                and deterministic_token_estimate(len(prompt))
                <= expected.budget.max_estimated_tokens,
                "legacy_prompt_budget_exceeded",
            )
        else:
            _require(
                attempt.incoming_request_kind == "native-root-repair",
                "legacy_preparation_unsupported",
            )
            repair = read(attempt.incoming_request_identity, NativeRootRepairRequest)
            diagnostic = read(
                repair.diagnostic_identity,
                NativeRootRepairDiagnostic
                if repair.cause_kind == "native-acceptance"
                else CandidateRepairDiagnostic,
            )
            rejection = (
                None
                if repair.acceptance_rejection_identity is None
                else read(
                    repair.acceptance_rejection_identity, NativeRootAcceptanceRejection
                )
            )
            repair.require_records(
                run, ledger.attempts[:index], diagnostic, rejection=rejection
            )
            _require(
                repair.candidate_ordinal == index
                and repair.bounded_generation_request_identity
                == attempt.bounded_generation_request_identity
                and repair.workspace_allocation_identity
                == attempt.workspace_allocation_identity,
                "repair_allocation_changed",
            )
            expected, prompt = render_native_root_repair_prompt(
                current.original, ledger.attempts[:index], diagnostic
            )
        request = read(
            attempt.bounded_generation_request_identity,
            BoundedComponentGenerationRequest,
        )
        _require(request == expected, "request_changed")
        _require(
            reader.read_bytes(request.prompt_identity) == prompt
            and _prompt_identity(prompt) == request.prompt_identity
            and len(prompt) <= request.budget.max_prompt_bytes,
            "public_prompt_changed",
        )
        allocation = reader.read_json(attempt.workspace_allocation_identity)
        _require(
            type(allocation) is dict
            and set(allocation)
            == {"schema", "component_revision", "generation_plan_identity", "locator"},
            "allocation_invalid",
        )
        _require(
            allocation
            == {
                "schema": "literate-ai/component-workspace-allocation@1",
                "component_revision": current.generation_plan.component_revision.uri,
                "generation_plan_identity": current.generation_plan.identity.uri,
                "locator": allocation["locator"],
            }
            and canonical_identity(allocation) == attempt.workspace_allocation_identity,
            "allocation_changed",
        )
        workspace = ComponentGenerationWorkspaceDescriptor(
            current.generation_plan.component_revision,
            current.generation_plan.identity,
            current.generation_plan.generation_key.identity,
            attempt.workspace_allocation_identity,
            allocation["locator"],
            ReplacementWorkspace.FRESH_EMPTY,
        )
        descriptor = {
            "schema": "literate-ai/component-generation-workspace@1",
            "component_revision": workspace.component_revision.uri,
            "generation_plan_identity": workspace.generation_plan_identity.uri,
            "generation_key_identity": workspace.generation_key_identity.uri,
            "allocation_identity": workspace.allocation_identity.uri,
            "locator": workspace.locator,
            "workspace": workspace.workspace.value,
        }
        _require(
            reader.read_json(workspace.identity) == descriptor, "descriptor_changed"
        )
        _require(workspace.locator not in locators, "workspace_reused")
        locators.add(workspace.locator)
        reopened.append(ReopenedNativeRootPreparation(request, prompt, workspace))
        current.require_unchanged()
    current.require_unchanged()
    return tuple(reopened)
