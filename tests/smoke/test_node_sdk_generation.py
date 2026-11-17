"""Bound recipe/context DATA fixtures; no model or SDK admission qualification."""

import unittest
from dataclasses import replace
from unittest import mock

from literate_ai.adapters.models import GenerationRecipe, RecipeDocument
from literate_ai.adapters.models.coding_cli import RecipeLibraryDependency
from literate_ai.adapters.models.node_sdk_recipe import RecipeNodeSDKProvider
from literate_ai.adapters.node_sdk_generation import bind_node_sdk_generation_invocation
from literate_ai.application.component_generation_context import (
    PromptSegmentInput,
    bind_component_generation_context_cache_key,
    prepare_component_generation_context,
)
from literate_ai.application.component_generation_preparation import (
    ComponentGenerationWorkspaceDescriptor,
    PreparedComponentGenerationNode,
)
from literate_ai.application.standard_project_lifecycle import (
    StandardProjectLifecycleError,
    StandardProjectLifecycleService,
    _rebind_standard_source_generation,
)
from literate_ai.contracts import (
    ArtifactExport,
    BlobRef,
    ContentIdentity,
    LibraryCapabilityImport,
    LibraryImportSurface,
    canonical_identity,
)
from literate_ai.contracts.capabilities import DependencyKind
from literate_ai.contracts.executable_components import (
    ComponentActionPhase,
    ContextAuthorityKind,
    ContextVisibility,
    SourceGenerationResumeCandidate,
)
from literate_ai.contracts.executable_components.context_journal import (
    ForwardGenerationContextSegmentBinding,
)
from literate_ai.contracts.executable_components.standard_command_profiles import (
    StandardNodeSDKCommandProfile,
)
from literate_ai.contracts.generation_cache import (
    SourceCacheModelBinding,
    SourceDerivationCacheKey,
)
from literate_ai.contracts.node_sdk import (
    CommonJSModuleDeclaration,
    NodeSDKExportDeclaration,
)
from tests.smoke.test_standard_project_lifecycle import LifecyclePorts, _Recipe
from tests.support.fixtures_test_coding_cli_generation import generation_skill
from tests.support.fixtures_test_component_execution_planning import _diamond_lock
from tests.support.fixtures_test_component_generation_scheduling import (
    _prepared_execution,
)
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


