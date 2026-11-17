"""Bound SDK generation DATA over a static graph, without live admission authority."""

from dataclasses import dataclass, replace

from literate_ai.adapters.models import GenerationRecipe
from literate_ai.adapters.models.node_sdk_recipe import RecipeNodeSDKProvider
from literate_ai.adapters.node_library_projection import (
    project_commonjs_library_declarations,
)
from literate_ai.adapters.node_library_verification import NodeLibraryChecks
from literate_ai.application.component_generation_context import (
    PromptSegmentInput,
    prepare_component_generation_context,
)
from literate_ai.application.component_generation_preparation import (
    PreparedComponentGenerationNode,
)
from literate_ai.application.source_generation_scheduling import (
    validate_prepared_component_generation_node,
)
from literate_ai.contracts import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.executable_components import (
    ComponentExecutionPlan,
    DependencyInputKind,
)
from literate_ai.contracts.executable_components.context import ContextAuthorityKind
from literate_ai.contracts.executable_components.standard_command_profiles import (
    StandardNodeSDKCommandProfile,
)


def node_sdk_provider_generation_data(
    scope,
    checks,
    compiler,
    verifier_request,
    *,
    environment,
    require_current,
    observe_process=None,
):
    """Check public-root closure inside the original guarded verifier consumer.

    This does not authenticate a checks DTO or authorize compiler execution. The
    lifecycle supplies original output and retains the exact execution grant.
    Oracle consumer imports cannot select which declaration bytes reach a model.
    """
    surface = scope.contract.library_import_surface
    if (
        type(checks) is not NodeLibraryChecks
        or checks.subject != scope.export.component_revision
        or checks.artifact != scope.export.identity
        or checks.surface != surface.identity
        or checks.declarations.compiler != compiler.identity
        or checks.runtime.oracle != checks.oracle
    ):
        raise ValueError("SDK generation checks differ from exact provider inputs")
    require_current()
    projection = project_commonjs_library_declarations(
        scope.export, surface, scope.files
    )
    roots = tuple(path for path, _symbols in projection.public_declarations)
    closure = compiler.run(
        operation="check",
        files=projection.files,
        roots=roots,
        environment=environment,
        require_current=require_current,
        observe_process=observe_process,
    )
    by_mode = dict(closure.inputs_by_mode)
    if (
        not closure.success
        or set(by_mode) != {"node16", "nodenext"}
        or any(not set(roots) <= set(paths) for paths in by_mode.values())
    ):
        raise ValueError("SDK public declaration roots lack an exact compiler closure")
    prefix = (
        "node_modules/"
        + surface.package
        + "/_providers/"
        + scope.export.component_revision.digest
        + "/artifact/"
    )
    used = {path[len(prefix) :] for path in closure.inputs if path.startswith(prefix)}
    files = {item.path: item.content for item in scope.files}
    if not used or not used <= files.keys():
        raise ValueError("SDK generation lacks original compiler declaration closure")
    return RecipeNodeSDKProvider(
        scope.export,
        surface,
        scope.acceptance.identity,
        checks.oracle,
        checks.identity,
        compiler.identity,
        ContentIdentity.parse_uri(compiler.node.identity),
        canonical_identity(verifier_request.to_dict()),
        canonical_identity(
            {
                "schema": "literate-ai/node-sdk-public-declaration-closure@1",
                "projection": projection.identity.uri,
                "compiler": compiler.identity.uri,
                "roots": list(roots),
                "inputs_by_mode": [
                    [mode, list(paths)] for mode, paths in closure.inputs_by_mode
                ],
            }
        ),
        tuple((name, files[name].decode("utf-8")) for name in sorted(used)),
    )


@dataclass(frozen=True, slots=True)
class BoundNodeSDKGenerationInvocation:
    """Exact invocation facts, never a source-cache membership or live capability."""

    base_recipe: ContentIdentity
    profile: ContentIdentity
    target: ContentIdentity
    prepared: PreparedComponentGenerationNode

    def __post_init__(self):
        if any(
            type(value) is not ContentIdentity
            for value in (self.base_recipe, self.profile, self.target)
        ):
            raise TypeError("bound SDK invocation requires exact typed identities")
        validate_prepared_component_generation_node(self.prepared)
        if not self.prepared.recipe.node_sdk_providers:
            raise ValueError("bound SDK invocation requires exact provider records")
        if dict(self.prepared.recipe.resolved_inputs).get(
            "node_sdk_profile"
        ) != self.profile.uri or any(
            item.artifact.target_identity != self.target
            for item in self.prepared.recipe.node_sdk_providers
        ):
            raise ValueError(
                "bound SDK invocation differs from exact profile or target"
            )

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/bound-node-sdk-generation-invocation@1",
                "static_plan": self.prepared.plan.identity.uri,
                "base_recipe": self.base_recipe.uri,
                "profile": self.profile.uri,
                "target": self.target.uri,
                "bound_recipe": self.prepared.recipe.identity,
                "request": self.prepared.request.request.identity.uri,
                "workspace": self.prepared.workspace.allocation_identity.uri,
                "providers": [
                    item.identity.uri
                    for item in self.prepared.recipe.node_sdk_providers
                ],
            }
        )


