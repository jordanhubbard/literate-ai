"""Deterministic injected-port scheduling; no native/generated SDK qualification.

The admission double is a trusted host port, not a provider-verification fixture.
Real provider/oracle/grant custody is covered separately by node_sdk_admission.
"""

import tempfile
import unittest
from contextvars import copy_context
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters.candidate_repair import (
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.application.standard_node_sdk_admission import (
    require_node_sdk_build_intent,
    require_node_sdk_source,
    run_node_sdk_lifecycle,
)
from literate_ai.application.standard_project_lifecycle import (
    StandardProjectLifecycleError,
    StandardProjectLifecycleService,
)
from literate_ai.contracts import ContentIdentity, canonical_identity
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
            assert ("accept", "money") in self.ports.events
            self.ports._record("sdk-admission", "pricing")
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
            self.ports._record("sdk-intent", "pricing")


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

    def configured_service(self, **ports_options):
        lock = _diamond_lock()
        _, requests = _prepared_execution(lock)
        nodes = _prepared_nodes(self.execution, requests)
        uri = self.fixture.prepared.plan.component_revision.uri
        nodes[uri] = self.fixture.prepared
        ports = _Ports(self.execution, _names(lock), **ports_options)
        admission = _Admission(self.fixture, ports)
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