class NodeSDKGenerationDataTests(unittest.TestCase):
    def setUp(self):
        lock = _diamond_lock()
        execution, requests = _prepared_execution(lock)
        names = {
            item.revision.coordinate.name: item.revision.identity for item in lock.nodes
        }
        plan = next(
            item
            for item in execution.generation_plans
            if item.component_revision == names["pricing"]
        )
        generation_action = next(
            item
            for item in execution.action_plans
            if item.phase is ComponentActionPhase.GENERATE
        )
        build_edges = tuple(
            sorted(
                (
                    replace(
                        edge, kind=DependencyKind.BUILD, public_interface_identity=None
                    )
                    for node in execution.generation_plans
                    for edge in node.direct_generation_edges
                ),
                key=lambda edge: (
                    edge.consumer_revision.uri,
                    edge.provider_revision.uri,
                    edge.requirement_id,
                    edge.kind.value,
                ),
            )
        )
        self.execution = replace(
            execution,
            action_plans=tuple(
                replace(
                    generation_action,
                    phase=ComponentActionPhase.BUILD,
                    dependency_edges=build_edges,
                )
                if action.phase is ComponentActionPhase.BUILD
                else action
                for action in execution.action_plans
            ),
        )
        edge = plan.direct_generation_edges[0]
        surface = LibraryImportSurface(
            "javascript",
            "money",
            (
                LibraryCapabilityImport(
                    edge.capability, edge.public_interface_identity, "money", ("add",)
                ),
            ),
            declarations=(
                CommonJSModuleDeclaration(
                    "money", "source/money/api.js", "source/money/api.d.ts"
                ),
            ),
        )
        self.target = canonical_identity("synthetic target")
        artifact = ArtifactExport(
            "library",
            edge.provider_revision,
            "library",
            canonical_identity("abi"),
            self.target,
            "application/zip",
            canonical_identity("producer"),
            canonical_identity("source"),
            canonical_identity("tool"),
            canonical_identity("authorization data"),
            (),
            BlobRef("0" * 64, 0, media_type="application/zip"),
        )
        self.provider = RecipeNodeSDKProvider(
            artifact,
            surface,
            *(
                canonical_identity(name)
                for name in (
                    "acceptance",
                    "oracle",
                    "checks",
                    "compiler",
                    "node",
                    "verifier policy",
                    "declaration closure",
                )
            ),
            (
                (
                    "source/money/api.d.ts",
                    "export declare function add(a:number,b:number):number;\n",
                ),
            ),
        )
        sdk_surface = LibraryImportSurface(
            "typescript",
            "money-sdk",
            (
                LibraryCapabilityImport(
                    "sdk", canonical_identity("sdk interface"), "money-sdk", ("add",)
                ),
            ),
            node_sdk_exports=(NodeSDKExportDeclaration("money-sdk", "index"),),
        )
        recipe = GenerationRecipe(
            "money-sdk",
            "money-sdk",
            (RecipeDocument.create("component.md", "# SDK data fixture\n"),),
            execution.component_lock_identity,
            skills=(generation_skill(),),
            library_import_surface=sdk_surface,
            library_dependencies=(
                RecipeLibraryDependency(
                    edge.provider_revision,
                    edge.capability,
                    edge.public_interface_identity,
                    surface,
                ),
            ),
        )
        workspace = ComponentGenerationWorkspaceDescriptor(
            plan.component_revision,
            plan.identity,
            plan.generation_key.identity,
            canonical_identity("fresh allocation"),
            "opaque-fixture-workspace",
        )
        original_request = requests[plan.component_revision.uri]
        segments = []
        offset = 0
        for segment in original_request.request.context_manifest.segments:
            content = original_request.prompt[offset : offset + segment.byte_count]
            offset += segment.byte_count
            if segment.index:
                segments.append(
                    PromptSegmentInput(
                        segment.authority_kind,
                        segment.source_component_revision,
                        segment.reason,
                        segment.content_identity,
                        content,
                    )
                )
        request = prepare_component_generation_context(
            plan,
            framework_envelope=recipe.prompt(
                include_locked_authority_documents=False
            ).encode(),
            authority_segments=tuple(segments),
            budget=original_request.request.budget,
        )
        self.prepared = PreparedComponentGenerationNode(
            plan, object(), recipe, request, workspace
        )
        self.profile = StandardNodeSDKCommandProfile(
            "node-sdk", "npm", "typescript", "src", ("LICENSE",)
        )

    def bind(self, **changes):
        args = dict(
            profile=self.profile,
            target=self.target,
            providers=(self.provider,),
            require_current=lambda: None,
        )
        args.update(changes)
        return bind_node_sdk_generation_invocation(
            self.execution, self.prepared, **args
        )

    def key(self, prepared):
        value = SourceDerivationCacheKey(
            ContentIdentity.parse_uri(prepared.recipe.identity),
            self.execution.identity,
            canonical_identity("coding tool"),
            SourceCacheModelBinding("fixture", "fixture"),
            prepared.request.request.prompt_identity,
        )
        return bind_component_generation_context_cache_key(
            value, prepared.request
        ).identity

    def test_static_plan_and_original_authority_stay_exact_while_cache_binding_changes(
        self,
    ):
        bound = self.bind()
        self.assertIs(bound.prepared.plan, self.prepared.plan)
        self.assertIs(bound.prepared.workspace, self.prepared.workspace)
        self.assertEqual(bound.base_recipe.uri, self.prepared.recipe.identity)
        self.assertNotEqual(
            bound.prepared.recipe.identity, self.prepared.recipe.identity
        )
        self.assertNotEqual(self.key(bound.prepared), self.key(self.prepared))
        original_segments = self.prepared.request.request.context_manifest.segments[1:]
        segments = bound.prepared.request.request.context_manifest.segments
        self.assertEqual(segments[1:-1], original_segments)
        self.assertIs(
            segments[-1].authority_kind,
            ContextAuthorityKind.LOCAL_NODE_SDK_PROVIDER_METADATA,
        )
        self.assertIs(segments[-1].visibility, ContextVisibility.LOCAL_AUTHORITY)
        declaration = self.provider.declarations[0][1].encode()
        # JSON encodes the newline, but the public declaration occurs only once.
        self.assertEqual(bound.prepared.request.prompt.count(declaration.rstrip()), 1)
        self.assertEqual(bound.identity, self.bind().identity)
        catalog = SchemaCatalog()
        catalog.validate(
            "urn:literate-ai:schema:v2:component-generation-context-contracts",
            bound.prepared.request.request.to_dict(),
        )
        segment = segments[-1]
        evidence = ForwardGenerationContextSegmentBinding(
            segment.index,
            segment.authority_kind,
            segment.source_component_revision,
            segment.content_identity,
            segment.byte_count,
            segment.estimated_tokens,
            segment.visibility,
        )
        catalog.validate(evidence.SCHEMA, evidence.to_dict())

    def test_every_provider_evidence_change_invalidates_recipe_context_and_cache(self):
        original = self.bind()
        for field in (
            "acceptance",
            "oracle",
            "checks",
            "compiler",
            "node",
            "verifier_policy",
            "declaration_closure",
        ):
            with self.subTest(field=field):
                provider = replace(
                    self.provider, **{field: canonical_identity("changed " + field)}
                )
                changed = self.bind(providers=(provider,))
                self.assertNotEqual(changed.identity, original.identity)
                self.assertNotEqual(
                    self.key(changed.prepared), self.key(original.prepared)
                )
        provider = replace(
            self.provider,
            declarations=(
                (
                    "source/money/api.d.ts",
                    "export declare function add(a:number,b:number):1;\n",
                ),
            ),
        )
        self.assertNotEqual(
            self.key(self.bind(providers=(provider,)).prepared),
            self.key(original.prepared),
        )

    def test_missing_build_edge_wrong_target_or_extra_provider_refuses_binding(self):
        original = self.execution
        self.execution = replace(
            original,
            action_plans=tuple(
                replace(action, dependency_edges=())
                if action.phase is ComponentActionPhase.BUILD
                else action
                for action in original.action_plans
            ),
        )
        with self.assertRaisesRegex(ValueError, "generation and build edge"):
            self.bind()
        self.execution = original
        with self.assertRaisesRegex(ValueError, "target"):
            self.bind(target=canonical_identity("other target"))
        with self.assertRaises(ValueError):
            self.bind(providers=(self.provider, self.provider))

    def test_rebinding_same_preparation_or_malformed_declarations_is_refused(self):
        self.prepared = self.bind().prepared
        with self.assertRaisesRegex(ValueError, "original static preparation"):
            self.bind()
        for declarations in (
            (),
            (("../private.d.ts", "text"),),
            (("source/money/api.js", "implementation"),),
        ):
            with self.subTest(declarations=declarations), self.assertRaises(ValueError):
                replace(self.provider, declarations=declarations)

    def test_closing_owner_loss_or_prompt_budget_prevents_invocation_publication(self):
        calls = 0

        def owner():
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("owner ended")

        with self.assertRaisesRegex(ValueError, "owner ended"):
            self.bind(require_current=owner)
        request = self.prepared.request
        budget = replace(request.request.budget, max_prompt_bytes=len(request.prompt))
        decision = replace(
            request.request.budget_decision, budget_identity=budget.identity
        )
        # Bound metadata must be metered; a new invocation cannot inherit an old
        # allowed complexity decision when the expanded prompt exceeds its budget.
        self.prepared = replace(
            self.prepared,
            request=replace(
                request,
                request=replace(
                    request.request,
                    budget=budget,
                    budget_decision=decision,
                    complexity_decision_identity=decision.identity,
                ),
            ),
        )
        with self.assertRaises(ValueError):
            self.bind()

    def test_static_source_paths_refuse_bound_data_before_reading_cache_or_resume(self):
        bound = self.bind()
        for prepared in (self.prepared, bound.prepared):
            for field in (
                "candidate",
                "source_cache_membership",
                "source_generation_resume",
            ):
                for regenerate in (False, True):
                    with self.subTest(
                        bound=prepared is bound.prepared,
                        field=field,
                        regenerate=regenerate,
                    ):
                        args = dict(
                            candidate=None,
                            source_cache_membership=None,
                            source_generation_resume=None,
                            regenerate=regenerate,
                        )
                        poison = mock.Mock()
                        poison.__bool__ = mock.Mock(
                            side_effect=AssertionError("source cache touched")
                        )
                        args[field] = poison
                        with self.assertRaisesRegex(
                            StandardProjectLifecycleError,
                            "live bound-invocation admission",
                        ):
                            StandardProjectLifecycleService._source_generation_candidate(
                                self.execution, prepared, **args
                            )

    def test_old_source_cannot_be_retagged_with_new_sdk_recipe_identity(self):
        # These are valid typed source fixture records, not actual model output.
        names = {
            node.component_revision.uri: "pricing"
            for node in self.execution.generation_plans
        }
        ports = LifecyclePorts(self.execution, names)
        original = replace(
            self.prepared,
            recipe=_Recipe(
                ContentIdentity.parse_uri(self.prepared.recipe.identity),
                self.execution.component_lock_identity,
            ),
        )
        output = ports(original)
        generation = SourceGenerationResumeCandidate(
            output,
            output.identity,
            original.request.request.budget.identity,
            original.request.request.complexity_decision_identity,
        )
        bound = self.bind()
        with self.assertRaisesRegex(
            StandardProjectLifecycleError, "exact planned Component and recipe"
        ):
            _rebind_standard_source_generation(
                self.execution,
                bound.prepared,
                generation,
                input_identity=canonical_identity("old cache membership"),
                custody_schema="fixture-custody@1",
                require_exact_generation=False,
            )