def bind_node_sdk_generation_invocation(
    execution_plan, prepared, *, profile, target, providers, require_current
):
    """Construct a new recipe/request before cache lookup; preserve the static plan.

    The caller retains original provider/verifier custody. Returned DATA cannot
    authorize later model execution, cache publication, builds or remote adoption.
    """
    if (
        type(execution_plan) is not ComponentExecutionPlan
        or type(profile) is not StandardNodeSDKCommandProfile
        or type(target) is not ContentIdentity
        or not callable(require_current)
    ):
        raise TypeError(
            "SDK generation requires a static plan, exact policy and live owner"
        )
    require_current()
    validate_prepared_component_generation_node(prepared)
    recipe = prepared.recipe
    if (
        type(recipe) is not GenerationRecipe
        or recipe.component_lock_identity != execution_plan.component_lock_identity
        or prepared.plan not in execution_plan.generation_plans
        or recipe.node_sdk_providers
        or dict(recipe.resolved_inputs).get("node_sdk_profile") is not None
    ):
        raise ValueError("SDK invocation differs from its original static preparation")
    if (
        type(providers) is not tuple
        or not providers
        or len(providers) > 32
        or any(type(item) is not RecipeNodeSDKProvider for item in providers)
    ):
        raise ValueError("SDK invocation requires bounded exact provider records")
    generation_edges = {
        (edge.provider_revision, edge.capability, edge.public_interface_identity)
        for edge in prepared.plan.direct_generation_edges
    }
    build_edges = {
        (edge.provider_revision, edge.capability)
        for action in execution_plan.action_plans
        for edge in action.dependency_edges
        if edge.consumer_revision == prepared.plan.component_revision
        and edge.semantics.consumed_input is DependencyInputKind.ARTIFACT_EXPORT
    }
    for dependency in recipe.library_dependencies:
        edge = (
            dependency.provider_component_revision,
            dependency.capability,
            dependency.interface_identity,
        )
        if edge not in generation_edges or edge[:2] not in build_edges:
            raise ValueError(
                "SDK imports require the same exact generation and build edge"
            )
    if any(item.artifact.target_identity != target for item in providers):
        raise ValueError("SDK generation provider target differs from its consumer")
    bound_recipe = replace(
        recipe,
        node_sdk_providers=providers,
        resolved_inputs=(
            *recipe.resolved_inputs,
            ("node_sdk_profile", profile.identity.uri),
        ),
    )
    original = prepared.request
    manifest = original.request.context_manifest
    segments = []
    offset = 0
    for segment in manifest.segments:
        content = original.prompt[offset : offset + segment.byte_count]
        offset += segment.byte_count
        if segment.index == 0:
            if content != recipe.prompt(
                include_locked_authority_documents=False
            ).encode("utf-8"):
                raise ValueError(
                    "SDK invocation requires the exact recipe framework envelope"
                )
            continue
        segments.append(
            PromptSegmentInput(
                segment.authority_kind,
                segment.source_component_revision,
                segment.reason,
                segment.content_identity,
                content,
            )
        )
    if offset != len(original.prompt):
        raise ValueError("SDK invocation original context boundaries differ")
    bound_request = prepare_component_generation_context(
        prepared.plan,
        framework_envelope=bound_recipe.prompt(
            include_locked_authority_documents=False
        ).encode("utf-8"),
        authority_segments=tuple(segments),
        budget=original.request.budget,
        node_sdk_provider_segments=tuple(
            PromptSegmentInput(
                ContextAuthorityKind.LOCAL_NODE_SDK_PROVIDER_METADATA,
                prepared.plan.component_revision,
                "verified direct SDK provider and public declaration closure",
                item.identity,
                canonical_json_bytes(item.to_dict()),
            )
            for item in sorted(providers, key=lambda item: item.identity.uri)
        ),
    )
    bound = replace(prepared, recipe=bound_recipe, request=bound_request)
    validate_prepared_component_generation_node(bound, expected_plan=prepared.plan)
    require_current()
    return BoundNodeSDKGenerationInvocation(
        ContentIdentity.parse_uri(recipe.identity), profile.identity, target, bound
    )
