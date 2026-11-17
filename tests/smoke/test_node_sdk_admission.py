"""Real accepted provider custody around SDK operation fixtures.

The consumer plan is inert contract DATA. No generated SDK, selected public
Flavor, actual model output or end-to-end lifecycle qualification is claimed.
"""

import os
import unittest
from concurrent.futures import Future
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from unittest import mock

from literate_ai.adapters.generation_preparation import (
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.models import GenerationRecipe
from literate_ai.adapters.models.coding_cli import RecipeLibraryDependency
from literate_ai.adapters.node_sdk_admission import (
    LocalNodeSDKGenerationAdmission,
    NodeSDKAdmissionError,
)
from literate_ai.application.component_generation_context import (
    PromptSegmentInput,
    prepare_component_generation_context,
)
from literate_ai.application.component_generation_preparation import (
    ComponentGenerationWorkspaceDescriptor,
    PreparedComponentGenerationNode,
)
from literate_ai.contracts import (
    LibraryCapabilityImport,
    LibraryImportSurface,
    canonical_identity,
)
from literate_ai.contracts.capabilities import DependencyKind
from literate_ai.contracts.executable_components import (
    ComponentActionPhase,
    ComponentActionPlan,
    ComponentExecutionPlan,
    ComponentTopologicalLayer,
    ContextAuthorityKind,
    ExecutableComponentEdge,
)
from literate_ai.contracts.executable_components.standard_command_profiles import (
    StandardNodeSDKCommandProfile,
)
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.node_sdk import NodeSDKExportDeclaration
from literate_ai.projects import PinnedInputClosureError
from literate_ai.security.policy import (
    AuthorizationError,
    BuildAuthorization,
    SecurityProfile,
)
from tests.smoke import test_node_provider_lifecycle as provider_fixture


@unittest.skipUnless(
    provider_fixture.os.name == "posix"
    and provider_fixture.os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and provider_fixture.shutil.which("node"),
    "requires selected compiler and POSIX provider custody",
)
class NodeSDKAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        provider_fixture.NodeProviderLifecycleTests.setUpClass.__func__(cls)

    def setUp(self):
        self.fixture = f = provider_fixture.NodeProviderLifecycleTests()
        f.node, f.compiler, f.environment = self.node, self.compiler, self.environment
        f.setUp()
        self.addCleanup(f.doCleanups)
        provider = f.accepted.build.exports[0]
        producer_plan = next(
            item
            for item in f.execution.generation_plans
            if item.component_revision == f.revision.identity
        )
        projection = LockedComponentNodePreparationAdapter().project(
            f.snapshot, producer_plan
        )
        provider_surface = f.ports.contracts[
            provider.component_revision.uri
        ].library_import_surface
        capability = provider_surface.capabilities[0]
        self.consumer_revision = canonical_identity(
            "inert SDK consumer fixture, no generation qualification"
        )
        graph = canonical_identity("inert SDK operation graph fixture")
        interface = capability.interface_identity
        generation_edge = ExecutableComponentEdge(
            self.consumer_revision,
            provider.component_revision,
            "provider",
            capability.capability,
            DependencyKind.GENERATION,
            interface,
        )
        build_edge = replace(
            generation_edge, kind=DependencyKind.BUILD, public_interface_identity=None
        )
        consumer_plan = replace(
            producer_plan,
            component_graph_identity=graph,
            component_revision=self.consumer_revision,
            generation_key=replace(
                producer_plan.generation_key,
                exported_public_interface_identities=(),
                direct_public_interface_identities=(interface,),
            ),
            direct_generation_edges=(generation_edge,),
        )
        producer_plan = replace(producer_plan, component_graph_identity=graph)
        revisions = tuple(
            sorted(
                (provider.component_revision, self.consumer_revision),
                key=lambda item: item.uri,
            )
        )
        actions = []
        for action in f.execution.action_plans:
            edges = (
                (generation_edge,)
                if action.phase is ComponentActionPhase.GENERATE
                else (build_edge,)
                if action.phase is ComponentActionPhase.BUILD
                else ()
            )
            layers = (
                (
                    ComponentTopologicalLayer(0, (provider.component_revision,)),
                    ComponentTopologicalLayer(1, (self.consumer_revision,)),
                )
                if edges
                else (ComponentTopologicalLayer(0, revisions),)
            )
            actions.append(
                ComponentActionPlan(graph, action.phase, revisions, edges, layers)
            )
        self.execution = ComponentExecutionPlan(
            graph,
            self.consumer_revision,
            f.execution.planner_identity,
            tuple(
                sorted(
                    (producer_plan, consumer_plan),
                    key=lambda item: item.component_revision.uri,
                )
            ),
            tuple(actions),
        )
        sdk_surface = LibraryImportSurface(
            "typescript",
            "fixture-sdk",
            (
                LibraryCapabilityImport(
                    capability.capability, interface, "fixture-sdk", capability.symbols
                ),
            ),
            node_sdk_exports=(NodeSDKExportDeclaration("fixture-sdk", "index"),),
        )
        recipe = GenerationRecipe(
            "fixture-sdk",
            "fixture-sdk",
            projection.recipe.documents,
            graph,
            skills=projection.recipe.skills,
            library_import_surface=sdk_surface,
            library_dependencies=(
                RecipeLibraryDependency(
                    provider.component_revision,
                    capability.capability,
                    interface,
                    provider_surface,
                ),
            ),
        )
        segments = [
            replace(segment, source_component_revision=self.consumer_revision)
            for segment in projection.authority_segments
            if segment.authority_kind is not ContextAuthorityKind.LOCAL_PUBLIC_INTERFACE
        ]
        reference = f.revision.public_interfaces[0]
        segments.append(
            PromptSegmentInput(
                ContextAuthorityKind.DIRECT_PUBLIC_INTERFACE,
                provider.component_revision,
                "exact public provider interface",
                interface,
                f.snapshot.component_content(f.revision.authoring_identity, reference),
            )
        )
        request = prepare_component_generation_context(
            consumer_plan,
            framework_envelope=recipe.prompt(
                include_locked_authority_documents=False
            ).encode(),
            authority_segments=tuple(segments),
            budget=self._budget(),
        )
        workspace = ComponentGenerationWorkspaceDescriptor(
            self.consumer_revision,
            consumer_plan.identity,
            consumer_plan.generation_key.identity,
            canonical_identity("fresh SDK fixture allocation"),
            "inert-operation-workspace",
        )
        self.prepared = PreparedComponentGenerationNode(
            consumer_plan, object(), recipe, request, workspace
        )
        self.consumer = replace(
            f.ports.contracts[provider.component_revision.uri],
            component_revision=self.consumer_revision,
            language_compiler_identity=self.compiler.identity,
            language_runtime_identity=ContentIdentity.parse_uri(self.node.identity),
            artifact_export=replace(
                f.ports.contracts[provider.component_revision.uri].artifact_export,
                export_id="sdk",
            ),
            library_import_surface=sdk_surface,
        )
        f.ports.contracts[self.consumer_revision.uri] = self.consumer
        self.grants = []
        self.policy_alive = True

    def _budget(self):
        from tests.support.fixtures_test_component_generation_context import _budget

        return _budget()

    def authorize(self, request):
        now = self.fixture.ports.clock()
        grant = BuildAuthorization(
            "explicit-operation-fixture-grant",
            canonical_identity(request.to_dict()).uri,
            canonical_identity(request.to_dict()).uri,
            request.effective_revision_digest,
            "fixture-operator",
            "authorize exact fixture verifier only",
            SecurityProfile.CONSTRAINED,
            request.requested_privileges,
            now,
            now + timedelta(minutes=5),
        )
        self.grants.append(grant)
        return grant

    def owner(self):
        if not self.policy_alive:
            raise ValueError("SDK policy ended")

    def admission(self, **changes):
        f = self.fixture
        args = dict(
            ports=f.ports,
            consumer=self.consumer,
            profile=StandardNodeSDKCommandProfile(
                "node-sdk", "npm", "typescript", "src", ("LICENSE",)
            ),
            compiler=self.compiler,
            revisions={f.revision.identity.uri: f.revision},
            oracles={f.revision.identity.uri: f.oracle},
            authorize_verifier=self.authorize,
            require_current=self.owner,
            environment=self.environment,
        )
        args.update(changes)
        return LocalNodeSDKGenerationAdmission(**args)

    def invoke(self, admission, consume, **changes):
        return admission.with_invocation(
            self.execution,
            self.prepared,
            (self.fixture.accepted,),
            consume=consume,
            **changes,
        )

    def test_real_provider_operation_and_fresh_exact_renewal_keep_original_binding(
        self,
    ):
        admission = self.admission()
        escaped = []

        def consume(invocation, guard):
            guard()
            escaped.append(guard)
            self.assertEqual(
                dict(invocation.prepared.recipe.resolved_inputs)[
                    "node_sdk_command_contract"
                ],
                self.consumer.identity.uri,
            )
            return invocation

        original = self.invoke(admission, consume)
        with self.assertRaisesRegex(NodeSDKAdmissionError, "scope ended"):
            escaped[0]()
        refreshed = self.invoke(admission, consume, expected=original)
        self.assertEqual(original.identity, refreshed.identity)
        self.assertEqual(len(self.grants), 2)
        self.assertEqual(self.fixture.ports._library_provider_scope_count, 0)
        self.assertEqual(self.fixture.ports._library_provider_scopes, {})

    def test_no_grant_or_changed_policy_cannot_start_verification(self):
        admission = self.admission(authorize_verifier=lambda _: None)
        with mock.patch.object(
            self.fixture.ports,
            "with_node_sdk_provider_generation_data",
            wraps=self.fixture.ports.with_node_sdk_provider_generation_data,
        ) as verify:
            with self.assertRaises(TypeError):
                self.invoke(admission, lambda *_: self.fail("operation ran"))
            verify.assert_not_called()
        admission = self.admission()
        admission.require_current = lambda: None
        with self.assertRaises(NodeSDKAdmissionError):
            self.invoke(admission, lambda *_: self.fail("operation ran"))

    def test_mismatched_historical_invocation_is_not_retagged_or_consumed(self):
        admission = self.admission()
        original = self.invoke(admission, lambda invocation, _guard: invocation)
        foreign = replace(original, base_recipe=canonical_identity("other base recipe"))
        with self.assertRaisesRegex(NodeSDKAdmissionError, "original invocation"):
            self.invoke(
                admission,
                lambda *_: self.fail("foreign invocation consumed"),
                expected=foreign,
            )
        self.assertEqual(original.base_recipe.uri, self.prepared.recipe.identity)

    def test_post_scope_grant_loss_withholds_operation_result(self):
        completed = False

        def owner():
            self.owner()
            if (
                completed
                and self.grants
                and not self.fixture.ports._library_provider_scopes
            ):
                object.__setattr__(self.grants[-1], "revoked", True)

        admission = self.admission(require_current=owner)

        def consume(_invocation, guard):
            nonlocal completed
            guard()
            completed = True
            return "must not escape after scope cleanup"

        with self.assertRaises(AuthorizationError):
            self.invoke(admission, consume)
        self.assertTrue(completed)

    def test_owner_loss_during_post_scope_oracle_read_withholds_result(self):
        from literate_ai.adapters import node_sdk_admission as module

        original = module.capture_loaded_node_library_verifier_inputs
        observed = []

        @contextmanager
        def capture(oracle):
            with original(oracle) as scope:

                def read():
                    scope()
                    if not self.fixture.ports._library_provider_scopes:
                        observed.append(True)
                        self.policy_alive = False

                yield scope._replace(require_unchanged=read)

        with mock.patch.object(
            module, "capture_loaded_node_library_verifier_inputs", capture
        ):
            with self.assertRaisesRegex(ValueError, "policy ended"):
                self.invoke(self.admission(), lambda *_: "must not escape")
        self.assertEqual(observed, [True])

    def test_oracle_write_in_final_owner_callback_withholds_result(self):
        completed = False
        changed = []
        # Locate the actual loader-owned document; fixture names are private.
        from literate_ai.adapters.node_library_acceptance import _LOADED

        witness = _LOADED[id(self.fixture.oracle)]
        oracle_path = next(iter(witness.authority._entries.values())).path

        def owner():
            self.owner()
            if completed and not self.fixture.ports._library_provider_scopes:
                # The second post-scope callback follows the final byte reads.
                changed.append(True)
                if len(changed) == 2:
                    before = oracle_path.stat()
                    content = oracle_path.read_bytes()
                    oracle_path.write_bytes(content)
                    os.utime(oracle_path, ns=(before.st_atime_ns, before.st_mtime_ns))

        def consume(*_):
            nonlocal completed
            completed = True
            return "must not escape"

        with self.assertRaisesRegex(PinnedInputClosureError, "changed before close"):
            self.invoke(self.admission(require_current=owner), consume)
        self.assertEqual(len(changed), 2)

    def test_asynchronous_operation_is_rejected_before_verification(self):
        async def consume(*_args):
            self.fail("async operation ran")

        with self.assertRaises(TypeError):
            self.invoke(self.admission(), consume)
        self.assertEqual(self.grants, [])

    def test_hidden_future_cannot_escape_live_ownership(self):
        with self.assertRaisesRegex(TypeError, "finish synchronously"):
            self.invoke(self.admission(), lambda *_: Future())
