"""Retain actual public preparation preimages under the original live owner.

These immutable bytes are historical evidence, never execution or retry rights.
The prompt is the exact PUBLIC bounded request already delivered to its provider;
no private acceptance oracle or native output is added to that request.
"""

import hashlib

from literate_ai.application.component_generation_context import (
    PreparedComponentGenerationRequest,
)
from literate_ai.application.component_generation_preparation import (
    ComponentGenerationWorkspaceDescriptor,
    PreparedComponentGenerationNode,
)
from literate_ai.contracts.executable_components import (
    ComponentExecutionPlan,
    ComponentGenerationPlan,
)
from literate_ai.contracts.executable_components.context import (
    BoundedComponentGenerationRequest,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity


def retain_native_root_preparation(controller) -> None:
    """Keep both held plans, three preparation records, and exact public prompt.

    Context/budget/decision stay unchanged for replacement requests. Their
    decision measured the original prompt; the repair adapter separately checks
    suffix bounds, so decision.prompt_bytes need not equal replacement length.
    """
    controller.require_current()
    scope, prepared = controller.scope, controller.prepared_candidate
    if type(prepared) is not PreparedComponentGenerationNode:
        raise TypeError("original typed prepared root candidate required")
    if type(prepared.request) is not PreparedComponentGenerationRequest:
        raise TypeError("actual prepared public request required")
    request, workspace = prepared.request.request, prepared.workspace
    if (
        type(request) is not BoundedComponentGenerationRequest
        or type(workspace) is not ComponentGenerationWorkspaceDescriptor
    ):
        raise TypeError("actual bounded request and workspace descriptor required")
    request.__post_init__()
    workspace.__post_init__()
    execution_plan, plan = scope.execution_plan, prepared.plan
    if (
        type(execution_plan) is not ComponentExecutionPlan
        or type(plan) is not ComponentGenerationPlan
    ):
        raise TypeError("original held execution and generation plans required")
    execution_plan.__post_init__()
    plan.__post_init__()
    if (
        execution_plan.identity != scope.run_binding.execution_plan_identity
        or execution_plan.root_revision != scope.run_binding.root_revision
        or execution_plan.component_lock_identity
        != scope.run_binding.component_lock_identity
        or plan.identity != scope.run_binding.original_generation_plan_identity
        or plan.component_revision != scope.run_binding.root_revision
        or not any(held is plan for held in execution_plan.generation_plans)
        or request.component_generation_plan_identity != plan.identity
        or request.generation_key_identity != plan.generation_key.identity
        or request.context_manifest.component_revision != plan.component_revision
        or workspace.component_revision != plan.component_revision
        or workspace.generation_plan_identity != plan.identity
        or workspace.generation_key_identity != plan.generation_key.identity
    ):
        raise ValueError("root preparation differs from its actual node plan")
    prompt = prepared.request.prompt
    if type(prompt) is not bytes or not prompt:
        raise TypeError("actual nonempty public prompt bytes required")
    if len(prompt) > request.budget.max_prompt_bytes:
        raise ValueError("public prompt exceeds its original byte budget")
    prompt_identity = ContentIdentity.parse_uri(
        "sha256:" + hashlib.sha256(prompt).hexdigest()
    )
    if prompt_identity != request.prompt_identity:
        raise ValueError("public prompt differs from its original identity")
    allocation = {
        "schema": "literate-ai/component-workspace-allocation@1",
        "component_revision": plan.component_revision.uri,
        "generation_plan_identity": plan.identity.uri,
        "locator": workspace.locator,
    }
    if canonical_identity(allocation) != workspace.allocation_identity:
        raise ValueError("root workspace allocation preimage differs")
    descriptor = {
        "schema": "literate-ai/component-generation-workspace@1",
        "component_revision": workspace.component_revision.uri,
        "generation_plan_identity": workspace.generation_plan_identity.uri,
        "generation_key_identity": workspace.generation_key_identity.uri,
        "allocation_identity": workspace.allocation_identity.uri,
        "locator": workspace.locator,
        "workspace": workspace.workspace.value,
    }
    request_identity, workspace_identity = request.identity, workspace.identity
    execution_identity, plan_identity = execution_plan.identity, plan.identity
    if canonical_identity(descriptor) != workspace_identity:
        raise ValueError("root workspace descriptor differs")

    def current():
        controller.require_current()
        if (
            controller.scope is not scope
            or controller.prepared_candidate is not prepared
            or prepared.request.request is not request
            or prepared.request.prompt is not prompt
            or prepared.workspace is not workspace
            or prepared.plan is not plan
            or scope.execution_plan is not execution_plan
            or request.identity != request_identity
            or workspace.identity != workspace_identity
            or execution_plan.identity != execution_identity
            or plan.identity != plan_identity
        ):
            raise ValueError("root preparation changed during retention")

    for record, expected in (
        (request, request_identity),
        (allocation, workspace.allocation_identity),
        (descriptor, workspace_identity),
        (execution_plan, execution_identity),
        (plan, plan_identity),
    ):
        current()
        if scope.retain_record(record) != expected:
            raise ValueError("retained root preparation identity differs")
        current()
    current()
    if scope.retain_bytes(prompt) != prompt_identity:
        raise ValueError("retained public prompt identity differs")
    current()
