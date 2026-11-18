"""Deterministic injected-port scheduling; no native/generated SDK qualification.

The admission double is a trusted host port, not a provider-verification fixture.
Real provider/oracle/grant custody is covered separately by node_sdk_admission.
"""

import tempfile
import unittest
from contextvars import copy_context
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.candidate_repair import (
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.application.standard_node_sdk_admission import (
    capture_node_sdk_finalization,
    capture_node_sdk_lifecycle,
    require_node_sdk_build_intent,
    require_node_sdk_source,
    run_node_sdk_lifecycle,
)
from literate_ai.application.standard_project_lifecycle import (
    StandardProjectLifecycleError,
    StandardProjectLifecycleService,
)
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.contracts.standard_root_integration import (
    StandardRootIntegrationEvidence,
)
from tests.smoke import test_node_sdk_generation as generation_fixture
from tests.smoke.test_standard_project_lifecycle import (
    LifecyclePorts,
    _decision,
    _names,
    _prepared_nodes,
    _Recipe,
    _service,
)
from tests.support.fixtures_test_component_execution_planning import _diamond_lock
from tests.support.fixtures_test_component_generation_scheduling import (
    _prepared_execution,
)


class _Admission:
    def __init__(self, fixture, ports=None):
        self.fixture, self.ports = fixture, ports
        self.calls = 0
        self.alive = True
        self.drift = False
        self.revoke_publication = False

    def owner(self):
        if not self.alive:
            raise ValueError("injected owner ended")

    def with_invocation(self, execution, prepared, receipts, *, consume, expected=None):
        self.calls += 1
        if self.ports is not None:
            for dependency in self.fixture.prepared.recipe.library_dependencies:
                assert (
                    "accept",
                    self.ports.names[dependency.provider_component_revision.uri],
                ) in self.ports.events
            self.ports._record(
                "sdk-admission", self.ports.names[prepared.plan.component_revision.uri]
            )
        invocation = self.fixture.bind()
        if expected is not None:
            if self.revoke_publication:
                self.alive = False
            if self.drift:
                invocation = replace(
                    invocation, base_recipe=canonical_identity("drift")
                )
        self.owner()
        result = consume(invocation, self.owner)
        self.owner()
        return result

    def require_build_intent(
        self, invocation, execution, prepared, candidate, providers, packages, intent
    ):
        self.owner()
        assert candidate.recipe_identity.uri == invocation.prepared.recipe.identity
        if self.ports is not None:
            self.ports._record(
                "sdk-intent", self.ports.names[prepared.plan.component_revision.uri]
            )


class _Ports(LifecyclePorts):
    def __call__(self, prepared):
        # The legacy fixture uses typed identity objects for recipes. Adapt its
        # DATA emitter, without changing the production recipe or source gate.
        if isinstance(prepared.recipe.identity, str):
            prepared = replace(
                prepared,
                recipe=_Recipe(
                    ContentIdentity.parse_uri(prepared.recipe.identity),
                    prepared.recipe.component_lock_identity,
                ),
            )
        return super().__call__(prepared)


class NodeSDKLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = generation_fixture.NodeSDKGenerationDataTests()
        self.fixture.setUp()
        self.execution = self.fixture.execution
        self.admission = _Admission(self.fixture)

    def run_owned(self, operation, **changes):
        return run_node_sdk_lifecycle(
            self.admission,
            self.execution,
            self.fixture.prepared,
            (),
            operation,
            **changes,
        )

    def test_source_data_needs_configured_port_and_copied_scope_retires(self):
        bound = self.fixture.bind()
        self.assertFalse(require_node_sdk_source(self.execution, bound.prepared))
        escaped = []

        def run(invocation, guard):
            self.assertTrue(
                require_node_sdk_source(self.execution, invocation.prepared)
            )
            self.assertIsNone(
                StandardProjectLifecycleService._source_generation_candidate(
                    self.execution,
                    invocation.prepared,
                    None,
                    None,
                    None,
                    False,
                )
            )
            escaped.append((copy_context(), guard, invocation.prepared))
            return "data"

        self.assertEqual(self.run_owned(run), "data")
        context, guard, prepared = escaped[0]
        with self.assertRaisesRegex(ValueError, "ended"):
            context.run(guard)
        with self.assertRaises(ValueError):
            context.run(require_node_sdk_source, self.execution, prepared)

    def test_recipe_or_context_drift_is_terminal_even_if_caught(self):
        def run(invocation, guard):
            foreign = replace(invocation.prepared, recipe=self.fixture.prepared.recipe)
            with self.assertRaises(ValueError):
                require_node_sdk_source(self.execution, foreign)
            guard()

        with self.assertRaises(ValueError):
            self.run_owned(run)

    def test_owner_loss_before_source_never_reads_cache(self):
        poison = mock.Mock()
        poison.generation = mock.PropertyMock(side_effect=AssertionError("cache read"))

        def run(invocation, _guard):
            self.admission.alive = False
            return StandardProjectLifecycleService._source_generation_candidate(
                self.execution,
                invocation.prepared,
                poison,
                None,
                None,
                False,
            )

        with self.assertRaisesRegex(ValueError, "owner ended"):
            self.run_owned(run)

    def test_build_intent_calls_original_configured_port(self):
        callback = mock.Mock(return_value=None)
        self.admission.require_build_intent = callback

        def run(invocation, _guard):
            require_node_sdk_build_intent(
                self.execution,
                invocation.prepared,
                "candidate",
                (),
                (),
                "intent",
            )

        self.run_owned(run)
        callback.assert_called_once()

    def configured_service(self, *, root_sdk=False, **ports_options):
        fixture = self.fixture
        if root_sdk:
            fixture = generation_fixture.NodeSDKGenerationDataTests()
            fixture.consumer_name = "invoice-cli"
            fixture.setUp()
        lock = _diamond_lock()
        _, requests = _prepared_execution(lock)
        nodes = _prepared_nodes(self.execution, requests)
        uri = fixture.prepared.plan.component_revision.uri
        nodes[uri] = fixture.prepared
        ports = _Ports(self.execution, _names(lock), **ports_options)
        admission = _Admission(fixture, ports)
        service = _service(ports)
        service.node_sdk_admissions = {uri: admission}
        args = dict(
            component_lock=lock,
            invalidation=_decision(
                self.execution, _names(lock), "money", tuple(_names(lock).values())
            ),
            prepared_nodes=nodes,
            max_parallelism=2,
        )
        return service, ports, admission, args

    def test_root_finalization_owns_every_stage_before_separate_publication(self):
        service, ports, admission, args = self.configured_service(root_sdk=True)
        observed = []
        retired = []
        methods = (
            "assemble_project_artifacts",
            "create_project_package",
            "test_root_integration",
            "execute_packaged_project",
            "accept_project_independently",
        )
        with mock.patch.multiple(
            ports, **{name: mock.DEFAULT for name in methods}
        ) as patched:
            for name in methods:
                original = getattr(type(ports), name).__get__(ports)

                def call(*values, name=name, original=original):
                    guard = capture_node_sdk_lifecycle()
                    self.assertIsNotNone(guard)
                    guard()
                    retired.append(guard)
                    observed.append(name)
                    return original(*values)

                patched[name].side_effect = call
            result = service.execute(self.execution, **args)
        self.assertTrue(result.successful)
        self.assertEqual(observed, list(methods))
        self.assertEqual(admission.calls, 3)
        for guard in retired:
            with self.assertRaises(ValueError):
                guard()
        self.assertLess(
            ports.events.index(("independent-accept", "project")),
            ports.events.index(("publish", "invoice-cli")),
        )

    def test_root_owner_loss_withholds_following_stages_and_publication(self):
        methods = (
            "assemble_project_artifacts",
            "create_project_package",
            "test_root_integration",
            "execute_packaged_project",
            "accept_project_independently",
        )
        for index, name in enumerate(methods):
            with self.subTest(stage=name):
                service, ports, admission, args = self.configured_service(root_sdk=True)
                original = getattr(ports, name)

                def lose(*values, original=original, admission=admission):
                    result = original(*values)
                    admission.alive = False
                    return result

                with mock.patch.object(ports, name, side_effect=lose):
                    with self.assertRaisesRegex(ValueError, "owner ended"):
                        service.execute(self.execution, **args)
                self.assertFalse(any(event[0] == "publish" for event in ports.events))
                for following in methods[index + 1 :]:
                    # No downstream finalization port may run after owner loss.
                    event = {
                        "create_project_package": "create-package",
                        "test_root_integration": "root-integration-test",
                        "execute_packaged_project": "execute-package",
                        "accept_project_independently": "independent-accept",
                    }[following]
                    self.assertNotIn((event, "project"), ports.events)

    def test_root_finalization_rejects_changed_plan_before_packaging(self):
        service, ports, _admission, args = self.configured_service(root_sdk=True)
        original = ports.assemble_project_artifacts

        def assemble(lock, execution, project, ordered):
            result = original(lock, execution, project, ordered)
            object.__setattr__(
                project,
                "execution_plan_identity",
                canonical_identity("foreign execution"),
            )
            return result

        with mock.patch.object(
            ports, "assemble_project_artifacts", side_effect=assemble
        ):
            with self.assertRaisesRegex(StandardProjectLifecycleError, "original lock"):
                service.execute(self.execution, **args)
        self.assertNotIn(("create-package", "project"), ports.events)
        self.assertFalse(any(event[0] == "publish" for event in ports.events))

    def test_root_cache_hit_still_finalizes_inside_fresh_ownership(self):
        service, ports, admission, args = self.configured_service(root_sdk=True)
        first = service.execute(self.execution, **args)
        root = next(
            node
            for node in first.node_results
            if node.component_revision == self.execution.root_revision
        )
        service.node_sdk_source_lookup = lambda *_: root.source_cache_membership
        args["invalidation"] = _decision(self.execution, ports.names, "money")
        ports.events.clear()
        original = ports.create_project_package

        def package(*values):
            guard = capture_node_sdk_lifecycle()
            self.assertIsNotNone(guard)
            guard()
            return original(*values)

        with mock.patch.object(ports, "create_project_package", side_effect=package):
            result = service.execute(self.execution, **args)
        self.assertTrue(result.successful)
        self.assertEqual(admission.calls, 5)
        self.assertNotIn(("generate", "invoice-cli"), ports.events)
        self.assertNotIn(("publish", "invoice-cli"), ports.events)
        self.assertIn(("independent-accept", "project"), ports.events)

    def test_combined_finalizer_runs_under_same_root_owner_and_closes_afterward(self):
        for revoke in (False, True):
            with self.subTest(revoke=revoke):
                service, ports, admission, args = self.configured_service(root_sdk=True)

                def finalize(
                    lock,
                    project,
                    graph,
                    plan,
                    result,
                    *,
                    revoke=revoke,
                    admission=admission,
                ):
                    guard = capture_node_sdk_lifecycle()
                    self.assertIsNotNone(guard)
                    guard()
                    evidence = StandardRootIntegrationEvidence(
                        lock.identity,
                        self.execution.identity,
                        project.identity,
                        graph,
                        graph.link_plans[0],
                        plan,
                        result,
                        canonical_identity("root test"),
                        canonical_identity("packaged exec"),
                        canonical_identity("independent accept"),
                    )
                    if revoke:
                        admission.alive = False
                    return evidence

                service.project_finalizer = SimpleNamespace(finalize=finalize)
                if revoke:
                    with self.assertRaisesRegex(ValueError, "owner ended"):
                        service.execute(self.execution, **args)
                    self.assertFalse(
                        any(event[0] == "publish" for event in ports.events)
                    )
                else:
                    self.assertTrue(service.execute(self.execution, **args).successful)
                    self.assertEqual(admission.calls, 3)

    def test_late_finalization_mutations_cannot_rebind_accepted_metadata(self):
        for stage in ("execute_packaged_project", "accept_project_independently"):
            for mutation in ("graph", "link", "plan-result"):
                with self.subTest(stage=stage, mutation=mutation):
                    service, ports, _admission, args = self.configured_service(
                        root_sdk=True
                    )
                    assembled = []
                    assemble = ports.assemble_project_artifacts
                    original = getattr(ports, stage)

                    def record(*values, assemble=assemble, assembled=assembled):
                        result = assemble(*values)
                        assembled.append(result)
                        return result

                    def mutate(
                        *values,
                        original=original,
                        mutation=mutation,
                        assembled=assembled,
                    ):
                        value = original(*values)
                        graph, link = assembled[-1]
                        if mutation == "graph":
                            object.__setattr__(
                                graph,
                                "build_system_driver_identity",
                                canonical_identity("foreign driver"),
                            )
                        elif mutation == "link":
                            object.__setattr__(
                                link,
                                "root_artifact_identity",
                                canonical_identity("foreign artifact"),
                            )
                        else:
                            plan, result = values[3:5]
                            object.__setattr__(
                                plan,
                                "packager_identity",
                                canonical_identity("foreign packager"),
                            )
                            object.__setattr__(
                                result, "package_plan_identity", plan.identity
                            )
                        return value

                    with (
                        mock.patch.object(
                            ports, "assemble_project_artifacts", side_effect=record
                        ),
                        mock.patch.object(ports, stage, side_effect=mutate),
                    ):
                        with self.assertRaisesRegex(
                            StandardProjectLifecycleError, "after validation"
                        ):
                            service.execute(self.execution, **args)
                    self.assertFalse(
                        any(event[0] == "publish" for event in ports.events)
                    )

    def test_scheduler_waits_for_accept_and_publication_renews_exact_binding(self):
        service, ports, admission, args = self.configured_service()
        result = service.execute(self.execution, **args)
        self.assertTrue(
            result.successful,
            [
                (item.component_revision.uri, item.failure_code)
                for item in result.node_results
            ],
        )
        self.assertLess(
            ports.events.index(("accept", "money")),
            ports.events.index(("generate", "pricing")),
        )
        self.assertEqual(admission.calls, 2)
        self.assertIn(("sdk-intent", "pricing"), ports.events)
        self.assertLess(
            ports.events.index(("independent-accept", "project")),
            ports.events.index(("publish", "pricing")),
        )

    def test_failed_sdk_checkpoint_preserves_bound_recipe_and_original_failure(self):
        service, ports, admission, args = self.configured_service(
            fail_build=("pricing",)
        )
        records = []
        service.checkpoint_recorder = SimpleNamespace(
            record=records.append,
            start_node_sdk_attempt=lambda *args: None,
            start_replacement=lambda *args: None,
        )
        result = service.execute(self.execution, **args)
        self.assertFalse(result.successful)
        revision = self.fixture.prepared.plan.component_revision
        node = next(n for n in result.node_results if n.component_revision == revision)
        self.assertEqual(node.failure_evidence.phase.value, "build")
        self.assertNotEqual(node.failure_code, "lifecycle.failed")
        failed = [
            r
            for r in records
            if r.component_revision == revision and r.failure_code is not None
        ]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0].failure_code, node.failure_code)
        self.assertEqual(
            failed[0].recipe_identity, node.source_output.candidate.recipe_identity
        )
        self.assertNotEqual(
            failed[0].recipe_identity.uri, self.fixture.prepared.recipe.identity
        )

    def test_failed_provider_prevents_sdk_admission_and_generation(self):
        service, ports, admission, args = self.configured_service(fail_build=("money",))
        result = service.execute(self.execution, **args)
        self.assertFalse(result.successful)
        self.assertEqual(admission.calls, 0)
        self.assertNotIn(("generate", "pricing"), ports.events)

    def test_publication_drift_or_owner_loss_withholds_cache_publication(self):
        for failure in ("drift", "revoke_publication"):
            with self.subTest(failure=failure):
                service, ports, admission, args = self.configured_service()
                setattr(admission, failure, True)
                result = service.execute(self.execution, **args)
                self.assertFalse(result.successful)
                self.assertEqual(admission.calls, 2)
                self.assertNotIn(("publish", "pricing"), ports.events)

    def test_checkpoint_recovery_refuses_before_work(self):
        service, ports, _, args = self.configured_service()
        uri = self.fixture.prepared.plan.component_revision.uri
        with self.assertRaisesRegex(
            StandardProjectLifecycleError, "separate qualification"
        ):
            service.execute(
                self.execution,
                source_generation_resume_candidates={uri: object()},
                **args,
            )
        self.assertEqual(ports.events, [])

    def test_exact_cache_hit_still_verifies_owner_without_model_or_republication(self):
        service, ports, admission, args = self.configured_service()
        first = service.execute(self.execution, **args)
        self.assertTrue(first.successful)
        uri = self.fixture.prepared.plan.component_revision.uri
        membership = next(
            item.source_cache_membership
            for item in first.node_results
            if item.component_revision.uri == uri
        )
        ports.events.clear()
        args["invalidation"] = _decision(self.execution, ports.names, "money")
        lookups = []

        def lookup(execution, prepared):
            self.assertTrue(require_node_sdk_source(execution, prepared))
            self.assertIn(("accept", "money"), ports.events)
            self.assertNotIn(("generate", "pricing"), ports.events)
            lookups.append(prepared.recipe.identity)
            return membership

        service.node_sdk_source_lookup = lookup
        second = service.execute(self.execution, **args)
        self.assertTrue(second.successful)
        self.assertEqual(len(lookups), 1)
        self.assertEqual(admission.calls, 3)
        self.assertNotIn(("generate", "pricing"), ports.events)
        self.assertNotIn(("publish", "pricing"), ports.events)
        self.assertIn(("sdk-intent", "pricing"), ports.events)

    def test_fresh_source_skips_deferred_sdk_lookup(self):
        service, ports, _, args = self.configured_service()
        args["invalidation"] = _decision(self.execution, ports.names, "money")
        service.node_sdk_source_lookup = mock.Mock(
            side_effect=AssertionError("cache used")
        )
        result = service.execute(
            self.execution, skip_node_sdk_cache_lookup=True, **args
        )
        self.assertTrue(result.successful)
        service.node_sdk_source_lookup.assert_not_called()
        self.assertIn(("generate", "pricing"), ports.events)

    def test_actual_repair_adapter_keeps_binding_and_uses_fresh_request_workspace(self):
        self.assert_actual_repair(cache_hit=False)

    def test_cache_hit_repaired_head_is_published_as_current_membership(self):
        self.assert_actual_repair(cache_hit=True)

    def assert_actual_repair(self, *, cache_hit):
        with tempfile.TemporaryDirectory() as raw:
            workspace = Path(raw).resolve() / "initial"
            workspace.mkdir()
            self.fixture.prepared = replace(
                self.fixture.prepared,
                workspace=replace(
                    self.fixture.prepared.workspace, locator=str(workspace)
                ),
            )
            service, ports, admission, args = self.configured_service()
            service.candidate_repair_port = FilesystemStandardCandidateRepairAdapter({})
            uri = self.fixture.prepared.plan.component_revision.uri
            original_membership = None
            if cache_hit:
                baseline = service.execute(self.execution, **args)
                self.assertTrue(baseline.successful)
                original_membership = next(
                    item.source_cache_membership
                    for item in baseline.node_results
                    if item.component_revision.uri == uri
                )
                ports.events.clear()
                args["invalidation"] = _decision(self.execution, ports.names, "money")
                service.node_sdk_source_lookup = lambda *_: original_membership
            original = ports.build
            failed = []

            def build(plan, providers):
                if ports.names[plan.component_revision.uri] == "pricing" and not failed:
                    failed.append(True)
                    raise StandardProjectLifecycleError(
                        "builder.generated-source-rejected",
                        "fixture generated build rejection",
                    )
                return original(plan, providers)

            with mock.patch.object(ports, "build", side_effect=build):
                result = service.execute(self.execution, **args)
            self.assertTrue(
                result.successful,
                [
                    (ports.names[item.component_revision.uri], item.failure_code)
                    for item in result.node_results
                ],
            )
            chain = next(
                item
                for item in result.candidate_attempt_chains
                if item.component_revision.uri == uri
            )
            self.assertEqual(len(chain.attempts), 2)
            self.assertNotEqual(
                chain.attempts[0].workspace_allocation_identity,
                chain.attempts[1].workspace_allocation_identity,
            )
            self.assertNotEqual(
                chain.attempts[0].generation_request_identity,
                chain.attempts[1].generation_request_identity,
            )
            self.assertEqual(admission.calls, 4 if cache_hit else 2)
            self.assertEqual(
                ports.events.count(("generate", "pricing")), 1 if cache_hit else 2
            )
            winner = next(
                item
                for item in result.node_results
                if item.component_revision.uri == uri
            )
            self.assertIn(("publish", "pricing"), ports.events)
            self.assertEqual(
                ports.published_memberships[uri], winner.source_cache_membership
            )
            if cache_hit:
                self.assertNotEqual(
                    original_membership.identity,
                    winner.source_cache_membership.identity,
                )


if __name__ == "__main__":
    unittest.main()

    def test_finalization_capture_requires_exact_live_invocation_and_retires(self):
        escaped = []

        def operation(invocation, _guard):
            live, close = capture_node_sdk_finalization(self.execution, invocation)
            live()
            close()
            escaped.extend((live, close))
            return "owned"

        self.assertEqual(self.run_owned(operation), "owned")
        for callback in escaped:
            with self.assertRaises(ValueError):
                callback()
        with self.assertRaises(ValueError):
            capture_node_sdk_finalization(self.execution, self.fixture.bind())

    def test_finalization_foreign_invocation_is_terminal_even_when_caught(self):
        def operation(invocation, guard):
            foreign = replace(invocation, base_recipe=canonical_identity("foreign"))
            with self.assertRaises(ValueError):
                capture_node_sdk_finalization(self.execution, foreign)
            guard()

        with self.assertRaises(ValueError):
            self.run_owned(operation)
