"""Durable SDK checkpoint DATA controls; no model or native SDK qualification."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters.cache.standard_checkpoint import (
    FilesystemStandardLifecycleCheckpointStore,
    StandardLifecycleCheckpointError,
)
from literate_ai.application.standard_node_sdk_admission import run_node_sdk_lifecycle
from literate_ai.contracts import ContentIdentity, StandardLifecycleStage
from tests.smoke import test_node_sdk_generation as data_fixture
from tests.smoke import test_standard_project_lifecycle as lifecycle
from tests.support.fixtures_test_component_execution_planning import _diamond_lock
from tests.support.fixtures_test_component_generation_scheduling import (
    _prepared_execution,
)


class SDKCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.data = data_fixture.NodeSDKGenerationDataTests()
        self.data.setUp()
        self.execution = self.data.execution
        self.prepared = self.data.prepared
        self.bound = self.data.bind()
        owner = tempfile.TemporaryDirectory()
        self.addCleanup(owner.cleanup)
        self.root = Path(owner.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "fixture.txt").write_text("typed fixture checkpoint source")
        self.store = self.new_store()
        _, requests = _prepared_execution(_diamond_lock())
        self.nodes = lifecycle._prepared_nodes(self.execution, requests)
        self.nodes[self.prepared.plan.component_revision.uri] = self.prepared
        self.store.start_attempt(self.execution, self.nodes)
        self.names = {
            p.component_revision.uri: "fixture" for p in self.execution.generation_plans
        }
        self.ports = lifecycle.LifecyclePorts(self.execution, self.names)
        self.service = lifecycle._service(self.ports, checkpoint_recorder=self.store)
        self.live = True
        self.admission = mock.Mock()
        self.admission.require_build_intent = lambda *args: None
        self.admission.with_invocation = (
            lambda execution, prepared, receipts, *, consume, expected: consume(
                self.bound, self.guard
            )
        )

    def new_store(self):
        return FilesystemStandardLifecycleCheckpointStore(
            self.root / "checkpoints",
            source_root=lambda identity: self.source,
            source_trees=mock.Mock(),
        )

    def guard(self):
        if not self.live:
            raise ValueError("fixture SDK owner ended")

    def scope(self, operation):
        return run_node_sdk_lifecycle(
            self.admission, self.execution, self.prepared, {}, operation
        )

    def start(self):
        return self.store.start_node_sdk_attempt(
            self.execution, self.prepared, self.bound
        )

    def stage(self):
        prepared = self.bound.prepared
        # Reuse typed source DATA fixtures with the bound CID, never retag an
        # actual generated candidate or bypass a production generator.
        typed = replace(
            prepared,
            recipe=lifecycle._Recipe(
                ContentIdentity.parse_uri(prepared.recipe.identity),
                self.execution.component_lock_identity,
            ),
        )
        output = self.ports(typed)
        self.service._record_stage(
            self.execution,
            prepared.plan,
            prepared,
            output,
            StandardLifecycleStage.SOURCE_GENERATION,
            output.identity,
        )

    def test_defers_static_sdk_attempt_then_records_exact_bound_stage(self):
        revision = self.prepared.plan.component_revision
        self.assertIsNone(self.store.latest_attempt(self.execution.identity, revision))

        def run(invocation, guard):
            self.start()
            self.stage()

        self.scope(run)
        attempt = self.store.latest_attempt(self.execution.identity, revision)
        head = self.store.latest(self.execution.identity, revision)
        self.assertEqual(
            attempt.recipe_identity.uri, self.bound.prepared.recipe.identity
        )
        self.assertEqual(head.attempt_evidence.identity, attempt.identity)
        self.assertEqual(head.evidence.recipe_identity, attempt.recipe_identity)

    def test_record_before_binding_and_data_without_live_scope_refuse(self):
        with self.assertRaisesRegex(StandardLifecycleCheckpointError, "not started"):
            self.stage()
        with self.assertRaisesRegex(StandardLifecycleCheckpointError, "live admission"):
            self.start()

    def test_copied_preparation_or_execution_cannot_consume_pending_node(self):
        for field in ("prepared", "execution"):
            with self.subTest(field=field):

                def run(invocation, guard, field=field):
                    with self.assertRaisesRegex(
                        StandardLifecycleCheckpointError, "original pending"
                    ):
                        self.store.start_node_sdk_attempt(
                            replace(self.execution)
                            if field == "execution"
                            else self.execution,
                            replace(self.prepared)
                            if field == "prepared"
                            else self.prepared,
                            invocation,
                        )

                self.store.start_attempt(self.execution, self.nodes)
                self.scope(run)
        self.store.start_attempt(self.execution, self.nodes)
        self.scope(lambda invocation, guard: self.start())

    def test_duplicate_binding_refuses_without_advancing_attempt(self):
        def run(invocation, guard):
            self.start()
            with self.assertRaisesRegex(
                StandardLifecycleCheckpointError, "not pending"
            ):
                self.start()

        self.scope(run)
        self.assertEqual(
            self.store.latest_attempt(
                self.execution.identity, self.prepared.plan.component_revision
            ).attempt,
            1,
        )

    def test_restart_preserves_previous_bound_attempt_and_stage_lineage(self):
        self.scope(lambda invocation, guard: (self.start(), self.stage()))
        revision = self.prepared.plan.component_revision
        previous = self.store.latest_attempt(self.execution.identity, revision)
        stage = self.store.latest(self.execution.identity, revision)
        self.store = self.new_store()
        self.service.checkpoint_recorder = self.store
        self.store.start_attempt(self.execution, self.nodes)
        self.scope(lambda invocation, guard: self.start())
        current = self.store.latest_attempt(self.execution.identity, revision)
        self.assertEqual(current.attempt, previous.attempt + 1)
        self.assertEqual(current.predecessor_attempt_identity, previous.identity)
        self.assertEqual(current.source_predecessor_identity, stage.identity)
        self.assertEqual(
            self.store.latest(self.execution.identity, revision).identity,
            stage.identity,
        )

    def test_repair_starts_new_attempt_with_same_bound_recipe(self):
        self.scope(lambda invocation, guard: self.start())
        revision = self.prepared.plan.component_revision
        first = self.store.latest_attempt(self.execution.identity, revision)
        self.store.start_replacement(self.execution.identity, revision)
        second = self.store.latest_attempt(self.execution.identity, revision)
        self.assertEqual(second.recipe_identity, first.recipe_identity)
        self.assertEqual(second.predecessor_attempt_identity, first.identity)

    def test_owner_loss_after_publication_withholds_generation(self):
        original = self.store._publish_attempt

        def lose_owner(*args):
            original(*args)
            self.live = False

        with (
            mock.patch.object(self.store, "_publish_attempt", side_effect=lose_owner),
            mock.patch.object(self.service, "_run_complete_node") as generation,
        ):
            with self.assertRaisesRegex(ValueError, "owner ended"):
                self.service._run_node_sdk(
                    self.admission,
                    {},
                    self.execution,
                    self.prepared.plan,
                    self.prepared,
                    None,
                    None,
                    None,
                    (),
                    (),
                    True,
                )
            generation.assert_not_called()
        self.assertIsNotNone(
            self.store.latest_attempt(
                self.execution.identity, self.prepared.plan.component_revision
            )
        )

    def test_publication_mutation_withholds_generation_and_retains_attempt(self):
        for field in ("definition", "workspace"):
            with self.subTest(field=field):
                self.store.start_attempt(self.execution, self.nodes)
                original = getattr(self.prepared, field)
                published = self.store._publish_attempt

                def mutate_after_publication(
                    *args, field=field, published=published, original=original
                ):
                    published(*args)
                    changed = (
                        object()
                        if field == "definition"
                        else replace(original, locator=original.locator + "-changed")
                    )
                    object.__setattr__(self.prepared, field, changed)
                    object.__setattr__(self.bound.prepared, field, changed)

                lookup = mock.Mock()
                try:
                    with (
                        mock.patch.object(
                            self.store,
                            "_publish_attempt",
                            side_effect=mutate_after_publication,
                        ),
                        mock.patch.object(
                            self.service, "_run_complete_node"
                        ) as generation,
                    ):
                        with self.assertRaisesRegex(
                            StandardLifecycleCheckpointError, "original pending"
                        ):
                            self.service._run_node_sdk(
                                self.admission,
                                {},
                                self.execution,
                                self.prepared.plan,
                                self.prepared,
                                None,
                                None,
                                None,
                                (),
                                (),
                                False,
                                source_lookup=lookup,
                            )
                        lookup.assert_not_called()
                        generation.assert_not_called()
                finally:
                    object.__setattr__(self.prepared, field, original)
                    object.__setattr__(self.bound.prepared, field, original)
                self.assertIsNotNone(
                    self.store.latest_attempt(
                        self.execution.identity, self.prepared.plan.component_revision
                    )
                )

    def test_owner_loss_before_binding_leaves_no_sdk_attempt(self):
        self.live = False
        with self.assertRaisesRegex(ValueError, "owner ended"):
            self.scope(lambda invocation, guard: self.start())
        self.assertIsNone(
            self.store.latest_attempt(
                self.execution.identity, self.prepared.plan.component_revision
            )
        )

    def test_changed_durable_predecessor_refuses_pending_binding(self):
        other = self.new_store()
        other.start_attempt(self.execution, self.nodes)
        self.scope(
            lambda invocation, guard: other.start_node_sdk_attempt(
                self.execution, self.prepared, invocation
            )
        )
        with self.assertRaisesRegex(
            StandardLifecycleCheckpointError, "original pending"
        ):
            self.scope(lambda invocation, guard: self.start())
        self.assertEqual(
            other.latest_attempt(
                self.execution.identity, self.prepared.plan.component_revision
            ).attempt,
            1,
        )

    def test_sdk_checkpoint_record_does_not_enable_historical_recovery(self):
        self.scope(lambda invocation, guard: (self.start(), self.stage()))
        with mock.patch.object(
            self.store,
            "_materialize",
            side_effect=AssertionError("SDK checkpoint recovery entered"),
        ):
            for prepared in (self.prepared, self.bound.prepared):
                self.assertIsNone(self.store.restore_prepared(self.execution, prepared))

    def assert_rejected_before_generation(self):
        def durable_heads():
            return {
                p.relative_to(self.store.root).as_posix(): p.read_bytes()
                for root in (self.store.heads, self.store.attempt_heads)
                for p in root.iterdir()
                if p.is_file()
            }

        before = durable_heads()
        lookup = mock.Mock()
        with mock.patch.object(self.service, "_run_complete_node") as generation:
            with self.assertRaises((StandardLifecycleCheckpointError, ValueError)):
                self.service._run_node_sdk(
                    self.admission,
                    {},
                    self.execution,
                    self.prepared.plan,
                    self.prepared,
                    None,
                    None,
                    None,
                    (),
                    (),
                    False,
                    source_lookup=lookup,
                )
            lookup.assert_not_called()
            generation.assert_not_called()
        self.assertEqual(durable_heads(), before)
        self.assertIsNone(
            self.store.latest_attempt(
                self.execution.identity, self.prepared.plan.component_revision
            )
        )

    def test_pending_workspace_and_definition_mutation_before_admission_refuse(self):
        for field in ("workspace", "definition", "plan"):
            with self.subTest(field=field):
                self.store.start_attempt(self.execution, self.nodes)
                target = (
                    self.prepared.workspace if field == "workspace" else self.prepared
                )
                name = "locator" if field == "workspace" else field
                original = getattr(target, name)
                replacement = (
                    original + "-changed"
                    if field == "workspace"
                    else replace(original)
                    if field == "plan"
                    else object()
                )
                bound_original = (
                    getattr(self.bound.prepared, field)
                    if field != "workspace"
                    else None
                )
                try:
                    object.__setattr__(target, name, replacement)
                    if field != "workspace":
                        object.__setattr__(self.bound.prepared, field, replacement)
                    self.assert_rejected_before_generation()
                finally:
                    object.__setattr__(target, name, original)
                    if field != "workspace":
                        object.__setattr__(self.bound.prepared, field, bound_original)

    def test_foreign_component_or_generation_key_refuses_pending_binding(self):
        plan = self.prepared.plan
        other = next(
            p
            for p in self.execution.generation_plans
            if p.component_revision != plan.component_revision
        )
        for field in ("component_revision", "generation_key"):
            with self.subTest(field=field):
                self.store.start_attempt(self.execution, self.nodes)
                original = getattr(plan, field)
                try:
                    object.__setattr__(plan, field, getattr(other, field))
                    self.assert_rejected_before_generation()
                finally:
                    object.__setattr__(plan, field, original)

    def test_second_live_callback_mutation_cannot_change_pending_preparation(self):
        from literate_ai.adapters.cache import standard_checkpoint as module

        original = module.require_node_sdk_source
        calls = 0
        prior = self.prepared.definition

        def mutate(execution, prepared):
            nonlocal calls
            result = original(execution, prepared)
            calls += 1
            if calls == 2:
                changed = object()
                object.__setattr__(self.prepared, "definition", changed)
                object.__setattr__(self.bound.prepared, "definition", changed)
            return result

        try:
            with mock.patch.object(
                module, "require_node_sdk_source", side_effect=mutate
            ):
                self.assert_rejected_before_generation()
            self.assertEqual(calls, 2)
        finally:
            object.__setattr__(self.prepared, "definition", prior)
            object.__setattr__(self.bound.prepared, "definition", prior)

    def test_changed_bound_resolved_input_prefix_refuses(self):
        original = self.bound.prepared.recipe
        changed = replace(
            original,
            resolved_inputs=(
                ("foreign-prefix", self.bound.profile.uri),
                *original.resolved_inputs,
            ),
        )
        object.__setattr__(self.bound.prepared, "recipe", changed)
        try:
            self.assert_rejected_before_generation()
        finally:
            object.__setattr__(self.bound.prepared, "recipe", original)

    def test_swallowed_recursive_start_reset_or_replacement_poisons_binding(self):
        from literate_ai.adapters.cache import standard_checkpoint as module

        original = module.require_node_sdk_source
        for action in ("bind", "reset", "replace"):
            with self.subTest(action=action):
                self.store.start_attempt(self.execution, self.nodes)
                entered = False

                def recurse(execution, prepared, action=action):
                    nonlocal entered
                    result = original(execution, prepared)
                    if not entered:
                        entered = True
                        try:
                            if action == "bind":
                                self.start()
                            elif action == "reset":
                                self.store.start_attempt(self.execution, self.nodes)
                            else:
                                self.store.start_replacement(
                                    self.execution.identity,
                                    self.prepared.plan.component_revision,
                                )
                        except StandardLifecycleCheckpointError:
                            pass
                    return result

                with mock.patch.object(
                    module, "require_node_sdk_source", side_effect=recurse
                ):
                    self.assert_rejected_before_generation()

    def test_ordinary_attempts_are_published_before_execution(self):
        for prepared in self.nodes.values():
            if prepared is self.prepared:
                continue
            attempt = self.store.latest_attempt(
                self.execution.identity, prepared.plan.component_revision
            )
            self.assertEqual(attempt.recipe_identity, prepared.recipe.identity)
            self.assertEqual(attempt.attempt, 1)
