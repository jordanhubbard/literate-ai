"""Closed source-attempt checks, not qualification or full-history acceptance.

The caller must first verify trusted policy/run/ledger joins and the complete
preparation history. Transport metadata is an EXPLICIT independently trusted
input: its provenance is not established by this module or by archived tool IDs.
Only a preimage of the independently held expected binding is reopened here.
Existing retained imports acquire no live coding-CLI requirement. No executable,
workspace or run owner is selected, opened or created here. Failed source stages,
retained/reused origins and missing transport provenance need separate handling;
build/test/package/native outcomes remain mandatory independent checks.

Replay's explicit approved workflow root must match the producer's actual root.
The Standard source adapter captures its admitted project root before per-node
callbacks and passes it to the same invocation projection used by replay.
The caller still establishes current root/authority custody independently.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from literate_ai.adapters.generation_preparation import (
    LockedComponentModelSelectionAdapter,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.models import CODING_CLIS
from literate_ai.adapters.models.coding_cli import (
    CodingCliIsolation,
    _planned_generation_prompt,
)
from literate_ai.adapters.native_root_preparation_replay import (
    CurrentNativeRootPreparation,
    ReopenedNativeRootPreparation,
)
from literate_ai.adapters.native_root_transport import (
    reopen_native_root_transport_preimage,
)
from literate_ai.adapters.qualification_capture import (
    QualificationEvidenceReader,
    reopen_qualification_node,
    verify_qualification_generation_records,
    verify_qualification_source_records,
)
from literate_ai.adapters.standard_project import project_standard_source_invocation
from literate_ai.application.component_generation_context import (
    PreparedComponentGenerationRequest,
)
from literate_ai.application.component_generation_preparation import (
    PreparedComponentGenerationNode,
)
from literate_ai.contracts.executable_components import SourceGenerationDisposition
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.native_root_continuation import (
    NativeRootCandidateAttempt,
    NativeRootRunBinding,
)
from literate_ai.contracts.rebuild_cache import rebuild_project_authority_identity


class NativeRootSourceHistoryReplayError(ValueError):
    """A source attempt cannot be joined to independently current preparation."""


def _require(condition, name):
    if not condition:
        raise NativeRootSourceHistoryReplayError("native_root_source_replay." + name)


@dataclass(frozen=True, slots=True)
class NativeRootSourceReplayTransport:
    """Inert caller-supplied transport data; never derive trust from an archive.

    Merely constructing this value does not establish independent provenance.
    Full import integration must anchor these fields separately or refuse this
    route. No live provider executable is required or inspected by this object.
    """

    provenance_status: ClassVar[str] = "independent-transport-anchor-required"
    name: str
    raw_executable_identity: ContentIdentity
    isolation: CodingCliIsolation

    def __post_init__(self):
        if (
            self.name not in CODING_CLIS
            or type(self.raw_executable_identity) is not ContentIdentity
            or type(self.isolation) is not CodingCliIsolation
        ):
            raise TypeError("explicit generated-source transport metadata required")
        self.raw_executable_identity.__post_init__()

    @property
    def executable_identity(self):
        return self.raw_executable_identity.uri

    @property
    def tool_binding_identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/coding-cli-tool-binding@1",
                "coding_cli": self.name,
                "executable_identity": self.executable_identity,
                "isolation": self.isolation.to_dict(),
            }
        ).uri


def _project_original_source_node(current, plan, *, provider_id, pipeline_model):
    owner = current._original_qualified_library_inputs
    _require(current._qualified_library_inputs is owner, "qualified_owner_changed")
    if owner is not None:
        current.require_unchanged()
    projection = LockedComponentNodePreparationAdapter(
        model_selector=LockedComponentModelSelectionAdapter(
            pipeline_model=pipeline_model
        ),
        coding_cli=provider_id,
        **({"qualified_library_inputs": owner} if owner is not None else {}),
    ).project(current.snapshot, plan)
    if owner is not None:
        current.require_unchanged()
    _require(
        current._qualified_library_inputs is owner
        and current._original_qualified_library_inputs is owner,
        "qualified_owner_changed",
    )
    return projection


def verify_closed_native_root_source_attempt(
    reader: QualificationEvidenceReader,
    *,
    current: CurrentNativeRootPreparation,
    run: NativeRootRunBinding,
    attempt: NativeRootCandidateAttempt,
    preparation: ReopenedNativeRootPreparation,
    expected_tool_binding_identity: ContentIdentity,
    provider_id: str,
    pipeline_model: str | None,
    approved_project_root: Path,
    approved_project_authority_identity: ContentIdentity,
    approved_source_project_authority_identity: ContentIdentity | None = None,
):
    """Verify source data after binding/preparation joins, without reopening paths.

    The portable binding expectation must be independently anchored before
    entering this checker. Its exact raw-executable/isolation preimage is required
    in capture; a stage's self-asserted binding is insufficient.
    `preparation` must be the corresponding item returned by the complete strict
    preparation-history verifier, not an unverified archived request. Likewise
    `attempt`/`run` must already belong to the verified ledger. These preconditions
    are deliberately not replaced by archive markers or decoded rejection codes.
    The returned original typed node remains data, never admission authority.
    """
    if (
        not isinstance(reader, QualificationEvidenceReader)
        or type(current) is not CurrentNativeRootPreparation
        or type(run) is not NativeRootRunBinding
        or type(attempt) is not NativeRootCandidateAttempt
        or type(preparation) is not ReopenedNativeRootPreparation
        or type(expected_tool_binding_identity) is not ContentIdentity
        or type(approved_project_authority_identity) is not ContentIdentity
        or (
            approved_source_project_authority_identity is not None
            and type(approved_source_project_authority_identity) is not ContentIdentity
        )
        or not isinstance(approved_project_root, Path)
        or not approved_project_root.is_absolute()
        or ".." in approved_project_root.parts
    ):
        raise TypeError("explicit current authority and joined source inputs required")
    current.require_unchanged()
    # Standard source commits the VALIDATED project authority. The native run
    # separately binds its effective rebuild authority including the lock set.
    # A strict integration supplies both independently current values; archive
    # assertions never select either. Standalone None keeps its original meaning.
    source_authority = approved_project_authority_identity
    if approved_source_project_authority_identity is not None:
        _require(
            rebuild_project_authority_identity(
                approved_source_project_authority_identity,
                (current.execution_plan.component_lock_identity,),
            )
            == approved_project_authority_identity,
            "source_authority_join_changed",
        )
        source_authority = approved_source_project_authority_identity
    run.__post_init__()
    attempt.__post_init__()
    transport = reopen_native_root_transport_preimage(
        reader,
        expected_provider_id=provider_id,
        expected_tool_binding_identity=expected_tool_binding_identity,
    )
    request, prompt, workspace = (
        preparation.request,
        preparation.prompt,
        preparation.workspace,
    )
    plan = current.generation_plan
    _require(
        run.project_authority_identity == approved_project_authority_identity
        and run.execution_plan_identity == current.execution_plan.identity
        and run.component_lock_identity
        == current.execution_plan.component_lock_identity
        and run.root_revision == plan.component_revision
        and run.original_recipe_identity == current.recipe_identity
        and run.original_generation_plan_identity == plan.identity
        and run.original_bounded_request_identity == current.original.request.identity
        and attempt.run_binding_identity == run.identity
        and attempt.bounded_generation_request_identity == request.identity
        and attempt.workspace_allocation_identity == workspace.allocation_identity
        and workspace.component_revision == plan.component_revision
        and workspace.generation_plan_identity == plan.identity
        and workspace.generation_key_identity == plan.generation_key.identity
        and transport.name == provider_id,
        "context_changed",
    )
    _require(
        reader.read_json(request.identity) == request.to_dict()
        and reader.read_bytes(request.prompt_identity) == prompt
        and "sha256:" + hashlib.sha256(prompt).hexdigest()
        == request.prompt_identity.uri
        and len(prompt) <= request.budget.max_prompt_bytes,
        "public_request_changed",
    )
    node = reopen_qualification_node(reader, attempt.node_lifecycle_result_identity)
    output = node.source_output
    _require(
        output is not None
        and node.source_generation.disposition is SourceGenerationDisposition.GENERATED
        and output.provenance.retained_source_identity is None
        and output.identity == attempt.source_output_identity,
        "generated_origin_required",
    )
    output.__post_init__()
    candidate, provenance, source = (
        output.candidate,
        output.provenance,
        node.source_generation,
    )
    expected = {
        "component_revision": plan.component_revision,
        "source_generation_request_identity": request.identity,
        "component_generation_plan_identity": plan.identity,
        "generation_key_identity": plan.generation_key.identity,
        "context_manifest_identity": request.context_manifest_identity,
        "prompt_identity": request.prompt_identity,
        "recipe_identity": current.recipe_identity,
        "workspace_allocation_identity": workspace.allocation_identity,
    }
    _require(
        node.component_revision == plan.component_revision
        and all(getattr(candidate, name) == value for name, value in expected.items())
        and all(
            getattr(
                provenance,
                "generated_component_revision_identity"
                if name == "component_revision"
                else name,
            )
            == value
            for name, value in expected.items()
        )
        and source.generation_plan_identity == plan.identity
        and source.generation_key_identity == plan.generation_key.identity
        and source.context_manifest_identity == request.context_manifest_identity
        and source.complexity_budget_identity == request.budget.identity
        and source.complexity_decision_identity == request.budget_decision.identity
        and source.prompt_identity == request.prompt_identity
        and source.recipe_identity == current.recipe_identity
        and source.workspace_allocation_identity == workspace.allocation_identity
        and provenance.component_lock_identity == run.component_lock_identity
        and provenance.application_root_revision_identity == run.root_revision,
        "source_context_changed",
    )
    verify_qualification_source_records(reader, candidate=candidate)
    verify_qualification_generation_records(reader, source_output=output)
    projection = _project_original_source_node(
        current, plan, provider_id=provider_id, pipeline_model=pipeline_model
    )
    _require(
        ContentIdentity.parse_uri(projection.recipe.identity)
        == current.recipe_identity,
        "current_recipe_changed",
    )
    prepared = PreparedComponentGenerationNode(
        plan,
        projection.definition,
        projection.recipe,
        PreparedComponentGenerationRequest(request, prompt),
        workspace,
    )
    invocation = project_standard_source_invocation(
        current.snapshot,
        current.execution_plan,
        prepared,
        selection=transport,
        project_authority_identity=source_authority,
        approved_project_root=approved_project_root,
    )
    manifest = reader.read_json(candidate.source_manifest_identity)
    _require(
        ContentIdentity.from_dict(manifest["invocation_identity"])
        == invocation.identity
        and canonical_json_bytes(reader.read_json(invocation.identity))
        == canonical_json_bytes(invocation.identity_document())
        and canonical_json_bytes(reader.read_json(invocation.execution_plan.identity))
        == canonical_json_bytes(invocation.execution_plan.to_dict())
        and provenance.readiness_identity == invocation.readiness_identity,
        "invocation_changed",
    )
    planned = canonical_identity(
        _planned_generation_prompt(
            projection.recipe,
            invocation.execution_plan,
            invocation.stage_request,
            transport,
            bounded_prompt=prompt,
        )
    )
    stage = reader.read_json(provenance.model_stage_output_identities[0])
    _require(
        planned == candidate.planned_coding_cli_request_identity
        and stage["coding_cli"] == provider_id
        and stage["model"] == projection.recipe.model_for(provider_id)
        and stage["coding_cli_tool_binding_identity"]
        == transport.tool_binding_identity,
        "planned_transport_changed",
    )
    current.require_unchanged()
    return node
